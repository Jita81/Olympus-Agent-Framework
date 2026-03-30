"""Append-only SQLite persistence for pipeline runs and agent calls."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class RunRecord:
    run_id: str
    pipeline_name: str
    pipeline_version: str
    input_payload: dict[str, Any]
    started_at: str
    completed_at: str | None
    overall_score: float | None


@dataclass
class AgentCallRecord:
    call_id: str
    run_id: str
    agent_name: str
    agent_version: str
    node_id: str
    prompt_full: str
    response_full: str
    tool_calls_json: list[dict[str, Any]]
    input_tokens: int
    output_tokens: int
    latency_ms: int
    score: float | None
    score_feedback: str | None
    retry_count: int
    timestamp: str


class RunStore:
    """Append-only run log. Rows are never updated or deleted (except run completion fields)."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    pipeline_name TEXT NOT NULL,
                    pipeline_version TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    overall_score REAL
                );
                CREATE TABLE IF NOT EXISTS agent_calls (
                    call_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(run_id),
                    agent_name TEXT NOT NULL,
                    agent_version TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    prompt_full TEXT NOT NULL,
                    response_full TEXT NOT NULL,
                    tool_calls_json TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    score REAL,
                    score_feedback TEXT,
                    retry_count INTEGER NOT NULL,
                    timestamp TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    feedback_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(run_id),
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_agent_calls_run ON agent_calls(run_id);
                """
            )

    def start_run(
        self,
        *,
        pipeline_name: str,
        pipeline_version: str,
        input_payload: dict[str, Any],
    ) -> str:
        run_id = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, pipeline_name, pipeline_version, input_json, started_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    pipeline_name,
                    pipeline_version,
                    json.dumps(input_payload),
                    _utc_now(),
                ),
            )
        return run_id

    def complete_run(self, run_id: str, *, overall_score: float | None) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE runs SET completed_at = ?, overall_score = ?
                WHERE run_id = ?
                """,
                (_utc_now(), overall_score, run_id),
            )

    def append_agent_call(
        self,
        *,
        run_id: str,
        agent_name: str,
        agent_version: str,
        node_id: str,
        prompt_full: str,
        response_full: str,
        tool_calls: list[dict[str, Any]],
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        score: float | None,
        score_feedback: str | None,
        retry_count: int,
    ) -> str:
        call_id = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO agent_calls (
                    call_id, run_id, agent_name, agent_version, node_id,
                    prompt_full, response_full, tool_calls_json,
                    input_tokens, output_tokens, latency_ms,
                    score, score_feedback, retry_count, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    call_id,
                    run_id,
                    agent_name,
                    agent_version,
                    node_id,
                    prompt_full,
                    response_full,
                    json.dumps(tool_calls),
                    input_tokens,
                    output_tokens,
                    latency_ms,
                    score,
                    score_feedback,
                    retry_count,
                    _utc_now(),
                ),
            )
        return call_id

    def get_run(self, run_id: str) -> RunRecord | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return RunRecord(
            run_id=row["run_id"],
            pipeline_name=row["pipeline_name"],
            pipeline_version=row["pipeline_version"],
            input_payload=json.loads(row["input_json"]),
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            overall_score=row["overall_score"],
        )

    def list_runs(self, *, limit: int = 100) -> list[RunRecord]:
        limit = min(max(limit, 1), 500)
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            RunRecord(
                run_id=r["run_id"],
                pipeline_name=r["pipeline_name"],
                pipeline_version=r["pipeline_version"],
                input_payload=json.loads(r["input_json"]),
                started_at=r["started_at"],
                completed_at=r["completed_at"],
                overall_score=r["overall_score"],
            )
            for r in rows
        ]

    def append_feedback(self, *, run_id: str, payload: dict[str, Any]) -> str:
        fid = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO feedback (feedback_id, run_id, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (fid, run_id, json.dumps(payload), _utc_now()),
            )
        return fid

    def list_feedback(self, run_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM feedback WHERE run_id = ? ORDER BY created_at",
                (run_id,),
            ).fetchall()
        return [
            {
                "feedback_id": r["feedback_id"],
                "run_id": r["run_id"],
                "payload": json.loads(r["payload_json"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def get_agent_call(self, run_id: str, call_id: str) -> AgentCallRecord | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM agent_calls WHERE run_id = ? AND call_id = ?",
                (run_id, call_id),
            ).fetchone()
        if row is None:
            return None
        r = row
        return AgentCallRecord(
            call_id=r["call_id"],
            run_id=r["run_id"],
            agent_name=r["agent_name"],
            agent_version=r["agent_version"],
            node_id=r["node_id"],
            prompt_full=r["prompt_full"],
            response_full=r["response_full"],
            tool_calls_json=json.loads(r["tool_calls_json"]),
            input_tokens=r["input_tokens"],
            output_tokens=r["output_tokens"],
            latency_ms=r["latency_ms"],
            score=r["score"],
            score_feedback=r["score_feedback"],
            retry_count=r["retry_count"],
            timestamp=r["timestamp"],
        )

    def list_agent_calls(self, run_id: str) -> list[AgentCallRecord]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_calls WHERE run_id = ? ORDER BY timestamp",
                (run_id,),
            ).fetchall()
        return [
            AgentCallRecord(
                call_id=r["call_id"],
                run_id=r["run_id"],
                agent_name=r["agent_name"],
                agent_version=r["agent_version"],
                node_id=r["node_id"],
                prompt_full=r["prompt_full"],
                response_full=r["response_full"],
                tool_calls_json=json.loads(r["tool_calls_json"]),
                input_tokens=r["input_tokens"],
                output_tokens=r["output_tokens"],
                latency_ms=r["latency_ms"],
                score=r["score"],
                score_feedback=r["score_feedback"],
                retry_count=r["retry_count"],
                timestamp=r["timestamp"],
            )
            for r in rows
        ]
