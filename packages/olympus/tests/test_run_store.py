import tempfile
from pathlib import Path

from olympus.run_store import RunStore


def test_append_only_calls():
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "t.sqlite"
        store = RunStore(db)
        rid = store.start_run(
            pipeline_name="demo",
            pipeline_version="1.0.0",
            input_payload={"task": "x"},
        )
        store.append_agent_call(
            run_id=rid,
            agent_name="a",
            agent_version="1",
            node_id="n1",
            prompt_full="p",
            response_full="r",
            tool_calls=[],
            input_tokens=1,
            output_tokens=2,
            latency_ms=3,
            score=0.9,
            score_feedback="ok",
            retry_count=0,
        )
        store.complete_run(rid, overall_score=0.9)
        run = store.get_run(rid)
        assert run is not None
        assert run.completed_at is not None
        assert len(store.list_agent_calls(rid)) == 1
