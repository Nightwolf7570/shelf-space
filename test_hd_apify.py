"""Compare Apify Home Depot product actors at a 50+ item threshold.

The runner starts actors asynchronously and polls their default datasets so
partial output is retained if an actor hits Home Depot blocking and fails.
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
TARGET_ITEMS = 60
PASS_ITEMS = 50
OUTPUT_DIR = Path("output/hd_apify_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SEARCH_URL = "https://www.homedepot.com/s/interior%20paint"
PAINT_CATEGORY_URL = "https://www.homedepot.com/b/Paint-Interior-Paint/N-5yc1vZar2d"

# Fields we care about for normalization
DESIRED_FIELDS = ["name", "title", "price", "brand", "rating", "url", "image"]

# Map of common field name variants
FIELD_ALIASES = {
    "name": ["name", "title", "productName", "product_name", "product_title", "productTitle", "identifiers.productLabel"],
    "price": ["price", "currentPrice", "salePrice", "current_price", "sale_price", "originalPrice", "priceString", "pricing.value", "pricing.original"],
    "brand": ["brand", "brandName", "brand_name", "manufacturer", "identifiers.brandName"],
    "rating": ["rating", "averageRating", "average_rating", "stars", "reviewRating", "reviews.ratingsReviews.averageRating", "ratingValue"],
    "url": ["url", "productUrl", "product_url", "link", "productLink", "identifiers.canonicalUrl", "identifiers.canonical_url"],
    "image": ["image", "imageUrl", "image_url", "thumbnail", "thumbnailUrl", "mainImage", "media.images.0.url"],
}

# ---- 5 CURRENT STORE CANDIDATES ----
ACTORS = [
    {
        "label": "crawlerbros/homedepot-scraper",
        "actor_id": "crawlerbros/homedepot-scraper",
        "input": {
            "searchQuery": SEARCH_TERM,
            "zipCode": DENVER_ZIP,
            "maxItems": TARGET_ITEMS,
        },
        "timeout": 600,
    },
    {
        "label": "scraptivo/homedepot-scraper",
        "actor_id": "scraptivo/homedepot-scraper",
        "input": {
            "url": SEARCH_URL,
            "deliveryZip": DENVER_ZIP,
            "maxProducts": TARGET_ITEMS,
            "proxyConfiguration": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
                "apifyProxyCountry": "US",
            },
        },
        "timeout": 600,
    },
    {
        "label": "rigelbytes/homedepot-scraper",
        "actor_id": "rigelbytes/homedepot-scraper",
        "input": {
            "url": PAINT_CATEGORY_URL,
            "deliveryZip": DENVER_ZIP,
            "address": DENVER_ZIP,
            "maxProducts": TARGET_ITEMS,
            "proxyConfiguration": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
                "apifyProxyCountry": "US",
            },
        },
        "timeout": 600,
    },
    {
        "label": "getdataforme/homedepot-category-scraper",
        "actor_id": "getdataforme/homedepot-category-scraper",
        "input": {
            "searchKeyword": SEARCH_TERM,
            "maxItems": TARGET_ITEMS,
            "proxyConfiguration": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
            },
        },
        "timeout": 600,
    },
    {
        "label": "studio-amba/homedepot-scraper",
        "actor_id": "studio-amba/homedepot-scraper",
        "input": {
            "searchQuery": SEARCH_TERM,
            "maxResults": TARGET_ITEMS,
            "proxyConfiguration": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
                "apifyProxyCountry": "US",
            },
        },
        "timeout": 600,
    },
]


def nested_get(item, dotted):
    current = item
    for part in dotted.split("."):
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current in (None, ""):
            return None
    return current


def resolve_field(item, field_name):
    """Try to find a value using known aliases for a field."""
    for alias in FIELD_ALIASES.get(field_name, [field_name]):
        val = nested_get(item, alias)
        if val is not None and val != "":
            if field_name == "url" and isinstance(val, str) and val.startswith("/"):
                return f"https://www.homedepot.com{val}"
            return val
    return None


def score_item(item):
    """Score a single item on data completeness (0-100)."""
    points = 0
    weights = {"name": 25, "price": 30, "brand": 15, "rating": 15, "url": 10, "image": 5}
    for field, weight in weights.items():
        if resolve_field(item, field) is not None:
            points += weight
    return points


def relevance_score(items):
    """Percentage of items that look related to the paint search."""
    needles = ("paint", "primer", "behr", "glidden", "kilz", "stain", "enamel")
    if not items:
        return 0
    relevant = 0
    for item in items:
        haystack = " ".join(str(resolve_field(item, f) or "") for f in ("name", "brand", "url")).lower()
        if any(n in haystack for n in needles):
            relevant += 1
    return round(relevant * 100 / len(items), 1)


def collect_dataset(dataset_id, limit=None):
    items = client.dataset(dataset_id).list_items(limit=limit).items
    return items or []


def test_actor(actor_cfg):
    """Run one actor and return results dict."""
    label = actor_cfg["label"]
    actor_id = actor_cfg["actor_id"]
    run_input = actor_cfg["input"]

    print(f"\n{'='*60}")
    print(f"TESTING: {label}")
    print(f"{'='*60}")

    result = {
        "actor": label,
        "status": "FAILED",
        "item_count": 0,
        "avg_quality": 0,
        "relevance": 0,
        "runtime_sec": 0,
        "fields_found": [],
        "sample": None,
        "error": None,
        "run_id": None,
        "run_status": None,
        "usage_usd": 0,
    }

    try:
        t0 = time.time()
        timeout = actor_cfg.get("timeout", 300)
        run = client.actor(actor_id).start(run_input=run_input)
        run_id = run["id"]
        dataset_id = run["defaultDatasetId"]
        result["run_id"] = run_id
        status = "UNKNOWN"
        aborted_at_limit = False

        while time.time() - t0 < timeout:
            info = client.run(run_id).get()
            status = info.get("status", "UNKNOWN")
            if status in ("SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"):
                break

            count = (client.dataset(dataset_id).get() or {}).get("itemCount", 0)
            print(f"  {label}: status={status}, items={count}")
            if count >= TARGET_ITEMS:
                client.run(run_id).abort()
                aborted_at_limit = True
                status = "ABORTED_AT_LIMIT"
                break
            time.sleep(10)
        else:
            status = "LOCAL_TIMEOUT"
            try:
                client.run(run_id).abort()
            except Exception:
                pass

        info = client.run(run_id).get()
        if aborted_at_limit:
            status = "ABORTED_AT_LIMIT"
        else:
            status = info.get("status", status)
        elapsed = round(time.time() - t0, 1)
        result["runtime_sec"] = elapsed
        result["run_status"] = status
        result["usage_usd"] = round(info.get("usageTotalUsd") or 0, 4)

        items = collect_dataset(dataset_id, limit=TARGET_ITEMS)
        result["item_count"] = len(items)

        if not items:
            result["error"] = "No items returned"
            print(f"  FAILED: 0 items ({elapsed}s)")
            return result

        # Score data quality
        scores = [score_item(it) for it in items]
        result["avg_quality"] = round(sum(scores) / len(scores), 1)
        result["relevance"] = relevance_score(items)
        result["status"] = "OK" if len(items) >= PASS_ITEMS and status in ("SUCCEEDED", "ABORTED_AT_LIMIT", "ABORTED") else "FAILED"
        if len(items) < PASS_ITEMS:
            result["error"] = f"Only returned {len(items)} items; need at least {PASS_ITEMS}"
        elif status not in ("SUCCEEDED", "ABORTED_AT_LIMIT", "ABORTED"):
            result["error"] = f"Run ended with status {status}"

        # Collect all unique top-level keys across items
        all_keys = set()
        for it in items:
            all_keys.update(it.keys())
        result["fields_found"] = sorted(all_keys)

        # Build a normalized sample from first item
        first = items[0]
        result["sample"] = {
            field: resolve_field(first, field) for field in DESIRED_FIELDS
        }

        # Save raw results
        safe = label.replace("/", "_")
        out_file = OUTPUT_DIR / f"{safe}.json"
        with open(out_file, "w") as f:
            json.dump(items, f, indent=2)

        print(
            f"  {result['status']}: {len(items)} items, quality={result['avg_quality']}/100, "
            f"relevance={result['relevance']}%, status={status}, cost=${result['usage_usd']}, {elapsed}s"
        )
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

    # Sort by: status OK first, then by quality desc, then by item count desc
    ranked = sorted(results, key=lambda r: (
        r["status"] == "OK",
        r["avg_quality"],
        r["item_count"],
        -r["runtime_sec"],
    ), reverse=True)

    print(f"\n{'Actor':<42} {'Status':<8} {'Run':<16} {'Items':>5} {'Quality':>7} {'Rel':>6} {'Cost':>7} {'Time':>6}")
    print("-" * 102)
    for r in ranked:
        print(
            f"{r['actor']:<42} {r['status']:<8} {str(r['run_status']):<16} {r['item_count']:>5} "
            f"{r['avg_quality']:>6}/100 {r['relevance']:>5}% ${r['usage_usd']:>5} {r['runtime_sec']:>5}s"
        )
        if r["error"]:
            print(f"  ^ Error: {r['error'][:70]}")

    # Pick winner
    winners = [r for r in ranked if r["status"] == "OK"]
    if winners:
        best = winners[0]
        print(f"\n>>> BEST ACTOR: {best['actor']}")
        print(
            f"    Items: {best['item_count']}, Quality: {best['avg_quality']}/100, "
            f"Relevance: {best['relevance']}%, Time: {best['runtime_sec']}s"
        )
        print(f"    Sample product: {best['sample']}")
    else:
        print("\n>>> No actors returned usable data.")

    # Save summary
    summary_file = OUTPUT_DIR / "comparison_summary.json"
    with open(summary_file, "w") as f:
        json.dump(ranked, f, indent=2, default=str)
    print(f"\nFull results saved to {summary_file}")


if __name__ == "__main__":
    if not APIFY_TOKEN:
        print("ERROR: Set APIFY_TOKEN in .env")
        exit(1)

    print("Home Depot Apify Actor Comparison Test")
    print(f"Search: '{SEARCH_TERM}' | ZIP: {DENVER_ZIP} | Target items: {TARGET_ITEMS} | Pass threshold: {PASS_ITEMS}")

    results = []
    for actor_cfg in ACTORS:
        r = test_actor(actor_cfg)
        results.append(r)

    print_comparison(results)
