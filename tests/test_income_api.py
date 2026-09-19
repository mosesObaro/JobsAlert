import pytest
from fastapi.testclient import TestClient

from src.api import server
from src.api.server import app

AUTH = {"X-JobsAlert-Token": server.API_TOKEN}


@pytest.fixture
def client():
    server._latest.update({"jobs": None, "income": None})
    server.RUN_GUARD.finish()
    return TestClient(app, base_url="http://localhost")


def test_get_income_config(client):
    response = client.get("/api/income/config")
    assert response.status_code == 200
    assert response.json()["enabled"] is True


def test_partial_income_config_update(client):
    before = client.get("/api/income/config").json()
    response = client.post("/api/income/config", json={"minimum_hourly_rate_usd": 12.0}, headers=AUTH)
    assert response.status_code == 200
    after = client.get("/api/income/config").json()
    assert after["minimum_hourly_rate_usd"] == 12.0
    assert after["sources"] == before["sources"]  # untouched sections keep their platform lists


def test_trigger_income_run_and_get_opportunities(client):
    run_res = client.post("/api/income/run", json={"dry_run": True, "force_all": True}, headers=AUTH)
    assert run_res.status_code == 200
    assert run_res.json()["opportunities_count"] > 0

    opps = client.get("/api/income/opportunities").json()
    assert opps["total"] > 0


def test_unified_run_updates_income_results(client):
    client.post("/api/run", json={"dry_run": True, "force_all": True}, headers=AUTH)
    assert client.get("/api/income/opportunities", params={"include_rejected": True}).json()["total"] > 0


def test_custom_income_opportunity_crud(client):
    created = client.post("/api/income/custom", json={
        "title": "Ad Hoc Video Study Participant",
        "organization": "University Lab",
        "category": "survey_research",
        "pay_rate_display": "$50/session",
        "url": "https://example.com/lab-study",
    }, headers=AUTH)
    assert created.status_code == 200
    entry_id = created.json()["opportunity"]["id"]

    items = client.get("/api/income/custom").json()["custom_opportunities"]
    assert [i["id"] for i in items] == [entry_id]

    assert client.delete(f"/api/income/custom/{entry_id}", headers=AUTH).status_code == 200
    assert client.delete(f"/api/income/custom/{entry_id}", headers=AUTH).status_code == 404


def test_income_preview_never_starts_a_scan(client, monkeypatch):
    async def fail(*args, **kwargs):
        raise AssertionError("the preview must not run the pipeline")

    monkeypatch.setattr(server.IncomeOpportunityPipeline, "execute", fail)
    monkeypatch.setattr(server.IncomeOpportunityPipeline, "evaluate", fail)
    res = client.get("/api/income/preview-email")
    assert res.status_code == 200
    assert "Online Income" in res.text


def test_dismiss_requires_token(client):
    assert client.post("/api/income/dismiss", json={"fingerprint": "abc"}).status_code == 401
    assert client.post("/api/income/dismiss", json={"fingerprint": "abc"}, headers=AUTH).status_code == 200
