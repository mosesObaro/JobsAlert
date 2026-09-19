// Mirrors the Pydantic models in src/config.py, src/models.py and src/income_opportunities/.

export interface WatchlistCompany {
  name: string;
  priority_multiplier: number;
}

export interface SourceSubConfig {
  enabled: boolean;
  companies: string[];
  categories: string[];
  tags: string[];
  category: string | null;
  limit_stories: number;
}

export interface RSSFeedConfig {
  name: string;
  url: string;
  enabled: boolean;
}

export interface TwitterConfig {
  enabled: boolean;
  search_queries: string[];
  monitored_accounts: string[];
  max_tweets: number;
}

export interface LinkVerificationConfig {
  enabled: boolean;
  timeout_seconds: number;
  max_concurrency: number;
  per_host_concurrency: number;
  check_content_keywords: boolean;
  cache_ttl_hours: number;
}

export interface ScoringWeights {
  title_and_stack: number;
  location_remote: number;
  compensation: number;
  company_priority: number;
  recency_urgency: number;
}

export interface JobSpec {
  name: string;
  keywords: string[];
  target_roles: string[];
  seniority: string | null;
  experience_years: number | null;
  technologies: string[];
  must_have_skills: string[];
  nice_to_have_skills: string[];
  employment_type: string | null;
  remote: boolean | null;
  preferred_locations: string[];
  salary_floor_usd: number | null;
  excluded_terms: string[];
  excluded_companies: string[];
  scoring_weights: ScoringWeights | null;
}

export interface IncomeSourceSubConfig {
  enabled: boolean;
  trust_tier: string;
  platforms: string[];
  categories: string[];
  tags: string[];
  limit_items: number;
}

export interface IncomeRSSFeedConfig {
  name: string;
  url: string;
  category: string;
  trust_tier: string;
  enabled: boolean;
}

export interface OnlineIncomeConfig {
  enabled: boolean;
  include_in_daily_digest: boolean;
  candidate_name: string;
  eligible_countries: string[];
  preferred_categories: string[];
  excluded_categories: string[];
  minimum_quality_score: number;
  minimum_side_job_fit_score: number;
  minimum_final_score: number;
  instant_alert_score: number;
  max_digest_items: number;
  min_source_trust_tier: string;
  require_verified_source: boolean;
  reject_unknown_eligibility: boolean;
  reject_unknown_compensation: boolean;
  catalog_stale_after_days: number;
  minimum_hourly_rate_usd: number;
  preferred_flexibility: string;
  maximum_hours_per_week: number;
  allow_asynchronous_only: boolean;
  preferred_currencies: string[];
  require_link_verification: boolean;
  scoring_weights: {
    quality: number;
    relevance: number;
    side_job_fit: number;
    country_eligibility: number;
    compensation: number;
  };
  sources: {
    ai_evaluation: IncomeSourceSubConfig;
    user_testing: IncomeSourceSubConfig;
    academic_tutoring: IncomeSourceSubConfig;
    transcription_support: IncomeSourceSubConfig;
    rss_feeds: IncomeRSSFeedConfig[];
    custom: IncomeSourceSubConfig;
  };
}

export type CatalogSourceKey = 'ai_evaluation' | 'user_testing' | 'academic_tutoring' | 'transcription_support';

export interface AppConfig {
  profile: {
    candidate_name: string;
    target_roles: string[];
    experience_years: number;
    preferred_locations: string[];
    salary_floor_usd: number;
  };
  filters: {
    must_have_skills: string[];
    nice_to_have_skills: string[];
    excluded_terms: string[];
    excluded_companies: string[];
  };
  job_specs: JobSpec[];
  scoring_weights: ScoringWeights;
  company_watchlist: WatchlistCompany[];
  sources: {
    greenhouse: SourceSubConfig;
    lever: SourceSubConfig;
    ashby: SourceSubConfig;
    remotive: SourceSubConfig;
    remoteok: SourceSubConfig;
    arbeitnow: SourceSubConfig;
    jobicy: SourceSubConfig;
    hackernews: SourceSubConfig;
    twitter: TwitterConfig;
    rss_feeds: RSSFeedConfig[];
  };
  link_verification: LinkVerificationConfig;
  schedule: {
    timezone: string;
    instant_alert_threshold: number;
  };
  delivery: {
    email_provider: string;
    recipient_email: string;
    from_email: string;
    send_instant_alerts: boolean;
    send_daily_digest: boolean;
  };
  state: {
    retention_days: number;
  };
  fx_rates_to_usd: Record<string, number>;
  online_income: OnlineIncomeConfig;
}

export interface JobPosting {
  id: string;
  fingerprint: string;
  title: string;
  company: string;
  location: string;
  is_remote: boolean;
  remote_scope: string;
  url: string;
  raw_url?: string | null;
  description: string;
  salary_min?: number | null;
  salary_max?: number | null;
  salary_currency: string;
  salary_period: string;
  employment_type: string;
  seniority?: string | null;
  posted_at?: string | null;
  source: string;
  tags: string[];
  is_verified?: boolean;
  verification_status?: string | null;
}

export interface MatchBreakdown {
  title_score: number;
  stack_score: number;
  location_score: number;
  compensation_score: number;
  company_score: number;
  recency_score: number;
  matched_must_have: string[];
  matched_nice_to_have: string[];
  missing_must_have: string[];
  penalties_applied: string[];
  highlights: string[];
  eligibility?: string | null;
  is_verified?: boolean;
}

export type TriageAction = 'discard' | 'low_match' | 'digest' | 'instant';

export interface ScoredJob {
  job: JobPosting;
  score: number;
  action: TriageAction;
  breakdown: MatchBreakdown;
  spec_name?: string | null;
  scored_at: string;
}

export type SourceStatus = 'healthy' | 'degraded' | 'error' | 'disabled';

export interface CrawlerHealth {
  source_name: string;
  status: SourceStatus;
  jobs_found?: number;
  opportunities_found?: number;
  latency_ms: number;
  last_crawled?: string | null;
  error_message?: string | null;
}

export interface RunSummary {
  run_id: string;
  timestamp: string;
  mode: 'live' | 'dry_run';
  trigger: string;
  total_fetched: number;
  unique_candidates: number;
  discarded: number;
  low_matches: number;
  digest_matches: number;
  instant_matches: number;
  spec_counts: Record<string, Record<string, number>>;
  emails_dispatched: number;
  delivery_errors: string[];
  pending_alerts: number;
  links_checked: number;
  expired_links_removed: number;
  unverified_links: number;
  execution_time_seconds: number;
  source_health: CrawlerHealth[];
  error_count: number;
  degraded_count: number;
}

export interface OnlineIncomeOpportunity {
  id: string;
  fingerprint: string;
  title: string;
  organization: string;
  description: string;
  category: string;
  opportunity_type: string;
  url: string;
  application_url?: string | null;
  source: string;
  source_trust_tier: string;
  location_eligibility: string;
  is_asynchronous: boolean;
  estimated_pay_min?: number | null;
  estimated_pay_max?: number | null;
  pay_rate_display?: string | null;
  pay_currency: string;
  pay_frequency: string;
  verification_status: string;
  legitimacy_indicators: string[];
  scam_risk_indicators: string[];
  rejection_reasons: string[];
  quality_score: number;
  side_job_fit_score: number;
  link_verification_status?: string | null;
  last_reviewed?: string | null;
  review_overdue?: boolean;
}

export interface IncomeMatchBreakdown {
  quality_score: number;
  side_job_fit_score: number;
  final_score: number;
  passed_quality_gate: boolean;
  eligibility_status: string;
  penalties_applied: string[];
  highlights: string[];
  rejection_reasons: string[];
  is_verified: boolean;
}

export interface ScoredOpportunity {
  opportunity: OnlineIncomeOpportunity;
  score: number;
  action: TriageAction;
  breakdown: IncomeMatchBreakdown;
  scored_at: string;
}

export interface IncomeRunSummary {
  run_id: string;
  timestamp: string;
  mode: 'live' | 'dry_run';
  trigger: string;
  total_fetched: number;
  unique_candidates: number;
  discarded: number;
  low_matches: number;
  digest_matches: number;
  instant_matches: number;
  emails_dispatched: number;
  delivery_errors: string[];
  pending_alerts: number;
  execution_time_seconds: number;
  source_health: CrawlerHealth[];
  error_count: number;
}

export interface CustomJob {
  id: string;
  title: string;
  company: string;
  location: string;
  url: string;
  description: string;
  salary_min?: number | null;
  salary_max?: number | null;
  salary_currency?: string;
  salary_period?: string;
  created_at?: string;
}

export interface CustomIncome {
  id: string;
  title: string;
  organization: string;
  category: string;
  url: string;
  location_eligibility: string;
  description: string;
  pay_rate_display?: string | null;
  created_at?: string;
}
