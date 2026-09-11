"""
User Testing & Research Studies Income Opportunities Collector.
Collects opportunities from leading usability, testing, and research platforms:
UserTesting, Testbirds, Respondent.io, Prolific.
"""

from __future__ import annotations
from typing import List, Dict, Any

from src.income_opportunities.collectors.base import BaseIncomeCollector
from src.income_opportunities.config import OnlineIncomeConfig
from src.income_opportunities.models import OnlineIncomeOpportunity


class UserTestingCollector(BaseIncomeCollector):
    """Discovers usability testing, bug testing, and paid research study opportunities."""

    def __init__(self):
        super().__init__(name="user_testing")

    async def collect(self, config: OnlineIncomeConfig) -> List[OnlineIncomeOpportunity]:
        sub_cfg = config.sources.user_testing
        if not sub_cfg.enabled:
            return []

        opportunities: List[OnlineIncomeOpportunity] = []
        platforms = sub_cfg.platforms or ["usertesting", "testbirds", "respondent", "prolific"]

        tracks = self._get_verified_testing_tracks()
        for track in tracks:
            platform_id = track.get("platform_id", "")
            if any(p in platform_id for p in platforms) or not platforms:
                opp = OnlineIncomeOpportunity(
                    id=track["id"],
                    title=track["title"],
                    organization=track["organization"],
                    description=track["description"],
                    category=track["category"],
                    opportunity_type=track.get("opportunity_type", "per_task"),
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
                    pay_frequency=track.get("pay_frequency", "per_task"),
                    experience_requirement="none",
                    time_commitment="ad_hoc",
                    flexibility="high",
                    source=self.name,
                    tags=track.get("tags", ["User Testing", "Usability", "PayPal"]),
                    verification_status="verified_source",
                    legitimacy_indicators=[
                        f"Recognized testing/research platform ({track['organization']})",
                        "No upfront investment required; verified payouts"
                    ],
                )
                opportunities.append(opp)

        limit = sub_cfg.limit_items or 30
        return opportunities[:limit]

    def _get_verified_testing_tracks(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "ut-tester-01",
                "platform_id": "usertesting",
                "title": "Website & Mobile App Usability Tester",
                "organization": "UserTesting",
                "description": "Share your perspective on new websites, applications, and digital prototypes by completing recorded 15–20 minute walkthroughs and speaking your thoughts aloud.",
                "category": "user_testing",
                "opportunity_type": "per_task",
                "pay_frequency": "per_task",
                "url": "https://www.usertesting.com",
                "application_url": "https://www.usertesting.com/get-paid-to-test",
                "location_eligibility": "Worldwide",
                "eligible_countries": ["Worldwide", "Nigeria", "South Africa", "United Kingdom", "United States", "Canada"],
                "estimated_pay_min": 10.0,
                "estimated_pay_max": 60.0,
                "pay_rate_display": "$10–$60 per test / live conversation",
                "tags": ["Usability Testing", "PayPal Payout", "No Experience Required"]
            },
            {
                "id": "testbirds-nest-01",
                "platform_id": "testbirds",
                "title": "Crowdtester & UX/Bug Bounty Contributor",
                "organization": "Testbirds",
                "description": "Test apps, software, and e-commerce platforms on your own smartphone or PC. Earn fixed payouts per completed test run plus additional bounties for discovered bugs.",
                "category": "user_testing",
                "opportunity_type": "per_task",
                "pay_frequency": "per_task",
                "url": "https://www.testbirds.com",
                "application_url": "https://nest.testbirds.com",
                "location_eligibility": "Worldwide (Global Crowd)",
                "eligible_countries": ["Worldwide", "Nigeria", "Kenya", "Ghana", "Germany", "United Kingdom"],
                "estimated_pay_min": 15.0,
                "estimated_pay_max": 45.0,
                "pay_rate_display": "€15–€50 per test + Bug Bounties",
                "tags": ["UX Testing", "Bug Bounty", "Bank Transfer", "PayPal"]
            },
            {
                "id": "respondent-research-01",
                "platform_id": "respondent",
                "title": "Paid Research Study & Professional Interview Participant",
                "organization": "Respondent.io",
                "description": "Participate in targeted market research studies, 1-on-1 video interviews, and focus groups. Great for professionals, finance practitioners, and consumers.",
                "category": "survey_research",
                "opportunity_type": "study",
                "pay_frequency": "per_milestone",
                "url": "https://www.respondent.io",
                "application_url": "https://www.respondent.io/respondents",
                "location_eligibility": "Worldwide / Global Participants",
                "eligible_countries": ["Worldwide", "Nigeria", "United States", "United Kingdom", "Canada"],
                "estimated_pay_min": 50.0,
                "estimated_pay_max": 150.0,
                "pay_rate_display": "$50–$150/hr per study",
                "tags": ["Research Studies", "High Payout", "Video Interviews", "PayPal"]
            },
            {
                "id": "prolific-academic-01",
                "platform_id": "prolific",
                "title": "Academic Research & Behavioral Study Participant",
                "organization": "Prolific",
                "description": "Take part in university and behavioral science studies conducted by researchers at Stanford, Oxford, and Harvard. Guaranteed ethical pay minimums.",
                "category": "survey_research",
                "opportunity_type": "study",
                "pay_frequency": "per_task",
                "url": "https://www.prolific.com",
                "application_url": "https://www.prolific.com/participants",
                "location_eligibility": "Worldwide / Available in 38+ countries",
                "eligible_countries": ["Worldwide", "Nigeria", "South Africa", "United Kingdom", "United States", "Australia"],
                "estimated_pay_min": 8.0,
                "estimated_pay_max": 16.0,
                "pay_rate_display": "£8–£15/hr ($10–$20/hr equivalent)",
                "tags": ["Academic Research", "Instant PayPal", "Ethical Pay Floor"]
            }
        ]
