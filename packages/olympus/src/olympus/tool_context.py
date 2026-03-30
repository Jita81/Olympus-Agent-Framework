"""Per-run context for tools (repo root, index, embeddings)."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chromadb.api import ClientAPI


@dataclass
class ToolContext:
    """Bound for the duration of a single `pipeline.run` / graph invoke."""

    repo_root: Path
    chroma_client: ClientAPI
    collection_name: str
    embedder: Any  # sentence_transformers.SentenceTransformer
    merkle_root: str
    indexed_chunks: int = 0


_ctx: ContextVar[ToolContext | None] = ContextVar("olympus_tool_ctx", default=None)


def set_tool_context(ctx: ToolContext) -> Token:
    return _ctx.set(ctx)


def reset_tool_context(token: Token) -> None:
    _ctx.reset(token)


def get_tool_context() -> ToolContext:
    c = _ctx.get()
    if c is None:
        raise RuntimeError(
            "Tool context is not set. Run the pipeline via olympus.pipeline.run_pipeline "
            "or set ToolContext before invoking tools."
        )
    return c
