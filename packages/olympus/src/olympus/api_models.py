"""Request/response Pydantic models for the Tuning Studio API (module-level for OpenAPI)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PromptBody(BaseModel):
    system_prompt: str


class ConfigBody(BaseModel):
    config: dict[str, Any]


class RollbackBody(BaseModel):
    version_id: str


class PipelinePutBody(BaseModel):
    yaml: str


class SectionFeedback(BaseModel):
    section: str
    agent: str
    accurate: bool
    complete: bool
    relevant: bool
    notes: str = ""


class FeedbackBody(BaseModel):
    outcome: str = Field(..., description="q1 | q2 | q3 | rating_1_5")
    overall_notes: str = ""
    section_feedback: list[SectionFeedback] = Field(default_factory=list)


class IsolationTestBody(BaseModel):
    state: dict[str, Any] = Field(default_factory=dict)
    state_schema: str | None = None


class ExperimentBody(BaseModel):
    agent_name: str
    config_a_version_id: str
    config_b_version_id: str
    input_state: dict[str, Any] = Field(default_factory=dict)


class PromoteBody(BaseModel):
    winner_version_id: str


class RunPipelineBody(BaseModel):
    state: dict[str, Any] = Field(default_factory=dict)
    register_demo: bool = False
    register_lethe: bool = False
    register_athena: bool = False
    index_repo: bool = False
