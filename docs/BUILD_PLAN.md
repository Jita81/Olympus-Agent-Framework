# Olympus Agent Framework — Build Plan

This plan implements the architecture described in [olympus-framework-architecture.pdf](./olympus-framework-architecture.pdf) (Version 1.0, March 2026). It is ordered for incremental value: a runnable core first, then the first real agent (Lethe), then additional agents and the Tuning Studio.

## Goals (from the architecture)

- **Agent-as-config** — YAML definitions with Pydantic validation; no redeploy for prompt/config changes.
- **Automatic observability** — Every Claude call logged (prompt, response, tokens, latency, score hook).
- **Feed-forward context** — Typed pipeline state; each agent reads full state and merges typed output.
- **Tuning Studio API** — REST + WebSocket for logs, config edits, feedback, and A/B tests.

**Non-goals (explicit):** cloud execution of source code; LLM fine-tuning; agent self-modification; dynamic agent creation; shared mutable state across unrelated pipelines.

---

## Phase 0 — Repository and tooling

| Step | Work |
|------|------|
| 0.1 | Python **3.11+** monorepo layout: `packages/olympus` (runtime + API), optional `packages/olympus-mcp` later. |
| 0.2 | **uv** for dependency and lock management; `pyproject.toml` with dev deps (pytest, ruff/mypy as chosen). |
| 0.3 | CI: lint + tests on push (GitHub Actions or equivalent). |
| 0.4 | Environment: `ANTHROPIC_API_KEY` for Claude; local-only defaults for Chroma and SQLite. |

---

## Sprint 0 — Olympus Core (framework)

Deliver a minimal end-to-end pipeline run: load YAML → build LangGraph → execute nodes → append-only run log.

### 0.1 Schemas and loading

- **Agent YAML** — Fields aligned with the doc: `name`, `version`, `role`, `description`, `system_prompt`, `tools`, `config`, `input_schema`, `output_schema`, `scoring` (e.g. `min_score`, rules / hooks).
- **Pipeline YAML** — `name`, `version`, `state_schema`, `nodes` (agent + `id`), `edges` (optional `condition`), `retry`, `orchestrator` as applicable.
- Parse with **PyYAML**; validate with **Pydantic** models generated or hand-mapped from declared `input_schema` / `output_schema` / `state_schema` (start with a small set of registered state/output types, then generalize).

### 0.2 LangGraph integration

- Map pipeline `nodes` and `edges` to a **LangGraph** `StateGraph` using the shared **state_schema** as graph state.
- Conditional edges from YAML `condition` (evaluate against current state; start with named predicates registered in code).

### 0.3 Tool system

- Implement `@tool` decorator (see doc) in `olympus.tools`: name, description, schema from function signature.
- Register only tools listed on each agent; pass definitions to the Anthropic API.

### 0.4 Agent node execution

Per node:

1. Build prompt: system prompt + serialized pipeline state (feed-forward).
2. Call **Anthropic SDK** (model per doc, e.g. `claude-sonnet-4-20250514`) with tools.
3. **Log** call to run store: `call_id`, agent, `node_id`, full prompt/context, full response, tool calls, tokens, latency, timestamp.
4. Parse structured output; validate against `output_schema`.
5. Run **scoring** (pluggable: rule text + optional callable); persist score and feedback.
6. Merge output into shared state.
7. **Retry** if score &lt; `min_score` and retries remain: `escalate_prompt` | `widen_retrieval` | `flag_human` as configured.

### 0.5 Run database (append-only)

- **SQLite** first (file path configurable); schema matching Run / `agent_calls[]` tree from the doc.
- No updates/deletes to log rows; feedback as separate tables keyed by `run_id`.
- Optional later: **PostgreSQL** for cloud deployments (same schema, different driver).

### 0.6 Demo pipeline

- One trivial two-node pipeline with stub tools and simple Pydantic state to prove execution, logging, and state merge without Lethe.

**Exit criteria:** `uv run` (or equivalent) executes the demo pipeline; run log queryable locally; tests cover load, validation, and one full dry or mocked Claude path.

---

## Sprint 1 — Lethe (first production agent on the framework)

Lethe establishes indexing, embeddings, and the first real tool surface.

| Workstream | Details |
|------------|---------|
| Chunking | **tree-sitter** + **Chonkie** (or doc-aligned stack) for language-aware chunks across supported languages. |
| Vector store | **ChromaDB** local; index built from repo path in pipeline state. |
| Embeddings | **sentence-transformers** locally (no embedding API by default). |
| Change tracking | **Merkle tree** (`hashlib`) for incremental re-index decisions. |
| Tools | Implement: `search_index`, `read_file`, `get_git_history` (and any stubs still needed for a minimal Lethe loop). |
| Config | `lethe.yaml` (or equivalent) with schemas and scoring as in product docs. |

**Exit criteria:** Pipeline slice runs Lethe against a sample repo; index and search work locally; calls appear in run log with scores.

---

## Sprint 2+ — Remaining heroes (Repo Analyser / Athena)

For each agent (Iris, Pallas, Asclepius, Daedalus, Nike, Tyche, Arete, orchestrator **Athena**):

- Add or extend **agent YAML** + **tools** only; avoid framework churn unless a gap appears.
- Extend **AthenaPipelineState** (and related Pydantic models) per the architecture doc.
- Grow **athena-pipeline.yaml** (or split subgraphs) with edges and conditions (`standing_knowledge_sufficient`, etc.).
- Wire **orchestrator** agent for final context package assembly.

**Exit criteria:** Full Athena pipeline produces the intended structured context package type; run log captures all heroes; retry policies validated on at least one edge case.

---

## Final phase — Tuning Studio

### Backend (FastAPI)

- REST endpoints as in the doc: agents (list, get, versions, prompt/config update, rollback), pipelines, runs, feedback, isolation tests, experiments, performance aggregates.
- **WebSocket** `GET` → `WS /runs/{run_id}/live` for live progress.
- OpenAPI published for the TypeScript client.

### Frontend (TypeScript + React)

- Agent inspector, prompt editor, run log viewer, feedback capture, A/B experiment UI (consumes API above).

### Optional

- **MCP server** (Python MCP SDK) exposing context packages to external agents.

**Exit criteria:** End-to-end flow: edit prompt → new version → run pipeline → view log → submit feedback → see aggregates.

---

## Dependency map (technical stack)

| Layer | Technology |
|-------|------------|
| Runtime | Python 3.11+ |
| Orchestration | LangGraph |
| LLM | Anthropic Claude API |
| Vector / search | ChromaDB (local), sentence-transformers |
| Chunking | tree-sitter, Chonkie |
| Config / state | YAML + Pydantic |
| Run store | SQLite → PostgreSQL |
| API | FastAPI + WebSocket |
| UI | TypeScript + React |
| Packaging | uv |

---

## Risk and sequencing notes

- **Claude + tool schemas** — Early integration test with real API avoids schema mismatches late in Sprint 0.
- **State size** — Full state in every prompt may hit context limits; plan summarization or selective projection before scaling heroes.
- **Scoring** — Start with simple numeric/rule-based scorers; evolve to match product “score_section” patterns.
- **Sub-pipelines** — ADO platform calling Athena as a sub-pipeline needs a clear boundary (separate run_id vs parent/child linkage); design when ADO agents land.

---

## Immediate next actions (after this document)

1. Scaffold `packages/olympus` with `pyproject.toml`, `src/olympus/`, and pytest layout.  
2. Implement agent/pipeline YAML loaders + Pydantic validation.  
3. Add LangGraph builder + stub Anthropic client for tests.  
4. Implement SQLite run log writer and reader.  
5. Add the demo pipeline and document `uv sync` / `uv run` in the root README.

This sequence matches **§9 Build Sequence** in the architecture PDF: Core → Lethe → heroes → Tuning Studio.
