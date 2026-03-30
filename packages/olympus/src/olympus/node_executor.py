"""LangGraph node factory: Claude + logging + scoring + retries."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from olympus.claude_runner import run_agent_turn
from olympus.conditions import eval_condition
from olympus.models_config import AgentConfig, PipelineConfig
from olympus.runtime_context import RuntimeContext
from olympus.schema_registry import resolve_output_schema
from olympus.scoring import score_agent_output
from olympus.tools import resolve_tools


def _merge_updates(parsed: BaseModel) -> dict[str, Any]:
    return parsed.model_dump(exclude_unset=True)


def make_agent_node(ctx: RuntimeContext, node_id: str, agent: AgentConfig):
    output_model = resolve_output_schema(agent.output_schema)
    tool_specs = resolve_tools(agent.tools)

    def node_fn(state: BaseModel) -> dict[str, Any]:
        pipeline_retry = ctx.pipeline.retry
        max_retries = pipeline_retry.max_retries if pipeline_retry else 0
        strategy = pipeline_retry.strategy if pipeline_retry else "escalate_prompt"
        threshold = agent.scoring.min_score

        suffix = ""
        last_parsed: BaseModel | None = None
        last_feedback = ""

        for attempt in range(max_retries + 1):
            parsed, meta = run_agent_turn(
                ctx.client,
                agent=agent,
                state=state,
                output_model=output_model,
                tool_specs=tool_specs,
                model=ctx.model,
                max_tokens=ctx.max_tokens,
                system_suffix=suffix,
            )
            score, feedback = score_agent_output(agent, parsed)
            last_parsed = parsed
            last_feedback = feedback

            state_json = state.model_dump_json(indent=2)
            prompt_full = f"{agent.system_prompt}\n\n--- state ---\n{state_json}{suffix}"
            ctx.run_store.append_agent_call(
                run_id=ctx.run_id,
                agent_name=agent.name,
                agent_version=agent.version,
                node_id=node_id,
                prompt_full=prompt_full,
                response_full=meta["response_text"],
                tool_calls=meta["tool_calls_log"],
                input_tokens=meta["input_tokens"],
                output_tokens=meta["output_tokens"],
                latency_ms=meta["latency_ms"],
                score=score,
                score_feedback=feedback,
                retry_count=attempt,
            )

            if score >= threshold:
                return _merge_updates(parsed)

            if attempt < max_retries:
                if strategy == "escalate_prompt":
                    suffix = (
                        f"\n\nYour previous output scored {score}. "
                        f"The specific issue was: {last_feedback}. Please improve."
                    )
                elif strategy == "widen_retrieval":
                    suffix = (
                        f"\n\nPrevious score {score}. {last_feedback} "
                        "Use broader retrieval or more context if applicable."
                    )
                elif strategy == "flag_human":
                    suffix = (
                        f"\n\nScore {score}. {last_feedback}. "
                        "If still failing, flag for human review."
                    )

        assert last_parsed is not None
        return _merge_updates(last_parsed)

    return node_fn


def make_router_fn(pipeline: PipelineConfig, from_node_id: str):
    outgoing = [e for e in pipeline.edges if e.from_ == from_node_id]
    unconditional = [e for e in outgoing if not e.condition]
    conditional = [e for e in outgoing if e.condition]

    if len(unconditional) > 1:
        raise ValueError(f"Node {from_node_id!r} has multiple unconditional edges (ambiguous).")

    def route(state: BaseModel) -> str:
        for e in conditional:
            if e.condition and eval_condition(e.condition, state):
                return e.to
        if unconditional:
            return unconditional[0].to
        raise RuntimeError(
            f"No matching edge from {from_node_id!r}: "
            f"add an unconditional fallback or cover all cases with conditions."
        )

    return route
