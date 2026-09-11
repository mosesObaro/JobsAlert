"""
Transcription, Virtual Assistant & Remote Support Collector.
Collects opportunities from transcription, VA, and customer support platforms:
Rev, GoTranscript, ModSquad, Belay, Time Etc.
"""

from __future__ import annotations
from typing import List, Dict, Any

from src.income_opportunities.collectors.base import BaseIncomeCollector
from src.income_opportunities.config import OnlineIncomeConfig
from src.income_opportunities.models import OnlineIncomeOpportunity


class TranscriptionSupportCollector(BaseIncomeCollector):
    """Discovers transcription, virtual assistance, and remote support opportunities."""

    def __init__(self):
        super().__init__(name="transcription_support")

    async def collect(self, config: OnlineIncomeConfig) -> List[OnlineIncomeOpportunity]:
        sub_cfg = config.sources.transcription_support
        if not sub_cfg.enabled:
            return []

        opportunities: List[OnlineIncomeOpportunity] = []
        platforms = sub_cfg.platforms or ["rev", "gotranscript", "modsquad", "belay", "time_etc"]

        tracks = self._get_verified_support_tracks()
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
                    experience_requirement=track.get("experience_requirement", "none"),
                    time_commitment="flexible",
                    flexibility="high",
                    source=self.name,
                    tags=track.get("tags", ["Transcription", "Virtual Assistant", "Remote Support"]),
                    verification_status="verified_source",
                    legitimacy_indicators=[
                        f"Established industry provider ({track['organization']})",
                        "Weekly / monthly verified payouts"
                    ],
                )
                opportunities.append(opp)

        limit = sub_cfg.limit_items or 30
        return opportunities[:limit]

    def _get_verified_support_tracks(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "rev-transcriptionist-01",
                "platform_id": "rev",
                "title": "Freelance Audio Transcriptionist & Captioner",
                "organization": "Rev.com",
                "description": "Listen to audio files and transcribe speech accurately with flexible weekly payouts via PayPal. Work as little or as much as you want.",
                "category": "transcription",
                "opportunity_type": "per_task",
                "pay_frequency": "weekly",
                "url": "https://www.rev.com",
                "application_url": "https://www.rev.com/freelancers/transcription",
                "location_eligibility": "Worldwide (Select Countries Accepted)",
                "eligible_countries": ["Worldwide", "Nigeria", "South Africa", "United States", "United Kingdom", "Canada"],
                "estimated_pay_min": 12.0,
                "estimated_pay_max": 22.0,
                "pay_rate_display": "$0.30–$1.10 per audio/video minute ($12–$22/hr)",
                "tags": ["Audio Transcription", "Weekly PayPal", "Flexible Hours"]
            },
            {
                "id": "gotranscript-transcriber-01",
                "platform_id": "gotranscript",
                "title": "Audio/Video Transcriber & Text Editor",
                "organization": "GoTranscript",
                "description": "Transcribe audio recordings from across medical, legal, and general disciplines. 100% remote with international contributor onboarding.",
                "category": "transcription",
                "opportunity_type": "per_task",
                "pay_frequency": "weekly",
                "url": "https://gotranscript.com",
                "application_url": "https://gotranscript.com/transcription-jobs",
                "location_eligibility": "Worldwide",
                "eligible_countries": ["Worldwide", "Nigeria", "Kenya", "Ghana", "India", "United Kingdom"],
                "estimated_pay_min": 8.0,
                "estimated_pay_max": 18.0,
                "pay_rate_display": "Up to $0.60 per audio minute ($10–$18/hr avg)",
                "tags": ["Transcription", "PayPal", "Payoneer", "Global"]
            },
            {
                "id": "modsquad-mod-01",
                "platform_id": "modsquad",
                "title": "Remote Community Moderator & Customer Support Specialist (Mod)",
                "organization": "ModSquad",
                "description": "Provide forum moderation, social media support, and ticketing customer service for top global gaming, entertainment, and e-commerce brands.",
                "category": "remote_support",
                "opportunity_type": "hourly",
                "pay_frequency": "monthly",
                "url": "https://modsquad.com",
                "application_url": "https://modsquad.com/join-the-mods/",
                "location_eligibility": "Worldwide (Mod Network)",
                "eligible_countries": ["Worldwide", "Nigeria", "United States", "United Kingdom", "Germany", "Brazil"],
                "estimated_pay_min": 12.0,
                "estimated_pay_max": 20.0,
                "pay_rate_display": "$12–$20/hr",
                "tags": ["Customer Support", "Community Moderation", "Flexible Shift Booking"]
            },
            {
                "id": "timeetc-va-01",
                "platform_id": "time_etc",
                "title": "Virtual Assistant (Executive Admin, Bookkeeping & Organization)",
                "organization": "Time Etc",
                "description": "Support entrepreneurs and busy executives with calendar scheduling, bookkeeping data entry, inbox triage, and travel planning.",
                "category": "virtual_assistant",
                "opportunity_type": "hourly",
                "pay_frequency": "monthly",
                "url": "https://web.timeetc.com",
                "application_url": "https://web.timeetc.com/be-a-virtual-assistant",
                "location_eligibility": "Worldwide / Remote",
                "eligible_countries": ["Worldwide", "Nigeria", "United Kingdom", "United States"],
                "estimated_pay_min": 14.0,
                "estimated_pay_max": 24.0,
                "pay_rate_display": "$14–$24/hr",
                "tags": ["Virtual Assistant", "Bookkeeping Support", "Flexible Part-Time"]
            }
        ]
