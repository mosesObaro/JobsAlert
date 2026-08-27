"""
JobsAlert Relevance & Scoring Engine.
Implements a 0–10 weighted scoring engine with transparent match breakdown and 'Why You Match' bullets.
"""

from __future__ import annotations
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from src.config import AppConfig
from src.models import JobPosting, MatchBreakdown, ScoredJob


SENIORITY_RANKS = {
    "intern": 0,
    "junior": 1,
    "entry": 1,
    "associate": 1,
    "mid": 2,
    "intermediate": 2,
    "senior": 3,
    "lead": 4,
    "staff": 5,
    "principal": 6,
    "director": 7,
    "head": 7,
    "vp": 8,
}


def extract_keywords(text: str) -> Set[str]:
    """Tokenizes text into lowercase alphanumeric words."""
    if not text:
        return set()
    return set(re.findall(r"\b[a-z0-9+#.-]+\b", text.lower()))


class ScoringEngine:
    """Evaluates job postings against configured candidate profile, skills, and geo-rules."""

    def __init__(self, config: AppConfig):
        self.config = config

    def score_job(self, job: JobPosting) -> ScoredJob:
        """
        Calculates a 0.0 to 10.0 score with granular weights and generates 'Why You Match' highlights.
        """
        breakdown = MatchBreakdown()
        full_text = f"{job.title} {job.location} {job.description} {' '.join(job.tags)}".lower()
        title_lower = job.title.lower()
        company_lower = job.company.lower()

        # -------------------------------------------------------------
        # 1. HARD EXCLUSIONS (Immediate score 0.0 -> Discard)
        # -------------------------------------------------------------
        # Excluded companies (staffing agencies, recruiters, blacklists)
        for exc_co in self.config.filters.excluded_companies:
            if exc_co and exc_co.lower() in company_lower:
                breakdown.penalties_applied.append(f"Blacklisted company: {exc_co}")
                return ScoredJob(job=job, score=0.0, action="discard", breakdown=breakdown)

        # Excluded terms (negative keywords like PHP, WordPress, No C2C, Security Clearance)
        for exc_term in self.config.filters.excluded_terms:
            if not exc_term:
                continue
            term_lower = exc_term.lower()
            # If in title, immediate hard exclusion
            if re.search(r"\b" + re.escape(term_lower) + r"\b", title_lower):
                breakdown.penalties_applied.append(f"Excluded term in title: {exc_term}")
                return ScoredJob(job=job, score=0.0, action="discard", breakdown=breakdown)
            # If in description
            if re.search(r"\b" + re.escape(term_lower) + r"\b", full_text):
                breakdown.penalties_applied.append(f"Excluded term in description: {exc_term}")
                return ScoredJob(job=job, score=0.0, action="discard", breakdown=breakdown)

        # Seniority mismatch penalty: if user seeks Senior/Staff but posting is Junior/Intern
        candidate_years = self.config.profile.experience_years
        if candidate_years >= 5:
            if any(j in title_lower for j in ["intern", "internship", "junior", "graduate"]):
                breakdown.penalties_applied.append("Junior/Intern role mismatch for experienced candidate")
                return ScoredJob(job=job, score=0.0, action="discard", breakdown=breakdown)

        # -------------------------------------------------------------
        # 2. TITLE & CORE STACK (Weight default: 40%)
        # -------------------------------------------------------------
        max_title_stack_weight = self.config.scoring_weights.title_and_stack

        # Title match (0 to 1.0)
        title_match_ratio = 0.0
        best_role_match = ""
        for role in self.config.profile.target_roles:
            role_clean = role.lower()
            # Exact title or substring match
            if role_clean in title_lower:
                title_match_ratio = 1.0
                best_role_match = role
                break
            else:
                # Word overlap score
                role_words = set(role_clean.split())
                title_words = set(title_lower.split())
                overlap = len(role_words & title_words) / max(len(role_words), 1)
                if overlap > title_match_ratio:
                    title_match_ratio = overlap
                    best_role_match = role

        # Must-have skills matching
        must_have = self.config.filters.must_have_skills
        matched_must = []
        missing_must = []
        for skill in must_have:
            pattern = r"\b" + re.escape(skill.lower()) + r"\b"
            if re.search(pattern, full_text):
                matched_must.append(skill)
            else:
                missing_must.append(skill)

        breakdown.matched_must_have = matched_must
        breakdown.missing_must_have = missing_must

        must_have_ratio = len(matched_must) / max(len(must_have), 1) if must_have else 1.0

        # Nice-to-have skills matching
        nice_to_have = self.config.filters.nice_to_have_skills
        matched_nice = []
        for skill in nice_to_have:
            pattern = r"\b" + re.escape(skill.lower()) + r"\b"
            if re.search(pattern, full_text):
                matched_nice.append(skill)

        breakdown.matched_nice_to_have = matched_nice
        nice_ratio = min(len(matched_nice) / max(len(nice_to_have), 1), 1.0) if nice_to_have else 0.5

        # Combined Title & Stack score
        # Title (40%), Must-Have (45%), Nice-to-Have (15%)
        title_stack_fraction = (title_match_ratio * 0.45) + (must_have_ratio * 0.40) + (nice_ratio * 0.15)
        raw_title_score = title_stack_fraction * max_title_stack_weight
        breakdown.title_score = round(title_match_ratio * (max_title_stack_weight * 0.45), 2)
        breakdown.stack_score = round((must_have_ratio * 0.40 + nice_ratio * 0.15) * max_title_stack_weight, 2)

        # -------------------------------------------------------------
        # 3. REMOTE POLICY & LOCATION (Weight default: 20%)
        # -------------------------------------------------------------
        max_location_weight = self.config.scoring_weights.location_remote
        location_score_fraction = 0.5  # Neutral default
        loc_str = f"{job.location} {job.remote_scope}".lower()

        preferred_locs = [loc.lower() for loc in self.config.profile.preferred_locations]
        user_wants_remote = any("remote" in p or "worldwide" in p for p in preferred_locs)

        is_job_remote = job.is_remote or "remote" in loc_str or "anywhere" in loc_str or "worldwide" in loc_str

        if is_job_remote:
            if any(w in loc_str for w in ["worldwide", "anywhere", "global", "work from anywhere"]):
                location_score_fraction = 1.0
                breakdown.highlights.append("Worldwide remote: zero geo-restrictions")
            elif any(pref in loc_str for pref in preferred_locs if pref not in ["remote", "worldwide"]):
                location_score_fraction = 1.0
                breakdown.highlights.append(f"Remote aligned with preferred region: {job.location}")
            elif user_wants_remote and ("us-only" in loc_str or "us only" in loc_str):
                # If candidate allows US
                if any("united states" in p or "us" in p for p in preferred_locs):
                    location_score_fraction = 0.9
                    breakdown.highlights.append("Remote (US timezone / authorization)")
                else:
                    location_score_fraction = 0.3
                    breakdown.penalties_applied.append("US-restricted remote")
            else:
                location_score_fraction = 0.85
                breakdown.highlights.append(f"Remote position: {job.location}")
        else:
            # Onsite or Hybrid
            matched_pref_onsite = any(pref in loc_str for pref in preferred_locs if pref not in ["remote", "worldwide"])
            if matched_pref_onsite:
                location_score_fraction = 0.95
                breakdown.highlights.append(f"Matches preferred on-site / hybrid location: {job.location}")
            elif "hybrid" in loc_str and user_wants_remote:
                location_score_fraction = 0.4
                breakdown.penalties_applied.append("Hybrid role (requires physical presence)")
            else:
                location_score_fraction = 0.2
                breakdown.penalties_applied.append(f"Non-matching on-site location: {job.location}")

        raw_location_score = location_score_fraction * max_location_weight
        breakdown.location_score = round(raw_location_score, 2)

        # -------------------------------------------------------------
        # 4. COMPENSATION FIT (Weight default: 15%)
        # -------------------------------------------------------------
        max_comp_weight = self.config.scoring_weights.compensation
        salary_floor = self.config.profile.salary_floor_usd
        comp_score_fraction = 0.7  # Neutral default when undisclosed

        if job.salary_max or job.salary_min:
            effective_max = job.salary_max or job.salary_min or 0.0
            effective_min = job.salary_min or effective_max

            # Normalize hourly / monthly rates to yearly
            if job.salary_period == "hourly" and effective_max < 1000:
                effective_max *= 2080
                effective_min *= 2080
            elif job.salary_period == "monthly" and effective_max < 25000:
                effective_max *= 12
                effective_min *= 12

            if effective_max >= salary_floor * 1.3:
                comp_score_fraction = 1.0
                breakdown.highlights.append(f"Top-tier compensation: ${int(effective_min):,} - ${int(effective_max):,}")
            elif effective_max >= salary_floor:
                comp_score_fraction = 0.9
                breakdown.highlights.append(f"Meets salary floor (${int(salary_floor):,}): posted ${int(effective_min):,} - ${int(effective_max):,}")
            elif effective_max >= salary_floor * 0.8:
                comp_score_fraction = 0.5
                breakdown.penalties_applied.append(f"Compensation slightly below floor (${int(effective_max):,} vs floor ${int(salary_floor):,})")
            else:
                # Far below salary floor
                comp_score_fraction = 0.1
                breakdown.penalties_applied.append(f"Compensation significantly below floor (${int(effective_max):,} vs ${int(salary_floor):,})")
        else:
            breakdown.highlights.append("Compensation unlisted (neutral score applied)")

        raw_comp_score = comp_score_fraction * max_comp_weight
        breakdown.compensation_score = round(raw_comp_score, 2)

        # -------------------------------------------------------------
        # 5. COMPANY PRIORITY & WATCHLIST (Weight default: 15%)
        # -------------------------------------------------------------
        max_company_weight = self.config.scoring_weights.company_priority
        company_score_fraction = 0.5  # Standard base company score

        watchlist_match = False
        for target in self.config.company_watchlist:
            if target.name.lower() in company_lower:
                watchlist_match = True
                company_score_fraction = min(1.0, 0.7 * target.priority_multiplier)
                breakdown.highlights.append(f"Priority Watchlist Company: {target.name} ({target.priority_multiplier}x boost)")
                break

        if not watchlist_match:
            # Reputable direct ATS source boost
            if job.source in ["greenhouse", "lever", "ashby"]:
                company_score_fraction = 0.7
                breakdown.highlights.append(f"Direct verified employer ATS posting ({job.source.capitalize()})")

        raw_company_score = company_score_fraction * max_company_weight
        breakdown.company_score = round(raw_company_score, 2)

        # -------------------------------------------------------------
        # 6. RECENCY & URGENCY (Weight default: 10%)
        # -------------------------------------------------------------
        max_recency_weight = self.config.scoring_weights.recency_urgency
        recency_score_fraction = 0.6  # Default if posted date not parsed

        if job.posted_at:
            now = datetime.now(timezone.utc) if job.posted_at.tzinfo else datetime.now(timezone.utc).replace(tzinfo=None)
            age_hours = (now - job.posted_at).total_seconds() / 3600.0


            if age_hours <= 24:
                recency_score_fraction = 1.0
                breakdown.highlights.append("Published within the last 24h (Early Applicant advantage)")
            elif age_hours <= 48:
                recency_score_fraction = 0.85
                breakdown.highlights.append("Published within 48h")
            elif age_hours <= 168:  # 7 days
                recency_score_fraction = 0.6
            else:
                recency_score_fraction = 0.3
                breakdown.penalties_applied.append("Posting older than 7 days")

        raw_recency_score = recency_score_fraction * max_recency_weight
        breakdown.recency_score = round(raw_recency_score, 2)

        # -------------------------------------------------------------
        # 7. TOTAL SCORE COMPILATION & TRIAGE ACTION
        # -------------------------------------------------------------
        total_points = raw_title_score + raw_location_score + raw_comp_score + raw_company_score + raw_recency_score
        max_possible_points = (
            max_title_stack_weight + max_location_weight + max_comp_weight + max_company_weight + max_recency_weight
        )

        scaled_score = (total_points / max(max_possible_points, 1.0)) * 10.0
        final_score = round(max(0.0, min(10.0, scaled_score)), 1)

        # Summarize skill highlights in why you match
        if matched_must:
            breakdown.highlights.insert(0, f"Aligned core skills: {', '.join(matched_must[:4])}")
        if best_role_match:
            breakdown.highlights.insert(0, f"Role matches target '{best_role_match}'")

        # Triage action
        # 0–4 = Discard / Exclude
        # 5–6 = Low Match (Archive for UI search, do not email)
        # 7–8 = Strong Match (Include in Scheduled Digest)
        # 9–10 = High Priority / Direct Target Match (Trigger Immediate Alert if enabled)
        if final_score < 5.0:
            action = "discard"
        elif final_score < 7.0:
            action = "low_match"
        elif final_score < self.config.schedule.instant_alert_threshold:
            action = "digest"
        else:
            action = "instant"

        return ScoredJob(
            job=job,
            score=final_score,
            action=action,
            breakdown=breakdown,
            scored_at=datetime.now(timezone.utc)
        )

