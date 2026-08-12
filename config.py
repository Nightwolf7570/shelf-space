"""Constants and category configuration for MysteryScraper."""

import os

ACE_STORE_ID = "17892"
DENVER_ZIP = "80205"
HD_STORE_ID = "1513"
TARGET_STORE_ID = "3330"
TARGET_REDSKY_KEY = os.environ.get("TARGET_REDSKY_KEY", "")

# Categories derived from Jerry's Ace catalog productType field.
# Paint + cleaning are Stephen's confirmed priorities.
CATEGORIES = {
    "paint": {
        "ace_type_prefix": "01301",
        "search_terms": [
            "interior wall paint",
            "exterior paint",
            "spray paint",
            "paint primer",
            "stain",
        ],
    },
}

# Brand aliases for fuzzy matching (lowercase)
BRAND_ALIASES = {
    "benjamin moore": ["ben moore", "benmoore"],
    "sherwin-williams": ["sherwin williams", "sw"],
    "rust-oleum": ["rustoleum", "rust oleum"],
    "valspar": [],
    "behr": [],
    "glidden": [],
    "kilz": [],
}
