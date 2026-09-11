"""
JobsAlert FastAPI Backend Server.
Provides REST APIs for configuration management, pipeline execution, email preview, and telemetry.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.config import (
    AppConfig,
    DEFAULT_CONFIG_PATH,
    PROFILES_DIR,
    list_profiles,
    load_config,
    load_profile,
    save_config,
)
from src.deduplication import StateManager
from src.income_opportunities.collectors.custom import (
    CUSTOM_INCOME_FILE,
    add_custom_income_opportunity,
)
from src.income_opportunities.config import OnlineIncomeConfig
from src.income_opportunities.deduplication import IncomeStateManager
from src.income_opportunities.models import IncomeRunSummary, ScoredOpportunity
from src.income_opportunities.pipeline import (
    INCOME_RUN_LOGS_FILE,
    IncomeOpportunityPipeline,
    get_income_run_logs,
)
from src.models import RunSummary, ScoredJob
from src.notifier.email_service import PREVIEW_FILE, EmailNotifier
from src.pipeline import JobPipeline, get_run_logs

app = FastAPI(
    title="JobsAlert Control Panel API",
    description="Autonomous Career Intelligence & Opportunity Scout API",
    version="1.0.0",
)

# Enable CORS for local Vite dev server and web dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory pipeline cache
active_pipeline_running = False
latest_run_summary: Optional[Dict[str, Any]] = None
latest_scored_jobs: List[Dict[str, Any]] = []

# Income scout pipeline cache
active_income_pipeline_running = False
latest_income_run_summary: Optional[Dict[str, Any]] = None
latest_scored_income_opps: List[Dict[str, Any]] = []


class RunRequest(BaseModel):
    dry_run: bool = True
    send_email: bool = False
    force_all: bool = True
    profile: Optional[str] = None


class IncomeRunRequest(BaseModel):
    dry_run: bool = True
    send_email: bool = False
    force_all: bool = True
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
    opportunity_type: str = "hourly"


class DismissIncomeRequest(BaseModel):
    fingerprint: str



@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "JobsAlert Intelligence",
        "version": "1.0.0",
        "active_config": str(DEFAULT_CONFIG_PATH.name),
    }


@app.get("/api/config")
async def get_config():
    """Returns the current active configuration."""
    config = load_config()
    return config.model_dump()


@app.post("/api/config")
async def update_config(config_data: Dict[str, Any]):
    """Validates and persists updated configuration to config/jobs.yaml."""
    try:
        validated_config = AppConfig(**config_data)
        save_config(validated_config)
        return {"status": "success", "message": "Configuration updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")


@app.get("/api/profiles")
async def get_profiles():
    """Lists all available search profile presets."""
    profiles = list_profiles()
    return {"profiles": profiles}


@app.post("/api/profiles/load")
async def load_preset_profile(req: ProfileActionRequest):
    """Loads a preset profile and writes it as the active configuration."""
    try:
        profile_config = load_profile(req.profile_name)
        save_config(profile_config)
        return {
            "status": "success",
            "message": f"Profile '{req.profile_name}' activated",
            "config": profile_config.model_dump(),
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/profiles/save")
async def save_custom_profile(req: ProfileActionRequest):
    """Saves the current configuration as a new profile preset."""
    try:
        config = load_config()
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        target_path = PROFILES_DIR / f"{req.profile_name}.yaml"
        save_config(config, target_path)
        return {"status": "success", "message": f"Profile '{req.profile_name}' saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/run")
async def trigger_run(req: RunRequest):
    """Executes the crawler and scoring engine on-demand."""
    global active_pipeline_running, latest_run_summary, latest_scored_jobs

    if active_pipeline_running:
        raise HTTPException(status_code=429, detail="Pipeline is already executing. Please wait.")

    active_pipeline_running = True
    try:
        config = load_profile(req.profile) if req.profile else load_config()
        pipeline = JobPipeline(config=config)

        summary, scored = await pipeline.execute(
            dry_run=req.dry_run,
            send_email=req.send_email,
            force_all=req.force_all,
        )

        latest_run_summary = summary.model_dump(mode="json")
        latest_scored_jobs = [s.model_dump(mode="json") for s in scored]

        return {
            "status": "completed",
            "summary": latest_run_summary,
            "jobs_count": len(scored),
            "top_matches": [s for s in latest_scored_jobs if s["score"] >= 7.0][:10],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {str(e)}")
    finally:
        active_pipeline_running = False


@app.get("/api/jobs")
async def get_latest_jobs(min_score: float = 0.0, limit: int = 50):
    """Returns the latest scored jobs from the most recent run."""
    global latest_scored_jobs
    filtered = [j for j in latest_scored_jobs if j["score"] >= min_score]
    # Sort descending by score
    filtered.sort(key=lambda x: x["score"], reverse=True)
    return {"total": len(filtered), "jobs": filtered[:limit]}


from src.collectors.custom import add_custom_job, CUSTOM_JOBS_FILE
import json


@app.post("/api/jobs/custom")
async def create_custom_job(req: CustomJobRequest):
    """Allows candidates to manually input an ad hoc job for scoring and alert inclusion."""
    job_entry = add_custom_job(
        title=req.title,
        company=req.company,
        location=req.location,
        url=req.url,
        description=req.description,
        salary_min=req.salary_min,
        salary_max=req.salary_max,
    )
    return {"status": "success", "message": "Custom job added successfully", "job": job_entry}


@app.get("/api/jobs/custom")
async def list_custom_jobs():
    """Lists all manually entered custom jobs."""
    if not CUSTOM_JOBS_FILE.exists():
        return {"custom_jobs": []}
    try:
        with open(CUSTOM_JOBS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {"custom_jobs": data}
    except Exception:
        return {"custom_jobs": []}


@app.delete("/api/jobs/custom/{index}")
async def delete_custom_job(index: int):
    """Removes a custom job by index."""
    if not CUSTOM_JOBS_FILE.exists():
        raise HTTPException(status_code=404, detail="No custom jobs found")
    try:
        with open(CUSTOM_JOBS_FILE, "r", encoding="utf-8") as f:
            jobs = json.load(f)
        if 0 <= index < len(jobs):
            deleted = jobs.pop(index)
            with open(CUSTOM_JOBS_FILE, "w", encoding="utf-8") as f:
                json.dump(jobs, f, indent=2)
            return {"status": "success", "deleted": deleted}
        raise HTTPException(status_code=404, detail="Index out of range")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))




@app.get("/api/preview-email", response_class=HTMLResponse)
async def preview_email_html():
    """Renders and returns the HTML email digest for immediate in-browser inspection."""
    global latest_scored_jobs
    if PREVIEW_FILE.exists():
        with open(PREVIEW_FILE, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)

    # If no preview exists yet, generate sample or empty
    config = load_config()
    notifier = EmailNotifier()
    subject, html_content, _ = notifier.render_digest([], config)
    return HTMLResponse(content=html_content, status_code=200)


@app.get("/api/logs")
async def get_execution_logs():
    """Returns past execution logs and health status."""
    logs = get_run_logs()
    return {"logs": logs}


@app.get("/api/seen-jobs")
async def get_seen_jobs_summary():
    """Returns telemetry on deduplication cache."""
    state = StateManager()
    count = state.get_seen_count()
    sample = list(state.seen_data.values())[:30]
    return {"total_seen": count, "sample": sample}


@app.post("/api/seen-jobs/clear")
async def clear_seen_jobs():
    """Clears the seen jobs database to allow full re-crawling."""
    state = StateManager()
    count = state.get_seen_count()
    state.seen_data = {}
    state.save()
    return {"status": "success", "cleared_count": count}


# ==============================================================================
# ONLINE INCOME OPPORTUNITIES ENDPOINTS
# ==============================================================================

@app.get("/api/income/config")
async def get_income_config():
    """Returns the online income scout configuration."""
    config = load_config()
    return config.online_income.model_dump()


@app.post("/api/income/config")
async def update_income_config(income_cfg_data: Dict[str, Any]):
    """Updates and validates online income scout configuration."""
    try:
        config = load_config()
        config.online_income = OnlineIncomeConfig(**income_cfg_data)
        save_config(config)
        return {"status": "success", "message": "Online Income configuration updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid online income configuration: {str(e)}")


@app.post("/api/income/run")
async def trigger_income_run(req: IncomeRunRequest):
    """Executes the online income opportunities discovery and evaluation pipeline on-demand."""
    global active_income_pipeline_running, latest_income_run_summary, latest_scored_income_opps

    if active_income_pipeline_running:
        raise HTTPException(status_code=429, detail="Income scout pipeline is already executing. Please wait.")

    active_income_pipeline_running = True
    try:
        config = load_profile(req.profile) if req.profile else load_config()
        pipeline = IncomeOpportunityPipeline(config=config.online_income)

        summary, scored = await pipeline.execute(
            dry_run=req.dry_run,
            send_email=req.send_email,
            force_all=req.force_all,
            recipient_email=config.delivery.recipient_email,
            email_provider=config.delivery.email_provider,
            from_email=config.delivery.from_email,
        )

        latest_income_run_summary = summary.model_dump(mode="json")
        latest_scored_income_opps = [s.model_dump(mode="json") for s in scored]

        return {
            "status": "completed",
            "summary": latest_income_run_summary,
            "opportunities_count": len(scored),
            "top_matches": [s for s in latest_scored_income_opps if s["score"] >= 7.0][:10],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Income scout execution failed: {str(e)}")
    finally:
        active_income_pipeline_running = False


@app.get("/api/income/opportunities")
async def get_latest_income_opportunities(min_score: float = 0.0, category: Optional[str] = None, limit: int = 50):
    """Returns the latest scored online income opportunities."""
    global latest_scored_income_opps
    filtered = [o for o in latest_scored_income_opps if o["score"] >= min_score]
    if category and category.strip():
        norm_c = category.strip().lower()
        filtered = [o for o in filtered if norm_c in o["opportunity"]["category"].lower()]
    filtered.sort(key=lambda x: x["score"], reverse=True)
    return {"total": len(filtered), "opportunities": filtered[:limit]}


@app.post("/api/income/custom")
async def create_custom_income_opportunity(req: CustomIncomeRequest):
    """Allows manual creation of an online income opportunity."""
    entry = add_custom_income_opportunity(
        title=req.title,
        organization=req.organization,
        category=req.category,
        url=req.url,
        application_url=req.application_url,
        location_eligibility=req.location_eligibility,
        description=req.description,
        estimated_pay_min=req.estimated_pay_min,
        estimated_pay_max=req.estimated_pay_max,
        pay_rate_display=req.pay_rate_display,
        opportunity_type=req.opportunity_type,
    )
    return {"status": "success", "message": "Custom income opportunity added", "opportunity": entry}


@app.get("/api/income/custom")
async def list_custom_income_opportunities():
    """Lists all manually added custom income opportunities."""
    if not CUSTOM_INCOME_FILE.exists():
        return {"custom_opportunities": []}
    try:
        with open(CUSTOM_INCOME_FILE, "r", encoding="utf-8") as f:
            return {"custom_opportunities": json.load(f)}
    except Exception:
        return {"custom_opportunities": []}


@app.delete("/api/income/custom/{index}")
async def delete_custom_income_opportunity(index: int):
    """Removes a custom income opportunity by index."""
    if not CUSTOM_INCOME_FILE.exists():
        raise HTTPException(status_code=404, detail="No custom income opportunities found")
    try:
        with open(CUSTOM_INCOME_FILE, "r", encoding="utf-8") as f:
            items = json.load(f)
        if 0 <= index < len(items):
            deleted = items.pop(index)
            with open(CUSTOM_INCOME_FILE, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2)
            return {"status": "success", "deleted": deleted}
        raise HTTPException(status_code=404, detail="Index out of range")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/income/dismiss")
async def dismiss_income_opportunity(req: DismissIncomeRequest):
    """Marks an opportunity as dismissed so it will not reappear in future digests."""
    state = IncomeStateManager()
    state.dismiss_opportunity(req.fingerprint)
    return {"status": "success", "fingerprint": req.fingerprint, "dismissed": True}


@app.get("/api/income/preview-email", response_class=HTMLResponse)
async def preview_income_email_html():
    """Renders HTML email preview for online income opportunities."""
    global latest_scored_income_opps
    config = load_config()
    notifier = EmailNotifier()
    preview_opps = latest_scored_income_opps or []
    # If no run happened yet, run lightweight collection to preview
    if not preview_opps:
        pipeline = IncomeOpportunityPipeline(config=config.online_income)
        _, scored = await pipeline.execute(dry_run=True, send_email=False, force_all=True)
        preview_opps = scored

    subject, html_content, _ = notifier.render_income_digest(
        preview_opps,
        config.online_income.candidate_name,
        config.delivery.recipient_email
    )
    return HTMLResponse(content=html_content, status_code=200)


@app.get("/api/income/logs")
async def get_income_logs():
    """Returns past execution logs and health telemetry for online income discovery."""
    logs = get_income_run_logs()
    return {"logs": logs}


@app.get("/api/income/seen")
async def get_seen_income_summary():
    """Returns seen state telemetry for online income opportunities."""
    state = IncomeStateManager()
    records = state.get_all_records()
    return {"total_seen": len(records), "sample": list(records.values())[:30]}


@app.post("/api/income/seen/clear")
async def clear_seen_income():
    """Clears the seen income opportunities database."""
    state = IncomeStateManager()
    count = len(state.get_all_records())
    state.clear()
    return {"status": "success", "cleared_count": count}


# Serve static build of React UI if available, otherwise serve embedded zero-dependency UI
WEB_DIST_DIR = Path(__file__).resolve().parent.parent.parent / "web" / "dist"

from src.api.embedded_ui import EMBEDDED_DASHBOARD_HTML

if WEB_DIST_DIR.exists() and (WEB_DIST_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIST_DIR), html=True), name="static")
else:
    @app.get("/", response_class=HTMLResponse)
    async def serve_embedded_ui():
        return HTMLResponse(content=EMBEDDED_DASHBOARD_HTML, status_code=200)

