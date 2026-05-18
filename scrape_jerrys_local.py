"""
Local Playwright scraper for Jerry's Ace Hardware paint products.
Runs on your machine to avoid Cloudflare datacenter blocks.
Approach: navigate to search pages + scrape rendered product cards from DOM.
"""

import json
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

ACE_STORE_ID = "17892"
BASE_URL = "https://www.acehardware.com"
OUTPUT_DIR = Path("output/ace")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


async def scrape_search_page(page, query, page_num=1):
    """Navigate to a search results page and extract products from the DOM."""
    url = f"{BASE_URL}/search?query={query}&store={ACE_STORE_ID}&page={page_num}"
    print(f"  Loading: {url}")

    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    # Wait for Cloudflare challenge to pass + products to render
    await asyncio.sleep(12)

    # Extract products from the rendered page
    products = await page.evaluate("""() => {
        const items = [];

        // Try multiple selector strategies
        const cards = document.querySelectorAll(
            '[class*="product-card"], [class*="ProductCard"], [data-testid*="product"], ' +
            '.search-results-product, .product-item, [class*="plp-product"]'
        );

        if (cards.length > 0) {
            cards.forEach(card => {
                const nameEl = card.querySelector('[class*="product-name"], [class*="ProductName"], [class*="title"], h2, h3, a[class*="name"]');
                const priceEl = card.querySelector('[class*="price"], [class*="Price"]');
                const linkEl = card.querySelector('a[href*="/product/"]');
                const brandEl = card.querySelector('[class*="brand"], [class*="Brand"]');
                const imgEl = card.querySelector('img');

                if (nameEl) {
                    items.push({
                        name: nameEl.textContent.trim(),
                        price: priceEl ? priceEl.textContent.trim() : '',
                        brand: brandEl ? brandEl.textContent.trim() : '',
                        url: linkEl ? linkEl.href : '',
                        image: imgEl ? imgEl.src : '',
                    });
                }
            });
        }

        // If no cards found, try getting all links with /product/ in href
        if (items.length === 0) {
            document.querySelectorAll('a[href*="/product/"]').forEach(a => {
                const text = a.textContent.trim();
                if (text && text.length > 3 && text.length < 300) {
                    // Look for price near this link
                    const parent = a.closest('[class*="product"], [class*="item"], li, article, div') || a.parentElement;
                    const priceEl = parent ? parent.querySelector('[class*="price"], [class*="Price"]') : null;
                    items.push({
                        name: text,
                        price: priceEl ? priceEl.textContent.trim() : '',
                        url: a.href,
                    });
                }
            });
        }

        // Get total results count if available
        const countEl = document.querySelector('[class*="result-count"], [class*="ResultCount"], [class*="total"]');
        const totalText = countEl ? countEl.textContent : '';

        return { items, totalText, bodyLength: document.body.innerText.length };
    }""")

    return products


async def scrape_all_paint():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        )
        # Hide webdriver flag
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await context.new_page()

        all_products = []
        page_num = 1

        # First page — also check what we're getting
        result = await scrape_search_page(page, "paint", page_num)
        items = result.get("items", [])
        print(f"  Found {len(items)} products on page {page_num} (body: {result.get('bodyLength', 0)} chars, total text: '{result.get('totalText', '')}')")

        if not items:
            # Debug: dump page content
            body = await page.evaluate("() => document.body.innerText.substring(0, 2000)")
            print(f"  Page body preview:\n{body[:1000]}")
            html = await page.content()
            with open(OUTPUT_DIR / "debug_page.html", "w") as f:
                f.write(html)
            print(f"  Saved debug HTML to output/ace/debug_page.html")
        else:
            all_products.extend(items)
            # Continue paginating
            while len(items) > 0 and page_num < 20:
                page_num += 1
                result = await scrape_search_page(page, "paint", page_num)
                items = result.get("items", [])
                print(f"  Found {len(items)} products on page {page_num}")
                if items:
                    all_products.extend(items)
                await asyncio.sleep(1)

        await browser.close()
        return all_products


if __name__ == "__main__":
    print(f"Scraping paint products from Jerry's Ace Hardware #{ACE_STORE_ID}\n")

    products = asyncio.run(scrape_all_paint())

    if not products:
        print("\nNo products from DOM scraping.")
        exit(1)

    # Dedupe by URL
    seen = set()
    unique = []
    for p in products:
        key = p.get("url") or p.get("name")
        if key not in seen:
            seen.add(key)
            unique.append(p)
    products = unique

    # Summary
    print(f"\n{'='*60}")
    print(f"TOTAL: {len(products)} unique paint products")
    print(f"{'='*60}")

    print(f"\nSample products:")
    for p in products[:15]:
        print(f"  {p.get('name', '?')[:65]} | {p.get('price', '?')}")

    out_file = OUTPUT_DIR / "jerrys_paint_all.json"
    with open(out_file, "w") as f:
        json.dump(products, f, indent=2)
    print(f"\nSaved {len(products)} products to {out_file}")
