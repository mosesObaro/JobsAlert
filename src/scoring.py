"""
JobsAlert Relevance & Scoring Engine.
Weighted 0–10 score with a transparent breakdown and 'Why You Match' bullets.
"""

from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import Optional

from src.config import AppConfig, JobSpecConfig
from src.eligibility import CandidateGeo, classify, display_place
from src.matching import contains_phrase, word_set
from src.models import JobPosting, MatchBreakdown, ScoredJob
from src.money import format_range, to_annual_usd

JUNIOR_LEVELS = {"junior", "entry", "intern", "internship"}
SENIOR_LEVELS = {"senior", "lead", "staff", "principal", "director"}
JUNIOR_TITLE = re.compile(r"(?<![a-z0-9])(interns?|internships?|junior|graduate|trainee)(?![a-z0-9])")
REMOTE_TERMS = ("remote", "anywhere", "worldwide", "work from home")
LOCATION_WILDCARDS = {"remote", "worldwide", "anywhere"}
STOPWORDS = {"and", "or", "of", "the", "a", "an", "for", "to", "in", "with", "&", "-", "/"}
ATS_SOURCES = {"greenhouse", "lever", "ashby"}


class ScoringEngine:
    """Scores job postings against a job spec (defaults come from the profile and filters)."""

    def __init__(self, config: AppConfig):
        self.config = config

    def score_job(self, job: JobPosting, spec: Optional[JobSpecConfig] = None) -> ScoredJob:
        base = spec or self.config.get_effective_job_specs()[0]
        s = base.resolved(self.config.profile, self.config.filters, self.config.scoring_weights)
        spec_name = spec.name if spec else None
        weights = s.scoring_weights or self.config.scoring_weights

        breakdown = MatchBreakdown()
        title = job.title
        title_lower = title.lower()
        full_text = f"{job.title} {job.location} {job.description} {' '.join(job.tags)}"

        def discard(reason: str) -> ScoredJob:
            breakdown.penalties_applied.append(reason)
            return ScoredJob(job=job, score=0.0, action="discard", breakdown=breakdown, spec_name=spec_name)

        # -------------------------------------------------------------
        # 1. HARD EXCLUSIONS (score 0.0 -> discard)
        # -------------------------------------------------------------
        for company in s.excluded_companies:
            if company and contains_phrase(job.company, company):
                return discard(f"Blacklisted company: {company}")

        for term in s.excluded_terms:
            if not term:
                continue
            if contains_phrase(title, term):
                return discard(f"Excluded term in title: {term}")
            if contains_phrase(full_text, term):
                return discard(f"Excluded term in description: {term}")

        spec_seniority = (s.seniority or "").lower().strip()
        years = s.experience_years if s.experience_years is not None else self.config.profile.experience_years
        if spec_seniority in JUNIOR_LEVELS:
            is_junior_spec, is_senior_spec = True, False
        elif spec_seniority in SENIOR_LEVELS:
            is_junior_spec, is_senior_spec = False, True
        else:
            is_junior_spec, is_senior_spec = years <= 2, years >= 5

        if is_senior_spec and JUNIOR_TITLE.search(title_lower):
            return discard("Junior/Intern role mismatch for experienced candidate")

        # -------------------------------------------------------------
        # 2. TITLE & CORE STACK
        # -------------------------------------------------------------
        max_title_stack_weight = weights.title_and_stack

        title_match_ratio = 0.0
        best_role_match = ""
        title_words = word_set(title) - STOPWORDS
        for role in s.get_all_roles():
            if contains_phrase(title, role):
                title_match_ratio, best_role_match = 1.0, role
                break
            role_words = word_set(role) - STOPWORDS
            overlap = len(role_words & title_words) / max(len(role_words), 1)
            if overlap > title_match_ratio:
                title_match_ratio, best_role_match = overlap, role

        must_have = s.get_must_have_skills()
        matched_must = [skill for skill in must_have if contains_phrase(full_text, skill)]
        breakdown.matched_must_have = matched_must
        breakdown.missing_must_have = [skill for skill in must_have if skill not in matched_must]
        must_have_ratio = len(matched_must) / len(must_have) if must_have else 1.0

        nice_to_have = s.nice_to_have_skills
        matched_nice = [skill for skill in nice_to_have if contains_phrase(full_text, skill)]
        breakdown.matched_nice_to_have = matched_nice
        nice_ratio = min(len(matched_nice) / len(nice_to_have), 1.0) if nice_to_have else 0.5

        title_stack_fraction = (title_match_ratio * 0.45) + (must_have_ratio * 0.40) + (nice_ratio * 0.15)
        raw_title_score = title_stack_fraction * max_title_stack_weight
        breakdown.title_score = round(title_match_ratio * (max_title_stack_weight * 0.45), 2)
        breakdown.stack_score = round((must_have_ratio * 0.40 + nice_ratio * 0.15) * max_title_stack_weight, 2)

        # -------------------------------------------------------------
        # 3. REMOTE POLICY, LOCATION & ELIGIBILITY
        # -------------------------------------------------------------
        max_location_weight = weights.location_remote
        preferred_locs = list(s.preferred_locations)
        if s.remote is True and not any(p.lower() in LOCATION_WILDCARDS for p in preferred_locs):
            preferred_locs.extend(["Remote", "Worldwide"])
        candidate = CandidateGeo.from_locations(preferred_locs)
        user_wants_remote = any(p.lower() in LOCATION_WILDCARDS for p in preferred_locs)
        loc_text = f"{job.location} {job.remote_scope}"
        is_job_remote = job.is_remote or any(contains_phrase(loc_text, term) for term in REMOTE_TERMS)

        if is_job_remote:
            eligibility = classify(loc_text, candidate, detail_text=job.description)
            breakdown.eligibility = eligibility.status
            if eligibility.status == "eligible":
                location_score_fraction = 1.0
                if eligibility.scope == "worldwide":
                    breakdown.highlights.append("Worldwide remote: open to all locations")
                else:
                    breakdown.highlights.append(f"Remote, open to {display_place(eligibility.places[0])}")
            elif eligibility.status == "ineligible":
                location_score_fraction = 0.1
                breakdown.penalties_applied.append(f"Remote but {eligibility.reason[0].lower()}{eligibility.reason[1:]}")
            else:
                location_score_fraction = 0.85
                breakdown.highlights.append(f"Remote position: {job.location}")
        else:
            here = classify(job.location, candidate)
            specific_prefs = [p for p in preferred_locs if p.lower() not in LOCATION_WILDCARDS]
            if here.status == "eligible" or any(contains_phrase(loc_text, p) for p in specific_prefs):
                location_score_fraction = 0.95
                breakdown.highlights.append(f"Matches preferred on-site / hybrid location: {job.location}")
            elif contains_phrase(loc_text, "hybrid") and user_wants_remote:
                location_score_fraction = 0.4
                breakdown.penalties_applied.append("Hybrid role (requires physical presence)")
            else:
                location_score_fraction = 0.2
                breakdown.penalties_applied.append(f"Non-matching on-site location: {job.location}")

        raw_location_score = location_score_fraction * max_location_weight
        breakdown.location_score = round(raw_location_score, 2)

        # -------------------------------------------------------------
        # 4. COMPENSATION FIT (converted to annual USD)
        # -------------------------------------------------------------
        max_comp_weight = weights.compensation
        comp_score_fraction = 0.7  # neutral when undisclosed or not convertible
        salary_floor = s.salary_floor_usd if s.salary_floor_usd is not None else self.config.profile.salary_floor_usd

        if job.salary_max or job.salary_min:
            currency = (job.salary_currency or "USD").upper()
            period = job.salary_period or "yearly"
            high = job.salary_max or job.salary_min
            low = job.salary_min or high
            if period == "yearly" and high < 1000:
                period = "hourly"  # "$45 - $60" labelled yearly is an hourly rate
            display = format_range(low, high, currency, None if period == "yearly" else period)
            annual_high = to_annual_usd(high, currency, period, self.config.fx_rates_to_usd)
            annual_low = to_annual_usd(low, currency, period, self.config.fx_rates_to_usd)

            if annual_high is None:
                breakdown.highlights.append(f"Compensation in {currency}: {display} (no exchange rate configured)")
            else:
                usd_note = "" if (currency == "USD" and period == "yearly") else f" (≈ ${annual_low:,.0f}–${annual_high:,.0f}/yr)"
                if annual_high >= salary_floor * 1.3:
                    comp_score_fraction = 1.0
                    breakdown.highlights.append(f"Top-tier compensation: {display}{usd_note}")
                elif annual_high >= salary_floor:
                    comp_score_fraction = 0.9
                    breakdown.highlights.append(f"Meets salary floor (${salary_floor:,.0f}): posted {display}{usd_note}")
                elif annual_high >= salary_floor * 0.8:
                    comp_score_fraction = 0.5
                    breakdown.penalties_applied.append(f"Compensation slightly below floor ({display}{usd_note} vs floor ${salary_floor:,.0f})")
                else:
                    comp_score_fraction = 0.1
                    breakdown.penalties_applied.append(f"Compensation significantly below floor ({display}{usd_note} vs ${salary_floor:,.0f})")
        else:
            breakdown.highlights.append("Compensation unlisted (neutral score applied)")

        raw_comp_score = comp_score_fraction * max_comp_weight
        breakdown.compensation_score = round(raw_comp_score, 2)

        # -------------------------------------------------------------
        # 5. COMPANY PRIORITY & WATCHLIST
        # -------------------------------------------------------------
        max_company_weight = weights.company_priority
        company_score_fraction = 0.5
        watchlisted = next((t for t in self.config.company_watchlist if contains_phrase(job.company, t.name)), None)
        if watchlisted:
            company_score_fraction = min(1.0, 0.7 * watchlisted.priority_multiplier)
            breakdown.highlights.append(f"Priority Watchlist Company: {watchlisted.name} ({watchlisted.priority_multiplier}x boost)")
        elif job.source in ATS_SOURCES:
            company_score_fraction = 0.7
            breakdown.highlights.append(f"Direct employer ATS posting ({job.source.capitalize()})")

        raw_company_score = company_score_fraction * max_company_weight
        breakdown.company_score = round(raw_company_score, 2)

        # -------------------------------------------------------------
        # 6. RECENCY
        # -------------------------------------------------------------
        max_recency_weight = weights.recency_urgency
        recency_score_fraction = 0.6  # when the posting date is unknown
        if job.posted_at:
            posted_at = job.posted_at if job.posted_at.tzinfo else job.posted_at.replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - posted_at).total_seconds() / 3600.0
            if age_hours <= 24:
                recency_score_fraction = 1.0
                breakdown.highlights.append("Published within the last 24h (Early Applicant advantage)")
            elif age_hours <= 48:
                recency_score_fraction = 0.85
                breakdown.highlights.append("Published within 48h")
            elif age_hours <= 168:
                recency_score_fraction = 0.6
            else:
                recency_score_fraction = 0.3
                breakdown.penalties_applied.append("Posting older than 7 days")

        raw_recency_score = recency_score_fraction * max_recency_weight
        breakdown.recency_score = round(raw_recency_score, 2)

        # -------------------------------------------------------------
        # 7. EMPLOYMENT TYPE & JUNIOR SIGNALS
        # -------------------------------------------------------------
        if s.employment_type:
            wanted = s.employment_type.lower().strip()
            job_type = (job.employment_type or "").lower().strip()
            if wanted in ("contract", "freelance", "c2c"):
                contract_terms = ["contract", "contractor", "freelance", "c2c", "fixed-term", "fixed term", "project-based"]
                if job_type == "contract" or any(contains_phrase(full_text, t) for t in contract_terms):
                    breakdown.highlights.append("Contract / Freelance role match")
                elif "full_time" in job_type and not contains_phrase(full_text, "contract"):
                    breakdown.penalties_applied.append("Permanent full-time role (contract preferred)")
            elif wanted in ("internship", "intern"):
                if job_type == "internship" or JUNIOR_TITLE.search(title_lower):
                    breakdown.highlights.append("Internship opportunity match")
            elif wanted in ("part_time", "part-time"):
                if "part_time" in job_type or contains_phrase(full_text, "part-time") or contains_phrase(full_text, "part time"):
                    breakdown.highlights.append("Part-time role match")

        if is_junior_spec:
            junior_terms = ["junior", "entry", "entry level", "associate", "graduate", "early career", "0-2 years", "1-2 years", "no experience required"]
            if any(contains_phrase(full_text, t) for t in junior_terms):
                breakdown.highlights.append("Junior-friendly opportunity")

        # -------------------------------------------------------------
        # 8. TOTAL SCORE & TRIAGE
        # -------------------------------------------------------------
        total_points = raw_title_score + raw_location_score + raw_comp_score + raw_company_score + raw_recency_score
        max_possible_points = (
            max_title_stack_weight + max_location_weight + max_comp_weight + max_company_weight + max_recency_weight
        )
        final_score = round(max(0.0, min(10.0, (total_points / max(max_possible_points, 1.0)) * 10.0)), 1)

        if matched_must:
            breakdown.highlights.insert(0, f"Aligned core skills: {', '.join(matched_must[:4])}")
        if best_role_match and title_match_ratio > 0:
            breakdown.highlights.insert(0, f"Role matches target '{best_role_match}'")

        return ScoredJob(
            job=job,
            score=final_score,
            action=triage(final_score, self.config.schedule.instant_alert_threshold),
            breakdown=breakdown,
            spec_name=spec_name,
            scored_at=datetime.now(timezone.utc),
        )


def triage(score: float, instant_threshold: float) -> str:
    """<5 discard, 5–7 low match (dashboard only), 7–threshold digest, >= threshold instant."""
    if score < 5.0:
        return "discard"
    if score < 7.0:
        return "low_match"
    if score < instant_threshold:
        return "digest"
    return "instant"
