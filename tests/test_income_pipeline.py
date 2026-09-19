import asyncio
from typing import List

from src import paths
from src.income_opportunities.config import OnlineIncomeConfig
from src.income_opportunities.deduplication import IncomeStateManager
from src.income_opportunities.pipeline import IncomeOpportunityPipeline
from src.notifier.email_service import DeliveryResult, EmailNotifier


class RecordingNotifier(EmailNotifier):
    """Captures what would be emailed; `ok` controls whether sends succeed."""

    def __init__(self, ok: bool = True):
        super().__init__()
        self.ok = ok
        self.digests: List[List[str]] = []
        self.instants: List[str] = []

    async def send_income_digest(self, opportunities, *args, **kwargs):
        self.digests.append([o.opportunity.fingerprint for o in opportunities])
        return DeliveryResult(ok=self.ok, provider="test", error=None if self.ok else "provider down")

    async def send_income_immediate(self, scored, *args, **kwargs):
        self.instants.append(scored.opportunity.fingerprint)
        return DeliveryResult(ok=self.ok, provider="test", error=None if self.ok else "provider down")


def make_pipeline(tmp_path, notifier=None, **config_overrides) -> IncomeOpportunityPipeline:
    config = OnlineIncomeConfig(eligible_countries=["Nigeria", "Worldwide"], require_link_verification=False, **config_overrides)
    return IncomeOpportunityPipeline(config=config, state_manager=IncomeStateManager(tmp_path / "seen_income.json"), notifier=notifier)


def test_income_pipeline_dry_run(tmp_path):
    pipeline = make_pipeline(tmp_path, instant_alert_score=9.0)
    summary, scored = asyncio.run(pipeline.execute(dry_run=True, send_email=False, force_all=True))

    assert summary.total_fetched > 0
    assert len(scored) > 0
    assert summary.instant_matches + summary.digest_matches > 0
    assert summary.mode == "dry_run"
    assert len(pipeline.state_manager.get_all_records()) == 0  # dry runs never persist
    assert paths.data_file(paths.EMAIL_PREVIEW).exists()  # the preview is saved, not discarded


def test_failed_delivery_keeps_candidates_pending_for_the_next_run(tmp_path):
    failing = RecordingNotifier(ok=False)
    pipeline = make_pipeline(tmp_path, notifier=failing, instant_alert_score=11.0)
    summary, _ = asyncio.run(pipeline.execute(dry_run=False, send_email=True))

    state = pipeline.state_manager
    assert failing.digests, "a digest was attempted"
    assert summary.delivery_errors
    assert summary.pending_alerts == len(failing.digests[0]) + (summary.digest_matches - len(failing.digests[0]))
    assert not any(state.is_seen(fp) for fp in failing.digests[0]), "undelivered items must stay unseen"

    working = RecordingNotifier(ok=True)
    retry = make_pipeline(tmp_path, notifier=working, instant_alert_score=11.0)
    retry.state_manager = IncomeStateManager(tmp_path / "seen_income.json")
    asyncio.run(retry.execute(dry_run=False, send_email=True))
    assert working.digests[0] == failing.digests[0]  # the same items are delivered on the retry
    assert all(retry.state_manager.is_alerted(fp) for fp in working.digests[0])


def test_digest_cap_queues_remaining_items_without_repeats(tmp_path):
    notifier = RecordingNotifier(ok=True)
    first = make_pipeline(tmp_path, notifier=notifier, instant_alert_score=11.0, max_digest_items=2)
    summary, _ = asyncio.run(first.execute(dry_run=False, send_email=True))
    assert len(notifier.digests[0]) == 2
    assert summary.pending_alerts == summary.digest_matches - 2

    second = make_pipeline(tmp_path, notifier=notifier, instant_alert_score=11.0, max_digest_items=2)
    asyncio.run(second.execute(dry_run=False, send_email=True))
    assert len(notifier.digests) == 2
    assert not set(notifier.digests[0]) & set(notifier.digests[1]), "queued items arrive later, never twice"


def test_live_run_without_sending_records_only_non_candidates(tmp_path):
    pipeline = make_pipeline(tmp_path, instant_alert_score=11.0)
    summary, scored = asyncio.run(pipeline.execute(dry_run=False, send_email=False, force_all=True))
    records = pipeline.state_manager.get_all_records()
    candidates = {s.opportunity.fingerprint for s in scored if s.action in ("instant", "digest")}
    assert summary.pending_alerts == len(candidates)
    assert not candidates & set(records)
    assert all(not r["alerted"] for r in records.values())
