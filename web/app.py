"""
MysteryScraper — FastAPI web UI.

Run: uvicorn web.app:app --reload --port 8000
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web import data_access as da
from web.runs import run as scraper_run

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="MysteryScraper")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
# Expose the AI-adjusted display score to all templates.
templates.env.globals["display_score"] = da.display_score


def _shared(date: str | None) -> dict:
    dates = da.list_snapshot_dates()
    snapshot_date = date if date in dates else (dates[-1] if dates else None)
    return {
        "snapshot_dates": list(reversed(dates)),
        "snapshot_date": snapshot_date,
        "snapshot_summary": da.snapshot_summary(snapshot_date) if snapshot_date else None,
        "categories": ["All"] + da.jerrys_categories(),
        "sources": ["All"] + (da.competitor_sources(snapshot_date) if snapshot_date else []),
    }


# ---------- Pages ----------

@app.get("/", response_class=HTMLResponse)
def page_recommendations(
    request: Request,
    date: str | None = None,
    category: str = "All",
    source: str = "All",
    q: str = "",
):
    ctx = _shared(date)
    recs = da.ranked_recommendations(
        ctx["snapshot_date"], category=category, source=source, query=q
    ) if ctx["snapshot_date"] else []
    return templates.TemplateResponse(
        request,
        "recommendations.html",
        {
            "active_tab": "recommendations",
            "recs": recs,
            "category": category,
            "source": source,
            "q": q,
            **ctx,
        },
    )


@app.get("/inventory", response_class=HTMLResponse)
def page_inventory(request: Request, date: str | None = None, q: str = ""):
    ctx = _shared(date)
    grouped = da.jerrys_by_category(q)
    return templates.TemplateResponse(
        request,
        "inventory.html",
        {
            "active_tab": "inventory",
            "grouped": grouped,
            "q": q,
            **ctx,
        },
    )


@app.get("/competitors", response_class=HTMLResponse)
def page_competitors(
    request: Request,
    date: str | None = None,
    category: str = "All",
    source: str = "All",
    q: str = "",
):
    ctx = _shared(date)
    items = da.competitors_filtered(
        ctx["snapshot_date"], category=category, source=source, query=q
    ) if ctx["snapshot_date"] else []
    return templates.TemplateResponse(
        request,
        "competitors.html",
        {
            "active_tab": "competitors",
            "items": items,
            "category": category,
            "source": source,
            "q": q,
            **ctx,
        },
    )


@app.get("/changes", response_class=HTMLResponse)
def page_changes(request: Request, date: str | None = None):
    ctx = _shared(date)
    diff = da.load_diff(ctx["snapshot_date"]) if ctx["snapshot_date"] else None
    return templates.TemplateResponse(
        request,
        "changes.html",
        {
            "active_tab": "changes",
            "diff": diff,
            **ctx,
        },
    )


# ---------- HTMX partials ----------

@app.get("/partials/recommendations", response_class=HTMLResponse)
def partial_recommendations(
    request: Request,
    date: str | None = None,
    category: str = "All",
    source: str = "All",
    q: str = "",
):
    ctx = _shared(date)
    recs = da.ranked_recommendations(
        ctx["snapshot_date"], category=category, source=source, query=q
    ) if ctx["snapshot_date"] else []
    return templates.TemplateResponse(
        request, "partials/_card_grid.html", {"recs": recs},
    )


@app.get("/partials/competitors", response_class=HTMLResponse)
def partial_competitors(
    request: Request,
    date: str | None = None,
    category: str = "All",
    source: str = "All",
    q: str = "",
):
    ctx = _shared(date)
    items = da.competitors_filtered(
        ctx["snapshot_date"], category=category, source=source, query=q
    ) if ctx["snapshot_date"] else []
    return templates.TemplateResponse(
        request, "partials/_competitor_rows.html", {"items": items},
    )


@app.get("/partials/inventory", response_class=HTMLResponse)
def partial_inventory(request: Request, date: str | None = None, q: str = ""):
    return templates.TemplateResponse(
        request, "partials/_inventory_groups.html",
        {"grouped": da.jerrys_by_category(q)},
    )


@app.get("/detail/{rec_id}", response_class=HTMLResponse)
def detail(request: Request, rec_id: int, date: str | None = None):
    ctx = _shared(date)
    rec = da.get_recommendation(ctx["snapshot_date"], rec_id) if ctx["snapshot_date"] else None
    if not rec:
        return HTMLResponse("<div class='p-6 text-sm text-gray-500'>Not found.</div>")
    return templates.TemplateResponse(
        request,
        "partials/_detail.html",
        {
            "rec": rec,
            "breakdown": da.score_breakdown(rec),
            "similar": da.closest_jerrys(rec),
        },
    )


@app.get("/detail/close", response_class=HTMLResponse)
def detail_close():
    return HTMLResponse("")


# ---------- New run ----------

@app.get("/run", response_class=HTMLResponse)
def page_run(request: Request):
    return templates.TemplateResponse(
        request,
        "run.html",
        {"active_tab": "run", "status": scraper_run.status(), **_shared(None)},
    )


@app.post("/run/start", response_class=HTMLResponse)
def run_start(
    request: Request,
    budget: float = Form(5.0),
    max_results: int = Form(400),
):
    started = scraper_run.start(budget=budget, max_results=max_results)
    return templates.TemplateResponse(
        request,
        "partials/_run_status.html",
        {"status": scraper_run.status(), "just_started": started},
    )


@app.get("/run/status", response_class=HTMLResponse)
def run_status(request: Request):
    return templates.TemplateResponse(
        request, "partials/_run_status.html",
        {"status": scraper_run.status(), "just_started": False},
    )
