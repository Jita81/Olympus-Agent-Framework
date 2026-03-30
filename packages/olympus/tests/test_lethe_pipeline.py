import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from olympus.conditions import default_demo_conditions
from olympus.pipeline import run_pipeline
from olympus.run_store import RunStore
from olympus.schema_registry import (
    default_demo_schemas,
    register_lethe_schemas,
    resolve_state_schema,
)


@pytest.fixture
def tiny_repo(tmp_path):
    (tmp_path / "hello.py").write_text("def main():\n    print('hi')\n")
    return tmp_path


def test_lethe_pipeline_mocked_with_patched_indexing(tiny_repo, tmp_path):
    register_lethe_schemas()
    default_demo_schemas()
    default_demo_conditions()

    db = tmp_path / "runs.sqlite"
    examples = Path(__file__).resolve().parent.parent / "examples" / "lethe"

    fake_emb = MagicMock()

    def fake_encode(texts, show_progress_bar=False):
        n = len(texts) if isinstance(texts, list) else 1
        return np.random.default_rng(0).random((n, 8)).astype(np.float32)

    fake_emb.encode = fake_encode

    with patch("olympus.indexing.SentenceTransformer", return_value=fake_emb):
        state_cls = resolve_state_schema("LethePipelineState")
        initial = state_cls(repo_path=str(tiny_repo), index_query="main")
        final, run_id = run_pipeline(
            pipeline_path=examples / "pipeline.yaml",
            agents_dir=examples / "agents",
            initial_state=initial,
            db_path=db,
            register_lethe=False,
            index_repo=True,
            chroma_path=tmp_path / "chroma",
            embedding_model="fake-model",
        )

    assert final.indexed_chunks is not None and final.indexed_chunks >= 1
    assert final.merkle_root
    assert "main" in final.summary.lower() or "hello" in final.summary.lower()
    store = RunStore(db)
    assert len(store.list_agent_calls(run_id)) == 1


def test_lethe_tools_search_readable(tiny_repo, tmp_path):
    register_lethe_schemas()
    fake_emb = MagicMock()

    def _enc(texts, show_progress_bar=False):
        return np.ones((len(texts), 4), dtype=np.float32)

    fake_emb.encode = _enc

    with patch("olympus.indexing.SentenceTransformer", return_value=fake_emb):
        from olympus.indexing import build_index
        from olympus.lethe_tools import read_file, search_index
        from olympus.tool_context import reset_tool_context, set_tool_context

        tctx = build_index(
            tiny_repo,
            chroma_path=tmp_path / "chroma",
            collection_name="testcoll",
            embedding_model_name="x",
        )
        tok = set_tool_context(tctx)
        try:
            raw = search_index.fn(query="main", top_k=2)
            data = json.loads(raw)
            assert isinstance(data, list)
            assert data
            path = data[0]["path"]
            text = read_file.fn(path=path, start_line=0, end_line=-1)
            assert "main" in text
        finally:
            reset_tool_context(tok)
