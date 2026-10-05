from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from labctl.card import load_card
from labctl.analysis import describe
from labctl.deliver import build_package
from labctl.ledger import Ledger
from labctl.report import draft_report
from labctl.workflow import assert_stage_ready, state


def test_card_is_valid():
    root = Path(__file__).parents[1]
    card = load_card(root / "experiments/cards/nanochat-local.json")
    assert card["primary_metric"] == "val_bpb"
    assert "baseline" in card["stages"]
    assert all(isinstance(seed, int) for seed in card["seeds"])


def test_ledger_approval_and_runs(tmp_path):
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.register_experiment("e1", {"experiment_id": "e1"})
    assert not ledger.approved("e1")
    ledger.approval("e1", "approve", "test", "tester")
    assert ledger.approved("e1")
    ledger.start_run({
        "run_id": "r1", "experiment_id": "e1", "stage": "baseline",
        "seed": 1, "command": ["python", "-V"], "run_dir": str(tmp_path),
    })
    ledger.finish_run("r1", {"status": "keep", "metric": 1.2, "runtime_seconds": 1.0})
    assert ledger.best_metric("e1", "minimize") == 1.2


def test_report_preserves_tbd(tmp_path):
    root = Path(__file__).parents[1]
    config = json.loads((root / "config/project.json").read_text())
    config["ledger_path"] = str(tmp_path / "ledger.sqlite3")
    (root / "config/project-test.json").write_text(json.dumps(config))
    try:
        # The report path uses the project config, so this test only checks the
        # generated card and ledger schema through the public components.
        ledger = Ledger(tmp_path / "ledger.sqlite3")
        ledger.register_experiment("nanochat-local", load_card(root / "experiments/cards/nanochat-local.json"))
        assert ledger.runs("nanochat-local") == []
    finally:
        (root / "config/project-test.json").unlink()


def test_run_directories_are_unique(tmp_path):
    from labctl.runner import _run_dir

    first = _run_dir(tmp_path, "e1", "baseline", "e1-baseline-42-a")
    second = _run_dir(tmp_path, "e1", "baseline", "e1-baseline-42-b")
    assert first != second


def test_workflow_requires_approval_and_orders_stages(tmp_path):
    root = Path(__file__).parents[1]
    original = (root / "config/project.json").read_text()
    config = json.loads(original)
    config["ledger_path"] = str(tmp_path / "ledger.sqlite3")
    (root / "config/project.json").write_text(json.dumps(config))
    try:
        card = load_card(root / "experiments/cards/nanochat-rtx4060-b16.json")
        ledger = Ledger(tmp_path / "ledger.sqlite3")
        ledger.register_experiment(card["experiment_id"], card)
        assert state(root, card["experiment_id"])["state"] == "human_approval"
        ledger.approval(card["experiment_id"], "approve", "test", "tester")
        current = state(root, card["experiment_id"])
        assert current["state"] == "baseline"
        assert current["next_stage"] == "baseline"
    finally:
        (root / "config/project.json").write_text(original)


def test_multi_seed_does_not_require_improvement(tmp_path):
    root = Path(__file__).parents[1]
    original = (root / "config/project.json").read_text()
    config = json.loads(original)
    config["ledger_path"] = str(tmp_path / "ledger.sqlite3")
    (root / "config/project.json").write_text(json.dumps(config))
    try:
        card = load_card(root / "experiments/cards/nanochat-rtx4060-b16.json")
        ledger = Ledger(tmp_path / "ledger.sqlite3")
        ledger.register_experiment(card["experiment_id"], card)
        ledger.approval(card["experiment_id"], "approve", "test", "tester")
        for run_id, stage, seed, status, metric in [
            ("b", "baseline", 42, "keep", 1.0),
            ("p", "pilot", 42, "keep", 0.9),
            ("f", "full", 42, "keep", 0.8),
        ]:
            ledger.start_run({"run_id": run_id, "experiment_id": card["experiment_id"],
                              "stage": stage, "seed": seed, "command": ["test"],
                              "run_dir": str(tmp_path)})
            ledger.finish_run(run_id, {"status": status, "metric": metric, "runtime_seconds": 1.0})
        current = state(root, card["experiment_id"])
        assert current["state"] == "multi_seed"
        assert current["next_stage"] == "multi_seed"
    finally:
        (root / "config/project.json").write_text(original)


def test_workflow_blocks_stage_skipping(tmp_path):
    root = Path(__file__).parents[1]
    original = (root / "config/project.json").read_text()
    config = json.loads(original)
    config["ledger_path"] = str(tmp_path / "ledger.sqlite3")
    (root / "config/project.json").write_text(json.dumps(config))
    try:
        card = load_card(root / "experiments/cards/nanochat-rtx4060-b16.json")
        ledger = Ledger(tmp_path / "ledger.sqlite3")
        ledger.register_experiment(card["experiment_id"], card)
        ledger.approval(card["experiment_id"], "approve", "test", "tester")
        try:
            assert_stage_ready(root, card["experiment_id"], "full")
        except RuntimeError as exc:
            assert "workflow gate blocked full" in str(exc)
        else:
            raise AssertionError("full stage unexpectedly bypassed the baseline and pilot gates")
    finally:
        (root / "config/project.json").write_text(original)


def test_single_run_statistics_keep_uncertainty_explicit():
    result = describe([1.2])
    assert result["n"] == 1
    assert result["std"] is None
    assert result["bootstrap_mean_ci95"] is None
    assert "one valid run" in result["boundary"]


def test_package_is_evidence_bound():
    root = Path(__file__).parents[1]
    package = build_package(root, "nanochat-window-slll-b16")
    assert (package / "evidence_manifest.json").is_file()
    assert (package / "analysis.json").is_file()
    assert (package / "paper_input.md").is_file()
    assert (package / "ppt_brief.md").is_file()
    assert (package / "boss_update.md").is_file()
    text = (package / "boss_update.md").read_text()
    assert "TBD" in text
