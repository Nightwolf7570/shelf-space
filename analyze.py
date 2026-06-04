"""
Gap analysis: compare competitor products against Jerry's Ace catalog.
"""

from config import BRAND_ALIASES


def _normalize_brand(brand):
    """Lowercase, strip, and resolve aliases."""
    b = brand.lower().strip()
    for canonical, aliases in BRAND_ALIASES.items():
        if b == canonical or b in aliases:
            return canonical
    return b


def _extract_brand_from_name(name):
    """Try to pull brand from product name (first 1-2 words before common keywords)."""
    if not name:
        return ""
    words = name.lower().split()
    # Known brand list for matching
    all_brands = set()
    for canonical, aliases in BRAND_ALIASES.items():
        all_brands.add(canonical)
        all_brands.update(aliases)

    # Check if first 1-3 words match a known brand
    for length in [3, 2, 1]:
        candidate = " ".join(words[:length])
        if candidate in all_brands:
            return _normalize_brand(candidate)
    return ""


def find_gaps(ace_products, competitor_products):
    """
    Find products/brands competitors carry that Jerry's doesn't.

    Returns a list of gap dicts, each representing a competitor product
    not matched in Jerry's catalog.
    """
    # Build set of brands Jerry's carries (from product names since brand field is empty)
    ace_brands = set()
    ace_names_lower = set()
    for p in ace_products:
        name = p.get("name", "").lower()
        ace_names_lower.add(name)
        # Extract brand from Ace product name
        brand = _extract_brand_from_name(name)
        if brand:
            ace_brands.add(brand)
        # Also add the explicit brand if present
        if p.get("brand"):
            ace_brands.add(_normalize_brand(p["brand"]))

    gaps = []
    seen = set()

    for p in competitor_products:
        comp_brand = _normalize_brand(p.get("brand", "")) or _extract_brand_from_name(p.get("name", ""))
        comp_name = p.get("name", "").lower()

        # Skip if Jerry's carries this brand
        if comp_brand and comp_brand in ace_brands:
            continue

        # Skip exact name duplicates we've already flagged
        dedup_key = f"{p['source']}:{comp_name[:60]}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        gaps.append({
            "name": p.get("name", ""),
            "brand": p.get("brand", "") or comp_brand,
            "source": p.get("source", ""),
            "price": p.get("price"),
            "rating": p.get("rating"),
            "reviews": p.get("reviews"),
            "category": p.get("category", ""),
            "signal": p.get("signal", ""),
            "url": p.get("url", ""),
        })

    return gaps


def rank_recommendations(gaps, max_items=100, balance_sources=False):
    """
    Score and rank gap products. Returns top N recommendations.

    Scoring:
    - bestseller signal: +5
    - high_rated signal: +4
    - rating >= 4.0: +3
    - reviews >= 100: +2
    - reviews >= 500: +2 more
    - has price (not None): +2
    - each additional competitor source: +3

    Results are returned in score-descending order by default. Source balancing
    can be enabled by passing balance_sources=True.
    """
    scored = []
    for g in gaps:
        score = 0
        if g.get("signal") == "bestseller":
            score += 5
        elif g.get("signal") == "high_rated":
            score += 4
        if g.get("rating") and g["rating"] >= 4.0:
            score += 3
        if g.get("reviews"):
            if g["reviews"] >= 100:
                score += 2
            if g["reviews"] >= 500:
                score += 2
        if g.get("price"):
            score += 2

        scored.append({**g, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)

    # Aggregate: if same product appears from multiple competitors, merge
    merged = {}
    for item in scored:
        key = item["name"].lower()[:50]
        if key in merged:
            if item["source"] not in merged[key]["sources"]:
                merged[key]["sources"].append(item["source"])
            if item["score"] > merged[key]["score"]:
                merged[key]["score"] = item["score"]
        else:
            merged[key] = {**item, "sources": [item["source"]]}

    # Re-score by number of additional competitor sources.
    for m in merged.values():
        m["score"] += max(0, len(m["sources"]) - 1) * 3

    ranked = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
    if not balance_sources:
        return ranked[:max_items]

    return _balance_by_source(ranked, max_items)


def _balance_by_source(items, max_items):
    """Interleave ranked items by source so one data-rich store cannot dominate."""
    buckets = {}
    source_order = []
    for item in items:
        source = item.get("source") or (item.get("sources") or [""])[0]
        if source not in buckets:
            buckets[source] = []
            source_order.append(source)
        buckets[source].append(item)

    # Start each round with the source whose next item has the strongest score.
    balanced = []
    seen_keys = set()
    while len(balanced) < max_items and any(buckets.values()):
        active_sources = [s for s in source_order if buckets[s]]
        active_sources.sort(key=lambda s: buckets[s][0]["score"], reverse=True)
        for source in active_sources:
            if len(balanced) >= max_items:
                break
            item = buckets[source].pop(0)
            key = item["name"].lower()[:50]
            if key in seen_keys:
                continue
            seen_keys.add(key)
            balanced.append(item)

    return balanced


def diff_snapshots(current_competitors, previous_competitors):
    """
    Compare two snapshots to find month-over-month changes.
    Returns dict with new_items, removed_items, price_changes.
    """
    def _key(p):
        return f"{p.get('source', '')}:{p.get('name', '').lower()[:60]}"

    current_map = {_key(p): p for p in current_competitors}
    previous_map = {_key(p): p for p in previous_competitors}

    current_keys = set(current_map.keys())
    previous_keys = set(previous_map.keys())

    new_items = [current_map[k] for k in current_keys - previous_keys]
    removed_items = [previous_map[k] for k in previous_keys - current_keys]

    price_changes = []
    for k in current_keys & previous_keys:
        curr_price = current_map[k].get("price")
        prev_price = previous_map[k].get("price")
        if curr_price and prev_price and curr_price != prev_price:
            pct = ((curr_price - prev_price) / prev_price) * 100
            if abs(pct) >= 5:  # Only flag 5%+ changes
                price_changes.append({
                    **current_map[k],
                    "previous_price": prev_price,
                    "price_change_pct": round(pct, 1),
                })

    return {
        "new_items": sorted(new_items, key=lambda x: x.get("signal", "") == "bestseller", reverse=True),
        "removed_items": removed_items,
        "price_changes": sorted(price_changes, key=lambda x: abs(x["price_change_pct"]), reverse=True),
    }
