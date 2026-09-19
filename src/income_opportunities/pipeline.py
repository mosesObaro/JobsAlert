"""
Online Income Opportunities Pipeline.

`evaluate()` collects, deduplicates, screens and scores opportunities and checks the
links of alert candidates; `persist()` records the outcome. The unified job pipeline
calls both so the income stage has a single implementation. `execute()` runs a
standalone income scan with its own digest.

Alert-worthy items are recorded as seen only once delivered. Items that fail to send,
or wait beyond the per-digest cap, stay unseen and are picked up by the next run.
"""

from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from src import paths
from src.config import LinkVerificationConfig
from src.income_opportunities.collectors import run_all_income_collectors
from src.income_opportunities.config import OnlineIncomeConfig
from src.income_opportunities.deduplication import IncomeStateManager
from src.income_opportunities.models import (
    EligibilityStatus,
    IncomeCollectorHealth,
    IncomeRunSummary,
    OnlineIncomeOpportunity,
    ScoredOpportunity,
    SourceTelemetry,
)
from src.income_opportunities.scoring import IncomeScoringEngine
from src.income_opportunities.verifier import IncomeOpportunityVerifier
from src.notifier.email_service import EmailNotifier
from src.telemetry import append_run_log, read_run_logs

ALERT_ACTIONS = ("instant", "digest")


def income_run_logs_file():
    return paths.data_file(paths.INCOME_RUN_LOGS)


@dataclass
class IncomeEvaluation:
    """Everything one income evaluation produced, before anything is sent or saved."""
    started: float
    raw: List[OnlineIncomeOpportunity] = field(default_factory=list)
    health: List[IncomeCollectorHealth] = field(default_factory=list)
    telemetry: Dict[str, SourceTelemetry] = field(default_factory=dict)
    new: List[OnlineIncomeOpportunity] = field(default_factory=list)
    scored: List[ScoredOpportunity] = field(default_factory=list)
    instant: List[ScoredOpportunity] = field(default_factory=list)
    digest: List[ScoredOpportunity] = field(default_factory=list)
    low: List[ScoredOpportunity] = field(default_factory=list)
    discarded: List[ScoredOpportunity] = field(default_factory=list)
    quality_rejected: int = 0
    ineligible: int = 0
    dead_links: int = 0
    unverified_links: int = 0

    @property
    def candidates(self) -> List[ScoredOpportunity]:
        return self.instant + self.digest


def _rank(items: List[ScoredOpportunity]) -> List[ScoredOpportunity]:
    return sorted(items, key=lambda x: (x.score, x.breakdown.quality_score, x.breakdown.side_job_fit_score), reverse=True)


class IncomeOpportunityPipeline:
    """Discovery, screening, scoring and alerting for online income opportunities."""

    def __init__(
        self,
        config: OnlineIncomeConfig,
        state_manager: Optional[IncomeStateManager] = None,
        verifier: Optional[IncomeOpportunityVerifier] = None,
        notifier: Optional[EmailNotifier] = None,
        fx_rates: Optional[Dict[str, float]] = None,
        link_config: Optional[LinkVerificationConfig] = None,
        retention_days: int = 90,
    ):
        self.config = config
        self.state_manager = state_manager if state_manager is not None else IncomeStateManager()
        self.scoring_engine = IncomeScoringEngine(config, fx_rates=fx_rates)
        self.verifier = verifier if verifier is not None else IncomeOpportunityVerifier()
        self.notifier = notifier if notifier is not None else EmailNotifier()
        self.link_config = link_config or LinkVerificationConfig()
        self.retention_days = retention_days

    # ------------------------------------------------------------------ evaluate
    async def evaluate(self, force_all: bool = False) -> IncomeEvaluation:
        ev = IncomeEvaluation(started=time.perf_counter())
        ev.raw, ev.health = await run_all_income_collectors(self.config)
        for h in ev.health:
            ev.telemetry[h.source_name] = h.telemetry or SourceTelemetry(source_name=h.source_name, discovered=h.opportunities_found)

        state = self.state_manager
        batch_seen: Set[str] = set()
        for opp in ev.raw:
            fp = opp.fingerprint
            if fp in batch_seen:
                continue
            batch_seen.add(fp)
            if not state.is_seen(fp):
                alias = state.find_equivalent(opp)
                if alias:
                    state.adopt(opp, alias)
            if state.is_dismissed(fp) or (not force_all and state.is_seen(fp)):
                state.touch(fp)
                self._count(ev, opp.source, "duplicates_removed")
                continue
            ev.new.append(opp)

        accepted, rejected = self.verifier.screen(ev.new)
        for opp in rejected:
            self._count(ev, opp.source, "hard_rejected")
            scored = self.scoring_engine.score_opportunity(opp)
            ev.scored.append(scored)
            ev.discarded.append(scored)

        scored_accepted = [self.scoring_engine.score_opportunity(opp) for opp in accepted]

        # Only alert candidates are link-checked; dead links are rescored (and discarded).
        candidates = [s for s in scored_accepted if s.action in ALERT_ACTIONS]
        if candidates and self.config.require_link_verification:
            statuses = await self.verifier.check_links([s.opportunity for s in candidates], self.link_config)
            ev.unverified_links = sum(1 for status in statuses.values() if status == "unknown")
            for position, item in enumerate(scored_accepted):
                if statuses.get(item.opportunity.fingerprint) == "dead":
                    ev.dead_links += 1
                    self._count(ev, item.opportunity.source, "verification_failed")
                    scored_accepted[position] = self.scoring_engine.score_opportunity(item.opportunity)

        for item in scored_accepted:
            ev.scored.append(item)
            source = item.opportunity.source
            if not item.breakdown.passed_quality_gate:
                ev.quality_rejected += 1
                self._count(ev, source, "quality_rejected")
                ev.discarded.append(item)
            elif item.breakdown.eligibility_status == EligibilityStatus.INELIGIBLE.value:
                ev.ineligible += 1
                self._count(ev, source, "ineligible")
                ev.discarded.append(item)
            elif item.action == "discard":
                ev.discarded.append(item)
            elif item.action == "low_match":
                ev.low.append(item)
                self._count(ev, source, "verified")
            else:
                (ev.instant if item.action == "instant" else ev.digest).append(item)
                self._count(ev, source, "verified")
                self._count(ev, source, "high_quality")

        ev.instant, ev.digest = _rank(ev.instant), _rank(ev.digest)
        return ev

    @staticmethod
    def _count(ev: IncomeEvaluation, source: str, counter: str, amount: int = 1) -> None:
        telemetry = ev.telemetry.get(source)
        if telemetry:
            setattr(telemetry, counter, getattr(telemetry, counter) + amount)

    # ------------------------------------------------------------------ selection
    def unalerted(self, items: List[ScoredOpportunity]) -> List[ScoredOpportunity]:
        return [s for s in items if not self.state_manager.is_alerted(s.opportunity.fingerprint)]

    def select_for_digest(self, ev: IncomeEvaluation) -> List[ScoredOpportunity]:
        """Top unalerted candidates up to the digest cap; the rest wait for a later digest."""
        cap = self.config.max_digest_items or 5
        return _rank(self.unalerted(ev.candidates))[:cap]

    # ------------------------------------------------------------------ persist
    def persist(self, ev: IncomeEvaluation, delivered: Set[str], skipped_on_purpose: Set[str] = frozenset()) -> int:
        """Records outcomes. Undelivered candidates stay unseen; returns how many are pending."""
        pending = 0
        for item in ev.scored:
            fp = item.opportunity.fingerprint
            is_candidate = item.action in ALERT_ACTIONS and not self.state_manager.is_alerted(fp)
            if is_candidate and fp not in delivered and fp not in skipped_on_purpose:
                pending += 1
                continue
            self.state_manager.record_opportunity(item.opportunity, item.score, item.action, alerted=fp in delivered)
        self.state_manager.prune(self.retention_days)
        self.state_manager.save()
        return pending

    def build_summary(self, ev: IncomeEvaluation, *, mode: str, trigger: str, emails: int,
                      errors: List[str], pending: int, run_id: Optional[str] = None) -> IncomeRunSummary:
        alerted = {fp for fp in (s.opportunity.fingerprint for s in ev.candidates) if self.state_manager.is_alerted(fp)}
        for item in ev.candidates:
            if item.opportunity.fingerprint in alerted:
                self._count(ev, item.opportunity.source, "alerted")
        return IncomeRunSummary(
            run_id=run_id or f"income_run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
            timestamp=datetime.now(timezone.utc),
            mode=mode,
            trigger=trigger,
            total_fetched=len(ev.raw),
            unique_candidates=len(ev.new),
            hard_rejected=sum(t.hard_rejected for t in ev.telemetry.values()),
            quality_rejected=ev.quality_rejected,
            ineligible=ev.ineligible,
            verification_failed=ev.dead_links,
            expired_links_removed=ev.dead_links,
            discarded=len(ev.discarded),
            low_matches=len(ev.low),
            digest_matches=len(ev.digest),
            instant_matches=len(ev.instant),
            high_quality=len(ev.candidates),
            emails_dispatched=emails,
            delivery_errors=errors,
            pending_alerts=pending,
            risk_rejected=sum(1 for s in ev.discarded if s.opportunity.verification_status == "rejected"),
            execution_time_seconds=round(time.perf_counter() - ev.started, 2),
            source_health=ev.health,
            source_telemetry=ev.telemetry,
            error_count=sum(1 for h in ev.health if h.status == "error"),
        )

    @staticmethod
    def record_summary(summary: IncomeRunSummary) -> None:
        append_run_log(income_run_logs_file(), summary.model_dump(mode="json"))

    # ------------------------------------------------------------------ standalone run
    async def execute(
        self,
        dry_run: bool = True,
        send_email: bool = False,
        force_all: bool = False,
        immediate_only: bool = False,
        recipient_email: str = "candidate@example.com",
        email_provider: str = "console",
        from_email: str = "alerts@jobsalert.dev",
        trigger: str = "manual",
    ) -> Tuple[IncomeRunSummary, List[ScoredOpportunity]]:
        """Runs a standalone income scan and sends its own digest."""
        mode = "dry_run" if dry_run else "live"
        print(f"\n💰 [INCOME SCOUT START] Mode: {mode.upper()} | Candidate: {self.config.candidate_name}")
        ev = await self.evaluate(force_all=force_all)
        print(f"📥 [COLLECTED] {len(ev.raw)} tracks, {len(ev.new)} new. Candidates: {len(ev.instant)} instant, {len(ev.digest)} digest.")

        selected = self.select_for_digest(ev)
        delivered: Set[str] = set()
        errors: List[str] = []
        emails = 0

        if not dry_run and send_email:
            for match in self.unalerted(ev.instant):
                result = await self.notifier.send_income_immediate(
                    scored=match, candidate_name=self.config.candidate_name, recipient_email=recipient_email,
                    email_provider=email_provider, from_email=from_email,
                )
                if result:
                    emails += 1
                    delivered.add(match.opportunity.fingerprint)
                else:
                    errors.append(f"Instant alert '{match.opportunity.title}': {getattr(result, 'error', 'failed')}")

            if not immediate_only and selected:
                result = await self.notifier.send_income_digest(
                    opportunities=selected, candidate_name=self.config.candidate_name, recipient_email=recipient_email,
                    email_provider=email_provider, from_email=from_email, instant_threshold=self.config.instant_alert_score,
                )
                if result:
                    emails += 1
                    delivered.update(s.opportunity.fingerprint for s in selected)
                else:
                    errors.append(f"Income digest: {getattr(result, 'error', 'failed')}")
        else:
            preview = selected or ev.low[:5] or ev.scored[:5]
            if preview:
                _subject, html, _text = self.notifier.render_income_digest(
                    preview, self.config.candidate_name, recipient_email, self.config.instant_alert_score,
                )
                self.notifier.save_preview(html)

        pending = 0 if dry_run else self.persist(ev, delivered)
        summary = self.build_summary(ev, mode=mode, trigger=trigger, emails=emails, errors=errors, pending=pending)
        self.record_summary(summary)
        print(f"🏁 [INCOME SCOUT FINISHED] {summary.execution_time_seconds}s | Emails: {emails} | Pending: {pending}\n")
        return summary, ev.scored


def get_income_run_logs() -> List[dict]:
    """Income run logs for the dashboard."""
    return read_run_logs(income_run_logs_file())
