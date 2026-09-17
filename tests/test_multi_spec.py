"""
Unit and integration tests for Multi-Spec Job Search and Consolidated Reporting.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import pytest

from src.config import AppConfig, JobSpecConfig
from src.deduplication import StateManager
from src.income_opportunities.deduplication import IncomeStateManager
from src.income_opportunities.models import IncomeCollectorHealth
from src.models import CrawlerHealth, JobPosting, MatchBreakdown, ScoredJob, SpecMatchGroup
from src.notifier.email_service import EmailNotifier
from src.pipeline import JobPipeline
from src.scoring import ScoringEngine


@pytest.fixture
def multi_spec_config():
    config = AppConfig()
    config.job_specs = [
        JobSpecConfig(
            name="HR Remote Roles",
            keywords=["HR", "Human Resources", "Recruiter", "People Operations"],
            target_roles=["HR Generalist", "Recruiter", "People Operations Specialist"],
            must_have_skills=["Human Resources", "Recruitment"],
            nice_to_have_skills=["BambooHR", "Workday"],
            remote=True,
            preferred_locations=["Remote", "Worldwide", "Nigeria"],
            salary_floor_usd=10000.0,
        ),
        JobSpecConfig(
            name="Junior Swift/iOS Developer — Remote Contract",
            keywords=["Swift", "iOS", "SwiftUI", "UIKit"],
            target_roles=["Junior Swift Developer", "Junior iOS Developer", "iOS Developer"],
            seniority="junior",
            experience_years=1,
            technologies=["Swift", "SwiftUI", "UIKit", "Xcode"],
            must_have_skills=["Swift", "iOS"],
            nice_to_have_skills=["SwiftUI", "Git"],
            employment_type="contract",
            remote=True,
            preferred_locations=["Remote", "Worldwide"],
            salary_floor_usd=12000.0,
        ),
        JobSpecConfig(
            name="Junior Data Analyst — Remote Contract",
            keywords=["Data Analyst", "SQL", "Excel", "Python"],
            target_roles=["Junior Data Analyst", "Data Analyst"],
            seniority="junior",
            experience_years=1,
            technologies=["SQL", "Python", "Tableau", "Power BI"],
            must_have_skills=["SQL", "Data Analysis"],
            nice_to_have_skills=["Python", "Power BI"],
            employment_type="contract",
            remote=True,
            preferred_locations=["Remote", "Worldwide"],
            salary_floor_usd=12000.0,
        ),
    ]
    return config


@pytest.fixture
def hr_job():
    return JobPosting(
        id="job_hr_1",
        fingerprint="fp_hr_1",
        title="People Operations & HR Generalist",
        company="Moniepoint",
        location="Remote (Nigeria)",
        is_remote=True,
        remote_scope="Worldwide",
        url="https://boards.greenhouse.io/moniepoint/jobs/101",
        description="Employee lifecycle, onboarding, HRIS BambooHR, recruitment, employee relations.",
        salary_min=18000.0,
        salary_max=28000.0,
        source="greenhouse",
        posted_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def swift_contract_job():
    return JobPosting(
        id="job_swift_1",
        fingerprint="fp_swift_1",
        title="Junior iOS Developer (Contract)",
        company="Novacrest Digital",
        location="Remote (Worldwide)",
        is_remote=True,
        remote_scope="Worldwide",
        employment_type="contract",
        seniority="junior",
        url="https://jobs.lever.co/novacrest/202",
        description="6-month remote contract. Build iOS apps with Swift and SwiftUI, integrate REST APIs. Junior-friendly.",
        salary_min=24000.0,
        salary_max=36000.0,
        source="lever",
        posted_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def data_analyst_contract_job():
    return JobPosting(
        id="job_data_1",
        fingerprint="fp_data_1",
        title="Junior Data Analyst (Remote Contract)",
        company="DataPulse Analytics",
        location="Remote (Worldwide)",
        is_remote=True,
        remote_scope="Worldwide",
        employment_type="contract",
        seniority="junior",
        url="https://jobs.ashbyhq.com/datapulse/303",
        description="Remote contract for Junior Data Analyst. SQL queries, Tableau dashboards, and Python analysis.",
        salary_min=20000.0,
        salary_max=32000.0,
        source="ashby",
        posted_at=datetime.now(timezone.utc),
    )


# ==============================================================================
# 1. Configuration Model & Fallback Tests
# ==============================================================================

def test_job_spec_config_defaults_and_fallback():
    # Test AppConfig with no job_specs falls back to profile + filters
    config = AppConfig()
    config.job_specs = []
    config.profile.candidate_name = "Solo Dev"
    config.profile.target_roles = ["Frontend Engineer"]
    config.filters.must_have_skills = ["TypeScript", "React"]

    specs = config.get_effective_job_specs()
    assert len(specs) == 1
    assert specs[0].name == "Solo Dev"
    assert "Frontend Engineer" in specs[0].target_roles
    assert "TypeScript" in specs[0].must_have_skills


def test_job_spec_config_explicit(multi_spec_config):
    specs = multi_spec_config.get_effective_job_specs()
    assert len(specs) == 3
    assert specs[0].name == "HR Remote Roles"
    assert specs[1].name == "Junior Swift/iOS Developer — Remote Contract"
    assert specs[1].employment_type == "contract"
    assert specs[1].seniority == "junior"
    assert specs[2].name == "Junior Data Analyst — Remote Contract"


# ==============================================================================
# 2. Independent Spec Scoring Tests
# ==============================================================================

def test_independent_scoring_across_specs(multi_spec_config, hr_job, swift_contract_job, data_analyst_contract_job):
    engine = ScoringEngine(multi_spec_config)
    specs = multi_spec_config.get_effective_job_specs()
    hr_spec = specs[0]
    swift_spec = specs[1]
    data_spec = specs[2]

    # HR Job scored against HR Spec vs Swift Spec
    scored_hr_on_hr = engine.score_job(hr_job, spec=hr_spec)
    scored_hr_on_swift = engine.score_job(hr_job, spec=swift_spec)

    assert scored_hr_on_hr.score >= 8.0
    assert scored_hr_on_hr.spec_name == "HR Remote Roles"
    assert scored_hr_on_swift.score < 7.0
    assert scored_hr_on_swift.action in ["low_match", "discard"]

    # Swift Contract Job scored against Swift Spec vs Data Analyst Spec vs HR Spec
    scored_swift_on_swift = engine.score_job(swift_contract_job, spec=swift_spec)
    scored_swift_on_hr = engine.score_job(swift_contract_job, spec=hr_spec)

    assert scored_swift_on_swift.score >= 8.5
    assert scored_swift_on_swift.spec_name == "Junior Swift/iOS Developer — Remote Contract"
    assert any("Contract / Freelance role match" in h for h in scored_swift_on_swift.breakdown.highlights)
    assert any("Junior-friendly opportunity" in h for h in scored_swift_on_swift.breakdown.highlights)
    assert scored_swift_on_hr.score < 7.0
    assert scored_swift_on_hr.action in ["low_match", "discard"]

    # Data Analyst Job scored against Data Spec
    scored_data_on_data = engine.score_job(data_analyst_contract_job, spec=data_spec)
    assert scored_data_on_data.score >= 8.5
    assert scored_data_on_data.spec_name == "Junior Data Analyst — Remote Contract"
    assert any("Contract / Freelance role match" in h for h in scored_data_on_data.breakdown.highlights)


# ==============================================================================
# 3. Email Template & Reporting Tests (Consolidated Digest & Empty Specs)
# ==============================================================================

def test_render_digest_with_spec_groups(multi_spec_config, hr_job, swift_contract_job):
    notifier = EmailNotifier()
    engine = ScoringEngine(multi_spec_config)
    specs = multi_spec_config.get_effective_job_specs()

    scored_hr = engine.score_job(hr_job, spec=specs[0])
    scored_swift = engine.score_job(swift_contract_job, spec=specs[1])

    spec_groups = [
        SpecMatchGroup(
            spec_name="HR Remote Roles",
            jobs=[scored_hr],
            unalerted_jobs=[scored_hr],
            total_matches=1,
        ),
        SpecMatchGroup(
            spec_name="Junior Swift/iOS Developer — Remote Contract",
            jobs=[scored_swift],
            unalerted_jobs=[scored_swift],
            total_matches=1,
        ),
        SpecMatchGroup(
            spec_name="Junior Data Analyst — Remote Contract",
            jobs=[],
            unalerted_jobs=[],
            total_matches=0,
        ),
    ]

    subject, html_content, text_content = notifier.render_digest(
        jobs=[scored_hr, scored_swift],
        config=multi_spec_config,
        spec_groups=spec_groups,
    )

    # Subject & Header Title assertions
    assert "2 Target Roles" in subject or "2 High-Match" in subject
    assert "2 High-Match Opportunities Found" in html_content

    # HTML assertions
    assert "HR Remote Roles" in html_content
    assert "Junior Swift/iOS Developer — Remote Contract" in html_content
    assert "Junior Data Analyst — Remote Contract" in html_content
    assert "People Operations &amp; HR Generalist" in html_content or "People Operations & HR Generalist" in html_content
    assert "Junior iOS Developer (Contract)" in html_content
    assert "No new matching jobs found for this specification today." in html_content

    # Plaintext assertions
    assert "SPECIFICATION: HR REMOTE ROLES (1 Matches)" in text_content
    assert "SPECIFICATION: JUNIOR SWIFT/IOS DEVELOPER — REMOTE CONTRACT (1 Matches)" in text_content
    assert "SPECIFICATION: JUNIOR DATA ANALYST — REMOTE CONTRACT (0 Matches)" in text_content
    assert "No new matching jobs found for this specification today." in text_content


def test_format_digest_subject_with_spec_groups(multi_spec_config, hr_job, swift_contract_job):
    notifier = EmailNotifier()
    engine = ScoringEngine(multi_spec_config)
    specs = multi_spec_config.get_effective_job_specs()

    scored_hr = engine.score_job(hr_job, spec=specs[0])
    scored_swift = engine.score_job(swift_contract_job, spec=specs[1])

    spec_groups = [
        SpecMatchGroup(spec_name="HR Remote Roles", jobs=[scored_hr], unalerted_jobs=[scored_hr], total_matches=1),
        SpecMatchGroup(spec_name="Junior Swift/iOS Developer", jobs=[scored_swift], unalerted_jobs=[scored_swift], total_matches=1),
    ]

    subject = notifier.format_digest_subject(spec_groups=spec_groups)
    assert "[Job Alert]" in subject
    assert "2 High-Match Opportunities Found" in subject


# ==============================================================================
# 4. Pipeline Integration & Deduplication Across Multi-Specs
# ==============================================================================

@pytest.mark.anyio
async def test_multi_spec_pipeline_run(multi_spec_config, hr_job, swift_contract_job, data_analyst_contract_job, tmp_path):
    state_file = tmp_path / "test_multi_spec_state.json"
    income_state_file = tmp_path / "test_multi_spec_income_state.json"

    state_mgr = StateManager(filepath=state_file)
    income_state_mgr = IncomeStateManager(filepath=income_state_file)

    multi_spec_config.link_verification.enabled = False
    multi_spec_config.online_income.include_in_daily_digest = False
    multi_spec_config.delivery.send_daily_digest = True

    pipeline = JobPipeline(
        config=multi_spec_config,
        state_manager=state_mgr,
        income_state_manager=income_state_mgr,
    )

    mock_jobs = [hr_job, swift_contract_job, data_analyst_contract_job]
    mock_health = [CrawlerHealth(source_name="custom", status="healthy", jobs_found=3, latency_ms=10.0)]

    with patch("src.pipeline.run_all_collectors", new_callable=AsyncMock) as mock_rc, \
         patch("src.pipeline.run_all_income_collectors", new_callable=AsyncMock) as mock_ric, \
         patch.object(pipeline.notifier, "send_digest", new_callable=AsyncMock) as mock_send_digest:

        mock_rc.return_value = (mock_jobs, mock_health)
        mock_ric.return_value = ([], [])
        mock_send_digest.return_value = True

        # First Run: send email
        summary1, scored_jobs1 = await pipeline.execute(
            dry_run=False,
            send_email=True,
            force_all=True,
        )
        assert summary1.total_fetched == 3
        assert summary1.emails_dispatched >= 1

        # Verify send_digest received 3 spec_groups with matching jobs
        assert mock_send_digest.called
        call_kwargs = mock_send_digest.call_args.kwargs
        sent_spec_groups = call_kwargs["spec_groups"]
        assert len(sent_spec_groups) == 3

        hr_group = next(g for g in sent_spec_groups if g.spec_name == "HR Remote Roles")
        swift_group = next(g for g in sent_spec_groups if "Swift" in g.spec_name)
        data_group = next(g for g in sent_spec_groups if "Data Analyst" in g.spec_name)

        assert len(hr_group.jobs) >= 1
        assert len(swift_group.jobs) >= 1
        assert len(data_group.jobs) >= 1

        # Verify state persistence marked all fingerprints alerted
        assert state_mgr.is_alerted(hr_job.fingerprint)
        assert state_mgr.is_alerted(swift_contract_job.fingerprint)
        assert state_mgr.is_alerted(data_analyst_contract_job.fingerprint)

        # Second Run: Since all jobs are already alerted, send_digest will not be invoked
        mock_send_digest.reset_mock()
        summary2, scored_jobs2 = await pipeline.execute(
            dry_run=False,
            send_email=True,
            force_all=False,
        )
        assert summary2.emails_dispatched == 0
        mock_send_digest.assert_not_called()
