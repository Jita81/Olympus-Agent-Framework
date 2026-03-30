# olympus

Sprint 0 core: YAML agents and pipelines, LangGraph execution, append-only SQLite run logs, and optional Claude via `ANTHROPIC_API_KEY` (deterministic mock when unset).

## Setup

```bash
cd packages/olympus
uv sync --extra dev
```

## Run the demo pipeline

Registers built-in `DemoPipelineState` / demo tools and runs the two-node example:

```bash
uv run olympus run \
  --register-demo \
  --pipeline examples/demo/pipeline.yaml \
  --agents examples/demo/agents \
  --task "Hello"
```

With `ANTHROPIC_API_KEY` set, the same command calls Claude (`claude-sonnet-4-20250514` by default).

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
- Register tools with `@tool` and add them to `olympus.tools.TOOL_REGISTRY`.
