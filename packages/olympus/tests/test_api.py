import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from olympus.api import AppSettings, create_app


@pytest.fixture
def demo_settings():
    root = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "studio.sqlite"
        yield AppSettings(
            db_path=db,
            agents_dir=root / "examples" / "demo" / "agents",
            pipelines_dir=root / "examples",
        )


def test_health_and_agents(demo_settings):
    app = create_app(demo_settings)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        r = client.get("/agents")
        assert r.status_code == 200
        names = {a["name"] for a in r.json()}
        assert "demo-greeter" in names


def test_prompt_version_and_run_demo(demo_settings):
    app = create_app(demo_settings)
    with TestClient(app) as client:
        g = client.get("/agents/demo-greeter")
        assert g.status_code == 200
        orig = g.json()["system_prompt"]
        u = client.put(
            "/agents/demo-greeter/prompt",
            json={"system_prompt": orig + "\n\n(UI test suffix)"},
        )
        assert u.status_code == 200
        vid = u.json()["version_id"]
        v = client.get("/agents/demo-greeter/versions")
        assert any(x["version_id"] == vid for x in v.json())

        run = client.post(
            "/pipelines/demo/run",
            json={"register_demo": True, "state": {"task": "api test"}},
        )
        assert run.status_code == 200
        body = run.json()
        rid = body["run_id"]

        detail = client.get(f"/runs/{rid}")
        assert detail.status_code == 200
        assert len(detail.json()["agent_calls"]) == 2

        fb = client.post(
            f"/runs/{rid}/feedback",
            json={
                "outcome": "rating_1_5",
                "overall_notes": "ok",
                "section_feedback": [],
            },
        )
        assert fb.status_code == 200
