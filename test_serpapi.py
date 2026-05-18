"""
SerpAPI approach: scrape Target, Home Depot, and Lowe's product data
using Google Shopping results filtered by store.
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
from serpapi import GoogleSearch

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
if not SERPAPI_KEY:
    raise RuntimeError("Set SERPAPI_KEY in .env")

OUTPUT_DIR = Path("output/serpapi")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DENVER_ZIP = "80205"


def search_store(store_name, query="paint", num=20):
    """Use Google Shopping via SerpAPI filtered to a specific store."""
    print(f"\n{'='*60}")
    print(f"SEARCHING: {store_name} — query: '{query}'")
    print(f"{'='*60}")

    params = {
        "engine": "google_shopping",
        "q": f"{query} site:{get_site(store_name)} OR {store_name} {query}",
        "location": "Denver, Colorado, United States",
        "hl": "en",
        "gl": "us",
        "num": num,
        "api_key": SERPAPI_KEY,
    }

    # For Google Shopping, use a simpler query
    params["q"] = f"{store_name} {query}"

    try:
        search = GoogleSearch(params)
        results = search.get_dict()

        shopping_results = results.get("shopping_results", [])
        print(f"  Got {len(shopping_results)} shopping results")

        if shopping_results:
            safe = store_name.lower().replace("'", "").replace(" ", "_")
            outfile = OUTPUT_DIR / f"{safe}_shopping.json"
            with open(outfile, "w") as f:
                json.dump(shopping_results, f, indent=2)
            print(f"  Saved to {outfile}")

            for i, item in enumerate(shopping_results[:3]):
                print(f"\n  --- Item {i+1} ---")
                print(f"    title:  {item.get('title', 'N/A')[:80]}")
                print(f"    price:  {item.get('price', 'N/A')}")
                print(f"    source: {item.get('source', 'N/A')}")
                print(f"    link:   {item.get('link', 'N/A')[:80]}")

        return shopping_results

    except Exception as e:
        print(f"  ERROR: {e}")
        return []


def search_store_organic(store_name, query="paint", num=20):
    """Fallback: use regular Google search scoped to the store's domain."""
    print(f"\n{'='*60}")
    print(f"ORGANIC SEARCH: {store_name} — query: '{query}'")
    print(f"{'='*60}")

    site = get_site(store_name)
    params = {
        "engine": "google",
        "q": f"site:{site} {query}",
        "location": "Denver, Colorado, United States",
        "hl": "en",
        "gl": "us",
        "num": num,
        "api_key": SERPAPI_KEY,
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()

        organic = results.get("organic_results", [])
        print(f"  Got {len(organic)} organic results")

        if organic:
            safe = store_name.lower().replace("'", "").replace(" ", "_")
            outfile = OUTPUT_DIR / f"{safe}_organic.json"
            with open(outfile, "w") as f:
                json.dump(organic, f, indent=2)
            print(f"  Saved to {outfile}")

            for i, item in enumerate(organic[:3]):
                print(f"\n  --- Item {i+1} ---")
                print(f"    title: {item.get('title', 'N/A')[:80]}")
                print(f"    link:  {item.get('link', 'N/A')[:80]}")
                snippet = item.get("snippet", "N/A")[:100]
                print(f"    snippet: {snippet}")

        return organic

    except Exception as e:
        print(f"  ERROR: {e}")
        return []


def get_site(store_name):
    sites = {
        "Target": "target.com",
        "Home Depot": "homedepot.com",
        "Lowes": "lowes.com",
    }
    return sites.get(store_name, "")


def try_native_engine(store_name, query="paint"):
    """Try SerpAPI's native retailer engines (Home Depot and Walmart have dedicated engines)."""
    engine_map = {
        "Home Depot": "home_depot",
    }
    engine = engine_map.get(store_name)
    if not engine:
        return None

    print(f"\n{'='*60}")
    print(f"NATIVE ENGINE: {store_name} ({engine}) — query: '{query}'")
    print(f"{'='*60}")

    params = {
        "engine": engine,
        "q": query,
        "api_key": SERPAPI_KEY,
    }

    # Home Depot supports delivery_zip
    if engine == "home_depot":
        params["delivery_zip"] = DENVER_ZIP

    try:
        search = GoogleSearch(params)
        results = search.get_dict()

        products = results.get("products", [])
        print(f"  Got {len(products)} products")

        if products:
            safe = store_name.lower().replace("'", "").replace(" ", "_")
            outfile = OUTPUT_DIR / f"{safe}_native.json"
            with open(outfile, "w") as f:
                json.dump(products, f, indent=2)
            print(f"  Saved to {outfile}")

            for i, item in enumerate(products[:3]):
                print(f"\n  --- Item {i+1} ---")
                print(f"    title: {item.get('title', 'N/A')[:80]}")
                print(f"    price: {item.get('price', 'N/A')}")
                print(f"    rating: {item.get('rating', 'N/A')}")
                link = item.get("link", item.get("serpapi_product_page_link", "N/A"))
                print(f"    link:  {str(link)[:80]}")

        return products

    except Exception as e:
        print(f"  ERROR: {e}")
        return None


if __name__ == "__main__":
    print("MysteryScraper — SerpAPI Approach")
    print(f"Target area: Denver, CO {DENVER_ZIP}")
    print(f"Search term: paint\n")

    summary = {}

    for store in ["Home Depot", "Target", "Lowes"]:
        # 1. Try native engine first (only Home Depot has one)
        native = try_native_engine(store, "paint")
        if native:
            summary[f"{store} (native)"] = len(native)

        # 2. Google Shopping results
        shopping = search_store(store, "paint")
        summary[f"{store} (shopping)"] = len(shopping)

        # 3. Organic site-scoped search
        organic = search_store_organic(store, "paint")
        summary[f"{store} (organic)"] = len(organic)

    # Summary
    print(f"\n\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for name, count in summary.items():
        status = "OK" if count > 0 else "FAILED"
        print(f"  {name:30s}: {status} ({count} items)")
