"""Register Pydantic models referenced by agent and pipeline YAML (`*_schema` fields)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# Populated by `register_schema` and demo/example imports.
_STATE_SCHEMAS: dict[str, type[BaseModel]] = {}
_OUTPUT_SCHEMAS: dict[str, type[BaseModel]] = {}


def register_state_schema(name: str, model: type[BaseModel]) -> None:
    _STATE_SCHEMAS[name] = model


def register_output_schema(name: str, model: type[BaseModel]) -> None:
    _OUTPUT_SCHEMAS[name] = model


def resolve_state_schema(name: str) -> type[BaseModel]:
    try:
        return _STATE_SCHEMAS[name]
    except KeyError as e:
        raise KeyError(
            f"Unknown state_schema {name!r}. Registered: {sorted(_STATE_SCHEMAS)}"
        ) from e


def resolve_output_schema(name: str) -> type[BaseModel]:
    try:
        return _OUTPUT_SCHEMAS[name]
    except KeyError as e:
        raise KeyError(
            f"Unknown output_schema {name!r}. Registered: {sorted(_OUTPUT_SCHEMAS)}"
        ) from e


def default_demo_schemas() -> None:
    """Register built-in demo pipeline models (idempotent)."""

    class DemoPipelineState(BaseModel):
        """Minimal feed-forward state for the Sprint 0 demo pipeline."""

        task: str = ""
        greeting: str | None = None
        summary: str | None = None

    class GreeterOutput(BaseModel):
        greeting: str

    class SummarizerOutput(BaseModel):
        summary: str

    register_state_schema("DemoPipelineState", DemoPipelineState)
    register_output_schema("GreeterOutput", GreeterOutput)
    register_output_schema("SummarizerOutput", SummarizerOutput)


def register_lethe_schemas() -> None:
    """Lethe slice: index + memory agent state and output (idempotent)."""

    if "LethePipelineState" in _STATE_SCHEMAS:
        return

    class LethePipelineState(BaseModel):
        """Pipeline state for a Lethe-only run (Sprint 1)."""

        repo_path: str = "."
        index_query: str = "main entrypoint"
        merkle_root: str | None = None
        indexed_chunks: int | None = None
        summary: str | None = None
        sample_hits: list[dict[str, Any]] = Field(default_factory=list)
        sample_file_excerpt: str | None = None
        git_history_json: str | None = None

    class LetheOutput(BaseModel):
        repo_path: str
        merkle_root: str
        indexed_chunks: int
        summary: str
        sample_hits: list[dict[str, Any]] = Field(default_factory=list)
        sample_file_excerpt: str = ""
        git_history_json: str = "{}"

    register_state_schema("LethePipelineState", LethePipelineState)
    register_output_schema("LetheOutput", LetheOutput)
