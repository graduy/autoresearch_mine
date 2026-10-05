from __future__ import annotations

import argparse
import getpass
import json
from pathlib import Path

from .card import load_card
from .analysis import analyze_experiment
from .deliver import build_package
from .evidence import build_manifest
from .ledger import Ledger
from .report import draft_report
from .figures import write_figures
from .runner import archive_experiment, card_path, project_config, run_stage
from .workflow import state as workflow_state, validate_ingest


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="labctl")
    sub = parser.add_subparsers(dest="command", required=True)

    card = sub.add_parser("card")
    card_sub = card.add_subparsers(dest="card_command", required=True)
    card_validate = card_sub.add_parser("validate")
    card_validate.add_argument("--card", required=True)

    approval = sub.add_parser("approval")
    approval_sub = approval.add_subparsers(dest="approval_command", required=True)
    approval_record = approval_sub.add_parser("record")
    approval_record.add_argument("--experiment", required=True)
    approval_record.add_argument("--decision", choices=["approve", "reject", "revoke"], required=True)
    approval_record.add_argument("--source", required=True)
    approval_record.add_argument("--actor", default=getpass.getuser())

    run = sub.add_parser("run")
    run.add_argument("--experiment", required=True)
    run.add_argument("--stage", choices=["baseline", "pilot", "full", "multi_seed"], required=True)
    run.add_argument("--seed", type=int)

    server = sub.add_parser("server")
    server_sub = server.add_subparsers(dest="server_command", required=True)
    for name in ("create", "destroy"):
        command = server_sub.add_parser(name)
        command.add_argument("--experiment", required=True)

    ledger = sub.add_parser("ledger")
    ledger_sub = ledger.add_subparsers(dest="ledger_command", required=True)
    show = ledger_sub.add_parser("show")
    show.add_argument("--experiment")

    report = sub.add_parser("report")
    report_sub = report.add_subparsers(dest="report_command", required=True)
    draft = report_sub.add_parser("draft")
    draft.add_argument("--experiment", required=True)

    archive = sub.add_parser("archive")
    archive.add_argument("--experiment", required=True)

    figures = sub.add_parser("figures")

    workflow = sub.add_parser("workflow")
    workflow_sub = workflow.add_subparsers(dest="workflow_command", required=True)
    for name in ("status", "next", "validate"):
        command = workflow_sub.add_parser(name)
        command.add_argument("--experiment", required=True)
    ingest = workflow_sub.add_parser("ingest")
    ingest.add_argument("--experiment", required=True)
    ingest.add_argument("--result", required=True)

    summary = sub.add_parser("summary")
    summary_sub = summary.add_subparsers(dest="summary_command", required=True)
    weekly = summary_sub.add_parser("weekly")
    weekly.add_argument("--since")
    weekly.add_argument("--output")

    analysis = sub.add_parser("analysis")
    analysis_sub = analysis.add_subparsers(dest="analysis_command", required=True)
    analyze = analysis_sub.add_parser("run")
    analyze.add_argument("--experiment", required=True)
    manifest = analysis_sub.add_parser("manifest")
    manifest.add_argument("--experiment", required=True)

    pipeline = sub.add_parser("pipeline")
    pipeline_sub = pipeline.add_subparsers(dest="pipeline_command", required=True)
    pipeline_status = pipeline_sub.add_parser("status")
    pipeline_status.add_argument("--experiment", required=True)
    package = pipeline_sub.add_parser("package")
    package.add_argument("--experiment", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = _root()
    project = project_config(root)
    ledger = Ledger(root / project["ledger_path"])
    if args.command == "card":
        card = load_card(args.card)
        print(json.dumps({"valid": True, "experiment_id": card["experiment_id"]}, ensure_ascii=False))
        return 0
    if args.command == "approval":
        card = load_card(card_path(root, args.experiment))
        ledger.register_experiment(args.experiment, card)
        ledger.approval(args.experiment, args.decision, args.source, args.actor)
        print(f"approval={args.decision} experiment={args.experiment} source={args.source}")
        return 0
    if args.command == "run":
        run_stage(root, args.experiment, args.stage, args.seed)
        return 0
    if args.command == "server":
        if args.server_command == "create":
            load_card(card_path(root, args.experiment))
            if not ledger.approved(args.experiment):
                raise SystemExit("server create requires approval")
            path = root / "artifacts" / "servers" / f"{args.experiment}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"experiment_id": args.experiment, "backend": "local", "status": "active"}, indent=2) + "\n", encoding="utf-8")
            print(f"local_server={path}")
        else:
            path = root / "artifacts" / "servers" / f"{args.experiment}.json"
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                data["status"] = "destroyed"
                path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            print(f"local_server_destroyed={args.experiment}")
        return 0
    if args.command == "ledger":
        for row in ledger.runs(args.experiment):
            print(json.dumps(row, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "report":
        print(draft_report(root, args.experiment))
        return 0
    if args.command == "archive":
        print(archive_experiment(root, args.experiment))
        return 0
    if args.command == "figures":
        for path in write_figures(root):
            print(path)
        return 0
    if args.command == "workflow":
        if args.workflow_command in {"status", "next", "validate"}:
            current = workflow_state(root, args.experiment)
            print(json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True))
            if args.workflow_command == "validate" and current["state"] in {"human_approval", "blocked", "candidate_rejected"}:
                return 1
            return 0
        if args.workflow_command == "ingest":
            print(json.dumps(validate_ingest(root, args.experiment, args.result), ensure_ascii=False, indent=2, sort_keys=True))
            return 0
    if args.command == "summary":
        if args.summary_command == "weekly":
            from .summary import write_weekly_summary
            output = write_weekly_summary(root, since=args.since, output=args.output)
            print(output)
            return 0
    if args.command == "analysis":
        if args.analysis_command == "run":
            print(analyze_experiment(root, args.experiment))
            return 0
        if args.analysis_command == "manifest":
            print(build_manifest(root, args.experiment))
            return 0
    if args.command == "pipeline":
        from .workflow import state as workflow_state
        routes = json.loads((root / "config" / "skill_routes.json").read_text(encoding="utf-8"))
        if args.pipeline_command == "status":
            current = workflow_state(root, args.experiment)
            print(json.dumps({"experiment": current, "routes": routes}, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if args.pipeline_command == "package":
            print(build_package(root, args.experiment))
            return 0
    return 2
