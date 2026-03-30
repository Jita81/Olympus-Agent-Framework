# Olympus Agent Framework

Shared agent runtime for Automated Agile products: LangGraph orchestration, YAML-defined agents, Claude via Anthropic, and append-only run logs for the Tuning Studio.

## Documentation

- **[Architecture (PDF)](docs/olympus-framework-architecture.pdf)** — Olympus Agent Framework v1.0 (March 2026): concepts, runtime, observability, Tuning Studio API, stack, and build sequence.
- **[Build plan](docs/BUILD_PLAN.md)** — Phased implementation plan aligned with the architecture (Core → Lethe → remaining agents → Tuning Studio).

## Code

Python package: [`packages/olympus`](packages/olympus) (see package README for sprints 0–2).

**Sprint 0 demo** (two-node mock-friendly pipeline):

```bash
cd packages/olympus
uv sync --extra dev
uv run olympus run --register-demo \
  --pipeline examples/demo/pipeline.yaml \
  --agents examples/demo/agents
```

**Sprint 1 — Lethe** (local Chroma + sentence-transformers + Chonkie chunking + Merkle skip logic; tools `read_file`, `search_index`, `get_git_history`):

```bash
cd packages/olympus
uv sync --extra dev
uv run olympus run --register-lethe --index-repo \
  --pipeline examples/lethe/pipeline.yaml \
  --agents examples/lethe/agents \
  --repo-path . \
  --index-query "def main"
```

With `ANTHROPIC_API_KEY`, Lethe runs a **tool loop** (Claude calls tools, then emits structured `LetheOutput`). Without the key, a deterministic mock still exercises indexing and tools for tests.

**Sprint 2 — Athena (Repo Analyser slice)** — eight heroes + orchestrator, conditional edge from standing gaps, `ContextPackage` output:

```bash
cd packages/olympus
uv run olympus run --register-athena \
  --pipeline examples/athena/pipeline.yaml \
  --agents examples/athena/agents \
  --user-story "Harden checkout validation" \
  --repo-path .
```

Use `--register-lethe` before `--register-athena` if you want real `read_file` / `search_index` / `get_git_history` instead of Athena stubs.

**Tuning Studio (API + UI)** — FastAPI server and optional React shell:

```bash
cd packages/olympus
uv sync --extra dev
uv run olympus-studio --port 8765
# OpenAPI: http://127.0.0.1:8765/docs
```

```bash
cd packages/tuning-ui
npm install
npm run dev   # proxies /api and /ws to olympus-studio
```

Set `OLYMPUS_STUDIO=1` when using `uv run olympus run …` so run start/complete events are written for the live WebSocket.

CI runs Python tests in `packages/olympus` and builds `packages/tuning-ui` (see `.github/workflows/ci.yml`).
