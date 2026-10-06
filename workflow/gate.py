#!/usr/bin/env python3
"""Small control-plane gate for orchestration rounds.

The local runner writes authoritative ledger rows. This gate only derives
state or validates a child result; it never turns a model recommendation into
human approval and never inserts a synthetic metric.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from labctl.workflow import state, validate_ingest  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="workflow/gate.py")
    sub = parser.add_subparsers(dest="command", required=True)
    for command_name in ("next", "validate"):
        command = sub.add_parser(command_name)
        command.add_argument("--experiment", required=True)
    ingest = sub.add_parser("ingest")
    ingest.add_argument("--experiment", required=True)
    ingest.add_argument("--result", required=True)
    args = parser.parse_args(argv)
    if args.command in {"next", "validate"}:
        payload = state(ROOT, args.experiment)
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        if args.command == "validate" and payload["state"] in {
            "innovation_package", "human_innovation_review", "human_compute_allocation",
            "human_approval", "blocked", "candidate_rejected", "conclusion_review", "paper_draft",
        }:
            return 1
        return 0
    print(json.dumps(validate_ingest(ROOT, args.experiment, args.result), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
