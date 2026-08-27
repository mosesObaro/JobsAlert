export interface WatchlistCompany {
  name: string;
  priority_multiplier: number;
}

export interface SourceSubConfig {
  enabled: boolean;
  companies?: string[];
  categories?: string[];
  tags?: string[];
  category?: string;
  limit_stories?: number;
}

export interface RSSFeedConfig {
  name: string;
  url: string;
  enabled: boolean;
}

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
  scoring_weights: {
    title_and_stack: number;
    location_remote: number;
    compensation: number;
    company_priority: number;
    recency_urgency: number;
  };
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
    rss_feeds: RSSFeedConfig[];
  };
  schedule: {
    timezone: string;
    daily_digest_time: string;
    weekly_digest_day: string;
    instant_alert_threshold: number;
  };
  delivery: {
    email_provider: string;
    recipient_email: string;
    from_email: string;
    send_instant_alerts: boolean;
    send_daily_digest: boolean;
  };
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
  raw_url?: string;
  description: string;
  salary_min?: number;
  salary_max?: number;
  salary_currency: string;
  salary_period: string;
  employment_type: string;
  seniority?: string;
  posted_at?: string;
  source: string;
  tags: string[];
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
}

export interface ScoredJob {
  job: JobPosting;
  score: number;
  action: 'discard' | 'low_match' | 'digest' | 'instant';
  breakdown: MatchBreakdown;
  scored_at: string;
}

export interface CrawlerHealth {
  source_name: string;
  status: 'healthy' | 'degraded' | 'error';
  jobs_found: number;
  latency_ms: number;
  last_crawled?: string;
  error_message?: string;
}

export interface RunSummary {
  run_id: string;
  timestamp: string;
  total_fetched: number;
  unique_candidates: number;
  discarded: number;
  low_matches: number;
  digest_matches: number;
  instant_matches: number;
  emails_dispatched: number;
  execution_time_seconds: number;
  source_health: CrawlerHealth[];
  error_count: number;
}
