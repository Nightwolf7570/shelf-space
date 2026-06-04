"""
Quick SerpAPI scrape — 1 query per store, no pagination. Validates all 4 stores work.
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import serpapi

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
if not SERPAPI_KEY:
    sys.exit("Set SERPAPI_KEY in .env")

client = serpapi.Client(api_key=SERPAPI_KEY)

OUTPUT_DIR = Path("output/serpapi")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DENVER_ZIP = "80205"

STORES = ["Home Depot", "Target", "Lowes", "Walmart"]

summary = {}

# --- Home Depot native engine ---
print("1/5  Home Depot (native engine)...")
try:
    results = client.search({
        "engine": "home_depot",
        "q": "paint",
        "delivery_zip": DENVER_ZIP,
    })
    products = results.get("products", [])
    print(f"     {len(products)} products")
    if products:
        print(f"     e.g. {products[0].get('title','?')[:60]} — ${products[0].get('price','?')}")
        with open(OUTPUT_DIR / "home_depot_native.json", "w") as f:
            json.dump(products, f, indent=2)
    summary["Home Depot (native)"] = len(products)
except Exception as e:
    print(f"     ERROR: {e}")
    summary["Home Depot (native)"] = 0

# --- Google Shopping per store ---
for i, store in enumerate(STORES, 2):
    print(f"{i}/5  {store} (Google Shopping)...")
    try:
        results = client.search({
            "engine": "google_shopping",
            "q": f"{store} paint",
            "location": "Denver, Colorado, United States",
            "hl": "en",
            "gl": "us",
        })
        items = results.get("shopping_results", [])
        print(f"     {len(items)} results")
        if items:
            print(f"     e.g. {items[0].get('title','?')[:60]} — {items[0].get('price','?')}")
            safe = store.lower().replace("'", "").replace(" ", "_")
            with open(OUTPUT_DIR / f"{safe}_shopping.json", "w") as f:
                json.dump(items, f, indent=2)
        summary[f"{store} (shopping)"] = len(items)
    except Exception as e:
        print(f"     ERROR: {e}")
        summary[f"{store} (shopping)"] = 0

# --- Summary ---
print(f"\n{'='*50}")
print("SUMMARY")
print(f"{'='*50}")
total = 0
for name, count in summary.items():
    status = "OK" if count > 0 else "FAIL"
    print(f"  {name:30s}  {status:4s}  ({count} items)")
    total += count
print(f"\n  TOTAL: {total} items across all stores")
