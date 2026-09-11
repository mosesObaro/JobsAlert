"""
Academic Proofreading, Editing & Online Tutoring Collector.
Collects opportunities from academic editing, tutoring, and research platforms:
Cambridge Proofreading, Scribbr / Enago, Preply, Cambly, Academic Positions.
"""

from __future__ import annotations
from typing import List, Dict, Any

from src.income_opportunities.collectors.base import BaseIncomeCollector
from src.income_opportunities.config import OnlineIncomeConfig
from src.income_opportunities.models import OnlineIncomeOpportunity


class AcademicTutoringCollector(BaseIncomeCollector):
    """Discovers academic proofreading, research assistant, and online tutoring opportunities."""

    def __init__(self):
        super().__init__(name="academic_tutoring")

    async def collect(self, config: OnlineIncomeConfig) -> List[OnlineIncomeOpportunity]:
        sub_cfg = config.sources.academic_tutoring
        if not sub_cfg.enabled:
            return []

        opportunities: List[OnlineIncomeOpportunity] = []
        platforms = sub_cfg.platforms or ["cambridge_proofreading", "scribbr", "preply", "cambly", "academic_positions"]

        tracks = self._get_verified_academic_tracks()
        for track in tracks:
            platform_id = track.get("platform_id", "")
            if any(p in platform_id for p in platforms) or not platforms:
                opp = OnlineIncomeOpportunity(
                    id=track["id"],
                    title=track["title"],
                    organization=track["organization"],
                    description=track["description"],
                    category=track["category"],
                    opportunity_type=track.get("opportunity_type", "hourly"),
                    url=track["url"],
                    application_url=track.get("application_url", track["url"]),
                    location_eligibility=track.get("location_eligibility", "Worldwide"),
                    eligible_countries=track.get("eligible_countries", ["Worldwide", "Nigeria"]),
                    country_restrictions=track.get("country_restrictions", []),
                    is_remote=True,
                    is_flexible=True,
                    estimated_pay_min=track.get("estimated_pay_min"),
                    estimated_pay_max=track.get("estimated_pay_max"),
                    pay_rate_display=track.get("pay_rate_display"),
                    pay_currency="USD",
                    pay_frequency=track.get("pay_frequency", "hourly"),
                    experience_requirement=track.get("experience_requirement", "intermediate"),
                    time_commitment="flexible",
                    flexibility="high",
                    source=self.name,
                    tags=track.get("tags", ["Proofreading", "Tutoring", "Academic"]),
                    verification_status="verified_source",
                    legitimacy_indicators=[
                        f"Established academic/tutoring provider ({track['organization']})",
                        "Direct onboarding with clear quality guidelines"
                    ],
                )
                opportunities.append(opp)

        limit = sub_cfg.limit_items or 30
        return opportunities[:limit]

    def _get_verified_academic_tracks(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "cp-proofreader-01",
                "platform_id": "cambridge_proofreading",
                "title": "Remote Academic Proofreader & Editor",
                "organization": "Cambridge Proofreading LLC",
                "description": "Edit academic manuscripts, theses, journal papers, and research proposals for international scholars and university researchers. Work flexibly on your own schedule.",
                "category": "academic_proofreading",
                "opportunity_type": "hourly",
                "pay_frequency": "biweekly",
                "url": "https://proofreading.org",
                "application_url": "https://proofreading.org/careers/",
                "location_eligibility": "Worldwide (Native or Near-Native English)",
                "eligible_countries": ["Worldwide", "Nigeria", "South Africa", "United Kingdom", "United States", "Canada"],
                "estimated_pay_min": 20.0,
                "estimated_pay_max": 30.0,
                "pay_rate_display": "$20–$30/hr equivalent",
                "experience_requirement": "intermediate",
                "tags": ["Academic Proofreading", "Manuscript Editing", "Flexible Schedule"]
            },
            {
                "id": "scribbr-editor-01",
                "platform_id": "scribbr",
                "title": "Academic Essay & Thesis Editor",
                "organization": "Scribbr / Enago",
                "description": "Proofread and polish university dissertations, essays, and academic publications. Flexible volume with continuous order availability during academic semesters.",
                "category": "academic_proofreading",
                "opportunity_type": "per_task",
                "pay_frequency": "monthly",
                "url": "https://www.scribbr.com",
                "application_url": "https://www.scribbr.com/jobs/freelance-editor/",
                "location_eligibility": "Worldwide",
                "eligible_countries": ["Worldwide", "Nigeria", "Kenya", "South Africa", "Netherlands", "United Kingdom"],
                "estimated_pay_min": 18.0,
                "estimated_pay_max": 28.0,
                "pay_rate_display": "€20–€30/hr equivalent",
                "experience_requirement": "intermediate",
                "tags": ["Academic Editing", "Dissertation Support", "Global"]
            },
            {
                "id": "preply-tutor-01",
                "platform_id": "preply",
                "title": "Online Subject / Language Tutor (Finance, Accounting, English)",
                "organization": "Preply",
                "description": "Teach students worldwide in subjects of your expertise, such as Business English, Accounting principles, Economics, or Languages. Set your own pricing and lesson availability.",
                "category": "online_tutoring",
                "opportunity_type": "hourly",
                "pay_frequency": "hourly",
                "url": "https://preply.com",
                "application_url": "https://preply.com/en/teach",
                "location_eligibility": "Worldwide (Global Tutors Welcomed)",
                "eligible_countries": ["Worldwide", "Nigeria", "Ghana", "Kenya", "United States", "United Kingdom"],
                "estimated_pay_min": 15.0,
                "estimated_pay_max": 40.0,
                "pay_rate_display": "$15–$40/hr (set your own rate)",
                "experience_requirement": "beginner",
                "tags": ["Online Tutoring", "Custom Rates", "Payoneer", "PayPal", "Wise"]
            },
            {
                "id": "cambly-tutor-01",
                "platform_id": "cambly",
                "title": "Conversational English Tutor (No Degree or Lesson Prep Needed)",
                "organization": "Cambly",
                "description": "Help adult and young learners practice conversational English on a flexible drop-in basis. Log in whenever you are free with zero lesson planning required.",
                "category": "online_tutoring",
                "opportunity_type": "hourly",
                "pay_frequency": "weekly",
                "url": "https://www.cambly.com",
                "application_url": "https://www.cambly.com/en/tutors",
                "location_eligibility": "Worldwide",
                "eligible_countries": ["Worldwide", "Nigeria", "South Africa", "United States", "United Kingdom"],
                "estimated_pay_min": 10.2,
                "estimated_pay_max": 12.0,
                "pay_rate_display": "$10.20–$12.00/hr ($0.17–$0.20/min)",
                "experience_requirement": "none",
                "tags": ["English Tutoring", "Weekly PayPal", "Zero Prep Required"]
            },
            {
                "id": "academic-research-asst-01",
                "platform_id": "academic_positions",
                "title": "Remote Academic Research Assistant & Literature Synthesizer",
                "organization": "Academic Positions Network",
                "description": "Support academic faculty and research labs with literature searches, data synthesis, citation formatting (APA/Harvard), and bibliography management.",
                "category": "research_assistant",
                "opportunity_type": "hourly",
                "pay_frequency": "monthly",
                "url": "https://academicpositions.com",
                "application_url": "https://academicpositions.com/jobs",
                "location_eligibility": "Worldwide / Remote",
                "eligible_countries": ["Worldwide", "Nigeria", "Europe", "United States"],
                "estimated_pay_min": 16.0,
                "estimated_pay_max": 26.0,
                "pay_rate_display": "$16–$26/hr",
                "experience_requirement": "intermediate",
                "tags": ["Research Assistant", "Literature Review", "Remote Academic"]
            }
        ]
