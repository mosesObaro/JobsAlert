"""
Source yield monitoring.

The point is to separate "this source is fine and had nothing new" from "this
source answered 200 with an empty body because its markup changed". Both look
healthy, and only history tells them apart. A note must never become a failure:
a quiet day is a legitimate outcome.
"""

from src.models import CrawlerHealth
from src.monitoring import (
    DROP_RATIO,
    MIN_RUNS_FOR_COMPARISON,
    annotate,
    recent_yields,
    yield_note,
)


def run_log(timestamp: str, **counts) -> dict:
    return {
        "timestamp": timestamp,
        "source_health": [
            {"source_name": name, "status": "healthy", "jobs_found": found}
            for name, found in counts.items()
        ],
    }


def history(*counts) -> dict:
    return {"linkedin": list(counts)}


# --- reading history ----------------------------------------------------------

def test_recent_yields_reads_counts_newest_first():
    logs = [
        run_log("2026-11-17T07:00:00Z", linkedin=40),
        run_log("2026-11-19T07:00:00Z", linkedin=70),
        run_log("2026-11-18T07:00:00Z", linkedin=60),
    ]
    assert recent_yields(logs)["linkedin"] == [70, 60, 40]


def test_recent_yields_ignores_disabled_sources():
    logs = [{
        "timestamp": "2026-11-19T07:00:00Z",
        "source_health": [
            {"source_name": "twitter", "status": "disabled", "jobs_found": 0},
            {"source_name": "linkedin", "status": "healthy", "jobs_found": 50},
        ],
    }]
    found = recent_yields(logs)
    assert "twitter" not in found
    assert found["linkedin"] == [50]


def test_recent_yields_reads_income_counts_too():
    logs = [{
        "timestamp": "2026-11-19T07:00:00Z",
        "source_health": [{"source_name": "ai_evaluation", "status": "healthy", "opportunities_found": 12}],
    }]
    assert recent_yields(logs)["ai_evaluation"] == [12]


def test_malformed_history_entries_are_skipped():
    logs = [{"timestamp": "x", "source_health": ["not a dict", {"jobs_found": 5}]}, {"timestamp": "y"}]
    assert recent_yields(logs) == {}


# --- when a note is warranted -------------------------------------------------

def test_a_collapse_to_zero_is_reported():
    note = yield_note("linkedin", 0, history(70, 60, 65))
    assert note is not None
    assert "returned nothing" in note
    assert "65" in note or "60" in note


def test_a_severe_drop_is_reported():
    note = yield_note("linkedin", 5, history(70, 60, 65))
    assert note is not None
    assert "far below" in note


def test_a_normal_run_is_not_reported():
    assert yield_note("linkedin", 60, history(70, 60, 65)) is None


def test_a_modest_dip_is_not_reported():
    """Sources fluctuate; only a collapse is worth a word."""
    assert yield_note("linkedin", int(65 * DROP_RATIO) + 5, history(70, 60, 65)) is None


def test_an_increase_is_never_reported():
    assert yield_note("linkedin", 500, history(70, 60, 65)) is None


# --- when a note would be noise -----------------------------------------------

def test_a_source_without_enough_history_is_left_alone():
    """A new source has no baseline, so nothing can be concluded from one run."""
    assert len(history(70, 60)["linkedin"]) < MIN_RUNS_FOR_COMPARISON
    assert yield_note("linkedin", 0, history(70, 60)) is None


def test_a_source_with_no_history_is_left_alone():
    assert yield_note("myjobmag", 0, {}) is None


def test_small_volume_sources_are_left_alone():
    """A source that normally returns 2 postings and now returns 0 proves
    nothing; a ratio on tiny numbers is noise."""
    assert yield_note("rss", 0, {"rss": [2, 1, 3]}) is None


# --- annotation ---------------------------------------------------------------

def test_annotate_sets_the_note_and_returns_it():
    reports = [CrawlerHealth(source_name="linkedin", status="healthy", jobs_found=0)]
    logs = [run_log(f"2026-11-1{n}T07:00:00Z", linkedin=70) for n in (6, 7, 8)]

    notes = annotate(reports, logs)

    assert len(notes) == 1
    assert reports[0].yield_note is not None
    assert "linkedin" in notes[0]


def test_annotate_never_changes_a_status():
    """A note is a diagnostic, not an outage."""
    reports = [CrawlerHealth(source_name="linkedin", status="healthy", jobs_found=0)]
    logs = [run_log(f"2026-11-1{n}T07:00:00Z", linkedin=70) for n in (6, 7, 8)]

    annotate(reports, logs)

    assert reports[0].status == "healthy"


def test_annotate_skips_disabled_sources():
    reports = [CrawlerHealth(source_name="twitter", status="disabled", jobs_found=0)]
    logs = [run_log(f"2026-11-1{n}T07:00:00Z", twitter=30) for n in (6, 7, 8)]

    assert annotate(reports, logs) == []
    assert reports[0].yield_note is None


def test_annotate_leaves_a_healthy_source_unmarked():
    reports = [CrawlerHealth(source_name="linkedin", status="healthy", jobs_found=68)]
    logs = [run_log(f"2026-11-1{n}T07:00:00Z", linkedin=70) for n in (6, 7, 8)]

    assert annotate(reports, logs) == []
    assert reports[0].yield_note is None


def test_annotate_handles_an_empty_history():
    reports = [CrawlerHealth(source_name="workable", status="healthy", jobs_found=0)]
    assert annotate(reports, []) == []


def test_annotate_works_on_income_health_reports():
    from src.income_opportunities.models import IncomeCollectorHealth

    reports = [IncomeCollectorHealth(source_name="ai_evaluation", status="healthy", opportunities_found=0)]
    logs = [{
        "timestamp": f"2026-11-1{n}T07:00:00Z",
        "source_health": [{"source_name": "ai_evaluation", "status": "healthy", "opportunities_found": 18}],
    } for n in (6, 7, 8)]

    notes = annotate(reports, logs)

    assert len(notes) == 1
    assert reports[0].yield_note is not None
    assert reports[0].status == "healthy"


# --- per-source new and duplicate counts --------------------------------------

def test_health_carries_new_and_duplicate_counts_by_default():
    """Additive fields: entries written before they existed simply lack them."""
    report = CrawlerHealth(source_name="myjobmag")
    assert report.new_postings == 0
    assert report.duplicate_postings == 0
    assert report.yield_note is None
