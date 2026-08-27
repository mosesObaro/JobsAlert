"""
Unit tests for URL canonicalization, fingerprinting, and deduplication state management.
"""

from pathlib import Path
import pytest

from src.deduplication import (
    StateManager,
    canonicalize_url,
    compute_job_fingerprint,
    normalize_string,
)
from src.models import JobPosting


def test_canonicalize_url():
    dirty_url = "https://boards.greenhouse.io/cloudflare/jobs/12345?utm_source=linkedin&utm_medium=cpc&ref=jobboard&gh_src=abc#details"
    clean_url = canonicalize_url(dirty_url)
    assert clean_url == "https://boards.greenhouse.io/cloudflare/jobs/12345"
    assert "utm_source" not in clean_url
    assert "gh_src" not in clean_url
    assert "#details" not in clean_url


def test_compute_job_fingerprint_equivalence():
    # Two identical postings from different boards with minor string discrepancies
    fp1 = compute_job_fingerprint(
        company="Stripe, Inc.",
        title="Senior Software Engineer - Infrastructure",
        location_type="Remote",
        reference_id="req_9981",
    )

    fp2 = compute_job_fingerprint(
        company="Stripe",
        title="Senior Software Engineer Infrastructure",
        location_type="remote",
        reference_id="req_9981",
    )

    assert fp1 == fp2


def test_state_manager_deduplication(tmp_path):
    state_file = tmp_path / "seen_jobs.json"
    state = StateManager(state_file_path=state_file)

    job = JobPosting(
        id="job_001",
        title="Distributed Systems Lead",
        company="Datadog",
        location="Remote",
        url="https://jobs.lever.co/datadog/001",
        description="Lead distributed systems",
        source="lever",
    )
    job.fingerprint = compute_job_fingerprint(job.company, job.title, job.location, job.id)

    assert not state.is_seen(job.fingerprint)
    state.record_job(job, score=8.5, action="digest")
    state.save()

    # Re-instantiate from disk
    state_reloaded = StateManager(state_file_path=state_file)
    assert state_reloaded.is_seen(job.fingerprint)
    assert state_reloaded.get_seen_count() == 1
