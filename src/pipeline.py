"""
JobsAlert Main Pipeline Orchestrator.
Coordinates collection, deduplication, scoring, triage, notification, and state persistence
for both Target Career Roles and Online Income Opportunities.
"""

from __future__ import annotations
import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.collectors import run_all_collectors
from src.config import AppConfig
from src.deduplication import StateManager
from src.income_opportunities.collectors import run_all_income_collectors
from src.income_opportunities.deduplication import IncomeStateManager
from src.income_opportunities.models import (
    EligibilityStatus,
    IncomeCollectorHealth,
    IncomeMatchBreakdown,
    IncomeRunSummary,
    OnlineIncomeOpportunity,
    OpportunityStatus,
    ScoredOpportunity,
    SourceTelemetry,
)
from src.income_opportunities.scoring import IncomeScoringEngine
from src.income_opportunities.verifier import IncomeOpportunityVerifier
from src.models import CrawlerHealth, JobPosting, MatchBreakdown, RunSummary, ScoredJob
from src.notifier.email_service import EmailNotifier
from src.scoring import ScoringEngine
from src.verifier import LinkVerifier

RUN_LOGS_FILE = Path(__file__).resolve().parent.parent / "data" / "run_logs.json"
INCOME_RUN_LOGS_FILE = Path(__file__).resolve().parent.parent / "data" / "income_run_logs.json"


class JobPipeline:
    def __init__(
        self,
        config: AppConfig,
        state_manager: Optional[StateManager] = None,
        income_state_manager: Optional[IncomeStateManager] = None,
    ):
        self.config = config
        self.state_manager = state_manager or StateManager()
        self.income_state_manager = income_state_manager or IncomeStateManager()
        self.scoring_engine = ScoringEngine(config)
        self.income_scoring_engine = IncomeScoringEngine(config.online_income)
        self.notifier = EmailNotifier()
        self.link_verifier = LinkVerifier()
        self.income_verifier = IncomeOpportunityVerifier()
        self.latest_income_opportunities: List[ScoredOpportunity] = []

    async def execute(
        self,
        dry_run: bool = True,
        send_email: bool = False,
        force_all: bool = False,
        immediate_only: bool = False,
    ) -> Tuple[RunSummary, List[ScoredJob]]:
        """
        Executes the unified job intelligence and online income pipeline.
        """
        start_time = time.perf_counter()
        run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        include_income = (
            self.config.online_income.enabled
            and self.config.online_income.include_in_daily_digest
        )

        print(f"\n🚀 [PIPELINE START] Run ID: {run_id} | Mode: {'DRY RUN' if dry_run else 'LIVE'} | Profile: {self.config.profile.candidate_name}")

        # 1. Collect from enabled job & income sources concurrently
        if include_income:
            (raw_jobs, health_reports), (raw_income, income_health) = await asyncio.gather(
                run_all_collectors(self.config),
                run_all_income_collectors(self.config.online_income),
            )
            print(f"📥 [COLLECTED] {len(raw_jobs)} career postings & {len(raw_income)} online income tracks.")
        else:
            raw_jobs, health_reports = await run_all_collectors(self.config)
            raw_income, income_health = [], []
            print(f"📥 [COLLECTED] {len(raw_jobs)} total job postings across {len(health_reports)} source connectors.")

        income_telemetry_map: Dict[str, SourceTelemetry] = {}
        for h in income_health:
            income_telemetry_map[h.source_name] = h.telemetry or SourceTelemetry(source_name=h.source_name, discovered=h.opportunities_found)

        # 2. Filter & Deduplicate Conventional Jobs
        new_jobs: List[JobPosting] = []
        seen_count = 0
        for job in raw_jobs:
            if not force_all and self.state_manager.is_seen(job.fingerprint):
                seen_count += 1
                continue
            new_jobs.append(job)

        print(f"🔍 [DEDUPLICATION - JOBS] {seen_count} previously processed jobs filtered out. {len(new_jobs)} unique candidates to verify & score.")

        # 3. Verify Job Links
        valid_jobs: List[JobPosting] = []
        invalid_jobs: List[Tuple[JobPosting, str]] = []
        if self.config.link_verification.enabled and new_jobs:
            print(f"🔗 [LINK VERIFICATION - JOBS] Verifying {len(new_jobs)} candidate URLs...")
            valid_jobs, invalid_jobs = await self.link_verifier.verify_jobs_batch(new_jobs, self.config.link_verification)
            if invalid_jobs:
                print(f"⚠️ [LINK VERIFICATION - JOBS] Excluded {len(invalid_jobs)} expired or closed job posting(s).")
        else:
            valid_jobs = new_jobs

        # 4. Score Conventional Jobs
        scored_jobs: List[ScoredJob] = []
        discarded: List[ScoredJob] = []
        low_matches: List[ScoredJob] = []
        digest_matches: List[ScoredJob] = []
        instant_matches: List[ScoredJob] = []

        for inv_job, reason in invalid_jobs:
            inv_job.is_verified = False
            inv_job.verification_status = reason
            breakdown = MatchBreakdown(
                penalties_applied=[f"Link Inactive/Expired ({reason})"],
                highlights=[f"Discarded: Link is dead or position is closed ({reason})"],
                is_verified=False
            )
            s_job = ScoredJob(
                job=inv_job,
                score=0.0,
                action="discard",
                breakdown=breakdown,
            )
            scored_jobs.append(s_job)
            discarded.append(s_job)

        for job in valid_jobs:
            scored = self.scoring_engine.score_job(job)
            scored.breakdown.is_verified = True
            scored_jobs.append(scored)

            if scored.action == "discard":
                discarded.append(scored)
            elif scored.action == "low_match":
                low_matches.append(scored)
            elif scored.action == "digest":
                digest_matches.append(scored)
            elif scored.action == "instant":
                instant_matches.append(scored)

        digest_matches.sort(key=lambda x: x.score, reverse=True)
        instant_matches.sort(key=lambda x: x.score, reverse=True)
        all_alert_jobs = instant_matches + digest_matches

        # 5. Deduplicate, Verify, Quality Gate & Score Online Income Opportunities
        scored_income_opps: List[ScoredOpportunity] = []
        instant_income_matches: List[ScoredOpportunity] = []
        digest_income_matches: List[ScoredOpportunity] = []
        low_income_matches: List[ScoredOpportunity] = []
        discarded_income: List[ScoredOpportunity] = []
        new_income: List[OnlineIncomeOpportunity] = []
        rejected_income: List[OnlineIncomeOpportunity] = []
        income_quality_rejected = 0
        income_ineligible = 0

        if include_income and raw_income:
            for opp in raw_income:
                fp = opp.fingerprint
                if self.income_state_manager.is_dismissed(fp):
                    if opp.source in income_telemetry_map:
                        income_telemetry_map[opp.source].duplicates_removed += 1
                    continue
                if not force_all and self.income_state_manager.is_seen(fp):
                    if opp.source in income_telemetry_map:
                        income_telemetry_map[opp.source].duplicates_removed += 1
                    continue
                new_income.append(opp)

            print(f"🔍 [DEDUPLICATION - INCOME] {len(new_income)} unique income tracks to screen & score.")

            if new_income:
                valid_income, rejected_income = await self.income_verifier.verify_opportunities_batch(
                    new_income,
                    check_links=self.config.online_income.require_link_verification,
                    max_concurrency=15,
                )
            else:
                valid_income = []

            for rej in rejected_income:
                if rej.source in income_telemetry_map:
                    if rej.verification_status == "rejected":
                        income_telemetry_map[rej.source].hard_rejected += 1
                    else:
                        income_telemetry_map[rej.source].verification_failed += 1
                s_rej = self.income_scoring_engine.score_opportunity(rej)
                scored_income_opps.append(s_rej)
                discarded_income.append(s_rej)

            for opp in valid_income:
                s_opp = self.income_scoring_engine.score_opportunity(opp)
                scored_income_opps.append(s_opp)
                telemetry = income_telemetry_map.get(opp.source)

                if not s_opp.breakdown.passed_quality_gate:
                    income_quality_rejected += 1
                    if telemetry:
                        telemetry.quality_rejected += 1
                    discarded_income.append(s_opp)
                elif s_opp.breakdown.eligibility_status == EligibilityStatus.INELIGIBLE.value:
                    income_ineligible += 1
                    if telemetry:
                        telemetry.ineligible += 1
                    discarded_income.append(s_opp)
                elif s_opp.action == "discard":
                    discarded_income.append(s_opp)
                elif s_opp.action == "low_match":
                    low_income_matches.append(s_opp)
                    if telemetry:
                        telemetry.verified += 1
                elif s_opp.action == "digest":
                    digest_income_matches.append(s_opp)
                    if telemetry:
                        telemetry.verified += 1
                        telemetry.high_quality += 1
                elif s_opp.action == "instant":
                    instant_income_matches.append(s_opp)
                    if telemetry:
                        telemetry.verified += 1
                        telemetry.high_quality += 1

            digest_income_matches.sort(key=lambda x: (x.score, x.breakdown.quality_score, x.breakdown.side_job_fit_score), reverse=True)
            instant_income_matches.sort(key=lambda x: (x.score, x.breakdown.quality_score, x.breakdown.side_job_fit_score), reverse=True)

        max_income_digest = self.config.online_income.max_digest_items or 5
        all_alert_income = (instant_income_matches + digest_income_matches)[:max_income_digest]
        self.latest_income_opportunities = scored_income_opps

        print(f"📊 [SCORING RESULTS]")
        print(f"   ★ Career Instant Matches (9.0+):   {len(instant_matches)}")
        print(f"   ✦ Career Strong Matches (7.0-8.9):  {len(digest_matches)}")
        print(f"   💰 Income Tracks Strong/Instant:     {len(all_alert_income)} (Quality Gated, Top {max_income_digest} Max)")
        print(f"   ✕ Total Discarded:                  {len(discarded) + len(discarded_income)}")

        # 6. Filter Unalerted Matches & Dispatch Notifications
        unalerted_instant_matches = [m for m in instant_matches if not self.state_manager.is_alerted(m.job.fingerprint)]
        unalerted_digest_matches = [m for m in digest_matches if not self.state_manager.is_alerted(m.job.fingerprint)]
        unalerted_alert_jobs = unalerted_instant_matches + unalerted_digest_matches

        unalerted_instant_income = [m for m in instant_income_matches if not self.income_state_manager.is_alerted(m.opportunity.fingerprint)]
        unalerted_digest_income = [m for m in digest_income_matches if not self.income_state_manager.is_alerted(m.opportunity.fingerprint)]
        unalerted_alert_income = (unalerted_instant_income + unalerted_digest_income)[:max_income_digest]

        already_sent_jobs_count = len(all_alert_jobs) - len(unalerted_alert_jobs)
        already_sent_income_count = len(instant_income_matches + digest_income_matches) - len(unalerted_instant_income + unalerted_digest_income)
        if already_sent_jobs_count > 0 or already_sent_income_count > 0:
            print(f"🛡️ [PREVIOUSLY SENT FILTER] Suppressed {already_sent_jobs_count} job(s) and {already_sent_income_count} income track(s) already emailed previously.")

        emails_dispatched = 0
        if not dry_run and send_email:
            # Immediate Job Alerts (New / Unalerted Only)
            if self.config.delivery.send_instant_alerts and unalerted_instant_matches:
                for match in unalerted_instant_matches:
                    success = await self.notifier.send_immediate(match, self.config, dry_run=False)
                    if success:
                        emails_dispatched += 1
                        self.state_manager.record_job(match.job, match.score, match.action, alerted=True)

            # Immediate Income Alerts (New / Unalerted Only)
            if self.config.delivery.send_instant_alerts and unalerted_instant_income:
                for match in unalerted_instant_income:
                    success = await self.notifier.send_income_immediate(
                        scored=match,
                        candidate_name=self.config.online_income.candidate_name,
                        recipient_email=self.config.delivery.recipient_email,
                        email_provider=self.config.delivery.email_provider,
                        from_email=self.config.delivery.from_email,
                        dry_run=False
                    )
                    if success:
                        emails_dispatched += 1
                        if match.opportunity.source in income_telemetry_map:
                            income_telemetry_map[match.opportunity.source].alerted += 1
                        self.income_state_manager.record_opportunity(match.opportunity, match.score, match.action, alerted=True)

            # Consolidated Daily Digest (New / Unalerted Only)
            if not immediate_only and self.config.delivery.send_daily_digest and (unalerted_alert_jobs or unalerted_alert_income):
                success = await self.notifier.send_digest(
                    jobs=unalerted_alert_jobs,
                    config=self.config,
                    income_opportunities=unalerted_alert_income,
                    dry_run=False
                )
                if success:
                    emails_dispatched += 1
                    for match in unalerted_alert_jobs:
                        self.state_manager.record_job(match.job, match.score, match.action, alerted=True)
                    for match in unalerted_alert_income:
                        if match.opportunity.source in income_telemetry_map:
                            income_telemetry_map[match.opportunity.source].alerted += 1
                        self.income_state_manager.record_opportunity(match.opportunity, match.score, match.action, alerted=True)
            elif not immediate_only and send_email and not (unalerted_alert_jobs or unalerted_alert_income):
                print("ℹ️ [NOTIFICATIONS] No new unalerted matches to dispatch. All matching opportunities were previously sent.")
        else:
            # Render and save preview for dry-run
            preview_jobs = unalerted_alert_jobs if unalerted_alert_jobs else (all_alert_jobs or low_matches[:5] or scored_jobs[:5])
            preview_income = unalerted_alert_income if unalerted_alert_income else (all_alert_income or low_income_matches[:5] or scored_income_opps[:5])
            if preview_jobs or preview_income:
                _, html_preview, _ = self.notifier.render_digest(
                    jobs=preview_jobs,
                    config=self.config,
                    income_opportunities=preview_income
                )
                self.notifier.save_preview(html_preview)

        # 7. Persist State
        if not dry_run:
            for s in scored_jobs:
                alerted = s in unalerted_alert_jobs and send_email
                self.state_manager.record_job(s.job, s.score, s.action, alerted=alerted)
            self.state_manager.save()

            if scored_income_opps:
                for s in scored_income_opps:
                    alerted = s in unalerted_alert_income and send_email
                    self.income_state_manager.record_opportunity(s.opportunity, s.score, s.action, alerted=alerted)
                self.income_state_manager.save()

        elapsed_sec = round(time.perf_counter() - start_time, 2)

        # 8. Build and record summary
        summary = RunSummary(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc),
            total_fetched=len(raw_jobs) + len(raw_income),
            unique_candidates=len(new_jobs) + len(new_income),
            discarded=len(discarded) + len(discarded_income),
            low_matches=len(low_matches) + len(low_income_matches),
            digest_matches=len(digest_matches) + len(digest_income_matches),
            instant_matches=len(instant_matches) + len(instant_income_matches),
            emails_dispatched=emails_dispatched,
            expired_links_removed=len(invalid_jobs) + len(rejected_income),
            execution_time_seconds=elapsed_sec,
            source_health=health_reports + income_health,
            error_count=sum(1 for h in (health_reports + income_health) if h.status == "error")
        )

        self._record_run_summary(summary)

        if include_income and (raw_income or scored_income_opps):
            income_summary = IncomeRunSummary(
                run_id=f"income_{run_id}",
                timestamp=datetime.now(timezone.utc),
                total_fetched=len(raw_income),
                unique_candidates=len(new_income),
                hard_rejected=sum(t.hard_rejected for t in income_telemetry_map.values()),
                quality_rejected=income_quality_rejected,
                ineligible=income_ineligible,
                verification_failed=sum(t.verification_failed for t in income_telemetry_map.values()),
                expired_links_removed=len(rejected_income),
                discarded=len(discarded_income),
                low_matches=len(low_income_matches),
                digest_matches=len(digest_income_matches),
                instant_matches=len(instant_income_matches),
                high_quality=len(instant_income_matches) + len(digest_income_matches),
                emails_dispatched=emails_dispatched,
                risk_rejected=sum(1 for o in rejected_income if o.verification_status == "rejected"),
                execution_time_seconds=elapsed_sec,
                source_health=income_health,
                source_telemetry=income_telemetry_map,
                error_count=sum(1 for h in income_health if h.status == "error")
            )
            self._record_income_run_summary(income_summary)

        print(f"🏁 [PIPELINE FINISHED] Completed in {elapsed_sec}s | Emails Dispatched: {emails_dispatched}\n")

        return summary, scored_jobs

    def _record_run_summary(self, summary: RunSummary) -> None:
        """Appends run summary to data/run_logs.json for UI telemetry."""
        RUN_LOGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        logs = []
        if RUN_LOGS_FILE.exists():
            try:
                with open(RUN_LOGS_FILE, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            except Exception:
                logs = []

        logs.insert(0, summary.model_dump(mode="json"))
        logs = logs[:50]

        with open(RUN_LOGS_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2)

    def _record_income_run_summary(self, summary: IncomeRunSummary) -> None:
        """Appends income run summary to data/income_run_logs.json for UI telemetry."""
        INCOME_RUN_LOGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        logs = []
        if INCOME_RUN_LOGS_FILE.exists():
            try:
                with open(INCOME_RUN_LOGS_FILE, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            except Exception:
                logs = []

        logs.insert(0, summary.model_dump(mode="json"))
        logs = logs[:50]

        with open(INCOME_RUN_LOGS_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2)


def get_run_logs() -> List[dict]:
    """Reads run logs for the dashboard."""
    if not RUN_LOGS_FILE.exists():
        return []
    try:
        with open(RUN_LOGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []
