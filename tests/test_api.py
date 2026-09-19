"""
Tests for the control panel API: behaviour, authentication and hardening.
"""

import pytest
import yaml
from fastapi.testclient import TestClient

from src import paths
from src.api import server
from src.api.server import app

AUTH = {"X-JobsAlert-Token": server.API_TOKEN}


@pytest.fixture
def client():
    server._latest.update({"jobs": None, "income": None})
    server.RUN_GUARD.finish()
    return TestClient(app, base_url="http://localhost")


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_config(client):
    data = client.get("/api/config").json()
    for section in ("profile", "filters", "job_specs", "sources", "schedule", "delivery", "online_income"):
        assert section in data


def test_get_profiles(client):
    assert isinstance(client.get("/api/profiles").json()["profiles"], list)


def test_preview_email_endpoint(client):
    response = client.get("/api/preview-email")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_root_serves_dashboard_or_build_instructions(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# --- security -------------------------------------------------------------

def test_state_changing_routes_require_the_token(client):
    for method, url, body in [
        ("post", "/api/config", {"delivery": {"recipient_email": "attacker@example.com"}}),
        ("post", "/api/run", {"dry_run": False, "send_email": True}),
        ("post", "/api/seen-jobs/clear", None),
        ("post", "/api/jobs/custom", {"title": "x", "company": "y"}),
        ("post", "/api/profiles/save", {"profile_name": "copy"}),
    ]:
        response = getattr(client, method)(url, json=body) if body is not None else getattr(client, method)(url)
        assert response.status_code == 401, url
        wrong = getattr(client, method)(url, json=body, headers={"X-JobsAlert-Token": "guess"}) if body is not None else \
            getattr(client, method)(url, headers={"X-JobsAlert-Token": "guess"})
        assert wrong.status_code == 401, url


def test_token_is_only_handed_to_local_clients(client):
    # The test client's address is "testclient", not a loopback address.
    assert client.get("/api/session").status_code == 403


def test_unknown_host_header_is_rejected(client):
    response = client.get("/api/health", headers={"Host": "attacker.example"})
    assert response.status_code == 400


def test_cors_does_not_admit_other_sites(client):
    response = client.options("/api/config", headers={
        "Origin": "https://attacker.example", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,x-jobsalert-token",
    })
    assert response.headers.get("access-control-allow-origin") != "https://attacker.example"
    allowed = client.options("/api/config", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST",
    })
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_profile_names_cannot_escape_the_profiles_folder(client):
    for name in ["../../config/jobs", "..\\evil", "a/b", "../../../../tmp/x"]:
        assert client.post("/api/profiles/save", json={"profile_name": name}, headers=AUTH).status_code == 400
        assert client.post("/api/profiles/load", json={"profile_name": name}, headers=AUTH).status_code == 400
    assert client.post("/api/profiles/save", json={"profile_name": "hr_copy"}, headers=AUTH).status_code == 200
    assert (paths.profiles_dir() / "hr_copy.yaml").exists()


# --- configuration --------------------------------------------------------

def test_partial_config_update_keeps_other_sections(client):
    before = client.get("/api/config").json()
    response = client.post("/api/config", json={"schedule": {"instant_alert_threshold": 9.5}}, headers=AUTH)
    assert response.status_code == 200
    after = client.get("/api/config").json()
    assert after["schedule"]["instant_alert_threshold"] == 9.5
    assert after["job_specs"] == before["job_specs"]
    assert after["online_income"] == before["online_income"]


def test_invalid_config_is_rejected_with_a_reason(client):
    response = client.post("/api/config", json={"schedule": {"instant_alert_threshold": "high"}}, headers=AUTH)
    assert response.status_code == 400
    assert "instant_alert_threshold" in response.json()["detail"]


def test_env_overrides_are_not_written_to_config(client, monkeypatch):
    monkeypatch.setenv("CANDIDATE_EMAIL", "real.person@example.org")
    monkeypatch.setenv("EMAIL_PROVIDER", "console")
    assert client.get("/api/config").json()["delivery"]["recipient_email"] == "real.person@example.org"

    assert client.post("/api/config", json={"profile": {"candidate_name": "Tester"}}, headers=AUTH).status_code == 200
    saved = yaml.safe_load(paths.config_path().read_text())
    assert saved["profile"]["candidate_name"] == "Tester"
    assert saved["delivery"]["recipient_email"] != "real.person@example.org"
    assert saved["delivery"]["email_provider"] != "console"


# --- custom jobs, results and runs -----------------------------------------

def test_custom_job_crud_by_id(client):
    created = client.post("/api/jobs/custom", json={"title": "HR Lead", "company": "Acme"}, headers=AUTH).json()["job"]
    listed = client.get("/api/jobs/custom").json()["custom_jobs"]
    assert [j["id"] for j in listed] == [created["id"]]
    assert client.delete("/api/jobs/custom/unknown-id", headers=AUTH).status_code == 404
    assert client.delete(f"/api/jobs/custom/{created['id']}", headers=AUTH).status_code == 200
    assert client.get("/api/jobs/custom").json()["custom_jobs"] == []


def test_dry_run_results_survive_a_restart(client):
    response = client.post("/api/run", json={"dry_run": True, "force_all": True}, headers=AUTH)
    assert response.status_code == 200
    assert response.json()["summary"]["mode"] == "dry_run"

    server._latest.update({"jobs": None, "income": None})  # simulate a server restart
    data = client.get("/api/jobs").json()
    assert data["summary"]["run_id"] == response.json()["summary"]["run_id"]


def test_only_one_run_at_a_time(client):
    server.RUN_GUARD.start("income")
    try:
        response = client.post("/api/run", json={"dry_run": True}, headers=AUTH)
        assert response.status_code == 429
    finally:
        server.RUN_GUARD.finish()


def test_clearing_seen_jobs_keeps_a_backup(client):
    state_file = paths.data_file(paths.SEEN_JOBS)
    state_file.write_text('{"fp": {"fingerprint": "fp", "alerted": true}}')
    assert client.post("/api/seen-jobs/clear", headers=AUTH).json()["cleared_count"] == 1
    assert list(state_file.parent.glob(f"{state_file.name}.*.bak"))
