import tempfile
from pathlib import Path

import pytest

from olympus.conditions import default_demo_conditions
from olympus.pipeline import run_pipeline
from olympus.run_store import RunStore
from olympus.schema_registry import default_demo_schemas, resolve_state_schema


@pytest.fixture
def one_node_demo(tmp_path):
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "solo.yaml").write_text(
        """
name: solo
version: "1.0.0"
system_prompt: "You are solo."
tools: []
output_schema: GreeterOutput
scoring:
  min_score: 0.99
  completeness_check: "nonempty"
""",
        encoding="utf-8",
    )
    (tmp_path / "pipe.yaml").write_text(
        """
name: retry-test
version: "1.0.0"
state_schema: DemoPipelineState
nodes:
  - agent: solo
    id: only
edges: []
retry:
  max_retries: 1
  strategy: escalate_prompt
""",
        encoding="utf-8",
    )
    return tmp_path


def test_retry_second_attempt_succeeds(monkeypatch, one_node_demo):
    default_demo_schemas()
    default_demo_conditions()

    calls = {"n": 0}

    def fake_score(agent, parsed):
        calls["n"] += 1
        if calls["n"] == 1:
            return 0.2, "forced low for test"
        return 1.0, "ok"

    monkeypatch.setattr("olympus.node_executor.score_agent_output", fake_score)

    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        db = Path(f.name)
    try:
        state_cls = resolve_state_schema("DemoPipelineState")
        initial = state_cls(task="retry")
        final, run_id = run_pipeline(
            pipeline_path=one_node_demo / "pipe.yaml",
            agents_dir=one_node_demo / "agents",
            initial_state=initial,
            db_path=db,
            register_demo=False,
        )
        assert final.greeting
        store = RunStore(db)
        ac = store.list_agent_calls(run_id)
        assert len(ac) == 2
        assert ac[0].retry_count == 0
        assert ac[0].score == pytest.approx(0.2)
        assert ac[1].retry_count == 1
        assert ac[1].score == pytest.approx(1.0)
    finally:
        db.unlink(missing_ok=True)
