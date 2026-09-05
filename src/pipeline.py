"""
JobsAlert Main Pipeline Orchestrator.
Coordinates collection, deduplication, scoring, triage, notification, and state persistence.
"""

from __future__ import annotations
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.collectors import run_all_collectors
from src.config import AppConfig
from src.deduplication import StateManager
from src.models import CrawlerHealth, JobPosting, MatchBreakdown, RunSummary, ScoredJob
from src.notifier.email_service import EmailNotifier
from src.scoring import ScoringEngine
from src.verifier import LinkVerifier

RUN_LOGS_FILE = Path(__file__).resolve().parent.parent / "data" / "run_logs.json"


class JobPipeline:
    def __init__(self, config: AppConfig, state_manager: Optional[StateManager] = None):
        self.config = config
        self.state_manager = state_manager or StateManager()
        self.scoring_engine = ScoringEngine(config)
        self.notifier = EmailNotifier()
        self.link_verifier = LinkVerifier()

    async def execute(
        self,
        dry_run: bool = True,
        send_email: bool = False,
        force_all: bool = False,
        immediate_only: bool = False,
    ) -> Tuple[RunSummary, List[ScoredJob]]:
        """
        Executes the entire job intelligence pipeline.
        """
        start_time = time.perf_counter()
        run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


        print(f"\n🚀 [PIPELINE START] Run ID: {run_id} | Mode: {'DRY RUN' if dry_run else 'LIVE'} | Profile: {self.config.profile.candidate_name}")

        # 1. Collect from all enabled sources concurrently
        raw_jobs, health_reports = await run_all_collectors(self.config)
        print(f"📥 [COLLECTED] {len(raw_jobs)} total job postings across {len(health_reports)} source connectors.")

        # 2. Filter & Deduplicate
        new_jobs: List[JobPosting] = []
        seen_count = 0
        for job in raw_jobs:
            if not force_all and self.state_manager.is_seen(job.fingerprint):
                seen_count += 1
                continue
            new_jobs.append(job)

        print(f"🔍 [DEDUPLICATION] {seen_count} previously processed jobs filtered out. {len(new_jobs)} unique candidates to verify & score.")

        # 3. Always Verify Job Links (Active, 404, 410, Soft-404 Closed Page Detection)
        valid_jobs: List[JobPosting] = []
        invalid_jobs: List[Tuple[JobPosting, str]] = []
        if self.config.link_verification.enabled and new_jobs:
            print(f"🔗 [LINK VERIFICATION] Verifying {len(new_jobs)} candidate URLs for active status...")
            valid_jobs, invalid_jobs = await self.link_verifier.verify_jobs_batch(new_jobs, self.config.link_verification)
            if invalid_jobs:
                print(f"⚠️ [LINK VERIFICATION] Excluded {len(invalid_jobs)} expired or closed job posting(s).")
        else:
            valid_jobs = new_jobs

        # 4. Score each job posting
        scored_jobs: List[ScoredJob] = []
        discarded: List[ScoredJob] = []
        low_matches: List[ScoredJob] = []
        digest_matches: List[ScoredJob] = []
        instant_matches: List[ScoredJob] = []

        # Record invalid / expired jobs as discarded
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

        # Sort matches by score descending
        digest_matches.sort(key=lambda x: x.score, reverse=True)
        instant_matches.sort(key=lambda x: x.score, reverse=True)
        all_alert_jobs = instant_matches + digest_matches

        print(f"📊 [SCORING RESULTS]")
        print(f"   ★ Instant Matches (9.0+):  {len(instant_matches)}")
        print(f"   ✦ Strong Matches (7.0-8.9): {len(digest_matches)}")
        print(f"   · Low Matches (5.0-6.9):    {len(low_matches)} (archived for UI)")
        print(f"   ✕ Discarded (0.0-4.9):      {len(discarded)} (including {len(invalid_jobs)} dead links)")

        # 5. Notifications
        emails_dispatched = 0
        if not dry_run and send_email:
            # Immediate Alerts
            if self.config.delivery.send_instant_alerts and instant_matches:
                for match in instant_matches:
                    success = await self.notifier.send_immediate(match, self.config, dry_run=False)
                    if success:
                        emails_dispatched += 1
                        self.state_manager.record_job(match.job, match.score, match.action, alerted=True)

            # Scheduled Digest
            if not immediate_only and self.config.delivery.send_daily_digest and all_alert_jobs:
                success = await self.notifier.send_digest(all_alert_jobs, self.config, dry_run=False)
                if success:
                    emails_dispatched += 1
                    for match in all_alert_jobs:
                        self.state_manager.record_job(match.job, match.score, match.action, alerted=True)
        else:
            # Render and save preview for dry-run
            preview_jobs = all_alert_jobs if all_alert_jobs else (low_matches[:5] or scored_jobs[:5])
            if preview_jobs:
                self.notifier.render_digest(preview_jobs, self.config)
                self.notifier.save_preview(self.notifier.render_digest(preview_jobs, self.config)[1])

        # 6. Persist State (in live runs or if requested)
        if not dry_run:
            for s in scored_jobs:
                alerted = s.action in ["instant", "digest"] and send_email
                self.state_manager.record_job(s.job, s.score, s.action, alerted=alerted)
            self.state_manager.save()

        elapsed_sec = round(time.perf_counter() - start_time, 2)

        # 7. Build and record summary
        summary = RunSummary(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc),
            total_fetched=len(raw_jobs),
            unique_candidates=len(new_jobs),
            discarded=len(discarded),
            low_matches=len(low_matches),
            digest_matches=len(digest_matches),
            instant_matches=len(instant_matches),
            emails_dispatched=emails_dispatched,
            expired_links_removed=len(invalid_jobs),
            execution_time_seconds=elapsed_sec,
            source_health=health_reports,
            error_count=sum(1 for h in health_reports if h.status == "error")
        )


        self._record_run_summary(summary)
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
        # Keep last 50 runs
        logs = logs[:50]

        with open(RUN_LOGS_FILE, "w", encoding="utf-8") as f:
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
