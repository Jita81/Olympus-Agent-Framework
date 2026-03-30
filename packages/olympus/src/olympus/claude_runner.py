"""Single-agent Claude turn: optional tools, structured output, usage metrics."""

from __future__ import annotations

import json
import time
from typing import Any

from anthropic import Anthropic
from pydantic import BaseModel

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
    One Claude call with structured JSON output via `messages.parse`.

    When *client* is None (no API key), uses a deterministic mock for known demo schemas.

    Returns (parsed_model, meta) with input_tokens, output_tokens, latency_ms,
    response_text, tool_calls_log.
    """

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
    tools = anthropic_tool_defs(tool_specs) if tool_specs else None

    t0 = time.perf_counter()
    if client is None:
        parsed = _mock_parse(agent, output_model, state)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        response_text = parsed.model_dump_json()
        meta = {
            "input_tokens": 0,
            "output_tokens": 0,
            "latency_ms": latency_ms,
            "response_text": response_text,
            "tool_calls_log": [],
            "raw_message_repr": response_text,
        }
        return parsed, meta

    kwargs: dict[str, Any] = {
        "max_tokens": max_tokens,
        "model": model,
        "system": system,
        "messages": [{"role": "user", "content": user_text}],
        "output_format": output_model,
    }
    if tools:
        kwargs["tools"] = tools
    parsed_msg = client.messages.parse(**kwargs)
    latency_ms = int((time.perf_counter() - t0) * 1000)
    usage = getattr(parsed_msg, "usage", None)
    in_tok = getattr(usage, "input_tokens", 0) if usage else 0
    out_tok = getattr(usage, "output_tokens", 0) if usage else 0
    parsed = _parsed_output(parsed_msg)
    if parsed is None:
        raise RuntimeError("Claude response had no parsed structured output")
    response_text = _content_to_text(parsed_msg)
    tool_calls_log = _extract_tool_calls(parsed_msg)
    meta = {
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "latency_ms": latency_ms,
        "response_text": response_text,
        "tool_calls_log": tool_calls_log,
        "raw_message_repr": response_text[:20000],
    }
    return parsed, meta


def _extract_tool_calls(parsed_message: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for block in getattr(parsed_message, "content", []) or []:
        if getattr(block, "type", None) == "tool_use":
            out.append(
                {
                    "name": getattr(block, "name", ""),
                    "input": getattr(block, "input", {}),
                    "output": None,
                }
            )
    return out


def _mock_parse(agent: AgentConfig, output_model: type[BaseModel], state: BaseModel) -> BaseModel:
    """Deterministic stub when no API key (tests and local demos)."""

    data = state.model_dump()
    if output_model.__name__ == "GreeterOutput":
        task = str(data.get("task", "world"))
        return output_model(greeting=f"Hello, {task}!")  # type: ignore[call-arg]
    if output_model.__name__ == "SummarizerOutput":
        g = data.get("greeting") or "nothing"
        return output_model(summary=f"Acknowledged: {g}")  # type: ignore[call-arg]
    raise NotImplementedError(f"No mock for output schema {output_model.__name__}")


def anthropic_client_from_env() -> Anthropic | None:
    import os

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    return Anthropic(api_key=key)
