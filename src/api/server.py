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


class RunRequest(BaseModel):
    dry_run: bool = True
    send_email: bool = False
    force_all: bool = True
    profile: Optional[str] = None


class ProfileActionRequest(BaseModel):
    profile_name: str


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


# Serve static build of React UI if available, otherwise serve embedded zero-dependency UI
WEB_DIST_DIR = Path(__file__).resolve().parent.parent.parent / "web" / "dist"

from src.api.embedded_ui import EMBEDDED_DASHBOARD_HTML

if WEB_DIST_DIR.exists() and (WEB_DIST_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIST_DIR), html=True), name="static")
else:
    @app.get("/", response_class=HTMLResponse)
    async def serve_embedded_ui():
        return HTMLResponse(content=EMBEDDED_DASHBOARD_HTML, status_code=200)

