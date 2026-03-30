"""Register Pydantic models referenced by agent and pipeline YAML (`*_schema` fields)."""

from __future__ import annotations

from pydantic import BaseModel

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
