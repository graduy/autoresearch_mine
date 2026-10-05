from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from .card import load_card
from .gpu import exclusive_check
from .integrity import snapshot, verify_snapshot, write_receipt
from .io import read_json, write_json
from .ledger import Ledger
from .workflow import assert_stage_ready
from .storage import execution_binding


STAGES = ("baseline", "pilot", "full", "multi_seed")


def project_config(root: Path) -> dict[str, Any]:
    return read_json(root / "config" / "project.json")


def card_path(root: Path, experiment_id: str) -> Path:
    return root / "experiments" / "cards" / f"{experiment_id}.json"


def _float_match(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, re.MULTILINE)
    return float(match.group(1)) if match else None


def _run_dir(root: Path, experiment_id: str, stage: str, run_id: str) -> Path:
    path = root / "runs" / experiment_id / stage / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cost(seconds: float, project: dict[str, Any]) -> float:
    return seconds / 3600.0 * float(project.get("gpu_hour_usd") or 0.0)


def _reference_metric(ledger: Ledger, card: dict[str, Any], seed: int | None) -> float | None:
    """Prefer a completed same-seed managed baseline over a historical value."""
    reference_id = card.get("reference_experiment_id")
    if not reference_id:
        return None
    runs = ledger.runs(reference_id)
    matching = [run for run in runs if run.get("status") == "keep"
                and run.get("metric") is not None and run.get("seed") == seed]
    if matching:
        return float(matching[-1]["metric"])
    metrics = [float(run["metric"]) for run in runs
               if run.get("status") == "keep" and run.get("metric") is not None]
    return sum(metrics) / len(metrics) if metrics else None


def run_stage(root: str | Path, experiment_id: str, stage: str, seed: int | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    project = project_config(root)
    card = load_card(card_path(root, experiment_id))
    if stage not in STAGES:
        raise ValueError(f"unsupported stage: {stage}")
    if stage not in card["stages"]:
        raise ValueError(f"stage {stage} is not configured in the card")
    if stage == "multi_seed":
        seeds = card.get("seeds", [])
        if seed is None or (seeds and seed not in seeds):
            raise ValueError(f"multi_seed requires one of the declared seeds: {seeds}")
    assert_stage_ready(root, experiment_id, stage)

    ledger = Ledger(root / project["ledger_path"])
    ledger.register_experiment(experiment_id, card)
    constraints = card.get("constraints", {})
    previous_runs = ledger.runs(experiment_id)
    if constraints.get("max_runs") is not None and len(previous_runs) >= int(constraints["max_runs"]):
        raise RuntimeError("experiment max_runs budget reached")

    code_root, binding_errors = execution_binding(root, card)
    if binding_errors:
        raise RuntimeError("managed experiment binding blocked: " + "; ".join(binding_errors))
    if not code_root.is_dir():
        raise FileNotFoundError(f"code_root does not exist: {code_root}")
    spec = card["stages"][stage]
    run_id = f"{experiment_id}-{stage}-{seed if seed is not None else 'single'}-{uuid.uuid4().hex[:8]}"
    command = [str(item) for item in spec["command"]]
    before = snapshot(code_root, project.get("protected_paths", []), project.get("allowed_change_paths", []))
    required_prefix = str(project.get("required_branch_prefix") or "")
    if required_prefix and not str(before.get("branch") or "").startswith(required_prefix):
        ledger.event(experiment_id, "run_blocked_branch", {
            "stage": stage, "branch": before.get("branch"), "required_prefix": required_prefix,
        })
        raise RuntimeError(f"run requires a branch beginning with {required_prefix!r}; got {before.get('branch')!r}")
    if project.get("require_clean_worktree") and before.get("status_paths"):
        ledger.event(experiment_id, "run_blocked_dirty_worktree", {
            "stage": stage, "status_paths": before.get("status_paths"),
        })
        raise RuntimeError("run requires a clean worktree; commit or revert the listed changes before execution")
    gpu_preflight = exclusive_check(int(project.get("max_foreign_gpu_mb", 512))) if project.get("require_gpu_exclusive") else {"passed": True, "available": False, "skipped": True}
    run_dir = _run_dir(root, experiment_id, stage, run_id)
    stdout_path, stderr_path = run_dir / "stdout.log", run_dir / "stderr.log"
    write_json(run_dir / "gpu_preflight.json", gpu_preflight)
    if project.get("require_gpu_exclusive") and gpu_preflight.get("available") and not gpu_preflight.get("passed"):
        ledger.event(experiment_id, "run_blocked_gpu_busy", {"stage": stage, "seed": seed, "gpu_preflight": gpu_preflight})
        raise RuntimeError("GPU is busy with external processes; see " + str(run_dir / "gpu_preflight.json"))
    write_json(run_dir / "run_request.json", {
        "run_id": run_id, "experiment_id": experiment_id, "stage": stage,
        "seed": seed, "command": command, "code_root": str(code_root),
        "before": before, "gpu_preflight": gpu_preflight,
    })
    ledger.start_run({
        "run_id": run_id, "experiment_id": experiment_id, "stage": stage,
        "seed": seed, "command": command, "run_dir": str(run_dir),
    })
    env = os.environ.copy()
    for variable in project.get("unset_environment", []):
        env.pop(str(variable), None)
    env.update({
        "AUTORESEARCH_EXPERIMENT_ID": experiment_id,
        "AUTORESEARCH_STAGE": stage,
        "AUTORESEARCH_SEED": str(seed if seed is not None else 42),
        "PYTHONUNBUFFERED": "1",
    })
    started = time.monotonic()
    status, exit_code = "crash", None
    try:
        with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
            completed = subprocess.run(
                command, cwd=code_root, env=env, stdout=out, stderr=err,
                timeout=float(constraints.get("max_runtime_seconds", 660)), check=False,
            )
        exit_code = completed.returncode
    except subprocess.TimeoutExpired:
        exit_code = 124
        (stderr_path).open("a", encoding="utf-8").write("autoresearch-lab: timeout\n")
    except OSError as exc:
        exit_code = 127
        with stderr_path.open("a", encoding="utf-8") as err:
            err.write(f"autoresearch-lab: failed to start command: {exc}\n")
    runtime = time.monotonic() - started
    combined = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in (stdout_path, stderr_path))
    metric = _float_match(str(spec["metric_pattern"]), combined)
    peak_vram = _float_match(str(spec.get("vram_pattern", r"^peak_vram_mb:\s*([0-9.]+)")), combined)
    gpu_postflight = exclusive_check(int(project.get("max_foreign_gpu_mb", 512))) if project.get("require_gpu_exclusive") else {"passed": True, "available": False, "skipped": True}
    after = snapshot(code_root, project.get("protected_paths", []), project.get("allowed_change_paths", []))
    scope = verify_snapshot(before, after, code_root)
    cost = _cost(runtime, project)
    spent_cost = sum(float(run.get("cost_usd") or 0.0) for run in previous_runs)
    budget_violation = (
        (constraints.get("max_runtime_seconds") is not None and runtime > float(constraints["max_runtime_seconds"]))
        or (constraints.get("max_cost_usd") is not None and spent_cost + cost > float(constraints["max_cost_usd"]))
        or (constraints.get("max_vram_gb") is not None and peak_vram is not None and peak_vram > float(constraints["max_vram_gb"]) * 1024)
    )
    if exit_code == 0 and metric is not None and scope["passed"] and not budget_violation:
        status = "keep" if stage == "baseline" else "candidate"
        best = ledger.best_metric(experiment_id, card["metric_direction"])
        if stage != "baseline" and best is None:
            best = _reference_metric(ledger, card, seed)
        if stage != "baseline" and best is None and card.get("reference_metric") is not None:
            best = float(card["reference_metric"])
        if stage == "multi_seed" or (stage == "full" and card.get("full_seeds")):
            # Multi-seed is stability evidence. A seed is valid when it
            # completes under the locked protocol; paired full seeds follow
            # the same rule and are judged by their aggregate afterward.
            status = "keep"
        elif stage != "baseline" and best is not None:
            improves = metric < best if card["metric_direction"] == "minimize" else metric > best
            status = "keep" if improves else "discard"
    elif exit_code == 0 and metric is not None and scope["passed"] and budget_violation:
        status = "budget_violation"
    if status == "crash" and gpu_postflight.get("available") and not gpu_postflight.get("passed"):
        status = "contested_crash"
    elif exit_code == 0 and metric is not None and not scope["passed"]:
        status = "integrity_failure"
    rollback = None
    if project.get("auto_rollback") and status in {"discard", "crash", "contested_crash", "integrity_failure", "budget_violation"}:
        target = None
        configured_base = str(card.get("base_commit") or "")
        if configured_base and configured_base != "recorded_at_run_time":
            resolved = subprocess.run(["git", "-C", str(code_root), "rev-parse", configured_base], text=True, capture_output=True, check=False)
            if resolved.returncode == 0:
                target = resolved.stdout.strip()
        if target is None and before.get("head") != after.get("head"):
            target = str(before["head"])
        if not before.get("status_porcelain") and not after.get("status_porcelain") and target and target != after.get("head"):
            reset = subprocess.run(["git", "-C", str(code_root), "reset", "--hard", target], text=True, capture_output=True, check=False)
            rollback = {"attempted": True, "target": target, "returncode": reset.returncode, "stdout": reset.stdout.strip(), "stderr": reset.stderr.strip()}
        else:
            rollback = {"attempted": False, "target": target, "reason": "working tree was not clean, target was unresolved, or HEAD already matched target"}
    receipt = {
        "run_id": run_id, "experiment_id": experiment_id, "stage": stage, "seed": seed,
        "command": command, "exit_code": exit_code, "metric": metric,
        "peak_vram_mb": peak_vram, "runtime_seconds": runtime,
        "scope_check": scope, "before": before, "after": after,
        "unset_environment": project.get("unset_environment", []),
        "gpu_postflight": gpu_postflight,
        "rollback": rollback,
        "status": status,
    }
    receipt_path = run_dir / "integrity_receipt.json"
    write_receipt(receipt_path, receipt)
    result = {
        "status": status, "exit_code": exit_code, "metric": metric,
        "peak_vram_mb": peak_vram, "runtime_seconds": runtime,
        "cost_usd": cost, "receipt_path": str(receipt_path),
    }
    write_json(run_dir / "result.json", {"run_id": run_id, "experiment_id": experiment_id,
                                          "stage": stage, "status": status,
                                          "metric": metric, "receipt_path": str(receipt_path)})
    ledger.finish_run(run_id, result)
    for path, kind in ((stdout_path, "stdout"), (stderr_path, "stderr"),
                       (receipt_path, "integrity_receipt"), (run_dir / "result.json", "result")):
        ledger.add_artifact(run_id, kind, str(path), None)
    print(f"run_id={run_id}")
    print(f"status={status}")
    print(f"metric={metric}")
    print(f"runtime_seconds={runtime:.1f}")
    print(f"peak_vram_mb={peak_vram}")
    return {"run_id": run_id, **result}


def archive_experiment(root: str | Path, experiment_id: str) -> Path:
    root = Path(root).resolve()
    project = project_config(root)
    card = load_card(card_path(root, experiment_id))
    code_root, binding_errors = execution_binding(root, card)
    if binding_errors:
        raise RuntimeError("managed experiment binding blocked: " + "; ".join(binding_errors))
    target = root / "artifacts" / "archives" / experiment_id
    target.mkdir(parents=True, exist_ok=True)
    write_json(target / "card.json", card)
    receipt = snapshot(code_root, project.get("protected_paths", []), project.get("allowed_change_paths", []))
    write_json(target / "code_snapshot.json", receipt)
    try:
        (target / "git_diff.patch").write_text(
            subprocess.run(["git", "-C", str(code_root), "diff", "HEAD"], text=True, capture_output=True, check=False).stdout,
            encoding="utf-8",
        )
    except OSError:
        pass
    python_candidates = [code_root / ".venv" / "bin" / "python", code_root / ".venv" / "bin" / "python3"]
    python_path = next((path for path in python_candidates if path.exists()), None)
    if python_path is None:
        environment_text = "environment interpreter not found\n"
    else:
        if shutil.which("uv"):
            env = subprocess.run(["uv", "pip", "freeze", "--python", str(python_path)], text=True, capture_output=True, check=False)
        else:
            env = subprocess.run([str(python_path), "-m", "pip", "freeze"], text=True, capture_output=True, check=False)
        environment_text = env.stdout
        if env.returncode != 0:
            environment_text += f"\n# pip freeze failed: {env.stderr.strip()}\n"
    (target / "environment.txt").write_text(environment_text, encoding="utf-8")
    ledger = Ledger(root / project["ledger_path"])
    write_json(target / "runs.json", {"runs": ledger.runs(experiment_id), "events": ledger.events(experiment_id)})
    return target
