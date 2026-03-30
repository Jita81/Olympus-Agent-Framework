# Olympus Agent Framework

Shared agent runtime for Automated Agile products: LangGraph orchestration, YAML-defined agents, Claude via Anthropic, and append-only run logs for the Tuning Studio.

## Documentation

- **[Architecture (PDF)](docs/olympus-framework-architecture.pdf)** — Olympus Agent Framework v1.0 (March 2026): concepts, runtime, observability, Tuning Studio API, stack, and build sequence.
- **[Build plan](docs/BUILD_PLAN.md)** — Phased implementation plan aligned with the architecture (Core → Lethe → remaining agents → Tuning Studio).

## Code (Sprint 0)

Python package: [`packages/olympus`](packages/olympus). From that directory:

```bash
uv sync --extra dev
uv run pytest -q
uv run olympus run --register-demo \
  --pipeline examples/demo/pipeline.yaml \
  --agents examples/demo/agents
```

CI runs lint and tests on `packages/olympus` (see `.github/workflows/ci.yml`).
