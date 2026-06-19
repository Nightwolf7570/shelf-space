"""
Direct API approach: Hit Target Redsky API and Home Depot GraphQL API directly.
No Apify needed — just HTTP requests.
"""

import json
import os
from pathlib import Path
import urllib.request
import urllib.parse

from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def test_target_redsky():
    """Target's Redsky API is public — query it directly."""
    print("=" * 60)
    print("TARGET — Redsky API (direct)")
    print("=" * 60)

    # Target Redsky API endpoint for search
    api_key = os.getenv("TARGET_REDSKY_KEY", "")
    store_id = "3330"  # A Denver-area Target store
    zip_code = "80205"

    # Search for paint
    search_term = "paint"
    url = (
        f"https://redsky.target.com/redsky_aggregations/v1/web/plp_search_v2"
        f"?key={api_key}"
        f"&channel=WEB"
        f"&count=20"
        f"&default_purchasability_filter=true"
        f"&keyword={urllib.parse.quote(search_term)}"
        f"&offset=0"
        f"&page=%2Fs%2F{urllib.parse.quote(search_term)}"
        f"&pricing_store_id={store_id}"
        f"&store_ids={store_id}"
        f"&visitor_id=test123"
        f"&zip={zip_code}"
    )

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        products = data.get("data", {}).get("search", {}).get("products", [])
        print(f"  GOT {len(products)} products")

        results = []
        for p in products[:10]:
            item = p.get("item", {})
            price_data = p.get("price", {})
            results.append({
                "name": item.get("product_description", {}).get("title", ""),
                "brand": item.get("primary_brand", {}).get("name", ""),
                "price": price_data.get("formatted_current_price", ""),
                "tcin": item.get("tcin", ""),
                "url": f"https://www.target.com{item.get('enrichment', {}).get('buy_url', '')}",
                "rating": item.get("ratings_and_reviews", {}).get("statistics", {}).get("rating", {}).get("average", ""),
                "review_count": item.get("ratings_and_reviews", {}).get("statistics", {}).get("review_count", 0),
            })

        for i, r in enumerate(results[:5]):
            print(f"  {i+1}. {r['brand']} — {r['name'][:80]}")
            print(f"     Price: {r['price']} | Rating: {r['rating']} ({r['review_count']} reviews)")

        with open(OUTPUT_DIR / "target_redsky.json", "w") as f:
            json.dump(results, f, indent=2)
        print(f"  Saved {len(results)} items to output/target_redsky.json")
        return results

    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def test_homedepot_graphql():
    """Home Depot's search uses a GraphQL API — try hitting it directly."""
    print("\n" + "=" * 60)
    print("HOME DEPOT — Search API (direct)")
    print("=" * 60)

    url = "https://www.homedepot.com/federation-gateway/graphql?opname=searchModel"

    query = """
    query searchModel($keyword: String!, $storeId: String, $zipCode: String, $pageSize: Int) {
        searchModel(keyword: $keyword, storefilter: $storeId, zipCode: $zipCode, pageSize: $pageSize) {
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
                media {
                    images {
                        url
                    }
                }
            }
        }
    }
    """

    payload = json.dumps({
        "operationName": "searchModel",
        "variables": {
            "keyword": "paint",
            "storeId": "1513",  # Denver HD store
            "zipCode": "80205",
            "pageSize": 20,
        },
        "query": query,
    }).encode()

    try:
        req = urllib.request.Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
            "x-experience-name": "general-merchandise",
            "x-current-url": "/s/paint",
        }, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        products = data.get("data", {}).get("searchModel", {}).get("products", [])
        print(f"  GOT {len(products)} products")

        results = []
        for p in products[:10]:
            ids = p.get("identifiers", {})
            pricing = p.get("pricing", {})
            reviews = p.get("reviews", {}).get("ratingsReviews", {})
            results.append({
                "name": ids.get("productLabel", ""),
                "brand": ids.get("brandName", ""),
                "price": pricing.get("value"),
                "original_price": pricing.get("original"),
                "model": ids.get("modelNumber", ""),
                "url": f"https://www.homedepot.com{ids.get('canonicalUrl', '')}",
                "rating": reviews.get("averageRating"),
                "review_count": reviews.get("totalReviews"),
            })

        for i, r in enumerate(results[:5]):
            print(f"  {i+1}. {r['brand']} — {r['name'][:80]}")
            print(f"     ${r['price']} | Rating: {r['rating']} ({r['review_count']} reviews)")

        with open(OUTPUT_DIR / "homedepot_search.json", "w") as f:
            json.dump(results, f, indent=2)
        print(f"  Saved {len(results)} items to output/homedepot_search.json")
        return results

    except Exception as e:
        print(f"  ERROR: {e}")
        return None


if __name__ == "__main__":
    test_target_redsky()
    test_homedepot_graphql()
    print("\nDone!")
