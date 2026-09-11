"""
Online Income Opportunities Relevance Scoring Engine.
Calculates a granular 0–10 score based on country eligibility, compensation,
legitimacy/verification, flexibility, category preferences, and recurring potential.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Tuple

from src.income_opportunities.config import OnlineIncomeConfig
from src.income_opportunities.models import (
    IncomeMatchBreakdown,
    OnlineIncomeOpportunity,
    ScoredOpportunity,
)


class IncomeScoringEngine:
    """Evaluates flexible online income opportunities against configured preferences."""

    def __init__(self, config: OnlineIncomeConfig):
        self.config = config

    def score_opportunity(self, opp: OnlineIncomeOpportunity) -> ScoredOpportunity:
        """Computes a deterministic 0–10 score and match breakdown for an opportunity."""
        breakdown = IncomeMatchBreakdown()
        weights = self.config.scoring_weights

        # ------------------------------------------------------------------
        # 1. HARD EXCLUSIONS & DISQUALIFIERS
        # ------------------------------------------------------------------
        # A. Rejected scam / risk flag
        if opp.verification_status == "rejected":
            breakdown.penalties_applied.append(f"Hard Exclusion: Scam or high-risk signal ({', '.join(opp.scam_risk_indicators)})")
            breakdown.highlights.append("⚠️ Disqualified: Failed safety and legitimacy screening.")
            breakdown.is_verified = False
            return ScoredOpportunity(
                opportunity=opp,
                score=0.0,
                action="discard",
                breakdown=breakdown,
                scored_at=datetime.now(timezone.utc),
            )

        # B. Dead / Unreachable link
        if not opp.is_verified:
            breakdown.penalties_applied.append("Hard Exclusion: Opportunity URL is unreachable or closed")
            breakdown.highlights.append("⚠️ Disqualified: Application link is inactive.")
            breakdown.is_verified = False
            return ScoredOpportunity(
                opportunity=opp,
                score=0.0,
                action="discard",
                breakdown=breakdown,
                scored_at=datetime.now(timezone.utc),
            )

        # C. Excluded categories (e.g. software engineering, crypto, marketing)
        norm_cat = opp.category.lower().strip()
        for exc in (self.config.excluded_categories or []):
            if exc.lower() in norm_cat or norm_cat in exc.lower():
                breakdown.penalties_applied.append(f"Hard Exclusion: Category '{opp.category}' is in excluded categories")
                breakdown.highlights.append(f"Excluded: Matches negative category '{opp.category}'.")
                return ScoredOpportunity(
                    opportunity=opp,
                    score=0.0,
                    action="discard",
                    breakdown=breakdown,
                    scored_at=datetime.now(timezone.utc),
                )

        # ------------------------------------------------------------------
        # 2. FACTOR EVALUATIONS (0.0 - 10.0 each)
        # ------------------------------------------------------------------

        # Factor A: Country Eligibility (25% Weight)
        country_score, country_notes = self._evaluate_country_eligibility(opp)
        breakdown.country_eligibility_score = country_score

        # If explicitly restricted from candidate's countries, drop heavily
        if country_score == 0.0:
            breakdown.penalties_applied.append("Country restriction: Opportunity not available in your configured regions")
            breakdown.highlights.append("Restricted location eligibility.")
            return ScoredOpportunity(
                opportunity=opp,
                score=0.0,
                action="discard",
                breakdown=breakdown,
                scored_at=datetime.now(timezone.utc),
            )

        # Factor B: Compensation & Pay Rate (20% Weight)
        comp_score, comp_notes = self._evaluate_compensation(opp)
        breakdown.compensation_score = comp_score

        # Factor C: Legitimacy & Verification (20% Weight)
        legit_score, legit_notes = self._evaluate_legitimacy(opp)
        breakdown.legitimacy_score = legit_score

        # Factor D: Flexibility & Time Commitment (15% Weight)
        flex_score, flex_notes = self._evaluate_flexibility(opp)
        breakdown.flexibility_score = flex_score

        # Factor E: Category Alignment (15% Weight)
        cat_score, cat_notes = self._evaluate_category(opp)
        breakdown.category_score = cat_score

        # Factor F: Ease of Entry & Recurring Potential (5% Weight)
        entry_score, entry_notes = self._evaluate_ease_and_recurring(opp)
        breakdown.ease_of_entry_score = entry_score
        breakdown.recurring_potential_score = entry_score

        # ------------------------------------------------------------------
        # 3. WEIGHTED SCORE CALCULATION
        # ------------------------------------------------------------------
        total_weight = (
            weights.country_eligibility +
            weights.compensation +
            weights.legitimacy_verification +
            weights.flexibility_time +
            weights.category_alignment +
            weights.ease_and_recurring
        ) or 100.0

        raw_score = (
            (country_score * weights.country_eligibility) +
            (comp_score * weights.compensation) +
            (legit_score * weights.legitimacy_verification) +
            (flex_score * weights.flexibility_time) +
            (cat_score * weights.category_alignment) +
            (entry_score * weights.ease_and_recurring)
        ) / total_weight

        # Apply mild caution penalty if risk flagged
        if opp.verification_status == "risk_flagged":
            raw_score *= 0.5
            breakdown.penalties_applied.append("Caution Flag: Minor unverified signals detected")

        final_score = round(max(0.0, min(10.0, raw_score)), 1)

        # ------------------------------------------------------------------
        # 4. HIGHLIGHTS GENERATION ("Why this is worth considering")
        # ------------------------------------------------------------------
        highlights: List[str] = []
        if country_notes:
            highlights.append(country_notes)
        if comp_notes:
            highlights.append(comp_notes)
        if legit_notes:
            highlights.append(legit_notes)
        if flex_notes and len(highlights) < 4:
            highlights.append(flex_notes)
        elif cat_notes and len(highlights) < 4:
            highlights.append(cat_notes)

        breakdown.highlights = highlights[:4]

        # ------------------------------------------------------------------
        # 5. ACTION TRIAGE
        # ------------------------------------------------------------------
        if final_score >= self.config.instant_alert_score:
            action = "instant"
        elif final_score >= self.config.minimum_score:
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

    def _evaluate_country_eligibility(self, opp: OnlineIncomeOpportunity) -> Tuple[float, str]:
        """Evaluates geographical and regional eligibility against configured user countries."""
        loc = (opp.location_eligibility or "").lower()
        user_countries = [c.lower().strip() for c in (self.config.eligible_countries or [])]

        # 1. Worldwide / Global / All countries
        if any(w in loc for w in ["worldwide", "global", "all countries", "anywhere", "remote (global)"]):
            matched_c = "Worldwide / " + self.config.eligible_countries[0] if self.config.eligible_countries else "Worldwide"
            return 10.0, f"Location: 100% Remote ({matched_c} eligible)"

        # 2. Check if explicitly listed in eligible countries
        for c in user_countries:
            if c in loc or any(c in ec.lower() for ec in opp.eligible_countries):
                return 10.0, f"Location: Verified eligibility in {c.title()}"

        # 3. Check country restrictions
        if opp.country_restrictions:
            # If restrictions explicitly exclude the user's country
            for c in user_countries:
                if any(c in cr.lower() for cr in opp.country_restrictions):
                    return 0.0, ""
            # If restricted to US/UK/Canada only and user is not in those
            us_uk_only = any(r in " ".join(opp.country_restrictions).lower() for r in ["us only", "usa only", "uk only"])
            if us_uk_only and not any(c in ["us", "usa", "united states", "uk"] for c in user_countries):
                return 0.0, ""

        # 4. Unspecified / Remote
        if "remote" in loc:
            return 7.0, "Location: Remote (verify specific country eligibility on platform)"

        return 6.0, "Location: Unspecified flexible location"

    def _evaluate_compensation(self, opp: OnlineIncomeOpportunity) -> Tuple[float, str]:
        """Scores estimated pay or hourly rate relative to the candidate floor."""
        floor = self.config.minimum_hourly_rate_usd or 5.0
        pay_min = opp.estimated_pay_min
        pay_max = opp.estimated_pay_max
        display = opp.pay_rate_display

        if pay_min or pay_max:
            effective_pay = pay_max or pay_min or 0.0
            if effective_pay >= floor * 3:
                return 10.0, f"Compensation: Excellent rate ({display or f'${effective_pay:.0f}/hr'})"
            elif effective_pay >= floor * 1.5:
                return 8.5, f"Compensation: Good rate ({display or f'${effective_pay:.0f}/hr'})"
            elif effective_pay >= floor:
                return 7.0, f"Compensation: Meets minimum threshold ({display or f'${effective_pay:.0f}/hr'})"
            else:
                return 3.5, f"Compensation: Below target threshold ({display or f'${effective_pay:.0f}/hr'})"

        if display:
            return 7.0, f"Compensation: {display}"

        return 5.5, "Compensation: Performance / per-task based pay"

    def _evaluate_legitimacy(self, opp: OnlineIncomeOpportunity) -> Tuple[float, str]:
        """Scores source quality, platform recognition, and security."""
        status = opp.verification_status
        if status == "verified_source":
            return 10.0, f"Legitimacy: Established, verified platform ({opp.organization})"
        elif status == "needs_review":
            return 7.0, f"Legitimacy: Standard active opportunity ({opp.organization})"
        elif status == "risk_flagged":
            return 2.5, "Caution: Unverified signals detected (review before applying)"
        return 0.0, ""

    def _evaluate_flexibility(self, opp: OnlineIncomeOpportunity) -> Tuple[float, str]:
        """Scores scheduling freedom, hours, and asynchronous nature."""
        if opp.is_flexible and opp.flexibility == "high":
            return 10.0, "Flexibility: High (self-paced, asynchronous task schedule)"
        elif opp.flexibility == "medium":
            return 8.0, "Flexibility: Moderate (flexible hours within weekly target)"
        return 6.5, "Flexibility: Standard flexible commitment"

    def _evaluate_category(self, opp: OnlineIncomeOpportunity) -> Tuple[float, str]:
        """Scores category preference alignment."""
        norm_cat = opp.category.lower().strip()
        preferred = [p.lower().strip() for p in (self.config.preferred_categories or [])]

        if any(p in norm_cat or norm_cat in p for p in preferred):
            readable = opp.category.replace("_", " ").title()
            return 10.0, f"Category: Matches preferred track ({readable})"
        return 6.0, ""

    def _evaluate_ease_and_recurring(self, opp: OnlineIncomeOpportunity) -> Tuple[float, str]:
        """Scores accessibility, recurring task pool, and onboarding ease."""
        if opp.opportunity_type in ["hourly", "per_task"] and opp.experience_requirement in ["none", "beginner"]:
            return 10.0, "Accessibility: Accessible entry with recurring task pool"
        return 7.0, "Accessibility: Standard onboarding process"
