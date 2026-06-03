"""
Test 5 Apify-only Target scrapers to find the best replacement for the Redsky API.

Evaluates each actor on:
  - Works at all (returns data)
  - Product count returned
  - Data quality (has name, price, brand, rating, reviews)
  - Relevance to paint search
  - Runtime speed
"""

import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from apify_client import ApifyClient

load_dotenv()

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
client = ApifyClient(APIFY_TOKEN)

DENVER_ZIP = "80205"
SEARCH_TERM = "interior paint"
MAX_ITEMS = 10
OUTPUT_DIR = Path("output/target_apify_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Fields we care about for normalization
FIELD_ALIASES = {
    "name": ["name", "title", "productName", "product_name", "product_title", "productTitle"],
    "price": ["price", "currentPrice", "salePrice", "current_price", "sale_price",
              "regularPrice", "regular_price", "offerPrice"],
    "brand": ["brand", "brandName", "brand_name", "manufacturer"],
    "rating": ["rating", "averageRating", "average_rating", "stars", "reviewRating",
               "ratingScore", "rating_score"],
    "reviews": ["reviews", "reviewCount", "review_count", "totalReviews", "reviewsCount",
                "ratingsCount", "numberOfReviews"],
    "url": ["url", "productUrl", "product_url", "link", "productLink"],
    "image": ["image", "imageUrl", "image_url", "thumbnail", "thumbnailUrl", "mainImage"],
}

ACTORS = [
    {
        "label": "automation-lab/target-scraper",
        "actor_id": "automation-lab/target-scraper",
        "input": {
            "searchQueries": [SEARCH_TERM],
            "maxProducts": MAX_ITEMS,
        },
        "timeout": 300,
    },
    {
        "label": "kawsar/target-product-search-scraper",
        "actor_id": "kawsar/target-product-search-scraper",
        "input": {
            "searchQuery": SEARCH_TERM,
            "maxItems": MAX_ITEMS,
        },
        "timeout": 300,
    },
    {
        "label": "sovereigntaylor/target-scraper",
        "actor_id": "sovereigntaylor/target-scraper",
        "input": {
            "searchQuery": SEARCH_TERM,
            "maxItems": MAX_ITEMS,
        },
        "timeout": 300,
    },
    {
        "label": "saswave/target-search-product-scraper",
        "actor_id": "saswave/target-search-product-scraper",
        "input": {
            "searchQuery": SEARCH_TERM,
            "maxItems": MAX_ITEMS,
        },
        "timeout": 300,
    },
    {
        "label": "getdataforme/target-product-scraper",
        "actor_id": "getdataforme/target-product-scraper",
        "input": {
            "url": f"https://www.target.com/s?searchTerm={SEARCH_TERM.replace(' ', '+')}",
            "maxItems": MAX_ITEMS,
        },
        "timeout": 300,
    },
]


def resolve_field(item, field_name):
    """Try to find a value using known aliases for a field."""
    for alias in FIELD_ALIASES.get(field_name, [field_name]):
        val = item.get(alias)
        if val is not None and val != "":
            return val
    return None


def score_item(item):
    """Score a single item on data completeness (0-100)."""
    points = 0
    weights = {"name": 25, "price": 30, "brand": 15, "rating": 15, "reviews": 10, "url": 5}
    for field, weight in weights.items():
        if resolve_field(item, field) is not None:
            points += weight
    return points


def test_actor(actor_cfg):
    """Run one actor and return results dict."""
    label = actor_cfg["label"]
    actor_id = actor_cfg["actor_id"]
    run_input = actor_cfg["input"]
    timeout = actor_cfg.get("timeout", 300)

    print(f"\n{'='*60}")
    print(f"TESTING: {label}")
    print(f"{'='*60}")

    result = {
        "actor": label,
        "status": "FAILED",
        "item_count": 0,
        "avg_quality": 0,
        "runtime_sec": 0,
        "fields_found": [],
        "sample": None,
        "error": None,
    }

    try:
        t0 = time.time()
        run = client.actor(actor_id).call(run_input=run_input, timeout_secs=timeout)
        elapsed = round(time.time() - t0, 1)
        result["runtime_sec"] = elapsed

        if not run:
            result["error"] = "Actor returned None"
            print(f"  FAILED: Actor returned None ({elapsed}s)")
            return result

        items = client.dataset(run["defaultDatasetId"]).list_items().items
        result["item_count"] = len(items)

        if not items:
            result["error"] = "No items returned"
            print(f"  FAILED: 0 items ({elapsed}s)")
            return result

        # Score data quality
        scores = [score_item(it) for it in items]
        result["avg_quality"] = round(sum(scores) / len(scores), 1)
        result["status"] = "OK"

        # Collect all unique top-level keys
        all_keys = set()
        for it in items:
            all_keys.update(it.keys())
        result["fields_found"] = sorted(all_keys)

        # Build a normalized sample from first item
        first = items[0]
        result["sample"] = {
            field: resolve_field(first, field) for field in FIELD_ALIASES
        }

        # Save raw results
        safe = label.replace("/", "_")
        out_file = OUTPUT_DIR / f"{safe}.json"
        with open(out_file, "w") as f:
            json.dump(items, f, indent=2)

        print(f"  OK: {len(items)} items, quality={result['avg_quality']}/100, {elapsed}s")
        print(f"  Sample: {result['sample']}")
        print(f"  All keys: {result['fields_found']}")

    except Exception as e:
        result["error"] = str(e)
        print(f"  ERROR: {e}")

    return result


def print_comparison(results):
    """Print a side-by-side comparison table."""
    print("\n\n" + "="*80)
    print("COMPARISON SUMMARY")
    print("="*80)

    ranked = sorted(results, key=lambda r: (
        r["status"] == "OK",
        r["avg_quality"],
        r["item_count"],
        -r["runtime_sec"],
    ), reverse=True)

    print(f"\n{'Actor':<45} {'Status':<8} {'Items':>5} {'Quality':>7} {'Time':>6}")
    print("-" * 75)
    for r in ranked:
        print(
            f"{r['actor']:<45} {r['status']:<8} {r['item_count']:>5} "
            f"{r['avg_quality']:>6}/100 {r['runtime_sec']:>5}s"
        )
        if r["error"]:
            print(f"  ^ Error: {r['error'][:70]}")

    winners = [r for r in ranked if r["status"] == "OK"]
    if winners:
        best = winners[0]
        print(f"\n>>> BEST ACTOR: {best['actor']}")
        print(f"    Items: {best['item_count']}, Quality: {best['avg_quality']}/100, Time: {best['runtime_sec']}s")
        print(f"    Sample product: {best['sample']}")
    else:
        print("\n>>> No actors returned usable data.")

    summary_file = OUTPUT_DIR / "comparison_summary.json"
    with open(summary_file, "w") as f:
        json.dump(ranked, f, indent=2, default=str)
    print(f"\nFull results saved to {summary_file}")


if __name__ == "__main__":
    if not APIFY_TOKEN:
        print("ERROR: Set APIFY_TOKEN in .env")
        exit(1)

    print("Target Apify Actor Comparison Test")
    print(f"Search: '{SEARCH_TERM}' | ZIP: {DENVER_ZIP} | Max items: {MAX_ITEMS}")

    results = []
    for actor_cfg in ACTORS:
        r = test_actor(actor_cfg)
        results.append(r)

    print_comparison(results)
