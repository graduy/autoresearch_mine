from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import read_json


REQUIRED = {
    "experiment_id", "hypothesis", "primary_metric", "metric_direction",
    "stages", "constraints", "human_approval",
}


def load_card(path: str | Path) -> dict[str, Any]:
    card = read_json(path)
    missing = sorted(REQUIRED - set(card))
    if missing:
        raise ValueError(f"card missing fields: {', '.join(missing)}")
    if not isinstance(card["stages"], dict) or not card["stages"]:
        raise ValueError("card.stages must be a non-empty object")
    if "seeds" in card and (not isinstance(card["seeds"], list) or not all(isinstance(seed, int) for seed in card["seeds"])):
        raise ValueError("card.seeds must be a list of integers")
    if card["metric_direction"] not in {"minimize", "maximize"}:
        raise ValueError("metric_direction must be minimize or maximize")
    constraints = card["constraints"]
    for key in ("max_runtime_seconds", "max_cost_usd", "max_runs"):
        if key in constraints and constraints[key] is not None and float(constraints[key]) < 0:
            raise ValueError(f"constraint {key} cannot be negative")
    for stage, spec in card["stages"].items():
        if stage not in {"baseline", "pilot", "full", "multi_seed"}:
            raise ValueError(f"unsupported stage: {stage}")
        if not isinstance(spec, dict) or not isinstance(spec.get("command"), list) or not spec["command"]:
            raise ValueError(f"stage {stage} needs a non-empty command list")
        if not spec.get("metric_pattern"):
            raise ValueError(f"stage {stage} needs metric_pattern")
    if "baseline" not in card["stages"] and card.get("reference_metric") is None:
        raise ValueError("a card without a baseline stage needs reference_metric")
    if "multi_seed" in card["stages"] and not card.get("seeds"):
        raise ValueError("multi_seed requires at least one declared seed")
    return card
