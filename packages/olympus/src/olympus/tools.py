"""Register Python callables as Claude tools."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters_schema: dict[str, Any]
    fn: Callable[..., Any]

    model_config = {"arbitrary_types_allowed": True}


def _python_type_to_json_schema(annotation: Any) -> dict[str, Any]:
    if annotation is inspect.Parameter.empty:
        return {}
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Union:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _python_type_to_json_schema(non_none[0])
        return {"type": "string"}
    if origin is list:
        inner = args[0] if args else Any
        return {"type": "array", "items": _python_type_to_json_schema(inner)}
    if annotation is str:
        return {"type": "string"}
    if annotation is int:
        return {"type": "integer"}
    if annotation is float:
        return {"type": "number"}
    if annotation is bool:
        return {"type": "boolean"}
    return {"type": "string"}


def tool(*, name: str, description: str) -> Callable[[Callable[..., Any]], ToolSpec]:
    def decorator(fn: Callable[..., Any]) -> ToolSpec:
        sig = inspect.signature(fn)
        properties: dict[str, Any] = {}
        required: list[str] = []
        for param_name, param in sig.parameters.items():
            if param_name.startswith("_"):
                continue
            properties[param_name] = _python_type_to_json_schema(param.annotation)
            if param.default is inspect.Parameter.empty:
                required.append(param_name)
        schema: dict[str, Any] = {
            "type": "object",
            "properties": properties,
        }
        if required:
            schema["required"] = required
        return ToolSpec(name=name, description=description, parameters_schema=schema, fn=fn)

    return decorator


def anthropic_tool_defs(specs: list[ToolSpec]) -> list[dict[str, Any]]:
    """Anthropic Messages API tool definitions."""

    out: list[dict[str, Any]] = []
    for s in specs:
        out.append(
            {
                "name": s.name,
                "description": s.description,
                "input_schema": s.parameters_schema,
            }
        )
    return out


# Built-in stub tools for Sprint 0 demo (register names used in agent YAML).


@tool(
    name="noop_echo",
    description="Return a fixed acknowledgment (demo stub).",
)
def noop_echo(message: str = "") -> str:
    return "ok"


@tool(
    name="format_greeting",
    description="Build a short greeting string from a name (demo stub).",
)
def format_greeting(name: str) -> str:
    return f"Hello, {name}!"


TOOL_REGISTRY: dict[str, ToolSpec] = {
    noop_echo.name: noop_echo,
    format_greeting.name: format_greeting,
}


def resolve_tools(names: list[str]) -> list[ToolSpec]:
    missing = [n for n in names if n not in TOOL_REGISTRY]
    if missing:
        raise KeyError(f"Unknown tools: {missing}. Known: {sorted(TOOL_REGISTRY)}")
    return [TOOL_REGISTRY[n] for n in names]
