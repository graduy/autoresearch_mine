from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .card import load_card
from .io import read_json
from .ledger import Ledger
from .research_gate import gate_snapshot, is_human_gated


TERMINAL_STATES = {"candidate_rejected", "human_approval", "complete"}


def _project(root: Path) -> dict[str, Any]:
    return read_json(root / "config" / "project.json")


def _card(root: Path, experiment_id: str) -> dict[str, Any]:
    return load_card(root / "experiments" / "cards" / f"{experiment_id}.json")


def _runs_by_stage(runs: list[dict[str, Any]], stage: str) -> list[dict[str, Any]]:
    return [run for run in runs if run.get("stage") == stage]


def _kept(runs: list[dict[str, Any]], stage: str) -> list[dict[str, Any]]:
    return [run for run in _runs_by_stage(runs, stage) if run.get("status") == "keep" and run.get("metric") is not None]


def _completed(runs: list[dict[str, Any]], stage: str) -> list[dict[str, Any]]:
    return [run for run in _runs_by_stage(runs, stage)
            if run.get("status") in {"keep", "candidate", "discard"} and run.get("metric") is not None]


def _failed_only(runs: list[dict[str, Any]], stage: str) -> bool:
    stage_runs = _runs_by_stage(runs, stage)
    return bool(stage_runs) and not _kept(runs, stage) and all(
        run.get("status") in {"crash", "contested_crash", "budget_violation", "integrity_failure"}
        for run in stage_runs
    )


def _candidate_rejected(runs: list[dict[str, Any]], stage: str) -> bool:
    stage_runs = _runs_by_stage(runs, stage)
    return bool(stage_runs) and not _kept(runs, stage) and any(run.get("status") == "discard" for run in stage_runs)


def _stage_ready_after(
    card: dict[str, Any],
    runs: list[dict[str, Any]],
    stage: str,
    reference_runs: list[dict[str, Any]] | None = None,
) -> tuple[bool, str | None]:
    """Return whether a stage may run and explain the first unmet dependency."""
    stages = card["stages"]
    if stage == "baseline":
        return True, None
    if stage == "pilot":
        if "baseline" in stages and not _kept(runs, "baseline"):
            return False, "a valid baseline keep is required before pilot"
        if "baseline" not in stages and card.get("reference_experiment_id"):
            if not _kept(reference_runs or [], "baseline"):
                return False, "the referenced baseline experiment needs a valid baseline keep before pilot"
        elif "baseline" not in stages and card.get("reference_metric") is None:
            return False, "pilot needs either a valid baseline or a locked reference_metric"
        return True, None
    if stage == "full":
        predecessor = "pilot" if "pilot" in stages else "baseline"
        if predecessor == "baseline" and predecessor not in stages and card.get("reference_metric") is None:
            return False, "full needs a valid pilot or baseline reference"
        if predecessor in stages and not _kept(runs, predecessor):
            return False, f"a valid {predecessor} keep is required before full"
        return True, None
    if stage == "multi_seed":
        predecessor = "full" if "full" in stages else ("pilot" if "pilot" in stages else "baseline")
        if predecessor in stages and not _kept(runs, predecessor):
            return False, f"a valid {predecessor} keep is required before multi_seed"
        if predecessor not in stages and card.get("reference_metric") is None:
            return False, "multi_seed needs a valid preceding result or locked reference_metric"
        return True, None
    return False, f"unsupported stage: {stage}"


def state(root: str | Path, experiment_id: str) -> dict[str, Any]:
    root = Path(root).resolve()
    card = _card(root, experiment_id)
    project = _project(root)
    ledger = Ledger(root / project["ledger_path"])
    runs = ledger.runs(experiment_id)
    reference_runs = ledger.runs(card["reference_experiment_id"]) if card.get("reference_experiment_id") else []
    approval = ledger.latest_approval(experiment_id)
    report_path = root / "reports" / f"{experiment_id}-draft.md"
    archive_path = root / "artifacts" / "archives" / experiment_id
    gates = gate_snapshot(root, card, runs)

    base = {
        "experiment_id": experiment_id,
        "approval": approval,
        "runs": runs,
        "report_path": str(report_path),
        "archive_path": str(archive_path),
        "evidence": {
            "baseline_keep": bool(_kept(runs, "baseline")),
            "pilot_keep": bool(_kept(runs, "pilot")),
            "full_keep": bool(_kept(runs, "full")),
            "multi_seed_keep_count": len(_kept(runs, "multi_seed")),
            "declared_seeds": card.get("seeds", []),
        },
        "gates": gates,
    }

    if is_human_gated(card, root):
        package_gate = gates["innovation_package"]
        if not package_gate["valid"]:
            return {**base, "state": "innovation_package", "next_stage": None,
                    "next_action": "complete the literature synthesis, innovation direction, compute estimate, architecture draft, and verification/ablation matrix",
                    "blockers": package_gate["errors"]}
        innovation_gate = gates["innovation_review"]
        if not innovation_gate["valid"]:
            return {**base, "state": "human_innovation_review", "next_stage": None,
                    "next_action": "manually edit and approve the innovation package, then record its file hashes",
                    "blockers": innovation_gate["errors"]}
        allocation_gate = gates["compute_allocation"]
        if not allocation_gate["valid"]:
            return {**base, "state": "human_compute_allocation", "next_stage": None,
                    "next_action": "record the exact human-provided GPU, runtime, run-count, VRAM, and cost allocation",
                    "blockers": allocation_gate["errors"]}

    if not approval or approval.get("decision") != "approve":
        return {**base, "state": "human_approval", "next_stage": None,
                "next_action": "record an explicit human approval before execution",
                "blockers": ["latest approval is missing or is not approve"]}

    configured = [stage for stage in ("baseline", "pilot", "full", "multi_seed") if stage in card["stages"]]
    for stage in configured:
        kept = _kept(runs, stage)
        if stage == "baseline":
            declared = card.get("baseline_seeds", [])
        elif stage == "full":
            declared = card.get("full_seeds", [])
        elif stage == "multi_seed":
            declared = card.get("seeds", [])
        else:
            declared = []
        if declared:
            completed_seeds = {run.get("seed") for run in _completed(runs, stage)}
            if declared and all(seed in completed_seeds for seed in declared):
                continue
        elif kept:
            continue

        ready, reason = _stage_ready_after(card, runs, stage, reference_runs)
        if not ready:
            return {**base, "state": "blocked", "next_stage": stage,
                    "next_action": "resolve the stage dependency",
                    "blockers": [reason] if reason else ["stage dependency is not satisfied"]}
        if _candidate_rejected(runs, stage) and (
            not declared or all(seed in {run.get("seed") for run in _completed(runs, stage)} for seed in declared)
        ) and not kept:
            return {**base, "state": "candidate_rejected", "next_stage": None,
                    "next_action": "revise the experiment card or create a new candidate before rerunning",
                    "blockers": [f"{stage} produced a discard; the same candidate is not rerun automatically"]}
        action = f"run {stage}"
        if _failed_only(runs, stage):
            action = f"repair or retry {stage} after reviewing the recorded failure"
        return {**base, "state": stage, "next_stage": stage,
                "next_action": action, "blockers": []}

    if is_human_gated(card, root):
        conclusion_gate = gates["conclusion_review"]
        if not conclusion_gate["valid"]:
            return {**base, "state": "conclusion_review", "next_stage": None,
                    "next_action": "manually verify the evidence-backed conclusions before writing the paper drafts",
                    "blockers": conclusion_gate["errors"]}
        package = root / "deliverables" / experiment_id
        draft_paths = [package / "paper_draft_zh.md", package / "paper_draft_en.md"]
        if not all(path.is_file() for path in draft_paths):
            return {**base, "state": "paper_draft", "next_stage": None,
                    "next_action": "generate the Chinese and English first drafts from the approved conclusions",
                    "blockers": [f"missing paper draft: {path}" for path in draft_paths if not path.is_file()]}
    elif not report_path.exists():
        return {**base, "state": "report_draft", "next_stage": None,
                "next_action": "generate the evidence-bound report draft", "blockers": []}
    if not archive_path.exists():
        return {**base, "state": "archive", "next_stage": None,
                "next_action": "archive the card, code snapshot, environment, runs, and receipts", "blockers": []}
    return {**base, "state": "complete", "next_stage": None,
            "next_action": "no required workflow step remains", "blockers": []}


def assert_stage_ready(root: str | Path, experiment_id: str, stage: str) -> dict[str, Any]:
    current = state(root, experiment_id)
    if current.get("next_stage") != stage:
        reason = "; ".join(current.get("blockers") or [current.get("next_action", "stage is not ready")])
        raise RuntimeError(f"workflow gate blocked {stage}: {reason}")
    return current


def validate_ingest(root: str | Path, experiment_id: str, result_path: str | Path) -> dict[str, Any]:
    """Validate a child-run result without allowing it to invent a ledger row."""
    root = Path(root).resolve()
    payload = json.loads(Path(result_path).read_text(encoding="utf-8"))
    required = {"run_id", "experiment_id", "stage", "status", "receipt_path"}
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"ingest result missing fields: {', '.join(missing)}")
    if payload["experiment_id"] != experiment_id:
        raise ValueError("ingest result experiment_id does not match the requested experiment")
    ledger = Ledger(root / _project(root)["ledger_path"])
    run = ledger.run(str(payload["run_id"]))
    if run is None:
        raise ValueError("ingest result refers to an unknown run_id")
    if run["experiment_id"] != experiment_id or run["stage"] != payload["stage"]:
        raise ValueError("ingest result does not match the ledger run")
    receipt = Path(payload["receipt_path"])
    if not receipt.is_absolute():
        receipt = root / receipt
    if not receipt.is_file():
        raise ValueError("ingest result receipt_path does not exist")
    receipt_data = json.loads(receipt.read_text(encoding="utf-8"))
    if receipt_data.get("status") != run.get("status"):
        raise ValueError("ingest result and integrity receipt status disagree with the ledger")
    ledger.event(experiment_id, "child_result_ingested", {
        "run_id": run["run_id"], "stage": run["stage"], "status": run["status"],
        "receipt_path": str(receipt),
    }, run_id=run["run_id"])
    return {"valid": True, "run_id": run["run_id"], "status": run["status"], "receipt_path": str(receipt)}
