"""Read-only output detection and explicit, hash-bound agent checkpoints."""
from __future__ import annotations

import hashlib
import math
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .io import read_json, write_json

PROTOCOL_FILE = "workflow/output_protocol.json"


def default_protocol(lab_root: Path) -> dict[str, Any]:
    return read_json(lab_root / PROTOCOL_FILE)


def materialize_protocol(task_root: Path, lab_root: Path, task_id: str) -> Path:
    target = task_root / "manifests/output_protocol.json"
    if not target.exists():
        payload = default_protocol(lab_root)
        payload["task_id"] = task_id
        write_json(target, payload)
    return target


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_output(task_root: Path, spec: dict[str, Any], task_id: str,
                  experiment_id: str | None) -> dict[str, Any]:
    relative = spec["path"].replace("{task_id}", task_id).replace("{experiment_id}", experiment_id or "__unregistered__")
    kind = spec["kind"]
    path = task_root / relative
    matches = sorted(task_root.glob(relative)) if kind == "glob_nonempty" else [path]
    if kind == "dir_nonempty":
        matches = sorted(path.rglob("*")) if path.is_dir() else []
    files = [item for item in matches if item.is_file() and item.stat().st_size > 0]
    errors = []
    complete = bool(files)
    if kind in {"json", "json_records"}:
        try:
            payload = read_json(path)
            complete = bool(payload)
            if kind == "json_records":
                records = payload.get("records")
                complete = isinstance(records, list) and bool(records) and all(isinstance(row, dict) and row for row in records)
        except (OSError, ValueError):
            complete = False
    for item in files:
        if not item.resolve().is_relative_to(task_root):
            errors.append(f"output escapes task directory: {relative}")
    return {"path": relative, "kind": kind, "complete": complete and not errors,
            "matches": [str(item.relative_to(task_root)) for item in files], "errors": errors}


def _context(archive_root: Path, task_id: str, lab_root: Path | None) -> tuple[Path, dict, dict, Path | None]:
    from .storage import task_dir
    target = task_dir(archive_root, task_id).resolve()
    task = read_json(target / "task.json")
    protocol_path = target / "manifests/output_protocol.json"
    if protocol_path.is_file():
        protocol = read_json(protocol_path)
    elif lab_root:
        protocol = default_protocol(lab_root)
    else:
        raise ValueError("output protocol is missing")
    if protocol.get("protocol_id") != "forautoresearch-task-output-v1" or not protocol.get("stages"):
        raise ValueError("unknown or empty output protocol")
    return target, task, protocol, protocol_path if protocol_path.is_file() else None


def _run_errors(target: Path, cards: list[dict], stage: str) -> list[str]:
    errors = []
    matrix = read_json(target / "plans/experiment_matrix.json")
    expected = {(row.get("experiment_id"), seed) for row in matrix.get("rows", [])
                if isinstance(row, dict) and row.get("stage") == stage
                for seed in row.get("seeds", []) if type(seed) is int}
    for card in cards:
        exp = card["experiment_id"]
        seeds = {seed for exp_id, seed in expected if exp_id == exp}
        if not seeds:
            seeds = set(card.get({"baseline": "baseline_seeds", "full": "full_seeds", "multi_seed": "seeds"}.get(stage, "pilot_seeds"), []) or [None])
        records = read_json(target / f"result/training_records/{exp}.json").get("runs", [])
        completed = set()
        for run in records:
            metric = run.get("metric")
            if (run.get("experiment_id") != exp or run.get("stage") != stage
                    or run.get("status") not in {"keep", "discard", "candidate"}
                    or run.get("exit_code") != 0 or type(metric) not in (int, float) or not math.isfinite(metric)):
                continue
            run_id = run.get("run_id")
            if not isinstance(run_id, str) or Path(run_id).name != run_id:
                continue
            receipt_path = target / f"runs/{exp}/{stage}/{run_id}/integrity_receipt.json"
            try:
                receipt = read_json(receipt_path)
                if receipt.get("run_id") == run_id and receipt.get("status") == run.get("status"):
                    completed.add(run.get("seed"))
            except (OSError, ValueError):
                continue
        for seed in seeds - completed:
            errors.append(f"incomplete or invalid {exp}/{stage}/seed={seed}")
    return errors


def checkpoint_status(archive_root: str | Path, task_id: str,
                      lab_root: str | Path | None = None,
                      experiment_id: str | None = None) -> dict[str, Any]:
    """Detect progress without creating files or changing the ledger."""
    archive_root = Path(archive_root).resolve()
    lab_root = Path(lab_root).resolve() if lab_root else None
    try:
        target, task, protocol, protocol_path = _context(archive_root, task_id, lab_root)
        registry = read_json(target / "manifests/experiments.json").get("records", [])
        cards = [read_json(target / row["card"]) for row in registry]
        if experiment_id:
            cards = [card for card in cards if card.get("experiment_id") == experiment_id]
            if not cards:
                raise ValueError("requested experiment is not registered in this task")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"valid": False, "task_id": task_id, "errors": [str(exc)]}
    gates = {}
    if lab_root:
        from .research_gate import gate_snapshot
        for card in cards:
            try:
                gates[card["experiment_id"]] = gate_snapshot(lab_root, card)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                gates[card.get("experiment_id", "invalid")] = {"error": str(exc)}

    stages, completed, skipped = [], [], []
    current = None
    upstream_hashes = {}
    for item in protocol["stages"]:
        stage_id = item["id"]
        card_stage = item.get("card_stage")
        relevant = [card for card in cards if not card_stage or card_stage in card.get("stages", {})]
        if card_stage and cards and not relevant:
            stage = {"id": stage_id, "label": item["label"], "status": "skipped", "outputs_ready": True,
                     "reason": "no registered card declares this optional stage"}
            skipped.append(stage_id)
            stages.append(stage)
            continue
        outputs, errors = [], []
        for spec in item["outputs"]:
            contexts = relevant if "{experiment_id}" in spec["path"] else [None]
            if not contexts:
                errors.append("no registered experiment card")
            for card in contexts:
                outputs.append(_check_output(target, spec, task_id, card["experiment_id"] if card else None))
        output_hashes = {name: _hash(target / name) for output in outputs for name in output["matches"]}
        validator = item.get("validator")
        try:
            if validator == "innovation_package":
                # The research package is the input to card registration.  It
                # must therefore be checkable before any experiment card exists.
                # Once cards are bound, the gate additionally verifies the
                # package hashes and the card-specific contract.
                if relevant and lab_root:
                    for card in relevant:
                        gate = gates.get(card["experiment_id"], {}).get(validator, {})
                        if not gate.get("valid"):
                            errors.extend(gate.get("errors") or ["innovation package validation is unavailable"])
            elif validator in {"innovation_review", "compute_allocation", "conclusion_review"}:
                if not relevant or not lab_root:
                    errors.append("registered cards and lab root are required for review validation")
                for card in relevant:
                    gate = gates.get(card["experiment_id"], {}).get(validator, {})
                    if not gate.get("valid"):
                        errors.extend(gate.get("errors") or ["review validation is unavailable"])
            elif validator == "cards":
                if not cards:
                    errors.append("no registered experiment cards")
                for row in registry:
                    if _hash(target / row["card"]) != row.get("card_sha256"):
                        errors.append("registered card hash changed")
                    if lab_root and _hash(lab_root / f"experiments/cards/{row['experiment_id']}.json") != row.get("card_sha256"):
                        errors.append("task and lab card hashes differ")
            elif validator == "approval":
                approval = task.get("approval") or {}
                if not approval.get("file") or task.get("status") != "confirmed":
                    errors.append("task has no recorded human execution approval")
                elif _hash(target / approval["file"]) != approval.get("sha256"):
                    errors.append("execution approval hash changed")
                else:
                    record = read_json(target / approval["file"])
                    if record.get("actor") != "user" or record.get("decision") != "approve" or not record.get("user_quote"):
                        errors.append("execution approval needs the user's actual approval")
                    for card in cards:
                        if record.get("approved_experiments", {}).get(card["experiment_id"]) != _hash(target / f"experiments/cards/{card['experiment_id']}.json"):
                            errors.append("experiment is outside the current human approval")
            elif validator == "runs" and relevant:
                errors.extend(_run_errors(target, relevant, stage_id))
            elif validator == "code":
                records = read_json(target / "manifests/code.json").get("records", [])
                for card in cards:
                    if not any(row.get("code_id") == card.get("code_id") and row.get("commit") for row in records):
                        errors.append("executed code ID and commit are not registered")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(str(exc))
        output_files_ready = bool(outputs) and all(output["complete"] for output in outputs)
        # `outputs_ready` deliberately excludes only the checkpoint-file error.
        # This lets the explicit checkpoint command seal a valid stage instead
        # of creating a circular requirement where the checkpoint must exist
        # before it can be saved.
        validation_errors = list(errors)
        checkpoint_path = target / f"manifests/checkpoints/{stage_id}.json"
        checkpoint_inputs = {**upstream_hashes, **output_hashes}
        checkpoint_error = None
        if item.get("checkpoint_required"):
            try:
                checkpoint = read_json(checkpoint_path)
                if checkpoint.get("files_sha256") != checkpoint_inputs:
                    checkpoint_error = "stage checkpoint is stale: inputs or outputs changed"
            except (OSError, ValueError):
                checkpoint_error = "save a hash-bound stage checkpoint after completing outputs"
        if checkpoint_error:
            errors.append(checkpoint_error)
        outputs_ready = output_files_ready and not validation_errors
        status = "complete" if outputs_ready and not errors and current is None else ("prepared" if outputs_ready and not errors else "pending")
        stage = {"id": stage_id, "label": item["label"], "status": status, "outputs_ready": outputs_ready,
                 "outputs": outputs, "errors": errors, "next_action": item["next_action"],
                 "checkpoint_file": str(checkpoint_path), "checkpoint_inputs": checkpoint_inputs}
        stages.append(stage)
        upstream_hashes.update(output_hashes)
        if status == "complete":
            completed.append(stage_id)
        if current is None and status == "pending":
            current = stage
    current = current or {"id": "complete", "label": "固定产出全部完成", "next_action": "工作已完成，可开始新版本。", "errors": []}
    missing = [output["path"] for output in current.get("outputs", []) if not output["complete"]]
    return {"valid": True, "protocol_id": protocol["protocol_id"], "protocol_file": str(protocol_path) if protocol_path else str(lab_root / PROTOCOL_FILE),
            "protocol_source": "task" if protocol_path else "read_only_fallback",
            "task_id": task_id, "task_path": str(target), "experiment_id": experiment_id,
            "current_stage": current["id"], "current_label": current["label"], "resume_action": current["next_action"],
            "missing_outputs": missing, "blockers": current["errors"], "completed_stages": completed,
            "skipped_stages": skipped, "stages": stages}


def save_checkpoint(archive_root: Path, task_id: str, lab_root: Path, stage_id: str) -> Path:
    """Explicitly save a verified checkpoint, never inventing approval or results."""
    status = checkpoint_status(archive_root, task_id, lab_root)
    if not status["valid"]:
        raise ValueError("; ".join(status["errors"]))
    stage = next((row for row in status["stages"] if row["id"] == stage_id), None)
    if stage is None or not stage.get("outputs_ready"):
        raise ValueError("complete and validate stage outputs before saving a checkpoint")
    before = status["stages"][:status["stages"].index(stage)]
    if any(row["status"] not in {"complete", "skipped"} for row in before):
        raise ValueError("earlier checkpoints are incomplete; resume there first")
    target = Path(status["task_path"])
    timestamp = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="microseconds")
    payload = {"schema_version": 1, "task_id": task_id, "stage_id": stage_id, "saved_at": timestamp,
               "files_sha256": stage["checkpoint_inputs"]}
    checkpoint_path = target / f"manifests/checkpoints/{stage_id}.json"
    if checkpoint_path.exists():
        old = read_json(checkpoint_path)
        write_json(target / f"manifests/checkpoints/history/{stage_id}-{_hash(checkpoint_path)[:12]}.json", old)
    write_json(checkpoint_path, payload)
    write_json(target / "manifests/workflow_status.json", checkpoint_status(archive_root, task_id, lab_root))
    return checkpoint_path
