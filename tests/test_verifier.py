"""
Unit tests for the Link Verification Engine: dead vs. unknown classification,
closed-posting detection, retries, caching and per-host limits.
"""

import asyncio
from datetime import datetime, timezone

import httpx

from src.config import LinkVerificationConfig
from src.verifier import LinkVerifier, VerificationResult


def verifier_with(handler, tmp_path) -> LinkVerifier:
    return LinkVerifier(cache_file=tmp_path / "cache.json", transport=httpx.MockTransport(handler))


def test_404_is_dead(tmp_path):
    verifier = verifier_with(lambda request: httpx.Response(404), tmp_path)
    result = asyncio.run(verifier.verify_url("https://real-site.test/job/404"))
    assert result.status == "dead"
    assert result.is_valid is False
    assert "404" in result.reason


def test_closed_posting_page_is_dead(tmp_path):
    page = "<html><p>This position has been closed and we are no longer accepting applications.</p></html>"
    verifier = verifier_with(lambda request: httpx.Response(200, text=page), tmp_path)
    result = asyncio.run(verifier.verify_url("https://boards.greenhouse.io/acme/jobs/999"))
    assert result.status == "dead"
    assert "Position closed" in result.reason


def test_open_posting_is_active(tmp_path):
    page = "<html><h1>Staff Engineer</h1><button>Apply Now</button></html>"
    verifier = verifier_with(lambda request: httpx.Response(200, text=page), tmp_path)
    result = asyncio.run(verifier.verify_url("https://jobs.ashbyhq.com/acme/123"))
    assert result.status == "active"
    assert result.is_valid


def test_rate_limits_blocks_and_server_errors_are_unknown_not_dead(tmp_path):
    for code in (429, 403, 401, 500, 503):
        verifier = verifier_with(lambda request, code=code: httpx.Response(code), tmp_path)
        result = asyncio.run(verifier.verify_url(f"https://news.ycombinator.com/item?id={code}"))
        assert result.status == "unknown", code
        assert result.is_valid, code


def test_timeouts_are_unknown(tmp_path):
    def timeout(request):
        raise httpx.ConnectTimeout("slow", request=request)

    result = asyncio.run(verifier_with(timeout, tmp_path).verify_url("https://slow.test/job"))
    assert result.status == "unknown"


def test_429_with_short_retry_after_is_retried_once(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, text="<html>Apply</html>")

    result = asyncio.run(verifier_with(handler, tmp_path).verify_url("https://busy.test/job"))
    assert result.status == "active"
    assert len(calls) == 2


def test_only_definite_results_are_cached(tmp_path):
    cache_file = tmp_path / "cache.json"
    verifier = LinkVerifier(cache_file=cache_file)
    now = datetime.now(timezone.utc).isoformat()
    verifier.cache_result(VerificationResult(url="https://a.test/1", status="active", status_code=200, reason="active", verified_at=now))
    verifier.cache_result(VerificationResult(url="https://a.test/2", status="unknown", status_code=429, reason="Rate limited", verified_at=now))
    verifier.save_cache()

    reloaded = LinkVerifier(cache_file=cache_file)
    assert reloaded.get_cached_result("https://a.test/1").status == "active"
    assert reloaded.get_cached_result("https://a.test/2") is None


def test_legacy_cache_entries_without_status_are_ignored(tmp_path):
    cache_file = tmp_path / "cache.json"
    now = datetime.now(timezone.utc).isoformat()
    cache_file.write_text('{"https://news.ycombinator.com/item?id=1": {"url": "x", "is_valid": false, "reason": "HTTP Error 429", "verified_at": "%s"}}' % now)
    assert LinkVerifier(cache_file=cache_file).get_cached_result("https://news.ycombinator.com/item?id=1") is None


def test_verify_many_limits_concurrency_per_host(tmp_path):
    active = {"now": 0, "peak": 0}

    async def handler(request):
        active["now"] += 1
        active["peak"] = max(active["peak"], active["now"])
        await asyncio.sleep(0.01)
        active["now"] -= 1
        return httpx.Response(200, text="<html>Apply</html>")

    verifier = verifier_with(handler, tmp_path)
    urls = [f"https://one-host.test/job/{i}" for i in range(12)]
    config = LinkVerificationConfig(max_concurrency=20, per_host_concurrency=2)
    results = asyncio.run(verifier.verify_many(urls, config))

    assert len(results) == 12
    assert all(r.status == "active" for r in results.values())
    assert active["peak"] <= 2
