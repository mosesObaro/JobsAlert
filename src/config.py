"""
JobsAlert Configuration Loader & Schema.
YAML configuration files, environment variable overrides, and profile presets.
"""

from __future__ import annotations
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from src import paths
from src.income_opportunities.config import OnlineIncomeConfig
from src.money import DEFAULT_FX_TO_USD
from src.storage import write_text_atomic

load_dotenv()

# Environment variables that override delivery settings at runtime. They are applied
# when the configuration is loaded and stripped again when it is saved, so values
# from .env or CI secrets never end up in tracked YAML.
ENV_OVERRIDES: Dict[str, tuple] = {
    "CANDIDATE_EMAIL": ("delivery", "recipient_email"),
    "ALERTS_FROM_EMAIL": ("delivery", "from_email"),
    "EMAIL_PROVIDER": ("delivery", "email_provider"),
}

PROFILE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class ProfileConfig(BaseModel):
    candidate_name: str = "Candidate"
    target_roles: List[str] = Field(default_factory=lambda: ["Senior Software Engineer"])
    experience_years: int = 5
    preferred_locations: List[str] = Field(default_factory=lambda: ["Remote", "Worldwide"])
    salary_floor_usd: float = 100000.0


class FiltersConfig(BaseModel):
    must_have_skills: List[str] = Field(default_factory=list)
    nice_to_have_skills: List[str] = Field(default_factory=list)
    excluded_terms: List[str] = Field(default_factory=list)
    excluded_companies: List[str] = Field(default_factory=list)


class ScoringWeightsConfig(BaseModel):
    title_and_stack: float = 40.0
    location_remote: float = 20.0
    compensation: float = 15.0
    company_priority: float = 15.0
    recency_urgency: float = 10.0


def _merge_unique(*lists: List[str]) -> List[str]:
    merged: List[str] = []
    seen = set()
    for items in lists:
        for item in items or []:
            key = item.strip().lower()
            if item and key not in seen:
                seen.add(key)
                merged.append(item)
    return merged


class JobSpecConfig(BaseModel):
    """One job search track. Empty fields inherit the profile and filter defaults."""
    name: str = "Target Roles"
    keywords: List[str] = Field(default_factory=list)
    target_roles: List[str] = Field(default_factory=list)
    seniority: Optional[str] = None  # "junior", "mid", "senior", "lead", "all"
    experience_years: Optional[int] = None
    technologies: List[str] = Field(default_factory=list)
    must_have_skills: List[str] = Field(default_factory=list)
    nice_to_have_skills: List[str] = Field(default_factory=list)
    employment_type: Optional[str] = None  # "contract", "full_time", "part_time", "internship", "any"
    remote: Optional[bool] = None
    preferred_locations: List[str] = Field(default_factory=list)
    salary_floor_usd: Optional[float] = None
    excluded_terms: List[str] = Field(default_factory=list)
    excluded_companies: List[str] = Field(default_factory=list)
    scoring_weights: Optional[ScoringWeightsConfig] = None

    def get_all_roles(self) -> List[str]:
        return _merge_unique(self.target_roles, self.keywords) or ["General Specialist"]

    def get_must_have_skills(self) -> List[str]:
        return _merge_unique(self.must_have_skills, self.technologies)

    def resolved(
        self,
        profile: ProfileConfig,
        filters: FiltersConfig,
        default_weights: ScoringWeightsConfig,
    ) -> "JobSpecConfig":
        """Returns a copy where every empty field falls back to the profile/filter defaults.

        Exclusions are additive: global excluded terms and companies always apply.
        """
        roles = _merge_unique(self.target_roles, self.keywords)
        must = _merge_unique(self.must_have_skills, self.technologies)
        return self.model_copy(update={
            "target_roles": roles or list(profile.target_roles),
            "keywords": [],
            "must_have_skills": must or list(filters.must_have_skills),
            "technologies": [],
            "nice_to_have_skills": list(self.nice_to_have_skills or filters.nice_to_have_skills),
            "preferred_locations": list(self.preferred_locations or profile.preferred_locations),
            "salary_floor_usd": self.salary_floor_usd if self.salary_floor_usd is not None else profile.salary_floor_usd,
            "experience_years": self.experience_years if self.experience_years is not None else profile.experience_years,
            "excluded_terms": _merge_unique(self.excluded_terms, filters.excluded_terms),
            "excluded_companies": _merge_unique(self.excluded_companies, filters.excluded_companies),
            "scoring_weights": self.scoring_weights or default_weights,
        })


class WatchlistCompany(BaseModel):
    name: str
    priority_multiplier: float = 1.2


class SourceSubConfig(BaseModel):
    enabled: bool = True
    companies: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    category: Optional[str] = None
    limit_stories: int = 1  # Hacker News: number of recent monthly "Who is hiring?" threads to read


class RSSFeedConfig(BaseModel):
    name: str
    url: str
    enabled: bool = True


class TwitterConfig(BaseModel):
    enabled: bool = True
    search_queries: List[str] = Field(
        default_factory=lambda: [
            "remote hiring (engineer OR developer OR python OR golang)",
            "#hiring #remotejobs",
        ]
    )
    monitored_accounts: List[str] = Field(
        default_factory=lambda: [
            "TechJobsAfrica",
            "RemoteJobs",
            "JobbermanOnline",
        ]
    )
    max_tweets: int = 30


class LinkVerificationConfig(BaseModel):
    enabled: bool = True
    timeout_seconds: float = 6.0
    max_concurrency: int = 20
    per_host_concurrency: int = 3
    check_content_keywords: bool = True
    cache_ttl_hours: int = 24


class SourcesConfig(BaseModel):
    greenhouse: SourceSubConfig = Field(
        default_factory=lambda: SourceSubConfig(enabled=True, companies=["cloudflare", "datadog", "figma"])
    )
    lever: SourceSubConfig = Field(
        default_factory=lambda: SourceSubConfig(enabled=True, companies=["netflix", "palantir"])
    )
    ashby: SourceSubConfig = Field(
        default_factory=lambda: SourceSubConfig(enabled=True, companies=["linear", "ramp", "retool"])
    )
    remotive: SourceSubConfig = Field(
        default_factory=lambda: SourceSubConfig(enabled=True, categories=["software-dev"])
    )
    remoteok: SourceSubConfig = Field(
        default_factory=lambda: SourceSubConfig(enabled=True, tags=["dev", "golang", "python"])
    )
    arbeitnow: SourceSubConfig = Field(default_factory=lambda: SourceSubConfig(enabled=True))
    jobicy: SourceSubConfig = Field(default_factory=lambda: SourceSubConfig(enabled=True, category="dev"))
    hackernews: SourceSubConfig = Field(default_factory=lambda: SourceSubConfig(enabled=True, limit_stories=1))
    twitter: TwitterConfig = Field(default_factory=TwitterConfig)
    rss_feeds: List[RSSFeedConfig] = Field(default_factory=list)


class ScheduleConfig(BaseModel):
    """Alert timing. When runs happen is set by the cron in .github/workflows/job_alert.yml."""
    timezone: str = "UTC"  # used for dates shown in emails
    instant_alert_threshold: float = 9.2


class DeliveryConfig(BaseModel):
    email_provider: str = "resend"  # "resend", "brevo", "sendgrid", "smtp", "console"
    recipient_email: str = "candidate@example.com"
    from_email: str = "Job Intelligence <alerts@resend.dev>"
    send_instant_alerts: bool = True
    send_daily_digest: bool = True


class StateConfig(BaseModel):
    retention_days: int = 90  # forget postings no source has listed for this many days


class AppConfig(BaseModel):
    profile: ProfileConfig = Field(default_factory=ProfileConfig)
    filters: FiltersConfig = Field(default_factory=FiltersConfig)
    job_specs: List[JobSpecConfig] = Field(default_factory=list)
    scoring_weights: ScoringWeightsConfig = Field(default_factory=ScoringWeightsConfig)
    company_watchlist: List[WatchlistCompany] = Field(default_factory=list)
    sources: SourcesConfig = Field(default_factory=SourcesConfig)
    link_verification: LinkVerificationConfig = Field(default_factory=LinkVerificationConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    delivery: DeliveryConfig = Field(default_factory=DeliveryConfig)
    state: StateConfig = Field(default_factory=StateConfig)
    fx_rates_to_usd: Dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_FX_TO_USD))
    online_income: OnlineIncomeConfig = Field(default_factory=OnlineIncomeConfig)

    def get_effective_job_specs(self) -> List[JobSpecConfig]:
        """Configured job specs with profile/filter defaults filled in, or one spec built from them."""
        specs = self.job_specs or [
            JobSpecConfig(
                name=self.profile.candidate_name if self.profile.candidate_name not in ["Candidate", "Finance Candidate", "HR Professional"] else "Target Career Roles",
            )
        ]
        return [spec.resolved(self.profile, self.filters, self.scoring_weights) for spec in specs]


def validate_profile_name(name: str) -> str:
    """Profile names become file names; allow letters, digits, '_' and '-' only."""
    name = (name or "").strip()
    if not PROFILE_NAME_PATTERN.match(name):
        raise ValueError("Profile names may contain letters, digits, '_' and '-' only (max 64 characters).")
    return name


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(config_path: Optional[str | Path] = None) -> AppConfig:
    """Loads configuration from YAML (defaults when missing) and applies environment overrides."""
    target_path = Path(config_path) if config_path else paths.config_path()
    config = AppConfig(**_read_yaml(target_path))
    for env_name, (section, key) in ENV_OVERRIDES.items():
        value = os.getenv(env_name)
        if value:
            setattr(getattr(config, section), key, value)
    return config


def save_config(config: AppConfig, config_path: Optional[str | Path] = None) -> Path:
    """Saves configuration to YAML atomically, without environment override values."""
    target_path = Path(config_path) if config_path else paths.config_path()
    data = config.model_dump(mode="json")

    persisted = _read_yaml(target_path) if target_path.exists() else _read_yaml(paths.config_path())
    defaults = AppConfig().model_dump(mode="json")
    for env_name, (section, key) in ENV_OVERRIDES.items():
        env_value = os.getenv(env_name)
        if env_value and data.get(section, {}).get(key) == env_value:
            data[section][key] = (persisted.get(section) or {}).get(key, defaults[section][key])

    write_text_atomic(target_path, yaml.safe_dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True))
    return target_path


def list_profiles() -> List[str]:
    """Names of saved profile presets."""
    directory = paths.profiles_dir()
    if not directory.exists():
        return []
    return sorted(p.stem for p in directory.glob("*.yaml") if PROFILE_NAME_PATTERN.match(p.stem))


def profile_path(name: str) -> Path:
    return paths.profiles_dir() / f"{validate_profile_name(name)}.yaml"


def load_profile(name: str) -> AppConfig:
    """Loads a saved profile preset."""
    profile_file = profile_path(name)
    if not profile_file.exists():
        raise FileNotFoundError(f"Profile preset '{name}' not found")
    return load_config(profile_file)


def save_profile(config: AppConfig, name: str) -> Path:
    """Saves a configuration as a named profile preset."""
    target = profile_path(name)
    target.parent.mkdir(parents=True, exist_ok=True)
    return save_config(config, target)
