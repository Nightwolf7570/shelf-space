"""
Test multiple Home Depot and Target actors to find ones that work.
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
from apify_client import ApifyClient

load_dotenv()

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
client = ApifyClient(APIFY_TOKEN)

DENVER_ZIP = "80205"
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def test_actor(name, actor_id, run_input):
    print(f"\n{'='*60}")
    print(f"TESTING: {name}")
    print(f"Actor: {actor_id}")
    print(f"{'='*60}")

    try:
        result = client.actor(actor_id).call(run_input=run_input)
        if not result:
            print(f"  FAILED: Actor returned None")
            return None

        dataset = client.dataset(result["defaultDatasetId"])
        items = dataset.list_items().items

        print(f"  GOT {len(items)} items")

        if items:
            # Save results
            safe_name = name.lower().replace(' ', '_').replace('/', '_')
            out_file = OUTPUT_DIR / f"{safe_name}.json"
            with open(out_file, "w") as f:
                json.dump(items, f, indent=2)
            print(f"  Saved to {out_file}")

            # Show useful fields from first item
            item = items[0]
            for key in ['name', 'title', 'productName', 'product_name', 'product_title',
                        'price', 'currentPrice', 'salePrice', 'brand', 'category',
                        'url', 'productUrl', 'link', 'rating', 'reviewCount']:
                if key in item and item[key]:
                    print(f"    {key}: {item[key]}")
            # Also show first 10 keys
            print(f"  First 10 keys: {list(item.keys())[:10]}")

        return items

    except Exception as e:
        print(f"  ERROR: {e}")
        return None


if __name__ == "__main__":
    print("Testing multiple Home Depot & Target actors")
    print(f"Denver ZIP: {DENVER_ZIP}\n")

    # ---- HOME DEPOT ACTORS ----

    print("\n" + "="*60)
    print("HOME DEPOT ACTORS")
    print("="*60)

    test_actor(
        "HD - crawlerbros",
        "crawlerbros/homedepot-scraper",
        {"searchQuery": "paint", "zipCode": DENVER_ZIP, "maxResults": 5},
    )

    test_actor(
        "HD - sovereigntaylor",
        "sovereigntaylor/homedepot-scraper",
        {"searchQuery": "paint", "zipCode": DENVER_ZIP, "maxResults": 5},
    )

    test_actor(
        "HD - mcdowell",
        "mcdowell/home-depot",
        {"searchQuery": "paint", "zipCode": DENVER_ZIP, "maxResults": 5},
    )

    test_actor(
        "HD - jupri",
        "jupri/homedepot",
        {"searchQuery": "paint", "zipCode": DENVER_ZIP, "maxResults": 5},
    )

    # ---- TARGET ACTORS ----

    print("\n" + "="*60)
    print("TARGET ACTORS")
    print("="*60)

    test_actor(
        "Target - axlymxp store",
        "axlymxp/target-store-scraper",
        {"searchKeyword": DENVER_ZIP, "searchRadius": 10, "resultsLimit": 5},
    )

    test_actor(
        "Target - getdataforme (url variant)",
        "getdataforme/target-product-scraper",
        {"url": "https://www.target.com/c/paint-painting-supplies-tools/-/N-5xth0", "maxItems": 5},
    )

    test_actor(
        "Target - silentflow",
        "silentflow/target-scraper",
        {"search": "paint", "maxItems": 5},
    )

    test_actor(
        "Target - misceres",
        "misceres/target-scraper",
        {"searchQuery": "paint", "maxItems": 5},
    )

    print("\nDone!")
