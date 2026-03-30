# Olympus Agent Framework

**Olympus** is the shared agent runtime for the Automated Agile product family: **YAML-defined agents**, **LangGraph** orchestration, **Claude** (Anthropic) with optional **tool loops**, **append-only run logs**, and a **Tuning Studio** (FastAPI + React) for editing configs and inspecting runs—matching the intent of the [Olympus architecture (PDF)](docs/olympus-framework-architecture.pdf) (v1.0, March 2026).

This repository implements the phased plan in [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md). The sections below give a **full accounting of what is built versus that plan**, what you can do with it today, and what remains optional or future work.

---

## Repository layout

| Path | Role |
|------|------|
| [`packages/olympus`](packages/olympus) | Python package **`olympus`** (runtime, CLI, Tuning Studio API). Version **0.4.x**. |
| [`packages/tuning-ui`](packages/tuning-ui) | **Tuning Studio** frontend (Vite + React + TypeScript). |
| [`docs/`](docs) | Architecture PDF, build plan, and design references. |
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | CI: Ruff + pytest for `olympus`, `npm run build` for `tuning-ui`. |

---

## Plan vs implementation

The architecture’s four pillars and how this repo delivers them:

| Architecture goal | In this repo |
|---------------------|--------------|
| **Agent-as-config** | Agents are YAML files under `examples/*/agents/`; validated with Pydantic (`AgentConfig`). Tuning Studio can create **new prompt/config versions** in SQLite without editing files; API runs merge current versions into the graph. |
| **Automatic observability** | Every agent node writes an **append-only** row to `agent_calls` (prompt, response, tools, tokens, latency, score, retry count). Runs table + optional `run_events` for live UI. |
| **Feed-forward context** | Pipeline `state_schema` is a Pydantic model; each node merges typed `output_schema` into shared state. |
| **Tuning Studio API** | FastAPI in `olympus.api`: REST + **WebSocket** `/runs/{run_id}/live`; OpenAPI at `/docs`. React UI in `packages/tuning-ui`. |

### Phase 0 — Repository and tooling

| Item | Status |
|------|--------|
| Python **3.11+**, `packages/olympus` | Done |
| **uv** + lockfile | Done |
| CI (lint, tests, UI build) | Done |
| `ANTHROPIC_API_KEY`; local Chroma + SQLite | Done |

### Sprint 0 — Olympus core

| Item | Status | Notes |
|------|--------|--------|
| Agent / pipeline YAML + Pydantic | Done | `loader.py`, `models_config.py` |
| LangGraph `StateGraph` from YAML | Done | `graph_builder.py` |
| Conditional edges | Done | Named conditions in `conditions.py` / `athena_conditions.py`; mixed conditional + unconditional from one node not supported |
| `@tool` + Anthropic tool defs | Done | `tools.py` |
| Claude **structured output** + optional **tool loop** | Done | `claude_runner.py`; mock path when API key unset |
| Scoring + retries (`escalate_prompt`, etc.) | Done | `widen_retrieval` / `flag_human` are prompt-level only |
| SQLite run log | Done | `run_store.py`; feedback rows supported |
| Demo pipeline | Done | `examples/demo/` |

### Sprint 1 — Lethe

| Item | Status | Notes |
|------|--------|--------|
| Chroma + sentence-transformers | Done | `indexing.py` |
| Chonkie + tree-sitter (+ fallbacks, skips) | Done | Skips `.venv`, `node_modules`, etc. |
| Merkle root for incremental index | Done | `merkle.py` |
| `read_file`, `search_index`, `get_git_history` | Done | `lethe_tools.py` + tool context |
| Lethe agent + pipeline example | Done | `examples/lethe/` |

### Sprint 2 — Athena (Repo Analyser slice)

| Item | Status | Notes |
|------|--------|--------|
| Eight heroes + orchestrator YAML | Done | `examples/athena/` (nine agent files + `pipeline.yaml`) |
| `AthenaPipelineState` + outputs | Done | `athena_state.py` |
| `standing_knowledge_*` condition | Done | `athena_conditions.py` |
| `ContextPackage` / orchestrator | Done | Mock + real API paths |
| Product tool surface for heroes | **Stubs** | `athena_tools.py` defers to Lethe for overlapping names when registered |
| Full Iris/Pallas “real” tools | Not product-complete | Stubs + Lethe trio where wired |

### Tuning Studio (final phase in plan)

| Item | Status | Notes |
|------|--------|--------|
| REST: agents, pipelines, runs, feedback | Done | See **API surface** below |
| Isolation test `POST /agents/{name}/test` | Done | |
| Experiments + promote | Done | Store + rollback winner; **no auto dual-run executor** |
| Performance aggregates | Done | Basic rollups from SQLite |
| WebSocket live runs | Done | Polls `run_events`; use `OLYMPUS_STUDIO=1` on CLI for same DB |
| React UI | Done | Minimal: agents, runs, demo run, feedback sample, live stream |
| **MCP server** for context packages | **Not built** | Optional in plan |

### Explicit non-goals (architecture)

Still respected: no cloud execution of customer source for indexing; no LLM fine-tuning; no agent self-modification; no dynamic agent creation; no shared mutable state across unrelated pipelines.

---

## What you can do today (capabilities)

### Run pipelines from the CLI

- **Demo** (two nodes, mock-friendly): `--register-demo`, `examples/demo/pipeline.yaml`.
- **Lethe** (index + tools): `--register-lethe --index-repo`, `examples/lethe/`.
- **Athena** (full graph, mocks without API key): `--register-athena`, `examples/athena/`.
- Combine **Lethe + Athena** so overlapping tools use real implementations: register Lethe before Athena in code or ensure Lethe tools are loaded first.

### Run the Tuning Studio

1. **API** (from `packages/olympus`):

   ```bash
   uv sync --extra dev
   uv run olympus-studio --port 8765
   ```

   Open **http://127.0.0.1:8765/docs** for OpenAPI.

2. **UI** (from `packages/tuning-ui`):

   ```bash
   npm install
   npm run dev
   ```

   Vite proxies `/api` and `/ws` to the API.

3. **CLI runs + live events**: use the **same** SQLite path as the server and `OLYMPUS_STUDIO=1` so `run_started`, `run_completed`, and per-node events are written for the WebSocket.

### API surface (high level)

Aligned with the architecture doc’s Tuning Studio section:

- **Agents:** `GET/PUT` list, detail, versions, prompt, config, rollback; `POST .../test`; performance + feedback slices.
- **Pipelines:** list, get YAML, put YAML; `POST /pipelines/{name}/run` with body flags (`register_demo`, `register_lethe`, `register_athena`, `index_repo`) and initial state.
- **Runs:** list, detail, call detail, feedback; **WebSocket** `/runs/{run_id}/live`.
- **Experiments:** create, get, promote (winner `version_id` in body).

---

## Quick start commands

```bash
# Install runtime + dev tools
cd packages/olympus && uv sync --extra dev

# Unit tests (includes API tests with TestClient)
uv run pytest -q
uv run ruff check src tests
```

**Demo pipeline**

```bash
uv run olympus run --register-demo \
  --pipeline examples/demo/pipeline.yaml \
  --agents examples/demo/agents
```

**Lethe** (first sync may download embedding weights)

```bash
uv run olympus run --register-lethe --index-repo \
  --pipeline examples/lethe/pipeline.yaml \
  --agents examples/lethe/agents \
  --repo-path . \
  --chroma-path /tmp/olympus_chroma
```

**Athena slice**

```bash
uv run olympus run --register-athena \
  --pipeline examples/athena/pipeline.yaml \
  --agents examples/athena/agents \
  --user-story "Your change" \
  --repo-path .
```

With **`ANTHROPIC_API_KEY`**, Claude runs with tool loops where configured; without it, **deterministic mocks** keep CI and local demos fast.

---

## Environment variables

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Real Claude calls; omit for mocks in tests/demos. |
| `OLYMPUS_STUDIO=1` | When set, `olympus run` attaches a `StudioStore` and writes **run_events** (for WebSocket) to the configured SQLite DB. |
| `OLYMPUS_MODEL` | Optional override for default Claude model (used by `olympus-studio`). |

---

## Technology stack (as implemented)

| Layer | Technology |
|-------|------------|
| Runtime | Python 3.11+ |
| Orchestration | LangGraph |
| LLM | Anthropic Claude (`messages.parse`, tool loop via `messages.create`) |
| Vector / local search | ChromaDB, sentence-transformers |
| Chunking | Chonkie, tree-sitter, Merkle directory hash |
| Config / state | YAML + Pydantic |
| Persistence | SQLite (runs, calls, feedback, studio versions, run_events) |
| API | FastAPI, Uvicorn, WebSocket |
| UI | React, TypeScript, Vite |
| Packaging | uv |

**PostgreSQL** for runs is listed in the plan as a later option; the code is still SQLite-first.

---

## Known limitations (honest scope)

- **Tool loop** is implemented for the Anthropic path; edge cases (very long tool chains, provider limits) may need tuning in production.
- **Athena hero tools** are largely **stubs**; full product depth is “YAML + tools” growth on top of the framework.
- **Experiments** persist metadata; **automatic A/B execution and scoring** is not a full product workflow yet.
- **MCP server** for context packages is **not** in this repo.
- **ADO platform** eight agents / sub-pipeline linking is **out of scope** for this repository (framework only).
- **Conditional routing:** one node cannot mix unconditional and conditional outgoing edges in the current builder (documented in package README).

---

## Documentation index

| Document | Contents |
|----------|----------|
| [docs/olympus-framework-architecture.pdf](docs/olympus-framework-architecture.pdf) | Canonical product architecture |
| [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md) | Phased plan + pointers to code |
| [packages/olympus/README.md](packages/olympus/README.md) | Package-focused usage and version notes |

---

## Contributing and quality

- **Branches:** develop on feature branches; default integration target is **`main`** per your workflow.
- **CI:** see [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

If you extend agents or state types, register schemas with `olympus.schema_registry` (or the existing `register_*` helpers) before running pipelines that reference them.
