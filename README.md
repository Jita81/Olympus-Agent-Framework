# Olympus Agent Framework

Shared agent runtime for Automated Agile products: LangGraph orchestration, YAML-defined agents, Claude via Anthropic, and append-only run logs for the Tuning Studio.

## Documentation

- **[Architecture (PDF)](docs/olympus-framework-architecture.pdf)** — Olympus Agent Framework v1.0 (March 2026): concepts, runtime, observability, Tuning Studio API, stack, and build sequence.
- **[Build plan](docs/BUILD_PLAN.md)** — Phased implementation plan aligned with the architecture (Core → Lethe → remaining agents → Tuning Studio).

## Code

Python package: [`packages/olympus`](packages/olympus) (see package README for Sprint 0 + Sprint 1).

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

CI runs lint and tests on `packages/olympus` (see `.github/workflows/ci.yml`).
