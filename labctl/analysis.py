from __future__ import annotations

import json
import random
import statistics
from pathlib import Path
from typing import Any

from .card import load_card
from .ledger import Ledger


VALID_STATUSES = {"keep", "discard"}


def _project(root: Path) -> dict[str, Any]:
    return json.loads((root / "config" / "project.json").read_text(encoding="utf-8"))


def _card(root: Path, experiment_id: str) -> dict[str, Any]:
    return load_card(root / "experiments" / "cards" / f"{experiment_id}.json")


def _valid(runs: list[dict[str, Any]], stage: str | None = None) -> list[dict[str, Any]]:
    return [
        run for run in runs
        if (stage is None or run.get("stage") == stage)
        and run.get("status") in VALID_STATUSES
        and run.get("metric") is not None
    ]


def _percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot calculate a percentile from no values")
    index = (len(ordered) - 1) * q
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def describe(values: list[float], bootstrap_samples: int = 2000) -> dict[str, Any]:
    """Return descriptive statistics without implying significance.

    A one-run result deliberately returns TBD for spread and intervals. This
    prevents the current single-seed pilot from being presented as statistical
    evidence.
    """
    if not values:
        return {"n": 0, "mean": None, "median": None, "std": None,
                "min": None, "max": None, "bootstrap_mean_ci95": None,
                "boundary": "TBD: no valid metric"}
    result: dict[str, Any] = {
        "n": len(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "std": statistics.stdev(values) if len(values) > 1 else None,
        "min": min(values),
        "max": max(values),
        "bootstrap_mean_ci95": None,
        "boundary": "descriptive only; no significance claim",
    }
    if len(values) > 1:
        rng = random.Random(20261005)
        samples = [statistics.mean(rng.choices(values, k=len(values))) for _ in range(bootstrap_samples)]
        result["bootstrap_mean_ci95"] = [_percentile(samples, 0.025), _percentile(samples, 0.975)]
    else:
        result["boundary"] = "TBD: one valid run; variance and confidence interval are not estimable"
    return result


def analyze_experiment(root: str | Path, experiment_id: str, output: str | Path | None = None) -> Path:
    root = Path(root).resolve()
    card = _card(root, experiment_id)
    project = _project(root)
    ledger = Ledger(root / project["ledger_path"])
    runs = ledger.runs(experiment_id)
    direction = card["metric_direction"]

    reference_runs = ledger.runs(card["reference_experiment_id"]) if card.get("reference_experiment_id") else []
    baseline = _valid(runs, "baseline") or _valid(reference_runs, "baseline")
    baseline_by_seed = {run.get("seed"): run for run in baseline}
    reference_metric = baseline[0]["metric"] if baseline else (
        float(card["reference_metric"]) if card.get("reference_metric") is not None else None
    )

    comparisons: list[dict[str, Any]] = []
    for run in runs:
        if run.get("stage") not in {"pilot", "full"} or run.get("metric") is None:
            continue
        reference = baseline_by_seed.get(run.get("seed"))
        ref_value = reference["metric"] if reference else reference_metric
        delta = run["metric"] - ref_value if ref_value is not None else None
        improves = None if delta is None else (delta < 0 if direction == "minimize" else delta > 0)
        comparisons.append({
            "run_id": run["run_id"], "stage": run["stage"], "seed": run.get("seed"),
            "metric": run["metric"], "reference_metric": ref_value, "delta": delta,
            "improves": improves, "status": run["status"],
        })

    multi_seed = _valid(runs, "multi_seed")
    independent_test = card.get("independent_test")
    independent_test_ready = bool(independent_test) and independent_test not in {"TBD", "pending"}
    requirements = {
        "locked_code_commit": bool(baseline and all(run.get("receipt_path") for run in baseline)),
        "multi_seed": bool(card.get("seeds")) and {run.get("seed") for run in multi_seed} >= set(card.get("seeds", [])),
        "independent_test": independent_test_ready,
        "statistics": len(multi_seed) >= 2,
    }
    payload = {
        "experiment_id": experiment_id,
        "title": card.get("title", experiment_id),
        "primary_metric": card["primary_metric"],
        "metric_direction": direction,
        "protocol_boundary": "upstream-comparable" if card.get("upstream_comparable") else "hardware-adapted/local protocol",
        "reference": {
            "metric": reference_metric,
            "source": "referenced baseline ledger row" if reference_runs and baseline else ("baseline ledger row" if baseline else ("experiment card reference_metric" if card.get("reference_metric") is not None else "TBD")),
            "run_id": baseline[0]["run_id"] if baseline else None,
        },
        "reference_runs": [
            {"run_id": run["run_id"], "stage": run["stage"], "seed": run.get("seed"),
             "status": run["status"], "metric": run.get("metric"),
             "runtime_seconds": run.get("runtime_seconds"), "peak_vram_mb": run.get("peak_vram_mb")}
            for run in reference_runs
        ],
        "runs": [
            {"run_id": run["run_id"], "stage": run["stage"], "seed": run.get("seed"),
             "status": run["status"], "metric": run.get("metric"),
             "runtime_seconds": run.get("runtime_seconds"), "peak_vram_mb": run.get("peak_vram_mb")}
            for run in runs
        ],
        "comparisons": comparisons,
        "multi_seed": {
            "runs": [run["run_id"] for run in multi_seed],
            "statistics": describe([run["metric"] for run in multi_seed]),
        },
        "claim_gate": {
            "requirements": requirements,
            "paper_claim_ready": all(requirements.values()),
            "independent_test": independent_test or "TBD",
            "interpretation": "TBD: evidence is exploratory or incomplete" if not all(requirements.values()) else "locked evidence may support a scoped claim",
        },
    }
    target = Path(output) if output else root / "reports" / f"{experiment_id}-analysis.json"
    if not target.is_absolute():
        target = root / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    markdown = target.with_suffix(".md")
    lines = [
        f"# Evidence analysis: {payload['title']}", "",
        f"Primary metric: `{payload['primary_metric']}` ({payload['metric_direction']}); protocol: `{payload['protocol_boundary']}`.", "",
        "This is a ledger-derived analysis. It does not convert a pilot result into a general claim.", "",
        "## Runs", "", "| stage | seed | status | metric | runtime (s) | peak VRAM (MB) | run id |", "|---|---:|---|---:|---:|---:|---|",
    ]
    for run in payload["runs"]:
        lines.append(f"| {run['stage']} | {run.get('seed', '')} | {run['status']} | {run.get('metric', 'TBD') if run.get('metric') is not None else 'TBD'} | {run.get('runtime_seconds', 'TBD') if run.get('runtime_seconds') is not None else 'TBD'} | {run.get('peak_vram_mb', 'TBD') if run.get('peak_vram_mb') is not None else 'TBD'} | `{run['run_id']}` |")
    lines += ["", "## Paired comparisons", "", "| run | stage | metric | reference | delta | improves |", "|---|---|---:|---:|---:|---|"]
    for row in comparisons:
        lines.append(f"| `{row['run_id']}` | {row['stage']} | {row['metric']} | {row['reference_metric'] if row['reference_metric'] is not None else 'TBD'} | {row['delta'] if row['delta'] is not None else 'TBD'} | {row['improves'] if row['improves'] is not None else 'TBD'} |")
    stats = payload["multi_seed"]["statistics"]
    lines += ["", "## Multi-seed statistics", "", f"- n: `{stats['n']}`", f"- mean: `{stats['mean'] if stats['mean'] is not None else 'TBD'}`", f"- standard deviation: `{stats['std'] if stats['std'] is not None else 'TBD'}`", f"- bootstrap 95% interval: `{stats['bootstrap_mean_ci95'] if stats['bootstrap_mean_ci95'] is not None else 'TBD'}`", f"- boundary: {stats['boundary']}", "", "## Claim gate", ""]
    for key, value in requirements.items():
        lines.append(f"- `{key}`: `{value}`")
    lines += ["", f"Paper claim ready: **{payload['claim_gate']['paper_claim_ready']}**.", f"Independent test: **{payload['claim_gate']['independent_test']}**.", ""]
    markdown.write_text("\n".join(lines), encoding="utf-8")
    return target
