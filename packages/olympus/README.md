# olympus

LangGraph-based Olympus runtime: YAML agents, optional Claude + **tool loop**, append-only SQLite run logs.

## Versions

- **0.1.x** — Sprint 0 (demo pipeline, structured output, no tool execution loop).
- **0.2.x** — Sprint 1 (Lethe: Chroma, embeddings, Chonkie + tree-sitter, Merkle, `read_file` / `search_index` / `get_git_history`, tool loop when using the API).
- **0.3.x** — Sprint 2 (Athena: full hero YAML graph, `AthenaPipelineState`, stub tools from the architecture doc, conditional `standing_knowledge_*`, orchestrator `ContextPackage`).
- **0.4.x** — Tuning Studio: FastAPI (`olympus.api`), versioned configs in SQLite (`studio_store`), `POST /pipelines/{name}/run`, WebSocket live stream, `olympus-studio` CLI; React UI in `../tuning-ui`.

## Setup

```bash
cd packages/olympus
uv sync --extra dev
```

Heavy deps (PyTorch, sentence-transformers, Chroma) install here; first `uv sync` can take several minutes.

## Sprint 0 — demo pipeline

```bash
uv run olympus run --register-demo \
  --pipeline examples/demo/pipeline.yaml \
  --agents examples/demo/agents \
  --task "Hello"
```

## Sprint 1 — Lethe slice

Builds a **persistent Chroma** index under `.olympus/chroma_lethe` (by default, next to the SQLite DB), keyed by **Merkle root** of the repo so unchanged trees skip re-embedding.

```bash
uv run olympus run --register-lethe --index-repo \
  --pipeline examples/lethe/pipeline.yaml \
  --agents examples/lethe/agents \
  --repo-path /path/to/repo \
  --index-query "authentication"
```

- **`--register-lethe`** — registers `LethePipelineState` / `LetheOutput`.
- **`--index-repo`** — chunks + embeds the repo, sets **tool context** for the graph run, merges `merkle_root` / `indexed_chunks` into final state.

With `ANTHROPIC_API_KEY`, the agent uses **tools** then returns structured JSON. Without it, tests and CI use a **mock** that still runs real indexing + tools when context is set.

## Sprint 2 — Athena (Repo Analyser)

```bash
uv run olympus run --register-athena \
  --pipeline examples/athena/pipeline.yaml \
  --agents examples/athena/agents \
  --user-story "Your story" \
  --repo-path .
```

`--register-athena` registers Pydantic state/output models, stub tools (unless Lethe already registered overlapping tool names), and pipeline conditions.

## Tuning Studio API

```bash
uv run olympus-studio --port 8765
```

Open `/docs` for OpenAPI. The UI in `packages/tuning-ui` proxies to this server. Pipeline runs triggered via the API use the Studio store so **edited prompts** apply. For CLI runs, set `OLYMPUS_STUDIO=1` to record `run_started` / `run_completed` and per-node events when a shared DB is used.

## Inspect a run

```bash
uv run olympus show-run <run_id>
```

## Tests

```bash
uv run pytest -q
uv run ruff check src tests
```

## Extending

- Register Pydantic models with `olympus.schema_registry.register_state_schema` / `register_output_schema`.
- Register edge conditions with `olympus.conditions.register_condition`.
- Register tools with `@tool` and add them to `olympus.tools.TOOL_REGISTRY` (or lazy-register like `lethe_tools`).
