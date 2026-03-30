"""Compile pipeline YAML to an executable LangGraph."""

from __future__ import annotations

from pathlib import Path

from langgraph.graph import END, START, StateGraph

from olympus.loader import load_agents_dir, load_pipeline
from olympus.models_config import PipelineConfig
from olympus.node_executor import make_agent_node, make_router_fn
from olympus.runtime_context import RuntimeContext
from olympus.schema_registry import resolve_state_schema
from olympus.studio_store import StudioStore


def _entry_node_id(pipeline: PipelineConfig) -> str:
    targets = {e.to for e in pipeline.edges}
    starts = [n.id for n in pipeline.nodes if n.id not in targets]
    if len(starts) != 1:
        raise ValueError(f"Expected exactly one entry node (no incoming edges); got {starts!r}")
    return starts[0]


def _outgoing_grouped(pipeline: PipelineConfig) -> dict[str, list]:
    by: dict[str, list] = {}
    for e in pipeline.edges:
        by.setdefault(e.from_, []).append(e)
    return by


def build_compiled_graph(ctx: RuntimeContext):
    pipeline = ctx.pipeline
    state_model = resolve_state_schema(pipeline.state_schema)
    graph = StateGraph(state_model)

    node_by_id = {n.id: n for n in pipeline.nodes}
    for nid, pnode in node_by_id.items():
        try:
            agent = ctx.agents[pnode.agent]
        except KeyError as e:
            raise KeyError(f"Unknown agent {pnode.agent!r} for node {nid!r}") from e
        graph.add_node(nid, make_agent_node(ctx, nid, agent))

    entry = _entry_node_id(pipeline)
    graph.add_edge(START, entry)

    outgoing_by_from = _outgoing_grouped(pipeline)
    for from_id in node_by_id:
        edges_out = outgoing_by_from.get(from_id, [])
        if not edges_out:
            graph.add_edge(from_id, END)
            continue

        unconditional = [e for e in edges_out if not e.condition]
        conditional = [e for e in edges_out if e.condition]

        if len(unconditional) == 1 and not conditional:
            graph.add_edge(from_id, unconditional[0].to)
        elif conditional and not unconditional:
            route = make_router_fn(pipeline, from_id)
            targets = list({e.to for e in edges_out})
            path_map = {t: t for t in targets}
            graph.add_conditional_edges(from_id, route, path_map)
        elif len(unconditional) == 1 and conditional:
            raise ValueError(
                f"Node {from_id!r}: mix of conditional and unconditional edges "
                "is not supported in Sprint 0."
            )
        else:
            raise ValueError(f"Unsupported edge pattern from {from_id!r}")

    return graph.compile()


def load_context_and_compile(
    *,
    pipeline_path: Path,
    agents_dir: Path,
    run_store,
    run_id: str,
    client,
    model: str,
    studio_store: StudioStore | None = None,
):
    pipeline_disk = load_pipeline(pipeline_path)
    agents_disk = load_agents_dir(agents_dir)
    if studio_store is not None:
        pipeline = studio_store.resolve_pipeline_config(pipeline_path, fallback=pipeline_disk)
        agents = studio_store.merge_agent_configs(agents_disk)
    else:
        pipeline = pipeline_disk
        agents = agents_disk
    ctx = RuntimeContext(
        agents=agents,
        pipeline=pipeline,
        client=client,
        model=model,
        run_store=run_store,
        run_id=run_id,
        studio_store=studio_store,
    )
    return build_compiled_graph(ctx), ctx
