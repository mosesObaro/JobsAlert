"""
Cross-source identity: one vacancy published on several platforms is alerted once.

The matching rules are deliberately conservative, and these tests pin both
directions: a confident duplicate is withheld, and anything weaker is kept. The
fixtures mirror what the live sources actually returned on 2026-11-19 — notably
Moniepoint's "Credit Risk Analyst" (a real Greenhouse/LinkedIn duplicate) and its
"Analytics Manager" openings, which share a company and title across Portugal,
Poland and Spain and are genuinely different jobs.
"""

from datetime import datetime, timezone
from typing import List
from unittest.mock import AsyncMock, patch

import pytest

from src.config import AppConfig, JobSpecConfig
from src.cross_source import (
    CrossSourceIndex,
    apply_reference,
    locations_overlap,
    normalize_company,
    normalize_title,
    preferred_copy,
)
from src.deduplication import StateManager, compute_job_fingerprint
from src.income_opportunities.deduplication import IncomeStateManager
from src.models import CrawlerHealth, JobPosting
from src.notifier.email_service import DeliveryResult
from src.pipeline import JobPipeline

pytestmark = pytest.mark.anyio


def job(**overrides) -> JobPosting:
    fields = dict(
        id="x", title="Credit Risk Analyst", company="Moniepoint", location="Lagos, Nigeria",
        is_remote=False, remote_scope="On-Site", url="https://example.com/1",
        description="Human Resources and recruitment work.", source="greenhouse",
        posted_at=datetime.now(timezone.utc),
    )
    fields.update(overrides)
    posting = JobPosting(**fields)
    if not posting.fingerprint:
        posting.fingerprint = compute_job_fingerprint(
            company=posting.company, title=posting.title,
            location_type=posting.remote_scope or posting.location,
            reference_id=posting.id, canonical_url=posting.url,
        )
    return posting


# --- normalisation primitives ------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("Moniepoint", "moniepoint"),
    ("Moniepoint Group", "moniepoint"),
    ("Moniepoint Technologies Limited", "moniepoint"),
    ("Acme Inc.", "acme"),
    ("Flutterwave", "flutterwave"),
])
def test_normalize_company_tolerates_org_suffixes(raw, expected):
    assert normalize_company(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("Credit Risk Analyst", "credit risk analyst"),
    ("Credit Risk Analyst (Lagos)", "credit risk analyst"),
    ("Credit  Risk — Analyst", "credit risk analyst"),
])
def test_normalize_title_drops_asides_and_punctuation(raw, expected):
    assert normalize_title(raw) == expected


@pytest.mark.parametrize("url, expected", [
    ("https://job-boards.greenhouse.io/moniepoint/jobs/4056914101", "greenhouse:4056914101"),
    ("https://jobs.lever.co/acme/1b2c3d4e-5678-90ab-cdef-112233445566", "lever:1b2c3d4e-5678-90ab-cdef-112233445566"),
    ("https://jobs.ashbyhq.com/lemfi/1b2c3d4e-5678-90ab-cdef-112233445566", "ashby:1b2c3d4e-5678-90ab-cdef-112233445566"),
    ("https://apply.workable.com/j/82E249C10F", "workable:82e249c10f"),
    ("https://www.linkedin.com/jobs/view/4463989511", None),
    ("", None),
])
def test_apply_reference_recognises_employer_boards_only(url, expected):
    """An aggregator's id identifies its own copy, not the vacancy."""
    assert apply_reference(url) == expected


@pytest.mark.parametrize("left, right, expected", [
    ("Lagos, Nigeria", "Nigeria", True),
    ("Remote, Nigeria", "Lagos, Lagos State, Nigeria", True),
    ("Remote, Portugal", "Remote, Nigeria", False),
    ("Nairobi, Kenya", "Remote, Nigeria", False),
    ("Lagos, Nigeria", "", False),
    ("", "", False),
    ("Somewhere Unrecognised", "Lagos, Nigeria", False),
])
def test_locations_overlap_is_conservative(left, right, expected):
    """An unresolvable location never counts as compatible."""
    assert locations_overlap(left, right) is expected


# --- the index ---------------------------------------------------------------

def test_same_vacancy_from_two_sources_is_matched():
    index = CrossSourceIndex()
    index.add(job(id="gh1", source="greenhouse", location="Lagos, Nigeria"))

    duplicate = index.find_duplicate(
        job(id="li1", source="linkedin", company="Moniepoint Group", location="Nigeria",
            url="https://www.linkedin.com/jobs/view/4463989511")
    )

    assert duplicate is not None
    assert duplicate.source == "greenhouse"
    assert "same company, title and location" in duplicate.reason


def test_same_employer_reference_matches_even_when_titles_differ():
    """The strongest evidence: both links point at one employer job id."""
    index = CrossSourceIndex()
    index.add(job(id="gh1", source="greenhouse", url="https://job-boards.greenhouse.io/acme/jobs/999"))

    duplicate = index.find_duplicate(
        job(id="rss1", source="rss", title="Risk Analyst, Credit (Remote)",
            url="https://job-boards.greenhouse.io/acme/jobs/999")
    )

    assert duplicate is not None
    assert "application reference" in duplicate.reason


def test_two_openings_from_the_same_source_are_never_matched():
    """Moniepoint lists "Analytics Manager" in Portugal, Poland and Spain; a
    source listing a role twice is listing two real openings."""
    index = CrossSourceIndex()
    index.add(job(id="gh1", source="greenhouse", title="Analytics Manager", location="Remote, Portugal"))

    assert index.find_duplicate(
        job(id="gh2", source="greenhouse", title="Analytics Manager", location="Remote, Poland")
    ) is None


def test_same_company_and_title_in_different_countries_are_kept_apart():
    """The hazard this guards: hiding a Nigerian role behind a Portuguese one."""
    index = CrossSourceIndex()
    index.add(job(id="gh1", source="greenhouse", title="Analytics Manager", location="Remote, Portugal"))

    assert index.find_duplicate(
        job(id="li1", source="linkedin", title="Analytics Manager", location="Lagos, Nigeria")
    ) is None


def test_an_unknown_location_is_not_assumed_compatible():
    index = CrossSourceIndex()
    index.add(job(id="gh1", source="greenhouse", location="Lagos, Nigeria"))

    assert index.find_duplicate(job(id="li1", source="linkedin", location="Unknown")) is None


def test_a_missing_description_does_not_prevent_matching():
    """LinkedIn cards carry no description; matching must not depend on one."""
    index = CrossSourceIndex()
    index.add(job(id="gh1", source="greenhouse", location="Lagos, Nigeria"))

    duplicate = index.find_duplicate(
        job(id="li1", source="linkedin", description="", company="Moniepoint Group", location="Nigeria")
    )
    assert duplicate is not None


def test_different_companies_are_never_matched():
    index = CrossSourceIndex()
    index.add(job(id="gh1", source="greenhouse", company="Moniepoint", location="Lagos, Nigeria"))

    assert index.find_duplicate(
        job(id="li1", source="linkedin", company="Flutterwave", location="Lagos, Nigeria")
    ) is None


def test_preferred_copy_picks_the_employer_board():
    chosen = preferred_copy([
        job(id="li", source="linkedin"),
        job(id="gh", source="greenhouse"),
        job(id="rss", source="rss"),
    ])
    assert chosen.source == "greenhouse"


# --- migration safety --------------------------------------------------------

def test_index_built_from_existing_records_keeps_them_matchable():
    records = {
        "fp_old": {
            "company": "Moniepoint", "title": "Credit Risk Analyst",
            "canonical_url": "https://job-boards.greenhouse.io/moniepoint/jobs/1",
            "source": "greenhouse", "location": "Lagos, Nigeria", "alerted": True,
        }
    }
    duplicate = CrossSourceIndex(records).find_duplicate(
        job(id="li1", source="linkedin", company="Moniepoint Group", location="Nigeria")
    )
    assert duplicate is not None
    assert duplicate.alerted is True
    assert duplicate.fingerprint == "fp_old"


def test_a_record_written_before_location_existed_does_not_match_on_identity():
    """Backward compatibility: no stored location means no confident match."""
    legacy = {
        "fp_legacy": {
            "company": "Moniepoint", "title": "Credit Risk Analyst",
            "canonical_url": "https://www.linkedin.com/jobs/view/1",
            "source": "linkedin", "alerted": True,
        }
    }
    assert CrossSourceIndex(legacy).find_duplicate(
        job(id="gh1", source="greenhouse", location="Lagos, Nigeria")
    ) is None


def test_recording_a_job_does_not_change_its_fingerprint_or_alerted_state(tmp_path):
    """The additive `location` field must not disturb existing identities."""
    state = StateManager(tmp_path / "seen.json")
    posting = job(id="gh1", source="greenhouse")
    original = posting.fingerprint

    state.record_job(posting, 8.0, "digest", alerted=True)
    state.save()

    reloaded = StateManager(tmp_path / "seen.json")
    entry = reloaded.get(original)
    assert entry is not None, "the record must still be keyed by its original fingerprint"
    assert reloaded.is_alerted(original) is True
    assert entry["location"] == "Lagos, Nigeria"
    assert compute_job_fingerprint(
        company=posting.company, title=posting.title,
        location_type=posting.remote_scope or posting.location,
        reference_id=posting.id, canonical_url=posting.url,
    ) == original


# --- through the pipeline -----------------------------------------------------

def make_config() -> AppConfig:
    config = AppConfig()
    # No must-have skills: a LinkedIn card carries no description, and these
    # tests are about cross-source identity, not about scoring.
    config.job_specs = [JobSpecConfig(
        name="HR", target_roles=["Credit Risk Analyst", "Analytics Manager"],
        preferred_locations=["Remote", "Worldwide", "Nigeria", "Portugal"],
        salary_floor_usd=10000,
    )]
    config.online_income.include_in_daily_digest = False
    config.link_verification.enabled = False
    config.schedule.instant_alert_threshold = 9.9
    return config


def make_pipeline(tmp_path, config: AppConfig) -> JobPipeline:
    return JobPipeline(config=config, state_manager=StateManager(tmp_path / "seen.json"),
                       income_state_manager=IncomeStateManager(tmp_path / "income.json"))


async def run(pipeline: JobPipeline, jobs: List[JobPosting], result: DeliveryResult, **kwargs):
    with patch("src.pipeline.run_all_collectors", new_callable=AsyncMock) as collectors, \
         patch.object(pipeline.notifier, "send_digest", new_callable=AsyncMock) as send_digest:
        collectors.return_value = (jobs, [CrawlerHealth(source_name="greenhouse", jobs_found=len(jobs))])
        send_digest.return_value = result
        summary, scored = await pipeline.execute(dry_run=False, send_email=True, **kwargs)
        return summary, scored, send_digest


async def test_one_vacancy_on_two_sources_is_alerted_once(tmp_path):
    greenhouse = job(id="gh1", source="greenhouse", location="Lagos, Nigeria",
                     url="https://job-boards.greenhouse.io/moniepoint/jobs/1")
    linkedin = job(id="li1", source="linkedin", company="Moniepoint Group", location="Nigeria",
                   description="", url="https://www.linkedin.com/jobs/view/1")

    pipeline = make_pipeline(tmp_path, make_config())
    summary, _, send = await run(pipeline, [greenhouse, linkedin], DeliveryResult(ok=True))

    alerted = [j.job.source for j in send.call_args.kwargs["jobs"]]
    assert alerted == ["greenhouse"], "the employer board copy is the one to send"
    assert summary.cross_source_duplicates == 1
    # The withheld copy is recorded, not queued for retry.
    assert summary.pending_alerts == 0
    assert pipeline.state_manager.is_seen(linkedin.fingerprint)
    assert not pipeline.state_manager.is_alerted(linkedin.fingerprint)
    assert pipeline.state_manager.is_alerted(greenhouse.fingerprint)


async def test_a_copy_is_not_alerted_when_the_other_source_was_alerted_earlier(tmp_path):
    config = make_config()
    first = make_pipeline(tmp_path, config)
    await run(first, [job(id="gh1", source="greenhouse", location="Lagos, Nigeria")], DeliveryResult(ok=True))

    later = make_pipeline(tmp_path, config)
    summary, _, send = await run(
        later,
        [job(id="li1", source="linkedin", company="Moniepoint Group", location="Nigeria", description="")],
        DeliveryResult(ok=True),
    )

    assert not send.called, "nothing new to send: the vacancy was already alerted via Greenhouse"
    assert summary.cross_source_duplicates == 1


async def test_genuinely_different_vacancies_are_both_alerted(tmp_path):
    portugal = job(id="gh1", source="greenhouse", title="Analytics Manager", location="Remote, Portugal")
    nigeria = job(id="li1", source="linkedin", title="Analytics Manager", location="Lagos, Nigeria", description="")

    pipeline = make_pipeline(tmp_path, make_config())
    summary, _, send = await run(pipeline, [portugal, nigeria], DeliveryResult(ok=True))

    assert summary.cross_source_duplicates == 0
    assert {j.job.fingerprint for j in send.call_args.kwargs["jobs"]} == {portugal.fingerprint, nigeria.fingerprint}


async def test_an_undelivered_alert_is_still_retried(tmp_path):
    """Cross-source handling must not weaken delivery-before-persist."""
    pipeline = make_pipeline(tmp_path, make_config())
    summary, _, _ = await run(pipeline, [job(id="gh1", source="greenhouse")],
                              DeliveryResult(ok=False, provider="resend", error="HTTP 500"))

    assert summary.pending_alerts == 1
    assert not pipeline.state_manager.is_seen(job(id="gh1", source="greenhouse").fingerprint)
