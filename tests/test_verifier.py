"""
Unit tests for the Link Verification Engine.
Tests HTTP status code evaluation, soft-404 closed posting keyword detection, caching, and timeouts.
"""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest
import httpx

from src.config import LinkVerificationConfig
from src.models import JobPosting
from src.verifier import LinkVerifier, VerificationResult


def test_link_verifier_cache(tmp_path):
    cache_file = tmp_path / "test_link_cache.json"
    verifier = LinkVerifier(cache_file=cache_file)

    res = VerificationResult(
        url="https://example.com/jobs/1",
        is_valid=True,
        status_code=200,
        reason="active",
        verified_at="2026-09-05T12:00:00+00:00",
    )
    verifier.cache_result(res)
    verifier._save_cache()

    # Load in new instance
    verifier2 = LinkVerifier(cache_file=cache_file)
    cached = verifier2.get_cached_result("https://example.com/jobs/1", ttl_hours=24)
    assert cached is not None
    assert cached.is_valid is True
    assert cached.status_code == 200


def test_mock_url_verification():
    verifier = LinkVerifier()
    res = asyncio.run(verifier.verify_url("https://example.com/test-job"))
    assert res.is_valid is True
    assert res.reason == "mock_valid"


def test_404_url_verification():
    verifier = LinkVerifier()
    mock_resp = httpx.Response(status_code=404, request=httpx.Request("GET", "https://real-site.com/job/404"))

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        res = asyncio.run(verifier.verify_url("https://real-site.com/job/404"))
        assert res.is_valid is False
        assert "404" in res.reason


def test_soft_404_closed_job_detection():
    verifier = LinkVerifier()
    html_content = """
    <html>
        <body>
            <h1>Thank you for your interest</h1>
            <p>This position has been closed and we are no longer accepting applications.</p>
        </body>
    </html>
    """
    mock_resp = httpx.Response(
        status_code=200,
        text=html_content,
        request=httpx.Request("GET", "https://boards.greenhouse.io/acme/jobs/999")
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        res = asyncio.run(verifier.verify_url("https://boards.greenhouse.io/acme/jobs/999"))
        assert res.is_valid is False
        assert "Position closed" in res.reason


def test_active_200_job_verification():
    verifier = LinkVerifier()
    html_content = """
    <html>
        <body>
            <h1>Staff Distributed Systems Engineer</h1>
            <p>We are hiring! Apply below.</p>
            <button>Apply Now</button>
        </body>
    </html>
    """
    mock_resp = httpx.Response(
        status_code=200,
        text=html_content,
        request=httpx.Request("GET", "https://jobs.ashbyhq.com/acme/123")
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        res = asyncio.run(verifier.verify_url("https://jobs.ashbyhq.com/acme/123"))
        assert res.is_valid is True
        assert res.reason == "active"


def test_verify_jobs_batch():
    verifier = LinkVerifier()
    jobs = [
        JobPosting(
            id="job_active",
            title="Senior Go Dev",
            company="Acme",
            url="https://example.com/active",
            source="custom"
        ),
        JobPosting(
            id="job_closed",
            title="Old Dev",
            company="OldCorp",
            url="https://real-site.com/closed-job",
            source="custom"
        ),
    ]

    mock_resp_closed = httpx.Response(
        status_code=200,
        text="<html><body>This job is no longer available</body></html>",
        request=httpx.Request("GET", "https://real-site.com/closed-job")
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp_closed
        valid, invalid = asyncio.run(verifier.verify_jobs_batch(jobs))

        assert len(valid) == 1
        assert valid[0].id == "job_active"
        assert len(invalid) == 1
        assert invalid[0][0].id == "job_closed"
        assert "Position closed" in invalid[0][1]
