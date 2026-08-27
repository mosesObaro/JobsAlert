"""
Unit tests for the FastAPI control panel endpoints.
"""

from fastapi.testclient import TestClient
import pytest

from src.api.server import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "JobsAlert Intelligence"


def test_get_config():
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "profile" in data
    assert "filters" in data
    assert "sources" in data
    assert "schedule" in data
    assert "delivery" in data


def test_get_profiles():
    response = client.get("/api/profiles")
    assert response.status_code == 200
    data = response.json()
    assert "profiles" in data
    assert isinstance(data["profiles"], list)


def test_preview_email_endpoint():
    response = client.get("/api/preview-email")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_root_dashboard_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "JobsAlert" in response.text

