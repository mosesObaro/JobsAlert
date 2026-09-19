"""
JobsAlert Control Panel API.
REST endpoints for configuration, profiles, on-demand runs, results, custom entries,
email previews and telemetry, plus the built React dashboard.

Security model:
- The server listens on 127.0.0.1 by default (see src/main.py).
- Every state-changing request needs the X-JobsAlert-Token header. GET /api/session
  hands the token only to clients on this machine; set JOBSALERT_API_TOKEN to use a
  fixed token (required when listening on another address).
- Host headers are checked to block DNS-rebinding, and CORS only admits the local
  Vite dev server.
"""

from __future__ import annotations
import ipaddress
import os
import secrets
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from src import paths
from src.collectors.custom import add_custom_job, custom_job_id, delete_custom_job, load_custom_jobs
from src.config import AppConfig, list_profiles, load_config, load_profile, save_config, save_profile, validate_profile_name
from src.deduplication import StateManager
from src.income_opportunities.collectors.custom import (
    add_custom_income_opportunity,
    custom_income_id,
    delete_custom_income_opportunity,
    load_custom_income,
)
from src.income_opportunities.config import OnlineIncomeConfig
from src.income_opportunities.deduplication import IncomeStateManager
from src.income_opportunities.models import ScoredOpportunity
from src.income_opportunities.pipeline import IncomeOpportunityPipeline, get_income_run_logs
from src.notifier.email_service import EmailNotifier, preview_file
from src.pipeline import JobPipeline, get_run_logs
from src.storage import StateFileError, read_json, write_json_atomic

MAX_SAVED_RESULTS = 500


def _csv_env(name: str, default: List[str]) -> List[str]:
    value = os.getenv(name)
    return [item.strip() for item in value.split(",") if item.strip()] if value else default


def _is_loopback(host: str) -> bool:
    if host in ("localhost",):
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


API_TOKEN = os.getenv("JOBSALERT_API_TOKEN") or secrets.token_urlsafe(32)
_bound_publicly = not _is_loopback(os.getenv("JOBSALERT_BIND_HOST", "127.0.0.1"))
ALLOWED_HOSTS = _csv_env("JOBSALERT_ALLOWED_HOSTS", ["*"] if _bound_publicly else ["localhost", "127.0.0.1", "::1", "[::1]"])
CORS_ORIGINS = _csv_env("JOBSALERT_CORS_ORIGINS", ["http://localhost:3000", "http://127.0.0.1:3000"])

app = FastAPI(
    title="JobsAlert Control Panel API",
    description="Job and online income alert scout",
    version="2.0.0",
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-JobsAlert-Token"],
)


@app.exception_handler(StateFileError)
async def state_file_error(_request: Request, exc: StateFileError):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


def require_token(x_jobsalert_token: Optional[str] = Header(default=None)) -> None:
    if not x_jobsalert_token or not secrets.compare_digest(x_jobsalert_token, API_TOKEN):
        raise HTTPException(status_code=401, detail="Missing or invalid API token. Reload the dashboard to get a new one.")


Protected = [Depends(require_token)]


class RunGuard:
    """Allows one pipeline run (job or income) at a time; both write the same state files."""

    def __init__(self):
        self.active: Optional[str] = None

    def start(self, name: str) -> None:
        if self.active:
            raise HTTPException(status_code=429, detail=f"A {self.active} run is already in progress. Try again when it finishes.")
        self.active = name

    def finish(self) -> None:
        self.active = None


RUN_GUARD = RunGuard()
_latest: Dict[str, Optional[dict]] = {"jobs": None, "income": None}


def _results_file():
    return paths.data_file(paths.LAST_RESULTS)


def _save_results(kind: str, summary: dict, items: List[dict]) -> None:
    items = sorted(items, key=lambda x: x.get("score", 0.0), reverse=True)[:MAX_SAVED_RESULTS]
    _latest[kind] = {"summary": summary, "items": items}
    stored = read_json(_results_file(), {})
    stored = stored if isinstance(stored, dict) else {}
    stored[kind] = _latest[kind]
    write_json_atomic(_results_file(), stored)


def _load_results(kind: str) -> dict:
    if _latest[kind] is None:
        stored = read_json(_results_file(), {})
        _latest[kind] = (stored.get(kind) if isinstance(stored, dict) else None) or {"summary": None, "items": []}
    return _latest[kind]


def _deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """Nested dicts merge; everything else (lists included) is replaced."""
    merged = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _validation_detail(exc: ValidationError) -> str:
    first = exc.errors()[0]
    return f"{'.'.join(str(p) for p in first['loc'])}: {first['msg']}"


# ==============================================================================
# REQUEST MODELS
# ==============================================================================

class RunRequest(BaseModel):
    dry_run: bool = True
    send_email: bool = False
    force_all: bool = False
    profile: Optional[str] = None


class ProfileActionRequest(BaseModel):
    profile_name: str


class CustomJobRequest(BaseModel):
    title: str
    company: str
    location: str = "Remote"
    url: str = ""
    description: str = ""
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: str = "USD"
    salary_period: str = "yearly"


class CustomIncomeRequest(BaseModel):
    title: str
    organization: str
    category: str = "general_flexible"
    url: str = ""
    application_url: str = ""
    location_eligibility: str = "Worldwide"
    description: str = ""
    estimated_pay_min: Optional[float] = None
    estimated_pay_max: Optional[float] = None
    pay_rate_display: Optional[str] = None
    pay_currency: str = "USD"
    opportunity_type: str = "hourly"


class DismissIncomeRequest(BaseModel):
    fingerprint: str


# ==============================================================================
# SESSION, HEALTH & CONFIG
# ==============================================================================

@app.get("/api/session")
async def session(request: Request):
    """Hands the API token to clients on this machine; others must enter it."""
    client = request.client.host if request.client else ""
    if not _is_loopback(client):
        raise HTTPException(status_code=403, detail="Enter the API token (JOBSALERT_API_TOKEN) to use the control panel remotely.")
    return {"token": API_TOKEN}


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "JobsAlert Intelligence", "version": app.version, "run_in_progress": RUN_GUARD.active}


@app.get("/api/config")
async def get_config():
    return load_config().model_dump(mode="json")


@app.post("/api/config", dependencies=Protected)
async def update_config(config_data: Dict[str, Any]):
    """Merges the submitted sections into the active configuration and saves it."""
    try:
        validated = AppConfig(**_deep_merge(load_config().model_dump(mode="json"), config_data))
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {_validation_detail(exc)}")
    save_config(validated)
    return {"status": "success", "message": "Configuration saved", "config": load_config().model_dump(mode="json")}


@app.get("/api/profiles")
async def get_profiles():
    return {"profiles": list_profiles()}


@app.post("/api/profiles/load", dependencies=Protected)
async def load_preset_profile(req: ProfileActionRequest):
    """Makes a saved profile the active configuration."""
    try:
        profile_config = load_profile(validate_profile_name(req.profile_name))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    save_config(profile_config)
    return {"status": "success", "message": f"Profile '{req.profile_name}' activated", "config": load_config().model_dump(mode="json")}


@app.post("/api/profiles/save", dependencies=Protected)
async def save_custom_profile(req: ProfileActionRequest):
    """Saves the active configuration as a named profile."""
    try:
        name = validate_profile_name(req.profile_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    save_profile(load_config(), name)
    return {"status": "success", "message": f"Profile '{name}' saved"}


# ==============================================================================
# RUNS & RESULTS
# ==============================================================================

def _profile_config(profile: Optional[str]) -> AppConfig:
    if not profile:
        return load_config()
    try:
        return load_profile(validate_profile_name(profile))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/run", dependencies=Protected)
async def trigger_run(req: RunRequest):
    """Runs the job pipeline (and the income stage when enabled) on demand."""
    RUN_GUARD.start("job")
    try:
        config = _profile_config(req.profile)
        pipeline = JobPipeline(config=config)
        summary, scored = await pipeline.execute(
            dry_run=req.dry_run, send_email=req.send_email and not req.dry_run, force_all=req.force_all, trigger="api",
        )
    finally:
        RUN_GUARD.finish()

    summary_data = summary.model_dump(mode="json")
    jobs = [s.model_dump(mode="json") for s in scored]
    _save_results("jobs", summary_data, jobs)
    if pipeline.latest_income_summary is not None:
        income = [s.model_dump(mode="json") for s in pipeline.latest_income_opportunities]
        _save_results("income", pipeline.latest_income_summary.model_dump(mode="json"), income)
    top_income = [s.model_dump(mode="json") for s in pipeline.latest_income_opportunities if s.score >= 7.0][:10]
    return {
        "status": "completed",
        "summary": summary_data,
        "jobs_count": len(jobs),
        "income_count": len(pipeline.latest_income_opportunities),
        "top_matches": [j for j in sorted(jobs, key=lambda j: j["score"], reverse=True) if j["score"] >= 7.0][:10],
        "top_income_matches": top_income,
    }


@app.get("/api/jobs")
async def get_latest_jobs(min_score: float = 0.0, limit: int = 50):
    """Scored jobs from the most recent run (kept across server restarts)."""
    results = _load_results("jobs")
    filtered = [j for j in results["items"] if j.get("score", 0.0) >= min_score]
    return {"total": len(filtered), "summary": results["summary"], "jobs": filtered[: max(0, limit)]}


@app.get("/api/preview-email", response_class=HTMLResponse)
async def preview_email_html():
    """The last rendered digest, or an empty digest when nothing has run yet."""
    target = preview_file()
    if target.exists():
        return HTMLResponse(content=target.read_text(encoding="utf-8"))
    _subject, html_content, _text = EmailNotifier().render_digest([], load_config())
    return HTMLResponse(content=html_content)


@app.get("/api/logs")
async def get_execution_logs():
    return {"logs": get_run_logs()}


def _recent(records: Dict[str, dict], limit: int = 30) -> List[dict]:
    return sorted(records.values(), key=lambda r: r.get("last_seen_at") or r.get("last_seen") or "", reverse=True)[:limit]


@app.get("/api/seen-jobs")
async def get_seen_jobs_summary():
    state = StateManager()
    return {"total_seen": len(state), "total_alerted": sum(1 for r in state.records.values() if r.get("alerted")),
            "sample": _recent(state.records)}


@app.post("/api/seen-jobs/clear", dependencies=Protected)
async def clear_seen_jobs():
    """Forgets every processed job (a timestamped backup of the file is kept)."""
    return {"status": "success", "cleared_count": StateManager().clear()}


# ==============================================================================
# CUSTOM JOBS
# ==============================================================================

@app.get("/api/jobs/custom")
async def list_custom_jobs():
    return {"custom_jobs": [{**entry, "id": custom_job_id(entry)} for entry in load_custom_jobs()]}


@app.post("/api/jobs/custom", dependencies=Protected)
async def create_custom_job(req: CustomJobRequest):
    entry = add_custom_job(**req.model_dump())
    return {"status": "success", "message": "Custom job added", "job": entry}


@app.delete("/api/jobs/custom/{entry_id}", dependencies=Protected)
async def remove_custom_job(entry_id: str):
    deleted = delete_custom_job(entry_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="Custom job not found")
    return {"status": "success", "deleted": deleted}


# ==============================================================================
# ONLINE INCOME
# ==============================================================================

@app.get("/api/income/config")
async def get_income_config():
    return load_config().online_income.model_dump(mode="json")


@app.post("/api/income/config", dependencies=Protected)
async def update_income_config(income_cfg_data: Dict[str, Any]):
    config = load_config()
    try:
        config.online_income = OnlineIncomeConfig(**_deep_merge(config.online_income.model_dump(mode="json"), income_cfg_data))
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid online income configuration: {_validation_detail(exc)}")
    save_config(config)
    return {"status": "success", "message": "Online income settings saved", "config": config.online_income.model_dump(mode="json")}


@app.post("/api/income/run", dependencies=Protected)
async def trigger_income_run(req: RunRequest):
    """Runs a standalone online income scan."""
    RUN_GUARD.start("income")
    try:
        config = _profile_config(req.profile)
        pipeline = IncomeOpportunityPipeline(
            config=config.online_income,
            fx_rates=config.fx_rates_to_usd,
            link_config=config.link_verification,
            retention_days=config.state.retention_days,
        )
        send = req.send_email and not req.dry_run
        summary, scored = await pipeline.execute(
            dry_run=req.dry_run, send_email=send, force_all=req.force_all,
            recipient_email=config.delivery.recipient_email, email_provider=config.delivery.email_provider,
            from_email=config.delivery.from_email, trigger="api",
        )
    finally:
        RUN_GUARD.finish()

    summary_data = summary.model_dump(mode="json")
    items = [s.model_dump(mode="json") for s in scored]
    _save_results("income", summary_data, items)
    return {
        "status": "completed",
        "summary": summary_data,
        "opportunities_count": len(items),
        "top_matches": [s for s in sorted(items, key=lambda s: s["score"], reverse=True) if s["score"] >= 7.0][:10],
    }


@app.get("/api/income/opportunities")
async def get_latest_income_opportunities(
    min_score: float = 0.0,
    min_quality: float = 0.0,
    min_side_job_fit: float = 0.0,
    category: Optional[str] = None,
    source_trust_tier: Optional[str] = None,
    include_rejected: bool = False,
    limit: int = 50,
):
    """Scored income opportunities from the most recent run, filtered."""
    filtered = []
    for item in _load_results("income")["items"]:
        breakdown, opp = item.get("breakdown", {}), item.get("opportunity", {})
        if not include_rejected and item.get("action") == "discard":
            continue
        if item.get("score", 0.0) < min_score:
            continue
        if (breakdown.get("quality_score") or opp.get("quality_score") or 0.0) < min_quality:
            continue
        if (breakdown.get("side_job_fit_score") or opp.get("side_job_fit_score") or 0.0) < min_side_job_fit:
            continue
        if category and category.strip().lower() not in str(opp.get("category", "")).lower():
            continue
        if source_trust_tier and source_trust_tier.strip().lower() not in str(opp.get("source_trust_tier", "")).lower():
            continue
        filtered.append(item)
    filtered.sort(key=lambda x: (x.get("score", 0.0), x.get("breakdown", {}).get("quality_score", 0.0)), reverse=True)
    return {"total": len(filtered), "opportunities": filtered[: max(0, limit)]}


@app.get("/api/income/custom")
async def list_custom_income_opportunities():
    return {"custom_opportunities": [{**entry, "id": custom_income_id(entry)} for entry in load_custom_income()]}


@app.post("/api/income/custom", dependencies=Protected)
async def create_custom_income_opportunity(req: CustomIncomeRequest):
    entry = add_custom_income_opportunity(**req.model_dump())
    return {"status": "success", "message": "Custom income opportunity added", "opportunity": entry}


@app.delete("/api/income/custom/{entry_id}", dependencies=Protected)
async def remove_custom_income_opportunity(entry_id: str):
    deleted = delete_custom_income_opportunity(entry_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="Custom income opportunity not found")
    return {"status": "success", "deleted": deleted}


@app.post("/api/income/dismiss", dependencies=Protected)
async def dismiss_income_opportunity(req: DismissIncomeRequest):
    """Hides an opportunity from future digests."""
    IncomeStateManager().dismiss_opportunity(req.fingerprint)
    return {"status": "success", "fingerprint": req.fingerprint, "dismissed": True}


@app.get("/api/income/preview-email", response_class=HTMLResponse)
async def preview_income_email_html():
    """Renders the income digest from the latest results. Never starts a scan."""
    config = load_config()
    items = [ScoredOpportunity.model_validate(i) for i in _load_results("income")["items"]]
    selected = [s for s in items if s.action in ("instant", "digest")][: config.online_income.max_digest_items or 5]
    _subject, html_content, _text = EmailNotifier().render_income_digest(
        selected or items[:5], config.online_income.candidate_name, config.delivery.recipient_email,
        config.online_income.instant_alert_score, config.schedule.timezone,
    )
    return HTMLResponse(content=html_content)


@app.get("/api/income/logs")
async def get_income_logs():
    return {"logs": get_income_run_logs()}


@app.get("/api/income/seen")
async def get_seen_income_summary():
    state = IncomeStateManager()
    return {"total_seen": len(state), "sample": _recent(state.records)}


@app.post("/api/income/seen/clear", dependencies=Protected)
async def clear_seen_income():
    """Forgets every processed income opportunity (a timestamped backup is kept)."""
    return {"status": "success", "cleared_count": IncomeStateManager().clear()}


# ==============================================================================
# DASHBOARD
# ==============================================================================

DASHBOARD_MISSING_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>JobsAlert control panel</title>
<style>body{font:16px/1.5 system-ui,sans-serif;max-width:40rem;margin:3rem auto;padding:0 1rem;color:#16202a}
code{background:#eef1f4;padding:.1rem .35rem;border-radius:4px}pre{background:#eef1f4;padding:1rem;border-radius:8px}</style>
</head><body><h1>The dashboard hasn't been built yet</h1>
<p>The API is running. Build the React control panel once, then reload this page:</p>
<pre>cd web
npm install
npm run build</pre>
<p>While developing, <code>npm run dev</code> serves it at <code>http://localhost:3000</code> with live reload.
The API reference is at <a href="/docs">/docs</a>.</p></body></html>"""

if (paths.web_dist_dir() / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(paths.web_dist_dir()), html=True), name="dashboard")
else:
    @app.get("/", response_class=HTMLResponse)
    async def dashboard_missing():
        return HTMLResponse(content=DASHBOARD_MISSING_HTML)
