"""Tuning Studio HTTP API (FastAPI) + WebSocket live run stream."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from olympus.api_models import (
    ConfigBody,
    ExperimentBody,
    FeedbackBody,
    IsolationTestBody,
    PipelinePutBody,
    PromoteBody,
    PromptBody,
    RollbackBody,
    RunPipelineBody,
)
from olympus.claude_runner import anthropic_client_from_env, run_agent_turn
from olympus.loader import load_agent, load_pipeline
from olympus.pipeline import run_pipeline
from olympus.run_store import RunStore
from olympus.runtime_context import default_sqlite_path
from olympus.schema_registry import resolve_output_schema, resolve_state_schema
from olympus.studio_store import StudioStore


class AppSettings(BaseModel):
    """Resolved paths for the API process."""

    db_path: Path
    agents_dir: Path
    pipelines_dir: Path
    model: str = "claude-sonnet-4-20250514"


def create_app(settings: AppSettings | None = None) -> FastAPI:
    settings = settings or AppSettings(
        db_path=default_sqlite_path(),
        agents_dir=Path.cwd() / "examples" / "demo" / "agents",
        pipelines_dir=Path.cwd() / "examples",
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        from olympus.athena_conditions import register_athena_conditions
        from olympus.athena_state import register_athena_schemas
        from olympus.athena_tools import register_athena_tools
        from olympus.conditions import default_demo_conditions
        from olympus.schema_registry import default_demo_schemas, register_lethe_schemas

        default_demo_schemas()
        default_demo_conditions()
        register_lethe_schemas()
        register_athena_schemas()
        register_athena_tools()
        register_athena_conditions()
        yield

    app = FastAPI(
        title="Olympus Tuning Studio API",
        version="0.4.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def run_store() -> RunStore:
        return RunStore(settings.db_path)

    def studio_store() -> StudioStore:
        st = StudioStore(settings.db_path)
        st.sync_agents_from_disk(settings.agents_dir)
        for p in sorted(settings.pipelines_dir.rglob("*.yaml")):
            if p.parent.name == "agents":
                continue
            try:
                st.sync_pipeline_from_disk(p)
            except Exception:
                continue
        return st

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/agents")
    def list_agents(st: StudioStore = Depends(studio_store)) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for name in st.list_catalog_agent_names(settings.agents_dir):
            cur = st.get_agent_current(name)
            out.append(
                {
                    "name": name,
                    "current_version_id": cur.version_id if cur else None,
                    "yaml_version": cur.yaml_version if cur else None,
                }
            )
        return out

    @app.get("/agents/{name}")
    def get_agent(name: str, st: StudioStore = Depends(studio_store)) -> dict[str, Any]:
        cur = st.get_agent_current(name)
        if cur is None:
            raise HTTPException(404, f"Unknown agent {name!r}")
        return {
            "name": cur.agent_name,
            "version_id": cur.version_id,
            "yaml_version": cur.yaml_version,
            "system_prompt": cur.system_prompt,
            "config": cur.config_json,
            "source": cur.source,
        }

    @app.get("/agents/{name}/versions")
    def agent_versions(name: str, st: StudioStore = Depends(studio_store)) -> list[dict[str, Any]]:
        rows = st.list_agent_versions(name)
        if not rows:
            raise HTTPException(404, f"Unknown agent {name!r}")
        return [
            {
                "version_id": r.version_id,
                "created_at": r.created_at,
                "yaml_version": r.yaml_version,
                "source": r.source,
            }
            for r in rows
        ]

    @app.put("/agents/{name}/prompt")
    def put_prompt(
        name: str,
        prompt_body: PromptBody,
        st: StudioStore = Depends(studio_store),
    ) -> dict[str, str]:
        try:
            vid = st.update_agent_prompt(name, prompt_body.system_prompt)
        except KeyError:
            raise HTTPException(404, f"Unknown agent {name!r}")
        return {"version_id": vid}

    @app.put("/agents/{name}/config")
    def put_config(
        name: str,
        config_body: ConfigBody,
        st: StudioStore = Depends(studio_store),
    ) -> dict[str, str]:
        try:
            vid = st.update_agent_config(name, config_body.config)
        except KeyError:
            raise HTTPException(404, f"Unknown agent {name!r}")
        return {"version_id": vid}

    @app.post("/agents/{name}/rollback")
    def rollback(
        name: str,
        rollback_body: RollbackBody,
        st: StudioStore = Depends(studio_store),
    ) -> dict[str, str]:
        try:
            st.rollback_agent(name, rollback_body.version_id)
        except KeyError:
            raise HTTPException(404, "Unknown agent or version")
        return {"current_version_id": rollback_body.version_id}

    @app.get("/pipelines")
    def list_pipelines(st: StudioStore = Depends(studio_store)) -> list[dict[str, str]]:
        return [{"name": n} for n in st.list_pipeline_names()]

    @app.get("/pipelines/{name}")
    def get_pipeline(name: str, st: StudioStore = Depends(studio_store)) -> dict[str, Any]:
        body = None
        for p in sorted(settings.pipelines_dir.rglob("pipeline.yaml")):
            try:
                cfg = load_pipeline(p)
            except Exception:
                continue
            if cfg.name == name:
                yaml_body = st.get_pipeline_current_yaml(name)
                body = yaml_body if yaml_body is not None else p.read_text(encoding="utf-8")
                break
        if body is None:
            body = st.get_pipeline_current_yaml(name)
        if body is None:
            raise HTTPException(404, f"Unknown pipeline {name!r}")
        return {"name": name, "yaml": body}

    @app.put("/pipelines/{name}")
    def put_pipeline(
        name: str,
        pipeline_body: PipelinePutBody,
        st: StudioStore = Depends(studio_store),
    ) -> dict[str, str]:
        vid = st.update_pipeline_yaml(name, pipeline_body.yaml)
        return {"version_id": vid}

    @app.get("/runs")
    def list_runs(
        store: RunStore = Depends(run_store),
        pipeline: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        rows = store.list_runs(limit=limit)
        if pipeline:
            rows = [r for r in rows if r.pipeline_name == pipeline]
        return [
            {
                "run_id": r.run_id,
                "pipeline": f"{r.pipeline_name}@{r.pipeline_version}",
                "started_at": r.started_at,
                "completed_at": r.completed_at,
                "overall_score": r.overall_score,
            }
            for r in rows
        ]

    @app.get("/runs/{run_id}")
    def get_run(run_id: str, store: RunStore = Depends(run_store)) -> dict[str, Any]:
        r = store.get_run(run_id)
        if r is None:
            raise HTTPException(404, "Unknown run")
        calls = store.list_agent_calls(run_id)
        return {
            "run": {
                "run_id": r.run_id,
                "pipeline_name": r.pipeline_name,
                "pipeline_version": r.pipeline_version,
                "input": r.input_payload,
                "started_at": r.started_at,
                "completed_at": r.completed_at,
                "overall_score": r.overall_score,
            },
            "agent_calls": [
                {
                    "call_id": c.call_id,
                    "agent": c.agent_name,
                    "node_id": c.node_id,
                    "score": c.score,
                    "retry_count": c.retry_count,
                    "latency_ms": c.latency_ms,
                }
                for c in calls
            ],
        }

    @app.get("/runs/{run_id}/calls/{call_id}")
    def get_call(run_id: str, call_id: str, store: RunStore = Depends(run_store)) -> dict[str, Any]:
        c = store.get_agent_call(run_id, call_id)
        if c is None:
            raise HTTPException(404, "Unknown call")
        return {
            "call_id": c.call_id,
            "agent": c.agent_name,
            "node_id": c.node_id,
            "prompt_full": c.prompt_full,
            "response_full": c.response_full,
            "tool_calls": c.tool_calls_json,
            "input_tokens": c.input_tokens,
            "output_tokens": c.output_tokens,
            "latency_ms": c.latency_ms,
            "score": c.score,
            "score_feedback": c.score_feedback,
            "retry_count": c.retry_count,
            "timestamp": c.timestamp,
        }

    @app.post("/runs/{run_id}/feedback")
    def post_feedback(
        run_id: str,
        feedback_body: FeedbackBody,
        store: RunStore = Depends(run_store),
    ) -> dict[str, str]:
        r = store.get_run(run_id)
        if r is None:
            raise HTTPException(404, "Unknown run")
        fb = feedback_body.model_dump()
        fid = store.append_feedback(run_id=run_id, payload=fb)
        return {"feedback_id": fid}

    @app.websocket("/runs/{run_id}/live")
    async def ws_live(websocket: WebSocket, run_id: str) -> None:
        await websocket.accept()
        st = studio_store()
        last = -1
        try:
            while True:
                events = st.list_run_events(run_id, after_seq=last)
                for ev in events:
                    last = max(last, ev["seq"])
                    await websocket.send_json(ev)
                await asyncio.sleep(0.4)
        except WebSocketDisconnect:
            return

    @app.post("/agents/{name}/test")
    def isolation_test(
        name: str,
        test_body: IsolationTestBody,
        st: StudioStore = Depends(studio_store),
    ) -> dict[str, Any]:
        path = settings.agents_dir / f"{name}.yaml"
        if not path.is_file():
            for p in settings.agents_dir.glob("*.yaml"):
                try:
                    if load_agent(p).name == name:
                        path = p
                        break
                except Exception:
                    continue
        if not path.is_file():
            raise HTTPException(404, f"No agent file for {name!r}")
        agent_disk = load_agent(path)
        merged = st.merge_agent_configs({agent_disk.name: agent_disk})
        agent = merged[agent_disk.name]
        out_name = agent.output_schema
        output_model = resolve_output_schema(out_name)
        schema_name = test_body.state_schema or agent.input_schema or "DemoPipelineState"
        try:
            state_model = resolve_state_schema(schema_name)
        except KeyError as e:
            raise HTTPException(400, f"Unknown state_schema: {e}") from e
        state = state_model.model_validate(test_body.state or {"task": "isolation"})
        client = anthropic_client_from_env()
        from olympus.tools import resolve_tools

        tool_specs = resolve_tools(agent.tools)
        parsed, meta = run_agent_turn(
            client,
            agent=agent,
            state=state,
            output_model=output_model,
            tool_specs=tool_specs,
            model=settings.model,
        )
        return {
            "output": parsed.model_dump(),
            "meta": {k: meta[k] for k in ("latency_ms",) if k in meta},
        }

    @app.post("/experiments")
    def create_experiment(
        experiment_body: ExperimentBody,
        st: StudioStore = Depends(studio_store),
    ) -> dict[str, str]:
        eid = st.create_experiment(
            experiment_body.agent_name,
            {
                "config_a_version_id": experiment_body.config_a_version_id,
                "config_b_version_id": experiment_body.config_b_version_id,
                "input_state": experiment_body.input_state,
            },
        )
        return {"experiment_id": eid}

    @app.get("/experiments/{experiment_id}")
    def get_experiment(
        experiment_id: str, st: StudioStore = Depends(studio_store)
    ) -> dict[str, Any]:
        row = st.get_experiment(experiment_id)
        if row is None:
            raise HTTPException(404, "Unknown experiment")
        return row

    @app.post("/experiments/{experiment_id}/promote")
    def promote_experiment(
        experiment_id: str,
        promote_body: PromoteBody,
        st: StudioStore = Depends(studio_store),
    ) -> dict[str, str]:
        row = st.get_experiment(experiment_id)
        if row is None:
            raise HTTPException(404, "Unknown experiment")
        agent_name = row["agent_name"]
        st.rollback_agent(agent_name, promote_body.winner_version_id)
        return {"current_version_id": promote_body.winner_version_id}

    @app.get("/agents/{name}/performance")
    def agent_performance(name: str, store: RunStore = Depends(run_store)) -> dict[str, Any]:
        calls: list[dict[str, Any]] = []
        for run in store.list_runs(limit=200):
            for c in store.list_agent_calls(run.run_id):
                if c.agent_name == name:
                    calls.append(
                        {
                            "run_id": run.run_id,
                            "score": c.score,
                            "latency_ms": c.latency_ms,
                            "input_tokens": c.input_tokens,
                            "output_tokens": c.output_tokens,
                        }
                    )
        scores = [c["score"] for c in calls if c["score"] is not None]
        avg = sum(scores) / len(scores) if scores else None
        return {"agent": name, "call_count": len(calls), "avg_score": avg, "recent": calls[:20]}

    @app.get("/agents/{name}/feedback")
    def agent_feedback(name: str, store: RunStore = Depends(run_store)) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for run in store.list_runs(limit=100):
            for fb in store.list_feedback(run.run_id):
                sections = fb["payload"].get("section_feedback") or []
                for s in sections:
                    if s.get("agent") == name:
                        out.append({"run_id": run.run_id, **s})
        return out

    @app.get("/pipelines/{name}/performance")
    def pipeline_performance(name: str, store: RunStore = Depends(run_store)) -> dict[str, Any]:
        runs = [r for r in store.list_runs(limit=200) if r.pipeline_name == name]
        scores = [r.overall_score for r in runs if r.overall_score is not None]
        avg = sum(scores) / len(scores) if scores else None
        return {"pipeline": name, "run_count": len(runs), "avg_overall_score": avg}

    @app.post("/pipelines/{name}/run")
    def http_run_pipeline(
        name: str,
        run_body: RunPipelineBody,
        st: StudioStore = Depends(studio_store),
    ) -> dict[str, Any]:
        pipeline_path: Path | None = None
        for p in sorted(settings.pipelines_dir.rglob("pipeline.yaml")):
            try:
                cfg = load_pipeline(p)
            except Exception:
                continue
            if cfg.name == name:
                pipeline_path = p
                break
        if pipeline_path is None:
            raise HTTPException(404, f"No pipeline file for {name!r}")
        cfg = st.resolve_pipeline_config(pipeline_path)
        agents_dir = pipeline_path.parent / "agents"
        if not agents_dir.is_dir():
            agents_dir = settings.agents_dir
        state_cls = resolve_state_schema(cfg.state_schema)
        initial = state_cls.model_validate(run_body.state)
        final, run_id = run_pipeline(
            pipeline_path=pipeline_path,
            agents_dir=agents_dir,
            initial_state=initial,
            model=settings.model,
            db_path=settings.db_path,
            register_demo=run_body.register_demo,
            register_lethe=run_body.register_lethe,
            register_athena=run_body.register_athena,
            index_repo=run_body.index_repo,
            studio_store=st,
        )
        return {"run_id": run_id, "final_state": final.model_dump()}

    return app
