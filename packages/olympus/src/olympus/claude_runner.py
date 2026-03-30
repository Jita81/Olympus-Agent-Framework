"""Agent turns: optional tool loop, then structured JSON output via Claude or mock."""

from __future__ import annotations

import json
import time
from typing import Any

from anthropic import Anthropic
from pydantic import BaseModel, TypeAdapter

from olympus.models_config import AgentConfig
from olympus.tools import ToolSpec, anthropic_tool_defs


def _content_to_text(message: Any) -> str:
    parts: list[str] = []
    for block in getattr(message, "content", []) or []:
        btype = getattr(block, "type", None)
        if btype == "text":
            parts.append(getattr(block, "text", "") or "")
        elif btype == "tool_use":
            parts.append(
                json.dumps(
                    {
                        "type": "tool_use",
                        "name": getattr(block, "name", ""),
                        "input": getattr(block, "input", {}),
                    }
                )
            )
    return "\n".join(parts) if parts else ""


def _parsed_output(parsed_message: Any) -> BaseModel | None:
    for block in getattr(parsed_message, "content", []) or []:
        po = getattr(block, "parsed_output", None)
        if po is not None:
            return po
    return None


def _assistant_blocks_to_params(message: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for block in getattr(message, "content", []) or []:
        d = block.model_dump()
        out.append(d)
    return out


def _accumulate_usage(total_in: int, total_out: int, message: Any) -> tuple[int, int]:
    usage = getattr(message, "usage", None)
    if usage:
        total_in += getattr(usage, "input_tokens", 0) or 0
        total_out += getattr(usage, "output_tokens", 0) or 0
    return total_in, total_out


def _run_tools(
    tool_specs: list[ToolSpec],
    tool_uses: list[Any],
) -> list[dict[str, Any]]:
    by_name = {s.name: s for s in tool_specs}
    results: list[dict[str, Any]] = []
    for block in tool_uses:
        name = getattr(block, "name", "")
        use_id = getattr(block, "id", "")
        inp = getattr(block, "input", {}) or {}
        spec = by_name.get(name)
        if spec is None:
            text = f"error: unknown tool {name!r}"
            is_error = True
        else:
            try:
                text = spec.fn(**inp)
                if not isinstance(text, str):
                    text = json.dumps(text, default=str)
                is_error = False
            except Exception as e:
                text = f"error: {e}"
                is_error = True
        results.append(
            {
                "type": "tool_result",
                "tool_use_id": use_id,
                "content": text,
                "is_error": is_error,
            }
        )
    return results


def _extract_tool_uses(message: Any) -> list[Any]:
    blocks = getattr(message, "content", []) or []
    return [b for b in blocks if getattr(b, "type", None) == "tool_use"]


def _run_with_tools_then_parse(
    client: Anthropic,
    *,
    agent: AgentConfig,
    state: BaseModel,
    output_model: type[BaseModel],
    tool_specs: list[ToolSpec],
    model: str,
    max_tokens: int,
    system_suffix: str,
    max_tool_rounds: int = 24,
) -> tuple[BaseModel, dict[str, Any]]:
    state_block = state.model_dump_json(indent=2)
    system = (
        f"{agent.system_prompt.rstrip()}\n\n"
        f"---\nCurrent pipeline state (JSON):\n{state_block}"
        f"{system_suffix}"
    )
    user_text = (
        "Use tools as needed to inspect the repository. When finished, respond with "
        "a JSON object matching the required output schema only (no markdown)."
    )
    tools = anthropic_tool_defs(tool_specs) if tool_specs else None

    messages: list[dict[str, Any]] = [{"role": "user", "content": user_text}]
    tool_calls_log: list[dict[str, Any]] = []
    total_in = 0
    total_out = 0
    t0 = time.perf_counter()
    response_text_parts: list[str] = []

    for _ in range(max_tool_rounds):
        kwargs: dict[str, Any] = {
            "max_tokens": max_tokens,
            "model": model,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        msg = client.messages.create(**kwargs)
        total_in, total_out = _accumulate_usage(total_in, total_out, msg)
        response_text_parts.append(_content_to_text(msg))
        messages.append({"role": "assistant", "content": _assistant_blocks_to_params(msg)})

        uses = _extract_tool_uses(msg)
        if uses:
            for u in uses:
                tool_calls_log.append(
                    {
                        "name": getattr(u, "name", ""),
                        "input": getattr(u, "input", {}),
                        "output": None,
                    }
                )
            results = _run_tools(tool_specs, uses)
            for i, r in enumerate(results):
                if i < len(tool_calls_log):
                    tool_calls_log[-len(results) + i]["output"] = r.get("content")
            messages.append({"role": "user", "content": results})
            continue

        stop = getattr(msg, "stop_reason", None)
        if stop == "max_tokens":
            break
        break

    messages.append(
        {
            "role": "user",
            "content": (
                "Now output only the final JSON object matching the required schema. "
                "Do not call tools."
            ),
        }
    )
    parsed_msg = client.messages.parse(
        max_tokens=max_tokens,
        model=model,
        system=system,
        messages=messages,
        output_format=output_model,
    )
    total_in, total_out = _accumulate_usage(total_in, total_out, parsed_msg)
    response_text_parts.append(_content_to_text(parsed_msg))

    parsed = _parsed_output(parsed_msg)
    if parsed is None:
        text = _content_to_text(parsed_msg)
        parsed = TypeAdapter(output_model).validate_json(text)

    latency_ms = int((time.perf_counter() - t0) * 1000)
    meta = {
        "input_tokens": total_in,
        "output_tokens": total_out,
        "latency_ms": latency_ms,
        "response_text": "\n---\n".join(response_text_parts),
        "tool_calls_log": tool_calls_log,
        "raw_message_repr": "\n---\n".join(response_text_parts)[:20000],
    }
    return parsed, meta


def run_agent_turn(
    client: Anthropic | None,
    *,
    agent: AgentConfig,
    state: BaseModel,
    output_model: type[BaseModel],
    tool_specs: list[ToolSpec],
    model: str,
    max_tokens: int = 1024,
    system_suffix: str = "",
) -> tuple[BaseModel, dict[str, Any]]:
    """
    Run tools in a loop (when client and tools are present), then structured output.

    Mock path when *client* is None uses `_mock_parse` for known output schemas.
    """

    t0 = time.perf_counter()
    if client is None:
        parsed = _mock_parse(agent, output_model, state, tool_specs)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        response_text = parsed.model_dump_json()
        meta = {
            "input_tokens": 0,
            "output_tokens": 0,
            "latency_ms": latency_ms,
            "response_text": response_text,
            "tool_calls_log": _mock_tool_log(output_model, tool_specs, state),
            "raw_message_repr": response_text,
        }
        return parsed, meta

    if tool_specs:
        return _run_with_tools_then_parse(
            client,
            agent=agent,
            state=state,
            output_model=output_model,
            tool_specs=tool_specs,
            model=model,
            max_tokens=max_tokens,
            system_suffix=system_suffix,
        )

    state_block = state.model_dump_json(indent=2)
    system = (
        f"{agent.system_prompt.rstrip()}\n\n"
        f"---\nCurrent pipeline state (JSON):\n{state_block}"
        f"{system_suffix}"
    )
    user_text = (
        "Respond with a JSON object matching the required schema for this step. "
        "Do not wrap in markdown."
    )
    parsed_msg = client.messages.parse(
        max_tokens=max_tokens,
        model=model,
        system=system,
        messages=[{"role": "user", "content": user_text}],
        output_format=output_model,
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)
    usage = getattr(parsed_msg, "usage", None)
    in_tok = getattr(usage, "input_tokens", 0) if usage else 0
    out_tok = getattr(usage, "output_tokens", 0) if usage else 0
    parsed = _parsed_output(parsed_msg)
    if parsed is None:
        text = _content_to_text(parsed_msg)
        parsed = TypeAdapter(output_model).validate_json(text)
    response_text = _content_to_text(parsed_msg)
    meta = {
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "latency_ms": latency_ms,
        "response_text": response_text,
        "tool_calls_log": [],
        "raw_message_repr": response_text[:20000],
    }
    return parsed, meta


def _mock_tool_log(
    output_model: type[BaseModel],
    tool_specs: list[ToolSpec],
    state: BaseModel,
) -> list[dict[str, Any]]:
    if output_model.__name__ != "LetheOutput":
        return []
    try:
        from olympus.tool_context import get_tool_context

        get_tool_context()
    except Exception:
        return []
    return [
        {"name": "search_index", "input": {"query": "def", "top_k": 3}, "output": "(mock log)"},
        {
            "name": "read_file",
            "input": {"path": "(first hit)", "start_line": 0, "end_line": -1},
            "output": "(mock)",
        },
    ]


def _mock_parse(
    agent: AgentConfig,
    output_model: type[BaseModel],
    state: BaseModel,
    tool_specs: list[ToolSpec],
) -> BaseModel:
    """Deterministic stub when no API key (tests and local demos)."""

    data = state.model_dump()
    if output_model.__name__ == "GreeterOutput":
        task = str(data.get("task", "world"))
        return output_model(greeting=f"Hello, {task}!")  # type: ignore[call-arg]
    if output_model.__name__ == "SummarizerOutput":
        g = data.get("greeting") or "nothing"
        return output_model(summary=f"Acknowledged: {g}")  # type: ignore[call-arg]
    if output_model.__name__ == "LetheOutput":
        from olympus import lethe_tools

        return lethe_tools.mock_lethe_output(state, tool_specs)
    if output_model.__name__.startswith("Athena"):
        from olympus.athena_mock import mock_athena_output

        return mock_athena_output(output_model, state)
    raise NotImplementedError(f"No mock for output schema {output_model.__name__}")


def anthropic_client_from_env() -> Anthropic | None:
    import os

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    return Anthropic(api_key=key)
