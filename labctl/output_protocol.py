"""Fixed task-output protocol and checkpoint detection for resumable agents."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .io import read_json, write_json


PROTOCOL_FILE = "workflow/output_protocol.json"


def default_protocol(lab_root: Path) -> dict[str, Any]:
    return read_json(lab_root / PROTOCOL_FILE)


def materialize_protocol(task_root: Path, lab_root: Path, task_id: str) -> Path:
    """Write an immutable protocol copy into a new task directory."""
    target = task_root / "manifests/output_protocol.json"
    if not target.exists():
        payload = default_protocol(lab_root)
        payload["task_id"] = task_id
        write_json(target, payload)
    return target


def _expand(path: str, task_id: str, experiment_id: str | None) -> str:
    return path.replace("{task_id}", task_id).replace("{experiment_id}", experiment_id or "*")


def _check_output(task_root: Path, spec: dict[str, Any], task_id: str,
                  experiment_id: str | None) -> dict[str, Any]:
    relative = _expand(str(spec["path"]), task_id, experiment_id)
    kind = spec.get("kind")
    path = task_root / relative
    matches: list[Path]
    if kind == "glob_nonempty":
        matches = sorted(task_root.glob(relative))
        complete = any(item.is_file() for item in matches)
    elif kind == "dir_nonempty":
        matches = [item for item in path.rglob("*") if item.is_file()] if path.is_dir() else []
        complete = bool(matches)
    elif kind == "json_records":
        matches = [path]
        complete = False
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                complete = isinstance(payload.get("records"), list) and bool(payload["records"])
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                complete = False
    else:
        matches = [path]
        complete = path.is_file() and path.stat().st_size > 0
    return {
        "path": relative,
        "kind": kind,
        "complete": complete,
        "matches": [str(item.relative_to(task_root)) for item in matches if item.exists()],
    }


def checkpoint_status(archive_root: str | Path, task_id: str,
                      lab_root: str | Path | None = None,
                      experiment_id: str | None = None) -> dict[str, Any]:
    """Return the first incomplete fixed-output stage for a task.

    The detector is deliberately conservative: a directory name alone never
    completes a stage, and later files do not allow an agent to skip an earlier
    missing checkpoint.
    """
    archive_root = Path(archive_root).resolve()
    task_root = archive_root / "tasks" / task_id
    if not task_root.is_dir():
        return {"valid": False, "task_id": task_id, "errors": [f"task directory does not exist: {task_root}"]}
    protocol_path = task_root / "manifests/output_protocol.json"
    if protocol_path.is_file():
        protocol = read_json(protocol_path)
    elif lab_root is not None:
        protocol = default_protocol(Path(lab_root).resolve())
    else:
        return {"valid": False, "task_id": task_id, "errors": ["output protocol is missing"]}

    task = read_json(task_root / "task.json")
    experiment_ids = task.get("experiment_ids") or []
    selected_experiment = experiment_id or (experiment_ids[0] if experiment_ids else None)
    cards = []
    for card_path in sorted((task_root / "experiments/cards").glob("*.json")):
        try:
            cards.append(read_json(card_path))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            cards.append({})

    stages: list[dict[str, Any]] = []
    completed: list[str] = []
    skipped: list[str] = []
    current: dict[str, Any] | None = None
    for item in protocol.get("stages", []):
        stage_id = str(item["id"])
        card_stage = item.get("card_stage")
        if card_stage and (not cards or not any(card_stage in (card.get("stages") or {}) for card in cards)):
            stage = {"id": stage_id, "label": item.get("label", stage_id), "status": "skipped",
                     "reason": f"no bound card declares stage {card_stage}"}
            skipped.append(stage_id)
        else:
            outputs = [_check_output(task_root, output, task_id, selected_experiment)
                       for output in item.get("outputs", [])]
            complete = all(output["complete"] for output in outputs)
            stage = {"id": stage_id, "label": item.get("label", stage_id),
                     "status": "complete" if complete else "pending", "outputs": outputs,
                     "next_action": item.get("next_action", "")}
            if complete:
                completed.append(stage_id)
        stages.append(stage)
        if current is None and stage["status"] == "pending":
            current = stage

    if current is None:
        current = {"id": "complete", "label": "全部固定产出已完成", "status": "complete",
                   "next_action": "可归档或开始新的版本。"}
    return {
        "valid": True,
        "protocol_id": protocol.get("protocol_id"),
        "protocol_file": str(protocol_path),
        "task_id": task_id,
        "task_path": str(task_root),
        "experiment_id": selected_experiment,
        "current_stage": current["id"],
        "current_label": current.get("label"),
        "resume_action": current.get("next_action", ""),
        "completed_stages": completed,
        "skipped_stages": skipped,
        "stages": stages,
    }
