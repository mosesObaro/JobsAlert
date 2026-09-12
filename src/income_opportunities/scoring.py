"""
Online Income Opportunities High-Precision Scoring Engine.
Implements a strict pre-scoring Quality Gate, Source Trust Model,
Side-Job Fit Evaluation (for supplementary work alongside full-time careers),
Geographic Eligibility Classification, and Multi-Factor Final Scoring.
"""

from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple

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


class IncomeScoringEngine:
    """Evaluates flexible online income opportunities with strict quality and side-job gating."""

    def __init__(self, config: OnlineIncomeConfig):
        self.config = config

    def score_opportunity(self, opp: OnlineIncomeOpportunity) -> ScoredOpportunity:
        """
        Executes the full evaluation pipeline:
        Hard Rejection -> Quality Gate -> Geographic Eligibility -> Side-Job Fit -> Relevance -> Final Score.
        """
        breakdown = IncomeMatchBreakdown()
        weights = self.config.scoring_weights

        # ------------------------------------------------------------------
        # 1. HARD EXCLUSIONS & DISQUALIFIERS
        # ------------------------------------------------------------------
        # A. Rejected scam / fraud / non-work advice / MLMs
        if opp.verification_status == "rejected" or opp.status == OpportunityStatus.REJECTED:
            reasons = opp.rejection_reasons or opp.scam_risk_indicators or ["Disqualified by safety and legitimacy filter"]
            breakdown.penalties_applied.extend([f"Hard Exclusion: {r}" for r in reasons])
            breakdown.rejection_reasons = reasons
            breakdown.highlights.append("⚠️ Disqualified: Failed safety or quality screening.")
            breakdown.is_verified = False
            breakdown.passed_quality_gate = False
            opp.final_score = 0.0
            return ScoredOpportunity(
                opportunity=opp,
                score=0.0,
                action="discard",
                breakdown=breakdown,
                scored_at=datetime.now(timezone.utc),
            )

        # B. Expired or Unreachable link
        if opp.status == OpportunityStatus.EXPIRED or not opp.is_verified:
            breakdown.penalties_applied.append(f"Hard Exclusion: URL unreachable or expired ({opp.link_verification_status})")
            breakdown.rejection_reasons = [f"Application link is inactive/closed ({opp.link_verification_status})"]
            breakdown.highlights.append("⚠️ Disqualified: Application link is inactive.")
            breakdown.is_verified = False
            breakdown.passed_quality_gate = False
            opp.final_score = 0.0
            return ScoredOpportunity(
                opportunity=opp,
                score=0.0,
                action="discard",
                breakdown=breakdown,
                scored_at=datetime.now(timezone.utc),
            )

        # C. Excluded categories (e.g. passive_income, dropshipping, software_dev)
        norm_cat = opp.category.lower().strip()
        for exc in (self.config.excluded_categories or []):
            if exc.lower() in norm_cat or norm_cat in exc.lower():
                reason = f"Category '{opp.category}' matches excluded category '{exc}'"
                breakdown.penalties_applied.append(f"Hard Exclusion: {reason}")
                breakdown.rejection_reasons = [reason]
                breakdown.highlights.append(f"Excluded: Matches negative category '{opp.category}'.")
                breakdown.passed_quality_gate = False
                opp.final_score = 0.0
                return ScoredOpportunity(
                    opportunity=opp,
                    score=0.0,
                    action="discard",
                    breakdown=breakdown,
                    scored_at=datetime.now(timezone.utc),
                )

        # ------------------------------------------------------------------
        # 2. DETERMINISTIC QUALITY EVALUATION & QUALITY GATE
        # ------------------------------------------------------------------
        quality_score, quality_breakdown = self._evaluate_quality(opp)
        opp.quality_score = quality_score
        opp.quality_breakdown = quality_breakdown
        breakdown.quality_score = quality_score
        breakdown.passed_quality_gate = quality_breakdown.passed_quality_gate
        breakdown.source_quality_score = quality_breakdown.source_trust_score

        # Enforce Hard Quality Gate
        min_quality = self.config.minimum_quality_score or 7.0
        if quality_score < min_quality:
            reasons = quality_breakdown.reasons or [f"Quality score ({quality_score:.1f}/10) is below minimum threshold ({min_quality:.1f}/10)"]
            breakdown.penalties_applied.extend([f"Quality Gate Failed: {r}" for r in reasons])
            breakdown.rejection_reasons = reasons
            breakdown.highlights.append(f"⚠️ Disqualified: Quality score ({quality_score:.1f}/10) below threshold.")
            opp.final_score = 0.0
            return ScoredOpportunity(
                opportunity=opp,
                score=0.0,
                action="discard",
                breakdown=breakdown,
                scored_at=datetime.now(timezone.utc),
            )

        # ------------------------------------------------------------------
        # 3. GEOGRAPHIC ELIGIBILITY EVALUATION
        # ------------------------------------------------------------------
        eligibility_status, country_score, country_notes = self._evaluate_geographic_eligibility(opp)
        opp.eligibility_status = eligibility_status
        breakdown.country_eligibility_score = country_score
        breakdown.eligibility_status = eligibility_status.value

        # Hard gate on ineligibility (e.g. US-only when candidate is in Nigeria)
        if eligibility_status == EligibilityStatus.INELIGIBLE or country_score == 0.0:
            reason = "Country restriction: Opportunity explicitly excludes your configured region (Nigeria / Africa)"
            breakdown.penalties_applied.append(f"Hard Exclusion: {reason}")
            breakdown.rejection_reasons = [reason]
            breakdown.highlights.append("Restricted location: Ineligible for your region.")
            opp.final_score = 0.0
            return ScoredOpportunity(
                opportunity=opp,
                score=0.0,
                action="discard",
                breakdown=breakdown,
                scored_at=datetime.now(timezone.utc),
            )

        # ------------------------------------------------------------------
        # 4. SIDE-JOB FIT EVALUATION (0–10)
        # ------------------------------------------------------------------
        side_job_fit_score, side_job_breakdown = self._evaluate_side_job_fit(opp)
        opp.side_job_fit_score = side_job_fit_score
        opp.side_job_breakdown = side_job_breakdown
        breakdown.side_job_fit_score = side_job_fit_score
        breakdown.flexibility_score = side_job_breakdown.asynchronous_flexibility_score

        # ------------------------------------------------------------------
        # 5. RELEVANCE & COMPENSATION EVALUATION
        # ------------------------------------------------------------------
        relevance_score, cat_notes = self._evaluate_relevance(opp)
        breakdown.relevance_score = relevance_score
        breakdown.category_score = relevance_score

        comp_score, comp_notes = self._evaluate_compensation(opp)
        breakdown.compensation_score = comp_score

        entry_score = 8.5 if opp.experience_requirement in ["none", "beginner"] else 6.5
        breakdown.ease_of_entry_score = entry_score

        # ------------------------------------------------------------------
        # 6. FINAL WEIGHTED SCORE CALCULATION
        # ------------------------------------------------------------------
        w_quality = weights.quality or 30.0
        w_relevance = weights.relevance or 25.0
        w_side_job = weights.side_job_fit or 20.0
        w_country = weights.country_eligibility or 15.0
        w_comp = weights.compensation or 10.0

        total_weight = w_quality + w_relevance + w_side_job + w_country + w_comp or 100.0

        raw_score = (
            (quality_score * w_quality) +
            (relevance_score * w_relevance) +
            (side_job_fit_score * w_side_job) +
            (country_score * w_country) +
            (comp_score * w_comp)
        ) / total_weight

        # Mild caution discount if risk flagged
        if opp.verification_status == "risk_flagged":
            raw_score *= 0.65
            breakdown.penalties_applied.append("Caution Flag: Minor unverified signals detected")

        final_score = round(max(0.0, min(10.0, raw_score)), 1)
        opp.final_score = final_score
        breakdown.final_score = final_score

        # ------------------------------------------------------------------
        # 7. STRUCTURED HIGHLIGHTS ("Why this is worth considering")
        # ------------------------------------------------------------------
        highlights: List[str] = []
        if quality_breakdown.source_trust_score >= 8.5:
            highlights.append(f"Platform: Verified {opp.source_trust_tier.value.replace('_', ' ').title()} ({opp.organization})")
        if side_job_breakdown.highlights:
            highlights.extend(side_job_breakdown.highlights)
        if comp_notes:
            highlights.append(comp_notes)
        if country_notes:
            highlights.append(country_notes)
        if cat_notes and len(highlights) < 4:
            highlights.append(cat_notes)

        breakdown.highlights = highlights[:4]
        opp.highlights = breakdown.highlights

        # ------------------------------------------------------------------
        # 8. ACTION TRIAGE
        # ------------------------------------------------------------------
        instant_thresh = self.config.instant_alert_score or 9.0
        min_final_thresh = self.config.minimum_final_score or 7.5

        if final_score >= instant_thresh and opp.is_verified:
            action = "instant"
        elif final_score >= min_final_thresh and opp.is_verified:
            action = "digest"
        elif final_score >= 5.0:
            action = "low_match"
        else:
            action = "discard"

        return ScoredOpportunity(
            opportunity=opp,
            score=final_score,
            action=action,
            breakdown=breakdown,
            scored_at=datetime.now(timezone.utc),
        )

    def _evaluate_quality(self, opp: OnlineIncomeOpportunity) -> Tuple[float, QualityBreakdown]:
        """Calculates deterministic quality score from 0–10 across 5 objective pillars."""
        reasons: List[str] = []

        # Pillar 1: Source Trust (30% weight)
        trust_scores = {
            SourceTrustTier.TIER_1_HIGHEST: 10.0,
            SourceTrustTier.TIER_2_GOOD: 8.5,
            SourceTrustTier.TIER_3_REVIEW: 6.0,
            SourceTrustTier.TIER_4_LOW: 1.0,
        }
        trust_score = trust_scores.get(opp.source_trust_tier, 6.0)

        # Pillar 2: Opportunity Specificity (25% weight)
        # Checks if task and role are clearly identified
        title_lower = opp.title.lower()
        has_concrete_role = any(
            r in title_lower for r in [
                "evaluator", "annotator", "trainer", "tutor", "proofreader",
                "editor", "tester", "transcriber", "assistant", "specialist",
                "moderator", "researcher", "analyst", "clerk", "contributor"
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

        # Pillar 3: Compensation Transparency (20% weight)
        has_exact_pay = bool(opp.estimated_pay_min or opp.estimated_pay_max)
        has_display = bool(opp.pay_rate_display and len(opp.pay_rate_display.strip()) > 2)

        if has_exact_pay or (has_display and "$" in opp.pay_rate_display or "₦" in (opp.pay_rate_display or "") or "£" in (opp.pay_rate_display or "") or "€" in (opp.pay_rate_display or "")):
            # Check for vague exaggeration
            if opp.pay_rate_display and re.search(r"\b(up\s+to\s+\$\d{4,}|make\s+thousands)\b", opp.pay_rate_display, re.IGNORECASE):
                comp_transparency_score = 2.0
                reasons.append("Vague or exaggerated earnings claim")
            else:
                comp_transparency_score = 10.0
        elif has_display:
            comp_transparency_score = 7.5
        else:
            comp_transparency_score = 4.5  # Unknown compensation reduces quality score

        # Pillar 4: Geographic Clarity (15% weight)
        loc = (opp.location_eligibility or "").lower()
        if any(w in loc for w in ["worldwide", "global", "all countries", "anywhere", "nigeria"]):
            geo_clarity_score = 10.0
        elif "remote" in loc:
            geo_clarity_score = 7.5
        else:
            geo_clarity_score = 5.0

        # Pillar 5: Application Actionability (10% weight)
        app_url = opp.application_url or opp.url
        if app_url and app_url.startswith("https://") and not any(h in app_url for h in ["example.com", "placeholder"]):
            actionability_score = 10.0
        elif app_url:
            actionability_score = 7.0
        else:
            actionability_score = 2.0
            reasons.append("Missing direct application URL")

        # Weighted calculation
        raw_quality = (
            (trust_score * 0.30) +
            (specificity_score * 0.25) +
            (comp_transparency_score * 0.20) +
            (geo_clarity_score * 0.15) +
            (actionability_score * 0.10)
        )
        quality_score = round(max(0.0, min(10.0, raw_quality)), 1)
        passed_gate = quality_score >= (self.config.minimum_quality_score or 7.0)

        breakdown = QualityBreakdown(
            source_trust_score=trust_score,
            specificity_score=specificity_score,
            compensation_transparency_score=comp_transparency_score,
            geographic_clarity_score=geo_clarity_score,
            actionability_score=actionability_score,
            passed_quality_gate=passed_gate,
            reasons=reasons,
        )

        return quality_score, breakdown

    def _evaluate_geographic_eligibility(self, opp: OnlineIncomeOpportunity) -> Tuple[EligibilityStatus, float, str]:
        """Classifies geographic eligibility against candidate countries (e.g. Nigeria)."""
        loc = (opp.location_eligibility or "").lower()
        user_countries = [c.lower().strip() for c in (self.config.eligible_countries or ["Nigeria", "Worldwide"])]
        candidate_primary_country = self.config.eligible_countries[0] if self.config.eligible_countries else "Nigeria"

        # 1. Check explicit country restrictions first
        all_restrictions = " ".join(opp.country_restrictions).lower()
        if opp.country_restrictions or "only" in loc:
            # Check US/UK/Canada/EU exclusivity
            exclusive_patterns = [
                (r"\b(us\s+only|usa\s+only|united\s+states\s+only|u\.s\.\s+only)\b", "US Only"),
                (r"\b(uk\s+only|united\s+kingdom\s+only)\b", "UK Only"),
                (r"\b(canada\s+only)\b", "Canada Only"),
                (r"\b(eu\s+only|europe\s+only)\b", "EU Only"),
                (r"\b(north\s+america\s+only)\b", "North America Only"),
            ]
            for pat, region_name in exclusive_patterns:
                if re.search(pat, f"{loc} {all_restrictions}", re.IGNORECASE):
                    # If candidate's configured country is NOT in that exclusive region
                    if not any(c in ["us", "usa", "united states", "uk", "canada", "europe"] for c in user_countries):
                        opp.geographic_scope = GeographicScope.REGION_SPECIFIC
                        return EligibilityStatus.INELIGIBLE, 0.0, f"Location Ineligible: Restricted to {region_name}"

        # 2. Worldwide / Global / All countries
        if any(w in loc for w in ["worldwide", "global", "all countries", "anywhere", "remote (global)"]):
            opp.geographic_scope = GeographicScope.WORLDWIDE
            return EligibilityStatus.ELIGIBLE, 10.0, f"Location: 100% Remote ({candidate_primary_country} eligible)"

        # 3. Explicitly mentions candidate country
        for c in user_countries:
            if c in loc or any(c in ec.lower() for ec in opp.eligible_countries):
                opp.geographic_scope = GeographicScope.COUNTRY_SPECIFIC
                return EligibilityStatus.ELIGIBLE, 10.0, f"Location: Verified eligibility in {c.title()}"

        # 4. Remote (with no conflicting restrictions)
        if "remote" in loc:
            opp.geographic_scope = GeographicScope.UNKNOWN
            return EligibilityStatus.ELIGIBLE, 7.5, "Location: Remote (verify specific country portal onboarding)"

        opp.geographic_scope = GeographicScope.UNKNOWN
        return EligibilityStatus.UNKNOWN, 5.0, "Location: Unspecified flexible location"

    def _evaluate_side_job_fit(self, opp: OnlineIncomeOpportunity) -> Tuple[float, SideJobFitBreakdown]:
        """
        Evaluates whether the opportunity is realistically doable alongside a full-time career:
        Asynchronous freedom, evenings/weekends, low minimum hours, and task-based structure.
        """
        highlights: List[str] = []

        # 1. Asynchrony & Schedule Freedom (50% weight)
        # Categories inherently asynchronous: AI evaluation, annotation, proofreading, transcription, user testing
        async_categories = {
            "ai_evaluation", "ai_training", "data_annotation",
            "academic_editing", "proofreading", "user_testing",
            "transcription", "research"
        }
        if opp.category in async_categories or opp.is_asynchronous:
            asynch_score = 10.0
            highlights.append("🌙 Side-Job Fit: 100% Asynchronous (work evenings & weekends)")
            sched_desc = "Asynchronous / Self-Paced"
        elif opp.flexibility == "high":
            asynch_score = 8.5
            highlights.append("🌙 Side-Job Fit: Flexible drop-in hours")
            sched_desc = "Flexible Hours"
        elif opp.flexibility == "medium":
            asynch_score = 6.0
            sched_desc = "Part-Time Flexible"
        else:
            asynch_score = 3.0
            sched_desc = "Fixed Shift"

        # 2. Hours Commitment (30% weight)
        if opp.time_commitment in ["flexible", "ad_hoc", "under_10_hrs"]:
            hours_score = 10.0
        elif opp.time_commitment == "10_to_20_hrs":
            hours_score = 8.0
        elif opp.time_commitment == "full_time":
            hours_score = 2.0
        else:
            hours_score = 7.5

        # 3. Task Structure (20% weight)
        if opp.opportunity_type in ["per_task", "hourly", "study", "freelance_project"]:
            structure_score = 10.0
        else:
            structure_score = 6.0

        raw_fit = (asynch_score * 0.50) + (hours_score * 0.30) + (structure_score * 0.20)
        side_job_fit_score = round(max(0.0, min(10.0, raw_fit)), 1)

        breakdown = SideJobFitBreakdown(
            asynchronous_flexibility_score=asynch_score,
            hours_commitment_score=hours_score,
            task_structure_score=structure_score,
            schedule_description=sched_desc,
            highlights=highlights,
        )

        return side_job_fit_score, breakdown

    def _evaluate_compensation(self, opp: OnlineIncomeOpportunity) -> Tuple[float, str]:
        """Scores pay rate relative to candidate minimum hourly floor ($8.0/hr default)."""
        floor = self.config.minimum_hourly_rate_usd or 8.0
        pay_min = opp.estimated_pay_min
        pay_max = opp.estimated_pay_max
        display = opp.pay_rate_display

        if pay_min or pay_max:
            effective_pay = pay_max or pay_min or 0.0
            if effective_pay >= floor * 2.5:
                return 10.0, f"Compensation: Excellent rate ({display or f'${effective_pay:.0f}/hr'})"
            elif effective_pay >= floor * 1.5:
                return 9.0, f"Compensation: High rate ({display or f'${effective_pay:.0f}/hr'})"
            elif effective_pay >= floor:
                return 7.5, f"Compensation: Verified rate ({display or f'${effective_pay:.0f}/hr'})"
            else:
                return 4.0, f"Compensation: Below target floor ({display or f'${effective_pay:.0f}/hr'})"

        if display:
            return 7.5, f"Compensation: {display}"

        return 5.0, "Compensation: Project / task-based pay"

    def _evaluate_relevance(self, opp: OnlineIncomeOpportunity) -> Tuple[float, str]:
        """Scores category alignment against candidate preferences."""
        norm_cat = opp.category.lower().strip()
        preferred = [p.lower().strip() for p in (self.config.preferred_categories or [])]

        if any(p in norm_cat or norm_cat in p for p in preferred):
            readable = opp.category.replace("_", " ").title()
            return 10.0, f"Track: Preferred work category ({readable})"
        return 7.0, ""
