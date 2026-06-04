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

from config import DENVER_ZIP, ACE_STORE_ID

load_dotenv()

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
_apify_client = ApifyClient(APIFY_TOKEN) if APIFY_TOKEN else None

# Shared budget tracker — set via set_budget() before scraping starts.
_budget_limit = float("inf")
_total_spend = 0.0

import threading
_budget_lock = threading.Lock()


def set_budget(limit_usd):
    """Set the max Apify spend for this session."""
    global _budget_limit, _total_spend
    _budget_limit = limit_usd
    _total_spend = 0.0
    print(f"  Budget set: ${limit_usd:.2f}")


def _track_spend(run_id):
    """Add a completed run's cost to the running total. Returns True if over budget."""
    global _total_spend
    try:
        info = _apify_client.run(run_id).get()
        cost = info.get("usageTotalUsd", 0) or 0
        with _budget_lock:
            _total_spend += cost
            over = _total_spend >= _budget_limit
        print(f"  Cost: ${cost:.3f} (total: ${_total_spend:.2f} / ${_budget_limit:.2f})")
        return over
    except Exception:
        return False


def is_over_budget():
    """Check if we've exceeded the budget."""
    with _budget_lock:
        return _total_spend >= _budget_limit


def _wait_and_collect(run, label="", timeout=180, max_items=None):
    """Poll an Apify run until terminal state, then return dataset items.

    Unlike .call(), this always retrieves partial data even if the actor
    crashes mid-run (common with HD's Akamai bot protection).

    If max_items is set, aborts the run early once the dataset reaches
    that count — prevents runaway actors that ignore maxProducts.
    Aborts if the session budget is exceeded.
    """
    import time as _time
    run_id = run["id"]
    dataset_id = run["defaultDatasetId"]
    deadline = _time.time() + timeout
    status = "UNKNOWN"

    while _time.time() < deadline:
        info = _apify_client.run(run_id).get()
        status = info.get("status", "UNKNOWN")
        if status in ("SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"):
            break

        # Abort if over budget
        if is_over_budget():
            print(f"  {label}: BUDGET EXCEEDED, aborting run")
            _apify_client.run(run_id).abort()
            status = "ABORTED (budget)"
            break

        # Abort runaway actors that ignore maxProducts
        if max_items:
            dataset_info = _apify_client.dataset(dataset_id).get()
            count = dataset_info.get("itemCount", 0) if dataset_info else 0
            if count >= max_items:
                print(f"  {label}: hit {count} items (limit {max_items}), aborting run")
                _apify_client.run(run_id).abort()
                status = "ABORTED (limit)"
                break

        _time.sleep(5)

    # Track this run's cost
    _track_spend(run_id)

    items = _apify_client.dataset(dataset_id).list_items().items
    print(f"  {label}: {len(items)} products (status: {status})")
    return items


# Home Depot category URLs for the rigelbytes/homedepot-scraper actor,
# which browses by category page rather than keyword search.
_HD_CATEGORY_URLS = {
    # Core paint
    "interior wall paint": "https://www.homedepot.com/b/Paint-Interior-Paint/N-5yc1vZar2d",
    "exterior paint":      "https://www.homedepot.com/b/Paint-Exterior-Paint/N-5yc1vZar2c",
    "spray paint":         "https://www.homedepot.com/b/Paint-Spray-Paint/N-5yc1vZar2f",
    "paint primer":        "https://www.homedepot.com/b/Paint-Primer/N-5yc1vZar2e",
    # Stains
    "stain":               "https://www.homedepot.com/b/Paint-Exterior-Stain-Waterproofing/N-5yc1vZar2b",
    "interior wood stain": "https://www.homedepot.com/b/Paint-Interior-Wood-Stains/N-5yc1vZbo8p",
    "exterior wood stain": "https://www.homedepot.com/b/Paint-Exterior-Wood-Coatings-Exterior-Wood-Stains/N-5yc1vZbbbm",
    # Specialty
    "garage floor paint":  "https://www.homedepot.com/b/Paint-Garage-Floor-Paint/N-5yc1vZbd13",
    "caulk and sealants":  "https://www.homedepot.com/b/Paint-Paint-Supplies-Caulk-Sealants/N-5yc1vZc5bp",
    # Supplies & applicators
    "paint supplies":      "https://www.homedepot.com/b/Paint-Paint-Supplies/N-5yc1vZci1w",
    "paint brushes":       "https://www.homedepot.com/b/Paint-Paint-Supplies-Paint-Applicators-Paint-Brushes/N-5yc1vZarac",
    "paint rollers":       "https://www.homedepot.com/b/Paint-Paint-Supplies-Paint-Applicators-Paint-Rollers/N-5yc1vZaqpy",
    "paint sprayers":      "https://www.homedepot.com/b/Paint-Paint-Supplies-Paint-Applicators-Paint-Sprayers/N-5yc1vZarv5",
}
_HD_DEFAULT_URL = "https://www.homedepot.com/b/Paint/N-5yc1vZar2d"


def scrape_home_depot(term, max_results=24, max_retries=3):
    """Apify rigelbytes/homedepot-scraper — category browse with ratings & reviews.

    The actor is flaky due to HD's Akamai bot protection — sometimes crashes
    with 0 results (57s), sometimes succeeds instantly (6s).  We retry up to
    max_retries times on empty results before giving up.
    """
    if not _apify_client:
        print("  [HD] No APIFY_TOKEN")
        return []
    category_url = _HD_CATEGORY_URLS.get(term.lower(), _HD_DEFAULT_URL)

    for attempt in range(1, max_retries + 1):
        if is_over_budget():
            print(f"  [HD] '{term}': skipping — budget exceeded")
            return []
        try:
            run = _apify_client.actor("rigelbytes/homedepot-scraper").start(run_input={
                "url": category_url,
                "deliveryZip": DENVER_ZIP,
                "address": DENVER_ZIP,
                "maxProducts": max_results,
                "proxyConfiguration": {
                    "useApifyProxy": True,
                    "apifyProxyGroups": ["RESIDENTIAL"],
                    "apifyProxyCountry": "US",
                },
            })
            items = _wait_and_collect(run, label=f"[HD] '{term}' (attempt {attempt})", timeout=120)
            if items:
                return items
            print(f"  [HD] '{term}': 0 results on attempt {attempt}/{max_retries}, retrying...")
        except Exception as e:
            print(f"  [HD] '{term}': attempt {attempt}/{max_retries} error: {e}")

    print(f"  [HD] '{term}': all {max_retries} attempts failed")
    return []


def scrape_target(term, max_results=24):
    """Apify automation-lab/target-scraper — keyword search with ratings & reviews."""
    if not _apify_client:
        print("  [Target] No APIFY_TOKEN")
        return []
    if is_over_budget():
        print(f"  [Target] '{term}': skipping — budget exceeded")
        return []
    try:
        run = _apify_client.actor("automation-lab/target-scraper").start(run_input={
            "searchQueries": [term],
            "maxProducts": max_results,
        })
        items = _wait_and_collect(run, label=f"[Target] '{term}'", timeout=180, max_items=max_results)
        return items
    except Exception as e:
        print(f"  [Target] ERROR: {e}")
        return []


def scrape_walmart(term, max_results=24):
    """Apify epctex/walmart-scraper actor."""
    if not _apify_client:
        print("  [Walmart] No APIFY_TOKEN")
        return []
    if is_over_budget():
        print(f"  [Walmart] '{term}': skipping — budget exceeded")
        return []
    try:
        run = _apify_client.actor("epctex/walmart-scraper").start(run_input={
            "search": term,
            "zipCode": DENVER_ZIP,
            "maxItems": max_results,
            "proxy": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
            },
        })
        items = _wait_and_collect(run, label=f"[Walmart] '{term}'", timeout=180)
        return items
    except Exception as e:
        print(f"  [Walmart] ERROR: {e}")
        return []


def scrape_lowes(term, max_results=24):
    """Apify automation-lab/google-shopping-scraper filtered to Lowe's."""
    if not _apify_client:
        print("  [Lowes] No APIFY_TOKEN")
        return []
    if is_over_budget():
        print(f"  [Lowes] '{term}': skipping — budget exceeded")
        return []
    try:
        run = _apify_client.actor("automation-lab/google-shopping-scraper").start(run_input={
            "queries": [f"Lowes {term}"],
            "maxProducts": max_results,
            "countryCode": "us",
            "language": "en",
        })
        items = _wait_and_collect(run, label=f"[Lowes] '{term}'", timeout=180, max_items=max_results)
        # Filter to only Lowe's merchant
        lowes_items = [i for i in items if "lowe" in (i.get("merchant") or "").lower()]
        print(f"  [Lowes] '{term}': {len(lowes_items)} Lowe's products (from {len(items)} total)")
        return lowes_items[:max_results]
    except Exception as e:
        print(f"  [Lowes] ERROR: {e}")
        return []


def scrape_lowes_batch(terms, max_results_per_term=24):
    """Scrape Lowe's for multiple terms in a single actor call."""
    if not _apify_client:
        print("  [Lowes] No APIFY_TOKEN")
        return {}
    if is_over_budget():
        print(f"  [Lowes] batch: skipping — budget exceeded")
        return {t: [] for t in terms}
    try:
        queries = [f"Lowes {t}" for t in terms]
        total_max = max_results_per_term * len(terms)
        run = _apify_client.actor("automation-lab/google-shopping-scraper").start(run_input={
            "queries": queries,
            "maxProducts": total_max,
            "countryCode": "us",
            "language": "en",
        })
        items = _wait_and_collect(run, label="[Lowes] batch", timeout=300, max_items=total_max)
        # Filter to Lowe's and bucket by query -> search term
        results = {t: [] for t in terms}
        for item in items:
            if "lowe" not in (item.get("merchant") or "").lower():
                continue
            query = item.get("query", "")
            for t in terms:
                if t.lower() in query.lower():
                    if len(results[t]) < max_results_per_term:
                        results[t].append(item)
                    break
        for t in terms:
            print(f"  [Lowes] '{t}': {len(results[t])} products")
        return results
    except Exception as e:
        print(f"  [Lowes] BATCH ERROR: {e}")
        return {t: [] for t in terms}


def scrape_target_batch(terms, max_results_per_term=24):
    """Scrape Target for multiple terms in a single actor call."""
    if not _apify_client:
        print("  [Target] No APIFY_TOKEN")
        return {}
    if is_over_budget():
        print(f"  [Target] batch: skipping — budget exceeded")
        return {t: [] for t in terms}
    try:
        total_max = max_results_per_term * len(terms)
        run = _apify_client.actor("automation-lab/target-scraper").start(run_input={
            "searchQueries": terms,
            "maxProducts": total_max,
        })
        items = _wait_and_collect(run, label="[Target] batch", timeout=300, max_items=total_max)
        # The actor returns items for all queries together; we distribute evenly
        # since the actor doesn't tag which query produced which result.
        per = max_results_per_term
        results = {}
        for i, t in enumerate(terms):
            start = i * per
            results[t] = items[start:start + per]
            print(f"  [Target] '{t}': {len(results[t])} products")
        return results
    except Exception as e:
        print(f"  [Target] BATCH ERROR: {e}")
        return {t: [] for t in terms}


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
