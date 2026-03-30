import tempfile
from pathlib import Path

from olympus.athena_conditions import register_athena_conditions
from olympus.athena_state import GapRegister, register_athena_schemas
from olympus.athena_tools import register_athena_tools
from olympus.pipeline import run_pipeline
from olympus.run_store import RunStore
from olympus.schema_registry import resolve_state_schema


def test_athena_conditions_mutually_exclusive():
    register_athena_schemas()
    register_athena_conditions()
    from olympus.athena_state import AthenaPipelineState
    from olympus.conditions import eval_condition

    s_ok = AthenaPipelineState(
        gap_register=GapRegister(summary="x", gap_count=1, gaps=[]),
    )
    s_bad = AthenaPipelineState(
        gap_register=GapRegister(summary="x", gap_count=9, gaps=[]),
    )
    assert eval_condition("standing_knowledge_sufficient", s_ok)
    assert not eval_condition("standing_knowledge_insufficient", s_ok)
    assert not eval_condition("standing_knowledge_sufficient", s_bad)
    assert eval_condition("standing_knowledge_insufficient", s_bad)


def test_athena_full_pipeline_mock():
    register_athena_schemas()
    register_athena_tools()
    register_athena_conditions()

    examples = Path(__file__).resolve().parent.parent / "examples" / "athena"
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "runs.sqlite"
        state_cls = resolve_state_schema("AthenaPipelineState")
        initial = state_cls(
            user_story="Add validation to checkout",
            acceptance_criteria=["Invalid input returns 400"],
            repo_path=str(examples),
        )
        final, run_id = run_pipeline(
            pipeline_path=examples / "pipeline.yaml",
            agents_dir=examples / "agents",
            initial_state=initial,
            db_path=db,
            register_athena=False,
        )

        assert final.context_package is not None
        assert final.context_package.title
        assert final.package_score is not None
        store = RunStore(db)
        calls = store.list_agent_calls(run_id)
        assert len(calls) == 9
        agents = {c.agent_name for c in calls}
        assert agents == {
            "lethe",
            "iris",
            "pallas",
            "asclepius",
            "daedalus",
            "nike",
            "tyche",
            "arete",
            "athena",
        }
        retries = [c for c in calls if c.retry_count > 0]
        assert not retries
