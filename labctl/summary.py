from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from .card import load_card
from .ledger import Ledger
from .workflow import state as workflow_state


TZ = ZoneInfo("Asia/Shanghai")


def _parse_since(value: str | None) -> datetime:
    now = datetime.now(TZ)
    if not value:
        return now - timedelta(days=7)
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=TZ) if parsed.tzinfo is None else parsed.astimezone(TZ)


def write_weekly_summary(root: str | Path, since: str | None = None, output: str | None = None) -> Path:
    root = Path(root).resolve()
    project = json.loads((root / "config" / "project.json").read_text(encoding="utf-8"))
    ledger = Ledger(root / project["ledger_path"])
    start = _parse_since(since)
    start_ts = start.timestamp()
    cards = sorted((root / "experiments" / "cards").glob("*.json"))
    runs = [run for run in ledger.runs() if float(run.get("created_at") or 0) >= start_ts]
    lines = [
        "# Autoresearch weekly evidence summary",
        "",
        f"Window start (Asia/Shanghai): `{start.isoformat(timespec='seconds')}`",
        "",
        "This summary reports ledger evidence only. Missing values remain `TBD`; hypotheses and literature are not measured results.",
        "",
        "## Runs in window",
        "",
        "| experiment | stage | seed | status | primary metric | runtime (s) |",
        "|---|---|---:|---|---:|---:|",
    ]
    if runs:
        for run in runs:
            lines.append(
                f"| {run['experiment_id']} | {run['stage']} | {run.get('seed', '')} | {run['status']} | "
                f"{run.get('metric') if run.get('metric') is not None else 'TBD'} | "
                f"{run.get('runtime_seconds') if run.get('runtime_seconds') is not None else 'TBD'} |"
            )
    else:
        lines.append("| TBD | TBD | TBD | no new ledger runs | TBD | TBD |")

    lines += ["", "## Current workflow state", "", "| experiment | state | next action | blockers |", "|---|---|---|---|"]
    attention: list[str] = []
    for card_path in cards:
        card = load_card(card_path)
        experiment_id = card["experiment_id"]
        current = workflow_state(root, experiment_id)
        blockers = "; ".join(current.get("blockers") or []) or "none"
        lines.append(f"| {experiment_id} | {current['state']} | {current['next_action']} | {blockers} |")
        if current["state"] in {"human_approval", "blocked", "candidate_rejected"}:
            attention.append(f"- `{experiment_id}` requires action: {current['next_action']}.")

    lines += ["", "## Requires attention", ""]
    lines.extend(attention or ["No blocking workflow state was recorded in the current cards."])
    target = Path(output) if output else root / "reports" / "weekly-summary.md"
    if not target.is_absolute():
        target = root / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
