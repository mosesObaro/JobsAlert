"""
JobsAlert CLI & Server Entrypoint.

Exit codes: 0 success, 1 a live run could not deliver some alerts (they stay queued
for the next run), 2 configuration or state files are unreadable.
"""

from __future__ import annotations
import argparse
import asyncio
import ipaddress
import os
import sys
from typing import Optional

from src.config import load_config, load_profile
from src.storage import StateFileError


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="JobsAlert — job and online income alert scout",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--dry-run", action="store_true", default=False, help="Collect and score without sending email or saving state")
    parser.add_argument("--send-email", action="store_true", default=False, help="Send alerts through the configured email provider")
    parser.add_argument("--force-all", action="store_true", default=False, help="Re-score postings that were already processed")
    parser.add_argument("--immediate-only", action="store_true", default=False, help="Send only instant alerts; digest matches wait for the next full run")
    parser.add_argument("--profile", type=str, default=None, help="Profile preset to run (e.g. remote_high_comp)")
    parser.add_argument("--trigger", type=str, default="cli", help="Recorded in run logs (e.g. schedule, workflow_dispatch)")
    parser.add_argument("--add-job", action="store_true", default=False, help="Interactively add a custom job posting")
    parser.add_argument("--income", action="store_true", default=False, help="Run only the online income scout")
    parser.add_argument("--income-dry-run", action="store_true", default=False, help="Run the income scout without sending email")
    parser.add_argument("--income-send-email", action="store_true", default=False, help="Run the income scout and send its digest")
    parser.add_argument("--add-income", action="store_true", default=False, help="Interactively add a custom online income opportunity")
    parser.add_argument("--server", action="store_true", default=False, help="Launch the web control panel API server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Web server host (non-local hosts require JOBSALERT_API_TOKEN)")
    parser.add_argument("--port", type=int, default=8000, help="Web server port")
    return parser.parse_args(argv)


def _prompt_float(label: str) -> Optional[float]:
    while True:
        raw = input(label).strip().replace(",", "")
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            print("  Please enter a number, e.g. 180000 (or leave blank).")


def interactive_add_job():
    from src.collectors.custom import add_custom_job

    print("\n📝 Add a Custom Job Posting")
    print("---------------------------------------------")
    title = input("Job Title: ").strip()
    company = input("Company Name: ").strip()
    if not title or not company:
        print("Error: job title and company name are required.")
        return
    location = input("Location (default: Worldwide Remote): ").strip() or "Worldwide Remote"
    url = input("Application URL: ").strip()
    salary_min = _prompt_float("Salary Min (e.g. 180000) [optional]: ")
    salary_max = _prompt_float("Salary Max (e.g. 240000) [optional]: ")
    currency = (input("Salary currency (default: USD): ").strip() or "USD").upper()
    period = input("Salary period — yearly, monthly or hourly (default: yearly): ").strip().lower() or "yearly"
    description = input("Job Description / Key Requirements: ").strip()

    add_custom_job(
        title=title, company=company, location=location, url=url, description=description,
        salary_min=salary_min, salary_max=salary_max, salary_currency=currency, salary_period=period,
    )
    print(f"\n✓ Custom job '{title}' at '{company}' saved to data/custom_jobs.json.")
    print("Run 'python run.py --dry-run' to score and preview it.\n")


def interactive_add_income():
    from src.income_opportunities.collectors.custom import add_custom_income_opportunity

    print("\n💰 Add a Custom Online Income Opportunity")
    print("---------------------------------------------")
    title = input("Opportunity Title: ").strip()
    org = input("Platform / Organization (e.g. Outlier AI, Preply): ").strip()
    if not title or not org:
        print("Error: title and platform/organization are required.")
        return
    category = input("Category (default: general_flexible): ").strip() or "general_flexible"
    location = input("Location Eligibility (default: Worldwide): ").strip() or "Worldwide"
    pay_min = _prompt_float("Minimum pay per hour/task [optional]: ")
    pay_max = _prompt_float("Maximum pay per hour/task [optional]: ")
    pay_display = input("Pay as shown on the listing (e.g. $20–$30/hr) [optional]: ").strip() or None
    url = input("Application URL: ").strip()
    description = input("Brief Description: ").strip()

    add_custom_income_opportunity(
        title=title, organization=org, category=category, location_eligibility=location,
        estimated_pay_min=pay_min, estimated_pay_max=pay_max, pay_rate_display=pay_display,
        url=url, description=description,
    )
    print(f"\n✓ Custom income opportunity '{title}' at '{org}' saved to data/custom_income_opportunities.json.")
    print("Run 'python run.py --income-dry-run' to score and preview it.\n")


async def run_income_cli(args) -> int:
    from src.income_opportunities.deduplication import IncomeStateManager
    from src.income_opportunities.pipeline import IncomeOpportunityPipeline

    config = load_profile(args.profile) if args.profile else load_config()
    send = args.income_send_email and not (args.income_dry_run or args.dry_run)
    pipeline = IncomeOpportunityPipeline(
        config=config.online_income,
        state_manager=IncomeStateManager(),
        fx_rates=config.fx_rates_to_usd,
        link_config=config.link_verification,
        retention_days=config.state.retention_days,
    )
    summary, scored = await pipeline.execute(
        dry_run=not send,
        send_email=send,
        force_all=args.force_all,
        immediate_only=args.immediate_only,
        recipient_email=config.delivery.recipient_email,
        email_provider=config.delivery.email_provider,
        from_email=config.delivery.from_email,
        trigger=args.trigger,
    )

    top = [s for s in scored if s.action in ("instant", "digest")]
    if top:
        print("🏆 Top online income opportunities:")
        for s in top[:8]:
            print(f"  ★ [{s.score}/10] {s.opportunity.title} ({s.opportunity.organization})")
            print(f"    💵 {s.opportunity.pay_rate_display or 'Pay not stated'} | 📍 {s.opportunity.location_eligibility}")
            print(f"    🔗 {s.opportunity.application_url or s.opportunity.url}")
    else:
        print("ℹ️ No income opportunities reached the alert threshold.")
    return _exit_code(summary.delivery_errors)


async def run_cli(args) -> int:
    from src.deduplication import StateManager
    from src.pipeline import JobPipeline

    if args.profile:
        print(f"📁 Loading profile preset: {args.profile}")
    config = load_profile(args.profile) if args.profile else load_config()
    send = args.send_email and not args.dry_run

    pipeline = JobPipeline(config=config, state_manager=StateManager())
    summary, scored_jobs = await pipeline.execute(
        dry_run=not send,
        send_email=send,
        force_all=args.force_all,
        immediate_only=args.immediate_only,
        trigger=args.trigger,
    )

    best = {}
    for s in scored_jobs:
        if s.action in ("instant", "digest") and s.score > best.get(s.job.fingerprint, (0, None))[0]:
            best[s.job.fingerprint] = (s.score, s)
    matches = sorted((s for _, s in best.values()), key=lambda s: s.score, reverse=True)
    if matches:
        print("🏆 Top career matches:")
        for s in matches[:5]:
            print(f"  ★ [{s.score}/10] {s.job.title} @ {s.job.company} ({s.job.location}) — {s.spec_name or 'default spec'}")
            if s.job.url:
                print(f"    🔗 {s.job.url}")
    else:
        print("ℹ️ No career postings reached the alert threshold in this run.")

    income = [s for s in pipeline.latest_income_opportunities if s.action in ("instant", "digest")]
    if income:
        print("💰 Top online income tracks:")
        for s in income[:5]:
            print(f"  ★ [{s.score}/10] {s.opportunity.title} ({s.opportunity.organization})")
    return _exit_code(summary.delivery_errors)


def _exit_code(delivery_errors) -> int:
    if delivery_errors:
        print("\n❌ Some alerts could not be delivered and will be retried on the next live run:")
        for error in delivery_errors:
            print(f"   - {error}")
        return 1
    return 0


def _is_loopback(host: str) -> bool:
    if host in ("localhost",):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def run_server(host: str, port: int) -> int:
    import uvicorn

    if not _is_loopback(host) and not os.getenv("JOBSALERT_API_TOKEN"):
        print("Refusing to listen on a non-local address without an API token.\n"
              "Set JOBSALERT_API_TOKEN to a long random value, or use the default --host 127.0.0.1.")
        return 2
    os.environ["JOBSALERT_BIND_HOST"] = host
    print(f"🌐 JobsAlert control panel on http://{'localhost' if _is_loopback(host) else host}:{port}")
    uvicorn.run("src.api.server:app", host=host, port=port, reload=False)
    return 0


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        if args.add_job:
            interactive_add_job()
            return 0
        if args.add_income:
            interactive_add_income()
            return 0
        if args.server:
            return run_server(args.host, args.port)
        if args.income or args.income_dry_run or args.income_send_email:
            return asyncio.run(run_income_cli(args))
        return asyncio.run(run_cli(args))
    except (StateFileError, FileNotFoundError, ValueError) as exc:
        print(f"❌ {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
