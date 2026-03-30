from pathlib import Path

import pytest

from olympus.loader import load_agents_dir, load_pipeline

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "demo"


def test_load_demo_pipeline():
    p = load_pipeline(EXAMPLES / "pipeline.yaml")
    assert p.name == "demo"
    assert p.state_schema == "DemoPipelineState"
    assert len(p.nodes) == 2


def test_load_agents_dir():
    agents = load_agents_dir(EXAMPLES / "agents")
    assert "demo-greeter" in agents
    assert agents["demo-greeter"].output_schema == "GreeterOutput"


def test_duplicate_agent_name_rejected(tmp_path):
    (tmp_path / "a.yaml").write_text("name: x\nsystem_prompt: s\noutput_schema: GreeterOutput\n")
    (tmp_path / "b.yaml").write_text("name: x\nsystem_prompt: t\noutput_schema: GreeterOutput\n")
    with pytest.raises(ValueError, match="Duplicate"):
        load_agents_dir(tmp_path)
