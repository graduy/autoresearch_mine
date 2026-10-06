from __future__ import annotations

import json
from pathlib import Path

from .analysis import analyze_experiment
from .card import load_card
from .evidence import build_manifest
from .ledger import Ledger
from .research_gate import is_human_gated, validate_conclusion_review
from .workflow import state as workflow_state


def _approved_drafts(
    package: Path,
    card: dict,
    experiment_id: str,
    valid: list[dict],
    best: float | None,
    manifest_path: Path,
    analysis_path: Path,
    conclusions: list[dict],
) -> tuple[Path, Path]:
    paper_draft_zh = package / "paper_draft_zh.md"
    paper_draft_en = package / "paper_draft_en.md"
    zh = [
        f"# {card.get('title', experiment_id)}：中文论文初稿", "",
        "## 研究问题与假设", "", card["hypothesis"], "",
        "## 实验设置", "",
        f"主指标：`{card['primary_metric']}`；指标方向：`{card['metric_direction']}`。",
        f"有效指标运行数：`{len(valid)}`；当前最佳记录值：`{best if best is not None else 'TBD'}`。", "",
        "## 实验结论", "",
    ]
    for conclusion in conclusions:
        zh += [f"### {conclusion['id']}", conclusion["zh"], f"证据运行：{', '.join(conclusion['evidence_refs'])}", ""]
    zh += ["## 证据与复现", "", f"证据清单：`{manifest_path}`。", f"统计分析：`{analysis_path.with_suffix('.md')}`。", ""]

    en = [
        f"# {card.get('title', experiment_id)}: English First Draft", "",
        "## Research Question and Hypothesis", "", card["hypothesis"], "",
        "## Experimental Setup", "",
        f"Primary metric: `{card['primary_metric']}`; direction: `{card['metric_direction']}`.",
        f"Valid metric-bearing runs: `{len(valid)}`; best recorded value: `{best if best is not None else 'TBD'}`.", "",
        "## Experimental Conclusions", "",
    ]
    for conclusion in conclusions:
        en += [f"### {conclusion['id']}", conclusion["en"], f"Evidence runs: {', '.join(conclusion['evidence_refs'])}", ""]
    en += ["## Evidence and Reproducibility", "", f"Evidence manifest: `{manifest_path}`.", f"Statistical analysis: `{analysis_path.with_suffix('.md')}`.", ""]

    paper_draft_zh.write_text("\n".join(zh), encoding="utf-8")
    paper_draft_en.write_text("\n".join(en), encoding="utf-8")
    return paper_draft_zh, paper_draft_en


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
    gated = is_human_gated(card, root)
    conclusion_gate = validate_conclusion_review(root, card, runs) if gated else {"valid": False, "errors": []}
    approved_conclusions = (conclusion_gate.get("review") or {}).get("approved_conclusions", []) if conclusion_gate.get("valid") else []

    paper = [f"# Manuscript input: {card.get('title', experiment_id)}", ""]
    if gated and conclusion_gate["valid"]:
        paper += [
            "> This manuscript input uses the conclusions manually verified and approved in the conclusion review record.", "",
            "## Research question and hypothesis", "", card["hypothesis"], "",
        ]
    else:
        paper += [
            "> This source-grounded manuscript input remains at the evidence review stage until the required human conclusion review is recorded.", "",
            "## Research question and hypothesis", "", card["hypothesis"], "",
        ]
    paper += ["## Evidence sources", ""]
    for source in card.get("source_papers", []):
        paper.append(f"- {source.get('title', 'TBD')}: {source.get('url', 'TBD')} ({source.get('role', 'TBD')})")
    paper += [
        "", "## Results ledger", "",
        f"- Valid metric-bearing runs: `{len(valid)}`",
        f"- Best recorded primary metric: `{best if best is not None else 'TBD'}`",
        f"- Evidence manifest: `{manifest_path}`",
        f"- Analysis: `{analysis_path.with_suffix('.md')}`", "",
    ]
    if gated and conclusion_gate["valid"]:
        paper += ["## Human-approved conclusions", ""]
        for conclusion in approved_conclusions:
            paper += [f"### {conclusion['id']}", conclusion["en"], f"Evidence: {', '.join(conclusion['evidence_refs'])}", ""]
    elif gated:
        paper += [
            "## Conclusion review gate", "",
            "The experiment results are available for human verification. No paper conclusion is generated until the human review record approves exact Chinese and English conclusion text.", "",
        ]
    else:
        paper += [
            "## Claim boundary", "",
            "- Pilot results are selection evidence.",
            "- Multi-seed stability is `TBD` until all declared seeds finish.",
            "- Independent-test evidence is `TBD` unless explicitly recorded in the experiment card.",
            "- Missing checkpoints, data availability records, and supplementary artifacts remain `TBD`.", "",
        ]
    (package / "paper_input.md").write_text("\n".join(paper), encoding="utf-8")

    paper_draft_zh: Path | None = None
    paper_draft_en: Path | None = None
    if gated and conclusion_gate["valid"]:
        paper_draft_zh, paper_draft_en = _approved_drafts(
            package, card, experiment_id, valid, best, manifest_path, analysis_path, approved_conclusions,
        )

    ppt = [
        f"# PPT handoff: {card.get('title', experiment_id)}", "",
        "> Route: `ppt-master` for narrative/layout/editable PPTX; Sivia for source-grounded scientific figures and figure review. Empirical plots must be generated from the evidence manifest.", "",
        "## Slide outline", "",
        "1. Research question and motivation — label literature-derived motivation, not measured gain.",
        "2. Fixed protocol — evaluator, data boundary, hardware and metric.",
        "3. Evidence-gated workflow — research package, human review, compute allocation, baseline, pilot, multi-seed and conclusion review.",
        "4. Baseline — only the recorded baseline metric and run conditions.",
        "5. Candidate pilot — show the real pilot outcome and label selection holdout.",
        "6. What is known and unknown — multi-seed, independent test, checkpoint and statistical evidence.",
        "7. Approved conclusion — use only conclusion text recorded by the human reviewer.",
        "8. Progress decision — ask for the specific approval or resource needed.",
        "", "## Figure and data rules", "",
        f"- Evidence manifest: `{manifest_path}`",
        "- Architecture/funnel schematics: use Sivia source-grounded design and audit.",
        "- Result chart: use real ledger values only; current pilot is single-seed exploratory evidence.",
        "- Do not use generated visual features, curves or metrics as experimental evidence.",
        "- For the human-gated workflow, the architecture draft and experiment matrix are reviewed before execution.", "",
    ]
    (package / "ppt_brief.md").write_text("\n".join(ppt), encoding="utf-8")

    current = workflow_state(root, experiment_id)
    status = "; ".join(evidence["claim_boundary"]["missing_evidence"]) or "none"
    observed = [run["metric"] for run in runs if run.get("metric") is not None]
    observed_text = ", ".join(str(value) for value in observed) if observed else "TBD"
    reference_text = analysis.get("reference", {}).get("metric")
    reference_text = reference_text if reference_text is not None else "TBD"
    if gated:
        boundary_line = "人工已审核结论，结论文本可写入论文初稿。" if conclusion_gate["valid"] else "等待人工核验实验结论；审核前不生成论文结论段。"
    else:
        boundary_line = "当前结果用于实验筛选，不能写成最终方法提升。"
    boss = [
        f"# 老板进度汇报：{card.get('title', experiment_id)}", "",
        "## 当前结论", "",
        f"- 工作流状态：`{current['state']}`",
        f"- 下一步：`{current['next_action']}`",
        f"- 已记录指标：`{observed_text}`；参考指标：`{reference_text}`",
        f"- 当前最佳保留指标：`{best if best is not None else 'TBD'}`",
        f"- 缺失证据：`{status}`",
        f"- 结论边界：{boundary_line}",
        "", "## 已完成", "",
        "- 实验卡、审批记录、运行日志、GPU检查和完整性回执已归档。",
        "- 论文输入包和PPT提纲已从同一证据清单生成。",
        "", "## 下一步", "",
        f"- 按工作流状态执行：`{current['next_action']}`。",
        ("- 按审核记录和证据清单继续生成论文与汇报材料." if gated else "- 补齐多种子和独立测试证据后再形成论文主张。"), "",
    ]
    (package / "boss_update.md").write_text("\n".join(boss), encoding="utf-8")

    index = {
        "experiment_id": experiment_id,
        "package_root": str(package),
        "analysis": str(analysis_path),
        "evidence_manifest": str(manifest_path),
        "paper_input": str(package / "paper_input.md"),
        "paper_draft_zh": str(paper_draft_zh) if paper_draft_zh else None,
        "paper_draft_en": str(paper_draft_en) if paper_draft_en else None,
        "ppt_brief": str(package / "ppt_brief.md"),
        "boss_update": str(package / "boss_update.md"),
        "claim_boundary": evidence["claim_boundary"],
    }
    (package / "package.json").write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return package
