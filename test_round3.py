"""
Round 3: Try remaining actors for Home Depot, Target, Lowe's, Ace.
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
from apify_client import ApifyClient

load_dotenv()

client = ApifyClient(os.getenv("APIFY_TOKEN"))
DENVER_ZIP = "80205"
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
            for k in ['name', 'title', 'productName', 'price', 'brand', 'url', 'canonicalUrl']:
                if k in item and item[k]:
                    val = str(item[k])[:100]
                    print(f"    {k}: {val}")
        return items
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


if __name__ == "__main__":
    # HOME DEPOT — try the clearance scraper (uses GraphQL API, not browser)
    test_actor(
        "HD clearance",
        "scrapyspider/home-depot-clearance-scraper",
        {"zipCode": DENVER_ZIP, "maxItems": 10},
    )

    # HOME DEPOT — try category scraper with direct URL
    test_actor(
        "HD category",
        "getdataforme/homedepot-category-scraper",
        {
            "startUrls": [
                {"url": "https://www.homedepot.com/b/Paint/N-5yc1vZar2d"}
            ],
            "deliveryZipCode": DENVER_ZIP,
            "maxItems": 10,
        },
    )

    # TARGET — fix axlymxp input (keyword not searchKeyword)
    test_actor(
        "Target stores",
        "axlymxp/target-store-scraper",
        {"keyword": DENVER_ZIP, "radius": 10, "resultsLimit": 5},
    )

    # TARGET — try product scraper with category URL
    test_actor(
        "Target products",
        "getdataforme/target-product-scraper",
        {"url": "https://www.target.com/c/paint-painting-supplies-tools/-/N-5xth0"},
    )

    # LOWE'S — try studio-amba actor
    test_actor(
        "Lowes amba",
        "studio-amba/lowes-scraper",
        {"searchQuery": "paint", "maxProducts": 10},
    )

    # ACE — try playwright with broader selectors
    test_actor(
        "Ace playwright",
        "apify/playwright-scraper",
        {
            "startUrls": [
                {"url": "https://www.acehardware.com/departments/paint-and-supplies?store=17892"}
            ],
            "pageFunction": """async function pageFunction(context) {
                const { page, request, log } = context;
                await page.waitForTimeout(5000);
                const html = await page.content();
                log.info('Page length: ' + html.length);
                // Try to get all links that look like products
                const products = await page.evaluate(() => {
                    const items = [];
                    // Grab all anchor tags with /product/ in href
                    document.querySelectorAll('a[href*="/product/"]').forEach(el => {
                        const name = el.textContent.trim();
                        if (name && name.length > 3 && name.length < 200) {
                            items.push({
                                name: name,
                                url: el.href,
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

    print("\nDone!")
