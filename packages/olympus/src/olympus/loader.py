"""Load agent and pipeline definitions from YAML on disk."""

from __future__ import annotations

from pathlib import Path

import yaml

from olympus.models_config import AgentConfig, PipelineConfig


def load_agent(path: Path) -> AgentConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Agent YAML must be a mapping: {path}")
    return AgentConfig.model_validate(data)


def load_pipeline(path: Path) -> PipelineConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Pipeline YAML must be a mapping: {path}")
    return PipelineConfig.model_validate(data)


def load_agents_dir(directory: Path) -> dict[str, AgentConfig]:
    """Load every `*.yaml` / `*.yml` in *directory* keyed by agent `name` from file."""

    agents: dict[str, AgentConfig] = {}
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in (".yaml", ".yml"):
            continue
        cfg = load_agent(path)
        if cfg.name in agents:
            raise ValueError(f"Duplicate agent name {cfg.name!r} ({path})")
        agents[cfg.name] = cfg
    return agents
