"""
CLI entrypoint: scrape all sources, normalize, save snapshot.

Usage:
    python run_snapshot.py                    # scrape all categories
    python run_snapshot.py --categories paint # scrape paint only
    python run_snapshot.py --skip-scrape      # use existing output/ data
"""

import argparse
import html
import json
from datetime import date
from pathlib import Path

from config import CATEGORIES
from scrapers import (
    scrape_home_depot, scrape_target, scrape_walmart, scrape_lowes,
    scrape_ace_catalog, load_ace_catalog_from_file,
)
from normalize import (
    normalize_home_depot, normalize_target, normalize_walmart,
    normalize_lowes, normalize_ace,
)
from analyze import find_gaps, rank_recommendations, diff_snapshots

SNAPSHOT_DIR = Path("data/snapshots")
DIFF_DIR = Path("data/diffs")


def run(categories=None, skip_scrape=False):
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    DIFF_DIR.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()
    cats = categories or list(CATEGORIES.keys())

    print(f"\n{'='*60}")
    print(f"MysteryScraper — Snapshot Run: {today}")
    print(f"Categories: {', '.join(cats)}")
    print(f"{'='*60}")

    # --- Scrape competitors ---
    all_competitor_products = []

    for cat_name in cats:
        cat = CATEGORIES.get(cat_name)
        if not cat:
            print(f"  Unknown category: {cat_name}")
            continue

        print(f"\n--- Category: {cat_name} ---")

        for term in cat["search_terms"]:
            print(f"\n  Search: '{term}'")

            if skip_scrape:
                print("    (skipping scrape, using cached data)")
                continue

            # Home Depot
            hd_raw = scrape_home_depot(term)
            all_competitor_products.extend(
                normalize_home_depot(hd_raw, category=cat_name, search_term=term)
            )

            # Target
            tgt_raw = scrape_target(term)
            all_competitor_products.extend(
                normalize_target(tgt_raw, category=cat_name, search_term=term)
            )

            # Walmart
            wm_raw = scrape_walmart(term)
            all_competitor_products.extend(
                normalize_walmart(wm_raw, category=cat_name, search_term=term)
            )

            # Lowe's
            low_raw = scrape_lowes(term)
            all_competitor_products.extend(
                normalize_lowes(low_raw, category=cat_name, search_term=term)
            )

    if skip_scrape:
        # Load from existing output files
        all_competitor_products = _load_cached_data(cats)

    # --- Scrape/load Ace catalog ---
    print(f"\n--- Jerry's Ace Hardware Catalog ---")
    ace_file = Path("output/ace/catalog_api.json")
    if ace_file.exists():
        ace_raw = load_ace_catalog_from_file(str(ace_file))
    else:
        print("  Fetching live catalog...")
        ace_raw = scrape_ace_catalog()

    ace_products = normalize_ace(ace_raw)

    # Filter Ace products to relevant categories
    ace_filtered = []
    for p in ace_products:
        for cat_name in cats:
            prefix = CATEGORIES[cat_name]["ace_type_prefix"]
            if p.get("product_type_id", "").startswith(prefix):
                p["category"] = cat_name
                ace_filtered.append(p)
                break

    print(f"\n  Jerry's products in selected categories: {len(ace_filtered)}")

    # --- Save snapshots ---
    comp_path = SNAPSHOT_DIR / f"{today}_competitors.json"
    ace_path = SNAPSHOT_DIR / f"{today}_ace_catalog.json"

    with open(comp_path, "w") as f:
        json.dump(all_competitor_products, f, indent=2)
    print(f"\n  Saved {len(all_competitor_products)} competitor products -> {comp_path}")

    with open(ace_path, "w") as f:
        json.dump(ace_filtered, f, indent=2)
    print(f"  Saved {len(ace_filtered)} Ace products -> {ace_path}")

    # --- Gap analysis ---
    print(f"\n--- Gap Analysis ---")
    gaps = find_gaps(ace_filtered, all_competitor_products)
    print(f"  Found {len(gaps)} total gaps")

    recommendations = rank_recommendations(gaps)
    print(f"\n  Top {len(recommendations)} Recommendations:")
    for i, r in enumerate(recommendations, 1):
        sources = ", ".join(r.get("sources", [r.get("source", "")]))
        signal = f" [{r['signal']}]" if r.get("signal") else ""
        price = f"${r['price']:.2f}" if r.get("price") else "N/A"
        print(f"    {i:2d}. {r['name'][:60]}")
        print(f"        {price} | {sources}{signal} | score: {r['score']}")

    # --- Month-over-month diff ---
    previous = _find_previous_snapshot(today)
    if previous:
        print(f"\n--- Month-over-Month Changes (vs {previous.stem.split('_')[0]}) ---")
        with open(previous) as f:
            prev_data = json.load(f)
        diff = diff_snapshots(all_competitor_products, prev_data)
        diff_path = DIFF_DIR / f"{today}_diff.json"
        with open(diff_path, "w") as f:
            json.dump(diff, f, indent=2)
        print(f"  New items: {len(diff['new_items'])}")
        print(f"  Removed items: {len(diff['removed_items'])}")
        print(f"  Price changes: {len(diff['price_changes'])}")
    else:
        print(f"\n  No previous snapshot found — run again next month to see changes.")

    print(f"\n{'='*60}")
    print("Done!")
    print(f"{'='*60}")


def _load_cached_data(cats):
    """Load competitor data from existing output/ files."""
    from normalize import (
        normalize_home_depot, normalize_target, normalize_walmart, normalize_lowes,
    )
    products = []

    # Home Depot — SerpAPI native results (list of products)
    for filepath, cat in [("output/serpapi/home_depot_native.json", "paint")]:
        try:
            with open(filepath) as f:
                data = json.load(f)
            normalized = normalize_home_depot(data, category=cat, search_term="cached")
            products.extend(normalized)
            print(f"  Loaded {len(normalized)} from {filepath}")
        except Exception as e:
            print(f"  Could not load {filepath}: {e}")

    # Target — already-normalized data (list of simple dicts, not Redsky raw)
    for filepath, cat in [
        ("output/target_interior_paint.json", "paint"),
        ("output/target_cleaning.json", "cleaning"),
    ]:
        try:
            with open(filepath) as f:
                data = json.load(f)
            # These are already partially normalized from test_refined.py
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            for item in data:
                price_str = item.get("price", "")
                price_val = None
                if price_str:
                    import re
                    cleaned = re.sub(r'[^\d.]', '', str(price_str))
                    try:
                        price_val = float(cleaned)
                    except ValueError:
                        pass
                products.append({
                    "source": "Target",
                    "name": html.unescape(item.get("name", "")),
                    "brand": item.get("brand", ""),
                    "price": price_val,
                    "rating": float(item["rating"]) if item.get("rating") else None,
                    "reviews": int(item["review_count"]) if item.get("review_count") else None,
                    "category": cat,
                    "search_term": "cached",
                    "url": item.get("url", ""),
                    "signal": "",
                    "scraped_at": now,
                })
            print(f"  Loaded {len(data)} from {filepath}")
        except Exception as e:
            print(f"  Could not load {filepath}: {e}")

    # Walmart — complex nested JSON (list of product objects)
    for filepath, cat in [("output/walmart.json", "paint")]:
        try:
            with open(filepath) as f:
                data = json.load(f)
            normalized = normalize_walmart(data, category=cat, search_term="cached")
            products.extend(normalized)
            print(f"  Loaded {len(normalized)} from {filepath}")
        except Exception as e:
            print(f"  Could not load {filepath}: {e}")

    # Lowe's — SerpAPI Google Shopping results
    for filepath, cat in [("output/serpapi/lowes_shopping.json", "paint")]:
        try:
            with open(filepath) as f:
                data = json.load(f)
            normalized = normalize_lowes(data, category=cat, search_term="cached")
            products.extend(normalized)
            print(f"  Loaded {len(normalized)} from {filepath}")
        except Exception as e:
            print(f"  Could not load {filepath}: {e}")

    return products


def _find_previous_snapshot(today_str):
    """Find the most recent competitor snapshot before today."""
    snapshots = sorted(SNAPSHOT_DIR.glob("*_competitors.json"))
    for s in reversed(snapshots):
        snap_date = s.stem.split("_")[0]
        if snap_date < today_str:
            return s
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MysteryScraper snapshot runner")
    parser.add_argument("--categories", nargs="+", help="Categories to scrape")
    parser.add_argument("--skip-scrape", action="store_true", help="Use cached output/ data")
    args = parser.parse_args()
    run(categories=args.categories, skip_scrape=args.skip_scrape)
