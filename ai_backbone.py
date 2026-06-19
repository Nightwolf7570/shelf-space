"""
AI backbone — OpenAI-powered substitute detection for gap recommendations.

The rule-based gap analysis in analyze.py only matches on brand: if Jerry's
doesn't carry a competitor's *brand*, the product is flagged as a gap. That
over-counts. Example: "Scotch Tape" is a bestseller at competitors and Jerry's
doesn't carry the Scotch brand, so it shows up as a gap — but Jerry's already
stocks a generic packing tape that serves the same need. That's a brand-switch
opportunity, not a true assortment hole, and it shouldn't outrank products
Jerry's has no answer for at all.

This module asks an LLM, for each recommended gap, whether Jerry's catalog
already contains a functional substitute (same use, any brand). It classifies
each gap and adjusts the score accordingly:

    true_gap   Jerry's has nothing comparable          -> boost   (+6)
    brand_gap  Jerry's has a substitute, other brand   -> reduce  (-2)
    covered    Jerry's effectively already carries it  -> bury    (-8)

It degrades gracefully: if there's no API key, the SDK is missing, or a call
fails, the original recommendations are returned untouched.
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Score delta applied per substitute classification.
ADJUSTMENT = {
    "true_gap": 6,
    "brand_gap": -2,
    "covered": -8,
}

_SYSTEM_PROMPT = (
    "You are a retail merchandising analyst for an independent hardware store. "
    "You decide whether the store already stocks a functional substitute for a "
    "competitor's product. A substitute serves the same customer need and use "
    "case, even if the brand, size, or color differs (e.g. a generic packing "
    "tape substitutes for Scotch-brand packing tape; an interior latex paint "
    "substitutes for another interior latex paint). Different product types are "
    "NOT substitutes (painter's tape is not a substitute for wall paint).\n\n"
    "For each competitor product, classify it as:\n"
    "  - \"true_gap\": the store stocks nothing that serves this need.\n"
    "  - \"brand_gap\": the store stocks a substitute, but not this brand.\n"
    "  - \"covered\": the store effectively already carries this product.\n\n"
    "Return STRICT JSON only."
)


def is_enabled():
    """True if an OpenAI API key is configured."""
    return bool(OPENAI_API_KEY)


def _client():
    from openai import OpenAI  # imported lazily so the app runs without openai

    return OpenAI(api_key=OPENAI_API_KEY)


def _catalog_lines(ace_products, limit=400):
    """Compact 'brand | name | category' listing of Jerry's catalog."""
    lines = []
    for p in ace_products[:limit]:
        brand = (p.get("brand") or "").strip() or "?"
        name = (p.get("name") or "").strip()
        cat = (p.get("category") or "").strip()
        lines.append(f"- {brand} | {name} | {cat}")
    return "\n".join(lines)


def _assess_batch(client, model, catalog, batch):
    """Classify one batch of gap products. Returns {local_index: info_dict}."""
    gap_lines = []
    for i, r in enumerate(batch):
        brand = (r.get("brand") or "").strip()
        name = (r.get("name") or "").strip()
        cat = (r.get("category") or "").strip()
        label = f"{brand} {name}".strip()
        gap_lines.append(f"{i}. {label}  (category: {cat})")

    user_prompt = (
        "JERRY'S CURRENT CATALOG (brand | product | category):\n"
        f"{catalog}\n\n"
        "COMPETITOR GAP PRODUCTS to classify (index. product (category)):\n"
        + "\n".join(gap_lines)
        + "\n\nReturn JSON of this exact shape:\n"
        '{"items": [{"index": <int>, "status": "true_gap|brand_gap|covered", '
        '"closest_match": "<Jerry\'s product name or null>", '
        '"rationale": "<max 18 words>"}]}\n'
        "Include one item for every index above."
    )

    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    payload = json.loads(resp.choices[0].message.content)

    out = {}
    for item in payload.get("items", []):
        try:
            idx = int(item["index"])
        except (KeyError, ValueError, TypeError):
            continue
        if 0 <= idx < len(batch):
            out[idx] = item
    return out


def assess_recommendations(recs, ace_products, model=None, batch_size=25):
    """Enrich recommendations with AI substitute analysis and re-rank.

    Adds to each recommendation: ai_status, ai_substitute, ai_rationale,
    ai_adjustment, and final_score (base score + adjustment, floored at 0).
    Returns the list re-sorted by final_score descending. If AI is unavailable
    or a batch fails, affected items keep their original score unchanged.
    """
    if not recs or not is_enabled():
        return recs

    model = model or OPENAI_MODEL
    catalog = _catalog_lines(ace_products)

    try:
        client = _client()
    except Exception:
        return recs

    batches = [recs[s:s + batch_size] for s in range(0, len(recs), batch_size)]

    def _safe_assess(batch):
        try:
            return _assess_batch(client, model, catalog, batch)
        except Exception:
            return {}

    # Run the batch classifications concurrently — each is an independent
    # OpenAI call, so this turns N sequential round-trips into ~one.
    max_workers = min(8, len(batches)) or 1
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = list(pool.map(_safe_assess, batches))

    enriched = []
    for batch, result in zip(batches, results):
        for i, r in enumerate(batch):
            info = result.get(i)
            base = r.get("score", 0)
            if not info:
                # Batch failed or model skipped this item — leave score as-is.
                enriched.append({**r, "final_score": base})
                continue
            status = info.get("status", "true_gap")
            if status not in ADJUSTMENT:
                status = "true_gap"
            adj = ADJUSTMENT[status]
            enriched.append({
                **r,
                "ai_status": status,
                "ai_substitute": info.get("closest_match") or None,
                "ai_rationale": (info.get("rationale") or "").strip(),
                "ai_adjustment": adj,
                "final_score": max(0, base + adj),
            })

    enriched.sort(key=lambda x: x.get("final_score", x.get("score", 0)), reverse=True)
    return enriched
