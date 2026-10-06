"""Human review contracts for literature-to-paper research.

Review records are provenance assertions backed by the actual user message;
JSON flags alone cannot authenticate that a human performed a review.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from .io import read_json
from .ledger import Ledger

HUMAN_GATED_WORKFLOW = "human_gated_research_to_paper"
PACKAGE_FIELDS = (
    "literature_synthesis", "innovation_proposal", "compute_budget",
    "experiment_matrix", "architecture_spec", "architecture_draft",
)
REVIEW_FIELDS = ("innovation", "compute", "conclusion")
WAITING_STATES = {
    "innovation_package", "human_innovation_review", "human_compute_allocation",
    "human_approval", "blocked", "candidate_rejected", "experiment_matrix",
    "conclusion_review", "paper_draft",
}


def is_human_gated(card: dict[str, Any], root: str | Path | None = None) -> bool:
    # New cards opt in explicitly. Existing cards are listed in the policy file
    # so an old run is not silently reclassified after the workflow changes.
    if card.get("workflow_mode") == HUMAN_GATED_WORKFLOW:
        return True
    if card.get("workflow_mode") in {"legacy", "historical"}:
        return False
    historical: list[str] = []
    if root is not None:
        config = Path(root) / "config/research_policy.json"
        if config.is_file():
            historical = read_json(config).get("historical_experiments", [])
    return False if card.get("experiment_id") in historical else bool(card.get("task_id") and card.get("research_package"))


def resolve(root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def file_hash(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _json(path: Path | None, label: str, errors: list[str]) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        errors.append(f"{label}: file does not exist ({path})")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: invalid JSON ({exc})")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label}: JSON root must be an object")
        return None
    return value


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _number(value: Any, *, positive: bool = False, integer: bool = False) -> bool:
    return (type(value) in (int, float) and math.isfinite(value)
            and (value > 0 if positive else value >= 0)
            and (not integer or value == int(value)))


def _placeholder(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(_placeholder(item) for item in value)
    return isinstance(value, str) and value.strip().casefold() in {"tbd", "待定", "待补充", "to be determined"}


def package_paths(root: str | Path, card: dict[str, Any]) -> dict[str, Path | None]:
    package = card.get("research_package", {})
    if not isinstance(package, dict):
        package = {}
    return {field: resolve(Path(root).resolve(), package.get(field)) for field in PACKAGE_FIELDS}


def review_paths(root: str | Path, card: dict[str, Any]) -> dict[str, Path | None]:
    reviews = card.get("human_reviews", {})
    if not isinstance(reviews, dict):
        reviews = {}
    return {field: resolve(Path(root).resolve(), reviews.get(field)) for field in REVIEW_FIELDS}


def _result(errors: list[str], **extra: Any) -> dict[str, Any]:
    return {"valid": not errors, "errors": errors, **extra}


def validate_innovation_package(root: str | Path, card: dict[str, Any]) -> dict[str, Any]:
    root = Path(root).resolve()
    paths = package_paths(root, card)
    errors: list[str] = []
    hashes: dict[str, str] = {}
    for field, path in paths.items():
        if path is None or not path.is_file() or not path.stat().st_size:
            errors.append(f"research package file is missing or empty: {field} ({path})")
        else:
            hashes[field] = file_hash(path)
    for field in ("literature_synthesis", "innovation_proposal", "architecture_spec"):
        path = paths[field]
        if path and path.is_file():
            try:
                content = path.read_text(encoding="utf-8").strip()
                if not content or _placeholder(content):
                    errors.append(f"{field}: actual content is required")
            except (OSError, UnicodeDecodeError) as exc:
                errors.append(f"{field}: unreadable text ({exc})")
    # Verify a supported image signature, not its scientific correctness.
    draft = paths["architecture_draft"]
    if draft and draft.is_file():
        head = draft.read_bytes()[:12]
        if not (head.startswith(b"\x89PNG\r\n\x1a\n") or head.startswith(b"\xff\xd8\xff")
                or (head.startswith(b"RIFF") and head[8:12] == b"WEBP")):
            errors.append("architecture_draft must be a PNG, JPEG, or WebP raster for human review")
    budget = _json(paths["compute_budget"], "compute_budget", errors)
    if budget is not None:
        for key in ("estimated_gpu_hours", "estimated_runs"):
            if not _number(budget.get(key), positive=True, integer=key == "estimated_runs"):
                errors.append(f"compute_budget.{key}: positive finite {'integer' if key == 'estimated_runs' else 'number'} required")
        if not _text(budget.get("assumptions")):
            errors.append("compute_budget.assumptions is required")
        if _placeholder(budget):
            errors.append("compute_budget contains a placeholder")
    matrix = _json(paths["experiment_matrix"], "experiment_matrix", errors)
    rows = matrix.get("rows") if matrix is not None else None
    if not isinstance(rows, list) or not rows:
        errors.append("experiment_matrix.rows must be a non-empty list")
        rows = []
    ids: set[str] = set()
    categories: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"experiment_matrix row {index} must be an object")
            continue
        for key in ("id", "category", "hypothesis", "control", "change", "metric", "pass_rule", "experiment_id", "stage"):
            if not _text(row.get(key)):
                errors.append(f"experiment_matrix row {index} needs {key}")
        category = row.get("category")
        if category not in {"verification", "ablation"}:
            errors.append(f"experiment_matrix row {index}: category must be verification or ablation")
        else:
            categories.add(category)
        if category == "ablation" and not _text(row.get("component")):
            errors.append(f"experiment_matrix ablation row {index} needs component")
        row_id = row.get("id")
        if isinstance(row_id, str):
            if row_id in ids:
                errors.append(f"duplicate experiment_matrix id: {row_id}")
            ids.add(row_id)
        if row.get("stage") not in {"baseline", "pilot", "full", "multi_seed"}:
            errors.append(f"experiment_matrix row {index}: invalid execution stage")
        seeds = row.get("seeds")
        if not isinstance(seeds, list) or not seeds or not all(type(seed) is int for seed in seeds) or len(set(seeds)) != len(seeds):
            errors.append(f"experiment_matrix row {index}: unique integer seeds are required")
        exp_id = row.get("experiment_id")
        if _text(exp_id) and (Path(exp_id).name != exp_id or exp_id in {".", ".."}):
            errors.append(f"experiment_matrix row {index}: invalid experiment ID")
        elif _text(exp_id):
            target = root / "experiments/cards" / f"{exp_id}.json"
            if not target.is_file():
                errors.append(f"experiment_matrix row {index}: card is not registered ({exp_id})")
            else:
                declared = _json(target, f"matrix card {exp_id}", errors)
                if declared and row.get("stage") not in declared.get("stages", {}):
                    errors.append(f"matrix stage is absent from card {exp_id}")
                if declared and row.get("metric") != declared.get("primary_metric"):
                    errors.append(f"matrix metric differs from card {exp_id}")
    for category in ("verification", "ablation"):
        if category not in categories:
            errors.append(f"experiment_matrix needs at least one {category} row")
    if matrix is not None and _placeholder(matrix):
        errors.append("experiment_matrix contains a placeholder")
    return _result(errors, paths={key: str(path) if path else None for key, path in paths.items()}, hashes=hashes, matrix_rows=rows)


def _approval(payload: dict[str, Any], label: str, errors: list[str], *, edited: bool = False) -> None:
    if payload.get("decision") != "approve" or payload.get("human_reviewed") is not True:
        errors.append(f"{label}: explicit human approve and human_reviewed=true are required")
    for field in ("reviewer", "reviewed_at", "source_thread_id", "user_quote"):
        if not _text(payload.get(field)):
            errors.append(f"{label}: {field} is required")
    if payload.get("actor") != "user":
        errors.append(f"{label}: actor must be user")
    if _text(payload.get("reviewed_at")):
        try:
            timestamp = datetime.fromisoformat(payload["reviewed_at"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                errors.append(f"{label}: reviewed_at needs a timezone")
        except ValueError:
            errors.append(f"{label}: reviewed_at must be ISO-8601")
    if edited and (payload.get("human_edited") is not True or not _text(payload.get("edit_summary"))):
        errors.append("innovation: human_edited=true and edit_summary are required")
    if _placeholder(payload):
        errors.append(f"{label}: review contains a placeholder")


def validate_innovation_review(root: str | Path, card: dict[str, Any]) -> dict[str, Any]:
    package = validate_innovation_package(root, card)
    errors = list(package["errors"])
    payload = _json(review_paths(root, card)["innovation"], "innovation review", errors)
    if payload is not None:
        _approval(payload, "innovation", errors, edited=True)
        recorded = payload.get("package_sha256", {})
        if not isinstance(recorded, dict):
            recorded = {}
        for field, digest in package["hashes"].items():
            if recorded.get(field) != digest:
                errors.append(f"innovation review hash does not match current {field}")
        if payload.get("card_sha256") != file_hash(Path(root) / "experiments/cards" / f"{card['experiment_id']}.json"):
            errors.append("innovation review does not match current experiment card")
    return _result(errors, package=package, review=payload)


def validate_compute_allocation(root: str | Path, card: dict[str, Any]) -> dict[str, Any]:
    innovation = validate_innovation_review(root, card)
    errors = list(innovation["errors"])
    payload = _json(review_paths(root, card)["compute"], "compute allocation", errors)
    if payload is not None:
        _approval(payload, "compute", errors)
        if not _text(payload.get("allocation_basis")) or not _text(payload.get("gpu_type")):
            errors.append("compute: allocation_basis and gpu_type are required")
        if payload.get("innovation_review_sha256") != file_hash(review_paths(root, card)["innovation"]):
            errors.append("compute allocation is not bound to the current innovation review")
        for key in ("gpu_count", "vram_gb", "max_gpu_hours", "max_runtime_seconds", "max_runs", "max_vram_gb", "max_cost_usd"):
            if not _number(payload.get(key), positive=key != "max_cost_usd", integer=key in {"gpu_count", "max_runs"}):
                errors.append(f"compute.{key}: finite numeric limit required")
        if _number(payload.get("max_vram_gb")) and _number(payload.get("vram_gb")) and payload["max_vram_gb"] > payload["vram_gb"]:
            errors.append("compute: max_vram_gb exceeds the allocated GPU memory")
    return _result(errors, innovation=innovation, allocation=payload)


def _ledger(root: Path) -> Ledger:
    return Ledger(root / read_json(root / "config/project.json")["ledger_path"])


def matrix_progress(root: str | Path, card: dict[str, Any]) -> dict[str, Any]:
    root = Path(root).resolve()
    errors: list[str] = []
    payload = _json(package_paths(root, card)["experiment_matrix"], "experiment_matrix", errors)
    rows = payload.get("rows", []) if payload else []
    ledger = _ledger(root)
    missing = []
    if not isinstance(rows, list) or not rows:
        errors.append("no executable experiment matrix is registered")
        rows = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("seeds"), list):
            errors.append("invalid experiment matrix row")
            continue
        runs = ledger.runs(row.get("experiment_id", ""))
        completed = {run.get("seed") for run in runs if run.get("stage") == row.get("stage")
                     and run.get("status") in {"keep", "discard", "candidate"} and _number(run.get("metric"))}
        # A completed negative verification/ablation is valid evidence too.
        for seed in row["seeds"]:
            if seed not in completed:
                missing.append({"row_id": row.get("id"), "category": row.get("category"),
                                "experiment_id": row.get("experiment_id"), "stage": row.get("stage"), "seed": seed})
    return _result(errors + [f"matrix run is incomplete: {item}" for item in missing], missing_runs=missing)


def evidence_snapshot(root: str | Path, card: dict[str, Any], runs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    ledger = _ledger(root)
    own_runs = ledger.runs(card["experiment_id"]) if runs is None else runs
    payload = _json(package_paths(root, card)["experiment_matrix"], "experiment_matrix", []) or {}
    rows = payload.get("rows", [])
    ids = {card["experiment_id"]}
    if card.get("reference_experiment_id"):
        ids.add(card["reference_experiment_id"])
    if isinstance(rows, list):
        ids.update(row["experiment_id"] for row in rows if isinstance(row, dict) and _text(row.get("experiment_id")))
    evidence_runs = list(own_runs)
    for exp_id in sorted(ids - {card["experiment_id"]}):
        evidence_runs.extend(ledger.runs(exp_id))
    cards = {exp_id: file_hash(root / "experiments/cards" / f"{exp_id}.json") for exp_id in sorted(ids)}
    records = [{
        "run_id": run["run_id"], "experiment_id": run["experiment_id"], "stage": run["stage"],
        "seed": run.get("seed"), "status": run["status"], "metric": run.get("metric"),
        "exit_code": run.get("exit_code"), "receipt_sha256": file_hash(resolve(root, run.get("receipt_path"))),
    } for run in sorted(evidence_runs, key=lambda item: item["run_id"])]
    return {"cards": cards, "runs": records,
            "matrix_sha256": file_hash(package_paths(root, card)["experiment_matrix"]),
            "compute_allocation_sha256": file_hash(review_paths(root, card)["compute"])}


def validate_conclusion_review(root: str | Path, card: dict[str, Any], runs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    allocation = validate_compute_allocation(root, card)
    errors = list(allocation["errors"])
    progress = matrix_progress(root, card)
    errors.extend(progress["errors"])
    payload = _json(review_paths(root, card)["conclusion"], "conclusion review", errors)
    snapshot = evidence_snapshot(root, card, runs)
    if payload is not None:
        _approval(payload, "conclusion", errors)
        if payload.get("evidence_checked") is not True or not _text(payload.get("claim_scope")):
            errors.append("conclusion: evidence_checked=true and claim_scope are required")
        if payload.get("evidence_sha256") != value_hash(snapshot):
            errors.append("conclusion review is stale or does not match the current evidence snapshot")
        known_runs = {item["run_id"]: item for item in snapshot["runs"]}
        conclusions = payload.get("approved_conclusions")
        if not isinstance(conclusions, list) or not conclusions:
            errors.append("conclusion: approved_conclusions must be a non-empty list")
            conclusions = []
        ids: set[str] = set()
        for index, conclusion in enumerate(conclusions):
            if not isinstance(conclusion, dict):
                errors.append(f"approved conclusion {index} must be an object")
                continue
            for key in ("id", "zh", "en"):
                if not _text(conclusion.get(key)):
                    errors.append(f"approved conclusion {index} needs {key}")
            if _text(conclusion.get("id")):
                if conclusion["id"] in ids:
                    errors.append(f"duplicate conclusion ID: {conclusion['id']}")
                ids.add(conclusion["id"])
            refs = conclusion.get("evidence_refs")
            if not isinstance(refs, list) or not refs or not all(_text(ref) for ref in refs):
                errors.append(f"approved conclusion {index}: evidence_refs must be a non-empty list of run IDs")
                continue
            for ref in refs:
                run = known_runs.get(ref)
                if not run or run["status"] not in {"keep", "discard", "candidate"} or run.get("exit_code") != 0 or not _number(run.get("metric")):
                    errors.append(f"approved conclusion {index}: missing or failed evidence run {ref}")
                    continue
                if not run.get("receipt_sha256"):
                    errors.append(f"approved conclusion {index}: missing receipt for {ref}")
    return _result(errors, allocation=allocation, matrix=progress, review=payload,
                   evidence_snapshot=snapshot, evidence_sha256=value_hash(snapshot))


def gate_snapshot(root: str | Path, card: dict[str, Any], runs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if not is_human_gated(card, root):
        return {"workflow_mode": "historical", "enabled": False}
    conclusion = validate_conclusion_review(root, card, runs)
    allocation = conclusion["allocation"]
    innovation = allocation["innovation"]
    return {"workflow_mode": HUMAN_GATED_WORKFLOW, "enabled": True,
            "innovation_package": innovation["package"], "innovation_review": innovation,
            "compute_allocation": allocation, "experiment_matrix": conclusion["matrix"],
            "conclusion_review": conclusion}
