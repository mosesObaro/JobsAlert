"""
JobsAlert Configuration Loader & Schema.
Supports YAML config files, environment variable overrides, and preset profile management.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, List, Optional
import yaml
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "jobs.yaml"
PROFILES_DIR = Path(__file__).resolve().parent.parent / "config" / "profiles"


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


class WatchlistCompany(BaseModel):
    name: str
    priority_multiplier: float = 1.2


class SourceSubConfig(BaseModel):
    enabled: bool = True
    companies: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    category: Optional[str] = None
    limit_stories: int = 1


class RSSFeedConfig(BaseModel):
    name: str
    url: str
    enabled: bool = True


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
    rss_feeds: List[RSSFeedConfig] = Field(default_factory=list)


class ScheduleConfig(BaseModel):
    timezone: str = "UTC"
    daily_digest_time: str = "08:30"
    weekly_digest_day: str = "Monday"
    instant_alert_threshold: float = 9.2


class DeliveryConfig(BaseModel):
    email_provider: str = "resend"  # "resend", "brevo", "sendgrid", "smtp", "console"
    recipient_email: str = "candidate@example.com"
    from_email: str = "Job Intelligence <alerts@resend.dev>"
    send_instant_alerts: bool = True
    send_daily_digest: bool = True


class AppConfig(BaseModel):
    profile: ProfileConfig = Field(default_factory=ProfileConfig)
    filters: FiltersConfig = Field(default_factory=FiltersConfig)
    scoring_weights: ScoringWeightsConfig = Field(default_factory=ScoringWeightsConfig)
    company_watchlist: List[WatchlistCompany] = Field(default_factory=list)
    sources: SourcesConfig = Field(default_factory=SourcesConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    delivery: DeliveryConfig = Field(default_factory=DeliveryConfig)


def load_config(config_path: Optional[str | Path] = None) -> AppConfig:
    """Load configuration from file, falling back to defaults and applying env overrides."""
    target_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH

    data = {}
    if target_path.exists():
        with open(target_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    config = AppConfig(**data)

    # Environment variable overrides
    if os.getenv("CANDIDATE_EMAIL"):
        config.delivery.recipient_email = os.getenv("CANDIDATE_EMAIL")
    if os.getenv("ALERTS_FROM_EMAIL"):
        config.delivery.from_email = os.getenv("ALERTS_FROM_EMAIL")
    if os.getenv("EMAIL_PROVIDER"):
        config.delivery.email_provider = os.getenv("EMAIL_PROVIDER")

    return config


def save_config(config: AppConfig, config_path: Optional[str | Path] = None) -> Path:
    """Save application configuration back to YAML."""
    target_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)

    config_dict = config.model_dump()
    with open(target_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config_dict, f, sort_keys=False, default_flow_style=False)

    return target_path


def list_profiles() -> List[str]:
    """List available saved profile preset names."""
    if not PROFILES_DIR.exists():
        return []
    return [p.stem for p in PROFILES_DIR.glob("*.yaml")]


def load_profile(name: str) -> AppConfig:
    """Load a specific saved profile preset."""
    profile_file = PROFILES_DIR / f"{name}.yaml"
    if not profile_file.exists():
        raise FileNotFoundError(f"Profile preset '{name}' not found at {profile_file}")
    return load_config(profile_file)
