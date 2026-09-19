# JobsAlert

JobsAlert watches job boards, company career pages and hiring feeds, scores every new posting against the job searches you define, and emails you the good ones. It runs on a schedule with GitHub Actions and has a local web control panel. An optional second track finds flexible online income work (AI evaluation, user testing, tutoring, transcription) and adds it to the same email.

## How it works

Each run goes through the same stages:

1. **Collect** postings from company job boards (Greenhouse, Lever, Ashby), remote job boards (Remotive, RemoteOK, Arbeitnow, Jobicy), the monthly Hacker News "Who is hiring?" threads, Twitter/X, RSS/Atom feeds and jobs you add by hand. Every source reports its health; a source that fails or returns nothing shows as degraded.
2. **Deduplicate** against postings already processed. Identities are stable across runs, and postings still listed are kept in memory until no source has shown them for `state.retention_days` (90 by default).
3. **Score** each new posting from 0 to 10 against every job spec, with a breakdown of why it matches.
4. **Verify links** of the postings worth alerting. Only a 404/410 or a "position closed" page counts as dead; rate limits, blocks and timeouts leave the posting in.
5. **Deliver** an instant email for top matches and one digest grouped by job spec.
6. **Save state.** A posting counts as alerted only after the email provider accepted it. Matches that couldn't be sent stay queued and are retried on the next run.

### Scoring

| Score | What happens |
|---|---|
| below 5.0 | Discarded |
| 5.0 – 7.0 | Kept as a low match (visible in the control panel, not emailed) |
| 7.0 – instant threshold | Included in the digest |
| instant threshold and above (`schedule.instant_alert_threshold`) | Instant email, and included in the digest |

The score weighs title and skills, location and remote eligibility, pay, your company watchlist and recency (weights are configurable). Roles, skills and company names are matched as whole words. Remote postings are checked against where you can work from: a role limited to other countries (e.g. "Remote (US)", "must be located in the UK") scores low. Salaries in other currencies and periods are converted to annual USD with the rates in `fx_rates_to_usd`.

## Quick start

Requirements: Python 3.12; Node 20 only if you want the web control panel.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # add your email provider key and address
python run.py --dry-run     # collect and score without sending or saving anything
```

A dry run saves the rendered digest to `data/latest_email_preview.html`.

### Control panel

```bash
cd web && npm install && npm run build && cd ..
python run.py --server      # http://localhost:8000
```

For frontend development, run `npm run dev` in `web/` (http://localhost:3000, proxied to the API on port 8000).

The server listens on 127.0.0.1 only. Every change goes through an API token that the dashboard fetches automatically on this machine. To reach the panel from another device, set `JOBSALERT_API_TOKEN` to a long random value and start with `--host 0.0.0.0`; the dashboard then asks for the token.

## Configuration

`config/jobs.yaml` holds everything the control panel edits:

- **`job_specs`** — the searches you run, e.g. "HR Remote Roles" or "Junior Data Analyst — Remote Contract". Each has its own roles, title keywords, skills, seniority, employment type, locations and salary floor. Empty fields inherit the defaults below.
- **`profile` / `filters`** — defaults for every spec. Excluded terms and companies here always apply.
- **`company_watchlist`** — companies whose postings get a score boost.
- **`sources`** — which sources run, company board slugs, RSS feeds, Twitter queries.
- **`schedule`** — the instant alert threshold and the time zone used for dates in emails. When runs happen is set by the cron in `.github/workflows/job_alert.yml` (07:30 and 19:30 UTC).
- **`delivery`** — email provider and addresses. `CANDIDATE_EMAIL`, `ALERTS_FROM_EMAIL` and `EMAIL_PROVIDER` from the environment override these at runtime and are never written back to the file.
- **`link_verification`**, **`state`**, **`fx_rates_to_usd`** — link checking limits, how long processed postings are remembered, exchange rates.
- **`online_income`** — the online income track: where you can work from, minimum hourly pay, maximum weekly hours, which platform groups to include, and quality gates.

`config/profiles/*.yaml` are saved presets (`python run.py --profile hr_remote_nigeria`). `config/income_catalog.yaml` is a hand-maintained list of income platforms; each entry has a `last_reviewed` date, and entries older than `online_income.catalog_stale_after_days` are flagged for review.

Jobs and income opportunities you add yourself live in `data/custom_jobs.json` and `data/custom_income_opportunities.json` (also editable from the control panel, or with `--add-job` / `--add-income`).

## Command line

| Flag | Description |
|---|---|
| `--dry-run` | Collect and score without sending email or saving state |
| `--send-email` | Send alerts through the configured provider |
| `--profile <name>` | Run a saved profile from `config/profiles/<name>.yaml` |
| `--force-all` | Re-score postings that were already processed (already-alerted ones are never re-sent) |
| `--immediate-only` | Send only instant alerts; digest matches wait for the next full run |
| `--income`, `--income-dry-run`, `--income-send-email` | Run only the online income track |
| `--add-job`, `--add-income` | Add a custom job or income opportunity interactively |
| `--server [--host H] [--port P]` | Start the control panel API |
| `--trigger <name>` | Label recorded in the run log (the scheduled workflow sets it) |

Exit codes: `0` success, `1` some alerts could not be delivered (they are retried on the next run), `2` the configuration or a state file could not be read.

## Scheduled runs (GitHub Actions)

1. Add repository secrets: `RESEND_API_KEY` (or `BREVO_API_KEY`, `SENDGRID_API_KEY`, or the `SMTP_*` settings), `CANDIDATE_EMAIL` and `ALERTS_FROM_EMAIL`.
2. `.github/workflows/job_alert.yml` runs twice a day and can be started manually from the Actions tab, with options for a dry run, a profile, re-scoring everything, or instant alerts only.
3. Processed postings, run logs and the link cache live on the **`jobsalert-state`** branch as a single commit that each run replaces, so `main`'s history doesn't grow. The first run after upgrading copies the state files from `main` to that branch and stops tracking them on `main`. To look at production state locally, run `scripts/sync_state.sh`.
4. If an email can't be sent, the run fails (red in Actions), records what was delivered, and keeps the rest queued for the next run.

`.github/workflows/ci.yml` runs the Python tests, `ruff`, and the dashboard type-check and build on every pull request.

## Development

```bash
pytest -q          # tests never touch real data, config or email, and make no network calls
ruff check .
cd web && npm run typecheck && npm run build
```

Project layout:

```
src/
  collectors/            job sources (one module per source) and the shared collector base
  income_opportunities/  income track: catalogue/RSS/custom collectors, screening, scoring, pipeline
  api/server.py          control panel API
  notifier/              email rendering (Jinja2 templates) and providers
  pipeline.py            the run: collect -> deduplicate -> score -> verify -> deliver -> save
  scoring.py, eligibility.py, money.py, matching.py, verifier.py, deduplication.py, storage.py
web/                     React + TypeScript control panel (Vite, Tailwind)
config/                  jobs.yaml, profiles/, income_catalog.yaml
data/                    custom entries (tracked) and local runtime state (ignored)
tests/                   pytest suite
```

## License

MIT
