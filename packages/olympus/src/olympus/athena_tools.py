"""Stub tools for Athena heroes (Sprint 2).

If Lethe registered read_file/search_index/get_git_history first, stubs are not used.
"""

from __future__ import annotations

from olympus.tools import tool


@tool(name="read_file", description="Read a file from the repository (stub if Lethe not loaded).")
def stub_read_file(path: str, start_line: int = 0, end_line: int = -1) -> str:
    return f"(stub read_file: {path} lines {start_line}-{end_line})"


@tool(name="search_index", description="Semantic search (stub if Lethe not loaded).")
def stub_search_index(query: str, top_k: int = 5) -> str:
    return f"(stub search_index: query={query!r} top_k={top_k})"


@tool(name="write_explanation", description="Persist an analytical explanation (stub).")
def write_explanation(module_path: str, text: str) -> str:
    return f"ok:{module_path}:{len(text)}"


@tool(name="read_explanation", description="Read Iris explanation for a module (stub).")
def read_explanation(module_path: str) -> str:
    return f"(stub explanation for {module_path})"


@tool(name="get_module_map", description="Module responsibility map (stub).")
def get_module_map() -> str:
    return "{}"


@tool(name="get_pattern", description="Fetch a pattern from the library (stub).")
def get_pattern(name: str) -> str:
    return f"(stub pattern {name})"


@tool(name="get_git_history", description="Git history for a path (stub if Lethe not loaded).")
def stub_get_git_history(path: str, max_commits: int = 5) -> str:
    return f"(stub git {path} max={max_commits})"


@tool(name="classify_change_type", description="Classify user story vs change taxonomy (stub).")
def classify_change_type(summary: str) -> str:
    return "refactor"


@tool(name="get_standard", description="Standards guidance for a change type (stub).")
def get_standard(change_type: str) -> str:
    return f"(stub standard for {change_type})"


@tool(name="write_gap", description="Write a gap to the register (stub).")
def write_gap(area: str, detail: str) -> str:
    return f"gap:{area}"


@tool(name="read_gaps", description="Read gap register for an area (stub).")
def read_gaps(area: str = "") -> str:
    return "[]"


@tool(name="score_section", description="Self-score a section (stub).")
def score_section(section: str, score: float) -> str:
    return f"scored:{section}:{score}"


ATHENA_TOOL_SPECS = [
    stub_read_file,
    stub_search_index,
    write_explanation,
    read_explanation,
    get_module_map,
    get_pattern,
    stub_get_git_history,
    classify_change_type,
    get_standard,
    write_gap,
    read_gaps,
    score_section,
]


def register_athena_tools() -> None:
    """Register stubs without overwriting Lethe (or other) implementations."""

    from olympus.tools import TOOL_REGISTRY

    for spec in ATHENA_TOOL_SPECS:
        if spec.name not in TOOL_REGISTRY:
            TOOL_REGISTRY[spec.name] = spec
