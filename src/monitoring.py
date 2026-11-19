"""
Source yield monitoring.

Health status alone cannot tell "this source is fine and had nothing new" apart
from "this source answered 200 with an empty body because its markup changed".
Both look healthy. What separates them is history: a source that has returned
hundreds of postings on every recent run and now returns none has almost
certainly broken, even though nothing errored.

This compares each source's count against its own recent runs, recorded in
data/run_logs.json, and annotates the health report. It never changes a status:
a note is a diagnostic for the log and the dashboard, not a failure, because a
quiet day is a legitimate outcome and must not be reported as an outage.
"""

from __future__ import annotations
from statistics import median
from typing import Dict, List, Optional

# A source needs some history before a single quiet run means anything.
MIN_RUNS_FOR_COMPARISON = 3
# How far below its own median a source has to fall before it is worth saying.
DROP_RATIO = 0.4
# Below this, counts are too small for a ratio to be meaningful.
MIN_MEDIAN = 5


def recent_yields(run_logs: List[dict], limit: int = 10) -> Dict[str, List[int]]:
    """Per-source posting counts from the most recent runs, newest first."""
    history: Dict[str, List[int]] = {}
    for entry in sorted(run_logs, key=lambda e: str(e.get("timestamp", "")), reverse=True)[:limit]:
        for health in entry.get("source_health") or []:
            if not isinstance(health, dict):
                continue
            name = health.get("source_name")
            if not name or health.get("status") == "disabled":
                continue
            found = health.get("jobs_found")
            if found is None:
                found = health.get("opportunities_found", 0)
            history.setdefault(name, []).append(int(found or 0))
    return history


def yield_note(source: str, found: int, history: Dict[str, List[int]]) -> Optional[str]:
    """A sentence about an unusual drop, or None when nothing stands out."""
    counts = history.get(source) or []
    if len(counts) < MIN_RUNS_FOR_COMPARISON:
        return None
    typical = median(counts)
    if typical < MIN_MEDIAN or found >= typical * DROP_RATIO:
        return None
    if found == 0:
        return f"returned nothing, where recent runs averaged {typical:.0f} — worth checking the source"
    return f"returned {found}, far below its recent median of {typical:.0f}"


def annotate(health_reports: List, run_logs: List[dict]) -> List[str]:
    """Adds yield notes to health reports; returns the notes for logging."""
    history = recent_yields(run_logs)
    notes: List[str] = []
    for report in health_reports:
        if getattr(report, "status", "") == "disabled":
            continue
        found = getattr(report, "jobs_found", None)
        if found is None:
            found = getattr(report, "opportunities_found", 0)
        note = yield_note(report.source_name, int(found or 0), history)
        if note:
            report.yield_note = note
            notes.append(f"{report.source_name} {note}")
    return notes
