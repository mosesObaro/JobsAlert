import pytest
from fastapi.testclient import TestClient
from src.api.server import app

client = TestClient(app)


def test_get_income_config():
    response = client.get("/api/income/config")
    assert response.status_code == 200
    data = response.json()
    assert "eligible_countries" in data
    assert "preferred_categories" in data
    assert data["enabled"] is True


def test_post_income_config_update():
    cfg_res = client.get("/api/income/config")
    cfg = cfg_res.json()
    cfg["minimum_hourly_rate_usd"] = 8.0

    post_res = client.post("/api/income/config", json=cfg)
    assert post_res.status_code == 200
    assert post_res.json()["status"] == "success"

    verify_res = client.get("/api/income/config")
    assert verify_res.json()["minimum_hourly_rate_usd"] == 8.0


def test_trigger_income_run_and_get_opportunities():
    run_res = client.post("/api/income/run", json={"dry_run": True, "force_all": True})
    assert run_res.status_code == 200
    data = run_res.json()
    assert data["status"] == "completed"
    assert data["opportunities_count"] > 0

    opps_res = client.get("/api/income/opportunities")
    assert opps_res.status_code == 200
    opps_data = opps_res.json()
    assert opps_data["total"] > 0


def test_custom_income_opportunity_crud():
    # 1. Create
    create_res = client.post("/api/income/custom", json={
        "title": "Ad Hoc Video Study Participant",
        "organization": "University Lab",
        "category": "survey_research",
        "pay_rate_display": "$50/session",
        "url": "https://example.com/lab-study",
    })
    assert create_res.status_code == 200
    assert create_res.json()["status"] == "success"

    # 2. List
    list_res = client.get("/api/income/custom")
    assert list_res.status_code == 200
    items = list_res.json()["custom_opportunities"]
    assert len(items) > 0
    assert any("Ad Hoc Video Study Participant" in i["title"] for i in items)

    # 3. Delete
    del_res = client.delete("/api/income/custom/0")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"


def test_preview_income_email():
    res = client.get("/api/income/preview-email")
    assert res.status_code == 200
    assert "Online Income" in res.text
