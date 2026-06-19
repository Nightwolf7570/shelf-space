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
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from math import ceil
from pathlib import Path

from config import CATEGORIES
from scrapers import (
    scrape_home_depot,
    scrape_target_batch, scrape_lowes_batch,
    scrape_ace_catalog, load_ace_catalog_from_file,
    set_budget,
)
from normalize import (
    normalize_home_depot, normalize_target,
    normalize_lowes, normalize_ace,
)
from analyze import find_gaps, rank_recommendations, diff_snapshots

SNAPSHOT_DIR = Path("data/snapshots")
DIFF_DIR = Path("data/diffs")
DEFAULT_HOME_DEPOT_QUOTA = 72
DEFAULT_TARGET_QUOTA = 200
DEFAULT_LOWES_REQUEST_QUOTA = 250
DEFAULT_MAX_RESULTS = 400
HOME_DEPOT_SHARE = DEFAULT_HOME_DEPOT_QUOTA / DEFAULT_MAX_RESULTS


def run(categories=None, skip_scrape=False, max_results=400, budget=5.0):
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

    if skip_scrape:
        all_competitor_products = _load_cached_data(cats)
    else:
        all_competitor_products = _scrape_parallel(cats, max_results=max_results, budget=budget)

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

    if not all_competitor_products:
        print(
            "\n  WARNING: zero competitor products were scraped. "
            "Refusing to write empty snapshots so the latest good run remains visible. "
            "Check your APIFY_API_TOKEN, the budget cap, and recent actor errors above."
        )
        return

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


def _scrape_parallel(cats, max_results=400, budget=5.0):
    """Scrape all competitors using batching + parallelism.

    max_results is the approximate target snapshot size. Home Depot scales as
    a share of the total target, Target requests about half the default target,
    and Lowe's deliberately over-requests because Google Shopping includes
    duplicate/non-Lowe's rows that get filtered out downstream.
    budget is the max Apify spend in USD — passed to scrapers for enforcement.

    - Target & Lowe's: batched (all search terms in one actor call each)
    - Home Depot: one category call, scaled from the default 72/400 share
    - All stores run concurrently via threads
    """
    all_products = []
    t0 = time.time()
    set_budget(budget)

    for cat_name in cats:
        cat = CATEGORIES.get(cat_name)
        if not cat:
            print(f"  Unknown category: {cat_name}")
            continue

        terms = cat["search_terms"]
        scale = max_results / DEFAULT_MAX_RESULTS if max_results else 0
        hd_quota = max(0, round(max_results * HOME_DEPOT_SHARE))
        target_quota = max(0, round(DEFAULT_TARGET_QUOTA * scale))
        lowes_quota = max(0, round(DEFAULT_LOWES_REQUEST_QUOTA * scale))
        target_per_term = ceil(target_quota / len(terms)) if target_quota else 0
        lowes_per_term = ceil(lowes_quota / len(terms)) if lowes_quota else 0

        print(
            f"\n--- Category: {cat_name} ({len(terms)} terms, target {max_results}: "
            f"Home Depot {hd_quota}, Target request {target_quota}, Lowe's request {lowes_quota}) ---"
        )

        # Launch all scraping concurrently
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {}

            # Target — single batched call for all terms
            if target_quota:
                futures[pool.submit(scrape_target_batch, terms, target_per_term)] = ("target_batch", cat_name, target_quota)

            # Lowe's — single batched call for all terms
            if lowes_quota:
                futures[pool.submit(scrape_lowes_batch, terms, lowes_per_term)] = ("lowes_batch", cat_name, lowes_quota)

            # Home Depot — fixed 72-product category run.
            if hd_quota:
                hd_term = terms[0]
                futures[pool.submit(scrape_home_depot, hd_term, hd_quota)] = ("hd", cat_name, hd_term, hd_quota)

            # Collect results as they finish
            for future in as_completed(futures):
                tag = futures[future]
                try:
                    result = future.result()
                except Exception as e:
                    print(f"  ERROR in {tag[0]}: {e}")
                    continue

                if tag[0] == "target_batch":
                    normalized = []
                    for term, items in result.items():
                        normalized.extend(normalize_target(items, category=tag[1], search_term=term))
                    all_products.extend(normalized[:tag[2]])

                elif tag[0] == "lowes_batch":
                    normalized = []
                    for term, items in result.items():
                        normalized.extend(normalize_lowes(items, category=tag[1], search_term=term))
                    all_products.extend(normalized[:tag[2]])

                elif tag[0] == "hd":
                    all_products.extend(
                        normalize_home_depot(result, category=tag[1], search_term=tag[2])[:tag[3]]
                    )

    elapsed = round(time.time() - t0, 1)
    print(f"\n  Scraped {len(all_products)} total products in {elapsed}s")
    return all_products


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
    parser.add_argument("--max-results", type=int, default=400, help="Approximate target product count; Lowe's is over-requested before filtering")
    parser.add_argument("--budget", type=float, default=5.0, help="Max Apify spend in USD")
    args = parser.parse_args()
    run(categories=args.categories, skip_scrape=args.skip_scrape, max_results=args.max_results, budget=args.budget)
