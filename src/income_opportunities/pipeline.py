"""
Online Income Opportunities Pipeline Orchestrator.
Coordinates collection, deduplication, hard rejection, quality gating,
eligibility verification, side-job scoring, selective Top-5 ranking,
email alert dispatch, and granular telemetry logging in data/income_run_logs.json.
"""

from __future__ import annotations
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.income_opportunities.collectors import run_all_income_collectors
from src.income_opportunities.config import OnlineIncomeConfig
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
from src.notifier.email_service import EmailNotifier

INCOME_RUN_LOGS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "income_run_logs.json"


class IncomeOpportunityPipeline:
    """End-to-end execution pipeline for Online Income Opportunities."""

    def __init__(
        self,
        config: OnlineIncomeConfig,
        state_manager: Optional[IncomeStateManager] = None,
        verifier: Optional[IncomeOpportunityVerifier] = None,
        notifier: Optional[EmailNotifier] = None,
    ):
        self.config = config
        self.state_manager = state_manager or IncomeStateManager()
        self.scoring_engine = IncomeScoringEngine(config)
        self.verifier = verifier or IncomeOpportunityVerifier()
        self.notifier = notifier or EmailNotifier()

    async def execute(
        self,
        dry_run: bool = True,
        send_email: bool = False,
        force_all: bool = False,
        immediate_only: bool = False,
        recipient_email: str = "candidate@example.com",
        email_provider: str = "console",
        from_email: str = "alerts@jobsalert.dev",
    ) -> Tuple[IncomeRunSummary, List[ScoredOpportunity]]:
        """Executes the quality-gated discovery, verification, and evaluation run."""
        start_time = time.perf_counter()
        run_id = f"income_run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        print(f"\n💰 [INCOME SCOUT START] Run ID: {run_id} | Mode: {'DRY RUN' if dry_run else 'LIVE'} | Candidate: {self.config.candidate_name}")

        # 1. Collect from all enabled sources
        raw_opps, health_reports = await run_all_income_collectors(self.config)
        print(f"📥 [COLLECTED] {len(raw_opps)} candidate tracks discovered across {len(health_reports)} source modules.")

        source_telemetry_map: Dict[str, SourceTelemetry] = {}
        for h in health_reports:
            source_telemetry_map[h.source_name] = h.telemetry or SourceTelemetry(source_name=h.source_name, discovered=h.opportunities_found)

        # 2. Filter & Deduplicate
        new_opps: List[OnlineIncomeOpportunity] = []
        seen_count = 0
        dismissed_count = 0

        for opp in raw_opps:
            fp = opp.fingerprint
            if self.state_manager.is_dismissed(fp):
                dismissed_count += 1
                if opp.source in source_telemetry_map:
                    source_telemetry_map[opp.source].duplicates_removed += 1
                continue
            if not force_all and self.state_manager.is_seen(fp):
                seen_count += 1
                if opp.source in source_telemetry_map:
                    source_telemetry_map[opp.source].duplicates_removed += 1
                continue
            new_opps.append(opp)

        print(f"🔍 [DEDUPLICATION] {seen_count} already processed, {dismissed_count} dismissed. {len(new_opps)} unique tracks to verify & score.")

        # 3. Verify Links, Scam Screening & Hard Rejection
        valid_opps: List[OnlineIncomeOpportunity] = []
        rejected_opps: List[OnlineIncomeOpportunity] = []

        if new_opps:
            print(f"🔗 [SAFETY & QUALITY VERIFICATION] Screening {len(new_opps)} opportunities...")
            valid_opps, rejected_opps = await self.verifier.verify_opportunities_batch(
                new_opps,
                check_links=self.config.require_link_verification,
                max_concurrency=15
            )
            for rej in rejected_opps:
                if rej.source in source_telemetry_map:
                    if rej.verification_status == "rejected":
                        source_telemetry_map[rej.source].hard_rejected += 1
                    else:
                        source_telemetry_map[rej.source].verification_failed += 1

            if rejected_opps:
                print(f"⚠️ [SAFETY VERIFICATION] Filtered out {len(rejected_opps)} dead links, non-work advice, or safety-flagged tracks.")

        # 4. Score Opportunities (Quality Gate -> Geographic Eligibility -> Side-Job Fit -> Final Score)
        scored_opps: List[ScoredOpportunity] = []
        discarded: List[ScoredOpportunity] = []
        low_matches: List[ScoredOpportunity] = []
        digest_matches: List[ScoredOpportunity] = []
        instant_matches: List[ScoredOpportunity] = []
        quality_rejected_count = 0
        ineligible_count = 0

        # Handle pre-rejected / dead
        for rej in rejected_opps:
            scored_rej = self.scoring_engine.score_opportunity(rej)
            scored_opps.append(scored_rej)
            discarded.append(scored_rej)

        # Handle valid
        for opp in valid_opps:
            scored = self.scoring_engine.score_opportunity(opp)
            scored_opps.append(scored)

            src = opp.source
            telemetry = source_telemetry_map.get(src)

            if not scored.breakdown.passed_quality_gate:
                quality_rejected_count += 1
                if telemetry:
                    telemetry.quality_rejected += 1
                discarded.append(scored)
            elif scored.breakdown.eligibility_status == EligibilityStatus.INELIGIBLE.value:
                ineligible_count += 1
                if telemetry:
                    telemetry.ineligible += 1
                discarded.append(scored)
            elif scored.action == "discard":
                discarded.append(scored)
            elif scored.action == "low_match":
                low_matches.append(scored)
                if telemetry:
                    telemetry.verified += 1
            elif scored.action == "digest":
                digest_matches.append(scored)
                if telemetry:
                    telemetry.verified += 1
                    telemetry.high_quality += 1
            elif scored.action == "instant":
                instant_matches.append(scored)
                if telemetry:
                    telemetry.verified += 1
                    telemetry.high_quality += 1

        # 5. Rank & Cap Selective Digest (Top 5 Max)
        digest_matches.sort(key=lambda x: (x.score, x.breakdown.quality_score, x.breakdown.side_job_fit_score), reverse=True)
        instant_matches.sort(key=lambda x: (x.score, x.breakdown.quality_score, x.breakdown.side_job_fit_score), reverse=True)

        max_items = self.config.max_digest_items or 5
        all_alert_opps = (instant_matches + digest_matches)[:max_items]

        print(f"📊 [HIGH-PRECISION SCORING RESULTS]")
        print(f"   ★ Instant Matches (9.0+):         {len(instant_matches)}")
        print(f"   ✦ Quality Digest Matches (7.5+):  {len(digest_matches)} (Capped at Top {max_items})")
        print(f"   · Low Matches (5.0-7.4):           {len(low_matches)} (saved for dashboard)")
        print(f"   ✕ Quality Gated / Discarded:       {len(discarded)} (Quality Blocked: {quality_rejected_count}, Ineligible: {ineligible_count})")

        # 6. Filter Unalerted Matches & Dispatch Notifications
        unalerted_instant = [m for m in instant_matches if not self.state_manager.is_alerted(m.opportunity.fingerprint)]
        unalerted_digest = [m for m in digest_matches if not self.state_manager.is_alerted(m.opportunity.fingerprint)]
        unalerted_all_opps = (unalerted_instant + unalerted_digest)[:max_items]

        already_sent_count = len(instant_matches + digest_matches) - len(unalerted_instant + unalerted_digest)
        if already_sent_count > 0:
            print(f"🛡️ [PREVIOUSLY SENT FILTER] Suppressed {already_sent_count} income track(s) already emailed previously.")

        emails_dispatched = 0
        if not dry_run and send_email:
            # Immediate Alerts (New / Unalerted Only)
            if unalerted_instant:
                for match in unalerted_instant:
                    success = await self.notifier.send_income_immediate(
                        scored=match,
                        candidate_name=self.config.candidate_name,
                        recipient_email=recipient_email,
                        email_provider=email_provider,
                        from_email=from_email,
                        dry_run=False
                    )
                    if success:
                        emails_dispatched += 1
                        if match.opportunity.source in source_telemetry_map:
                            source_telemetry_map[match.opportunity.source].alerted += 1
                        self.state_manager.record_opportunity(match.opportunity, match.score, match.action, alerted=True)

            # Scheduled Digest (New / Unalerted Only)
            if not immediate_only and unalerted_all_opps:
                success = await self.notifier.send_income_digest(
                    opportunities=unalerted_all_opps,
                    candidate_name=self.config.candidate_name,
                    recipient_email=recipient_email,
                    email_provider=email_provider,
                    from_email=from_email,
                    dry_run=False
                )
                if success:
                    emails_dispatched += 1
                    for match in unalerted_all_opps:
                        if match.opportunity.source in source_telemetry_map:
                            source_telemetry_map[match.opportunity.source].alerted += 1
                        self.state_manager.record_opportunity(match.opportunity, match.score, match.action, alerted=True)
            elif not immediate_only and send_email and not unalerted_all_opps:
                print("ℹ️ [NOTIFICATIONS] No new unalerted income tracks to dispatch. All matching tracks were previously sent.")
        else:
            # Render and save preview for dry run
            preview_opps = unalerted_all_opps if unalerted_all_opps else (all_alert_opps or low_matches[:5] or scored_opps[:5])
            if preview_opps:
                self.notifier.render_income_digest(
                    preview_opps,
                    self.config.candidate_name,
                    recipient_email
                )

        # 7. Persist State
        if not dry_run:
            for s in scored_opps:
                alerted = s in unalerted_all_opps and send_email
                self.state_manager.record_opportunity(s.opportunity, s.score, s.action, alerted=alerted)
            self.state_manager.save()

        elapsed_sec = round(time.perf_counter() - start_time, 2)

        # 8. Build and Record Run Summary
        summary = IncomeRunSummary(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc),
            total_fetched=len(raw_opps),
            unique_candidates=len(new_opps),
            hard_rejected=sum(t.hard_rejected for t in source_telemetry_map.values()),
            quality_rejected=quality_rejected_count,
            ineligible=ineligible_count,
            verification_failed=sum(t.verification_failed for t in source_telemetry_map.values()),
            expired_links_removed=len(rejected_opps),
            discarded=len(discarded),
            low_matches=len(low_matches),
            digest_matches=len(digest_matches),
            instant_matches=len(instant_matches),
            high_quality=len(instant_matches) + len(digest_matches),
            emails_dispatched=emails_dispatched,
            risk_rejected=sum(1 for o in rejected_opps if o.verification_status == "rejected"),
            execution_time_seconds=elapsed_sec,
            source_health=health_reports,
            source_telemetry=source_telemetry_map,
            error_count=sum(1 for h in health_reports if h.status == "error")
        )

        self._record_run_summary(summary)
        print(f"🏁 [INCOME SCOUT FINISHED] Completed in {elapsed_sec}s | Emails Dispatched: {emails_dispatched}\n")

        return summary, scored_opps

    def _record_run_summary(self, summary: IncomeRunSummary) -> None:
        """Appends run summary to data/income_run_logs.json for UI telemetry."""
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


def get_income_run_logs() -> List[dict]:
    """Reads income run logs for the dashboard."""
    if not INCOME_RUN_LOGS_FILE.exists():
        return []
    try:
        with open(INCOME_RUN_LOGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []
