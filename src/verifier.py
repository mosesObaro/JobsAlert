"""
JobsAlert Link Verification Engine.
Checks whether application links still lead to an open posting.

Only a 404/410 or a page saying the posting is closed counts as dead. Rate limits
(429), access blocks (401/403), server errors and timeouts are "unknown": the
posting is kept and the result is not cached, so a throttled site never causes a
permanent discard.
"""

from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, Optional
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel

from src import paths
from src.config import LinkVerificationConfig
from src.storage import parse_timestamp, read_json, write_json_atomic

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 JobsAlert/2.0"
MAX_BODY_BYTES = 65536
MAX_RETRY_AFTER_SECONDS = 10.0

ACTIVE = "active"
DEAD = "dead"
UNKNOWN = "unknown"

# Text used by ATS platforms and job boards when a position is closed or expired
CLOSED_JOB_PHRASES = [
    "this job is no longer available",
    "this position has been closed",
    "this posting has expired",
    "this vacancy is closed",
    "no longer accepting applications",
    "the position you are trying to view has been filled",
    "the job you are trying to view has expired",
    "this job opening is closed",
    "page not found",
    "this job has expired",
    "job posting not found",
    "this role has been filled",
    "this position is closed",
    "we are no longer accepting applicants",
    "this listing is no longer active",
    "job listing not found",
    "position is no longer open",
    "applications for this job are closed",
]


class VerificationResult(BaseModel):
    url: str
    status: str = UNKNOWN  # "active", "dead" or "unknown"
    status_code: Optional[int] = None
    reason: str = ""
    verified_at: str = ""

    @property
    def is_dead(self) -> bool:
        return self.status == DEAD

    @property
    def is_valid(self) -> bool:
        """False only for links known to be dead."""
        return self.status != DEAD


def _result(url: str, status: str, reason: str, status_code: Optional[int] = None) -> VerificationResult:
    return VerificationResult(
        url=url, status=status, status_code=status_code, reason=reason,
        verified_at=datetime.now(timezone.utc).isoformat(),
    )


class LinkVerifier:
    """Verifies URLs concurrently with per-host limits and a persistent cache of definite results."""

    def __init__(self, cache_file: Optional[Path] = None, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.cache_file = Path(cache_file) if cache_file else paths.data_file(paths.LINK_CACHE)
        self.transport = transport  # injectable for tests
        self._cache: Dict[str, dict] = self._load_cache()

    def _load_cache(self) -> Dict[str, dict]:
        data = read_json(self.cache_file, {})
        if not isinstance(data, dict):
            return {}
        # Entries written before results had a `status` may record throttling as dead; drop them.
        return {url: entry for url, entry in data.items() if isinstance(entry, dict) and entry.get("status") in (ACTIVE, DEAD)}

    def save_cache(self, ttl_hours: int = 24) -> None:
        """Persists definite results younger than the TTL (keeps the cache bounded)."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
        fresh = {}
        for url, entry in self._cache.items():
            verified_at = parse_timestamp(entry.get("verified_at"))
            if verified_at and verified_at >= cutoff:
                fresh[url] = entry
        self._cache = fresh
        try:
            write_json_atomic(self.cache_file, fresh)
        except OSError as exc:
            print(f"[WARNING] Could not save link cache: {exc}")

    def get_cached_result(self, url: str, ttl_hours: int = 24) -> Optional[VerificationResult]:
        entry = self._cache.get(url)
        if not entry:
            return None
        verified_at = parse_timestamp(entry.get("verified_at"))
        if verified_at and datetime.now(timezone.utc) - verified_at < timedelta(hours=ttl_hours):
            return VerificationResult(**entry)
        return None

    def cache_result(self, result: VerificationResult) -> None:
        if result.status in (ACTIVE, DEAD):
            self._cache[result.url] = result.model_dump()

    def _client(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*"},
            timeout=timeout,
            follow_redirects=True,
            transport=self.transport,
        )

    async def verify_url(
        self,
        url: str,
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = 6.0,
        check_content: bool = True,
        ttl_hours: int = 24,
    ) -> VerificationResult:
        """Checks whether a single URL still leads to an open posting."""
        if not url or not url.startswith(("http://", "https://")):
            return _result(url, UNKNOWN, "No link to check")
        cached = self.get_cached_result(url, ttl_hours=ttl_hours)
        if cached:
            return cached

        own_client = client is None
        client = client or self._client(timeout)
        try:
            result = await self._fetch(client, url, timeout, check_content, allow_retry=True)
        finally:
            if own_client:
                await client.aclose()
        self.cache_result(result)
        return result

    async def _fetch(self, client: httpx.AsyncClient, url: str, timeout: float, check_content: bool, allow_retry: bool) -> VerificationResult:
        try:
            async with client.stream("GET", url, timeout=timeout) as resp:
                code = resp.status_code
                if code in (404, 410):
                    return _result(url, DEAD, f"HTTP {code} (not found)", code)
                if code == 429:
                    retry_after = _retry_after_seconds(resp.headers.get("retry-after"))
                    if allow_retry and retry_after is not None and retry_after <= MAX_RETRY_AFTER_SECONDS:
                        await resp.aclose()
                        await asyncio.sleep(retry_after)
                        return await self._fetch(client, url, timeout, check_content, allow_retry=False)
                    return _result(url, UNKNOWN, "Rate limited (HTTP 429)", code)
                if code in (401, 403):
                    return _result(url, UNKNOWN, f"Access blocked (HTTP {code})", code)
                if code >= 500:
                    return _result(url, UNKNOWN, f"Server error (HTTP {code})", code)
                if code >= 400:
                    return _result(url, UNKNOWN, f"HTTP {code}", code)

                if check_content:
                    body = await _read_limited(resp, MAX_BODY_BYTES)
                    text = body.decode(resp.encoding or "utf-8", errors="ignore").lower()
                    for phrase in CLOSED_JOB_PHRASES:
                        if phrase in text:
                            return _result(url, DEAD, f"Position closed ('{phrase}')", code)
                return _result(url, ACTIVE, "active", code)
        except httpx.TimeoutException:
            return _result(url, UNKNOWN, "Timed out")
        except httpx.HTTPError as exc:
            return _result(url, UNKNOWN, f"Connection failed ({type(exc).__name__})")

    async def verify_many(self, urls: Iterable[str], config: Optional[LinkVerificationConfig] = None) -> Dict[str, VerificationResult]:
        """Verifies distinct URLs with global and per-host concurrency limits."""
        cfg = config or LinkVerificationConfig()
        unique = list(dict.fromkeys(u for u in urls if u))
        if not unique:
            return {}

        global_limit = asyncio.Semaphore(max(1, cfg.max_concurrency))
        host_limits: Dict[str, asyncio.Semaphore] = {}

        async with self._client(cfg.timeout_seconds) as client:
            async def check(url: str) -> VerificationResult:
                host = urlparse(url).netloc.lower()
                host_limit = host_limits.setdefault(host, asyncio.Semaphore(max(1, cfg.per_host_concurrency)))
                # Host slot first, so tasks queued behind a busy host don't hold global slots.
                async with host_limit, global_limit:
                    return await self.verify_url(
                        url, client=client, timeout=cfg.timeout_seconds,
                        check_content=cfg.check_content_keywords, ttl_hours=cfg.cache_ttl_hours,
                    )

            outcomes = await asyncio.gather(*(check(u) for u in unique), return_exceptions=True)

        results: Dict[str, VerificationResult] = {}
        for url, outcome in zip(unique, outcomes):
            results[url] = outcome if isinstance(outcome, VerificationResult) else _result(url, UNKNOWN, f"Check failed ({type(outcome).__name__})")
        self.save_cache(cfg.cache_ttl_hours)
        return results


async def _read_limited(resp: httpx.Response, limit: int) -> bytes:
    chunks = bytearray()
    async for chunk in resp.aiter_bytes():
        chunks.extend(chunk)
        if len(chunks) >= limit:
            break
    return bytes(chunks[:limit])


def _retry_after_seconds(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
