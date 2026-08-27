# JobsAlert — Autonomous Career Intelligence & Email Alert System

> **Autonomous Career Intelligence & Opportunity Scout**  
> Continuously monitors target job boards, employer career APIs, ATS platforms, and public vacancy feeds, paired with a web control panel for visual configuration and high-signal, deduplicated email alerts scored against exact candidate criteria.

---

## Architecture Overview

```
                      ┌────────────────────────────────────────────────────────┐
                      │                   DATA SOURCES                         │
                      │  • Direct ATS: Greenhouse, Lever, Ashby                │
                      │  • Aggregators: Remotive, RemoteOK, Arbeitnow, Jobicy  │
                      │  • Startup Feeds: Hacker News "Who is Hiring?"         │
                      │  • Custom RSS/Atom Feeds                               │
                      └───────────────────────────┬────────────────────────────┘
                                                  │ Concurrent Fetch
                                                  ▼
                      ┌────────────────────────────────────────────────────────┐
                      │           URL CANONICALIZER & DEDUPLICATOR             │
                      │  • Strips utm_*, ref, gh_src, lever-origin tracking    │
                      │  • SHA-256 Fingerprint: Company + Title + Loc + Ref    │
                      │  • Queries State Layer (seen_jobs.json / Supabase)     │
                      └───────────────────────────┬────────────────────────────┘
                                                  │ Unique Postings
                                                  ▼
                      ┌────────────────────────────────────────────────────────┐
                      │            RELEVANCE SCORING ENGINE (0–10)             │
                      │  • Title & Core Stack (40%)                            │
                      │  • Remote Policy & Location (20%)                      │
                      │  • Compensation Fit (15%)                              │
                      │  • Company Priority Watchlist (15%)                    │
                      │  • Recency & Urgency (10%)                             │
                      │  • Generates "Why You Match" bullet points             │
                      └───────────────────────────┬────────────────────────────┘
                                                  │
                 ┌────────────────────────────────┴────────────────────────────────┐
                 │                                                                 │
                 ▼                                                                 ▼
      [0.0 - 4.9] Discard                                              [5.0 - 6.9] Low Match
      Dropped immediately                                              Archived for UI search
                 │                                                                 │
                 ▼                                                                 ▼
      [7.0 - 8.9] Strong Match                                         [9.0 - 10.0] Instant Alert
      Queued for Daily Digest                                          Triggers Immediate Dispatch
                 │                                                                 │
                 └────────────────────────────────┬────────────────────────────────┘
                                                  │
                                                  ▼
                      ┌────────────────────────────────────────────────────────┐
                      │                 DISPATCH & NOTIFIER                    │
                      │  • Resend API (3,000 free emails/mo)                   │
                      │  • Brevo / Sendinblue (300 free emails/day)            │
                      │  • Standard SMTP (Gmail App Password, AWS SES)         │
                      │  • Local Preview (latest_email_preview.html)           │
                      └────────────────────────────────────────────────────────┘
```

---

## Features

- **Granular 0–10 Scoring Model:** Evaluates roles beyond keyword counting. Penalizes mismatched seniority (e.g. Junior roles for experienced staff), verifies remote policies (distinguishing Worldwide from US-only), scores compensation bands against floors, and boosts target watchlist employers.
- **Why You Match Breakdown:** Every alerted opportunity includes 3–4 transparent bullet points highlighting skill alignment, compensation fit, and location match.
- **Cross-Platform Deduplication:** Prevents duplicate emails when a position is cross-posted across multiple boards using URL canonicalization and deterministic SHA-256 fingerprinting.
- **Web Control Panel:** Modern responsive dashboard featuring Role & Skill matrices, compensation sliders, dream company manager, ATS source switches, delivery settings, and a real-time dry-run previewer with an embedded HTML email reader.
- **100% Free-Tier Infrastructure:** Built to run cost-free using GitHub Actions (scheduled execution), GitHub Pages or Cloudflare Pages (control panel hosting), Git-committed state or Supabase (persistence), and Resend or Brevo (email dispatch).

---

## Directory Structure

```
JobsAlert/
├── config/
│   ├── jobs.yaml                    # Active configuration schema
│   └── profiles/                    # Preset search personas
│       ├── remote_high_comp.yaml    # US & Worldwide High-Comp Staff Engineer
│       ├── hybrid_lead.yaml         # Hybrid Tech Lead / Engineering Manager
│       └── contract_specialist.yaml # Freelance / C2C Distributed Systems
├── src/
│   ├── config.py                    # Pydantic v2 configuration manager
│   ├── models.py                    # Standardized schemas for jobs, scores, telemetry
│   ├── deduplication.py             # URL canonicalization, fingerprinting, StateManager
│   ├── scoring.py                   # 0–10 weighted relevance scoring engine
│   ├── pipeline.py                  # End-to-end execution orchestrator
│   ├── main.py                      # CLI runner and entrypoint
│   ├── collectors/                  # Pluggable collector modules
│   │   ├── base.py                  # BaseCollector with retry & rate limiting
│   │   ├── greenhouse.py            # Greenhouse public boards API
│   │   ├── lever.py                 # Lever public postings API
│   │   ├── ashby.py                 # Ashby public API
│   │   ├── remotive.py              # Remotive remote jobs API
│   │   ├── remoteok.py              # RemoteOK public API
│   │   ├── arbeitnow.py             # Arbeitnow European & global remote API
│   │   ├── jobicy.py                # Jobicy API
│   │   ├── hackernews.py            # Hacker News "Who is Hiring?" Algolia collector
│   │   └── rss.py                   # Generic RSS / Atom feed parser
│   ├── notifier/                    # Multi-provider email notification engine
│   │   ├── email_service.py         # Resend, Brevo, SendGrid, SMTP, Console preview
│   │   └── templates/
│   │       ├── digest.html          # Responsive mobile-friendly HTML digest
│   │       ├── digest.txt           # Plaintext email fallback
│   │       └── immediate.html       # Single high-priority 9.0+ match alert
│   └── api/                         # FastAPI Web Control Panel Backend
│       ├── server.py                # REST API endpoints & static asset router
│       └── embedded_ui.py           # Self-contained zero-dependency dashboard UI
├── web/                             # React + Vite + Tailwind Control Panel source
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── src/
│       ├── App.tsx                  # Dashboard container & navigation
│       ├── types.ts                 # TypeScript schemas
│       └── components/              # Tab components (Roles, Filters, Sources, etc.)
├── data/                            # Persistent state & telemetry
│   ├── seen_jobs.json               # Deduplication fingerprint cache
│   ├── run_logs.json                # Execution logs and crawler latency
│   └── latest_email_preview.html    # Rendered HTML preview from last dry run
├── .github/
│   └── workflows/
│       ├── job_alert.yml            # Scheduled GitHub Actions cron runner
│       └── deploy_dashboard.yml     # Automated frontend deployment to GitHub Pages
├── tests/                           # Pytest test suite (18 unit tests)
├── .env.example                     # Environment template
├── requirements.txt                 # Backend dependencies
├── run.py                           # Root runner script
└── README.md
```

---

## Quick Start (Local Setup)

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ (optional, only needed for modifying the React frontend source)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/yourusername/JobsAlert.git
cd JobsAlert

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create your local environment file
cp .env.example .env
```

### 3. Running a Dry-Run & Email Preview
Test the collection and scoring pipeline without dispatching real emails:
```bash
python run.py --dry-run
```
This will:
1. Query active ATS and aggregator feeds.
2. Filter out blacklisted companies and excluded terms.
3. Score candidates on a 0–10 scale.
4. Render the email digest and save it to `data/latest_email_preview.html`.

### 4. Launching the Web Control Panel
Start the control panel web server:
```bash
python run.py --server --port 8000
```
Open your browser to: **`http://localhost:8000`**

From the Web Control Panel you can:
- Adjust roles, must-have skills, and excluded terms with tag chips.
- Fine-tune salary floors and scoring weights using dynamic sliders.
- Manage your dream company priority watchlist and agency blacklist.
- Toggle ATS sources and configure target company slugs (e.g. `cloudflare, datadog, linear`).
- Switch between saved search profiles (e.g., *Remote High-Comp*, *Hybrid Lead*, *Contract Specialist*).
- Click **"Test Run & Preview"** to execute a dry-run and inspect the live interactive HTML email preview in an iframe.

---

## CLI Options

The `run.py` script provides flexible flags for automation and local development:

| Flag | Description |
|---|---|
| `--dry-run` | Runs collection and scoring without sending emails or updating permanent state |
| `--send-email` | Dispatches live emails via the configured provider |
| `--profile <name>` | Executes a specific profile preset from `config/profiles/<name>.yaml` |
| `--force-all` | Ignores the deduplication cache and re-evaluates all collected postings |
| `--immediate-only` | Only sends alerts for high-priority matches scoring ≥ 9.0 |
| `--preview-email` | Renders and saves `data/latest_email_preview.html` |
| `--server` | Launches the FastAPI web control panel server |
| `--port <number>` | Specifies port for the web server (default: 8000) |

---

## Scoring Engine Specifications

The engine scores opportunities on a **0.0 to 10.0 scale**:

| Score Band | Classification | Action Taken |
|---|---|---|
| **0.0 – 4.9** | Discard / Exclude | Discarded immediately. Never alerted or emailed. |
| **5.0 – 6.9** | Low Match | Archived in state database for UI search; excluded from email. |
| **7.0 – 8.9** | Strong Match | Included in the scheduled daily/weekly email digest. |
| **9.0 – 10.0** | High Priority Target | Triggers an immediate instant alert email if enabled. |

### Evaluation Criteria Breakdown:
1. **Title & Core Stack (40% Weight):**
   - Exact title match vs. adjacent match vs. seniority match.
   - Must-have skills matching (missing skills incur score drops).
   - Nice-to-have toolchain bonuses (e.g., Rust, WebAssembly, Edge AI).
   - Hard exclusion check: postings containing negative keywords (e.g. `PHP`, `WordPress`, `Security Clearance`) or mismatched junior roles for senior candidates drop immediately to 0.0.
2. **Remote Policy & Location (20% Weight):**
   - Distinguishes "Worldwide Remote", country-restricted remote ("US-Only Remote"), and local tech hubs.
   - Full points for Worldwide remote or candidate's preferred country/state.
3. **Compensation Fit (15% Weight):**
   - Parses listed salary bands. Bonus points for salaries meeting or exceeding the user's floor.
   - Unlisted salaries are scored neutrally without penalty.
   - Significant penalties for postings explicitly below the candidate floor.
4. **Company Priority Watchlist (15% Weight):**
   - Multipliers (e.g. 1.25x - 1.50x) applied to postings from dream companies (e.g. Cloudflare, Stripe, Datadog).
   - Direct verified ATS postings (Greenhouse, Lever, Ashby) receive a source reputation boost.
   - Blacklisted agencies/recruiters drop immediately to 0.0.
5. **Recency & Urgency (10% Weight):**
   - Postings published within the last 24 hours receive maximum recency score to maximize early-applicant advantage.

---

## 100% Free-Tier Cloud Deployment Guide

You can host and run the entire system 100% free with zero monthly server costs:

### Step 1: Push Repository to GitHub
Create a private GitHub repository and push this codebase:
```bash
git remote add origin https://github.com/yourusername/JobsAlert.git
git branch -M main
git push -u origin main
```

### Step 2: Configure Free Email Delivery (Resend)
1. Register for a free account at [resend.com](https://resend.com) (includes 3,000 free emails/month).
2. Generate an API Key under **API Keys**.
3. In your GitHub repository, navigate to **Settings** → **Secrets and variables** → **Actions** and add the following repository secrets:
   - `RESEND_API_KEY`: Your Resend API token (`re_...`)
   - `CANDIDATE_EMAIL`: Your destination email address
   - `ALERTS_FROM_EMAIL`: `Job Intelligence <onboarding@resend.dev>` (works out of the box with zero custom domain DNS setup)

### Step 3: Scheduled Automation via GitHub Actions
The included workflow [`.github/workflows/job_alert.yml`](.github/workflows/job_alert.yml) is pre-configured to run on a scheduled cron trigger (e.g. daily at 07:30 UTC).

It performs the following automatically:
1. Wakes up on the scheduled cron time.
2. Pulls target vacancies from Greenhouse, Lever, Ashby, Remotive, RemoteOK, Arbeitnow, Jobicy, and Hacker News.
3. Deduplicates against previously seen postings in `data/seen_jobs.json`.
4. Scores postings using candidate rules from `config/jobs.yaml`.
5. Dispatches formatted HTML digests to your inbox via Resend.
6. Commits updated `seen_jobs.json` and execution telemetry back to the repository with `[skip ci]`.

You can also trigger a manual run anytime by visiting **Actions** → **Automated Job Intelligence Scout & Alert** → **Run workflow**.

### Step 4: Deploying the Web Control Panel (GitHub Pages or Cloudflare Pages)
- **GitHub Pages:** Enable GitHub Pages in your repo settings pointing to GitHub Actions. The included workflow [`.github/workflows/deploy_dashboard.yml`](.github/workflows/deploy_dashboard.yml) builds and publishes the web control panel automatically.
- **Cloudflare Pages / Vercel:** Connect your GitHub repo, set the root directory to `web`, framework preset to `Vite`, and build command to `npm run build`.

---

## Testing

Run the full automated test suite:
```bash
pytest -v
```

All 18 unit tests cover:
- Scoring engine edge cases (blacklists, negative terms, seniority mismatch, watchlist boosts, salary floors).
- URL canonicalization and parameter stripping (`utm_*`, `gh_src`, `ref`).
- Deduplication state persistence and SHA-256 fingerprint collisions.
- HTML and plaintext email template rendering and "Why You Match" bullets.
- FastAPI REST endpoints (`/api/health`, `/api/config`, `/api/profiles`, `/api/preview-email`, `/`).

---

## License

MIT License. Free for personal and commercial career intelligence automation.
