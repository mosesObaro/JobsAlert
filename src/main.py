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
    parser.add_argument("--server", action="store_true", default=False, help="Launch the FastAPI Web Control Panel server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Web server host")
    parser.add_argument("--port", type=int, default=8000, help="Web server port")
    return parser.parse_args()


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

    # Print top 5 matches
    high_matches = [s for s in scored_jobs if s.score >= 7.0]
    if high_matches:
        print("\n🏆 Top Matched Opportunities:")
        for s in high_matches[:5]:
            print(f"  ★ [{s.score}/10] {s.job.title} @ {s.job.company} ({s.job.location})")
            print(f"    🔗 {s.job.url}")
            for h in s.breakdown.highlights[:2]:
                print(f"       • {h}")
    else:
        print("\nℹ️ No jobs currently meet the 7.0+ alert threshold for this run.")


def main():
    args = parse_args()
    if args.server:
        import uvicorn
        print(f"🌐 Launching JobsAlert Web Control Panel on http://{args.host}:{args.port}")
        uvicorn.run("src.api.server:app", host=args.host, port=args.port, reload=False)
    else:
        asyncio.run(run_cli(args))


if __name__ == "__main__":
    main()
