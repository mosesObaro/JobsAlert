"""
Online Income Opportunities Pipeline Orchestrator.
Coordinates collection, state deduplication, safety verification, relevance scoring,
email alert dispatch, and telemetry logging in data/income_run_logs.json.
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
    IncomeCollectorHealth,
    IncomeMatchBreakdown,
    IncomeRunSummary,
    OnlineIncomeOpportunity,
    ScoredOpportunity,
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
        """Executes the full online income discovery, verification, and evaluation run."""
        start_time = time.perf_counter()
        run_id = f"income_run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        print(f"\n💰 [INCOME SCOUT START] Run ID: {run_id} | Mode: {'DRY RUN' if dry_run else 'LIVE'} | Candidate: {self.config.candidate_name}")

        # 1. Collect from all enabled sources
        raw_opps, health_reports = await run_all_income_collectors(self.config)
        print(f"📥 [COLLECTED] {len(raw_opps)} income tracks discovered across {len(health_reports)} source modules.")

        # 2. Filter & Deduplicate
        new_opps: List[OnlineIncomeOpportunity] = []
        seen_count = 0
        dismissed_count = 0

        for opp in raw_opps:
            fp = opp.fingerprint
            if self.state_manager.is_dismissed(fp):
                dismissed_count += 1
                continue
            if not force_all and self.state_manager.is_seen(fp):
                seen_count += 1
                continue
            new_opps.append(opp)

        print(f"🔍 [DEDUPLICATION] {seen_count} already processed, {dismissed_count} dismissed. {len(new_opps)} candidate tracks to verify & score.")

        # 3. Verify Links & Scam Safety
        valid_opps: List[OnlineIncomeOpportunity] = []
        rejected_opps: List[OnlineIncomeOpportunity] = []

        if new_opps:
            print(f"🔗 [SAFETY & LINK VERIFICATION] Screening {len(new_opps)} opportunities...")
            valid_opps, rejected_opps = await self.verifier.verify_opportunities_batch(
                new_opps,
                check_links=self.config.require_link_verification,
                max_concurrency=15
            )
            if rejected_opps:
                print(f"⚠️ [SAFETY VERIFICATION] Filtered out {len(rejected_opps)} dead links or safety-flagged tracks.")

        # 4. Score each opportunity
        scored_opps: List[ScoredOpportunity] = []
        discarded: List[ScoredOpportunity] = []
        low_matches: List[ScoredOpportunity] = []
        digest_matches: List[ScoredOpportunity] = []
        instant_matches: List[ScoredOpportunity] = []

        # Handle rejected/dead
        for rej in rejected_opps:
            scored_rej = self.scoring_engine.score_opportunity(rej)
            scored_opps.append(scored_rej)
            discarded.append(scored_rej)

        # Handle valid
        for opp in valid_opps:
            scored = self.scoring_engine.score_opportunity(opp)
            scored_opps.append(scored)

            if scored.action == "discard":
                discarded.append(scored)
            elif scored.action == "low_match":
                low_matches.append(scored)
            elif scored.action == "digest":
                digest_matches.append(scored)
            elif scored.action == "instant":
                instant_matches.append(scored)

        # Sort matches by score descending
        digest_matches.sort(key=lambda x: x.score, reverse=True)
        instant_matches.sort(key=lambda x: x.score, reverse=True)
        all_alert_opps = instant_matches + digest_matches

        print(f"📊 [INCOME SCORING RESULTS]")
        print(f"   ★ Instant Matches (9.0+):  {len(instant_matches)}")
        print(f"   ✦ Strong Matches (7.0-8.9): {len(digest_matches)}")
        print(f"   · Low Matches (5.0-6.9):    {len(low_matches)} (saved for dashboard)")
        print(f"   ✕ Discarded (0.0-4.9):      {len(discarded)}")

        # 5. Email Notifications
        emails_dispatched = 0
        if not dry_run and send_email:
            # Immediate Alerts
            if instant_matches:
                for match in instant_matches:
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
                        self.state_manager.record_opportunity(match.opportunity, match.score, match.action, alerted=True)

            # Scheduled Digest
            if not immediate_only and all_alert_opps:
                success = await self.notifier.send_income_digest(
                    opportunities=all_alert_opps,
                    candidate_name=self.config.candidate_name,
                    recipient_email=recipient_email,
                    email_provider=email_provider,
                    from_email=from_email,
                    dry_run=False
                )
                if success:
                    emails_dispatched += 1
                    for match in all_alert_opps:
                        self.state_manager.record_opportunity(match.opportunity, match.score, match.action, alerted=True)
        else:
            # Render and save preview for dry run
            preview_opps = all_alert_opps if all_alert_opps else (low_matches[:5] or scored_opps[:5])
            if preview_opps:
                self.notifier.render_income_digest(
                    preview_opps,
                    self.config.candidate_name,
                    recipient_email
                )

        # 6. Persist State
        if not dry_run:
            for s in scored_opps:
                alerted = s.action in ["instant", "digest"] and send_email
                self.state_manager.record_opportunity(s.opportunity, s.score, s.action, alerted=alerted)
            self.state_manager.save()

        elapsed_sec = round(time.perf_counter() - start_time, 2)

        # 7. Build and Record Run Summary
        summary = IncomeRunSummary(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc),
            total_fetched=len(raw_opps),
            unique_candidates=len(new_opps),
            discarded=len(discarded),
            low_matches=len(low_matches),
            digest_matches=len(digest_matches),
            instant_matches=len(instant_matches),
            emails_dispatched=emails_dispatched,
            expired_links_removed=len(rejected_opps),
            risk_rejected=sum(1 for o in rejected_opps if o.verification_status == "rejected"),
            execution_time_seconds=elapsed_sec,
            source_health=health_reports,
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
        # Keep last 50 runs
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
