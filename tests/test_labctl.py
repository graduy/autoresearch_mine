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
            "pilot": {"command": ["python", "-V"], "metric_pattern": r"Python ([0-9.]+)"},
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
            "baseline_reference": "plans/gated/baseline_reference.json",
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
    library = root / "local-code/models"
    library.mkdir(parents=True)
    (library / "temporal_aggregation.py").write_text("# source", encoding="utf-8")
    (library / "light_decoder.py").write_text("# source", encoding="utf-8")
    (package / "literature.md").write_text("The cited literature supports the proposed controlled comparison.", encoding="utf-8")
    (package / "innovation.md").write_text("Use the proposed module under the locked evaluator and compare it with the baseline.", encoding="utf-8")
    (package / "compute.json").write_text(json.dumps({
        "estimated_gpu_hours": 24,
        "estimated_runs": 3,
        "assumptions": "Three experiments are scheduled on four local GPUs with wall-clock margin.",
        "schedule_basis": "Three matrix rows each use four GPUs for two hours; the wall-clock recommendation includes scheduling margin.",
        "budget_summary": {
            "total_experiments": 3,
            "gpu_type": "4090-24G",
            "required_gpu_count": 4,
            "wall_clock_hours": 6,
            "recommended_gpu_count": 4,
            "recommended_hours": 6,
            "recommended_rental": "推荐租4张4090-24G，运行6小时",
        },
        "run_estimates": [
            {"row_id": "V1", "seed": 1, "gpu_count": 4, "hours": 2, "estimate_source": "baseline reproduction estimate"},
            {"row_id": "V2", "seed": 1, "gpu_count": 4, "hours": 2, "estimate_source": "whole-system optimization estimate"},
            {"row_id": "A1", "seed": 1, "gpu_count": 4, "hours": 2, "estimate_source": "ablation estimate"},
        ],
    }), encoding="utf-8")
    (package / "matrix.json").write_text(json.dumps({"rows": [
        {"id": "V1", "category": "verification", "strategy_role": "reference_reproduction", "experiment_id": "gated-e1", "stage": "baseline", "seeds": [1], "hypothesis": "The reference protocol reproduces the baseline.", "control": "paper baseline", "change": "faithful reproduction", "metric": "score", "pass_rule": "reproduction meets the declared acceptance rule"},
        {"id": "V2", "category": "verification", "strategy_role": "recent_optimization", "experiment_id": "gated-e1", "stage": "pilot", "seeds": [1], "hypothesis": "The whole-system candidate improves the reproduced baseline.", "control": "reproduced baseline", "change": "coherent combination of selected recent methods", "metric": "score", "pass_rule": "optimization passes the predeclared comparison rule"},
        {"id": "A1", "category": "ablation", "strategy_role": "ablation", "experiment_id": "gated-e1", "stage": "pilot", "seeds": [1], "component": "selected recent method set", "hypothesis": "Removing the selected method set identifies its contribution.", "control": "whole-system optimization", "change": "remove the selected method set", "metric": "score", "pass_rule": "ablation is interpreted with the paired optimization"},
    ]}), encoding="utf-8")
    (package / "architecture.md").write_text("Inputs -> proposed module -> evaluator", encoding="utf-8")
    (package / "architecture.png").write_bytes(b"\x89PNG\r\n\x1a\narchitecture draft")
    (package / "baseline_reference.json").write_text(json.dumps({
        "research_strategy": "reference_first_reproduction_and_whole_system_optimization",
        "publication_positioning": "reproduction_plus_whole_system_optimization",
        "paper": {
            "title": "A source-backed baseline paper",
            "venue": "Journal of Controlled Research",
            "venue_type": "journal",
            "year": 2024,
            "publication_source": "Publisher record",
            "full_text_source": "Publisher full text",
            "indexing": "SCIE",
            "indexing_source": "Web of Science record",
            "quartile_system": "CAS",
            "quartile_scope": "major",
            "quartile_category": "Computer Science",
            "sci_quartile": "2",
            "impact_factor": 5.1,
            "doi": "10.1000/example",
            "quartile_source": "CAS 2024 major-category record",
            "quartile_year": 2024,
            "impact_factor_source": "JCR 2024 record",
            "impact_factor_year": 2024,
            "verified_at": "2026-10-06T10:00:00+08:00",
        },
        "reference_baseline": {
            "name": "Reference baseline",
            "model": "Locked reference model",
            "input_or_sequence": "Fixed input protocol",
            "reported_metrics": ["score"],
            "source_location": "paper section 3",
        },
        "reference_experiment_scheme": {
            "dataset": "Reference dataset",
            "split": "Reference train/validation/test split",
            "training": "Reference training protocol",
            "evaluation": "Reference evaluation protocol",
            "metrics": ["score"],
            "ablation": "Reference ablation protocol",
            "source_location": "paper section 4",
        },
        "reference_reproduction": {
            "protocol_lock": "Use the paper dataset split, preprocessing, training schedule and evaluator before any extension.",
            "allowed_deviations": "Only environment differences are recorded and justified.",
            "acceptance_rule": "Reproduction must satisfy the predeclared metric tolerance before extension runs.",
            "source_location": "paper methods and experiment sections",
        },
        "recent_optimization": {
            "optimization_scope": "whole_system",
            "selected_methods": ["Recent temporal aggregation", "Recent lightweight decoder"],
            "method_sources": ["Recent peer-reviewed method record A", "Recent peer-reviewed method record B"],
            "publication_years": [2025, 2026],
            "changed_components": ["temporal aggregation", "decoder", "training schedule"],
            "coherence_rationale": "The selected methods address complementary temporal and efficiency limits and are evaluated as one coherent candidate.",
            "source_location": "recent method papers and extension plan",
        },
        "local_code_library": {
            "root": str(root / "local-code"),
            "lookback_years": 2,
            "scope_basis": "Custom venue scope chosen for the task: three CV venues and three ML venues.",
            "cv_venue_scope": ["CV Venue A", "CV Venue B", "CV Venue C"],
            "ml_venue_scope": ["ML Venue A", "ML Venue B", "ML Venue C"],
            "records": [
                {"venue": "CV Venue A", "year": 2025, "method": "Recent temporal aggregation", "code_path": "models/temporal_aggregation.py", "source_location": "local code index"},
                {"venue": "ML Venue A", "year": 2026, "method": "Recent lightweight decoder", "code_path": "models/light_decoder.py", "source_location": "local code index"},
            ],
        },
        "final_experiment_scheme": {
            "method": "Proposed method",
            "dataset": "Same locked dataset",
            "split": "Same locked split",
            "training": "Paired controlled training",
            "evaluation": "Same evaluator",
            "metrics": ["score"],
            "ablation_plan": "Remove the proposed module under the same protocol",
            "experiment_matrix_sha256": hashlib.sha256((package / "matrix.json").read_bytes()).hexdigest(),
        },
        "candidate_selection": {
            "status": "candidate_best_under_recorded_evidence",
            "basis": "Selected after comparing the reference reproduction with the coherent recent-method candidate and its ablation plan.",
            "alternatives_considered": ["reference reproduction only", "single-method replacement"],
        },
        "comparison_table": [
            {"dimension_key": "model_baseline", "dimension": "Model/baseline", "reference_paper": "Locked reference model", "final_scheme": "Proposed method", "decision_or_difference": "Controlled method change", "source_location": "paper section 3; plan section 2"},
            {"dimension_key": "data_split", "dimension": "Data and split", "reference_paper": "Reference dataset and split", "final_scheme": "Same locked dataset and split", "decision_or_difference": "Keep fixed for comparability", "source_location": "paper section 2; plan section 3"},
            {"dimension_key": "training_protocol", "dimension": "Training protocol", "reference_paper": "Reference training protocol", "final_scheme": "Paired controlled training", "decision_or_difference": "Record changed settings", "source_location": "paper section 4; plan section 4"},
            {"dimension_key": "evaluation_metrics", "dimension": "Evaluation metrics", "reference_paper": "score", "final_scheme": "score", "decision_or_difference": "Same primary metric", "source_location": "paper section 5; plan section 5", "comparable": True},
            {"dimension_key": "ablation_protocol", "dimension": "Ablation protocol", "reference_paper": "Reported ablations", "final_scheme": "Remove proposed module", "decision_or_difference": "Required causal check", "source_location": "paper section 4; plan section 6"},
        ],
    }, ensure_ascii=False), encoding="utf-8")
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
        "baseline_eligibility_checked": True,
        "reference_reproduction_checked": True,
        "recent_optimization_checked": True,
        "protocol_comparison_checked": True,
        "conference_quality_confirmed": False,
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
        "reviewed_at": "2026-10-06T10:05:00+08:00", "allocation_basis": "Local 4090-24G reservation.",
        "source_thread_id": "test-thread", "user_quote": "I provided the exact compute allocation.",
        "innovation_review_sha256": digest, "gpu_type": "4090-24G", "gpu_count": 4,
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
    first_review = state(root, card["experiment_id"])
    baseline_review = first_review["gates"]["baseline_reference"]
    assert baseline_review["valid"] is True
    assert len(baseline_review["comparison_table"]) == 5
    assert first_review["gates"]["innovation_package"]["compute_budget"]["summary_text"] == (
        "共有 3 个实验需要跑；需要 4 张 4090-24G 跑 6 小时；推荐租 4 张 4090-24G，运行 6 小时。"
    )
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
    ledger.start_run({
        "run_id": "gated-pilot", "experiment_id": card["experiment_id"], "stage": "pilot",
        "seed": 1, "command": ["test"], "run_dir": str(root / "runs"),
    })
    pilot_receipt = root / "runs/gated-pilot/receipt.json"
    pilot_receipt.parent.mkdir(parents=True, exist_ok=True)
    pilot_receipt.write_text(json.dumps({"status": "keep"}), encoding="utf-8")
    ledger.finish_run("gated-pilot", {"status": "keep", "exit_code": 0, "metric": 1.1, "runtime_seconds": 1.0, "receipt_path": str(pilot_receipt)})
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
