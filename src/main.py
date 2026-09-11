"""
JobsAlert CLI & Server Entrypoint.
"""

from __future__ import annotations
import argparse
import asyncio
import sys
from pathlib import Path

from src.config import load_config, load_profile
from src.deduplication import StateManager
from src.pipeline import JobPipeline


def parse_args():
    parser = argparse.ArgumentParser(
        description="JobsAlert — Autonomous Career Intelligence & Opportunity Scout",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--dry-run", action="store_true", default=False, help="Run without dispatching real emails or saving live state")
    parser.add_argument("--send-email", action="store_true", default=False, help="Dispatch live emails via configured email provider")
    parser.add_argument("--preview-email", action="store_true", default=False, help="Render and save latest_email_preview.html")
    parser.add_argument("--force-all", action="store_true", default=False, help="Ignore seen_jobs cache and evaluate all collected postings")
    parser.add_argument("--immediate-only", action="store_true", default=False, help="Only dispatch alerts for 9.0+ immediate target matches")
    parser.add_argument("--profile", type=str, default=None, help="Preset profile name to execute (e.g. remote_high_comp)")
    parser.add_argument("--add-job", action="store_true", default=False, help="Interactively add a custom job posting")
    parser.add_argument("--income", action="store_true", default=False, help="Run the Online Income Opportunities scout pipeline")
    parser.add_argument("--income-dry-run", action="store_true", default=False, help="Evaluate online income opportunities without sending email")
    parser.add_argument("--income-send-email", action="store_true", default=False, help="Dispatch online income email digest")
    parser.add_argument("--add-income", action="store_true", default=False, help="Interactively add a custom online income opportunity")
    parser.add_argument("--server", action="store_true", default=False, help="Launch the FastAPI Web Control Panel server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Web server host")
    parser.add_argument("--port", type=int, default=8000, help="Web server port")
    return parser.parse_args()


def interactive_add_job():
    from src.collectors.custom import add_custom_job
    print("\n📝 Add a Custom Job Posting")
    print("---------------------------------------------")
    title = input("Job Title: ").strip()
    if not title:
        print("Error: Job title is required.")
        return
    company = input("Company Name: ").strip()
    if not company:
        print("Error: Company name is required.")
        return
    location = input("Location (default: Worldwide Remote): ").strip() or "Worldwide Remote"
    url = input("Application URL: ").strip()
    salary_str = input("Salary Min (e.g. 180000) [optional]: ").strip()
    salary_min = float(salary_str) if salary_str else None
    salary_max_str = input("Salary Max (e.g. 240000) [optional]: ").strip()
    salary_max = float(salary_max_str) if salary_max_str else None
    description = input("Job Description / Key Requirements: ").strip()

    entry = add_custom_job(
        title=title,
        company=company,
        location=location,
        url=url,
        description=description,
        salary_min=salary_min,
        salary_max=salary_max,
    )
    print(f"\n✓ Custom job '{title}' at '{company}' saved to data/custom_jobs.json!")
    print("Run 'python run.py --dry-run' to score and preview it.\n")


def interactive_add_income():
    from src.income_opportunities.collectors.custom import add_custom_income_opportunity
    print("\n💰 Add a Custom Online Income Opportunity")
    print("---------------------------------------------")
    title = input("Opportunity Title: ").strip()
    if not title:
        print("Error: Opportunity title is required.")
        return
    org = input("Platform / Organization (e.g. Outlier AI, Preply): ").strip()
    if not org:
        print("Error: Platform/organization is required.")
        return
    category = input("Category (default: ai_evaluation): ").strip() or "ai_evaluation"
    location = input("Location Eligibility (default: Worldwide): ").strip() or "Worldwide"
    pay_display = input("Pay Rate Display (e.g. $20–$30/hr) [optional]: ").strip() or None
    url = input("Application URL: ").strip()
    desc = input("Brief Description: ").strip()

    entry = add_custom_income_opportunity(
        title=title,
        organization=org,
        category=category,
        location_eligibility=location,
        pay_rate_display=pay_display,
        url=url,
        description=desc,
    )
    print(f"\n✓ Custom income opportunity '{title}' at '{org}' saved to data/custom_income_opportunities.json!")
    print("Run 'python run.py --income --income-dry-run' to score and preview it.\n")


async def run_income_cli(args):
    from src.income_opportunities.pipeline import IncomeOpportunityPipeline

    if args.profile:
        print(f"📁 Loading profile preset: {args.profile}")
        config = load_profile(args.profile)
    else:
        config = load_config()

    is_dry_run = not args.income_send_email or args.income_dry_run or args.dry_run

    pipeline = IncomeOpportunityPipeline(config=config.online_income)

    summary, scored_opps = await pipeline.execute(
        dry_run=is_dry_run,
        send_email=args.income_send_email or (args.send_email and not is_dry_run),
        force_all=args.force_all,
        immediate_only=args.immediate_only,
        recipient_email=config.delivery.recipient_email,
        email_provider=config.delivery.email_provider,
        from_email=config.delivery.from_email,
    )

    high_matches = [s for s in scored_opps if s.score >= 7.0]
    if high_matches:
        print("\n🏆 Top Matched Online Income Opportunities:")
        for s in high_matches[:8]:
            print(f"  ★ [{s.score}/10] {s.opportunity.title} ({s.opportunity.organization})")
            print(f"    💵 Comp: {s.opportunity.pay_rate_display or 'Flexible'}")
            print(f"    📍 Eligibility: {s.opportunity.location_eligibility}")
            print(f"    🔗 Apply: {s.opportunity.application_url or s.opportunity.url}")
            for h in s.breakdown.highlights[:2]:
                print(f"       • {h}")
    else:
        print("\nℹ️ No income opportunities currently meet the 7.0+ alert threshold.")


async def run_cli(args):
    # Load configuration
    if args.profile:
        print(f"📁 Loading profile preset: {args.profile}")
        config = load_profile(args.profile)
    else:
        config = load_config()

    is_dry_run = not args.send_email or args.dry_run

    state_mgr = StateManager()
    pipeline = JobPipeline(config=config, state_manager=state_mgr)

    summary, scored_jobs = await pipeline.execute(
        dry_run=is_dry_run,
        send_email=args.send_email,
        force_all=args.force_all,
        immediate_only=args.immediate_only,
    )

    # Print top career matches
    high_matches = [s for s in scored_jobs if s.score >= 7.0]
    if high_matches:
        print("\n🏆 Top Matched Career Opportunities:")
        for s in high_matches[:5]:
            print(f"  ★ [{s.score}/10] {s.job.title} @ {s.job.company} ({s.job.location})")
            print(f"    🔗 {s.job.url}")
            for h in s.breakdown.highlights[:2]:
                print(f"       • {h}")
    else:
        print("\nℹ️ No career jobs currently meet the 7.0+ alert threshold for this run.")

    # Print top online income matches
    if pipeline.latest_income_opportunities:
        high_income = [s for s in pipeline.latest_income_opportunities if s.score >= 7.0]
        if high_income:
            print("\n💰 Top Matched Online Income Tracks:")
            for s in high_income[:5]:
                print(f"  ★ [{s.score}/10] {s.opportunity.title} ({s.opportunity.organization})")
                print(f"    💵 Comp: {s.opportunity.pay_rate_display or 'Flexible'} | 📍 {s.opportunity.location_eligibility}")
                print(f"    🔗 Apply: {s.opportunity.application_url or s.opportunity.url}")
                for h in s.breakdown.highlights[:2]:
                    print(f"       • {h}")


def main():
    args = parse_args()
    if args.add_job:
        interactive_add_job()
        return
    if args.add_income:
        interactive_add_income()
        return
    if args.income or args.income_dry_run or args.income_send_email:
        asyncio.run(run_income_cli(args))
        return
    if args.server:
        import uvicorn
        print(f"🌐 Launching JobsAlert Web Control Panel on http://{args.host}:{args.port}")
        uvicorn.run("src.api.server:app", host=args.host, port=args.port, reload=False)
    else:
        asyncio.run(run_cli(args))


if __name__ == "__main__":
    main()
