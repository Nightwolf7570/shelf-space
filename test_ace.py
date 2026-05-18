"""
Test scraping Jerry's Ace Hardware catalog (store #17892).
Try multiple approaches: direct HTTP, SerpAPI, Apify.
"""

import json
import os
import urllib.request
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
OUTPUT_DIR = Path("output/ace")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ACE_STORE_ID = "17892"
ACE_BASE = "https://www.acehardware.com"


def try_ace_api():
    """Try Ace Hardware's internal API endpoints."""
    print("=" * 60)
    print("ACE — Direct API attempts")
    print("=" * 60)

    # Try their search/product API
    endpoints = [
        # Product search API
        (
            "Search API (paint)",
            f"{ACE_BASE}/api/search?query=paint&storeId={ACE_STORE_ID}&pageSize=20",
        ),
        # Category browse
        (
            "Category API (paint)",
            f"{ACE_BASE}/api/v2/browse/category/paint-and-supplies?storeId={ACE_STORE_ID}&pageSize=20",
        ),
        # Store inventory
        (
            "Store products",
            f"{ACE_BASE}/api/v2/stores/{ACE_STORE_ID}/products?pageSize=20",
        ),
        # Algolia-style search (many retail sites use this)
        (
            "Search v2",
            f"{ACE_BASE}/api/v2/search?q=paint&store={ACE_STORE_ID}&limit=20",
        ),
    ]

    for name, url in endpoints:
        print(f"\n  Trying: {name}")
        print(f"  URL: {url[:100]}...")
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": f"{ACE_BASE}/store-details/{ACE_STORE_ID}",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                print(f"  SUCCESS — got response with keys: {list(data.keys())[:10]}")
                safe = name.lower().replace(' ', '_').replace('(', '').replace(')', '')
                with open(OUTPUT_DIR / f"api_{safe}.json", "w") as f:
                    json.dump(data, f, indent=2)
                return data
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code}")
        except Exception as e:
            print(f"  ERROR: {e}")

    return None


def try_ace_store_page():
    """Fetch the store detail page and look for embedded JSON data."""
    print("\n" + "=" * 60)
    print("ACE — Store page embedded data")
    print("=" * 60)

    urls = [
        f"{ACE_BASE}/store-details/{ACE_STORE_ID}",
        f"{ACE_BASE}/departments/paint-and-supplies?store={ACE_STORE_ID}",
    ]

    for url in urls:
        print(f"\n  Fetching: {url}")
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
                print(f"  Got {len(html)} bytes of HTML")

                # Look for __NEXT_DATA__ or similar embedded JSON
                for marker in ["__NEXT_DATA__", "__INITIAL_STATE__", "window.__data",
                               "window.__PRELOADED_STATE__", "application/ld+json"]:
                    if marker in html:
                        print(f"  Found embedded data marker: {marker}")
                        # Extract JSON
                        if marker == "application/ld+json":
                            import re
                            matches = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
                            if matches:
                                for i, m in enumerate(matches):
                                    try:
                                        data = json.loads(m)
                                        print(f"    ld+json block {i}: type={data.get('@type', '?')}")
                                    except:
                                        pass
                        else:
                            idx = html.index(marker)
                            snippet = html[idx:idx+500]
                            print(f"    Preview: {snippet[:200]}")

                # Check for product-like patterns
                import re
                product_links = re.findall(r'href="(/product/[^"]+)"', html)
                print(f"  Found {len(product_links)} product links")
                for link in product_links[:5]:
                    print(f"    {link}")

        except Exception as e:
            print(f"  ERROR: {e}")


def try_serpapi_ace():
    """Use SerpAPI to search for Ace Hardware products."""
    print("\n" + "=" * 60)
    print("ACE — SerpAPI Google Shopping")
    print("=" * 60)

    if not SERPAPI_KEY:
        print("  No SERPAPI_KEY set")
        return None

    from serpapi import GoogleSearch

    # Google Shopping filtered to acehardware.com
    params = {
        "engine": "google_shopping",
        "q": "Ace Hardware paint",
        "location": "Denver, Colorado, United States",
        "hl": "en",
        "gl": "us",
        "num": 20,
        "api_key": SERPAPI_KEY,
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        products = results.get("shopping_results", [])
        print(f"  Got {len(products)} shopping results")

        ace_products = [p for p in products if "ace" in p.get("source", "").lower()]
        print(f"  Filtered to Ace Hardware source: {len(ace_products)}")

        all_items = products  # Keep all for now
        with open(OUTPUT_DIR / "serpapi_shopping.json", "w") as f:
            json.dump(all_items, f, indent=2)

        for p in all_items[:5]:
            print(f"  - {p.get('title', '')[:60]}")
            print(f"    {p.get('price', '?')} | {p.get('source', '?')}")

        return all_items

    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def try_ace_sitemap():
    """Check if Ace has a sitemap with product URLs."""
    print("\n" + "=" * 60)
    print("ACE — Sitemap check")
    print("=" * 60)

    urls = [
        f"{ACE_BASE}/robots.txt",
        f"{ACE_BASE}/sitemap.xml",
    ]

    for url in urls:
        print(f"\n  Fetching: {url}")
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0",
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8", errors="replace")[:3000]
                print(f"  Got {len(content)} chars")
                # Show relevant lines
                for line in content.split('\n'):
                    if any(kw in line.lower() for kw in ['sitemap', 'product', 'disallow', 'allow']):
                        print(f"    {line.strip()}")
        except Exception as e:
            print(f"  ERROR: {e}")


if __name__ == "__main__":
    print("Testing Jerry's Ace Hardware scraping approaches")
    print(f"Store ID: {ACE_STORE_ID}\n")

    try_ace_api()
    try_ace_store_page()
    try_serpapi_ace()
    try_ace_sitemap()

    print("\nDone!")
