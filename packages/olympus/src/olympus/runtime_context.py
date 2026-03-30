"""Per-run settings shared by LangGraph nodes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from anthropic import Anthropic

from olympus.models_config import AgentConfig, PipelineConfig
from olympus.run_store import RunStore


@dataclass
class RuntimeContext:
    agents: dict[str, AgentConfig]
    pipeline: PipelineConfig
    client: Anthropic | None
    model: str
    run_store: RunStore
    run_id: str
    max_tokens: int = 1024


def default_sqlite_path(base_dir: Path | None = None) -> Path:
    root = base_dir or Path.cwd()
    return root / ".olympus" / "runs.sqlite"
