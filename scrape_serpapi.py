"""Simple SerpAPI scrape — all 4 stores, streams output live."""

import json, os, sys
from pathlib import Path
from dotenv import load_dotenv
import serpapi

load_dotenv()
client = serpapi.Client(api_key=os.getenv("SERPAPI_KEY"))

OUT = Path("output/serpapi")
OUT.mkdir(parents=True, exist_ok=True)

stores = ["Home Depot", "Target", "Lowes", "Walmart"]
queries = ["paint", "interior paint", "exterior paint", "spray paint", "primer", "stain"]

for store in stores:
    print(f"\n--- {store} ---", flush=True)
    all_items = []
    for q in queries:
        r = client.search({"engine": "google_shopping", "q": f"{store} {q}", "location": "Denver, Colorado, United States", "hl": "en", "gl": "us"})
        items = r.get("shopping_results", [])
        all_items.extend(items)
        print(f"  {q}: {len(items)} results", flush=True)

    # dedup
    seen = set()
    unique = [x for x in all_items if x.get("title") not in seen and not seen.add(x.get("title"))]
    safe = store.lower().replace(" ", "_")
    with open(OUT / f"{safe}.json", "w") as f:
        json.dump(unique, f, indent=2)
    print(f"  TOTAL: {len(unique)} unique products saved", flush=True)

# Home Depot native engine bonus
print(f"\n--- Home Depot (native engine) ---", flush=True)
all_native = []
for q in queries:
    r = client.search({"engine": "home_depot", "q": q, "delivery_zip": "80205"})
    items = r.get("products", [])
    all_native.extend(items)
    print(f"  {q}: {len(items)} products", flush=True)

seen = set()
unique = [x for x in all_native if x.get("title") not in seen and not seen.add(x.get("title"))]
with open(OUT / "home_depot_native.json", "w") as f:
    json.dump(unique, f, indent=2)
print(f"  TOTAL: {len(unique)} unique products saved", flush=True)

print("\nDone!", flush=True)
