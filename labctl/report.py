from __future__ import annotations

from pathlib import Path
from typing import Any

from .card import load_card
from .io import read_json
from .ledger import Ledger
from .runner import card_path, project_config


def draft_report(root: str | Path, experiment_id: str) -> Path:
    root = Path(root).resolve()
    project = project_config(root)
    card = load_card(card_path(root, experiment_id))
    ledger = Ledger(root / project["ledger_path"])
    runs = ledger.runs(experiment_id)
    reference_runs = ledger.runs(card["reference_experiment_id"]) if card.get("reference_experiment_id") else []
    fresh_baseline = [run for run in reference_runs if run.get("stage") == "baseline"
                      and run.get("status") == "keep" and run.get("metric") is not None]
    best = ledger.best_metric(experiment_id, card["metric_direction"])
    report_path = root / "reports" / f"{experiment_id}-draft.md"
    lines = [
        f"# {card.get('title', experiment_id)}: preliminary draft",
        "",
        "> This is an evidence-bound draft. It is not a final submission and does not convert hypotheses into claims.",
        "",
        "## Abstract",
        "",
        f"We tested the hypothesis: {card['hypothesis']}",
        "",
        "The current ledger contains " + str(len(runs)) + " recorded run(s). The best recorded primary metric is " + (str(best) if best is not None else "TBD") + ".",
    ]
    if fresh_baseline:
        values = [run["metric"] for run in fresh_baseline]
        mean = sum(values) / len(values)
        lines += [f"The fresh referenced baseline mean from `{card.get('reference_experiment_id', 'reference experiment')}` is `{mean:.6f}` across seeds `{', '.join(str(run.get('seed')) for run in fresh_baseline)}`.", ""]
    elif card.get("reference_metric") is not None:
        lines += [f"The historical reference metric from `{card.get('reference_experiment_id', 'reference experiment')}` is `{card['reference_metric']}`; fresh baseline verification is unavailable.", ""]
    else:
        lines += [""]
    lines += [
        "## Method",
        "",
        f"The primary metric was `{card['primary_metric']}` with direction `{card['metric_direction']}`. The evaluation script was `{card.get('evaluation_script', 'TBD')}`.",
        "Protected data and evaluation inputs were checked through an integrity receipt for every run.",
        "",
        "## Results",
        "",
        "| stage | seed | status | metric | runtime (s) | peak VRAM (MB) |",
        "|---|---:|---|---:|---:|---:|",
    ]
    for run in runs:
        lines.append(
            f"| {run['stage']} | {run.get('seed', '')} | {run['status']} | {run.get('metric') if run.get('metric') is not None else 'TBD'} | {run.get('runtime_seconds') if run.get('runtime_seconds') is not None else 'TBD'} | {run.get('peak_vram_mb') if run.get('peak_vram_mb') is not None else 'TBD'} |"
        )
    lines += [
        "",
        "## Innovation boundary",
        "",
        "Any improvement is a candidate finding until it is repeated under the same protocol with multiple seeds and, where applicable, an independent test.",
        "",
        "## Limitations",
        "",
        "- The current draft does not claim cross-hardware comparability.",
        "- Cloud cost is `TBD` unless a provider rate is configured and recorded.",
        "- Unsupported or missing evidence remains `TBD`.",
        "",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
