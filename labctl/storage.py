"""Local research storage, immutable receipts and review-bound execution.

This module does not infer human approval, train a model, provision a GPU,
delete old work, or upload research assets. All copies remain local.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import math
import re
import shutil
import subprocess
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .integrity import git, sha256_file
from .io import read_json, write_json

SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TASK_ID = re.compile(r"^AR-[0-9]{8}-[0-9]{3}-[a-z0-9]+(?:-[a-z0-9]+)*$")
TASK_DIRS = (
    "reference/papers", "reference/notes", "reference/code", "reference/metadata",
    "ideas/candidates", "ideas/approved", "ideas/reviews", "plans", "approvals",
    "code/baseline", "code/variants", "code/snapshots", "experiments/cards",
    "runs", "result/evaluations", "result/checkpoints", "result/training_records",
    "result/freezes", "paper/zh", "paper/en", "paper/bibliography", "figures/drafts",
    "figures/approved", "figures/editable", "figures/exports", "ppt/briefs",
    "ppt/source", "ppt/exports", "reports", "archive", "manifests",
)
ROOT_DIRS = ("inbox", "reference/papers", "reference/notes", "reference/code",
             "reference/metadata", "tasks", "reports", "indexes")


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def valid_slug(value: str) -> str:
    if not SLUG.fullmatch(value) or len(value) > 64:
        raise ValueError("slug must use lowercase letters, numbers and single hyphens (max 64)")
    return value


def inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("path escapes the managed directory")
    return path


def workspace_root(lab: Path, override: str | Path | None = None) -> Path:
    return Path(override or read_json(lab / "config/workspace.json")["root"]).expanduser().resolve()


@contextmanager
def locked(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".storage.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def task_dir(root: Path, task_id: str) -> Path:
    if not TASK_ID.fullmatch(task_id):
        raise ValueError("invalid task ID")
    path = inside(root, f"tasks/{task_id}")
    if not (path / "task.json").is_file():
        raise FileNotFoundError(f"task is not registered: {task_id}")
    return path


def tasks(root: Path) -> list[dict[str, Any]]:
    return [read_json(path) for path in sorted((root / "tasks").glob("*/task.json"))]


def index(root: Path) -> None:
    records = tasks(root)
    write_json(root / "indexes/tasks.json", {"updated_at": now(), "tasks": records})
    lines = ["# forautoresearch 总索引", "", "所有条目均为本地文件；目录存在不代表课题或训练已获批准。", "",
             "| 编号 | 课题 | 状态 | 路径 |", "|---|---|---|---|"]
    for record in records:
        name = record["title"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {record['task_id']} | {name} | {record['status']} | [进入课题](tasks/{record['task_id']}/README.md) |")
    (root / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def init_workspace(root: Path, lab: Path) -> Path:
    with locked(root):
        for relative in ROOT_DIRS:
            inside(root, relative).mkdir(parents=True, exist_ok=True)
        if not (root / "workspace.json").exists():
            write_json(root / "workspace.json", {"schema_version": 1, "created_at": now(),
                       "root": str(root), "lab_root": str(lab.resolve()), "timezone": "Asia/Shanghai"})
        for name in ("README.md", "NAMING_RULES.md", "WORKFLOW.md", "AGENTS.md"):
            source = lab / "templates/storage" / name
            target = root / name
            if not target.exists():
                shutil.copyfile(source, target)
        index(root)
    return root


def new_task(root: Path, title: str, slug: str, status: str = "proposed") -> Path:
    valid_slug(slug)
    if status not in {"proposed", "historical"}:
        raise ValueError("new work must start proposed; legacy imports may be historical")
    with locked(root):
        date = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d")
        existing = [int(item["task_id"].split("-")[2]) for item in tasks(root)
                    if item["task_id"].startswith(f"AR-{date}-")]
        serial = max(existing, default=0) + 1
        if serial > 999:
            raise ValueError("daily task ID capacity reached")
        task_id = f"AR-{date}-{serial:03d}-{slug}"
        target = root / "tasks" / task_id
        target.mkdir(parents=True, exist_ok=False)
        for relative in TASK_DIRS:
            (target / relative).mkdir(parents=True)
        write_json(target / "task.json", {"schema_version": 1, "task_id": task_id,
                   "title": title, "slug": slug, "status": status, "created_at": now(),
                   "approval": None, "experiment_ids": [], "owner_thread": None,
                   "deliverables": {"paper_zh": "pending", "paper_en": "pending",
                                    "architecture": "pending", "pptx": "pending"}})
        (target / "README.md").write_text(
            f"# {title}\n\n编号：`{task_id}`；初始状态：`{status}`。以 task.json 为当前状态。\n\n"
            "- reference/：文献原件、阅读笔记、来源元数据和参考代码。\n"
            "- ideas/ 与 plans/：候选创新、审核记录、方向提案、算力预算。\n"
            "- code/：独立基线与变体仓库，以及对应不可覆盖快照。\n"
            "- experiments/、runs/、result/：实验卡、原始日志、指标、权重和冻结证据。\n"
            "- paper/zh 与 paper/en：中文版、英文版可编辑初稿及导出件。\n"
            "- figures/ 与 ppt/：草图、批准稿、可编辑源文件和导出件。\n"
            "- approvals/、manifests/、archive/：人工批准、哈希清单、历史归档。\n\n"
            "先提交 plans/innovation_proposal.md 与 plans/compute_budget.json，等待用户明确批准。\n",
            encoding="utf-8")
        for name in ("references", "code", "experiments", "assets"):
            write_json(target / f"manifests/{name}.json", {"records": []})
        index(root)
    return target


def add_reference(root: Path, metadata: dict[str, Any], task_id: str | None = None,
                  file: str | Path | None = None) -> dict[str, Any]:
    required = {"key", "title", "year", "url", "kind", "reading_level"}
    if required - metadata.keys():
        raise ValueError(f"reference missing fields: {sorted(required - metadata.keys())}")
    key = valid_slug(str(metadata["key"]))
    year = int(metadata["year"])
    if not 1900 <= year <= 2100 or not str(metadata["url"]).startswith(("https://", "http://")):
        raise ValueError("reference needs a real year and source URL")
    if metadata["kind"] not in {"paper", "repository", "documentation", "dataset"}:
        raise ValueError("unsupported reference kind")
    if metadata["reading_level"] not in {"metadata", "abstract", "full_text", "code_inspected"}:
        raise ValueError("declare the actual reading depth")
    with locked(root):
        target = task_dir(root, task_id) if task_id else root
        ref_id = f"REF-{year}-{key}"
        meta_path = target / f"reference/metadata/{ref_id}.json"
        if meta_path.exists():
            raise FileExistsError(f"reference ID already exists: {ref_id}")
        record = {**metadata, "reference_id": ref_id, "registered_at": now(),
                  "file": None, "file_sha256": None, "metadata_file": str(meta_path.relative_to(target))}
        if file:
            source = Path(file).resolve(strict=True)
            if not source.is_file() or source.suffix.lower() not in {".pdf", ".md", ".txt", ".bib", ".html"}:
                raise ValueError("reference file must be PDF, text, Markdown, BibTeX or HTML")
            category = "papers" if source.suffix.lower() == ".pdf" else "notes"
            dest = target / f"reference/{category}/{ref_id}{source.suffix.lower()}"
            if dest.exists():
                raise FileExistsError(dest)
            shutil.copyfile(source, dest)
            record.update(file=str(dest.relative_to(target)), file_sha256=sha256_file(dest))
        write_json(meta_path, record)
        registry = target / ("manifests/references.json" if task_id else "indexes/references.json")
        records = read_json(registry)["records"] if registry.exists() else []
        records.append(record)
        write_json(registry, {"records": records})
        index(root)
    return record


def _safe_git_tree(repo: Path, commit: str) -> list[str]:
    listing = subprocess.run(["git", "-C", str(repo), "ls-tree", "-r", "-z", commit],
                             capture_output=True, check=True).stdout
    files = []
    for raw in listing.split(b"\0"):
        if not raw:
            continue
        properties, raw_name = raw.split(b"\t", 1)
        mode = properties.split()[0]
        name = raw_name.decode("utf-8")
        parts = Path(name).parts
        if mode != b"100644" and mode != b"100755":
            raise ValueError("code snapshot does not support symlinks or submodules")
        if Path(name).is_absolute() or ".." in parts:
            raise ValueError("unsafe Git tree path")
        if any(part.lower() in {".env", "credentials", "secrets", ".venv", "dataset", "datasets", "weights"} for part in parts):
            raise ValueError(f"material data or secrets require a separate manifest: {name}")
        if Path(name).suffix.lower() in {".pt", ".pth", ".ckpt", ".safetensors", ".parquet"}:
            raise ValueError(f"weight/data files must not be included in a code snapshot: {name}")
        files.append(name)
    return files


def add_code(root: Path, task_id: str, repo: str | Path, ref: str,
             role: str, slug: str) -> dict[str, Any]:
    if role not in {"baseline", "variant", "reference"}:
        raise ValueError("code role must be baseline, variant or reference")
    valid_slug(slug)
    repo = Path(repo).resolve(strict=True)
    # A dirty HEAD must never be silently represented as a frozen working copy.
    if ref == "HEAD" and git(repo, "status", "--porcelain"):
        raise ValueError("commit changes before capturing HEAD")
    commit = git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")
    files = _safe_git_tree(repo, commit)
    with locked(root):
        target = task_dir(root, task_id)
        code_id = f"{role}-{slug}-{commit[:12]}"
        category = {"baseline": "code/baseline", "variant": "code/variants", "reference": "reference/code"}[role]
        checkout = target / category / code_id
        archive = target / f"code/snapshots/{code_id}.tar.gz"
        if checkout.exists() or archive.exists():
            raise FileExistsError(f"code record already exists: {code_id}")
        subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", "--no-checkout", str(repo), str(checkout)],
                       check=True, capture_output=True, text=True)
        branch = f"autoresearch/{task_id.lower()}-{role}-{slug}"
        subprocess.run(["git", "-C", str(checkout), "checkout", "--quiet", "-b", branch, commit],
                       check=True, capture_output=True, text=True)
        subprocess.run(["git", "-C", str(repo), "archive", "--format=tar.gz", f"--output={archive}", commit],
                       check=True, capture_output=True, text=True)
        record = {"code_id": code_id, "role": role, "slug": slug, "source_repo": str(repo),
                  "source_ref": ref, "commit": commit, "branch": branch, "created_at": now(),
                  "checkout": str(checkout.relative_to(target)), "snapshot": str(archive.relative_to(target)),
                  "snapshot_sha256": sha256_file(archive), "files": files,
                  "file_hashes": {name: sha256_file(checkout / name) for name in files},
                  "runtime": None}
        # Reuse the already prepared runtime without copying its packages.
        runtime = repo / ".venv"
        if runtime.is_dir():
            (checkout / ".venv").symlink_to(runtime.resolve(), target_is_directory=True)
            record["runtime"] = {"path": str(runtime.resolve()), "mode": "shared_read_only_environment"}
        registry = target / "manifests/code.json"
        records = read_json(registry)["records"]
        records.append(record)
        write_json(registry, {"records": records})
        index(root)
    return record


def bind_card(root: Path, lab: Path, task_id: str, card_file: str | Path, code_id: str) -> Path:
    from .card import load_card
    card = load_card(card_file)
    experiment_id = str(card["experiment_id"])
    if not SLUG.fullmatch(experiment_id) or not experiment_id.startswith(task_id.lower() + "-"):
        raise ValueError("new experiment IDs must begin with the lowercase task ID")
    with locked(root):
        target = task_dir(root, task_id)
        task = read_json(target / "task.json")
        if task["status"] != "proposed":
            raise ValueError("bind cards before confirmation; revisions require a new proposal")
        codes = read_json(target / "manifests/code.json")["records"]
        code = next((item for item in codes if item["code_id"] == code_id), None)
        if not code or code["role"] == "reference":
            raise ValueError("select a registered baseline or variant code ID")
        primary = lab / f"experiments/cards/{experiment_id}.json"
        local = target / f"experiments/cards/{experiment_id}.json"
        if primary.exists() or local.exists():
            raise FileExistsError("card already registered; create a versioned experiment ID")
        card.update(task_id=task_id, workspace_root=str(root), code_id=code_id,
                    code_root=str(inside(target, code["checkout"])))
        # Every newly managed experiment uses the human-gated research-to-paper
        # contract. Absolute paths keep the card valid when the runner executes
        # from the lab repository while the evidence lives in forautoresearch.
        card.update(
            workflow_mode="human_gated_research_to_paper",
            research_package={
                "literature_synthesis": str(target / "plans/literature_synthesis.md"),
                "innovation_proposal": str(target / "plans/innovation_proposal.md"),
                "compute_budget": str(target / "plans/compute_budget.json"),
                "experiment_matrix": str(target / "plans/experiment_matrix.json"),
                "architecture_spec": str(target / "figures/architecture_spec.md"),
                "architecture_draft": str(target / "figures/drafts/architecture_draft.png"),
            },
            human_reviews={
                "innovation": str(target / "approvals/innovation_review.json"),
                "compute": str(target / "approvals/compute_allocation.json"),
                "conclusion": str(target / "approvals/conclusion_review.json"),
            },
        )
        card["human_approval"] = {"required": True, "status": "pending"}
        write_json(primary, card)
        write_json(local, card)
        records = read_json(target / "manifests/experiments.json")["records"]
        records.append({"experiment_id": experiment_id, "card": str(local.relative_to(target)),
                        "lab_card": str(primary), "card_sha256": sha256_file(local), "code_id": code_id})
        write_json(target / "manifests/experiments.json", {"records": records})
        task["experiment_ids"].append(experiment_id)
        write_json(target / "task.json", task)
        index(root)
    return local


def confirm_task(root: Path, task_id: str, evidence_file: str | Path) -> Path:
    """Record a user's actual approval; an agent must not fabricate this input."""
    approval = read_json(evidence_file)
    required = {"task_id", "decision", "actor", "source_thread_id", "user_quote",
                "proposal_sha256", "budget_sha256", "approved_experiments"}
    if required - approval.keys() or approval.get("decision") != "approve" or approval.get("actor") != "user":
        raise ValueError("confirmation needs a direct user approval with proposal/budget hashes")
    if approval["task_id"] != task_id or not str(approval["user_quote"]).strip() or not approval["source_thread_id"]:
        raise ValueError("approval must identify this task and the actual user message")
    with locked(root):
        target = task_dir(root, task_id)
        task = read_json(target / "task.json")
        if task["status"] != "proposed":
            raise ValueError("only proposed tasks can be confirmed")
        proposal = target / "plans/innovation_proposal.md"
        budget_path = target / "plans/compute_budget.json"
        for path, key in ((proposal, "proposal_sha256"), (budget_path, "budget_sha256")):
            if not path.is_file() or sha256_file(path) != approval[key]:
                raise ValueError("approval does not match the reviewable proposal and budget")
        budget = read_json(budget_path)
        for key in ("max_runs", "max_gpu_hours", "max_cost_usd"):
            if key not in budget or not math.isfinite(float(budget[key])) or float(budget[key]) < 0:
                raise ValueError(f"compute budget needs a finite nonnegative {key}")
        if float(budget["max_runs"]) <= 0 or float(budget["max_gpu_hours"]) <= 0:
            raise ValueError("execution needs a positive run and GPU time budget")
        if not read_json(target / "manifests/references.json")["records"]:
            raise ValueError("confirmed work requires registered references")
        cards = read_json(target / "manifests/experiments.json")["records"]
        approved = approval["approved_experiments"]
        if not isinstance(approved, dict) or not approved or set(approved) - {item["experiment_id"] for item in cards}:
            raise ValueError("approval must bind registered experiment IDs and exact card hashes")
        max_runs = max_cost = max_seconds = 0.0
        for item in cards:
            if item["experiment_id"] not in approved:
                continue
            card = read_json(target / item["card"])
            if approved[item["experiment_id"]] != sha256_file(target / item["card"]) or sha256_file(Path(item["lab_card"])) != approved[item["experiment_id"]]:
                raise ValueError("approval card hash mismatch")
            limits = card["constraints"]
            for key in ("max_runs", "max_runtime_seconds", "max_cost_usd"):
                if key not in limits or not math.isfinite(float(limits[key])) or float(limits[key]) < 0:
                    raise ValueError("approved cards need finite run, runtime and cost limits")
            max_runs += float(limits["max_runs"])
            max_cost += float(limits["max_cost_usd"])
            # The reviewed GPU-hour budget is the declared training budget.
            # Runtime timeout also covers compile/evaluation overhead and is
            # therefore tracked separately rather than charged as training.
            max_seconds += float(limits["max_runs"]) * float(
                limits.get("training_seconds_per_run", limits["max_runtime_seconds"])
            )
            if card.get("workflow_mode") == "human_gated_research_to_paper":
                from .research_gate import validate_compute_allocation
                lab_card = Path(item["lab_card"]).resolve()
                lab_root = lab_card.parents[2]
                gate = validate_compute_allocation(lab_root, card)
                if not gate["valid"]:
                    raise ValueError("human innovation and compute review is incomplete: " + "; ".join(gate["errors"]))
        if max_runs > float(budget["max_runs"]) or max_cost > float(budget["max_cost_usd"]) or max_seconds > float(budget["max_gpu_hours"]) * 3600:
            raise ValueError("card limits exceed the reviewed total task budget")
        report = audit(root, task_id)
        if report["errors"]:
            raise ValueError(f"repair storage audit before confirmation: {report['errors']}")
        approval_path = target / f"approvals/direction-budget-{digest(approval)[:12]}.json"
        write_json(approval_path, {**approval, "recorded_at": now()})
        task.update(status="confirmed", approval={"file": str(approval_path.relative_to(target)),
                                                  "sha256": sha256_file(approval_path)})
        write_json(target / "task.json", task)
        index(root)
    return approval_path


def execution_binding(lab: Path, card: dict[str, Any]) -> tuple[Path, list[str]]:
    """Legacy cards stay historical; managed cards additionally need review hashes."""
    project = read_json(lab / "config/project.json")
    if not card.get("task_id"):
        return Path(project["code_root"]).resolve(), []
    root = workspace_root(lab, card.get("workspace_root"))
    target = task_dir(root, card["task_id"])
    task = read_json(target / "task.json")
    errors = []
    code = next((item for item in read_json(target / "manifests/code.json")["records"]
                 if item["code_id"] == card.get("code_id")), None)
    if not code:
        return Path(project["code_root"]).resolve(), ["card code ID is not registered"]
    code_root = inside(target, code["checkout"])
    if card.get("code_root") != str(code_root):
        errors.append("card code root differs from the registered checkout")
    if task["status"] != "confirmed" or not task.get("approval"):
        errors.append("task direction and budget await explicit user approval")
        return code_root, errors
    approval_path = inside(target, task["approval"]["file"])
    if sha256_file(approval_path) != task["approval"]["sha256"]:
        errors.append("approval file changed")
    approval = read_json(approval_path)
    for path, key in ((target / "plans/innovation_proposal.md", "proposal_sha256"),
                      (target / "plans/compute_budget.json", "budget_sha256")):
        if not path.is_file() or sha256_file(path) != approval[key]:
            errors.append("proposal or budget changed after approval")
    card_file = lab / f"experiments/cards/{card['experiment_id']}.json"
    approved_hash = approval["approved_experiments"].get(card["experiment_id"])
    if not approved_hash or sha256_file(card_file) != approved_hash:
        errors.append("experiment card is outside the reviewed approval")
    local_card = target / f"experiments/cards/{card['experiment_id']}.json"
    if not local_card.is_file() or sha256_file(local_card) != approved_hash:
        errors.append("task card no longer matches the reviewed card")
    if git(code_root, "rev-parse", "HEAD") != code["commit"]:
        errors.append("code commit differs from the registered reviewed version")
    return code_root, errors


def capture_asset(root: Path, task_id: str, source: str | Path, category: str, name: str) -> dict[str, Any]:
    allowed = {"idea": "ideas/candidates", "report": "reports", "paper-zh": "paper/zh",
               "paper-en": "paper/en", "figure-draft": "figures/drafts", "figure-approved": "figures/approved",
               "figure-editable": "figures/editable", "pptx": "ppt/source", "legacy": "archive/legacy"}
    if category not in allowed or Path(name).name != name or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]+", name):
        raise ValueError("choose a managed category and an ASCII filename without directory separators")
    source = Path(source).resolve(strict=True)
    if not source.is_file():
        raise ValueError("asset capture only accepts individual files")
    with locked(root):
        target = task_dir(root, task_id)
        dest = inside(target, f"{allowed[category]}/{name}")
        if dest.exists():
            raise FileExistsError("versioned assets are never overwritten")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        record = {"category": category, "file": str(dest.relative_to(target)), "sha256": sha256_file(dest),
                  "source": str(source), "captured_at": now()}
        registry = target / "manifests/assets.json"
        records = read_json(registry)["records"]
        records.append(record)
        write_json(registry, {"records": records})
    return record


def audit(root: Path, task_id: str | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    records = [read_json(task_dir(root, task_id) / "task.json")] if task_id else tasks(root)
    checked = 0
    targets = [(root, "indexes/references.json", "reference")]
    for task in records:
        target = task_dir(root, task["task_id"])
        for relative in TASK_DIRS:
            if not inside(target, relative).is_dir():
                errors.append(f"{task['task_id']}: missing directory {relative}")
        targets += [(target, "manifests/references.json", "reference"),
                    (target, "manifests/assets.json", "asset"),
                    (target, "manifests/code.json", "code")]
        for item in read_json(target / "manifests/experiments.json")["records"]:
            local = inside(target, item["card"])
            for path in (local, Path(item["lab_card"])):
                checked += 1
                if not path.is_file() or sha256_file(path) != item["card_sha256"]:
                    errors.append(f"card missing or changed: {path}")
        if task["status"] == "proposed":
            warnings.append(f"{task['task_id']}: pending direction and compute review")
    for target, registry, kind in targets:
        if not (target / registry).exists():
            continue
        for item in read_json(target / registry)["records"]:
            if kind == "code":
                files = [(item["snapshot"], item["snapshot_sha256"])]
                checkout = inside(target, item["checkout"])
                if not checkout.is_dir():
                    errors.append(f"code checkout missing: {checkout}")
                else:
                    if git(checkout, "rev-parse", "HEAD") != item["commit"]:
                        warnings.append(f"code checkout advanced; register a new version: {checkout}")
                    if git(checkout, "status", "--porcelain"):
                        warnings.append(f"uncommitted code edits: {checkout}")
                    for name, expected in item.get("file_hashes", {}).items():
                        path = inside(checkout, name)
                        checked += 1
                        if not path.is_file() or sha256_file(path) != expected:
                            errors.append(f"code file missing or changed: {path}")
            elif kind == "reference":
                metadata_file = inside(target, item["metadata_file"])
                if not metadata_file.is_file() or read_json(metadata_file) != item:
                    errors.append(f"reference metadata missing or changed: {metadata_file}")
                files = [(item["file"], item["file_sha256"])] if item.get("file") else []
                if not item.get("file"):
                    warnings.append(f"{item['reference_id']}: source URL registered; no local full text")
            else:
                files = [(item["file"], item["sha256"])]
            for relative, expected in files:
                path = inside(target, relative)
                checked += 1
                if not path.is_file() or sha256_file(path) != expected:
                    errors.append(f"file missing or changed: {path}")
    return {"root": str(root), "audited_at": now(), "tasks": len(records),
            "checked_files": checked, "passed": not errors, "errors": errors, "warnings": warnings}


def sync_experiment(root: Path, lab: Path, experiment_id: str) -> Path | None:
    """Mirror each completed run into its task without rewriting prior evidence."""
    card = read_json(lab / f"experiments/cards/{experiment_id}.json")
    if not card.get("task_id"):
        return None
    from .ledger import Ledger
    ledger = Ledger(lab / read_json(lab / "config/project.json")["ledger_path"])
    with locked(root):
        target = task_dir(root, card["task_id"])
        for run in ledger.runs(experiment_id):
            source = Path(run["run_dir"])
            dest = target / "runs" / experiment_id / run["stage"] / run["run_id"]
            if dest.exists():
                continue
            dest.mkdir(parents=True)
            files = []
            for file in sorted(source.rglob("*")):
                if file.is_symlink():
                    raise ValueError("run archive must not contain symlinks")
                if file.is_file():
                    relative = file.relative_to(source)
                    out = dest / relative
                    out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(file, out)
                    files.append({"file": str(out.relative_to(target)), "sha256": sha256_file(out)})
            write_json(target / f"manifests/run-{run['run_id']}.json", {"run": run, "files": files})
        write_json(target / f"result/training_records/{experiment_id}.json",
                   {"runs": ledger.runs(experiment_id), "events": ledger.events(experiment_id), "synced_at": now()})
    return target
