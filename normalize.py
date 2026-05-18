"""
Normalize raw scraper output into a common product schema.
"""

import html
import re
from datetime import datetime, timezone


def _parse_price(val):
    """Extract float from price string like '$19.47' or 19.47."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    cleaned = re.sub(r'[^\d.]', '', str(val))
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _clean_name(name):
    """Decode HTML entities and clean whitespace."""
    if not name:
        return ""
    return html.unescape(str(name)).strip()


def _extract_brand_from_title(title):
    """Best-effort brand extraction from product title."""
    if not title:
        return ""
    # Common pattern: "Brand Name Product Description"
    # Try splitting on common separators
    for sep in [" - ", " – ", " — "]:
        if sep in title:
            return title.split(sep)[0].strip()
    return ""


def normalize_home_depot(products, category="", search_term=""):
    """Normalize SerpAPI Home Depot native results."""
    now = datetime.now(timezone.utc).isoformat()
    results = []
    for p in products:
        badges = p.get("badges", [])
        signal = ""
        if isinstance(badges, list):
            for b in badges:
                if isinstance(b, str) and "bestseller" in b.lower():
                    signal = "bestseller"
                    break

        rating = p.get("rating")
        reviews = p.get("reviews")
        if not signal and rating and float(rating) >= 4.5 and reviews and int(reviews) >= 500:
            signal = "high_rated"

        results.append({
            "source": "Home Depot",
            "name": _clean_name(p.get("title", "")),
            "brand": p.get("brand", "") or _extract_brand_from_title(p.get("title", "")),
            "price": _parse_price(p.get("price")),
            "rating": float(rating) if rating else None,
            "reviews": int(reviews) if reviews else None,
            "category": category,
            "search_term": search_term,
            "url": p.get("link", ""),
            "signal": signal,
            "scraped_at": now,
        })
    return results


def normalize_target(products, category="", search_term=""):
    """Normalize Target Redsky API results."""
    now = datetime.now(timezone.utc).isoformat()
    results = []
    for p in products:
        item = p.get("item", {})
        price_data = p.get("price", {})
        desc = item.get("product_description", {})
        brand_info = item.get("primary_brand", {})
        ratings = item.get("ratings_and_reviews", {}).get("statistics", {})

        buy_url = item.get("enrichment", {}).get("buy_url", "")
        url = f"https://www.target.com{buy_url}" if buy_url and not buy_url.startswith("http") else buy_url

        rating_val = ratings.get("rating", {}).get("average")
        review_count = ratings.get("review_count", 0)

        results.append({
            "source": "Target",
            "name": _clean_name(desc.get("title", "")),
            "brand": brand_info.get("name", ""),
            "price": _parse_price(price_data.get("formatted_current_price")),
            "rating": float(rating_val) if rating_val else None,
            "reviews": int(review_count) if review_count else None,
            "category": category,
            "search_term": search_term,
            "url": url,
            "signal": "",
            "scraped_at": now,
        })
    return results


def normalize_walmart(products, category="", search_term=""):
    """Normalize Apify Walmart results."""
    now = datetime.now(timezone.utc).isoformat()
    results = []
    for p in products:
        # Price from conditionOffers or direct
        price = None
        offers = p.get("conditionOffers") or []
        if offers:
            price = _parse_price(offers[0].get("price", {}).get("price"))
        if price is None:
            price = _parse_price(p.get("price"))

        # Signal from badges
        signal = ""
        badges = p.get("badges") or {}
        flags = badges.get("flags") or []
        for flag in flags:
            if isinstance(flag, dict) and flag.get("key", "").upper() == "BESTSELLER":
                signal = "bestseller"
                break

        canonical = p.get("canonicalUrl", "")
        url = f"https://www.walmart.com{canonical}" if canonical and not canonical.startswith("http") else canonical

        results.append({
            "source": "Walmart",
            "name": _clean_name(p.get("name", "")),
            "brand": p.get("brand", ""),
            "price": price,
            "rating": float(p["averageRating"]) if p.get("averageRating") else None,
            "reviews": int(p["numberOfReviews"]) if p.get("numberOfReviews") else None,
            "category": category,
            "search_term": search_term,
            "url": url,
            "signal": signal,
            "scraped_at": now,
        })
    return results


def normalize_lowes(products, category="", search_term=""):
    """Normalize SerpAPI Google Shopping results for Lowe's."""
    now = datetime.now(timezone.utc).isoformat()
    results = []
    for p in products:
        title = p.get("title", "")
        rating = p.get("rating")
        reviews = p.get("reviews")
        signal = ""
        if rating and float(rating) >= 4.5 and reviews and int(reviews) >= 500:
            signal = "high_rated"

        results.append({
            "source": "Lowes",
            "name": _clean_name(title),
            "brand": _extract_brand_from_title(title),
            "price": _parse_price(p.get("extracted_price")),
            "rating": float(rating) if rating else None,
            "reviews": int(reviews) if reviews else None,
            "category": category,
            "search_term": search_term,
            "url": p.get("product_link", ""),
            "signal": signal,
            "scraped_at": now,
        })
    return results


def normalize_ace(items):
    """Normalize Ace Hardware catalog items."""
    now = datetime.now(timezone.utc).isoformat()
    results = []
    for item in items:
        content = item.get("content", {})
        price_data = item.get("price", {})
        product_type = item.get("productType", "")

        # Extract category from productType like "013010501005-Wall Paint"
        category = ""
        if "-" in product_type:
            category = product_type.split("-", 1)[1].strip()

        results.append({
            "source": "Ace",
            "name": _clean_name(content.get("productName", "")),
            "brand": "",  # Brand is embedded in product name for Ace
            "price": _parse_price(price_data.get("price")),
            "rating": None,
            "reviews": None,
            "category": category,
            "search_term": "",
            "url": f"https://www.acehardware.com/{content.get('seoFriendlyUrl', '')}",
            "product_code": item.get("productCode", ""),
            "product_type_id": product_type,
            "signal": "",
            "scraped_at": now,
        })
    return results
