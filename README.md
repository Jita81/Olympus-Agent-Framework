# Olympus Agent Framework

**Olympus** is the shared agent runtime for the Automated Agile product family: **YAML-defined agents**, **LangGraph** orchestration, **Claude** (Anthropic) with optional **tool loops**, and **append-only run logs**—matching the intent of the [Olympus architecture (PDF)](docs/olympus-framework-architecture.pdf) (v1.0, March 2026).

This repository implements the phased plan in [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md). The sections below give a **full accounting of what is built versus that plan** on the default branch, what you can do today, and what lives on follow-up branches or remains future work.

---

## Repository layout

| Path | Role |
|------|------|
| [`packages/olympus`](packages/olympus) | Python package **`olympus`** — runtime, `olympus` CLI, tests. **v0.3.0** on `main`. |
| [`docs/`](docs) | Architecture PDF, build plan, and design references. |
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | CI: Ruff + pytest for `packages/olympus`. |

**Tuning Studio** (FastAPI + SQLite-backed config versions + React UI) is implemented on branch **`cursor/tuning-studio`** (pending merge to `main`). After merge, `packages/tuning-ui` and `olympus-studio` appear here; CI also builds the UI.

---

## Plan vs implementation

The architecture’s four pillars and how **`main`** delivers them today:

| Architecture goal | On `main` today |
|-------------------|-----------------|
| **Agent-as-config** | Agents are YAML under `examples/*/agents/`, validated with Pydantic (`AgentConfig`). |
| **Automatic observability** | Every agent node appends a row to **`agent_calls`** (prompt, response, tools, tokens, latency, score, retry count). **`runs`** + optional **`feedback`**. |
| **Feed-forward context** | Pipeline `state_schema` is a Pydantic model; each node merges typed `output_schema` into shared state. |
| **Tuning Studio API** | Spec’d in the PDF; **full REST + WebSocket + UI on branch `cursor/tuning-studio`** (not yet on `main`). |

### Phase 0 — Repository and tooling

| Item | Status |
|------|--------|
| Python **3.11+**, `packages/olympus` | Done |
| **uv** + lockfile | Done |
| CI (lint, tests) | Done |
| `ANTHROPIC_API_KEY`; local Chroma + SQLite | Done |

### Sprint 0 — Olympus core

| Item | Status | Notes |
|------|--------|--------|
| Agent / pipeline YAML + Pydantic | Done | `loader.py`, `models_config.py` |
| LangGraph `StateGraph` from YAML | Done | `graph_builder.py` |
| Conditional edges | Done | `conditions.py` / `athena_conditions.py`; mixed conditional + unconditional from one node not supported |
| `@tool` + Anthropic tool defs | Done | `tools.py` |
| Claude **structured output** + optional **tool loop** | Done | `claude_runner.py`; mock path when API key unset |
| Scoring + retries | Done | `widen_retrieval` / `flag_human` are prompt-level only |
| SQLite run log | Done | `run_store.py`; feedback supported |
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
| Eight heroes + orchestrator YAML | Done | `examples/athena/` |
| `AthenaPipelineState` + outputs | Done | `athena_state.py` |
| `standing_knowledge_*` condition | Done | `athena_conditions.py` |
| `ContextPackage` / orchestrator | Done | Mock + real API paths |
| Product tool surface for heroes | **Stubs** | `athena_tools.py`; overlaps defer to Lethe when registered |
| Full Iris/Pallas “real” tools | Not product-complete | Stubs + Lethe trio where wired |

### Tuning Studio (final phase in plan)

| Item | On `main` | On `cursor/tuning-studio` (merge pending) |
|------|-----------|------------------------------------------|
| REST: agents, pipelines, runs, feedback | — | Done (`olympus.api`, `studio_store`) |
| Isolation test, experiments, promote, performance | — | Done |
| WebSocket `/runs/{id}/live`, `run_events` | — | Done |
| `olympus-studio` CLI, `OLYMPUS_STUDIO=1` | — | Done |
| React UI (`packages/tuning-ui`) | — | Done |
| CI: `npm run build` for UI | — | Done |
| **MCP server** | — | **Not built** (optional in plan) |

### Explicit non-goals (architecture)

Still respected: no cloud execution of customer source for indexing; no LLM fine-tuning; no agent self-modification; no dynamic agent creation; no shared mutable state across unrelated pipelines.

---

## What you can do today (on `main`)

### Run pipelines from the CLI

- **Demo:** `--register-demo`, `examples/demo/pipeline.yaml`.
- **Lethe:** `--register-lethe --index-repo`, `examples/lethe/`.
- **Athena:** `--register-athena`, `examples/athena/` (mocks without API key).
- Register **Lethe before Athena** when you want real `read_file` / `search_index` / `get_git_history` instead of stubs for overlapping names.

### Inspect runs

```bash
uv run olympus show-run <run_id>
```

### After Tuning Studio merges

You will run **`uv run olympus-studio`**, open **`/docs`**, and use **`packages/tuning-ui`** with Vite dev proxy—see that branch’s `packages/olympus/README.md` for exact commands.

---

## Quick start (`main`)

```bash
cd packages/olympus && uv sync --extra dev
uv run pytest -q
uv run ruff check src tests
```

**Demo pipeline**

```bash
uv run olympus run --register-demo \
  --pipeline examples/demo/pipeline.yaml \
  --agents examples/demo/agents
```

**Lethe** (first run may download embedding weights)

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

## Environment variables (`main`)

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Real Claude calls; omit for mocks in tests/demos. |

*(After Tuning Studio merge: `OLYMPUS_STUDIO`, `OLYMPUS_MODEL`, and `olympus-studio` — see merged README / package docs.)*

---

## Technology stack (as on `main`)

| Layer | Technology |
|-------|------------|
| Runtime | Python 3.11+ |
| Orchestration | LangGraph |
| LLM | Anthropic Claude |
| Vector / local search | ChromaDB, sentence-transformers |
| Chunking | Chonkie, tree-sitter, Merkle directory hash |
| Config / state | YAML + Pydantic |
| Persistence | SQLite (runs, calls, feedback) |
| Packaging | uv |

**Planned with Tuning Studio merge:** FastAPI, Uvicorn, WebSocket, React (Vite). **PostgreSQL** for runs remains a future option per the plan.

---

## Known limitations (honest scope)

- **Tool loop** — Implemented for Anthropic; long chains / limits may need production tuning.
- **Athena** — Hero tools are largely **stubs**; depth grows via YAML + new tool modules.
- **Experiments** — Full A/B automation not product-complete until Studio branch semantics land on `main`.
- **MCP server** — Not in this repo (optional in architecture).
- **ADO platform** agents / sub-pipeline linking — Out of scope here.
- **Graph builder** — Cannot mix unconditional and conditional outgoing edges from the same node (see package README).

---

## Documentation index

| Document | Contents |
|----------|----------|
| [docs/olympus-framework-architecture.pdf](docs/olympus-framework-architecture.pdf) | Canonical product architecture |
| [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md) | Phased plan + code pointers |
| [packages/olympus/README.md](packages/olympus/README.md) | Package usage and sprint notes |

---

## Contributing

Develop on feature branches; integrate via PRs to **`main`**. CI: [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

Register new `state_schema` / `output_schema` names with `olympus.schema_registry` (or `register_*` helpers) before running pipelines that reference them.
