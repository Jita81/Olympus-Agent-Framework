"""High-level pipeline execution."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from olympus.claude_runner import anthropic_client_from_env
from olympus.conditions import default_demo_conditions
from olympus.graph_builder import load_context_and_compile
from olympus.loader import load_pipeline
from olympus.run_store import RunStore
from olympus.runtime_context import default_sqlite_path
from olympus.schema_registry import default_demo_schemas, resolve_state_schema


def run_pipeline(
    *,
    pipeline_path: Path,
    agents_dir: Path,
    initial_state: BaseModel,
    model: str = "claude-sonnet-4-20250514",
    db_path: Path | None = None,
    register_demo: bool = False,
) -> tuple[BaseModel, str]:
    """
    Execute a pipeline once. Returns (final_state, run_id).

    When `ANTHROPIC_API_KEY` is unset, uses deterministic mocks for built-in demo schemas.
    """

    if register_demo:
        default_demo_schemas()
        default_demo_conditions()

    client = anthropic_client_from_env()
    store_path = db_path or default_sqlite_path()
    store = RunStore(store_path)
    pipeline_cfg = load_pipeline(pipeline_path)
    run_id = store.start_run(
        pipeline_name=pipeline_cfg.name,
        pipeline_version=pipeline_cfg.version,
        input_payload=initial_state.model_dump(),
    )

    app, ctx = load_context_and_compile(
        pipeline_path=pipeline_path,
        agents_dir=agents_dir,
        run_store=store,
        run_id=run_id,
        client=client,
        model=model,
    )

    final = app.invoke(initial_state)
    if not isinstance(final, BaseModel):
        state_cls = resolve_state_schema(pipeline_cfg.state_schema)
        final = state_cls.model_validate(final)

    calls = store.list_agent_calls(run_id)
    scores = [c.score for c in calls if c.score is not None]
    overall = sum(scores) / len(scores) if scores else None
    store.complete_run(run_id, overall_score=overall)

    return final, run_id
