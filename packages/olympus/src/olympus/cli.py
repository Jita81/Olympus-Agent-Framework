"""CLI entrypoint for Sprint 0 demo pipeline runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from olympus.conditions import default_demo_conditions
from olympus.pipeline import run_pipeline
from olympus.run_store import RunStore
from olympus.schema_registry import default_demo_schemas, resolve_state_schema


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="olympus", description="Olympus agent framework CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Run a pipeline YAML once")
    run_p.add_argument(
        "--pipeline",
        type=Path,
        required=True,
        help="Path to pipeline YAML",
    )
    run_p.add_argument(
        "--agents",
        type=Path,
        required=True,
        help="Directory of agent YAML files",
    )
    run_p.add_argument(
        "--task",
        default="Sprint 0",
        help="Initial `task` field for DemoPipelineState (demo default)",
    )
    run_p.add_argument(
        "--model",
        default="claude-sonnet-4-20250514",
        help="Claude model id",
    )
    run_p.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite path for run log (default: ./.olympus/runs.sqlite)",
    )
    run_p.add_argument(
        "--register-demo",
        action="store_true",
        help="Register built-in DemoPipelineState / demo conditions (Sprint 0 demo)",
    )

    show_p = sub.add_parser("show-run", help="Print run and agent calls from SQLite")
    show_p.add_argument("run_id", type=str)
    show_p.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite path (default: ./.olympus/runs.sqlite)",
    )

    args = parser.parse_args(argv)

    if args.cmd == "run":
        if args.register_demo:
            default_demo_schemas()
            default_demo_conditions()
        from olympus.loader import load_pipeline

        pipeline_path = args.pipeline
        pcfg = load_pipeline(pipeline_path)
        state_cls = resolve_state_schema(pcfg.state_schema)
        initial = state_cls(task=args.task)

        final, run_id = run_pipeline(
            pipeline_path=pipeline_path,
            agents_dir=args.agents,
            initial_state=initial,
            model=args.model,
            db_path=args.db,
            register_demo=False,
        )
        print(json.dumps({"run_id": run_id, "final_state": final.model_dump()}, indent=2))
        return 0

    if args.cmd == "show-run":
        from olympus.runtime_context import default_sqlite_path

        db = args.db or default_sqlite_path()
        store = RunStore(db)
        run = store.get_run(args.run_id)
        if run is None:
            print(f"Unknown run_id: {args.run_id}", file=sys.stderr)
            return 1
        calls = store.list_agent_calls(args.run_id)
        out = {
            "run": {
                "run_id": run.run_id,
                "pipeline": f"{run.pipeline_name}@{run.pipeline_version}",
                "started_at": run.started_at,
                "completed_at": run.completed_at,
                "overall_score": run.overall_score,
                "input": run.input_payload,
            },
            "agent_calls": [
                {
                    "call_id": c.call_id,
                    "agent": f"{c.agent_name}@{c.agent_version}",
                    "node_id": c.node_id,
                    "score": c.score,
                    "score_feedback": c.score_feedback,
                    "retry_count": c.retry_count,
                    "latency_ms": c.latency_ms,
                    "input_tokens": c.input_tokens,
                    "output_tokens": c.output_tokens,
                }
                for c in calls
            ],
        }
        print(json.dumps(out, indent=2))
        return 0

    return 1
