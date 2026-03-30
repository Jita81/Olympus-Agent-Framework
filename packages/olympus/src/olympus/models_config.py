"""Pydantic models for agent and pipeline YAML files."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ScoringConfig(BaseModel):
    """Agent scoring thresholds and optional rule text."""

    min_score: float = 0.0
    completeness_check: str | None = None


class AgentConfig(BaseModel):
    name: str
    version: str = "1.0.0"
    role: str | None = None
    description: str | None = None
    system_prompt: str
    tools: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    input_schema: str | None = None
    output_schema: str
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)


class PipelineNode(BaseModel):
    agent: str
    id: str


class PipelineEdge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    condition: str | None = None

    model_config = {"populate_by_name": True}


class RetryConfig(BaseModel):
    on_score_below: float = 0.7
    max_retries: int = 2
    strategy: str = "escalate_prompt"  # escalate_prompt | widen_retrieval | flag_human


class PipelineConfig(BaseModel):
    name: str
    version: str = "1.0.0"
    description: str | None = None
    state_schema: str
    nodes: list[PipelineNode]
    edges: list[PipelineEdge]
    retry: RetryConfig | None = None
    orchestrator: str | None = None
