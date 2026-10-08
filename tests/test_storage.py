from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from labctl.storage import add_code, add_reference, audit, bind_card, init_workspace, new_task


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "source"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "README.md").write_text("source\n", encoding="utf-8")
    (repo / "train.py").write_text("print('ok')\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-q", "-m", "initial"], check=True)
    return repo


def test_storage_registers_references_and_immutable_code(tmp_path):
    lab = Path(__file__).parents[1]
    root = tmp_path / "forautoresearch"
    init_workspace(root, lab)
    task = new_task(root, "Test task", "test-task")
    task_id = task.name
    metadata = {
        "key": "test-paper", "title": "Test paper", "year": 2026,
        "url": "https://example.com/paper", "kind": "paper", "reading_level": "abstract",
    }
    record = add_reference(root, metadata, task_id)
    assert record["reference_id"] == "REF-2026-test-paper"
    repo = _git_repo(tmp_path)
    code = add_code(root, task_id, repo, "HEAD", "baseline", "test-baseline")
    assert code["commit"]
    report = audit(root, task_id)
    assert report["passed"] is True
    assert not report["errors"]

    checkout = task / code["checkout"]
    (checkout / "train.py").write_text("tampered\n", encoding="utf-8")
    report = audit(root, task_id)
    assert report["passed"] is False
    assert any("code file missing or changed" in error for error in report["errors"])
    assert any("uncommitted code edits" in warning for warning in report["warnings"])


def test_code_snapshot_rejects_weights_and_datasets(tmp_path):
    lab = Path(__file__).parents[1]
    root = tmp_path / "forautoresearch"
    init_workspace(root, lab)
    task = new_task(root, "Unsafe source", "unsafe-source")
    repo = _git_repo(tmp_path)
    (repo / "weights.pt").write_bytes(b"weights")
    subprocess.run(["git", "-C", str(repo), "add", "weights.pt"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-q", "-m", "weights"], check=True)
    with pytest.raises(ValueError, match="weight/data"):
        add_code(root, task.name, repo, "HEAD", "variant", "unsafe")


def test_new_bound_cards_receive_research_to_paper_contract(tmp_path):
    lab = tmp_path / "lab"
    (lab / "experiments/cards").mkdir(parents=True)
    root = tmp_path / "forautoresearch"
    init_workspace(root, Path(__file__).parents[1])
    task = new_task(root, "Gated task", "gated-task")
    repo = _git_repo(tmp_path)
    code = add_code(root, task.name, repo, "HEAD", "baseline", "baseline")
    experiment_id = task.name.lower() + "-baseline"
    card_path = tmp_path / f"{experiment_id}.json"
    card_path.write_text(json.dumps({
        "experiment_id": experiment_id,
        "hypothesis": "The controlled method improves score.",
        "primary_metric": "score", "metric_direction": "maximize",
        "stages": {"baseline": {"command": ["python", "-V"], "metric_pattern": "Python ([0-9.]+)"}},
        "constraints": {"max_runs": 1, "max_runtime_seconds": 60, "max_cost_usd": 0},
        "human_approval": {"required": True},
    }), encoding="utf-8")
    bound = bind_card(root, lab, task.name, card_path, code["code_id"])
    payload = json.loads(bound.read_text(encoding="utf-8"))
    assert payload["workflow_mode"] == "human_gated_research_to_paper"
    assert set(payload["research_package"]) == {
        "literature_synthesis", "innovation_proposal", "compute_budget",
        "experiment_matrix", "architecture_spec", "architecture_draft",
        "baseline_reference",
    }
    assert all(Path(value).is_absolute() for value in payload["research_package"].values())
    assert set(payload["human_reviews"]) == {"innovation", "compute", "conclusion"}
