# Shelf Space

A competitive-intelligence dashboard used by independent hardware-store owners (initial user: Stephen, Jerry's Ace Hardware #17892, Denver). It scrapes competitor catalogs (Home Depot, Lowes, Target, Walmart) and surfaces products competitors carry that the user's store doesn't — ranked by a composite "opportunity score" derived from competitor signals (bestseller / high-rated flags), ratings, review counts, price availability, and how many competitors carry the item.

## Register

product

## Audience

Non-technical retail manager. The reader is the store owner deciding what to stock next week, not a data analyst exploring the data. Scannable beats granular. They open the app, look at the top of the Recommendations grid, and act.

## Surfaces

- **Recommendations** (`/`) — ranked card grid (LTR top-to-bottom). Card click → right-side slide-out detail panel with score breakdown and Jerry's closest existing products.
- **Jerry's Inventory** (`/inventory`) — own catalog grouped by category, low-stock (≤3) flagged.
- **Competitor Catalog** (`/competitors`) — every scraped competitor product as a table (dense).
- **Changes** (`/changes`) — new / removed / price-change diffs vs the prior snapshot.

Top bar persists across surfaces: logo, full-width search, snapshot date picker, tab nav.

## Voice

Plain English. No jargon. No emoji. Short, declarative.

## Visual identity

Warm but restrained. Slate surfaces (white / slate-50 / slate-100, borders slate-200). One accent: warm amber-terracotta (`#c2410c` brand-600, `#9a3412` brand-700, `#fef3e7` brand-50). Red-700/red-50 for warnings only. No green, no purple, no gradients, no decorative shadows.

System font stack (no web fonts; the app must load fast inside a back-office browser).

## Strategy

Restrained. The brand color appears only on: score badges, signal chips (Bestseller / Top Rated), active tab underline, focus borders, and the logo mark. Everything else is monochrome slate. The data carries the page.

## Anti-patterns (avoid)

- Green accents (the original direction, explicitly rejected)
- Purple, lavender, indigo
- Per-retailer brand colors as dots/chips (looks like a startup logo wall, not a tool)
- Gradient text or glassmorphism
- Numbered eyebrows ("01 / 02 / 03") above sections
- Cream / sand / beige backgrounds
- Identical-card-grid feel — the #1 recommendation should read as the headline answer, not as one of N
