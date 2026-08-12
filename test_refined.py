"""
Refined tests: Target Redsky with better search terms, HD alternative approaches.
"""

import json
import os
from pathlib import Path
import urllib.request
import urllib.parse
from dotenv import load_dotenv
from apify_client import ApifyClient

load_dotenv()

client = ApifyClient(os.getenv("APIFY_TOKEN"))
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def target_redsky(search_term, filename):
    """Query Target Redsky API."""
    print(f"\nTARGET Redsky: '{search_term}'")
    api_key = os.environ.get("TARGET_REDSKY_KEY", "")
    store_id = "3330"
    url = (
        f"https://redsky.target.com/redsky_aggregations/v1/web/plp_search_v2"
        f"?key={api_key}&channel=WEB&count=24"
        f"&default_purchasability_filter=true"
        f"&keyword={urllib.parse.quote(search_term)}"
        f"&offset=0&page=%2Fs%2F{urllib.parse.quote(search_term)}"
        f"&pricing_store_id={store_id}&store_ids={store_id}"
        f"&visitor_id=test123&zip=80205"
    )
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        products = data.get("data", {}).get("search", {}).get("products", [])
        results = []
        for p in products:
            item = p.get("item", {})
            price_data = p.get("price", {})
            results.append({
                "name": item.get("product_description", {}).get("title", ""),
                "brand": item.get("primary_brand", {}).get("name", ""),
                "price": price_data.get("formatted_current_price", ""),
                "tcin": item.get("tcin", ""),
                "dpci": item.get("dpci", ""),
                "url": f"https://www.target.com{item.get('enrichment', {}).get('buy_url', '')}",
                "category": item.get("product_classification", {}).get("product_type_name", ""),
                "image": item.get("enrichment", {}).get("images", {}).get("primary_image_url", ""),
            })
        print(f"  Got {len(results)} products")
        for r in results[:3]:
            print(f"    - {r['brand']}: {r['name'][:70]} — {r['price']}")
        with open(OUTPUT_DIR / filename, "w") as f:
            json.dump(results, f, indent=2)
        return results
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def test_hd_via_serp():
    """Try Apify's Google Search scraper to get Home Depot product results."""
    print(f"\nHD via Google Search Results Scraper")
    try:
        result = client.actor("apify/google-search-scraper").call(run_input={
            "queries": "site:homedepot.com paint Denver",
            "maxPagesPerQuery": 1,
            "resultsPerPage": 20,
            "languageCode": "en",
            "countryCode": "us",
        })
        if not result:
            print("  FAILED")
            return None
        items = client.dataset(result["defaultDatasetId"]).list_items().items
        print(f"  Got {len(items)} result pages")
        if items:
            organic = items[0].get("organicResults", [])
            print(f"  Got {len(organic)} organic results")
            results = []
            for r in organic[:10]:
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "description": r.get("description", ""),
                })
                print(f"    - {r.get('title', '')[:80]}")
            with open(OUTPUT_DIR / "hd_google.json", "w") as f:
                json.dump(results, f, indent=2)
            return results
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def test_hd_clearance_paint():
    """Use the working clearance scraper but filter to paint category."""
    print(f"\nHD Clearance Scraper — paint category only")
    try:
        result = client.actor("scrapyspider/home-depot-clearance-scraper").call(run_input={
            "zipCode": "80205",
            "maxItems": 50,
            "categoryKeywords": ["paint"],
        })
        if not result:
            print("  FAILED")
            return None
        items = client.dataset(result["defaultDatasetId"]).list_items().items
        print(f"  Got {len(items)} items")
        paint_items = []
        for it in items:
            ids = it.get("identifiers", {})
            pricing = it.get("pricing", {})
            tax = it.get("taxonomy", {})
            cats = [b.get("label", "") for b in tax.get("breadCrumbs", [])]
            paint_items.append({
                "name": ids.get("productLabel", ""),
                "brand": ids.get("brandName", ""),
                "price": pricing.get("value"),
                "original_price": pricing.get("original"),
                "item_id": ids.get("itemId"),
                "url": f"https://www.homedepot.com{ids.get('canonicalUrl', '')}",
                "categories": cats,
            })
        for r in paint_items[:5]:
            print(f"    - {r['brand']}: {r['name'][:60]} — ${r['price']}")
            print(f"      Categories: {' > '.join(r['categories'])}")
        with open(OUTPUT_DIR / "hd_clearance_paint.json", "w") as f:
            json.dump(paint_items, f, indent=2)
        return paint_items
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


if __name__ == "__main__":
    # Target searches
    target_redsky("interior wall paint", "target_interior_paint.json")
    target_redsky("cleaning supplies", "target_cleaning.json")

    # Home Depot approaches
    test_hd_via_serp()
    test_hd_clearance_paint()

    print("\nDone!")
