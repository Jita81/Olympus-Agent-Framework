"""CLI entrypoint for Sprint 0 demo pipeline runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from olympus.conditions import default_demo_conditions
from olympus.pipeline import run_pipeline
from olympus.run_store import RunStore
from olympus.schema_registry import (
    default_demo_schemas,
    register_lethe_schemas,
    resolve_state_schema,
)


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
    run_p.add_argument(
        "--register-lethe",
        action="store_true",
        help="Register LethePipelineState / LetheOutput (Sprint 1)",
    )
    run_p.add_argument(
        "--register-athena",
        action="store_true",
        help="Register Athena pipeline state, hero outputs, stub tools, conditions (Sprint 2)",
    )
    run_p.add_argument(
        "--index-repo",
        action="store_true",
        help="Build Chroma index from repo_path in initial state before running agents",
    )
    run_p.add_argument(
        "--repo-path",
        type=Path,
        default=None,
        help="For Lethe / Athena: repository root (default: cwd)",
    )
    run_p.add_argument(
        "--user-story",
        default="Improve error handling in the API layer",
        help="For AthenaPipelineState: user_story field",
    )
    run_p.add_argument(
        "--acceptance-criteria",
        action="append",
        default=[],
        help="For Athena: acceptance criterion (repeat flag for multiple)",
    )
    run_p.add_argument(
        "--index-query",
        default="def main",
        help="For Lethe: default semantic search query seed in state",
    )
    run_p.add_argument(
        "--chroma-path",
        type=Path,
        default=None,
        help="Chroma persistence directory (default: next to SQLite under .olympus/)",
    )
    run_p.add_argument(
        "--embedding-model",
        default="all-MiniLM-L6-v2",
        help="sentence-transformers model id for indexing",
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
        if args.register_lethe:
            register_lethe_schemas()
        from olympus.loader import load_pipeline

        pipeline_path = args.pipeline
        pcfg = load_pipeline(pipeline_path)
        state_cls = resolve_state_schema(pcfg.state_schema)
        if pcfg.state_schema == "LethePipelineState":
            rp = (args.repo_path or Path.cwd()).resolve()
            initial = state_cls(repo_path=str(rp), index_query=args.index_query)
        elif pcfg.state_schema == "AthenaPipelineState":
            rp = (args.repo_path or Path.cwd()).resolve()
            ac = (
                list(args.acceptance_criteria)
                if args.acceptance_criteria
                else ["Errors are logged"]
            )
            initial = state_cls(
                user_story=args.user_story,
                acceptance_criteria=ac,
                repo_path=str(rp),
            )
        else:
            initial = state_cls(task=args.task)

        final, run_id = run_pipeline(
            pipeline_path=pipeline_path,
            agents_dir=args.agents,
            initial_state=initial,
            model=args.model,
            db_path=args.db,
            register_demo=False,
            register_lethe=False,
            register_athena=args.register_athena,
            index_repo=args.index_repo,
            chroma_path=args.chroma_path,
            embedding_model=args.embedding_model,
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
