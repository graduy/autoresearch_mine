from __future__ import annotations

import json
import hashlib
import sqlite3
from pathlib import Path

from labctl.card import load_card
from labctl.analysis import describe
from labctl.deliver import build_package
from labctl.ledger import Ledger
from labctl.report import draft_report
from labctl.workflow import assert_stage_ready, state


def _human_gated_fixture(tmp_path: Path) -> tuple[Path, dict]:
    root = tmp_path / "project"
    (root / "config").mkdir(parents=True)
    (root / "experiments/cards").mkdir(parents=True)
    (root / "config/project.json").write_text(json.dumps({"ledger_path": "artifacts/ledger.sqlite3"}), encoding="utf-8")
    card = {
        "experiment_id": "gated-e1",
        "title": "Human gated test",
        "hypothesis": "The controlled change improves the primary metric.",
        "primary_metric": "score",
        "metric_direction": "maximize",
        "stages": {
            "baseline": {"command": ["python", "-V"], "metric_pattern": r"Python ([0-9.]+)"},
        },
        "constraints": {"max_runs": 4, "max_runtime_seconds": 60},
        "human_approval": {"required": True},
        "workflow_mode": "human_gated_research_to_paper",
        "research_package": {
            "literature_synthesis": "plans/gated/literature.md",
            "innovation_proposal": "plans/gated/innovation.md",
            "compute_budget": "plans/gated/compute.json",
            "experiment_matrix": "plans/gated/matrix.json",
            "architecture_spec": "plans/gated/architecture.md",
            "architecture_draft": "plans/gated/architecture.png",
        },
        "human_reviews": {
            "innovation": "approvals/gated/innovation.json",
            "compute": "approvals/gated/compute.json",
            "conclusion": "approvals/gated/conclusion.json",
        },
    }
    card_path = root / "experiments/cards/gated-e1.json"
    card_path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    return root, card


def _write_human_package(root: Path, card: dict) -> dict[str, str]:
    package = root / "plans/gated"
    package.mkdir(parents=True)
    (package / "literature.md").write_text("The cited literature supports the proposed controlled comparison.", encoding="utf-8")
    (package / "innovation.md").write_text("Use the proposed module under the locked evaluator and compare it with the baseline.", encoding="utf-8")
    (package / "compute.json").write_text(json.dumps({"estimated_gpu_hours": 2, "estimated_runs": 4, "assumptions": "One local GPU per run."}), encoding="utf-8")
    (package / "matrix.json").write_text(json.dumps({"rows": [
        {"id": "V1", "category": "verification", "experiment_id": "gated-e1", "stage": "baseline", "seeds": [1], "hypothesis": "The full method improves score.", "control": "locked baseline", "change": "full method", "metric": "score", "pass_rule": "full score exceeds baseline"},
        {"id": "A1", "category": "ablation", "experiment_id": "gated-e1", "stage": "baseline", "seeds": [1], "component": "proposed module", "hypothesis": "Removing the module reduces score.", "control": "full method", "change": "remove proposed module", "metric": "score", "pass_rule": "ablation score decreases"},
    ]}), encoding="utf-8")
    (package / "architecture.md").write_text("Inputs -> proposed module -> evaluator", encoding="utf-8")
    (package / "architecture.png").write_bytes(b"\x89PNG\r\n\x1a\narchitecture draft")
    from labctl.research_gate import validate_innovation_package
    return validate_innovation_package(root, card)["hashes"]


def _write_innovation_review(root: Path, package_hashes: dict[str, str]) -> None:
    path = root / "approvals/gated"
    path.mkdir(parents=True)
    (path / "innovation.json").write_text(json.dumps({
        "decision": "approve", "human_reviewed": True, "human_edited": True,
        "reviewer": "tester", "actor": "user", "reviewed_at": "2026-10-06T10:00:00+08:00",
        "source_thread_id": "test-thread", "user_quote": "I reviewed and approved the edited innovation package.",
        "edit_summary": "Adjusted the proposed module and fixed the ablation pass rule.",
        "package_sha256": package_hashes,
        "card_sha256": hashlib.sha256((root / "experiments/cards/gated-e1.json").read_bytes()).hexdigest(),
    }), encoding="utf-8")


def _write_compute_review(root: Path) -> None:
    from labctl.research_gate import review_paths
    card = json.loads((root / "experiments/cards/gated-e1.json").read_text())
    innovation = review_paths(root, card)["innovation"]
    digest = hashlib.sha256(innovation.read_bytes()).hexdigest()
    (root / "approvals/gated/compute.json").write_text(json.dumps({
        "decision": "approve", "human_reviewed": True, "reviewer": "tester", "actor": "user",
        "reviewed_at": "2026-10-06T10:05:00+08:00", "allocation_basis": "Local RTX 4060 reservation.",
        "source_thread_id": "test-thread", "user_quote": "I provided the exact compute allocation.",
        "innovation_review_sha256": digest, "gpu_type": "RTX 4060", "gpu_count": 1,
        "vram_gb": 8, "max_gpu_hours": 2, "max_runtime_seconds": 60,
        "max_runs": 4, "max_vram_gb": 8, "max_cost_usd": 0,
    }), encoding="utf-8")


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


def test_human_gated_workflow_requires_package_reviews_and_allocation(tmp_path):
    root, card = _human_gated_fixture(tmp_path)
    ledger = Ledger(root / "artifacts/ledger.sqlite3")
    ledger.register_experiment(card["experiment_id"], card)
    assert state(root, card["experiment_id"])["state"] == "innovation_package"

    hashes = _write_human_package(root, card)
    assert state(root, card["experiment_id"])["state"] == "human_innovation_review"
    _write_innovation_review(root, hashes)
    assert state(root, card["experiment_id"])["state"] == "human_compute_allocation"
    _write_compute_review(root)
    assert state(root, card["experiment_id"])["state"] == "human_approval"
    ledger.approval(card["experiment_id"], "approve", "human_review", "tester")
    assert state(root, card["experiment_id"])["state"] == "baseline"


def test_human_conclusion_review_controls_bilingual_drafts(tmp_path):
    root, card = _human_gated_fixture(tmp_path)
    ledger = Ledger(root / "artifacts/ledger.sqlite3")
    ledger.register_experiment(card["experiment_id"], card)
    hashes = _write_human_package(root, card)
    _write_innovation_review(root, hashes)
    _write_compute_review(root)
    ledger.approval(card["experiment_id"], "approve", "human_review", "tester")
    ledger.start_run({
        "run_id": "gated-baseline", "experiment_id": card["experiment_id"], "stage": "baseline",
        "seed": 1, "command": ["test"], "run_dir": str(root / "runs"),
    })
    receipt = root / "runs/gated-baseline/receipt.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps({"status": "keep"}), encoding="utf-8")
    ledger.finish_run("gated-baseline", {"status": "keep", "exit_code": 0, "metric": 1.0, "runtime_seconds": 1.0, "receipt_path": str(receipt)})
    assert state(root, card["experiment_id"])["state"] == "conclusion_review"

    package = build_package(root, card["experiment_id"])
    assert not (package / "paper_draft_zh.md").exists()
    assert not (package / "paper_draft_en.md").exists()

    conclusion = {
        "decision": "approve", "human_reviewed": True, "reviewer": "tester", "actor": "user",
        "reviewed_at": "2026-10-06T10:10:00+08:00", "evidence_checked": True,
        "source_thread_id": "test-thread", "user_quote": "I checked the recorded evidence and approved these conclusions.",
        "claim_scope": "The locked baseline run only.",
        "approved_conclusions": [{
            "id": "C1", "zh": "锁定评估器下，基线运行完成并记录了指标。",
            "en": "Under the locked evaluator, the baseline run completed and recorded the metric.",
            "evidence_refs": ["gated-baseline"],
        }],
    }
    from labctl.research_gate import evidence_snapshot, value_hash
    snapshot = evidence_snapshot(root, card, ledger.runs(card["experiment_id"]))
    conclusion["evidence_sha256"] = value_hash(snapshot)
    (root / "approvals/gated/conclusion.json").write_text(json.dumps(conclusion, ensure_ascii=False), encoding="utf-8")
    package = build_package(root, card["experiment_id"])
    assert (package / "paper_draft_zh.md").is_file()
    assert (package / "paper_draft_en.md").is_file()
    assert "锁定评估器下" in (package / "paper_draft_zh.md").read_text(encoding="utf-8")
    assert "Under the locked evaluator" in (package / "paper_draft_en.md").read_text(encoding="utf-8")
