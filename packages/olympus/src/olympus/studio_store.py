"""SQLite catalog for Tuning Studio: agent/pipeline versions and run events."""

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

import yaml

from olympus.loader import load_agent, load_pipeline
from olympus.models_config import AgentConfig, PipelineConfig


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class PipelineVersionRow:
    version_id: str
    pipeline_name: str
    created_at: str
    yaml_body: str
    source: str


@dataclass
class AgentVersionRow:
    version_id: str
    agent_name: str
    created_at: str
    system_prompt: str
    config_json: dict[str, Any]
    yaml_version: str
    source: str


class StudioStore:
    """Versioned agent/pipeline configs and run lifecycle events (same DB file as RunStore)."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_extra()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_extra(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS agent_versions (
                    version_id TEXT PRIMARY KEY,
                    agent_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    system_prompt TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    yaml_version TEXT NOT NULL,
                    source TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agent_current (
                    agent_name TEXT PRIMARY KEY,
                    current_version_id TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pipeline_versions (
                    version_id TEXT PRIMARY KEY,
                    pipeline_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    yaml_body TEXT NOT NULL,
                    source TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pipeline_current (
                    pipeline_name TEXT PRIMARY KEY,
                    current_version_id TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS run_events (
                    event_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS experiments (
                    experiment_id TEXT PRIMARY KEY,
                    agent_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_agent_versions_name ON agent_versions(agent_name);
                CREATE INDEX IF NOT EXISTS idx_run_events_run ON run_events(run_id);
                """
            )

    def list_run_events(self, run_id: str, *, after_seq: int = -1) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM run_events
                WHERE run_id = ? AND seq > ?
                ORDER BY seq
                """,
                (run_id, after_seq),
            ).fetchall()
        return [
            {
                "event_id": r["event_id"],
                "run_id": r["run_id"],
                "seq": r["seq"],
                "event_type": r["event_type"],
                "payload": json.loads(r["payload_json"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def append_run_event(
        self,
        *,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(seq), -1) + 1 AS n FROM run_events WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            seq = int(row["n"])
            eid = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO run_events (event_id, run_id, seq, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    eid,
                    run_id,
                    seq,
                    event_type,
                    json.dumps(payload),
                    _utc_now(),
                ),
            )

    def sync_agents_from_disk(self, agents_dir: Path) -> None:
        if not agents_dir.is_dir():
            return
        for path in sorted(agents_dir.iterdir()):
            if path.suffix.lower() not in (".yaml", ".yml"):
                continue
            cfg = load_agent(path)
            with self._conn() as conn:
                cur = conn.execute(
                    "SELECT current_version_id FROM agent_current WHERE agent_name = ?",
                    (cfg.name,),
                ).fetchone()
                if cur is not None:
                    continue
            self._insert_agent_version(
                cfg.name,
                cfg.system_prompt,
                cfg.config,
                cfg.version,
                source="disk",
            )

    def _insert_agent_version(
        self,
        name: str,
        prompt: str,
        config: dict[str, Any],
        yaml_version: str,
        *,
        source: str,
    ) -> str:
        vid = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO agent_versions (
                    version_id, agent_name, created_at, system_prompt,
                    config_json, yaml_version, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    vid,
                    name,
                    _utc_now(),
                    prompt,
                    json.dumps(config),
                    yaml_version,
                    source,
                ),
            )
            conn.execute(
                """
                INSERT INTO agent_current (agent_name, current_version_id)
                VALUES (?, ?)
                ON CONFLICT(agent_name) DO UPDATE SET
                    current_version_id = excluded.current_version_id
                """,
                (name, vid),
            )
        return vid

    def list_agent_names_on_disk(self, agents_dir: Path) -> list[str]:
        names: list[str] = []
        if not agents_dir.is_dir():
            return names
        for path in sorted(agents_dir.iterdir()):
            if path.suffix.lower() not in (".yaml", ".yml"):
                continue
            names.append(load_agent(path).name)
        return names

    def list_catalog_agent_names(self, agents_dir: Path) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT agent_name FROM agent_current ORDER BY agent_name"
            ).fetchall()
        db_names = [r["agent_name"] for r in rows]
        disk = set(self.list_agent_names_on_disk(agents_dir))
        merged = set(db_names) | disk
        return sorted(merged)

    def get_agent_current(self, name: str) -> AgentVersionRow | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT v.* FROM agent_versions v
                JOIN agent_current c ON c.current_version_id = v.version_id
                WHERE v.agent_name = ?
                """,
                (name,),
            ).fetchone()
        if row is None:
            return None
        return AgentVersionRow(
            version_id=row["version_id"],
            agent_name=row["agent_name"],
            created_at=row["created_at"],
            system_prompt=row["system_prompt"],
            config_json=json.loads(row["config_json"]),
            yaml_version=row["yaml_version"],
            source=row["source"],
        )

    def list_agent_versions(self, name: str) -> list[AgentVersionRow]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_versions WHERE agent_name = ? ORDER BY created_at",
                (name,),
            ).fetchall()
        return [
            AgentVersionRow(
                version_id=r["version_id"],
                agent_name=r["agent_name"],
                created_at=r["created_at"],
                system_prompt=r["system_prompt"],
                config_json=json.loads(r["config_json"]),
                yaml_version=r["yaml_version"],
                source=r["source"],
            )
            for r in rows
        ]

    def update_agent_prompt(self, name: str, prompt: str) -> str:
        cur = self.get_agent_current(name)
        if cur is None:
            raise KeyError(name)
        return self._insert_agent_version(
            name,
            prompt,
            cur.config_json,
            cur.yaml_version,
            source="api",
        )

    def update_agent_config(self, name: str, config: dict[str, Any]) -> str:
        cur = self.get_agent_current(name)
        if cur is None:
            raise KeyError(name)
        return self._insert_agent_version(
            name,
            cur.system_prompt,
            config,
            cur.yaml_version,
            source="api",
        )

    def rollback_agent(self, name: str, version_id: str) -> None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM agent_versions WHERE agent_name = ? AND version_id = ?",
                (name, version_id),
            ).fetchone()
            if row is None:
                raise KeyError(version_id)
            conn.execute(
                "UPDATE agent_current SET current_version_id = ? WHERE agent_name = ?",
                (version_id, name),
            )

    def sync_pipeline_from_disk(self, pipeline_path: Path) -> None:
        if not pipeline_path.is_file():
            return
        cfg = load_pipeline(pipeline_path)
        body = pipeline_path.read_text(encoding="utf-8")
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT current_version_id FROM pipeline_current WHERE pipeline_name = ?",
                (cfg.name,),
            ).fetchone()
            if cur is not None:
                return
        self._insert_pipeline_version(cfg.name, body, source="disk")

    def _insert_pipeline_version(self, name: str, yaml_body: str, *, source: str) -> str:
        vid = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO pipeline_versions (
                    version_id, pipeline_name, created_at, yaml_body, source
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (vid, name, _utc_now(), yaml_body, source),
            )
            conn.execute(
                """
                INSERT INTO pipeline_current (pipeline_name, current_version_id)
                VALUES (?, ?)
                ON CONFLICT(pipeline_name) DO UPDATE SET
                    current_version_id = excluded.current_version_id
                """,
                (name, vid),
            )
        return vid

    def get_pipeline_current_yaml(self, name: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT v.yaml_body FROM pipeline_versions v
                JOIN pipeline_current c ON c.current_version_id = v.version_id
                WHERE v.pipeline_name = ?
                """,
                (name,),
            ).fetchone()
        return row["yaml_body"] if row else None

    def update_pipeline_yaml(self, name: str, yaml_body: str) -> str:
        return self._insert_pipeline_version(name, yaml_body, source="api")

    def create_experiment(self, agent_name: str, payload: dict[str, Any]) -> str:
        eid = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO experiments (experiment_id, agent_name, created_at, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (eid, agent_name, _utc_now(), json.dumps(payload)),
            )
        return eid

    def list_pipeline_names(self) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT pipeline_name FROM pipeline_versions ORDER BY pipeline_name"
            ).fetchall()
        return [r["pipeline_name"] for r in rows]

    def list_pipeline_versions(self, name: str) -> list[PipelineVersionRow]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM pipeline_versions WHERE pipeline_name = ? ORDER BY created_at",
                (name,),
            ).fetchall()
        return [
            PipelineVersionRow(
                version_id=r["version_id"],
                pipeline_name=r["pipeline_name"],
                created_at=r["created_at"],
                yaml_body=r["yaml_body"],
                source=r["source"],
            )
            for r in rows
        ]

    def resolve_pipeline_config(
        self, pipeline_path: Path, *, fallback: PipelineConfig | None = None
    ) -> PipelineConfig:
        base = fallback or load_pipeline(pipeline_path)
        body = self.get_pipeline_current_yaml(base.name)
        if body is None:
            return base
        data = yaml.safe_load(body)
        if not isinstance(data, dict):
            return base
        return PipelineConfig.model_validate(data)

    def merge_agent_configs(self, disk_agents: dict[str, AgentConfig]) -> dict[str, AgentConfig]:
        out = dict(disk_agents)
        for name, orig in list(out.items()):
            row = self.get_agent_current(name)
            if row is None:
                continue
            out[name] = orig.model_copy(
                update={
                    "system_prompt": row.system_prompt,
                    "config": row.config_json,
                    "version": row.yaml_version,
                }
            )
        return out

    def get_experiment(self, experiment_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM experiments WHERE experiment_id = ?", (experiment_id,)
            ).fetchone()
        if row is None:
            return None
        return {
            "experiment_id": row["experiment_id"],
            "agent_name": row["agent_name"],
            "created_at": row["created_at"],
            "payload": json.loads(row["payload_json"]),
        }
