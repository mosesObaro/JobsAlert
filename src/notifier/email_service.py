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
from jinja2 import Environment, FileSystemLoader

from src.config import AppConfig
from src.models import ScoredJob

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
PREVIEW_FILE = Path(__file__).resolve().parent.parent / "data" / "latest_email_preview.html"


class EmailNotifier:
    """Renders structured templates and handles multi-provider dispatch."""

    def __init__(self):
        self.env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
        self.digest_html_tmpl = self.env.get_template("digest.html")
        self.digest_txt_tmpl = self.env.get_template("digest.txt")
        self.immediate_html_tmpl = self.env.get_template("immediate.html")

    def format_digest_subject(self, jobs: List[ScoredJob]) -> str:
        """Formats standard subject: [Job Alert] 27 Aug 2026 — 5 High-Match Opportunities Found"""
        date_str = datetime.now(timezone.utc).strftime("%d %b %Y")
        count = len(jobs)
        plural = "Opportunities" if count != 1 else "Opportunity"
        return f"[Job Alert] {date_str} — {count} High-Match {plural} Found"

    def render_digest(self, jobs: List[ScoredJob], config: AppConfig) -> tuple[str, str, str]:
        """Renders HTML and plaintext versions of the digest email."""
        date_str = datetime.now(timezone.utc).strftime("%A, %d %B %Y")
        subject = self.format_digest_subject(jobs)
        min_score = min([j.score for j in jobs]) if jobs else 7.0


        ctx = {
            "subject": subject,
            "header_title": f"{len(jobs)} High-Match Opportunities Found",
            "date_str": date_str,
            "candidate_name": config.profile.candidate_name,
            "recipient_email": config.delivery.recipient_email,
            "jobs": jobs,
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
        jobs: List[ScoredJob],
        config: AppConfig,
        dry_run: bool = False
    ) -> bool:
        """Sends the digest email or outputs preview in dry-run mode."""
        if not jobs:
            return True

        subject, html_body, text_body = self.render_digest(jobs, config)
        self.save_preview(html_body)

        if dry_run or config.delivery.email_provider == "console":
            print(f"\n[DRY RUN / PREVIEW] Email Subject: {subject}")
            print(f"[DRY RUN / PREVIEW] Recipient: {config.delivery.recipient_email}")
            print(f"[DRY RUN / PREVIEW] Preview saved to: {PREVIEW_FILE.resolve()}")
            return True

        return await self._dispatch_provider(
            provider=config.delivery.email_provider,
            to_email=config.delivery.recipient_email,
            from_email=config.delivery.from_email,
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
