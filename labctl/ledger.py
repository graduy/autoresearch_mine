from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS experiments (
  experiment_id TEXT PRIMARY KEY,
  card_json TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  experiment_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  source TEXT NOT NULL,
  actor TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  experiment_id TEXT NOT NULL,
  stage TEXT NOT NULL,
  seed INTEGER,
  status TEXT NOT NULL,
  exit_code INTEGER,
  metric REAL,
  runtime_seconds REAL,
  peak_vram_mb REAL,
  cost_usd REAL,
  command_json TEXT NOT NULL,
  run_dir TEXT NOT NULL,
  receipt_path TEXT,
  created_at REAL NOT NULL,
  finished_at REAL
);
CREATE TABLE IF NOT EXISTS artifacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  path TEXT NOT NULL,
  sha256 TEXT,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  experiment_id TEXT NOT NULL,
  run_id TEXT,
  event TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at REAL NOT NULL
);
"""


class Ledger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _init(self) -> None:
        with self._connect() as db:
            db.executescript(SCHEMA)

    def register_experiment(self, experiment_id: str, card: dict[str, Any]) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO experiments(experiment_id,card_json,created_at) VALUES(?,?,?)",
                (experiment_id, json.dumps(card, ensure_ascii=False, sort_keys=True), time.time()),
            )

    def approval(self, experiment_id: str, decision: str, source: str, actor: str) -> None:
        if decision not in {"approve", "reject", "revoke"}:
            raise ValueError(f"unsupported approval decision: {decision}")
        with self._connect() as db:
            db.execute(
                "INSERT INTO approvals(experiment_id,decision,source,actor,created_at) VALUES(?,?,?,?,?)",
                (experiment_id, decision, source, actor, time.time()),
            )
            db.execute(
                "INSERT INTO events(experiment_id,event,payload_json,created_at) VALUES(?,?,?,?)",
                (experiment_id, "approval", json.dumps({"decision": decision, "source": source, "actor": actor}), time.time()),
            )

    def approved(self, experiment_id: str) -> bool:
        row = self.latest_approval(experiment_id)
        return bool(row and row["decision"] == "approve")

    def latest_approval(self, experiment_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM approvals WHERE experiment_id=? ORDER BY id DESC LIMIT 1",
                (experiment_id,),
            ).fetchone()
        return dict(row) if row else None

    def run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return dict(row) if row else None

    def experiments(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM experiments ORDER BY created_at").fetchall()
        return [dict(row) for row in rows]

    def start_run(self, run: dict[str, Any]) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO runs(run_id,experiment_id,stage,seed,status,command_json,run_dir,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (run["run_id"], run["experiment_id"], run["stage"], run.get("seed"), "running",
                 json.dumps(run["command"]), run["run_dir"], time.time()),
            )
            db.execute(
                "INSERT INTO events(experiment_id,run_id,event,payload_json,created_at) VALUES(?,?,?,?,?)",
                (run["experiment_id"], run["run_id"], "run_started", json.dumps(run), time.time()),
            )

    def finish_run(self, run_id: str, result: dict[str, Any]) -> None:
        fields = {
            "status": result.get("status"),
            "exit_code": result.get("exit_code"),
            "metric": result.get("metric"),
            "runtime_seconds": result.get("runtime_seconds"),
            "peak_vram_mb": result.get("peak_vram_mb"),
            "cost_usd": result.get("cost_usd"),
            "receipt_path": result.get("receipt_path"),
            "finished_at": time.time(),
        }
        with self._connect() as db:
            db.execute(
                """UPDATE runs SET status=:status,exit_code=:exit_code,metric=:metric,
                runtime_seconds=:runtime_seconds,peak_vram_mb=:peak_vram_mb,cost_usd=:cost_usd,
                receipt_path=:receipt_path,finished_at=:finished_at WHERE run_id=:run_id""",
                {**fields, "run_id": run_id},
            )
            row = db.execute("SELECT experiment_id FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if row:
                db.execute(
                    "INSERT INTO events(experiment_id,run_id,event,payload_json,created_at) VALUES(?,?,?,?,?)",
                    (row["experiment_id"], run_id, "run_finished", json.dumps(result), time.time()),
                )

    def reclassify_run(self, run_id: str, status: str, reason: str) -> None:
        with self._connect() as db:
            db.execute("UPDATE runs SET status=? WHERE run_id=?", (status, run_id))
            row = db.execute("SELECT experiment_id FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if row:
                db.execute(
                    "INSERT INTO events(experiment_id,run_id,event,payload_json,created_at) VALUES(?,?,?,?,?)",
                    (row["experiment_id"], run_id, "run_reclassified", json.dumps({"status": status, "reason": reason}), time.time()),
                )

    def add_artifact(self, run_id: str, kind: str, path: str, sha256: str | None) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO artifacts(run_id,kind,path,sha256,created_at) VALUES(?,?,?,?,?)",
                (run_id, kind, path, sha256, time.time()),
            )

    def event(self, experiment_id: str, event: str, payload: dict[str, Any], run_id: str | None = None) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO events(experiment_id,run_id,event,payload_json,created_at) VALUES(?,?,?,?,?)",
                (experiment_id, run_id, event, json.dumps(payload, ensure_ascii=False), time.time()),
            )

    def runs(self, experiment_id: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as db:
            if experiment_id:
                rows = db.execute("SELECT * FROM runs WHERE experiment_id=? ORDER BY created_at", (experiment_id,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM runs ORDER BY created_at").fetchall()
        return [dict(row) for row in rows]

    def best_metric(self, experiment_id: str, direction: str) -> float | None:
        values = [r["metric"] for r in self.runs(experiment_id) if r["status"] == "keep" and r["metric"] is not None]
        if not values:
            return None
        return min(values) if direction == "minimize" else max(values)

    def events(self, experiment_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM events WHERE experiment_id=? ORDER BY id", (experiment_id,)).fetchall()
        return [dict(row) for row in rows]

    def artifacts(self, experiment_id: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT a.*, r.experiment_id, r.stage, r.seed, r.status
            FROM artifacts a JOIN runs r ON r.run_id = a.run_id
        """
        params: tuple[Any, ...] = ()
        if experiment_id:
            query += " WHERE r.experiment_id=?"
            params = (experiment_id,)
        query += " ORDER BY a.created_at"
        with self._connect() as db:
            rows = db.execute(query, params).fetchall()
        return [dict(row) for row in rows]
