"""
Run ALL scrapers: SerpAPI (Google Shopping + HD native), Target Redsky API,
Apify Walmart, and Ace Hardware API. Saves results to output/serpapi/.
"""

import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
import serpapi
from apify_client import ApifyClient
import urllib.request
import urllib.parse

load_dotenv()

from config import DENVER_ZIP, TARGET_STORE_ID, TARGET_REDSKY_KEY, ACE_STORE_ID

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
APIFY_TOKEN = os.getenv("APIFY_TOKEN")

serp_client = serpapi.Client(api_key=SERPAPI_KEY) if SERPAPI_KEY else None
apify_client = ApifyClient(APIFY_TOKEN) if APIFY_TOKEN else None

OUTPUT_DIR = Path("output/serpapi")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

QUERIES = ["paint", "interior paint", "exterior paint", "spray paint", "primer", "stain"]

now = datetime.now(timezone.utc).isoformat()
summary = {}


def save(name, data):
    safe = name.lower().replace(" ", "_").replace("'", "")
    path = OUTPUT_DIR / f"{safe}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved {len(data)} items -> {path}", flush=True)


def dedup(items, key="title"):
    seen = set()
    out = []
    for item in items:
        k = item.get(key, "")
        if k and k not in seen:
            seen.add(k)
            out.append(item)
    return out


# ============================================================
# 1. SerpAPI Google Shopping — Home Depot, Target, Lowes, Walmart
# ============================================================
if serp_client:
    for store in ["Home Depot", "Target", "Lowes", "Walmart"]:
        print(f"\n--- {store} (SerpAPI Google Shopping) ---", flush=True)
        all_items = []
        for q in QUERIES:
            try:
                r = serp_client.search({
                    "engine": "google_shopping",
                    "q": f"{store} {q}",
                    "location": "Denver, Colorado, United States",
                    "hl": "en", "gl": "us",
                })
                items = r.get("shopping_results", [])
                all_items.extend(items)
                print(f"  {q}: {len(items)} results", flush=True)
            except Exception as e:
                print(f"  {q}: ERROR - {e}", flush=True)
        unique = dedup(all_items)
        save(store, unique)
        summary[f"{store} (Shopping)"] = len(unique)

    # Home Depot native engine
    print(f"\n--- Home Depot (SerpAPI Native Engine) ---", flush=True)
    all_native = []
    for q in QUERIES:
        try:
            r = serp_client.search({
                "engine": "home_depot",
                "q": q,
                "delivery_zip": DENVER_ZIP,
            })
            items = r.get("products", [])
            all_native.extend(items)
            print(f"  {q}: {len(items)} products", flush=True)
        except Exception as e:
            print(f"  {q}: ERROR - {e}", flush=True)
    unique = dedup(all_native)
    save("home_depot_native", unique)
    summary["Home Depot (Native)"] = len(unique)
else:
    print("\nSKIPPING SerpAPI scrapers — no SERPAPI_KEY", flush=True)


# ============================================================
# 2. Target Redsky API (direct, no auth)
# ============================================================
print(f"\n--- Target (Redsky API) ---", flush=True)
target_products = []
for q in QUERIES:
    try:
        url = (
            f"https://redsky.target.com/redsky_aggregations/v1/web/plp_search_v2"
            f"?key={TARGET_REDSKY_KEY}&channel=WEB&count=24"
            f"&default_purchasability_filter=true"
            f"&keyword={urllib.parse.quote(q)}"
            f"&offset=0&page=%2Fs%2F{urllib.parse.quote(q)}"
            f"&pricing_store_id={TARGET_STORE_ID}&store_ids={TARGET_STORE_ID}"
            f"&visitor_id=mysteryscraper&zip={DENVER_ZIP}"
        )
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        products = data.get("data", {}).get("search", {}).get("products", [])
        target_products.extend(products)
        print(f"  {q}: {len(products)} products", flush=True)
    except Exception as e:
        print(f"  {q}: ERROR - {e}", flush=True)

if target_products:
    # Dedup by tcin
    seen = set()
    unique_target = []
    for p in target_products:
        tcin = p.get("tcin", "")
        if tcin and tcin not in seen:
            seen.add(tcin)
            unique_target.append(p)
    save("target_redsky", unique_target)
    summary["Target (Redsky API)"] = len(unique_target)


# ============================================================
# 3. Walmart via Apify
# ============================================================
if apify_client:
    print(f"\n--- Walmart (Apify) ---", flush=True)
    walmart_all = []
    for q in QUERIES:
        try:
            print(f"  {q}: running actor...", flush=True)
            result = apify_client.actor("epctex/walmart-scraper").call(run_input={
                "search": q,
                "zipCode": DENVER_ZIP,
                "maxItems": 24,
                "proxy": {
                    "useApifyProxy": True,
                    "apifyProxyGroups": ["RESIDENTIAL"],
                },
            })
            if result:
                items = apify_client.dataset(result["defaultDatasetId"]).list_items().items
                walmart_all.extend(items)
                print(f"  {q}: {len(items)} products", flush=True)
            else:
                print(f"  {q}: no result", flush=True)
        except Exception as e:
            print(f"  {q}: ERROR - {e}", flush=True)

    if walmart_all:
        # Dedup by url or name
        seen = set()
        unique_wm = []
        for item in walmart_all:
            key = item.get("url", item.get("name", ""))
            if key and key not in seen:
                seen.add(key)
                unique_wm.append(item)
        save("walmart_apify", unique_wm)
        summary["Walmart (Apify)"] = len(unique_wm)
else:
    print("\nSKIPPING Apify Walmart — no APIFY_TOKEN", flush=True)


# ============================================================
# 4. Ace Hardware API (Jerry's store)
# ============================================================
print(f"\n--- Ace Hardware (Store API) ---", flush=True)
ace_all = []
seen_codes = set()
for q in QUERIES:
    start = 0
    page_size = 48
    while True:
        try:
            url = (
                f"https://www.acehardware.com/api/search"
                f"?query={urllib.parse.quote(q)}"
                f"&storeId={ACE_STORE_ID}"
                f"&pageSize={page_size}&startIndex={start}"
            )
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "Accept": "application/json",
                "Referer": f"https://www.acehardware.com/store-details/{ACE_STORE_ID}",
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            items = data.get("items", [])
            total = data.get("totalCount", 0)
            for item in items:
                code = item.get("productCode", "")
                if code and code not in seen_codes:
                    seen_codes.add(code)
                    ace_all.append(item)
            print(f"  {q} p{start//page_size+1}: {len(items)} items (total {total})", flush=True)
            if start + page_size >= total or not items:
                break
            start += page_size
        except Exception as e:
            print(f"  {q}: ERROR - {e}", flush=True)
            break

if ace_all:
    save("ace_hardware", ace_all)
    summary["Ace Hardware (API)"] = len(ace_all)


# ============================================================
# Summary
# ============================================================
print(f"\n{'='*50}", flush=True)
print("SUMMARY", flush=True)
print(f"{'='*50}", flush=True)
total = 0
for name, count in summary.items():
    status = "OK" if count > 0 else "FAIL"
    print(f"  {name:30s}  {status:4s}  ({count} items)", flush=True)
    total += count
print(f"\n  GRAND TOTAL: {total} unique items", flush=True)
print("Done!", flush=True)
