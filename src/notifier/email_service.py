"""
JobsAlert Email Notification Service.
Supports Resend (recommended free tier), Brevo, SendGrid, SMTP, and local Console/File preview.
"""

from __future__ import annotations
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, List, Optional
import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.config import AppConfig
from src.models import ScoredJob

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
PREVIEW_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "latest_email_preview.html"


class EmailNotifier:
    """Renders structured templates and handles multi-provider dispatch."""

    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(TEMPLATES_DIR),
            autoescape=select_autoescape(["html", "xml"])
        )
        self.digest_html_tmpl = self.env.get_template("digest.html")
        self.digest_txt_tmpl = self.env.get_template("digest.txt")
        self.immediate_html_tmpl = self.env.get_template("immediate.html")
        self.income_digest_html_tmpl = self.env.get_template("income_digest.html")
        self.income_digest_txt_tmpl = self.env.get_template("income_digest.txt")
        self.income_immediate_html_tmpl = self.env.get_template("income_immediate.html")

    def format_digest_subject(
        self,
        jobs: Optional[List[ScoredJob]] = None,
        income_opportunities: Optional[list] = None
    ) -> str:
        """Formats standard subject dynamically for jobs, income tracks, or unified alerts."""
        date_str = datetime.now(timezone.utc).strftime("%d %b %Y")
        job_count = len(jobs) if jobs else 0
        income_count = len(income_opportunities) if income_opportunities else 0

        if job_count > 0 and income_count > 0:
            job_plural = "Roles" if job_count != 1 else "Role"
            inc_plural = "Income Tracks" if income_count != 1 else "Income Track"
            return f"[Daily Alert] {date_str} — {job_count} Target {job_plural} & {income_count} Online {inc_plural} Found"
        elif job_count > 0:
            plural = "Opportunities" if job_count != 1 else "Opportunity"
            return f"[Job Alert] {date_str} — {job_count} High-Match {plural} Found"
        elif income_count > 0:
            plural = "Tracks" if income_count != 1 else "Track"
            return f"[Income Alert] {date_str} — {income_count} Verified Online Income {plural} Found"
        else:
            return f"[Daily Alert] {date_str} — Daily Intelligence Digest"

    def format_income_digest_subject(self, opportunities: list) -> str:
        """Formats standard subject: [Income Alert] 27 Aug 2026 — 4 Verified Online Gigs & AI Evaluation Tracks"""
        date_str = datetime.now(timezone.utc).strftime("%d %b %Y")
        count = len(opportunities)
        plural = "Tracks" if count != 1 else "Track"
        return f"[Income Alert] {date_str} — {count} Verified Online Income {plural} Found"

    def render_digest(
        self,
        jobs: Optional[List[ScoredJob]] = None,
        config: Optional[AppConfig] = None,
        income_opportunities: Optional[list] = None
    ) -> tuple[str, str, str]:
        """Renders HTML and plaintext versions of the digest email, supporting combined jobs & income tracks."""
        date_str = datetime.now(timezone.utc).strftime("%A, %d %B %Y")
        jobs_list = jobs or []
        income_list = income_opportunities or []
        subject = self.format_digest_subject(jobs_list, income_list)

        all_scores = [j.score for j in jobs_list]
        for opp in income_list:
            if isinstance(opp, dict):
                all_scores.append(opp.get("score", 0.0))
            else:
                all_scores.append(getattr(opp, "score", 0.0))

        min_score = min(all_scores) if all_scores else 7.0

        if jobs_list and income_list:
            header_title = f"{len(jobs_list)} Target Roles & {len(income_list)} Online Income Tracks"
        elif jobs_list:
            header_title = f"{len(jobs_list)} High-Match Opportunities Found"
        elif income_list:
            header_title = f"{len(income_list)} Verified Online Income Tracks"
        else:
            header_title = "Daily Intelligence Digest"

        candidate_name = config.profile.candidate_name if config else "Candidate"
        recipient_email = config.delivery.recipient_email if config else "candidate@example.com"

        ctx = {
            "subject": subject,
            "header_title": header_title,
            "date_str": date_str,
            "candidate_name": candidate_name,
            "recipient_email": recipient_email,
            "jobs": jobs_list,
            "income_opportunities": income_list,
            "min_score": min_score,
        }

        html_content = self.digest_html_tmpl.render(ctx)
        text_content = self.digest_txt_tmpl.render(ctx)
        return subject, html_content, text_content

    def render_immediate(self, scored: ScoredJob, config: AppConfig) -> tuple[str, str]:
        """Renders an instant high-priority alert for a 9.0+ match."""
        subject = f"[URGENT 9.0+] {scored.score}/10 Match: {scored.job.title} @ {scored.job.company}"
        ctx = {
            "scored": scored,
            "candidate_name": config.profile.candidate_name,
            "recipient_email": config.delivery.recipient_email,
        }
        html_content = self.immediate_html_tmpl.render(ctx)
        return subject, html_content

    def save_preview(self, html_content: str) -> Path:
        """Saves rendered HTML to data/latest_email_preview.html for instant inspection."""
        PREVIEW_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PREVIEW_FILE, "w", encoding="utf-8") as f:
            f.write(html_content)
        return PREVIEW_FILE

    async def send_digest(
        self,
        jobs: Optional[List[ScoredJob]] = None,
        config: Optional[AppConfig] = None,
        income_opportunities: Optional[list] = None,
        dry_run: bool = False
    ) -> bool:
        """Sends the digest email or outputs preview in dry-run mode, supporting combined opportunities."""
        jobs_list = jobs or []
        income_list = income_opportunities or []
        if not jobs_list and not income_list:
            return True

        subject, html_body, text_body = self.render_digest(jobs_list, config, income_opportunities=income_list)
        self.save_preview(html_body)

        to_email = config.delivery.recipient_email if config else "candidate@example.com"
        provider = config.delivery.email_provider if config else "console"
        from_email = config.delivery.from_email if config else "alerts@jobsalert.dev"

        if dry_run or provider == "console":
            print(f"\n[DRY RUN / PREVIEW] Email Subject: {subject}")
            print(f"[DRY RUN / PREVIEW] Recipient: {to_email}")
            print(f"[DRY RUN / PREVIEW] Preview saved to: {PREVIEW_FILE.resolve()}")
            return True

        return await self._dispatch_provider(
            provider=provider,
            to_email=to_email,
            from_email=from_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

    async def send_immediate(
        self,
        job: ScoredJob,
        config: AppConfig,
        dry_run: bool = False
    ) -> bool:
        """Dispatches an immediate alert for top-tier opportunities."""
        subject, html_body = self.render_immediate(job, config)
        self.save_preview(html_body)

        if dry_run or config.delivery.email_provider == "console":
            print(f"\n[DRY RUN / PREVIEW] Instant Alert: {subject}")
            return True

        return await self._dispatch_provider(
            provider=config.delivery.email_provider,
            to_email=config.delivery.recipient_email,
            from_email=config.delivery.from_email,
            subject=subject,
            html_body=html_body,
            text_body=f"Instant Match: {job.job.title} at {job.job.company}. Apply at: {job.job.url}",
        )

    def render_income_digest(self, opportunities: list, candidate_name: str, recipient_email: str) -> tuple[str, str, str]:
        """Renders HTML and plaintext versions of the online income opportunities digest."""
        date_str = datetime.now(timezone.utc).strftime("%A, %d %B %Y")
        subject = self.format_income_digest_subject(opportunities)
        
        def _get_score(o):
            return o.get("score", 0.0) if isinstance(o, dict) else getattr(o, "score", 0.0)

        scores = [_get_score(o) for o in opportunities]
        min_score = min(scores) if scores else 7.0

        ctx = {
            "subject": subject,
            "header_title": f"{len(opportunities)} Verified Income Tracks Found",
            "date_str": date_str,
            "candidate_name": candidate_name,
            "recipient_email": recipient_email,
            "opportunities": opportunities,
            "min_score": min_score,
        }

        html_content = self.income_digest_html_tmpl.render(ctx)
        text_content = self.income_digest_txt_tmpl.render(ctx)
        return subject, html_content, text_content

    def render_income_immediate(self, scored: any, candidate_name: str, recipient_email: str) -> tuple[str, str]:
        """Renders an instant high-priority alert for a 9.0+ income opportunity."""
        subject = f"[URGENT 9.0+] Top Online Income Track: {scored.opportunity.title} ({scored.opportunity.organization})"
        ctx = {
            "scored": scored,
            "candidate_name": candidate_name,
            "recipient_email": recipient_email,
        }
        html_content = self.income_immediate_html_tmpl.render(ctx)
        return subject, html_content

    async def send_income_digest(
        self,
        opportunities: list,
        candidate_name: str,
        recipient_email: str,
        email_provider: str = "console",
        from_email: str = "alerts@jobsalert.dev",
        dry_run: bool = False
    ) -> bool:
        """Sends the online income digest email or outputs preview in dry-run mode."""
        if not opportunities:
            return True

        subject, html_body, text_body = self.render_income_digest(opportunities, candidate_name, recipient_email)
        self.save_preview(html_body)

        if dry_run or email_provider == "console":
            print(f"\n[INCOME SCOUT PREVIEW] Email Subject: {subject}")
            print(f"[INCOME SCOUT PREVIEW] Recipient: {recipient_email}")
            print(f"[INCOME SCOUT PREVIEW] Preview saved to: {PREVIEW_FILE.resolve()}")
            return True

        return await self._dispatch_provider(
            provider=email_provider,
            to_email=recipient_email,
            from_email=from_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

    async def send_income_immediate(
        self,
        scored: any,
        candidate_name: str,
        recipient_email: str,
        email_provider: str = "console",
        from_email: str = "alerts@jobsalert.dev",
        dry_run: bool = False
    ) -> bool:
        """Dispatches an immediate alert for a top-tier income track."""
        subject, html_body = self.render_income_immediate(scored, candidate_name, recipient_email)
        self.save_preview(html_body)

        if dry_run or email_provider == "console":
            print(f"\n[INCOME SCOUT PREVIEW] Instant Alert: {subject}")
            return True

        return await self._dispatch_provider(
            provider=email_provider,
            to_email=recipient_email,
            from_email=from_email,
            subject=subject,
            html_body=html_body,
            text_body=f"Instant Income Match: {scored.opportunity.title} ({scored.opportunity.organization}). Apply at: {scored.opportunity.application_url or scored.opportunity.url}",
        )

    async def _dispatch_provider(
        self,
        provider: str,
        to_email: str,
        from_email: str,
        subject: str,
        html_body: str,
        text_body: str,
    ) -> bool:
        provider = provider.lower().strip()

        # 1. RESEND (Default free tier: 3,000 emails/mo)
        if provider == "resend":
            api_key = os.getenv("RESEND_API_KEY")
            if not api_key:
                print("[WARNING] RESEND_API_KEY is not set. Falling back to preview.")
                return False
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "from": from_email,
                        "to": [to_email],
                        "subject": subject,
                        "html": html_body,
                        "text": text_body,
                    },
                )
                if resp.status_code in [200, 201]:
                    print(f"✓ Email successfully delivered via Resend to {to_email}")
                    return True
                print(f"[ERROR] Resend error {resp.status_code}: {resp.text}")
                return False

        # 2. BREVO (300 free emails/day)
        elif provider == "brevo":
            api_key = os.getenv("BREVO_API_KEY")
            if not api_key:
                print("[WARNING] BREVO_API_KEY is not set.")
                return False
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://api.brevo.com/v3/smtp/email",
                    headers={"api-key": api_key, "Content-Type": "application/json"},
                    json={
                        "sender": {"email": from_email.split("<")[-1].replace(">", "").strip() or "alerts@jobsalert.dev", "name": "JobsAlert Scout"},
                        "to": [{"email": to_email}],
                        "subject": subject,
                        "htmlContent": html_body,
                        "textContent": text_body,
                    },
                )
                return resp.status_code in [200, 201]

        # 3. SENDGRID
        elif provider == "sendgrid":
            api_key = os.getenv("SENDGRID_API_KEY")
            if not api_key:
                print("[WARNING] SENDGRID_API_KEY is not set.")
                return False
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "personalizations": [{"to": [{"email": to_email}]}],
                        "from": {"email": from_email.split("<")[-1].replace(">", "").strip() or "alerts@jobsalert.dev"},
                        "subject": subject,
                        "content": [
                            {"type": "text/plain", "value": text_body},
                            {"type": "text/html", "value": html_body},
                        ],
                    },
                )
                return resp.status_code in [200, 202]

        # 4. STANDARD SMTP (Gmail App Password, AWS SES, Custom SMTP)
        elif provider == "smtp":
            host = os.getenv("SMTP_HOST", "smtp.gmail.com")
            port = int(os.getenv("SMTP_PORT", "587"))
            username = os.getenv("SMTP_USERNAME")
            password = os.getenv("SMTP_PASSWORD")
            use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = from_email
            msg["To"] = to_email

            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            try:
                server = smtplib.SMTP(host, port)
                if use_tls:
                    server.starttls()
                if username and password:
                    server.login(username, password)
                server.sendmail(from_email, [to_email], msg.as_string())
                server.quit()
                print(f"✓ Email successfully delivered via SMTP to {to_email}")
                return True
            except Exception as e:
                print(f"[ERROR] SMTP sending failed: {e}")
                return False

        return False
