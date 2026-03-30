import tempfile
from pathlib import Path

from olympus.conditions import default_demo_conditions
from olympus.pipeline import run_pipeline
from olympus.run_store import RunStore
from olympus.schema_registry import default_demo_schemas, resolve_state_schema

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "demo"


def test_demo_pipeline_mocked_claude():
    default_demo_schemas()
    default_demo_conditions()
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "runs.sqlite"
        state_cls = resolve_state_schema("DemoPipelineState")
        initial = state_cls(task="Olympus")
        final, run_id = run_pipeline(
            pipeline_path=EXAMPLES / "pipeline.yaml",
            agents_dir=EXAMPLES / "agents",
            initial_state=initial,
            db_path=db,
            register_demo=False,
        )
        assert final.greeting is not None
        assert "Olympus" in final.greeting
        assert final.summary is not None
        store = RunStore(db)
        calls = store.list_agent_calls(run_id)
        assert len(calls) == 2
        assert all(c.score is not None for c in calls)
