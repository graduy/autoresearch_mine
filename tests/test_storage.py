from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from labctl.storage import add_code, add_reference, audit, init_workspace, new_task


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
