from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(code_root: str | Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(code_root), *args], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git command failed: {args}")
    return result.stdout.strip()


def snapshot(code_root: str | Path, protected_paths: list[str], allowed_paths: list[str]) -> dict[str, Any]:
    root = Path(code_root)
    status_porcelain = git(root, "status", "--porcelain")
    receipt: dict[str, Any] = {
        "code_root": str(root),
        "head": git(root, "rev-parse", "HEAD"),
        "branch": git(root, "branch", "--show-current"),
        "status_porcelain": status_porcelain,
        "status_paths": [line[3:] for line in status_porcelain.splitlines() if len(line) >= 4],
        "allowed_change_paths": allowed_paths,
        "protected_hashes": {},
    }
    for rel in protected_paths:
        path = root / rel
        if path.is_file():
            receipt["protected_hashes"][rel] = sha256_file(path)
    return receipt


def changed_paths(code_root: str | Path, base_head: str | None = None) -> list[str]:
    committed = git(code_root, "diff", "--name-only", f"{base_head}..HEAD") if base_head else ""
    text = git(code_root, "diff", "--name-only")
    staged = git(code_root, "diff", "--cached", "--name-only")
    return sorted({line.strip() for line in (committed + "\n" + text + "\n" + staged).splitlines() if line.strip()})


def verify_snapshot(before: dict[str, Any], after: dict[str, Any], code_root: str | Path) -> dict[str, Any]:
    changed = changed_paths(code_root, str(before.get("head") or ""))
    protected_changed = [
        path for path, digest in before.get("protected_hashes", {}).items()
        if after.get("protected_hashes", {}).get(path) != digest
    ]
    allowed = set(before.get("allowed_change_paths", []))
    scope_violations = [path for path in changed if path not in allowed]
    return {
        "before_head": before.get("head"),
        "after_head": after.get("head"),
        "changed_paths": changed,
        "protected_changed": protected_changed,
        "scope_violations": scope_violations,
        "passed": not protected_changed and not scope_violations,
    }


def write_receipt(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
