"""
SerpAPI approach (large scale): scrape Target, Home Depot, and Lowe's product data
using Google Shopping with pagination + multiple queries + native engines.
"""

import json
import os
import time
import random
from pathlib import Path
from dotenv import load_dotenv
import serpapi

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
if not SERPAPI_KEY:
    raise RuntimeError("Set SERPAPI_KEY in .env")

client = serpapi.Client(api_key=SERPAPI_KEY)

API_CALLS = 0

def serpapi_search(params, retries=3):
    """Search with retry and backoff."""
    global API_CALLS
    for attempt in range(retries):
        try:
            API_CALLS += 1
            result = client.search(params)
            return result
        except Exception as e:
            if attempt < retries - 1:
                wait = 5 * (attempt + 1) + random.uniform(1, 3)
                print(f"      retry {attempt+1}/{retries} in {wait:.0f}s ({e})")
                time.sleep(wait)
            else:
                raise

OUTPUT_DIR = Path("output/serpapi")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DENVER_ZIP = "80205"

SEARCH_QUERIES = [
    "paint",
    "interior paint",
    "exterior paint",
    "spray paint",
    "paint primer",
    "paint brushes rollers",
    "stain wood finish",
    "paint supplies",
]

STORES = {
    "Home Depot": "homedepot.com",
    "Target": "target.com",
    "Lowes": "lowes.com",
}


def search_shopping_paginated(store_name, query, max_pages=3):
    """Google Shopping with pagination — up to max_pages of ~40 results each."""
    all_results = []
    for page in range(max_pages):
        start = page * 40
        params = {
            "engine": "google_shopping",
            "q": f"{store_name} {query}",
            "location": "Denver, Colorado, United States",
            "hl": "en",
            "gl": "us",
            "num": 100,
            "start": start,
            "api_key": SERPAPI_KEY,
        }
        try:
            results = serpapi_search(params)
            items = results.get("shopping_results", [])
            if not items:
                break
            all_results.extend(items)
            print(f"    page {page+1}: {len(items)} results")
            if len(items) < 20:
                break
            time.sleep(2 + random.uniform(0.5, 1.5))
        except Exception as e:
            print(f"    page {page+1} error: {e}")
            break
    return all_results


def search_organic_paginated(store_name, query, max_pages=3):
    """Organic site-scoped search with pagination."""
    site = STORES[store_name]
    all_results = []
    for page in range(max_pages):
        start = page * 10
        params = {
            "engine": "google",
            "q": f"site:{site} {query}",
            "location": "Denver, Colorado, United States",
            "hl": "en",
            "gl": "us",
            "num": 100,
            "start": start,
            "api_key": SERPAPI_KEY,
        }
        try:
            results = serpapi_search(params)
            items = results.get("organic_results", [])
            if not items:
                break
            all_results.extend(items)
            print(f"    page {page+1}: {len(items)} results")
            if len(items) < 5:
                break
            time.sleep(2 + random.uniform(0.5, 1.5))
        except Exception as e:
            print(f"    page {page+1} error: {e}")
            break
    return all_results


def search_native_hd_paginated(query, max_pages=5):
    """Home Depot native engine with pagination."""
    all_results = []
    for page in range(max_pages):
        params = {
            "engine": "home_depot",
            "q": query,
            "delivery_zip": DENVER_ZIP,
            "page": page + 1,
            "api_key": SERPAPI_KEY,
        }
        try:
            results = serpapi_search(params)
            items = results.get("products", [])
            if not items:
                break
            all_results.extend(items)
            print(f"    page {page+1}: {len(items)} products")
            if len(items) < 10:
                break
            time.sleep(2 + random.uniform(0.5, 1.5))
        except Exception as e:
            print(f"    page {page+1} error: {e}")
            break
    return all_results


def dedup(items, key_field="title"):
    """Remove duplicates by title."""
    seen = set()
    unique = []
    for item in items:
        k = item.get(key_field, "")
        if k and k not in seen:
            seen.add(k)
            unique.append(item)
    return unique


if __name__ == "__main__":
    print("MysteryScraper — SerpAPI Large Scale Run")
    print(f"Target area: Denver, CO {DENVER_ZIP}")
    print(f"Queries: {SEARCH_QUERIES}")
    print(f"Stores: {list(STORES.keys())}\n")

    grand_summary = {}

    for store in STORES:
        print(f"\n{'#'*60}")
        print(f"# {store.upper()}")
        print(f"{'#'*60}")

        all_shopping = []
        all_organic = []
        all_native = []

        for query in SEARCH_QUERIES:
            # --- Native engine (Home Depot only) ---
            if store == "Home Depot":
                print(f"\n  [NATIVE] '{query}':")
                native = search_native_hd_paginated(query, max_pages=3)
                all_native.extend(native)

            # --- Google Shopping ---
            print(f"\n  [SHOPPING] '{query}':")
            shopping = search_shopping_paginated(store, query, max_pages=2)
            all_shopping.extend(shopping)

            # --- Organic ---
            print(f"\n  [ORGANIC] '{query}':")
            organic = search_organic_paginated(store, query, max_pages=2)
            all_organic.extend(organic)

            # Pause between query groups to avoid throttling
            time.sleep(2)

        # Dedup and save
        safe = store.lower().replace("'", "").replace(" ", "_")

        all_shopping = dedup(all_shopping, "title")
        all_organic = dedup(all_organic, "title")

        with open(OUTPUT_DIR / f"{safe}_shopping.json", "w") as f:
            json.dump(all_shopping, f, indent=2)
        with open(OUTPUT_DIR / f"{safe}_organic.json", "w") as f:
            json.dump(all_organic, f, indent=2)

        print(f"\n  >> {store} TOTALS (after dedup):")
        print(f"     Shopping: {len(all_shopping)}")
        print(f"     Organic:  {len(all_organic)}")
        grand_summary[store] = {"shopping": len(all_shopping), "organic": len(all_organic)}

        if all_native:
            all_native = dedup(all_native, "title")
            with open(OUTPUT_DIR / f"{safe}_native.json", "w") as f:
                json.dump(all_native, f, indent=2)
            print(f"     Native:   {len(all_native)}")
            grand_summary[store]["native"] = len(all_native)

    # Final summary
    print(f"\n\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    total = 0
    for store, counts in grand_summary.items():
        store_total = sum(counts.values())
        total += store_total
        parts = ", ".join(f"{k}: {v}" for k, v in counts.items())
        print(f"  {store:15s}: {store_total:4d} total  ({parts})")
    print(f"\n  GRAND TOTAL: {total} unique items")
    print(f"  API calls used: {API_CALLS}")
