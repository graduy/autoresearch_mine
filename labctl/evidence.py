from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .card import load_card
from .ledger import Ledger
from .research_gate import is_human_gated, validate_conclusion_review


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: str | Path, experiment_id: str, output: str | Path | None = None) -> Path:
    root = Path(root).resolve()
    card = load_card(root / "experiments" / "cards" / f"{experiment_id}.json")
    project = json.loads((root / "config" / "project.json").read_text(encoding="utf-8"))
    ledger = Ledger(root / project["ledger_path"])
    runs = ledger.runs(experiment_id)
    artifacts = ledger.artifacts(experiment_id)
    receipt_records: list[dict[str, Any]] = []
    for run in runs:
        receipt_path = Path(run["receipt_path"]) if run.get("receipt_path") else None
        receipt = None
        if receipt_path and receipt_path.is_file():
            try:
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                receipt = {"parse_error": True}
        receipt_records.append({
            "run_id": run["run_id"], "stage": run["stage"], "seed": run.get("seed"),
            "status": run["status"], "metric": run.get("metric"),
            "code_commit": (receipt or {}).get("after", {}).get("head"),
            "branch": (receipt or {}).get("after", {}).get("branch"),
            "receipt_path": str(receipt_path) if receipt_path else None,
            "receipt_sha256": _sha256(receipt_path) if receipt_path else None,
        })
    declared_seeds = set(card.get("seeds", []))
    kept_multi = {run.get("seed") for run in runs if run["stage"] == "multi_seed" and run["status"] == "keep" and run.get("metric") is not None}
    conclusion_gate = validate_conclusion_review(root, card, runs) if is_human_gated(card, root) else {"valid": True, "errors": []}
    human_gate_ready = conclusion_gate["valid"]
    missing_evidence = {
        "multi_seed": bool(declared_seeds) and kept_multi >= declared_seeds,
        "independent_test": bool(card.get("independent_test")),
        "checkpoint": any("checkpoint" in str(artifact["path"]).lower() for artifact in artifacts),
    }
    if is_human_gated(card, root):
        missing_evidence.update({
            "innovation_package": bool(conclusion_gate.get("allocation", {}).get("innovation", {}).get("package", {}).get("valid")),
            "innovation_review": bool(conclusion_gate.get("allocation", {}).get("innovation", {}).get("valid")),
            "compute_allocation": bool(conclusion_gate.get("allocation", {}).get("valid")),
            "human_conclusion_review": human_gate_ready,
        })
    manifest = {
        "schema_version": 1,
        "experiment_id": experiment_id,
        "title": card.get("title", experiment_id),
        "generated_by": "autoresearch-lab evidence layer",
        "source_papers": card.get("source_papers", []),
        "protocol": {
            "primary_metric": card["primary_metric"],
            "metric_direction": card["metric_direction"],
            "evaluation_script": card.get("evaluation_script", "TBD"),
            "base_commit": card.get("base_commit", "TBD"),
            "dataset_manifest_hash": card.get("dataset_manifest_hash", "TBD"),
            "upstream_comparable": card.get("upstream_comparable", "TBD"),
        },
        "runs": receipt_records,
        "artifacts": [
            {**artifact, "exists": Path(artifact["path"]).is_file(), "sha256": _sha256(Path(artifact["path"]))}
            for artifact in artifacts
        ],
        "claim_boundary": {
            "selection_holdout": "pilot results select candidates; they do not establish a final claim",
            "multi_seed": "stability evidence only",
            "independent_test": card.get("independent_test", "TBD"),
            "human_gate": "approved" if human_gate_ready else ("required" if is_human_gated(card, root) else "not_enabled"),
            "paper_ready": bool(declared_seeds) and kept_multi >= declared_seeds and bool(card.get("independent_test")) and human_gate_ready,
            "missing_evidence": [key for key, present in missing_evidence.items() if not present],
        },
    }
    target = Path(output) if output else root / "reports" / f"{experiment_id}-evidence-manifest.json"
    if not target.is_absolute():
        target = root / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target
