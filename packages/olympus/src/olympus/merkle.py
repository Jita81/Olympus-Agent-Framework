"""Content-addressed Merkle root for a directory tree (incremental re-index signal)."""

from __future__ import annotations

import hashlib
from pathlib import Path


def _file_digest(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.name.encode())
    h.update(b"\0")
    h.update(path.read_bytes())
    return h.hexdigest()


def directory_merkle_root(
    root: Path,
    *,
    ignore_dirs: frozenset[str] | None = None,
) -> str:
    """
    Deterministic hash over all regular files under *root* (recursive).

    Symlinks are not followed. Hidden directories (``.`` prefix) are skipped except
    the root itself. Default ignores: ``.git``, ``.venv``, ``__pycache__``, ``node_modules``.
    """

    root = root.resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)

    default_ignores = frozenset(
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
    ignore = default_ignores | (ignore_dirs or frozenset())

    entries: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        parts = path.relative_to(root).parts
        if any(p.startswith(".") for p in parts[:-1]) or any(p in ignore for p in parts):
            continue
        if parts[0] in ignore:
            continue
        entries.append((rel, _file_digest(path)))

    h = hashlib.sha256()
    for rel, digest in entries:
        h.update(rel.encode())
        h.update(b"\0")
        h.update(digest.encode())
        h.update(b"\n")
    return h.hexdigest()
