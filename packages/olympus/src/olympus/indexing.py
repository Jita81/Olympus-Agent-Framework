"""Build and query a local Chroma index over repository chunks (Lethe)."""

from __future__ import annotations

import uuid
from pathlib import Path

import chromadb
import chromadb.errors
from chonkie import Chunk, CodeChunker
from sentence_transformers import SentenceTransformer

from olympus.merkle import directory_merkle_root
from olympus.tool_context import ToolContext

_SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        ".olympus",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "dist",
        "build",
        ".tox",
        "chroma",
        "chroma_lethe",
    }
)


def _path_is_skipped(rel: Path) -> bool:
    return any(p in _SKIP_DIR_NAMES or p.startswith(".") for p in rel.parts)


def _fallback_line_chunks(raw: str, *, max_chars: int = 2400) -> list[Chunk]:
    """Plain-text chunks when tree-sitter has no parser for the detected language."""

    out: list[Chunk] = []
    pos = 0
    while pos < len(raw):
        end = min(pos + max_chars, len(raw))
        piece = raw[pos:end].strip()
        if piece:
            out.append(
                Chunk(
                    text=piece,
                    start_index=pos,
                    end_index=end,
                    token_count=max(1, len(piece) // 4),
                )
            )
        pos = end
    return out


def _guess_language(path: Path) -> str | None:
    """Return a tree-sitter language id, or None to use plain-text chunking."""

    ext = path.suffix.lower()
    if ext == ".py":
        return "python"
    if ext in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}:
        return "javascript"
    if ext == ".kt":
        return "kotlin"
    if ext in {".rs", ".go", ".java", ".c", ".h", ".cpp", ".hpp", ".rb", ".php"}:
        return ext.lstrip(".")
    return None


def build_index(
    repo_root: Path,
    *,
    chroma_path: Path,
    collection_name: str,
    embedding_model_name: str = "all-MiniLM-L6-v2",
    chunk_size: int = 512,
) -> ToolContext:
    """
    Compute Merkle root; if it matches stored metadata on the collection, skip re-embedding.

    Otherwise re-chunk source files, embed with sentence-transformers, upsert into Chroma.
    """

    repo_root = repo_root.resolve()
    merkle = directory_merkle_root(repo_root)

    client = chromadb.PersistentClient(path=str(chroma_path))
    embedder = SentenceTransformer(embedding_model_name)

    try:
        coll = client.get_collection(collection_name)
        meta = coll.metadata or {}
        if meta.get("merkle_root") == merkle:
            count = coll.count()
            return ToolContext(
                repo_root=repo_root,
                chroma_client=client,
                collection_name=collection_name,
                embedder=embedder,
                merkle_root=merkle,
                indexed_chunks=count,
            )
        client.delete_collection(collection_name)
    except chromadb.errors.NotFoundError:
        pass

    coll = client.create_collection(
        name=collection_name,
        metadata={"merkle_root": merkle, "repo_root": str(repo_root)},
    )

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, str]] = []

    text_ext = {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".mjs",
        ".cjs",
        ".md",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".rs",
        ".go",
        ".java",
        ".kt",
        ".c",
        ".h",
        ".cpp",
        ".hpp",
        ".rb",
        ".php",
        ".txt",
    }

    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(repo_root)
        if _path_is_skipped(rel):
            continue
        if path.suffix.lower() not in text_ext:
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not raw.strip():
            continue

        lang = _guess_language(path)
        if lang is None:
            chunks = _fallback_line_chunks(raw, max_chars=max(800, chunk_size * 5))
        else:
            try:
                chunker = CodeChunker(chunk_size=chunk_size, language=lang)
                chunks = chunker.chunk(raw)
            except Exception:
                chunks = _fallback_line_chunks(raw, max_chars=max(800, chunk_size * 5))

        for i, ch in enumerate(chunks):
            text = ch.text.strip()
            if not text:
                continue
            cid = str(uuid.uuid4())
            ids.append(cid)
            documents.append(text)
            metadatas.append(
                {
                    "path": rel.as_posix(),
                    "chunk_index": str(i),
                }
            )

    n_chunks = len(documents)
    if documents:
        embs = embedder.encode(documents, show_progress_bar=False)
        coll.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embs.tolist())

    return ToolContext(
        repo_root=repo_root,
        chroma_client=client,
        collection_name=collection_name,
        embedder=embedder,
        merkle_root=merkle,
        indexed_chunks=n_chunks,
    )
