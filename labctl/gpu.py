from __future__ import annotations

import csv
import io
import subprocess
from typing import Any


def snapshot() -> dict[str, Any]:
    """Return a best-effort GPU process snapshot without touching processes."""
    query = "pid,process_name,used_memory"
    result = subprocess.run(
        ["nvidia-smi", f"--query-compute-apps={query}", "--format=csv,noheader,nounits"],
        text=True, capture_output=True, check=False,
    )
    if result.returncode != 0:
        return {"available": False, "error": result.stderr.strip() or "nvidia-smi unavailable", "processes": []}
    processes: list[dict[str, Any]] = []
    for row in csv.reader(io.StringIO(result.stdout)):
        if len(row) < 3:
            continue
        try:
            processes.append({"pid": int(row[0].strip()), "name": row[1].strip(), "used_memory_mb": int(row[2].strip())})
        except ValueError:
            continue
    return {"available": True, "processes": processes}


def exclusive_check(max_foreign_mb: int = 512) -> dict[str, Any]:
    state = snapshot()
    processes = state.get("processes", [])
    foreign = [p for p in processes if int(p.get("used_memory_mb", 0)) > max_foreign_mb]
    return {**state, "foreign_processes": foreign, "passed": not foreign}

