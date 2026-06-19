"""
Data access layer for the MysteryScraper web UI.

Thin wrappers around snapshot files and analyze.py. Route handlers stay tiny;
all I/O and scoring lives here so it's easy to test and swap.
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from analyze import find_gaps, rank_recommendations
import ai_backbone

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = ROOT / "data" / "snapshots"
DIFF_DIR = ROOT / "data" / "diffs"

STOPWORDS = {"the", "a", "an", "and", "or", "for", "with", "in", "of", "to"}


def list_snapshot_dates() -> list[str]:
    """Available snapshot dates, oldest first. Empty files (failed/no-op runs) are skipped."""
    if not SNAPSHOT_DIR.exists():
        return []
    dates: list[str] = []
    for p in sorted(SNAPSHOT_DIR.glob("*_competitors.json")):
        # Treat "[]" (2 bytes) or shorter as no data; a real snapshot is always larger.
        try:
            if p.stat().st_size < 10:
                continue
        except OSError:
            continue
        dates.append(p.stem.split("_")[0])
    return dates


def latest_date() -> str | None:
    dates = list_snapshot_dates()
    return dates[-1] if dates else None


@lru_cache(maxsize=16)
def load_competitors(date: str) -> list[dict]:
    path = SNAPSHOT_DIR / f"{date}_competitors.json"
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_jerrys() -> list[dict]:
    """Load Jerry's verified inventory from the most recent non-empty
    ``*_ace_catalog.json`` snapshot.

    Some scrape runs fail to capture the Ace catalog and write an empty file,
    so we walk newest-first and use the first run that actually has data.
    """
    if not SNAPSHOT_DIR.exists():
        return []

    for path in sorted(SNAPSHOT_DIR.glob("*_ace_catalog.json"), reverse=True):
        try:
            with open(path) as f:
                items = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if not items:
            continue
        rows: list[dict] = []
        for it in items:
            rows.append({
                "name": it.get("name", ""),
                "brand": it.get("brand", "") or "",
                "price": float(it["price"]) if it.get("price") is not None else 0.0,
                "qty": int(it["qty"]) if it.get("qty") is not None else 0,
                "category": it.get("category", ""),
            })
        return rows
    return []


@lru_cache(maxsize=16)
def load_diff(date: str) -> dict | None:
    path = DIFF_DIR / f"{date}_diff.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


@lru_cache(maxsize=16)
def _ranked_for(date: str) -> list[dict]:
    competitors = load_competitors(date)
    jerrys = load_jerrys()
    if not competitors or not jerrys:
        return []
    gaps = find_gaps(jerrys, competitors)
    ranked = rank_recommendations(gaps, max_items=200)
    # Substitute-aware AI re-ranking (no-op if OPENAI_API_KEY is unset).
    if ai_backbone.is_enabled():
        ranked = ai_backbone.assess_recommendations(ranked, jerrys)
    # Stamp a stable id on each rec so the slide-out can fetch one back.
    for i, r in enumerate(ranked):
        r["id"] = i
    return ranked


def ranked_recommendations(
    date: str,
    category: str | None = None,
    source: str | None = None,
    query: str | None = None,
    limit: int = 60,
) -> list[dict]:
    items = _ranked_for(date)
    if category and category != "All":
        items = [r for r in items if r.get("category") == category]
    if source and source != "All":
        items = [r for r in items if source in (r.get("sources") or [r.get("source")])]
    if query:
        q = query.lower().strip()
        items = [
            r for r in items
            if q in r.get("name", "").lower() or q in (r.get("brand") or "").lower()
        ]
    return items[:limit]


def get_recommendation(date: str, rec_id: int) -> dict | None:
    for r in _ranked_for(date):
        if r.get("id") == rec_id:
            return r
    return None


def closest_jerrys(rec: dict, limit: int = 5) -> list[dict]:
    """Return Jerry's products whose names share the most non-stopword tokens with rec."""
    name = (rec.get("name") or "").lower()
    rec_words = set(name.split()) - STOPWORDS
    scored: list[tuple[int, dict]] = []
    for p in load_jerrys():
        ace_words = set((p.get("name") or "").lower().split()) - STOPWORDS
        overlap = len(rec_words & ace_words)
        if overlap >= 2:
            scored.append((overlap, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:limit]]


def score_breakdown(rec: dict) -> list[tuple[str, int]]:
    """Mirror the scoring logic in analyze.rank_recommendations so the panel can show why."""
    items: list[tuple[str, int]] = []
    signal = rec.get("signal")
    if signal == "bestseller":
        items.append(("Bestseller badge at competitor", 5))
    elif signal == "high_rated":
        items.append(("High Rated badge at competitor", 4))
    if rec.get("rating") and rec["rating"] >= 4.0:
        items.append(("Customer rating 4.0+", 3))
    if rec.get("reviews"):
        if rec["reviews"] >= 100:
            items.append(("100+ customer reviews", 2))
        if rec["reviews"] >= 500:
            items.append(("500+ customer reviews", 2))
    if rec.get("price"):
        items.append(("Listed price available", 2))
    extra_sources = max(0, len(rec.get("sources") or [rec.get("source")]) - 1)
    if extra_sources:
        items.append((f"Carried by {extra_sources} extra competitor(s)", extra_sources * 3))
    adj = rec.get("ai_adjustment")
    if adj is not None:
        verdict = {
            "true_gap": "AI: true gap — Jerry's has no substitute",
            "brand_gap": "AI: brand gap — Jerry's has a similar item",
            "covered": "AI: covered — Jerry's already carries it",
        }.get(rec.get("ai_status"), "AI adjustment")
        items.append((verdict, adj))
    return items


def display_score(rec: dict) -> int:
    """The score to show: AI-adjusted final_score when present, else base score."""
    val = rec.get("final_score")
    return val if val is not None else rec.get("score", 0)


def invalidate_caches() -> None:
    """Drop cached snapshot/diff/jerrys reads. Call after a fresh scrape lands."""
    load_competitors.cache_clear()
    load_jerrys.cache_clear()
    load_diff.cache_clear()
    _ranked_for.cache_clear()


def jerrys_categories() -> list[str]:
    return sorted({p["category"] for p in load_jerrys() if p.get("category")})


def competitor_sources(date: str) -> list[str]:
    return sorted({p["source"] for p in load_competitors(date) if p.get("source")})


def jerrys_by_category(query: str | None = None) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    q = (query or "").lower().strip()
    for p in load_jerrys():
        if q and q not in p["name"].lower() and q not in p["brand"].lower():
            continue
        grouped.setdefault(p["category"] or "Uncategorized", []).append(p)
    return grouped


def competitors_filtered(
    date: str,
    category: str | None = None,
    source: str | None = None,
    query: str | None = None,
    limit: int = 500,
) -> list[dict]:
    items = load_competitors(date)
    if category and category != "All":
        items = [p for p in items if p.get("category") == category]
    if source and source != "All":
        items = [p for p in items if p.get("source") == source]
    if query:
        q = query.lower().strip()
        items = [
            p for p in items
            if q in (p.get("name") or "").lower()
            or q in (p.get("brand") or "").lower()
        ]
    return items[:limit]


def format_date(date: str | None) -> str:
    if not date:
        return ""
    try:
        return datetime.strptime(date, "%Y-%m-%d").strftime("%b %d, %Y")
    except ValueError:
        return date


def snapshot_summary(date: str) -> dict:
    competitors = load_competitors(date)
    jerrys = load_jerrys()
    return {
        "date": date,
        "date_display": format_date(date),
        "competitor_count": len(competitors),
        "jerrys_count": len(jerrys),
        "sources": competitor_sources(date),
    }
