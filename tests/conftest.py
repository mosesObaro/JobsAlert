"""
Test isolation for the whole suite.

Every test runs against a temporary data directory and a temporary copy of the
configuration, with email credentials removed from the environment and real network
access blocked. Tests that need HTTP responses use httpx.MockTransport explicitly.
"""

import shutil
from pathlib import Path

import httpx
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SENSITIVE_ENV = [
    "RESEND_API_KEY", "BREVO_API_KEY", "SENDGRID_API_KEY",
    "SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_USE_TLS",
    "CANDIDATE_EMAIL", "ALERTS_FROM_EMAIL", "EMAIL_PROVIDER",
    "JOBSALERT_API_TOKEN", "JOBSALERT_ALLOWED_HOSTS", "JOBSALERT_CORS_ORIGINS",
]


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    profiles_dir = tmp_path / "config" / "profiles"
    data_dir.mkdir()
    profiles_dir.mkdir(parents=True)
    shutil.copy(PROJECT_ROOT / "config" / "jobs.yaml", tmp_path / "config" / "jobs.yaml")
    for profile in (PROJECT_ROOT / "config" / "profiles").glob("*.yaml"):
        shutil.copy(profile, profiles_dir / profile.name)

    monkeypatch.setenv("JOBSALERT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("JOBSALERT_CONFIG", str(tmp_path / "config" / "jobs.yaml"))
    monkeypatch.setenv("JOBSALERT_PROFILES_DIR", str(profiles_dir))
    for name in SENSITIVE_ENV:
        monkeypatch.delenv(name, raising=False)
    yield tmp_path


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fails any real HTTP request fast; MockTransport-based clients are unaffected."""

    async def refuse(self, request):
        raise httpx.ConnectError(f"Network access is disabled in tests ({request.url.host})", request=request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", refuse)
