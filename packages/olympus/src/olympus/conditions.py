"""Named pipeline edge conditions evaluated against current state (Pydantic)."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

ConditionFn = Callable[[BaseModel], bool]

CONDITION_REGISTRY: dict[str, ConditionFn] = {}


def register_condition(name: str, fn: ConditionFn) -> None:
    CONDITION_REGISTRY[name] = fn


def eval_condition(name: str, state: BaseModel) -> bool:
    try:
        fn = CONDITION_REGISTRY[name]
    except KeyError as e:
        raise KeyError(
            f"Unknown condition {name!r}. Registered: {sorted(CONDITION_REGISTRY)}"
        ) from e
    return fn(state)


def default_demo_conditions() -> None:
    """Predicates referenced by example pipelines (idempotent)."""

    def always(_state: BaseModel) -> bool:
        return True

    register_condition("always_continue", always)
