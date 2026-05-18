"""
Hit Home Depot's browse GraphQL API directly — the same API the clearance scraper uses.
Target the Paint category specifically for Denver store.
"""

import json
import urllib.request

OUTPUT_DIR = "output"

# HD's GraphQL browse endpoint (same one the clearance scraper uses)
GRAPHQL_URL = "https://www.homedepot.com/federation-gateway/graphql?opname=searchModel"

# Denver area HD store
STORE_ID = "1513"  # Home Depot on Colorado Blvd, Denver
ZIP = "80205"

# Paint category navParam from HD's URL structure
# /b/Paint/N-5yc1vZar2d = top-level Paint
# /b/Paint-Interior-Paint/N-5yc1vZar2d = Interior Paint
PAINT_CATEGORIES = {
    "Interior Paint": "5yc1vZbzg4",
    "Exterior Paint": "5yc1vZbzg3",
    "Paint": "5yc1vZar2d",
}


def fetch_hd_category(category_name, nav_param, page_size=24):
    """Fetch products from HD's browse API using navParam."""
    print(f"\n  Trying category: {category_name} (navParam: {nav_param})")

    # This is the GraphQL query the browse pages use
    payload = json.dumps({
        "operationName": "searchModel",
        "variables": {
            "channel": "DESKTOP",
            "additionalSearchParams": {
                "deliveryZip": ZIP,
                "store": STORE_ID,
            },
            "filter": {},
            "navParam": nav_param,
            "orderBy": {"field": "TOP_SELLERS", "order": "ASC"},
            "pageSize": page_size,
            "startIndex": 0,
            "storefilter": "ALL",
        },
        "query": """query searchModel($channel: Channel!, $additionalSearchParams: AdditionalParams, $filter: ProductFilter, $navParam: String, $orderBy: ProductSort, $pageSize: Int, $startIndex: Int, $storefilter: StoreFilter) {
            searchModel(channel: $channel, additionalSearchParams: $additionalSearchParams, filter: $filter, navParam: $navParam, orderBy: $orderBy, pageSize: $pageSize, startIndex: $startIndex, storefilter: $storefilter) {
                products {
                    identifiers {
                        productLabel
                        brandName
                        modelNumber
                        canonicalUrl
                        itemId
                    }
                    pricing {
                        value
                        original
                    }
                    reviews {
                        ratingsReviews {
                            averageRating
                            totalReviews
                        }
                    }
                    info {
                        categoryHierarchy
                    }
                }
                searchReport {
                    totalProducts
                }
            }
        }""",
    }).encode()

    try:
        req = urllib.request.Request(GRAPHQL_URL, data=payload, headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "x-experience-name": "general-merchandise",
            "x-current-url": f"/b/Paint/N-{nav_param}",
            "Origin": "https://www.homedepot.com",
            "Referer": "https://www.homedepot.com/",
        }, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        search = data.get("data", {}).get("searchModel", {})
        total = search.get("searchReport", {}).get("totalProducts", 0)
        products = search.get("products", [])
        print(f"    Total available: {total}, returned: {len(products)}")

        results = []
        for p in products:
            ids = p.get("identifiers", {})
            pricing = p.get("pricing", {})
            reviews = p.get("reviews", {}).get("ratingsReviews", {})
            results.append({
                "name": ids.get("productLabel", ""),
                "brand": ids.get("brandName", ""),
                "price": pricing.get("value"),
                "original_price": pricing.get("original"),
                "model": ids.get("modelNumber", ""),
                "item_id": ids.get("itemId", ""),
                "url": f"https://www.homedepot.com{ids.get('canonicalUrl', '')}",
                "rating": reviews.get("averageRating"),
                "review_count": reviews.get("totalReviews"),
                "category": category_name,
            })

        for r in results[:5]:
            print(f"    - {r['brand']}: {r['name'][:60]} — ${r['price']}")

        return results

    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        print(f"    HTTP {e.code}: {body}")
        return []
    except Exception as e:
        print(f"    ERROR: {e}")
        return []


def try_search_api(keyword, page_size=24):
    """Try HD's search GraphQL endpoint."""
    print(f"\n  Trying search: '{keyword}'")

    payload = json.dumps({
        "operationName": "searchModel",
        "variables": {
            "channel": "DESKTOP",
            "keyword": keyword,
            "additionalSearchParams": {
                "deliveryZip": ZIP,
                "store": STORE_ID,
            },
            "navParam": "",
            "orderBy": {"field": "TOP_SELLERS", "order": "ASC"},
            "pageSize": page_size,
            "startIndex": 0,
            "storefilter": "ALL",
        },
        "query": """query searchModel($channel: Channel!, $keyword: String, $additionalSearchParams: AdditionalParams, $navParam: String, $orderBy: ProductSort, $pageSize: Int, $startIndex: Int, $storefilter: StoreFilter) {
            searchModel(channel: $channel, keyword: $keyword, additionalSearchParams: $additionalSearchParams, navParam: $navParam, orderBy: $orderBy, pageSize: $pageSize, startIndex: $startIndex, storefilter: $storefilter) {
                products {
                    identifiers {
                        productLabel
                        brandName
                        modelNumber
                        canonicalUrl
                        itemId
                    }
                    pricing {
                        value
                        original
                    }
                    reviews {
                        ratingsReviews {
                            averageRating
                            totalReviews
                        }
                    }
                }
                searchReport {
                    totalProducts
                }
            }
        }""",
    }).encode()

    try:
        req = urllib.request.Request(GRAPHQL_URL, data=payload, headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "x-experience-name": "general-merchandise",
            "x-current-url": f"/s/{keyword}",
            "Origin": "https://www.homedepot.com",
            "Referer": "https://www.homedepot.com/",
        }, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        search = data.get("data", {}).get("searchModel", {})
        total = search.get("searchReport", {}).get("totalProducts", 0)
        products = search.get("products", [])
        print(f"    Total: {total}, returned: {len(products)}")

        for p in products[:5]:
            ids = p.get("identifiers", {})
            pr = p.get("pricing", {})
            print(f"    - {ids.get('brandName')}: {ids.get('productLabel', '')[:60]} — ${pr.get('value')}")

        results = []
        for p in products:
            ids = p.get("identifiers", {})
            pricing = p.get("pricing", {})
            reviews = p.get("reviews", {}).get("ratingsReviews", {})
            results.append({
                "name": ids.get("productLabel", ""),
                "brand": ids.get("brandName", ""),
                "price": pricing.get("value"),
                "original_price": pricing.get("original"),
                "model": ids.get("modelNumber", ""),
                "item_id": ids.get("itemId", ""),
                "url": f"https://www.homedepot.com{ids.get('canonicalUrl', '')}",
                "rating": reviews.get("averageRating"),
                "review_count": reviews.get("totalReviews"),
            })
        return results

    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        print(f"    HTTP {e.code}: {body}")
        return []
    except Exception as e:
        print(f"    ERROR: {e}")
        return []


if __name__ == "__main__":
    print("HOME DEPOT — Direct GraphQL API Tests")
    print(f"Store: {STORE_ID}, ZIP: {ZIP}")

    all_results = []

    # Try category browse
    print("\n=== Category Browse ===")
    for name, nav in PAINT_CATEGORIES.items():
        results = fetch_hd_category(name, nav)
        all_results.extend(results)

    # Try keyword search
    print("\n=== Keyword Search ===")
    results = try_search_api("interior paint")
    all_results.extend(results)

    results = try_search_api("cleaning supplies")
    all_results.extend(results)

    if all_results:
        with open(f"{OUTPUT_DIR}/homedepot_products.json", "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\nSaved {len(all_results)} total products to output/homedepot_products.json")
    else:
        print("\nNo products retrieved from any approach.")

    print("\nDone!")
