"""
Try every approach to get Target product data.
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
from apify_client import ApifyClient

load_dotenv()

client = ApifyClient(os.getenv("APIFY_TOKEN"))
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def test_actor(name, actor_id, run_input):
    print(f"\n{'='*60}")
    print(f"TESTING: {name} ({actor_id})")
    print(f"{'='*60}")
    try:
        result = client.actor(actor_id).call(run_input=run_input)
        if not result:
            print("  FAILED: None")
            return None
        items = client.dataset(result["defaultDatasetId"]).list_items().items
        print(f"  GOT {len(items)} items")
        if items:
            safe = name.lower().replace(' ', '_').replace('/', '_')
            with open(OUTPUT_DIR / f"{safe}.json", "w") as f:
                json.dump(items, f, indent=2)
            item = items[0]
            print(f"  Keys: {list(item.keys())[:15]}")
            for k in ['name', 'title', 'productName', 'price', 'brand', 'url',
                       'product_name', 'product_title', 'current_price']:
                if k in item and item[k]:
                    print(f"    {k}: {str(item[k])[:120]}")
        return items
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


if __name__ == "__main__":
    print("Target product scraping attempts\n")

    # 1. getdataforme with single product URL to test if it works at all
    test_actor(
        "Target single product",
        "getdataforme/target-product-scraper",
        {"url": "https://www.target.com/p/crayola-washable-kids-paint-set-10ct/-/A-14150888"},
    )

    # 2. getdataforme with search results page
    test_actor(
        "Target search page",
        "getdataforme/target-product-scraper",
        {"url": "https://www.target.com/s?searchTerm=interior+paint"},
    )

    # 3. Try the Target Shop Scraper (different actor)
    test_actor(
        "Target shop scraper",
        "getdataforme/target-shop-scraper-client",
        {"url": "https://www.target.com/s?searchTerm=paint", "maxItems": 10},
    )

    # 4. Try Google Shopping via Apify to get Target results
    test_actor(
        "Google Shopping paint",
        "apify/google-shopping-scraper",
        {
            "queries": "paint site:target.com",
            "maxResultsPerQuery": 10,
            "countryCode": "us",
        },
    )

    # 5. Try a generic website content crawler on Target
    test_actor(
        "Target WCC",
        "apify/website-content-crawler",
        {
            "startUrls": [{"url": "https://www.target.com/s?searchTerm=paint"}],
            "maxCrawlPages": 1,
        },
    )

    print("\nDone!")
