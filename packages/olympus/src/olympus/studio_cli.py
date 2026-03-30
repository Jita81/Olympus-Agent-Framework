"""CLI for Tuning Studio API server."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from olympus.api import AppSettings, create_app
from olympus.runtime_context import default_sqlite_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="olympus-studio", description="Olympus Tuning Studio API")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite path (default: ./.olympus/runs.sqlite)",
    )
    p.add_argument(
        "--agents-dir",
        type=Path,
        default=None,
        help="Agent YAML directory (default: ./examples/demo/agents from cwd)",
    )
    p.add_argument(
        "--pipelines-dir",
        type=Path,
        default=None,
        help="Root to scan for pipeline.yaml (default: ./examples)",
    )
    p.add_argument(
        "--model",
        default=os.environ.get("OLYMPUS_MODEL", "claude-sonnet-4-20250514"),
    )
    args = p.parse_args(argv)

    root = Path.cwd()
    db = args.db or default_sqlite_path(root)
    agents = args.agents_dir or (root / "examples" / "demo" / "agents")
    pipes = args.pipelines_dir or (root / "examples")
    settings = AppSettings(db_path=db, agents_dir=agents, pipelines_dir=pipes, model=args.model)
    app = create_app(settings)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0
