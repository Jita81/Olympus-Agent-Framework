"""Lethe tools: read_file, search_index, get_git_history (repo-bound via ToolContext)."""

from __future__ import annotations

import json
from typing import Any

from git import Repo
from pydantic import BaseModel

from olympus.tool_context import get_tool_context
from olympus.tools import tool


@tool(
    name="read_file",
    description="Read file contents under the indexed repository (path relative to repo root).",
)
def read_file(path: str, start_line: int = 0, end_line: int = -1) -> str:
    ctx = get_tool_context()
    full = (ctx.repo_root / path).resolve()
    try:
        full.relative_to(ctx.repo_root.resolve())
    except ValueError:
        return "error: path escapes repository root"
    if not full.is_file():
        return f"error: not a file: {path}"
    lines = full.read_text(encoding="utf-8", errors="replace").splitlines()
    if end_line < 0:
        chunk = lines[start_line:]
    else:
        chunk = lines[start_line:end_line]
    return "\n".join(chunk)


@tool(
    name="search_index",
    description="Semantic search over the local Chroma index built from the repository.",
)
def search_index(query: str, top_k: int = 5) -> str:
    ctx = get_tool_context()
    coll = ctx.chroma_client.get_collection(ctx.collection_name)
    emb = ctx.embedder.encode([query], show_progress_bar=False)
    res = coll.query(query_embeddings=emb.tolist(), n_results=min(max(top_k, 1), 20))
    hits: list[dict[str, Any]] = []
    ids = res.get("ids") or [[]]
    docs = res.get("documents") or [[]]
    metas = res.get("metadatas") or [[]]
    dists = res.get("distances") or [[]]
    for row in zip(
        ids[0] if ids else [],
        docs[0] if docs else [],
        metas[0] if metas else [],
        dists[0] if dists else [],
        strict=False,
    ):
        hid, doc, meta, dist = row
        meta = meta or {}
        hits.append(
            {
                "id": hid,
                "path": meta.get("path", ""),
                "chunk_index": meta.get("chunk_index", ""),
                "distance": dist,
                "snippet": (doc or "")[:500],
            }
        )
    return json.dumps(hits, indent=2)


@tool(
    name="get_git_history",
    description="Recent commits touching a path (path relative to repo root).",
)
def get_git_history(path: str, max_commits: int = 10) -> str:
    ctx = get_tool_context()
    max_commits = min(max(max_commits, 1), 50)
    try:
        repo = Repo(ctx.repo_root, search_parent_directories=True)
    except Exception as e:
        return json.dumps({"error": str(e)})

    rel = path
    commits_out: list[dict[str, str]] = []
    try:
        for i, commit in enumerate(repo.iter_commits(paths=rel, max_count=max_commits)):
            commits_out.append(
                {
                    "hexsha": commit.hexsha[:12],
                    "summary": (commit.summary or "")[:200],
                    "committed_datetime": commit.committed_datetime.isoformat(),
                }
            )
    except Exception as e:
        return json.dumps({"error": str(e), "path": rel})

    return json.dumps({"path": rel, "commits": commits_out}, indent=2)


LETHE_TOOL_MAP: dict[str, Any] = {
    read_file.name: read_file,
    search_index.name: search_index,
    get_git_history.name: get_git_history,
}


def mock_lethe_output(
    state: BaseModel,
    tool_specs: list[Any],
) -> BaseModel:
    """Deterministic Lethe output for CI (runs real tools if context is set)."""

    from olympus.schema_registry import resolve_output_schema

    LetheOutput = resolve_output_schema("LetheOutput")
    data = state.model_dump()
    repo = str(data.get("repo_path", "."))

    try:
        ctx = get_tool_context()
        q = str(data.get("index_query") or "README")
        raw = search_index.fn(query=q, top_k=3)
        hits = json.loads(raw)
        first_path = ""
        if isinstance(hits, list) and hits:
            first_path = str(hits[0].get("path", ""))
        sample = ""
        if first_path:
            sample = read_file.fn(path=first_path, start_line=0, end_line=20)
        gh = get_git_history.fn(path=first_path or ".", max_commits=5)
        merkle = ctx.merkle_root
        chunks = ctx.indexed_chunks
    except Exception as exc:
        return LetheOutput(
            repo_path=repo,
            merkle_root="",
            indexed_chunks=0,
            summary=f"Lethe mock without full context: {exc}",
            sample_hits=[],
        )

    return LetheOutput(
        repo_path=repo,
        merkle_root=merkle,
        indexed_chunks=chunks,
        summary=(
            f"Indexed {chunks} chunks at merkle {merkle[:16]}… Top path: {first_path or 'n/a'}."
        ),
        sample_hits=hits if isinstance(hits, list) else [],
        sample_file_excerpt=sample[:2000],
        git_history_json=gh,
    )
