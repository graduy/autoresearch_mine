"""Human review contracts for literature-to-paper research.

Review records are provenance assertions backed by the actual user message;
JSON flags alone cannot authenticate that a human performed a review.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from .io import read_json
from .ledger import Ledger

HUMAN_GATED_WORKFLOW = "human_gated_research_to_paper"
PACKAGE_FIELDS = (
    "literature_synthesis", "innovation_proposal", "compute_budget",
    "experiment_matrix", "architecture_spec", "architecture_draft",
    "baseline_reference",
)
REVIEW_FIELDS = ("innovation", "compute", "conclusion")
BASELINE_QUARTILES = {"CAS": {"1", "2"}}
BASELINE_COMPARISON_KEYS = {
    "model_baseline", "data_split", "training_protocol",
    "evaluation_metrics", "ablation_protocol",
}
RESEARCH_STRATEGY = "reference_first_reproduction_and_whole_system_optimization"
MATRIX_STRATEGY_ROLES = {"reference_reproduction", "recent_optimization", "ablation"}
WAITING_STATES = {
    "innovation_package", "human_innovation_review", "human_compute_allocation",
    "human_approval", "blocked", "candidate_rejected", "experiment_matrix",
    "conclusion_review", "paper_draft",
}


def is_human_gated(card: dict[str, Any], root: str | Path | None = None) -> bool:
    # New cards opt in explicitly. Existing cards are listed in the policy file
    # so an old run is not silently reclassified after the workflow changes.
    if card.get("workflow_mode") == HUMAN_GATED_WORKFLOW:
        return True
    if card.get("workflow_mode") in {"legacy", "historical"}:
        return False
    historical: list[str] = []
    if root is not None:
        config = Path(root) / "config/research_policy.json"
        if config.is_file():
            historical = read_json(config).get("historical_experiments", [])
    return False if card.get("experiment_id") in historical else bool(card.get("task_id") and card.get("research_package"))


def resolve(root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def file_hash(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _json(path: Path | None, label: str, errors: list[str]) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        errors.append(f"{label}: file does not exist ({path})")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: invalid JSON ({exc})")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label}: JSON root must be an object")
        return None
    return value


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _number(value: Any, *, positive: bool = False, integer: bool = False) -> bool:
    return (type(value) in (int, float) and math.isfinite(value)
            and (value > 0 if positive else value >= 0)
            and (not integer or value == int(value)))


def _placeholder(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(_placeholder(item) for item in value)
    return isinstance(value, str) and value.strip().casefold() in {"tbd", "待定", "待补充", "to be determined"}


def package_paths(root: str | Path, card: dict[str, Any]) -> dict[str, Path | None]:
    package = card.get("research_package", {})
    if not isinstance(package, dict):
        package = {}
    return {field: resolve(Path(root).resolve(), package.get(field)) for field in PACKAGE_FIELDS}


def review_paths(root: str | Path, card: dict[str, Any]) -> dict[str, Path | None]:
    reviews = card.get("human_reviews", {})
    if not isinstance(reviews, dict):
        reviews = {}
    return {field: resolve(Path(root).resolve(), reviews.get(field)) for field in REVIEW_FIELDS}


def _result(errors: list[str], **extra: Any) -> dict[str, Any]:
    return {"valid": not errors, "errors": errors, **extra}


def _required_text_fields(value: Any, label: str, fields: tuple[str, ...], errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return
    for field in fields:
        if not _text(value.get(field)):
            errors.append(f"{label}.{field} is required")


def _required_text_list(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value or not all(_text(item) for item in value):
        errors.append(f"{label} must be a non-empty list of text values")


def _valid_year(value: Any) -> bool:
    return type(value) is int and 1900 <= value <= datetime.now().year


def _valid_timestamp(value: Any) -> bool:
    if not _text(value):
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def validate_baseline_reference(root: str | Path, card: dict[str, Any]) -> dict[str, Any]:
    """Validate the reference paper shown at the first human-review gate.

    Journals require a source-backed SCI/SCIE 1/2 ranking and JIF > 4.
    Conferences use peer-review and standing evidence instead of journal
    metrics, with venue quality confirmed in the same human review. This
    validates provenance declarations, not the external sources themselves.
    """
    root = Path(root).resolve()
    path = package_paths(root, card)["baseline_reference"]
    errors: list[str] = []
    payload = _json(path, "baseline_reference", errors)
    if payload is None:
        return _result(errors, path=str(path) if path else None, reference=None, comparison_table=[])

    if payload.get("research_strategy") != RESEARCH_STRATEGY:
        errors.append(f"baseline_reference.research_strategy must be {RESEARCH_STRATEGY}")
    if payload.get("publication_positioning") != "reproduction_plus_whole_system_optimization":
        errors.append("baseline_reference.publication_positioning must be reproduction_plus_whole_system_optimization")

    paper = payload.get("paper")
    _required_text_fields(
        paper, "baseline_reference.paper",
        ("title", "venue", "venue_type", "publication_source", "full_text_source", "verified_at"), errors,
    )
    if isinstance(paper, dict):
        if not _valid_year(paper.get("year")):
            errors.append("baseline_reference.paper.year must be a valid publication year")
        if not _valid_timestamp(paper.get("verified_at")):
            errors.append("baseline_reference.paper.verified_at needs ISO-8601 with a timezone")
        if not (_text(paper.get("doi")) or _text(paper.get("url"))):
            errors.append("baseline_reference.paper needs doi or url")
        venue_type = paper.get("venue_type")
        if venue_type == "journal":
            _required_text_fields(paper, "baseline_reference.paper", (
                "indexing_source", "quartile_system", "quartile_category", "quartile_source",
                "impact_factor_source",
            ), errors)
            if paper.get("indexing") not in ("SCI", "SCIE"):
                errors.append("baseline_reference.paper.indexing must be SCI or SCIE")
            system = paper.get("quartile_system")
            if system != "CAS":
                errors.append("baseline_reference.paper.quartile_system must be CAS")
            elif paper.get("sci_quartile") not in tuple(BASELINE_QUARTILES[system]):
                errors.append("baseline_reference.paper.sci_quartile must be CAS major-category 1 or 2")
            if system == "CAS" and paper.get("quartile_scope") != "major":
                errors.append("baseline_reference.paper.quartile_scope must be major for CAS")
            for key in ("quartile_year", "impact_factor_year"):
                if not _valid_year(paper.get(key)):
                    errors.append(f"baseline_reference.paper.{key} must identify the metric year")
            impact_factor = paper.get("impact_factor")
            if not _number(impact_factor, positive=True) or impact_factor <= 4:
                errors.append("baseline_reference.paper.impact_factor must be strictly greater than 4")
        elif venue_type == "conference":
            quality = paper.get("conference_quality")
            _required_text_fields(quality, "baseline_reference.paper.conference_quality", (
                "standing_basis", "standing_source", "peer_review_source", "proceedings_source",
            ), errors)
            if isinstance(quality, dict):
                if quality.get("peer_reviewed") is not True:
                    errors.append("conference reference must have verified peer review")
                if quality.get("paper_type") not in ("full", "regular"):
                    errors.append("conference baseline must be a full or regular paper")
            # Do not manufacture journal quartiles or impact factors for a conference.
            for key in ("sci_quartile", "impact_factor"):
                if paper.get(key) is not None:
                    errors.append(f"conference reference must leave journal field {key} absent or null")
        else:
            errors.append("baseline_reference.paper.venue_type must be journal or conference")

    reference_baseline = payload.get("reference_baseline")
    _required_text_fields(
        reference_baseline, "baseline_reference.reference_baseline",
        ("name", "model", "input_or_sequence", "source_location"), errors,
    )
    if isinstance(reference_baseline, dict):
        _required_text_list(reference_baseline.get("reported_metrics"),
                            "baseline_reference.reference_baseline.reported_metrics", errors)

    reference_scheme = payload.get("reference_experiment_scheme")
    _required_text_fields(
        reference_scheme, "baseline_reference.reference_experiment_scheme",
        ("dataset", "split", "training", "evaluation", "ablation", "source_location"), errors,
    )
    if isinstance(reference_scheme, dict):
        _required_text_list(reference_scheme.get("metrics"),
                            "baseline_reference.reference_experiment_scheme.metrics", errors)

    reproduction = payload.get("reference_reproduction")
    _required_text_fields(
        reproduction, "baseline_reference.reference_reproduction",
        ("protocol_lock", "allowed_deviations", "acceptance_rule", "source_location"), errors,
    )

    optimization = payload.get("recent_optimization")
    _required_text_fields(
        optimization, "baseline_reference.recent_optimization",
        ("optimization_scope", "coherence_rationale", "source_location"), errors,
    )
    if isinstance(optimization, dict):
        if optimization.get("optimization_scope") != "whole_system":
            errors.append("baseline_reference.recent_optimization.optimization_scope must be whole_system")
        _required_text_list(optimization.get("selected_methods"),
                            "baseline_reference.recent_optimization.selected_methods", errors)
        _required_text_list(optimization.get("method_sources"),
                            "baseline_reference.recent_optimization.method_sources", errors)
        _required_text_list(optimization.get("changed_components"),
                            "baseline_reference.recent_optimization.changed_components", errors)
        for key in ("selected_methods", "changed_components"):
            values = optimization.get(key)
            if isinstance(values, list) and all(_text(item) for item in values) and len(set(values)) < 2:
                errors.append(f"baseline_reference.recent_optimization.{key} needs at least two distinct values for a whole-system scheme")
        years = optimization.get("publication_years")
        if (not isinstance(years, list) or not years
                or not all(_valid_year(year) for year in years)):
            errors.append("baseline_reference.recent_optimization.publication_years must contain valid years")
        methods = optimization.get("selected_methods")
        sources = optimization.get("method_sources")
        if isinstance(methods, list) and (not isinstance(sources, list) or not isinstance(years, list)
                                         or len(methods) != len(sources) or len(methods) != len(years)):
            errors.append("recent_optimization selected_methods, method_sources and publication_years must align")

    local_library = payload.get("local_code_library")
    _required_text_fields(local_library, "baseline_reference.local_code_library",
                          ("root", "scope_basis"), errors)
    if isinstance(local_library, dict):
        lookback = local_library.get("lookback_years")
        if not _number(lookback, positive=True, integer=True):
            errors.append("baseline_reference.local_code_library.lookback_years must be a positive integer (default 2)")
        _required_text_list(local_library.get("cv_venue_scope"),
                            "baseline_reference.local_code_library.cv_venue_scope", errors)
        _required_text_list(local_library.get("ml_venue_scope"),
                            "baseline_reference.local_code_library.ml_venue_scope", errors)
        scope = set()
        for key in ("cv_venue_scope", "ml_venue_scope"):
            venues = local_library.get(key)
            if isinstance(venues, list) and all(_text(venue) for venue in venues):
                scope.update(venues)
                if len(set(venues)) < 3:
                    errors.append(f"baseline_reference.local_code_library.{key} must list at least three venues")
                if len(set(venues)) != len(venues):
                    errors.append(f"baseline_reference.local_code_library.{key} must not repeat venues")
        library_root = resolve(root, local_library.get("root"))
        if library_root is None or not library_root.is_dir():
            errors.append("baseline_reference.local_code_library.root must be an existing local directory")
        records = local_library.get("records")
        recorded_methods = set()
        if not isinstance(records, list) or not records:
            errors.append("baseline_reference.local_code_library.records must be a non-empty list")
        else:
            for index, record in enumerate(records):
                _required_text_fields(
                    record, f"baseline_reference.local_code_library.records[{index}]",
                    ("venue", "method", "code_path", "source_location"), errors,
                )
                if isinstance(record, dict):
                    if _text(record.get("method")):
                        recorded_methods.add(record["method"])
                    if record.get("venue") not in scope:
                        errors.append(f"local_code_library.records[{index}].venue is outside the declared scope")
                    if not _valid_year(record.get("year")):
                        errors.append(f"baseline_reference.local_code_library.records[{index}].year must be a valid year")
                    elif _number(lookback, positive=True, integer=True) and record["year"] < datetime.now().year - lookback:
                        errors.append(f"local_code_library.records[{index}].year is outside the declared year window")
                    code_path = resolve(library_root or root, record.get("code_path"))
                    if code_path is None or not code_path.exists():
                        errors.append(f"local_code_library.records[{index}].code_path does not exist")
        if isinstance(optimization, dict):
            selected = optimization.get("selected_methods")
            if isinstance(selected, list) and all(_text(item) for item in selected):
                if not set(selected).issubset(recorded_methods):
                    errors.append("every selected method needs a local_code_library record")
            years = optimization.get("publication_years")
            if isinstance(years, list) and _number(lookback, positive=True, integer=True):
                if any(_valid_year(year) and year < datetime.now().year - lookback for year in years):
                    errors.append("recent_optimization.publication_years are outside the declared year window")

    final_scheme = payload.get("final_experiment_scheme")
    _required_text_fields(
        final_scheme, "baseline_reference.final_experiment_scheme",
        ("method", "dataset", "split", "training", "evaluation", "ablation_plan"), errors,
    )
    if isinstance(final_scheme, dict):
        _required_text_list(final_scheme.get("metrics"),
                            "baseline_reference.final_experiment_scheme.metrics", errors)
        matrix_path = package_paths(root, card)["experiment_matrix"]
        if not file_hash(matrix_path) or final_scheme.get("experiment_matrix_sha256") != file_hash(matrix_path):
            errors.append("baseline_reference.final_experiment_scheme must bind the current experiment_matrix_sha256")
        if card.get("primary_metric") not in (final_scheme.get("metrics") or []):
            errors.append("baseline_reference.final_experiment_scheme.metrics must include the card primary_metric")

    selection = payload.get("candidate_selection")
    _required_text_fields(selection, "baseline_reference.candidate_selection", ("status", "basis"), errors)
    if isinstance(selection, dict):
        if selection.get("status") != "candidate_best_under_recorded_evidence":
            errors.append("baseline_reference.candidate_selection.status must be candidate_best_under_recorded_evidence")
        _required_text_list(selection.get("alternatives_considered"),
                           "baseline_reference.candidate_selection.alternatives_considered", errors)

    table = payload.get("comparison_table")
    if not isinstance(table, list) or not table:
        errors.append("baseline_reference.comparison_table must be a non-empty table")
        table = []
    seen_keys: set[str] = set()
    for index, row in enumerate(table):
        if not isinstance(row, dict):
            errors.append(f"baseline_reference.comparison_table row {index} must be an object")
            continue
        for field in ("dimension_key", "dimension", "reference_paper", "final_scheme", "decision_or_difference", "source_location"):
            if not _text(row.get(field)):
                errors.append(f"baseline_reference.comparison_table row {index} needs {field}")
        key = row.get("dimension_key")
        if _text(key):
            if key not in BASELINE_COMPARISON_KEYS:
                errors.append(f"baseline_reference.comparison_table row {index} has unsupported dimension_key: {key}")
            if key in seen_keys:
                errors.append(f"baseline_reference.comparison_table duplicates dimension_key: {key}")
            seen_keys.add(key)
        if row.get("dimension_key") == "evaluation_metrics" and not isinstance(row.get("comparable"), bool):
            errors.append("evaluation_metrics comparison needs comparable=true/false")
    missing_keys = sorted(BASELINE_COMPARISON_KEYS - seen_keys)
    if missing_keys:
        errors.append("baseline_reference.comparison_table missing dimensions: " + ", ".join(missing_keys))
    if _placeholder(payload):
        errors.append("baseline_reference contains a placeholder")
    return _result(errors, path=str(path) if path else None, reference=payload, comparison_table=table)


def validate_compute_budget(budget: dict[str, Any], rows: list[Any]) -> dict[str, Any]:
    """Count actual matrix executions and preserve the evidence for each estimate."""
    errors: list[str] = []
    for key in ("estimated_gpu_hours", "estimated_runs"):
        if not _number(budget.get(key), positive=True, integer=key == "estimated_runs"):
            errors.append(f"compute_budget.{key}: positive finite number required")
    _required_text_fields(budget, "compute_budget", ("assumptions", "schedule_basis"), errors)
    summary = budget.get("budget_summary")
    _required_text_fields(summary, "compute_budget.budget_summary", ("gpu_type", "recommended_rental"), errors)
    if isinstance(summary, dict):
        for key in ("total_experiments", "required_gpu_count", "wall_clock_hours",
                    "recommended_gpu_count", "recommended_hours"):
            if not _number(summary.get(key), positive=True,
                           integer=key not in {"wall_clock_hours", "recommended_hours"}):
                errors.append(f"compute_budget.budget_summary.{key}: positive finite number required")
        if summary.get("total_experiments") != budget.get("estimated_runs"):
            errors.append("compute_budget.budget_summary.total_experiments must match estimated_runs")

    expected = set()
    for row in rows:
        if isinstance(row, dict) and _text(row.get("id")) and isinstance(row.get("seeds"), list):
            expected.update((row["id"], seed) for seed in row["seeds"] if type(seed) is int)
    estimates = budget.get("run_estimates")
    if not isinstance(estimates, list) or not estimates:
        errors.append("compute_budget.run_estimates must list every matrix row and seed")
        estimates = []
    seen = set()
    gpu_hours = 0.0
    largest_run = 0
    for index, estimate in enumerate(estimates):
        label = f"compute_budget.run_estimates[{index}]"
        _required_text_fields(estimate, label, ("row_id", "estimate_source"), errors)
        if not isinstance(estimate, dict):
            continue
        row_id, seed = estimate.get("row_id"), estimate.get("seed")
        if not _text(row_id) or type(seed) is not int:
            errors.append(f"{label}: row_id and integer seed required")
        else:
            key = (row_id, seed)
            if key in seen:
                errors.append(f"{label}: duplicate row/seed estimate")
            seen.add(key)
        if not _number(estimate.get("gpu_count"), positive=True, integer=True) or not _number(estimate.get("hours"), positive=True):
            errors.append(f"{label}: positive gpu_count and hours required")
        else:
            gpu_hours += estimate["gpu_count"] * estimate["hours"]
            largest_run = max(largest_run, estimate["gpu_count"])
    if expected != seen:
        errors.append("compute_budget.run_estimates must match experiment_matrix rows and seeds exactly")
    if budget.get("estimated_runs") != len(expected):
        errors.append("compute_budget.estimated_runs must equal the matrix execution count (including seeds)")
    if _number(budget.get("estimated_gpu_hours"), positive=True) and not math.isclose(budget["estimated_gpu_hours"], gpu_hours, rel_tol=1e-6):
        errors.append("compute_budget.estimated_gpu_hours must equal the sum of per-run GPU-hours")
    if isinstance(summary, dict):
        for count_key, hours_key in (("required_gpu_count", "wall_clock_hours"),
                                     ("recommended_gpu_count", "recommended_hours")):
            count, hours = summary.get(count_key), summary.get(hours_key)
            if _number(count, positive=True, integer=True) and _number(hours, positive=True):
                if count < largest_run or count * hours + 1e-6 < gpu_hours:
                    errors.append(f"compute_budget.budget_summary.{count_key}/{hours_key} cannot cover the declared runs")
    if _placeholder(budget):
        errors.append("compute_budget contains a placeholder")
    display = None
    if not errors:
        display = (f"共有 {summary['total_experiments']:g} 个实验需要跑；"
                   f"需要 {summary['required_gpu_count']:g} 张 {summary['gpu_type']} 跑 {summary['wall_clock_hours']:g} 小时；"
                   f"推荐租 {summary['recommended_gpu_count']:g} 张 {summary['gpu_type']}，运行 {summary['recommended_hours']:g} 小时。")
    return _result(errors, budget=budget, summary_text=display)


def validate_innovation_package(root: str | Path, card: dict[str, Any]) -> dict[str, Any]:
    root = Path(root).resolve()
    paths = package_paths(root, card)
    errors: list[str] = []
    hashes: dict[str, str] = {}
    for field, path in paths.items():
        if path is None or not path.is_file() or not path.stat().st_size:
            errors.append(f"research package file is missing or empty: {field} ({path})")
        else:
            hashes[field] = file_hash(path)
    for field in ("literature_synthesis", "innovation_proposal", "architecture_spec"):
        path = paths[field]
        if path and path.is_file():
            try:
                content = path.read_text(encoding="utf-8").strip()
                if not content or _placeholder(content):
                    errors.append(f"{field}: actual content is required")
            except (OSError, UnicodeDecodeError) as exc:
                errors.append(f"{field}: unreadable text ({exc})")
    baseline = validate_baseline_reference(root, card)
    errors.extend(baseline["errors"])
    # Verify a supported image signature, not its scientific correctness.
    draft = paths["architecture_draft"]
    if draft and draft.is_file():
        head = draft.read_bytes()[:12]
        if not (head.startswith(b"\x89PNG\r\n\x1a\n") or head.startswith(b"\xff\xd8\xff")
                or (head.startswith(b"RIFF") and head[8:12] == b"WEBP")):
            errors.append("architecture_draft must be a PNG, JPEG, or WebP raster for human review")
    budget = _json(paths["compute_budget"], "compute_budget", errors)
    matrix = _json(paths["experiment_matrix"], "experiment_matrix", errors)
    rows = matrix.get("rows") if matrix is not None else None
    if not isinstance(rows, list) or not rows:
        errors.append("experiment_matrix.rows must be a non-empty list")
        rows = []
    ids: set[str] = set()
    categories: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"experiment_matrix row {index} must be an object")
            continue
        for key in ("id", "category", "strategy_role", "hypothesis", "control", "change", "metric", "pass_rule", "experiment_id", "stage"):
            if not _text(row.get(key)):
                errors.append(f"experiment_matrix row {index} needs {key}")
        category = row.get("category")
        if category not in {"verification", "ablation"}:
            errors.append(f"experiment_matrix row {index}: category must be verification or ablation")
        else:
            categories.add(category)
        role = row.get("strategy_role")
        if role not in MATRIX_STRATEGY_ROLES:
            errors.append(f"experiment_matrix row {index}: strategy_role must be one of {sorted(MATRIX_STRATEGY_ROLES)}")
        elif role == "reference_reproduction" and row.get("stage") != "baseline":
            errors.append(f"experiment_matrix row {index}: reference_reproduction must run at baseline stage")
        elif role == "recent_optimization" and row.get("stage") == "baseline":
            errors.append(f"experiment_matrix row {index}: recent_optimization must follow baseline reproduction")
        if category == "ablation" and not _text(row.get("component")):
            errors.append(f"experiment_matrix ablation row {index} needs component")
        row_id = row.get("id")
        if isinstance(row_id, str):
            if row_id in ids:
                errors.append(f"duplicate experiment_matrix id: {row_id}")
            ids.add(row_id)
        if row.get("stage") not in {"baseline", "pilot", "full", "multi_seed"}:
            errors.append(f"experiment_matrix row {index}: invalid execution stage")
        seeds = row.get("seeds")
        if not isinstance(seeds, list) or not seeds or not all(type(seed) is int for seed in seeds) or len(set(seeds)) != len(seeds):
            errors.append(f"experiment_matrix row {index}: unique integer seeds are required")
        exp_id = row.get("experiment_id")
        if _text(exp_id) and (Path(exp_id).name != exp_id or exp_id in {".", ".."}):
            errors.append(f"experiment_matrix row {index}: invalid experiment ID")
        elif _text(exp_id):
            target = root / "experiments/cards" / f"{exp_id}.json"
            if not target.is_file():
                errors.append(f"experiment_matrix row {index}: card is not registered ({exp_id})")
            else:
                declared = _json(target, f"matrix card {exp_id}", errors)
                if declared and row.get("stage") not in declared.get("stages", {}):
                    errors.append(f"matrix stage is absent from card {exp_id}")
                if declared and row.get("metric") != declared.get("primary_metric"):
                    errors.append(f"matrix metric differs from card {exp_id}")
    for category in ("verification", "ablation"):
        if category not in categories:
            errors.append(f"experiment_matrix needs at least one {category} row")
    roles = {row.get("strategy_role") for row in rows if isinstance(row, dict)}
    for role in ("reference_reproduction", "recent_optimization"):
        if role not in roles:
            errors.append(f"experiment_matrix needs a {role} row")
    if matrix is not None and _placeholder(matrix):
        errors.append("experiment_matrix contains a placeholder")
    budget_result = validate_compute_budget(budget, rows) if budget is not None else None
    if budget_result is not None:
        errors.extend(budget_result["errors"])
    return _result(
        errors,
        paths={key: str(path) if path else None for key, path in paths.items()},
        hashes=hashes,
        matrix_rows=rows,
        baseline_reference=baseline,
        compute_budget=budget_result,
    )


def _approval(payload: dict[str, Any], label: str, errors: list[str], *, edited: bool = False) -> None:
    if payload.get("decision") != "approve" or payload.get("human_reviewed") is not True:
        errors.append(f"{label}: explicit human approve and human_reviewed=true are required")
    for field in ("reviewer", "reviewed_at", "source_thread_id", "user_quote"):
        if not _text(payload.get(field)):
            errors.append(f"{label}: {field} is required")
    if payload.get("actor") != "user":
        errors.append(f"{label}: actor must be user")
    if _text(payload.get("reviewed_at")):
        try:
            timestamp = datetime.fromisoformat(payload["reviewed_at"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                errors.append(f"{label}: reviewed_at needs a timezone")
        except ValueError:
            errors.append(f"{label}: reviewed_at must be ISO-8601")
    if edited and (payload.get("human_edited") is not True or not _text(payload.get("edit_summary"))):
        errors.append("innovation: human_edited=true and edit_summary are required")
    if _placeholder(payload):
        errors.append(f"{label}: review contains a placeholder")


def validate_innovation_review(root: str | Path, card: dict[str, Any]) -> dict[str, Any]:
    package = validate_innovation_package(root, card)
    errors = list(package["errors"])
    payload = _json(review_paths(root, card)["innovation"], "innovation review", errors)
    if payload is not None:
        _approval(payload, "innovation", errors, edited=True)
        for field in ("baseline_eligibility_checked", "reference_reproduction_checked",
                      "recent_optimization_checked", "protocol_comparison_checked"):
            if payload.get(field) is not True:
                errors.append(f"innovation: {field}=true is required in the first human review")
        reference = package["baseline_reference"].get("reference") or {}
        if (reference.get("paper") or {}).get("venue_type") == "conference" and payload.get("conference_quality_confirmed") is not True:
            errors.append("innovation: conference_quality_confirmed=true is required for a conference baseline")
        recorded = payload.get("package_sha256", {})
        if not isinstance(recorded, dict):
            recorded = {}
        for field, digest in package["hashes"].items():
            if recorded.get(field) != digest:
                errors.append(f"innovation review hash does not match current {field}")
        if payload.get("card_sha256") != file_hash(Path(root) / "experiments/cards" / f"{card['experiment_id']}.json"):
            errors.append("innovation review does not match current experiment card")
    return _result(errors, package=package, review=payload)


def validate_compute_allocation(root: str | Path, card: dict[str, Any]) -> dict[str, Any]:
    innovation = validate_innovation_review(root, card)
    errors = list(innovation["errors"])
    payload = _json(review_paths(root, card)["compute"], "compute allocation", errors)
    if payload is not None:
        _approval(payload, "compute", errors)
        if not _text(payload.get("allocation_basis")) or not _text(payload.get("gpu_type")):
            errors.append("compute: allocation_basis and gpu_type are required")
        if payload.get("innovation_review_sha256") != file_hash(review_paths(root, card)["innovation"]):
            errors.append("compute allocation is not bound to the current innovation review")
        for key in ("gpu_count", "vram_gb", "max_gpu_hours", "max_runtime_seconds", "max_runs", "max_vram_gb", "max_cost_usd"):
            if not _number(payload.get(key), positive=key != "max_cost_usd", integer=key in {"gpu_count", "max_runs"}):
                errors.append(f"compute.{key}: finite numeric limit required")
        if _number(payload.get("max_vram_gb")) and _number(payload.get("vram_gb")) and payload["max_vram_gb"] > payload["vram_gb"]:
            errors.append("compute: max_vram_gb exceeds the allocated GPU memory")
    return _result(errors, innovation=innovation, allocation=payload)


def _ledger(root: Path) -> Ledger:
    return Ledger(root / read_json(root / "config/project.json")["ledger_path"])


def matrix_progress(root: str | Path, card: dict[str, Any]) -> dict[str, Any]:
    root = Path(root).resolve()
    errors: list[str] = []
    payload = _json(package_paths(root, card)["experiment_matrix"], "experiment_matrix", errors)
    rows = payload.get("rows", []) if payload else []
    ledger = _ledger(root)
    missing = []
    if not isinstance(rows, list) or not rows:
        errors.append("no executable experiment matrix is registered")
        rows = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("seeds"), list):
            errors.append("invalid experiment matrix row")
            continue
        runs = ledger.runs(row.get("experiment_id", ""))
        completed = {run.get("seed") for run in runs if run.get("stage") == row.get("stage")
                     and run.get("status") in {"keep", "discard", "candidate"} and _number(run.get("metric"))}
        # A completed negative verification/ablation is valid evidence too.
        for seed in row["seeds"]:
            if seed not in completed:
                missing.append({"row_id": row.get("id"), "category": row.get("category"),
                                "experiment_id": row.get("experiment_id"), "stage": row.get("stage"), "seed": seed})
    return _result(errors + [f"matrix run is incomplete: {item}" for item in missing], missing_runs=missing)


def evidence_snapshot(root: str | Path, card: dict[str, Any], runs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    ledger = _ledger(root)
    own_runs = ledger.runs(card["experiment_id"]) if runs is None else runs
    payload = _json(package_paths(root, card)["experiment_matrix"], "experiment_matrix", []) or {}
    rows = payload.get("rows", [])
    ids = {card["experiment_id"]}
    if card.get("reference_experiment_id"):
        ids.add(card["reference_experiment_id"])
    if isinstance(rows, list):
        ids.update(row["experiment_id"] for row in rows if isinstance(row, dict) and _text(row.get("experiment_id")))
    evidence_runs = list(own_runs)
    for exp_id in sorted(ids - {card["experiment_id"]}):
        evidence_runs.extend(ledger.runs(exp_id))
    cards = {exp_id: file_hash(root / "experiments/cards" / f"{exp_id}.json") for exp_id in sorted(ids)}
    records = [{
        "run_id": run["run_id"], "experiment_id": run["experiment_id"], "stage": run["stage"],
        "seed": run.get("seed"), "status": run["status"], "metric": run.get("metric"),
        "exit_code": run.get("exit_code"), "receipt_sha256": file_hash(resolve(root, run.get("receipt_path"))),
    } for run in sorted(evidence_runs, key=lambda item: item["run_id"])]
    return {"cards": cards, "runs": records,
            "matrix_sha256": file_hash(package_paths(root, card)["experiment_matrix"]),
            "compute_allocation_sha256": file_hash(review_paths(root, card)["compute"])}


def validate_conclusion_review(root: str | Path, card: dict[str, Any], runs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    allocation = validate_compute_allocation(root, card)
    errors = list(allocation["errors"])
    progress = matrix_progress(root, card)
    errors.extend(progress["errors"])
    payload = _json(review_paths(root, card)["conclusion"], "conclusion review", errors)
    snapshot = evidence_snapshot(root, card, runs)
    if payload is not None:
        _approval(payload, "conclusion", errors)
        if payload.get("evidence_checked") is not True or not _text(payload.get("claim_scope")):
            errors.append("conclusion: evidence_checked=true and claim_scope are required")
        if payload.get("evidence_sha256") != value_hash(snapshot):
            errors.append("conclusion review is stale or does not match the current evidence snapshot")
        known_runs = {item["run_id"]: item for item in snapshot["runs"]}
        conclusions = payload.get("approved_conclusions")
        if not isinstance(conclusions, list) or not conclusions:
            errors.append("conclusion: approved_conclusions must be a non-empty list")
            conclusions = []
        ids: set[str] = set()
        for index, conclusion in enumerate(conclusions):
            if not isinstance(conclusion, dict):
                errors.append(f"approved conclusion {index} must be an object")
                continue
            for key in ("id", "zh", "en"):
                if not _text(conclusion.get(key)):
                    errors.append(f"approved conclusion {index} needs {key}")
            if _text(conclusion.get("id")):
                if conclusion["id"] in ids:
                    errors.append(f"duplicate conclusion ID: {conclusion['id']}")
                ids.add(conclusion["id"])
            refs = conclusion.get("evidence_refs")
            if not isinstance(refs, list) or not refs or not all(_text(ref) for ref in refs):
                errors.append(f"approved conclusion {index}: evidence_refs must be a non-empty list of run IDs")
                continue
            for ref in refs:
                run = known_runs.get(ref)
                if not run or run["status"] not in {"keep", "discard", "candidate"} or run.get("exit_code") != 0 or not _number(run.get("metric")):
                    errors.append(f"approved conclusion {index}: missing or failed evidence run {ref}")
                    continue
                if not run.get("receipt_sha256"):
                    errors.append(f"approved conclusion {index}: missing receipt for {ref}")
    return _result(errors, allocation=allocation, matrix=progress, review=payload,
                   evidence_snapshot=snapshot, evidence_sha256=value_hash(snapshot))


def gate_snapshot(root: str | Path, card: dict[str, Any], runs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if not is_human_gated(card, root):
        return {"workflow_mode": "historical", "enabled": False}
    conclusion = validate_conclusion_review(root, card, runs)
    allocation = conclusion["allocation"]
    innovation = allocation["innovation"]
    return {"workflow_mode": HUMAN_GATED_WORKFLOW, "enabled": True,
            "innovation_package": innovation["package"], "innovation_review": innovation,
            "baseline_reference": innovation["package"].get("baseline_reference"),
            "compute_allocation": allocation, "experiment_matrix": conclusion["matrix"],
            "conclusion_review": conclusion}
