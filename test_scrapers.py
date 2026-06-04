"""
Test script: validate that Apify actors return real product data for Denver area retailers.
Tests one actor per retailer with "paint" as the search term.
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


def test_actor(name, actor_id, run_input, max_display=3):
    """Run an actor and print a sample of results."""
    print(f"\n{'='*60}")
    print(f"TESTING: {name}")
    print(f"Actor: {actor_id}")
    print(f"Input: {json.dumps(run_input, indent=2)}")
    print(f"{'='*60}")

    try:
        result = client.actor(actor_id).call(run_input=run_input)
        if not result:
            print(f"  FAILED: Actor returned None")
            return None

        dataset = client.dataset(result["defaultDatasetId"])
        items = dataset.list_items().items

        print(f"  SUCCESS: Got {len(items)} items")

        # Save full results
        out_file = OUTPUT_DIR / f"{name.lower().replace(' ', '_')}.json"
        with open(out_file, "w") as f:
            json.dump(items, f, indent=2)
        print(f"  Saved to {out_file}")

        # Show sample
        for i, item in enumerate(items[:max_display]):
            print(f"\n  --- Item {i+1} ---")
            for key, val in list(item.items())[:8]:
                print(f"    {key}: {val}")

        return items

    except Exception as e:
        print(f"  ERROR: {e}")
        return None


if __name__ == "__main__":
    print("MysteryScraper - Apify Actor Validation")
    print(f"Target area: Denver, CO {DENVER_ZIP}")
    print(f"Search term: paint")

    results = {}

    # 1. Home Depot — field is zip_code not zipCode
    results["home_depot"] = test_actor(
        "Home Depot",
        "bluebird/home-depot-scraper",
        {
            "searchQuery": "paint",
            "zip_code": DENVER_ZIP,
            "maxResults": 10,
        },
    )

    # 2. Walmart
    results["walmart"] = test_actor(
        "Walmart",
        "epctex/walmart-scraper",
        {
            "search": "paint",
            "zipCode": DENVER_ZIP,
            "maxItems": 10,
            "proxy": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
            },
        },
    )

    # 3. Target — field is url (single string), not startUrls
    results["target"] = test_actor(
        "Target",
        "getdataforme/target-product-scraper",
        {
            "url": "https://www.target.com/s?searchTerm=paint",
            "maxItems": 10,
        },
    )

    # 4. Lowe's — use the other Lowe's actor that supports search
    results["lowes"] = test_actor(
        "Lowes",
        "natanielsantos/lowe-s-scraper",
        {
            "startUrls": [
                {"url": "https://www.lowes.com/search?searchTerm=paint"}
            ],
            "maxItems": 10,
        },
    )

    # 5. Ace Hardware — use playwright scraper instead of cheerio
    results["ace"] = test_actor(
        "Ace Hardware",
        "apify/playwright-scraper",
        {
            "startUrls": [
                {"url": "https://www.acehardware.com/departments/paint-and-supplies?store=17892"}
            ],
            "pageFunction": """async function pageFunction(context) {
                const { page, request } = context;
                await page.waitForTimeout(3000);
                const products = await page.evaluate(() => {
                    const items = [];
                    document.querySelectorAll('[class*="product-card"], [class*="ProductCard"], [data-testid*="product"]').forEach(el => {
                        const name = el.querySelector('h3, h2, [class*="name"], [class*="title"], [class*="Name"]');
                        const price = el.querySelector('[class*="price"], [class*="Price"]');
                        if (name) {
                            items.push({
                                name: name.textContent.trim(),
                                price: price ? price.textContent.trim() : '',
                                store: "Jerry's Ace #17892"
                            });
                        }
                    });
                    return items;
                });
                return products;
            }""",
            "maxRequestsPerCrawl": 3,
        },
    )

    # Summary
    print(f"\n\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for name, data in results.items():
        count = len(data) if data else 0
        status = "OK" if count > 0 else "FAILED"
        print(f"  {name:15s}: {status} ({count} items)")
