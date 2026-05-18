"""
Scraper functions for each retail data source.
Each function takes a search term and returns a list of raw product dicts.
"""

import json
import os
import urllib.request
import urllib.parse
from dotenv import load_dotenv
from apify_client import ApifyClient
import serpapi

from config import (
    DENVER_ZIP, HD_STORE_ID, TARGET_STORE_ID, TARGET_REDSKY_KEY, ACE_STORE_ID,
)

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
APIFY_TOKEN = os.getenv("APIFY_TOKEN")
_apify_client = ApifyClient(APIFY_TOKEN) if APIFY_TOKEN else None


def scrape_home_depot(term, max_results=24):
    """SerpAPI native Home Depot engine."""
    if not SERPAPI_KEY:
        print("  [HD] No SERPAPI_KEY")
        return []
    try:
        client = serpapi.Client(api_key=SERPAPI_KEY)
        results = client.search({
            "engine": "home_depot",
            "q": term,
            "delivery_zip": DENVER_ZIP,
        })
        products = list(results.get("products", []))[:max_results]
        print(f"  [HD] '{term}': {len(products)} products")
        return products
    except Exception as e:
        print(f"  [HD] ERROR: {e}")
        return []


def scrape_target(term, max_results=24):
    """Target Redsky API (direct HTTP, no auth needed)."""
    url = (
        f"https://redsky.target.com/redsky_aggregations/v1/web/plp_search_v2"
        f"?key={TARGET_REDSKY_KEY}&channel=WEB&count={max_results}"
        f"&default_purchasability_filter=true"
        f"&keyword={urllib.parse.quote(term)}"
        f"&offset=0&page=%2Fs%2F{urllib.parse.quote(term)}"
        f"&pricing_store_id={TARGET_STORE_ID}&store_ids={TARGET_STORE_ID}"
        f"&visitor_id=mysteryscraper&zip={DENVER_ZIP}"
    )
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        products = data.get("data", {}).get("search", {}).get("products", [])
        print(f"  [Target] '{term}': {len(products)} products")
        return products
    except Exception as e:
        print(f"  [Target] ERROR: {e}")
        return []


def scrape_walmart(term, max_results=24):
    """Apify epctex/walmart-scraper actor."""
    if not _apify_client:
        print("  [Walmart] No APIFY_TOKEN")
        return []
    try:
        result = _apify_client.actor("epctex/walmart-scraper").call(run_input={
            "search": term,
            "zipCode": DENVER_ZIP,
            "maxItems": max_results,
            "proxy": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
            },
        })
        if not result:
            return []
        items = _apify_client.dataset(result["defaultDatasetId"]).list_items().items
        print(f"  [Walmart] '{term}': {len(items)} products")
        return items
    except Exception as e:
        print(f"  [Walmart] ERROR: {e}")
        return []


def scrape_lowes(term, max_results=24):
    """SerpAPI Google Shopping filtered to Lowe's."""
    if not SERPAPI_KEY:
        print("  [Lowes] No SERPAPI_KEY")
        return []
    try:
        client = serpapi.Client(api_key=SERPAPI_KEY)
        results = client.search({
            "engine": "google_shopping",
            "q": f"Lowes {term}",
            "location": "Denver, Colorado, United States",
            "hl": "en",
            "gl": "us",
            "num": max_results,
        })
        shopping = list(results.get("shopping_results", []))
        # Filter to only Lowe's source
        lowes_items = [s for s in shopping if "lowe" in s.get("source", "").lower()]
        print(f"  [Lowes] '{term}': {len(lowes_items)} products (from {len(shopping)} total)")
        return lowes_items
    except Exception as e:
        print(f"  [Lowes] ERROR: {e}")
        return []


def scrape_ace_catalog(search_terms=None):
    """Fetch Jerry's Ace Hardware paint catalog via their search API.

    Uses paint-specific search terms to pull only relevant products
    for store 17892, then paginates through all results.
    """
    if search_terms is None:
        search_terms = [
            "paint",
            "primer",
            "stain",
            "spray paint",
            "exterior paint",
            "interior paint",
        ]

    base = "https://www.acehardware.com"
    all_items = []
    seen_codes = set()
    page_size = 48

    for term in search_terms:
        start = 0
        print(f"  [Ace] Searching '{term}'...")

        while True:
            url = (
                f"{base}/api/search?query={urllib.parse.quote(term)}"
                f"&storeId={ACE_STORE_ID}"
                f"&pageSize={page_size}"
                f"&startIndex={start}"
            )
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                    "Accept": "application/json",
                    "Referer": f"{base}/store-details/{ACE_STORE_ID}",
                })
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read())
                items = data.get("items", [])
                total = data.get("totalCount", 0)

                for item in items:
                    code = item.get("productCode", "")
                    if code and code not in seen_codes:
                        seen_codes.add(code)
                        all_items.append(item)

                print(f"    Fetched page {start // page_size + 1} "
                      f"({len(items)} items, {total} total for '{term}')")

                if start + page_size >= total or not items:
                    break
                start += page_size
            except Exception as e:
                print(f"  [Ace] ERROR for '{term}' at offset {start}: {e}")
                break

    print(f"  [Ace] Total unique paint products: {len(all_items)}")
    return all_items


def load_ace_catalog_from_file(filepath="output/ace/catalog_api.json"):
    """Load previously saved Ace catalog data."""
    try:
        with open(filepath) as f:
            data = json.load(f)
        items = data.get("items", []) if isinstance(data, dict) else data
        print(f"  [Ace] Loaded {len(items)} products from {filepath}")
        return items
    except Exception as e:
        print(f"  [Ace] ERROR loading file: {e}")
        return []
