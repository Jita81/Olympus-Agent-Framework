"""High-level pipeline execution."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel

from olympus.claude_runner import anthropic_client_from_env
from olympus.conditions import default_demo_conditions
from olympus.graph_builder import load_context_and_compile
from olympus.loader import load_pipeline
from olympus.run_store import RunStore
from olympus.runtime_context import default_sqlite_path
from olympus.schema_registry import (
    default_demo_schemas,
    register_lethe_schemas,
    resolve_state_schema,
)
from olympus.studio_store import StudioStore
from olympus.tool_context import reset_tool_context, set_tool_context


def run_pipeline(
    *,
    pipeline_path: Path,
    agents_dir: Path,
    initial_state: BaseModel,
    model: str = "claude-sonnet-4-20250514",
    db_path: Path | None = None,
    register_demo: bool = False,
    register_lethe: bool = False,
    register_athena: bool = False,
    index_repo: bool = False,
    chroma_path: Path | None = None,
    embedding_model: str = "all-MiniLM-L6-v2",
    studio_store: StudioStore | None = None,
) -> tuple[BaseModel, str]:
    """
    Execute a pipeline once. Returns (final_state, run_id).

    When `ANTHROPIC_API_KEY` is unset, uses deterministic mocks for built-in demo schemas.
    """

    if register_demo:
        default_demo_schemas()
        default_demo_conditions()
    if register_lethe:
        register_lethe_schemas()
    if register_athena:
        from olympus.athena_conditions import register_athena_conditions
        from olympus.athena_state import register_athena_schemas
        from olympus.athena_tools import register_athena_tools

        register_athena_schemas()
        register_athena_tools()
        register_athena_conditions()

    client = anthropic_client_from_env()
    store_path = db_path or default_sqlite_path()
    store = RunStore(store_path)
    if studio_store is None and os.environ.get("OLYMPUS_STUDIO", "").strip() == "1":
        studio_store = StudioStore(store_path)
    if studio_store is not None:
        studio_store.sync_agents_from_disk(agents_dir)
        studio_store.sync_pipeline_from_disk(pipeline_path)

    pipeline_cfg = load_pipeline(pipeline_path)
    if studio_store is not None:
        pipeline_cfg = studio_store.resolve_pipeline_config(pipeline_path, fallback=pipeline_cfg)

    run_id = store.start_run(
        pipeline_name=pipeline_cfg.name,
        pipeline_version=pipeline_cfg.version,
        input_payload=initial_state.model_dump(),
    )
    if studio_store is not None:
        studio_store.append_run_event(
            run_id=run_id,
            event_type="run_started",
            payload={"pipeline": pipeline_cfg.name},
        )

    app, ctx = load_context_and_compile(
        pipeline_path=pipeline_path,
        agents_dir=agents_dir,
        run_store=store,
        run_id=run_id,
        client=client,
        model=model,
        studio_store=studio_store,
    )

    token = None
    index_meta: dict | None = None
    if index_repo:
        from olympus.indexing import build_index

        repo = Path(initial_state.model_dump().get("repo_path", ".")).resolve()
        cpath = chroma_path or (store_path.parent / "chroma_lethe")
        collection = f"lethe_{run_id.replace('-', '')[:16]}"
        tctx = build_index(
            repo,
            chroma_path=cpath,
            collection_name=collection,
            embedding_model_name=embedding_model,
        )
        index_meta = {
            "merkle_root": tctx.merkle_root,
            "indexed_chunks": tctx.indexed_chunks,
        }
        token = set_tool_context(tctx)

    try:
        final = app.invoke(initial_state)
    finally:
        if token is not None:
            reset_tool_context(token)
    if not isinstance(final, BaseModel):
        state_cls = resolve_state_schema(pipeline_cfg.state_schema)
        final = state_cls.model_validate(final)

    if index_meta and pipeline_cfg.state_schema == "LethePipelineState":
        state_cls = resolve_state_schema(pipeline_cfg.state_schema)
        merged = {**final.model_dump(), **index_meta}
        final = state_cls.model_validate(merged)

    calls = store.list_agent_calls(run_id)
    scores = [c.score for c in calls if c.score is not None]
    overall = sum(scores) / len(scores) if scores else None
    store.complete_run(run_id, overall_score=overall)
    if studio_store is not None:
        studio_store.append_run_event(
            run_id=run_id,
            event_type="run_completed",
            payload={"overall_score": overall},
        )

    return final, run_id
