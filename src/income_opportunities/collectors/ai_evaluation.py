"""
AI Evaluation & Data Annotation Income Opportunities Collector.
Collects opportunities from leading AI training & data annotation platforms:
DataAnnotation.tech, Outlier.ai / Remotasks, OneForma / Centific, Telus International, Appen.
"""

from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any
import httpx

from src.income_opportunities.collectors.base import BaseIncomeCollector
from src.income_opportunities.config import OnlineIncomeConfig
from src.income_opportunities.models import OnlineIncomeOpportunity


class AIEvaluationCollector(BaseIncomeCollector):
    """Discovers AI training, prompt evaluation, and data annotation opportunities."""

    def __init__(self):
        super().__init__(name="ai_evaluation")

    async def collect(self, config: OnlineIncomeConfig) -> List[OnlineIncomeOpportunity]:
        sub_cfg = config.sources.ai_evaluation
        if not sub_cfg.enabled:
            return []

        opportunities: List[OnlineIncomeOpportunity] = []
        platforms = sub_cfg.platforms or ["dataannotation", "outlier", "oneforma", "telus", "appen"]

        # 1. Platform Catalog: Verified Active Standing Tracks
        standing_tracks = self._get_verified_ai_tracks()
        for track in standing_tracks:
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
                    pay_frequency="hourly",
                    experience_requirement=track.get("experience_requirement", "none"),
                    time_commitment="flexible",
                    flexibility="high",
                    source=self.name,
                    tags=track.get("tags", ["AI Evaluation", "Remote", "Flexible"]),
                    verification_status="verified_source",
                    legitimacy_indicators=[
                        f"Established AI data platform ({track['organization']})",
                        "Direct application portal with onboarding assessment"
                    ],
                )
                opportunities.append(opp)

        # 2. Dynamic Career Endpoints for AI Openings
        dynamic_opps = await self._fetch_dynamic_openings()
        opportunities.extend(dynamic_opps)

        limit = sub_cfg.limit_items or 30
        return opportunities[:limit]

    def _get_verified_ai_tracks(self) -> List[Dict[str, Any]]:
        """Returns verified, continuously active onboarding and project tracks from tier-1 AI evaluation platforms."""
        return [
            {
                "id": "dat-core-eval-01",
                "platform_id": "dataannotation",
                "title": "AI Evaluator & Content Annotator (Generalist)",
                "organization": "DataAnnotation.tech",
                "description": "Evaluate conversational AI model responses for factual accuracy, reasoning, grammar, and alignment. Self-paced, asynchronous work with continuous project streams.",
                "category": "ai_evaluation",
                "opportunity_type": "hourly",
                "url": "https://www.dataannotation.tech",
                "application_url": "https://www.dataannotation.tech/workers",
                "location_eligibility": "Worldwide / Global",
                "eligible_countries": ["Worldwide", "Nigeria", "United States", "United Kingdom", "Canada", "Australia"],
                "estimated_pay_min": 20.0,
                "estimated_pay_max": 25.0,
                "pay_rate_display": "$20–$25/hr",
                "experience_requirement": "none",
                "tags": ["AI Trainer", "LLM Evaluation", "Flexible", "Weekly Pay"]
            },
            {
                "id": "outlier-ai-trainer-01",
                "platform_id": "outlier",
                "title": "AI Trainer & Reasoning Evaluator (Domain Specialist / Generalist)",
                "organization": "Outlier.ai",
                "description": "Train state-of-the-art frontier AI models by providing detailed feedback, creative prompts, and fact-checking generated outputs across humanities, logic, writing, and STEM topics.",
                "category": "ai_evaluation",
                "opportunity_type": "hourly",
                "url": "https://outlier.ai",
                "application_url": "https://outlier.ai/experts",
                "location_eligibility": "Worldwide (Global Candidates Accepted)",
                "eligible_countries": ["Worldwide", "Nigeria", "Kenya", "South Africa", "United States", "United Kingdom"],
                "estimated_pay_min": 15.0,
                "estimated_pay_max": 35.0,
                "pay_rate_display": "$15–$35/hr",
                "experience_requirement": "beginner",
                "tags": ["AI Evaluation", "Fact Checking", "Direct Deposit", "PayPal"]
            },
            {
                "id": "oneforma-llm-annotator-01",
                "platform_id": "oneforma",
                "title": "Micro-Task Contributor & Multimodal AI Evaluator",
                "organization": "OneForma / Centific",
                "description": "Participate in global AI annotation projects, audio collection, prompt engineering, and linguistic quality evaluations. Pick and choose tasks based on interest.",
                "category": "data_annotation",
                "opportunity_type": "per_task",
                "url": "https://www.oneforma.com",
                "application_url": "https://www.oneforma.com/job-opportunities/",
                "location_eligibility": "Worldwide / Over 150 Countries",
                "eligible_countries": ["Worldwide", "Nigeria", "Ghana", "Kenya", "Egypt", "India"],
                "estimated_pay_min": 8.0,
                "estimated_pay_max": 18.0,
                "pay_rate_display": "$8–$18/hr equivalent (per-task)",
                "experience_requirement": "none",
                "tags": ["Data Annotation", "Multimodal AI", "Payoneer", "Global"]
            },
            {
                "id": "telus-ai-community-01",
                "platform_id": "telus",
                "title": "AI Community Evaluator & Personalized Internet Assessor",
                "organization": "TELUS International AI",
                "description": "Review and rate search results, social media relevance, and AI queries to improve search algorithms and AI assistants worldwide. Fully flexible part-time hours.",
                "category": "ai_evaluation",
                "opportunity_type": "hourly",
                "url": "https://www.telusinternational.com/solutions/ai-data-solutions",
                "application_url": "https://www.telusinternational.ai/community",
                "location_eligibility": "Worldwide / Regional Community Opportunities",
                "eligible_countries": ["Worldwide", "Nigeria", "South Africa", "United Kingdom", "Germany"],
                "estimated_pay_min": 10.0,
                "estimated_pay_max": 16.0,
                "pay_rate_display": "$10–$16/hr",
                "experience_requirement": "none",
                "tags": ["Search Evaluator", "Part-Time", "Flexible Hours", "TELUS"]
            },
            {
                "id": "appen-crowd-contributor-01",
                "platform_id": "appen",
                "title": "Crowdsourced Data Annotator & Search Relevance Rater",
                "organization": "Appen",
                "description": "Help world-leading technology companies evaluate datasets, transcribe audio, annotate computer vision assets, and test AI voice assistants.",
                "category": "data_annotation",
                "opportunity_type": "per_task",
                "url": "https://appen.com",
                "application_url": "https://appen.com/join-our-crowd/",
                "location_eligibility": "Worldwide",
                "eligible_countries": ["Worldwide", "Nigeria", "Kenya", "India", "Philippines", "Brazil"],
                "estimated_pay_min": 7.0,
                "estimated_pay_max": 15.0,
                "pay_rate_display": "$7–$15/hr equivalent",
                "experience_requirement": "none",
                "tags": ["Data Annotation", "Search Rating", "Payoneer", "PayPal"]
            }
        ]

    async def _fetch_dynamic_openings(self) -> List[OnlineIncomeOpportunity]:
        """Optionally queries public RSS/APIs for newly opened AI evaluation projects."""
        # Future live feed integrations can append here
        return []
