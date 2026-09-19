"""
Unit tests for URL canonicalization, fingerprinting, and deduplication state management.
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from src.deduplication import (
    StateManager,
    canonicalize_url,
    compute_job_fingerprint,
    stable_hash,
)
from src.models import JobPosting
from src.storage import StateFileError

PROJECT_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent


def make_job(**overrides) -> JobPosting:
    fields = dict(
        id="job_001",
        title="Distributed Systems Lead",
        company="Datadog",
        location="Remote",
        url="https://jobs.lever.co/datadog/001",
        description="Lead distributed systems",
        source="lever",
    )
    fields.update(overrides)
    job = JobPosting(**fields)
    job.fingerprint = compute_job_fingerprint(job.company, job.title, job.location, job.id)
    return job


def test_canonicalize_url():
    dirty_url = "https://boards.greenhouse.io/cloudflare/jobs/12345?utm_source=linkedin&utm_medium=cpc&ref=jobboard&gh_src=abc#details"
    clean_url = canonicalize_url(dirty_url)
    assert clean_url == "https://boards.greenhouse.io/cloudflare/jobs/12345"


def test_canonicalize_url_sorts_remaining_parameters():
    assert canonicalize_url("https://x.test/job?b=2&a=1&hsCtaTracking=abc") == "https://x.test/job?a=1&b=2"


def test_compute_job_fingerprint_equivalence():
    fp1 = compute_job_fingerprint("Stripe, Inc.", "Senior Software Engineer - Infrastructure", "Remote", "req_9981")
    fp2 = compute_job_fingerprint("Stripe", "Senior Software Engineer Infrastructure", "remote", "req_9981")
    assert fp1 == fp2


def test_stable_hash_is_identical_across_processes():
    code = "from src.deduplication import stable_hash; print(stable_hash('https://www.jobberman.com', 'Moniepoint', 'Finance Accountant'))"
    outputs = {
        subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=PROJECT_ROOT, check=True).stdout.strip()
        for _ in range(3)
    }
    assert len(outputs) == 1
    assert outputs == {stable_hash("https://www.jobberman.com", "Moniepoint", "Finance Accountant")}


def test_state_manager_round_trip(tmp_path):
    state_file = tmp_path / "seen_jobs.json"
    state = StateManager(state_file)
    job = make_job()

    assert not state.is_seen(job.fingerprint)
    state.record_job(job, score=8.5, action="digest", spec="Leads")
    state.save()

    reloaded = StateManager(state_file)
    assert reloaded.is_seen(job.fingerprint)
    assert reloaded.get_seen_count() == 1
    assert reloaded.get(job.fingerprint)["spec"] == "Leads"


def test_alerted_flag_never_reverts(tmp_path):
    state = StateManager(tmp_path / "seen.json")
    job = make_job()
    state.record_job(job, score=9.5, action="instant", alerted=True)
    state.record_job(job, score=4.0, action="discard", alerted=False)
    assert state.is_alerted(job.fingerprint)


def test_corrupt_state_file_stops_instead_of_resetting(tmp_path):
    state_file = tmp_path / "seen_jobs.json"
    state_file.write_text('{"abc": {"alerted": true}\n<<<<<<< HEAD\n')
    with pytest.raises(StateFileError):
        StateManager(state_file)


def test_save_is_atomic_and_leaves_no_temp_file(tmp_path):
    state_file = tmp_path / "seen_jobs.json"
    state = StateManager(state_file)
    state.record_job(make_job(), score=7.5, action="digest")
    state.save()
    assert json.loads(state_file.read_text())
    assert not list(tmp_path.glob(".*.tmp"))


def test_legacy_duplicate_record_is_adopted_with_alerted_state(tmp_path):
    """Records written under an unstable (per-process) id are recognised by content."""
    state = StateManager(tmp_path / "seen.json")
    legacy = make_job(id="custom_0_918273645", source="custom", url="https://www.jobberman.com")
    state.record_job(legacy, score=8.0, action="digest", alerted=True)

    current = make_job(id="custom_" + stable_hash("https://www.jobberman.com", "Datadog", "Distributed Systems Lead"),
                       source="custom", url="https://www.jobberman.com")
    assert current.fingerprint != legacy.fingerprint

    alias = state.find_equivalent(current)
    assert alias == legacy.fingerprint
    state.adopt(current, alias)
    assert state.is_seen(current.fingerprint)
    assert state.is_alerted(current.fingerprint)


def test_touch_keeps_listed_postings_and_prune_drops_stale_ones(tmp_path):
    state = StateManager(tmp_path / "seen.json")
    old, listed = make_job(id="a"), make_job(id="b", title="Other Role")
    long_ago = datetime.now(timezone.utc) - timedelta(days=200)
    state.record_job(old, score=5.0, action="low_match")
    state.record_job(listed, score=5.0, action="low_match")
    for fp in (old.fingerprint, listed.fingerprint):
        state.records[fp]["last_seen_at"] = long_ago.isoformat()

    state.touch(listed.fingerprint)  # still present in a source today
    removed = state.prune(retention_days=90)

    assert removed == 1
    assert not state.is_seen(old.fingerprint)
    assert state.is_seen(listed.fingerprint)


def test_clear_keeps_a_backup(tmp_path):
    state_file = tmp_path / "seen.json"
    state = StateManager(state_file)
    state.record_job(make_job(), score=6.0, action="low_match")
    state.save()
    assert state.clear() == 1
    assert len(StateManager(state_file)) == 0
    assert list(tmp_path.glob("seen.json.*.bak"))
