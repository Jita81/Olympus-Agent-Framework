# Olympus Agent Framework

Shared agent runtime for Automated Agile products: LangGraph orchestration, YAML-defined agents, Claude via Anthropic, and append-only run logs for the Tuning Studio.

## Documentation

- **[Architecture (PDF)](docs/olympus-framework-architecture.pdf)** — Olympus Agent Framework v1.0 (March 2026): concepts, runtime, observability, Tuning Studio API, stack, and build sequence.
- **[Build plan](docs/BUILD_PLAN.md)** — Phased implementation plan aligned with the architecture (Core → Lethe → remaining agents → Tuning Studio).

## Status

The repository currently contains the architecture document and build plan. The Python package (`olympus`), tooling, and CI will land per `docs/BUILD_PLAN.md` (Sprint 0 onward).
