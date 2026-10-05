from __future__ import annotations

import json
from pathlib import Path

from .analysis import analyze_experiment
from .card import load_card
from .evidence import build_manifest
from .ledger import Ledger
from .workflow import state as workflow_state


def build_package(root: str | Path, experiment_id: str) -> Path:
    root = Path(root).resolve()
    card = load_card(root / "experiments" / "cards" / f"{experiment_id}.json")
    project = json.loads((root / "config" / "project.json").read_text(encoding="utf-8"))
    ledger = Ledger(root / project["ledger_path"])
    package = root / "deliverables" / experiment_id
    package.mkdir(parents=True, exist_ok=True)
    analysis_path = analyze_experiment(root, experiment_id, package / "analysis.json")
    manifest_path = build_manifest(root, experiment_id, package / "evidence_manifest.json")
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    runs = ledger.runs(experiment_id)
    valid = [run for run in runs if run.get("metric") is not None]
    best = ledger.best_metric(experiment_id, card["metric_direction"])
    evidence = json.loads(manifest_path.read_text(encoding="utf-8"))

    paper = [
        f"# Manuscript input: {card.get('title', experiment_id)}", "",
        "> This is a source-grounded manuscript input pack, not a final submission.", "",
        "## Research question and hypothesis", "",
        card["hypothesis"], "",
        "The hypothesis remains a hypothesis until the locked experiment and claim gate are complete.", "",
        "## Evidence sources", "",
    ]
    for source in card.get("source_papers", []):
        paper.append(f"- {source.get('title', 'TBD')}: {source.get('url', 'TBD')} ({source.get('role', 'TBD')})")
    paper += ["", "## Results ledger", "", f"- Valid metric-bearing runs: `{len(valid)}`", f"- Best recorded primary metric: `{best if best is not None else 'TBD'}`", f"- Evidence manifest: `{manifest_path}`", f"- Analysis: `{analysis_path.with_suffix('.md')}`", "", "## Claim boundary", "", "- Pilot results are selection evidence.", "- Multi-seed stability is `TBD` until all declared seeds finish.", "- Independent-test evidence is `TBD` unless explicitly recorded in the experiment card.", "- Missing checkpoints, data availability records, and supplementary artifacts remain `TBD`.", ""]
    (package / "paper_input.md").write_text("\n".join(paper), encoding="utf-8")

    ppt = [
        f"# PPT handoff: {card.get('title', experiment_id)}", "",
        "> Route: `ppt-master` for narrative/layout/editable PPTX; Sivia for source-grounded scientific figures and figure review. Empirical plots must be generated from the evidence manifest.", "",
        "## Slide outline", "",
        "1. Research question and motivation — label literature-derived motivation, not measured gain.",
        "2. Fixed protocol — evaluator, data boundary, hardware and metric.",
        "3. Evidence-gated workflow — idea, approval, baseline, pilot, multi-seed and claim gate.",
        "4. Baseline — only the recorded baseline metric and run conditions.",
        "5. Candidate pilot — show the real pilot outcome and label selection holdout.",
        "6. What is known and unknown — multi-seed, independent test, checkpoint and statistical evidence.",
        "7. Next experiment — only a pre-registered hypothesis with cost and stop rule.",
        "8. Progress decision — ask for the specific approval or resource needed.",
        "", "## Figure and data rules", "", f"- Evidence manifest: `{manifest_path}`", "- Architecture/funnel schematics: use Sivia source-grounded design and audit.", "- Result chart: use real ledger values only; current pilot is single-seed exploratory evidence.", "- Do not use generated visual features, curves or metrics as experimental evidence.", ""]
    (package / "ppt_brief.md").write_text("\n".join(ppt), encoding="utf-8")

    current = workflow_state(root, experiment_id)
    status = "; ".join(evidence["claim_boundary"]["missing_evidence"]) or "none"
    observed = [run["metric"] for run in runs if run.get("metric") is not None]
    observed_text = ", ".join(str(value) for value in observed) if observed else "TBD"
    reference_text = analysis.get("reference", {}).get("metric")
    reference_text = reference_text if reference_text is not None else "TBD"
    boss = [
        f"# 老板进度汇报：{card.get('title', experiment_id)}", "",
        "## 当前结论", "",
        f"- 工作流状态：`{current['state']}`",
        f"- 下一步：`{current['next_action']}`",
        f"- 已记录指标：`{observed_text}`；参考指标：`{reference_text}`",
        f"- 当前最佳保留指标：`{best if best is not None else 'TBD'}`",
        f"- 缺失证据：`{status}`",
        "- 结论边界：当前结果用于实验筛选，不能写成最终方法提升。",
        "", "## 已完成", "", "- 实验卡、审批记录、运行日志、GPU检查和完整性回执已归档。", "- 论文输入包和PPT提纲已从同一证据清单生成。", "", "## 下一步", "", f"- 按工作流状态执行：`{current['next_action']}`。", "- 补齐多种子和独立测试证据后再形成论文主张。", ""]
    (package / "boss_update.md").write_text("\n".join(boss), encoding="utf-8")

    index = {
        "experiment_id": experiment_id,
        "package_root": str(package),
        "analysis": str(analysis_path),
        "evidence_manifest": str(manifest_path),
        "paper_input": str(package / "paper_input.md"),
        "ppt_brief": str(package / "ppt_brief.md"),
        "boss_update": str(package / "boss_update.md"),
        "claim_boundary": evidence["claim_boundary"],
    }
    (package / "package.json").write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return package
