"""
JobsAlert Email Notification Service.
Renders digest and instant-alert emails and delivers them through Resend, Brevo,
SendGrid or SMTP (or prints a preview with the "console" provider).

Every send returns a DeliveryResult; callers record an alert as delivered only
when it is truthy.
"""

from __future__ import annotations
import asyncio
import os
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr
from pathlib import Path
from typing import Any, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src import paths
from src.config import AppConfig
from src.models import ScoredJob, SpecMatchGroup
from src.money import format_range
from src.storage import write_text_atomic

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
PROVIDER_TIMEOUT_SECONDS = 20.0


def preview_file() -> Path:
    return paths.data_file(paths.EMAIL_PREVIEW)


@dataclass
class DeliveryResult:
    ok: bool
    provider: str = ""
    error: Optional[str] = None

    def __bool__(self) -> bool:
        return self.ok


def _salary(job: Any) -> str:
    period = getattr(job, "salary_period", "yearly") or "yearly"
    return format_range(job.salary_min, job.salary_max, getattr(job, "salary_currency", "USD") or "USD",
                        None if period == "yearly" else period)


def _pay(opp: Any) -> str:
    period = getattr(opp, "pay_frequency", "hourly") or "hourly"
    return format_range(opp.estimated_pay_min, opp.estimated_pay_max, getattr(opp, "pay_currency", "USD") or "USD",
                        period if period in ("hourly", "daily", "weekly", "monthly", "yearly") else None)


def _one_line(text: str) -> str:
    """Collapses whitespace so subjects built from posting titles can't span header lines."""
    return " ".join(str(text).split())


def _local_date(fmt: str, tz_name: str) -> str:
    try:
        tz = ZoneInfo(tz_name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        tz = timezone.utc
    return datetime.now(tz).strftime(fmt)


def _bare_address(address: str) -> str:
    return parseaddr(address)[1] or address.strip()


class EmailNotifier:
    """Renders templates and delivers email through the configured provider."""

    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(TEMPLATES_DIR),
            autoescape=select_autoescape(["html", "xml"]),
        )
        self.env.filters["salary"] = _salary
        self.env.filters["pay"] = _pay
        self.digest_html_tmpl = self.env.get_template("digest.html")
        self.digest_txt_tmpl = self.env.get_template("digest.txt")
        self.immediate_html_tmpl = self.env.get_template("immediate.html")
        self.income_digest_html_tmpl = self.env.get_template("income_digest.html")
        self.income_digest_txt_tmpl = self.env.get_template("income_digest.txt")
        self.income_immediate_html_tmpl = self.env.get_template("income_immediate.html")

    # ------------------------------------------------------------------ subjects
    def format_digest_subject(
        self,
        jobs: Optional[List[ScoredJob]] = None,
        income_opportunities: Optional[list] = None,
        spec_groups: Optional[List[SpecMatchGroup]] = None,
        tz_name: str = "UTC",
    ) -> str:
        """Subject for job-only, income-only or combined digests."""
        date_str = _local_date("%d %b %Y", tz_name)
        job_count = sum(len(g.jobs) for g in spec_groups) if spec_groups is not None else len(jobs or [])
        income_count = len(income_opportunities or [])

        if job_count > 0 and income_count > 0:
            job_plural = "Roles" if job_count != 1 else "Role"
            inc_plural = "Income Tracks" if income_count != 1 else "Income Track"
            return f"[Daily Alert] {date_str} — {job_count} Target {job_plural} & {income_count} Online {inc_plural} Found"
        if job_count > 0:
            plural = "Opportunities" if job_count != 1 else "Opportunity"
            return f"[Job Alert] {date_str} — {job_count} High-Match {plural} Found"
        if income_count > 0:
            plural = "Tracks" if income_count != 1 else "Track"
            return f"[Income Alert] {date_str} — {income_count} Online Income {plural} Found"
        return f"[Daily Alert] {date_str} — Daily Intelligence Digest"

    # ------------------------------------------------------------------ rendering
    def render_digest(
        self,
        jobs: Optional[List[ScoredJob]] = None,
        config: Optional[AppConfig] = None,
        income_opportunities: Optional[list] = None,
        spec_groups: Optional[List[SpecMatchGroup]] = None,
    ) -> tuple[str, str, str]:
        """Renders the HTML and plaintext digest (jobs, income tracks, or both)."""
        config = config or AppConfig()
        tz_name = config.schedule.timezone
        jobs_list = jobs or []
        income_list = income_opportunities or []
        subject = self.format_digest_subject(jobs_list, income_list, spec_groups=spec_groups, tz_name=tz_name)

        all_scores = [j.score for j in jobs_list]
        for group in spec_groups or []:
            all_scores.extend(j.score for j in group.jobs)
        all_scores.extend(o.get("score", 0.0) if isinstance(o, dict) else getattr(o, "score", 0.0) for o in income_list)

        total_jobs_count = sum(len(g.jobs) for g in spec_groups) if spec_groups is not None else len(jobs_list)
        if total_jobs_count > 0 and income_list:
            header_title = f"{total_jobs_count} Target Roles & {len(income_list)} Online Income Tracks"
        elif total_jobs_count > 0:
            header_title = f"{total_jobs_count} High-Match Opportunities Found"
        elif income_list:
            header_title = f"{len(income_list)} Online Income Tracks"
        else:
            header_title = "Daily Intelligence Digest"

        ctx = {
            "subject": subject,
            "header_title": header_title,
            "date_str": _local_date("%A, %d %B %Y", tz_name),
            "candidate_name": config.profile.candidate_name,
            "recipient_email": config.delivery.recipient_email,
            "jobs": jobs_list,
            "spec_groups": spec_groups,
            "income_opportunities": income_list,
            "min_score": min(all_scores) if all_scores else 7.0,
            "job_instant_threshold": config.schedule.instant_alert_threshold,
            "income_instant_threshold": config.online_income.instant_alert_score,
        }
        return subject, self.digest_html_tmpl.render(ctx), self.digest_txt_tmpl.render(ctx)

    def render_immediate(self, scored: ScoredJob, config: AppConfig) -> tuple[str, str]:
        """Renders an instant alert for a match at or above the instant threshold."""
        subject = _one_line(f"[Instant Alert] {scored.score}/10 Match: {scored.job.title} @ {scored.job.company}")
        ctx = {
            "scored": scored,
            "candidate_name": config.profile.candidate_name,
            "recipient_email": config.delivery.recipient_email,
            "instant_threshold": config.schedule.instant_alert_threshold,
        }
        return subject, self.immediate_html_tmpl.render(ctx)

    def render_income_digest(self, opportunities: list, candidate_name: str, recipient_email: str,
                             instant_threshold: float = 9.0, tz_name: str = "UTC") -> tuple[str, str, str]:
        """Renders the HTML and plaintext online income digest."""
        subject = self.format_digest_subject([], opportunities, tz_name=tz_name)
        scores = [o.get("score", 0.0) if isinstance(o, dict) else getattr(o, "score", 0.0) for o in opportunities]
        ctx = {
            "subject": subject,
            "header_title": f"{len(opportunities)} Online Income Tracks Found",
            "date_str": _local_date("%A, %d %B %Y", tz_name),
            "candidate_name": candidate_name,
            "recipient_email": recipient_email,
            "opportunities": opportunities,
            "min_score": min(scores) if scores else 7.0,
            "income_instant_threshold": instant_threshold,
        }
        return subject, self.income_digest_html_tmpl.render(ctx), self.income_digest_txt_tmpl.render(ctx)

    def render_income_immediate(self, scored: Any, candidate_name: str, recipient_email: str) -> tuple[str, str]:
        """Renders an instant alert for a top-scoring income track."""
        subject = _one_line(f"[Instant Alert] Online Income Track: {scored.opportunity.title} ({scored.opportunity.organization})")
        ctx = {"scored": scored, "candidate_name": candidate_name, "recipient_email": recipient_email}
        return subject, self.income_immediate_html_tmpl.render(ctx)

    def save_preview(self, html_content: str) -> Path:
        """Writes the rendered HTML to data/latest_email_preview.html."""
        target = preview_file()
        write_text_atomic(target, html_content)
        return target

    # ------------------------------------------------------------------ sending
    async def send_digest(
        self,
        jobs: Optional[List[ScoredJob]] = None,
        config: Optional[AppConfig] = None,
        income_opportunities: Optional[list] = None,
        spec_groups: Optional[List[SpecMatchGroup]] = None,
        dry_run: bool = False,
    ) -> DeliveryResult:
        """Sends the digest, or saves a preview in dry-run / console mode."""
        config = config or AppConfig()
        if not jobs and not income_opportunities and not any(g.jobs for g in spec_groups or []):
            return DeliveryResult(ok=True, provider="none")

        subject, html_body, text_body = self.render_digest(jobs, config, income_opportunities, spec_groups)
        self.save_preview(html_body)
        if dry_run or config.delivery.email_provider == "console":
            print(f"\n[DRY RUN / PREVIEW] Email Subject: {subject}")
            print(f"[DRY RUN / PREVIEW] Preview saved to: {preview_file().resolve()}")
            return DeliveryResult(ok=True, provider="console")
        return await self._dispatch_provider(config.delivery.email_provider, config.delivery.recipient_email,
                                             config.delivery.from_email, subject, html_body, text_body)

    async def send_immediate(self, job: ScoredJob, config: AppConfig, dry_run: bool = False) -> DeliveryResult:
        """Sends an instant alert for one top-tier job."""
        subject, html_body = self.render_immediate(job, config)
        self.save_preview(html_body)
        if dry_run or config.delivery.email_provider == "console":
            print(f"\n[DRY RUN / PREVIEW] Instant Alert: {subject}")
            return DeliveryResult(ok=True, provider="console")
        apply_line = f" Apply at: {job.job.url}" if job.job.url else ""
        return await self._dispatch_provider(
            config.delivery.email_provider, config.delivery.recipient_email, config.delivery.from_email,
            subject, html_body, f"Instant Match: {job.job.title} at {job.job.company}.{apply_line}",
        )

    async def send_income_digest(
        self,
        opportunities: list,
        candidate_name: str,
        recipient_email: str,
        email_provider: str = "console",
        from_email: str = "alerts@jobsalert.dev",
        dry_run: bool = False,
        instant_threshold: float = 9.0,
    ) -> DeliveryResult:
        """Sends the online income digest, or saves a preview in dry-run / console mode."""
        if not opportunities:
            return DeliveryResult(ok=True, provider="none")
        subject, html_body, text_body = self.render_income_digest(opportunities, candidate_name, recipient_email, instant_threshold)
        self.save_preview(html_body)
        if dry_run or email_provider == "console":
            print(f"\n[INCOME SCOUT PREVIEW] Email Subject: {subject}")
            print(f"[INCOME SCOUT PREVIEW] Preview saved to: {preview_file().resolve()}")
            return DeliveryResult(ok=True, provider="console")
        return await self._dispatch_provider(email_provider, recipient_email, from_email, subject, html_body, text_body)

    async def send_income_immediate(
        self,
        scored: Any,
        candidate_name: str,
        recipient_email: str,
        email_provider: str = "console",
        from_email: str = "alerts@jobsalert.dev",
        dry_run: bool = False,
    ) -> DeliveryResult:
        """Sends an instant alert for one top-tier income track."""
        subject, html_body = self.render_income_immediate(scored, candidate_name, recipient_email)
        self.save_preview(html_body)
        if dry_run or email_provider == "console":
            print(f"\n[INCOME SCOUT PREVIEW] Instant Alert: {subject}")
            return DeliveryResult(ok=True, provider="console")
        link = scored.opportunity.application_url or scored.opportunity.url
        return await self._dispatch_provider(
            email_provider, recipient_email, from_email, subject, html_body,
            f"Instant Income Match: {scored.opportunity.title} ({scored.opportunity.organization}). Apply at: {link}",
        )

    async def _dispatch_provider(self, provider: str, to_email: str, from_email: str, subject: str,
                                 html_body: str, text_body: str) -> DeliveryResult:
        provider = (provider or "").lower().strip()
        try:
            if provider == "smtp":
                return await asyncio.to_thread(self._send_smtp, to_email, from_email, subject, html_body, text_body)
            if provider in ("resend", "brevo", "sendgrid"):
                return await self._send_http(provider, to_email, from_email, subject, html_body, text_body)
            return self._failed(provider, f"Unknown email provider '{provider}'")
        except httpx.HTTPError as exc:
            return self._failed(provider, f"{type(exc).__name__}: {exc}")
        except Exception as exc:  # any other delivery failure must be reported, not crash the run
            return self._failed(provider, f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _failed(provider: str, error: str) -> DeliveryResult:
        print(f"[ERROR] Email delivery via {provider or 'unknown provider'} failed: {error}")
        return DeliveryResult(ok=False, provider=provider, error=error[:500])

    async def _send_http(self, provider: str, to_email: str, from_email: str, subject: str,
                         html_body: str, text_body: str) -> DeliveryResult:
        key_name = {"resend": "RESEND_API_KEY", "brevo": "BREVO_API_KEY", "sendgrid": "SENDGRID_API_KEY"}[provider]
        api_key = os.getenv(key_name)
        if not api_key:
            return self._failed(provider, f"{key_name} is not set")

        sender = _bare_address(from_email) or "alerts@jobsalert.dev"
        if provider == "resend":
            url, ok_codes = "https://api.resend.com/emails", (200, 201)
            headers = {"Authorization": f"Bearer {api_key}"}
            payload: dict = {"from": from_email, "to": [to_email], "subject": subject, "html": html_body, "text": text_body}
        elif provider == "brevo":
            url, ok_codes = "https://api.brevo.com/v3/smtp/email", (200, 201)
            headers = {"api-key": api_key}
            payload = {"sender": {"email": sender, "name": parseaddr(from_email)[0] or "JobsAlert"},
                       "to": [{"email": to_email}], "subject": subject, "htmlContent": html_body, "textContent": text_body}
        else:
            url, ok_codes = "https://api.sendgrid.com/v3/mail/send", (200, 202)
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {"personalizations": [{"to": [{"email": to_email}]}], "from": {"email": sender},
                       "subject": subject, "content": [{"type": "text/plain", "value": text_body},
                                                       {"type": "text/html", "value": html_body}]}

        async with httpx.AsyncClient(timeout=PROVIDER_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, headers={**headers, "Content-Type": "application/json"}, json=payload)
        if resp.status_code in ok_codes:
            print(f"✓ Email delivered via {provider.capitalize()}")
            return DeliveryResult(ok=True, provider=provider)
        return self._failed(provider, f"HTTP {resp.status_code}: {resp.text[:300]}")

    def _send_smtp(self, to_email: str, from_email: str, subject: str, html_body: str, text_body: str) -> DeliveryResult:
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

        context = ssl.create_default_context()
        if port == 465:
            server: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=PROVIDER_TIMEOUT_SECONDS, context=context)
        else:
            server = smtplib.SMTP(host, port, timeout=PROVIDER_TIMEOUT_SECONDS)
        try:
            if use_tls and port != 465:
                server.starttls(context=context)
            if username and password:
                server.login(username, password)
            server.sendmail(_bare_address(from_email), [to_email], msg.as_string())
        finally:
            try:
                server.quit()
            except smtplib.SMTPException:
                server.close()
        print("✓ Email delivered via SMTP")
        return DeliveryResult(ok=True, provider="smtp")
