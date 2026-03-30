"""Conditional edges for the Athena pipeline graph."""

from __future__ import annotations

from pydantic import BaseModel

from olympus.conditions import register_condition


def register_athena_conditions() -> None:
    from olympus.conditions import CONDITION_REGISTRY

    if "standing_knowledge_sufficient" in CONDITION_REGISTRY:
        return

    def standing_knowledge_sufficient(state: BaseModel) -> bool:
        d = state.model_dump()
        gaps = d.get("gap_register")
        if not isinstance(gaps, dict):
            return True
        return int(gaps.get("gap_count", 0)) <= 2

    def standing_knowledge_insufficient(state: BaseModel) -> bool:
        return not standing_knowledge_sufficient(state)

    register_condition("standing_knowledge_sufficient", standing_knowledge_sufficient)
    register_condition("standing_knowledge_insufficient", standing_knowledge_insufficient)
