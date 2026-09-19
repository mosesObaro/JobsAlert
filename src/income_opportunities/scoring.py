"""
Online Income Opportunities Scoring Engine.
Hard exclusions and a quality gate, geographic eligibility, side-job fit
(work that fits alongside a full-time job), relevance and pay, combined into a
0–10 score with configurable gates.
"""

from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from src.eligibility import CandidateGeo, classify, extract_places
from src.income_opportunities.config import OnlineIncomeConfig
from src.income_opportunities.models import (
    EligibilityStatus,
    GeographicScope,
    IncomeMatchBreakdown,
    OnlineIncomeOpportunity,
    OpportunityStatus,
    QualityBreakdown,
    ScoredOpportunity,
    SideJobFitBreakdown,
    SourceTrustTier,
)
from src.money import DEFAULT_FX_TO_USD, to_hourly_usd

TIER_ORDER = [
    SourceTrustTier.TIER_1_HIGHEST,
    SourceTrustTier.TIER_2_GOOD,
    SourceTrustTier.TIER_3_REVIEW,
    SourceTrustTier.TIER_4_LOW,
]
ASYNC_CATEGORIES = {
    "ai_evaluation", "ai_training", "data_annotation", "academic_editing", "proofreading",
    "user_testing", "transcription", "research",
}
# Minimum weekly hours implied by each time_commitment value
MIN_WEEKLY_HOURS = {"full_time": 40, "10_to_20_hrs": 10, "under_10_hrs": 0, "flexible": 0, "ad_hoc": 0}
FLEXIBILITY_RANK = {"low": 0, "medium": 1, "high": 2}


def _tier_rank(value: str) -> int:
    for rank, tier in enumerate(TIER_ORDER):
        if value.startswith(tier.value.rsplit("_", 1)[0]):  # "tier_2" matches "tier_2_good"
            return rank
    return len(TIER_ORDER) - 2  # unknown -> treat as tier 3


class IncomeScoringEngine:
    """Scores flexible online income opportunities with quality and side-job gates."""

    def __init__(self, config: OnlineIncomeConfig, fx_rates: Optional[Dict[str, float]] = None):
        self.config = config
        self.fx_rates = fx_rates or DEFAULT_FX_TO_USD
        self.candidate = CandidateGeo.from_locations(config.eligible_countries or ["Nigeria"])

    # ------------------------------------------------------------------
    def score_opportunity(self, opp: OnlineIncomeOpportunity) -> ScoredOpportunity:
        """Hard exclusions -> quality gate -> eligibility -> side-job fit -> relevance & pay -> score -> gates."""
        breakdown = IncomeMatchBreakdown()
        weights = self.config.scoring_weights

        def discard(reasons: List[str], prefix: str = "Hard Exclusion", highlight: Optional[str] = None,
                    quality_failed: bool = True) -> ScoredOpportunity:
            breakdown.penalties_applied.extend(f"{prefix}: {r}" for r in reasons)
            breakdown.rejection_reasons = list(reasons)
            breakdown.highlights.append(highlight or f"Excluded: {reasons[0]}")
            if quality_failed:
                breakdown.passed_quality_gate = False
            opp.final_score = 0.0
            return ScoredOpportunity(opportunity=opp, score=0.0, action="discard", breakdown=breakdown,
                                     scored_at=datetime.now(timezone.utc))

        # 1. HARD EXCLUSIONS -------------------------------------------------
        if opp.verification_status == "rejected" or opp.status == OpportunityStatus.REJECTED:
            breakdown.is_verified = False
            reasons = opp.rejection_reasons or opp.scam_risk_indicators or ["Disqualified by safety and legitimacy filter"]
            return discard(reasons, highlight="⚠️ Disqualified: Failed safety or quality screening.")

        if opp.status == OpportunityStatus.EXPIRED or not opp.is_verified:
            breakdown.is_verified = False
            return discard([f"URL unreachable or expired ({opp.link_verification_status})"],
                           highlight="⚠️ Disqualified: Application link is inactive.")

        norm_cat = opp.category.lower().strip()
        for excluded in self.config.excluded_categories or []:
            if excluded.lower() in norm_cat or (norm_cat and norm_cat in excluded.lower()):
                return discard([f"Category '{opp.category}' matches excluded category '{excluded}'"],
                               highlight=f"Excluded: Matches negative category '{opp.category}'.")

        tier = opp.source_trust_tier or SourceTrustTier.TIER_3_REVIEW
        if tier == SourceTrustTier.TIER_4_LOW or TIER_ORDER.index(tier) > _tier_rank(self.config.min_source_trust_tier):
            return discard([f"Source trust tier {tier.value} is below your minimum ({self.config.min_source_trust_tier})"])

        # 2. QUALITY GATE ----------------------------------------------------
        quality_score, quality_breakdown = self._evaluate_quality(opp)
        opp.quality_score = quality_score
        opp.quality_breakdown = quality_breakdown
        breakdown.quality_score = quality_score
        breakdown.passed_quality_gate = quality_breakdown.passed_quality_gate
        breakdown.source_quality_score = quality_breakdown.source_trust_score

        min_quality = self.config.minimum_quality_score or 7.0
        if quality_score < min_quality:
            reasons = quality_breakdown.reasons or [f"Quality score ({quality_score:.1f}/10) is below minimum threshold ({min_quality:.1f}/10)"]
            return discard(reasons, prefix="Quality Gate Failed",
                           highlight=f"⚠️ Disqualified: Quality score ({quality_score:.1f}/10) below threshold.")

        # 3. GEOGRAPHIC ELIGIBILITY ------------------------------------------
        eligibility_status, country_score, country_notes = self._evaluate_geographic_eligibility(opp)
        opp.eligibility_status = eligibility_status
        breakdown.country_eligibility_score = country_score
        breakdown.eligibility_status = eligibility_status.value
        if eligibility_status == EligibilityStatus.INELIGIBLE:
            return discard([f"Country restriction: {country_notes}"], highlight="Restricted location: Ineligible for your region.",
                           quality_failed=False)
        if eligibility_status == EligibilityStatus.UNKNOWN and self.config.reject_unknown_eligibility:
            return discard(["Eligible countries not stated"], quality_failed=False)

        has_pay = bool(opp.estimated_pay_min or opp.estimated_pay_max or (opp.pay_rate_display or "").strip())
        if not has_pay and self.config.reject_unknown_compensation:
            return discard(["Pay not stated"], quality_failed=False)

        # 4. SIDE-JOB FIT ----------------------------------------------------
        is_async = opp.is_asynchronous or norm_cat in ASYNC_CATEGORIES
        if self.config.allow_asynchronous_only and not is_async:
            return discard(["Needs fixed hours or live sessions (asynchronous work only)"], quality_failed=False)
        min_hours = MIN_WEEKLY_HOURS.get(opp.time_commitment, 0)
        if min_hours > (self.config.maximum_hours_per_week or 40):
            return discard([f"Needs about {min_hours}+ hours a week (your limit is {self.config.maximum_hours_per_week})"],
                           quality_failed=False)

        side_job_fit_score, side_job_breakdown = self._evaluate_side_job_fit(opp, is_async)
        opp.side_job_fit_score = side_job_fit_score
        opp.side_job_breakdown = side_job_breakdown
        breakdown.side_job_fit_score = side_job_fit_score
        breakdown.flexibility_score = side_job_breakdown.asynchronous_flexibility_score

        # 5. RELEVANCE & PAY -------------------------------------------------
        relevance_score, cat_notes = self._evaluate_relevance(opp)
        breakdown.relevance_score = relevance_score
        breakdown.category_score = relevance_score

        comp_score, comp_notes = self._evaluate_compensation(opp)
        breakdown.compensation_score = comp_score
        breakdown.ease_of_entry_score = 8.5 if opp.experience_requirement in ["none", "beginner"] else 6.5

        # 6. FINAL SCORE -----------------------------------------------------
        w_quality = weights.quality or 30.0
        w_relevance = weights.relevance or 25.0
        w_side_job = weights.side_job_fit or 20.0
        w_country = weights.country_eligibility or 15.0
        w_comp = weights.compensation or 10.0
        total_weight = (w_quality + w_relevance + w_side_job + w_country + w_comp) or 100.0
        raw_score = (
            quality_score * w_quality + relevance_score * w_relevance + side_job_fit_score * w_side_job
            + country_score * w_country + comp_score * w_comp
        ) / total_weight

        if opp.verification_status == "risk_flagged":
            raw_score *= 0.65
            breakdown.penalties_applied.append("Caution Flag: " + "; ".join(opp.scam_risk_indicators[:2] or ["unverified signals"]))

        final_score = round(max(0.0, min(10.0, raw_score)), 1)
        opp.final_score = final_score
        breakdown.final_score = final_score

        # 7. HIGHLIGHTS ------------------------------------------------------
        highlights: List[str] = []
        if quality_breakdown.source_trust_score >= 8.5:
            highlights.append(f"Platform: Known {tier.value.replace('_', ' ').title()} platform ({opp.organization})")
        highlights.extend(side_job_breakdown.highlights)
        if comp_notes:
            highlights.append(comp_notes)
        if country_notes:
            highlights.append(country_notes)
        if cat_notes and len(highlights) < 4:
            highlights.append(cat_notes)
        breakdown.highlights = highlights[:4]
        opp.highlights = breakdown.highlights

        # 8. TRIAGE & GATES --------------------------------------------------
        instant_thresh = self.config.instant_alert_score or 9.0
        digest_thresh = self.config.minimum_final_score or 7.5
        if final_score >= instant_thresh:
            action = "instant"
        elif final_score >= digest_thresh:
            action = "digest"
        elif final_score >= 5.0:
            action = "low_match"
        else:
            action = "discard"

        if action in ("instant", "digest"):
            if side_job_fit_score < (self.config.minimum_side_job_fit_score or 0.0):
                action = "low_match"
                breakdown.penalties_applied.append(
                    f"Side-job fit {side_job_fit_score:.1f} is below your minimum ({self.config.minimum_side_job_fit_score:.1f}); kept for review")
            elif self.config.require_verified_source and opp.verification_status != "verified_source":
                action = "low_match"
                breakdown.penalties_applied.append("Not from a known platform or your own list; kept for review in the dashboard")

        return ScoredOpportunity(opportunity=opp, score=final_score, action=action, breakdown=breakdown,
                                 scored_at=datetime.now(timezone.utc))

    # ------------------------------------------------------------------
    def _evaluate_quality(self, opp: OnlineIncomeOpportunity) -> Tuple[float, QualityBreakdown]:
        """Deterministic 0–10 quality score across five pillars."""
        reasons: List[str] = []

        trust_scores = {
            SourceTrustTier.TIER_1_HIGHEST: 10.0,
            SourceTrustTier.TIER_2_GOOD: 8.5,
            SourceTrustTier.TIER_3_REVIEW: 6.0,
            SourceTrustTier.TIER_4_LOW: 1.0,
        }
        trust_score = trust_scores.get(opp.source_trust_tier, 6.0)

        title_lower = opp.title.lower()
        has_concrete_role = any(
            r in title_lower for r in [
                "evaluator", "annotator", "trainer", "tutor", "proofreader", "editor", "tester", "transcriber",
                "assistant", "specialist", "moderator", "researcher", "analyst", "clerk", "contributor", "participant",
            ]
        )
        desc_len = len(opp.description.strip())
        if has_concrete_role and desc_len >= 50:
            specificity_score = 10.0
        elif has_concrete_role or desc_len >= 30:
            specificity_score = 8.0
        else:
            specificity_score = 4.0
            reasons.append("Vague opportunity description or non-specific task role")

        display = opp.pay_rate_display or ""
        has_exact_pay = bool(opp.estimated_pay_min or opp.estimated_pay_max)
        has_display = len(display.strip()) > 2
        if has_exact_pay or (has_display and any(symbol in display for symbol in "$₦£€")):
            if re.search(r"\b(up\s+to\s+\$\d{4,}|make\s+thousands)\b", display, re.IGNORECASE):
                comp_transparency_score = 2.0
                reasons.append("Vague or exaggerated earnings claim")
            else:
                comp_transparency_score = 10.0
        elif has_display:
            comp_transparency_score = 7.5
        else:
            comp_transparency_score = 4.5

        loc = (opp.location_eligibility or "").lower()
        if any(w in loc for w in ["worldwide", "global", "all countries", "anywhere", "nigeria"]):
            geo_clarity_score = 10.0
        elif "remote" in loc:
            geo_clarity_score = 7.5
        else:
            geo_clarity_score = 5.0

        app_url = opp.application_url or opp.url
        if app_url and app_url.startswith("https://") and not any(h in app_url for h in ["example.com", "placeholder"]):
            actionability_score = 10.0
        elif app_url:
            actionability_score = 7.0
        else:
            actionability_score = 2.0
            reasons.append("Missing direct application URL")

        raw_quality = (
            trust_score * 0.30 + specificity_score * 0.25 + comp_transparency_score * 0.20
            + geo_clarity_score * 0.15 + actionability_score * 0.10
        )
        quality_score = round(max(0.0, min(10.0, raw_quality)), 1)
        return quality_score, QualityBreakdown(
            source_trust_score=trust_score,
            specificity_score=specificity_score,
            compensation_transparency_score=comp_transparency_score,
            geographic_clarity_score=geo_clarity_score,
            actionability_score=actionability_score,
            passed_quality_gate=quality_score >= (self.config.minimum_quality_score or 7.0),
            reasons=reasons,
        )

    def _evaluate_geographic_eligibility(self, opp: OnlineIncomeOpportunity) -> Tuple[EligibilityStatus, float, str]:
        """Classifies eligibility for the candidate's countries (shared with job scoring)."""
        if opp.country_restrictions:
            # A restriction list names the only places allowed, even when the location says "Worldwide".
            restricted = classify(" ".join(opp.country_restrictions), self.candidate)
            if restricted.status == "ineligible":
                opp.geographic_scope = GeographicScope.REGION_SPECIFIC
                return EligibilityStatus.INELIGIBLE, 0.0, f"Location Ineligible: {restricted.reason}"
        result = classify(opp.location_eligibility or "", self.candidate, detail_text=opp.description)

        if result.status == "ineligible":
            opp.geographic_scope = GeographicScope.REGION_SPECIFIC
            return EligibilityStatus.INELIGIBLE, 0.0, f"Location Ineligible: {result.reason}"
        if result.status == "eligible":
            opp.geographic_scope = GeographicScope.WORLDWIDE if result.scope == "worldwide" else GeographicScope.COUNTRY_SPECIFIC
            label = self.candidate.label()
            return EligibilityStatus.ELIGIBLE, 10.0, (
                f"Location: 100% Remote ({label} eligible)" if result.scope == "worldwide" else f"Location: {result.reason}"
            )
        if opp.eligible_countries and any(self.candidate.accepts(p) for c in opp.eligible_countries for p in extract_places(c)):
            opp.geographic_scope = GeographicScope.COUNTRY_SPECIFIC
            return EligibilityStatus.ELIGIBLE, 10.0, "Location: Listed as open to your country"
        opp.geographic_scope = GeographicScope.UNKNOWN
        if "remote" in (opp.location_eligibility or "").lower():
            return EligibilityStatus.ELIGIBLE, 7.5, "Location: Remote (check the platform's country list when you sign up)"
        return EligibilityStatus.UNKNOWN, 5.0, "Location: Eligible countries not stated"

    def _evaluate_side_job_fit(self, opp: OnlineIncomeOpportunity, is_async: bool) -> Tuple[float, SideJobFitBreakdown]:
        """How well the work fits alongside a full-time job: schedule freedom, hours, task structure."""
        highlights: List[str] = []
        if is_async:
            async_score = 10.0
            highlights.append("🌙 Side-Job Fit: 100% Asynchronous (work evenings & weekends)")
            schedule = "Asynchronous / Self-Paced"
        elif opp.flexibility == "high":
            async_score = 8.5
            highlights.append("🌙 Side-Job Fit: Flexible drop-in hours")
            schedule = "Flexible Hours"
        elif opp.flexibility == "medium":
            async_score, schedule = 6.0, "Part-Time Flexible"
        else:
            async_score, schedule = 3.0, "Fixed Shift"

        preferred = FLEXIBILITY_RANK.get((self.config.preferred_flexibility or "any").lower())
        actual = FLEXIBILITY_RANK.get((opp.flexibility or "high").lower(), 2)
        if preferred is not None and actual < preferred and not is_async:
            async_score = max(0.0, async_score - 1.5 * (preferred - actual))

        if opp.time_commitment in ["flexible", "ad_hoc", "under_10_hrs"]:
            hours_score = 10.0
        elif opp.time_commitment == "10_to_20_hrs":
            hours_score = 8.0
        elif opp.time_commitment == "full_time":
            hours_score = 2.0
        else:
            hours_score = 7.5

        structure_score = 10.0 if opp.opportunity_type in ["per_task", "hourly", "study", "freelance_project"] else 6.0

        fit = round(max(0.0, min(10.0, async_score * 0.50 + hours_score * 0.30 + structure_score * 0.20)), 1)
        return fit, SideJobFitBreakdown(
            asynchronous_flexibility_score=async_score,
            hours_commitment_score=hours_score,
            task_structure_score=structure_score,
            schedule_description=schedule,
            highlights=highlights,
        )

    def _evaluate_compensation(self, opp: OnlineIncomeOpportunity) -> Tuple[float, str]:
        """Scores pay against the hourly floor (converted to USD)."""
        floor = self.config.minimum_hourly_rate_usd or 8.0
        currency = (opp.pay_currency or "USD").upper()
        display = opp.pay_rate_display
        penalty = 0.0
        note = ""
        preferred = [c.upper() for c in (self.config.preferred_currencies or [])]
        if preferred and currency not in preferred:
            penalty, note = 1.0, f" (pays in {currency})"

        pay = opp.estimated_pay_max or opp.estimated_pay_min
        if pay:
            period = "hourly" if opp.pay_frequency in (None, "", "hourly") else opp.pay_frequency
            hourly = to_hourly_usd(pay, currency, period, self.fx_rates) if period in ("hourly", "daily", "weekly", "monthly", "yearly") else None
            if hourly is None:
                # Per-task and per-session pay can't be converted to an hourly rate.
                hourly = pay * (self.fx_rates.get(currency) or 0.0) if currency != "USD" else pay
            label = display or f"${hourly:,.0f}/hr"
            if hourly >= floor * 2.5:
                return max(0.0, 10.0 - penalty), f"Compensation: Excellent rate ({label}){note}"
            if hourly >= floor * 1.5:
                return max(0.0, 9.0 - penalty), f"Compensation: High rate ({label}){note}"
            if hourly >= floor:
                return max(0.0, 7.5 - penalty), f"Compensation: Meets your floor ({label}){note}"
            return max(0.0, 4.0 - penalty), f"Compensation: Below target floor ({label}){note}"

        if display:
            return max(0.0, 7.5 - penalty), f"Compensation: {display}{note}"
        return 5.0, "Compensation: Project / task-based pay"

    def _evaluate_relevance(self, opp: OnlineIncomeOpportunity) -> Tuple[float, str]:
        """Category alignment with the candidate's preferred categories."""
        norm_cat = opp.category.lower().strip()
        preferred = [p.lower().strip() for p in (self.config.preferred_categories or [])]
        if any(p in norm_cat or norm_cat in p for p in preferred if p):
            return 10.0, f"Track: Preferred work category ({opp.category.replace('_', ' ').title()})"
        return 7.0, ""

