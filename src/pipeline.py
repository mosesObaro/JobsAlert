"""
JobsAlert Main Pipeline.
Collect -> deduplicate -> score against every job spec -> verify the links of alert
candidates -> deliver -> persist, for career roles plus (optionally) the online
income stage, which is delegated to IncomeOpportunityPipeline.

A posting is recorded as alerted only after its email was accepted by the provider.
Alert-worthy postings that could not be delivered stay unseen, so the next live run
retries them.
"""

from __future__ import annotations
import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from src import paths
from src.collectors import run_all_collectors
from src.config import AppConfig
from src.deduplication import StateManager
from src.income_opportunities.deduplication import IncomeStateManager
from src.income_opportunities.models import IncomeRunSummary, ScoredOpportunity
from src.income_opportunities.pipeline import IncomeEvaluation, IncomeOpportunityPipeline
from src.models import MatchBreakdown, RunSummary, ScoredJob, SpecMatchGroup
from src.notifier.email_service import EmailNotifier
from src.scoring import ScoringEngine
from src.telemetry import append_run_log, read_run_logs
from src.verifier import LinkVerifier

ALERT_ACTIONS = ("instant", "digest")
# Discussion permalinks never close, so checking them only burns requests.
UNVERIFIABLE_SOURCES = {"hackernews"}


def run_logs_file():
    return paths.data_file(paths.RUN_LOGS)


def _by_score(items: List[ScoredJob]) -> List[ScoredJob]:
    return sorted(items, key=lambda x: x.score, reverse=True)


def _dead_link(result: ScoredJob, reason: str) -> ScoredJob:
    breakdown = MatchBreakdown(
        penalties_applied=[f"Link inactive or posting closed ({reason})"],
        highlights=[f"Discarded: the link is dead or the position is closed ({reason})"],
        is_verified=False,
    )
    return ScoredJob(job=result.job, score=0.0, action="discard", breakdown=breakdown, spec_name=result.spec_name)


class JobPipeline:
    def __init__(
        self,
        config: AppConfig,
        state_manager: Optional[StateManager] = None,
        income_state_manager: Optional[IncomeStateManager] = None,
    ):
        self.config = config
        self.state_manager = state_manager if state_manager is not None else StateManager()
        self.scoring_engine = ScoringEngine(config)
        self.notifier = EmailNotifier()
        self.link_verifier = LinkVerifier()
        self.income_pipeline = IncomeOpportunityPipeline(
            config.online_income,
            state_manager=income_state_manager,
            notifier=self.notifier,
            fx_rates=config.fx_rates_to_usd,
            link_config=config.link_verification,
            retention_days=config.state.retention_days,
        )
        self.latest_income_opportunities: List[ScoredOpportunity] = []
        self.latest_income_summary: Optional[IncomeRunSummary] = None

    @property
    def income_state_manager(self) -> IncomeStateManager:
        return self.income_pipeline.state_manager

    async def execute(
        self,
        dry_run: bool = True,
        send_email: bool = False,
        force_all: bool = False,
        immediate_only: bool = False,
        trigger: str = "manual",
    ) -> Tuple[RunSummary, List[ScoredJob]]:
        """Runs one full pass. Returns the run summary and every (job, spec) score."""
        started = time.perf_counter()
        run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        mode = "dry_run" if dry_run else "live"
        config, state, delivery = self.config, self.state_manager, self.config.delivery
        include_income = config.online_income.enabled and config.online_income.include_in_daily_digest
        print(f"\n🚀 [PIPELINE START] Run ID: {run_id} | Mode: {mode.upper()} | Profile: {config.profile.candidate_name}")

        # 1. COLLECT (jobs and income concurrently) ---------------------------
        income_ev: Optional[IncomeEvaluation] = None
        if include_income:
            (raw_jobs, health), income_ev = await asyncio.gather(
                run_all_collectors(config), self.income_pipeline.evaluate(force_all=force_all)
            )
        else:
            raw_jobs, health = await run_all_collectors(config)
        print(f"📥 [COLLECTED] {len(raw_jobs)} career postings" + (f" & {len(income_ev.raw)} income tracks." if income_ev else "."))
        self._print_health(health + (income_ev.health if income_ev else []))

        # 2. DEDUPLICATE -------------------------------------------------------
        new_jobs = []
        batch: Set[str] = set()
        for job in raw_jobs:
            fp = job.fingerprint
            if fp in batch:
                continue
            batch.add(fp)
            if not state.is_seen(fp):
                alias = state.find_equivalent(job)
                if alias:
                    state.adopt(job, alias)  # same posting recorded under an older fingerprint
            if state.is_seen(fp):
                state.touch(fp)
                if not force_all:
                    continue
            new_jobs.append(job)
        print(f"🔍 [DEDUPLICATION] {len(new_jobs)} postings to score ({len(batch) - len(new_jobs)} already processed).")

        # 3. SCORE against every spec -----------------------------------------
        specs = config.get_effective_job_specs()
        per_job: Dict[str, List[ScoredJob]] = {
            job.fingerprint: [self.scoring_engine.score_job(job, spec=spec) for spec in specs] for job in new_jobs
        }

        # 4. VERIFY LINKS of alert candidates only ------------------------------
        links_checked = dead_links = unverified_links = 0
        candidates = [job for job in new_jobs if any(r.action in ALERT_ACTIONS for r in per_job[job.fingerprint])]
        if config.link_verification.enabled and candidates:
            urls = {job.fingerprint: (job.raw_url or job.url) for job in candidates if job.source not in UNVERIFIABLE_SOURCES}
            results = await self.link_verifier.verify_many(urls.values(), config.link_verification)
            for job in candidates:
                result = results.get(urls.get(job.fingerprint, ""))
                if result is None:
                    job.verification_status = "not checked"
                    continue
                links_checked += 1
                job.verification_status = result.status
                if result.is_dead:
                    dead_links += 1
                    job.is_verified = False
                    per_job[job.fingerprint] = [_dead_link(r, result.reason) for r in per_job[job.fingerprint]]
                elif result.status == "unknown":
                    unverified_links += 1
                    for r in per_job[job.fingerprint]:
                        r.breakdown.penalties_applied.append(f"Link could not be checked: {result.reason}")
            print(f"🔗 [LINKS] Checked {links_checked}: {dead_links} dead, {unverified_links} unverifiable (kept).")

        scored_jobs = [r for results in per_job.values() for r in results]
        best = {fp: max(results, key=lambda r: r.score) for fp, results in per_job.items()}

        spec_groups: List[SpecMatchGroup] = []
        for spec in specs:
            matches = _by_score([r for r in scored_jobs if r.spec_name == spec.name and r.action in ALERT_ACTIONS])
            unalerted = [m for m in matches if not state.is_alerted(m.job.fingerprint)]
            spec_groups.append(SpecMatchGroup(spec_name=spec.name, jobs=matches, unalerted_jobs=unalerted, total_matches=len(matches)))

        alert_jobs = _by_score([b for fp, b in best.items() if b.action in ALERT_ACTIONS and not state.is_alerted(fp)])
        instant_jobs = [b for b in alert_jobs if b.action == "instant"]
        income_instant = self.income_pipeline.unalerted(income_ev.instant) if income_ev else []
        income_digest = self.income_pipeline.select_for_digest(income_ev) if income_ev else []

        # 5. DELIVER -----------------------------------------------------------
        delivered_jobs: Set[str] = set()
        delivered_income: Set[str] = set()
        errors: List[str] = []
        emails = income_emails = 0
        if not dry_run and send_email:
            if delivery.send_instant_alerts:
                for match in instant_jobs:
                    result = await self.notifier.send_immediate(match, config, dry_run=False)
                    if result:
                        emails += 1
                        delivered_jobs.add(match.job.fingerprint)
                    else:
                        errors.append(f"Instant alert '{match.job.title}': {getattr(result, 'error', 'failed')}")
                for match in income_instant:
                    result = await self.notifier.send_income_immediate(
                        scored=match,
                        candidate_name=config.online_income.candidate_name,
                        recipient_email=delivery.recipient_email,
                        email_provider=delivery.email_provider,
                        from_email=delivery.from_email,
                        dry_run=False,
                    )
                    if result:
                        emails += 1
                        income_emails += 1
                        delivered_income.add(match.opportunity.fingerprint)
                    else:
                        errors.append(f"Instant income alert '{match.opportunity.title}': {getattr(result, 'error', 'failed')}")

            if not immediate_only and delivery.send_daily_digest and (alert_jobs or income_digest):
                digest_groups = [
                    SpecMatchGroup(spec_name=g.spec_name, jobs=g.unalerted_jobs, unalerted_jobs=g.unalerted_jobs, total_matches=len(g.unalerted_jobs))
                    for g in spec_groups
                ]
                result = await self.notifier.send_digest(
                    jobs=alert_jobs, config=config, income_opportunities=income_digest, spec_groups=digest_groups, dry_run=False
                )
                if result:
                    emails += 1
                    income_emails += 1 if income_digest else 0
                    delivered_jobs.update(m.job.fingerprint for m in alert_jobs)
                    delivered_income.update(m.opportunity.fingerprint for m in income_digest)
                else:
                    errors.append(f"Daily digest: {getattr(result, 'error', 'failed')}")
            elif not immediate_only and not (alert_jobs or income_digest):
                print("ℹ️ [NOTIFICATIONS] Nothing new to send.")
        else:
            preview_jobs = alert_jobs or _by_score(list(best.values()))[:5]
            preview_income = income_digest or ((income_ev.candidates or income_ev.low)[:5] if income_ev else [])
            if preview_jobs or preview_income or spec_groups:
                _subject, html, _text = self.notifier.render_digest(
                    jobs=preview_jobs, config=config, income_opportunities=preview_income, spec_groups=spec_groups
                )
                self.notifier.save_preview(html)

        # 6. PERSIST -----------------------------------------------------------
        pending = income_pending = 0
        if not dry_run:
            digest_off = not delivery.send_daily_digest
            instant_off = digest_off and not delivery.send_instant_alerts
            for fp, b in best.items():
                if b.action in ALERT_ACTIONS and not state.is_alerted(fp) and fp not in delivered_jobs:
                    skipped_on_purpose = (b.action == "digest" and digest_off) or (b.action == "instant" and instant_off)
                    if not skipped_on_purpose:
                        pending += 1  # retried on the next live run
                        continue
                state.record_job(b.job, b.score, b.action, alerted=fp in delivered_jobs, spec=b.spec_name)
            state.prune(config.state.retention_days)
            state.save()

            if income_ev:
                skipped_income = {
                    s.opportunity.fingerprint for s in income_ev.candidates
                    if (s.action == "digest" and digest_off) or (s.action == "instant" and instant_off)
                }
                income_pending = self.income_pipeline.persist(income_ev, delivered_income, skipped_income)
                pending += income_pending

        # 7. SUMMARY -----------------------------------------------------------
        actions = [b.action for b in best.values()]
        income_counts = (len(income_ev.discarded), len(income_ev.low), len(income_ev.digest), len(income_ev.instant)) if income_ev else (0, 0, 0, 0)
        spec_counts = {
            g.spec_name: {a: sum(1 for r in scored_jobs if r.spec_name == g.spec_name and r.action == a) for a in ("instant", "digest", "low_match")}
            for g in spec_groups
        }
        all_health = health + (income_ev.health if income_ev else [])
        summary = RunSummary(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc),
            mode=mode,
            trigger=trigger,
            total_fetched=len(raw_jobs) + (len(income_ev.raw) if income_ev else 0),
            unique_candidates=len(new_jobs) + (len(income_ev.new) if income_ev else 0),
            discarded=actions.count("discard") + income_counts[0],
            low_matches=actions.count("low_match") + income_counts[1],
            digest_matches=actions.count("digest") + income_counts[2],
            instant_matches=actions.count("instant") + income_counts[3],
            spec_counts=spec_counts,
            emails_dispatched=emails,
            delivery_errors=errors,
            pending_alerts=pending,
            links_checked=links_checked,
            expired_links_removed=dead_links + (income_ev.dead_links if income_ev else 0),
            unverified_links=unverified_links + (income_ev.unverified_links if income_ev else 0),
            execution_time_seconds=round(time.perf_counter() - started, 2),
            source_health=all_health,
            error_count=sum(1 for h in all_health if h.status == "error"),
            degraded_count=sum(1 for h in all_health if h.status == "degraded"),
        )
        append_run_log(run_logs_file(), summary.model_dump(mode="json"))

        self.latest_income_opportunities = income_ev.scored if income_ev else []
        if income_ev:
            self.latest_income_summary = self.income_pipeline.build_summary(
                income_ev, mode=mode, trigger=trigger, emails=income_emails,
                errors=[e for e in errors if "income" in e.lower() or e.startswith("Daily digest")],
                pending=income_pending, run_id=f"income_{run_id}",
            )
            self.income_pipeline.record_summary(self.latest_income_summary)

        for group in spec_groups:
            print(f"   📋 Spec '{group.spec_name}': {len(group.jobs)} match(es), {len(group.unalerted_jobs)} new")
        status = f"Emails: {emails}" + (f" | Pending: {pending}" if pending else "") + (f" | Delivery errors: {len(errors)}" if errors else "")
        print(f"🏁 [PIPELINE FINISHED] {summary.execution_time_seconds}s | {status}\n")
        return summary, scored_jobs

    @staticmethod
    def _print_health(health: list) -> None:
        for h in health:
            if h.status != "healthy":
                found = getattr(h, "jobs_found", None)
                if found is None:
                    found = getattr(h, "opportunities_found", 0)
                detail = f" — {h.error_message}" if h.error_message else ""
                print(f"   ⚠️ Source {h.source_name}: {h.status.upper()} ({found} items){detail}")


def get_run_logs() -> List[dict]:
    """Run logs for the dashboard."""
    return read_run_logs(run_logs_file())
