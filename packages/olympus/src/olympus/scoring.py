"""Default scoring from agent YAML `scoring` block."""

from __future__ import annotations

from pydantic import BaseModel

from olympus.models_config import AgentConfig


def score_agent_output(agent: AgentConfig, parsed: BaseModel) -> tuple[float, str]:
    """
    Return (score, feedback). Sprint 0: optional `completeness_check` containing
    "nonempty" penalizes empty/null fields; otherwise 1.0 if parsing succeeded.
    """

    rules = agent.scoring
    feedback_parts: list[str] = []
    score = 1.0
    check = (rules.completeness_check or "").lower()
    if "nonempty" in check:
        for field_name, val in parsed.model_dump().items():
            if val is None or val == "":
                score = min(score, 0.4)
                feedback_parts.append(f"empty:{field_name}")
    fb = "; ".join(feedback_parts) if feedback_parts else "ok"
    if score < rules.min_score:
        fb = f"{fb} (below min_score {rules.min_score})"
    return score, fb
