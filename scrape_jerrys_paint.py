"""
Scrape ALL paint products from Jerry's Ace Hardware (store #17892).
Uses the Mozu/Kibo commerce API with session auth.
"""

import json
import urllib.request
import http.cookiejar
from pathlib import Path

ACE_STORE_ID = "17892"
TENANT_ID = "24645"
BASE_URL = "https://www.acehardware.com"
OUTPUT_DIR = Path("output/ace")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PAGE_SIZE = 48


def get_session():
    """Visit the store page to get session cookies."""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    req = urllib.request.Request(
        f"{BASE_URL}/departments/paint-and-supplies?store={ACE_STORE_ID}",
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html",
        },
    )
    opener.open(req, timeout=15).read()
    return opener


def search_products(opener, query, start_index=0, page_size=PAGE_SIZE):
    """Search for products via the Mozu API."""
    url = (
        f"{BASE_URL}/api/commerce/catalog/storefront/productsearch/search"
        f"?query={query}&pageSize={page_size}&startIndex={start_index}"
    )
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
        "x-vol-tenant": TENANT_ID,
        "Referer": f"{BASE_URL}/departments/paint-and-supplies?store={ACE_STORE_ID}",
    })
    resp = opener.open(req, timeout=20)
    return json.loads(resp.read())


def fetch_all_paint(opener):
    """Paginate through all paint products."""
    all_items = []
    start = 0

    # First request to get total count
    data = search_products(opener, "paint", start_index=0)
    total = data["totalCount"]
    all_items.extend(data["items"])
    print(f"Total paint products: {total}")
    print(f"  Page 1: got {len(data['items'])} items")

    # Paginate through remaining pages
    while len(all_items) < total:
        start += PAGE_SIZE
        try:
            data = search_products(opener, "paint", start_index=start)
            new_items = data["items"]
            all_items.extend(new_items)
            print(f"  Page {start // PAGE_SIZE + 1}: got {len(new_items)} items (total: {len(all_items)}/{total})")
            if not new_items:
                break
        except Exception as e:
            print(f"  Error at offset {start}: {e}")
            # Try refreshing session
            opener = get_session()
            try:
                data = search_products(opener, "paint", start_index=start)
                all_items.extend(data["items"])
                print(f"  Retried page {start // PAGE_SIZE + 1}: got {len(data['items'])} items")
            except Exception as e2:
                print(f"  Retry failed: {e2}, stopping.")
                break

    return all_items, opener


def extract_product(item):
    """Extract clean product data from a Mozu API item."""
    content = item.get("content", {})
    price_data = item.get("price", {})
    cats = [c.get("content", {}).get("name", "") for c in item.get("categories", [])]
    properties = {}
    for prop in item.get("properties", []):
        name = prop.get("attributeFQN", prop.get("name", ""))
        vals = prop.get("values", [])
        if vals:
            properties[name] = vals[0].get("stringValue", vals[0].get("value", ""))

    return {
        "name": content.get("productName", ""),
        "sku": item.get("productCode", ""),
        "upc": item.get("upc", ""),
        "price": price_data.get("price"),
        "sale_price": price_data.get("salePrice"),
        "msrp": price_data.get("msrp"),
        "brand": properties.get("tenant~brand", ""),
        "categories": cats,
        "url": f"{BASE_URL}{content.get('seoFriendlyUrl', '')}",
        "image": content.get("productImages", [{}])[0].get("imageUrl", "") if content.get("productImages") else "",
        "in_stock": item.get("inventoryInfo", {}).get("onlineStockAvailable", False),
        "description": content.get("productShortDescription", ""),
    }


if __name__ == "__main__":
    print(f"Scraping ALL paint products from Jerry's Ace Hardware #{ACE_STORE_ID}")
    print()

    opener = get_session()
    raw_items, opener = fetch_all_paint(opener)

    # Clean up the data
    products = [extract_product(item) for item in raw_items]

    # Summary by brand
    brands = {}
    for p in products:
        b = p["brand"] or "Unknown"
        brands[b] = brands.get(b, 0) + 1

    print(f"\n{'='*60}")
    print(f"TOTAL: {len(products)} paint products")
    print(f"{'='*60}")
    print(f"\nBy brand:")
    for brand, count in sorted(brands.items(), key=lambda x: -x[1]):
        print(f"  {brand}: {count}")

    print(f"\nSample products:")
    for p in products[:10]:
        print(f"  {p['brand']:20s} | {p['name'][:60]} | ${p['price']}")

    # Save
    with open(OUTPUT_DIR / "jerrys_paint_all.json", "w") as f:
        json.dump(products, f, indent=2)
    print(f"\nSaved {len(products)} products to output/ace/jerrys_paint_all.json")

    # Also save raw for debugging
    with open(OUTPUT_DIR / "jerrys_paint_raw.json", "w") as f:
        json.dump(raw_items, f, indent=2)
