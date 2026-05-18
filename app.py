"""
MysteryScraper — Streamlit UI
Linear/Notion-inspired competitive intelligence dashboard for Jerry's Ace Hardware.
"""

import json
from pathlib import Path
from datetime import datetime
import streamlit as st
import pandas as pd

from analyze import find_gaps, rank_recommendations, diff_snapshots
from config import CATEGORIES

# --- Page config ---
st.set_page_config(
    page_title="MysteryScraper",
    page_icon="M",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Design System CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --bg-primary: #ffffff;
        --bg-secondary: #f9fafb;
        --bg-hover: #f3f4f6;
        --border: #e5e7eb;
        --text-primary: #111827;
        --text-secondary: #6b7280;
        --text-tertiary: #9ca3af;
        --accent: #059669;
        --accent-light: #d1fae5;
        --accent-hover: #047857;
        --primary-color: #059669;
    }

    /* Global font and background */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    }
    .stApp {
        background-color: var(--bg-primary);
        color: var(--text-primary);
        color-scheme: light;
    }
    .block-container {
        padding: 2rem 2.5rem !important;
        max-width: 1400px !important;
    }

    /* Hide Streamlit chrome */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* --- Sidebar --- */
    section[data-testid="stSidebar"] {
        background-color: var(--bg-secondary);
        border-right: none;
        width: 260px !important;
    }
    section[data-testid="stSidebar"] > div {
        padding-top: 1.5rem;
    }
    section[data-testid="stSidebar"] .block-container {
        padding: 0.5rem 1.25rem !important;
    }
    section[data-testid="stSidebar"] hr {
        border-color: var(--border);
        margin: 0.75rem 0;
    }

    /* --- Tabs (single underline; hide animated highlight to avoid double green bar) --- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        border-bottom: 1px solid var(--border);
        background: transparent;
    }
    .stTabs [data-baseweb="tab-highlight"] {
        display: none !important;
    }
    .stTabs [data-baseweb="tab-list"] button {
        background: transparent !important;
        border: none !important;
        border-bottom: 2px solid transparent !important;
        color: var(--text-secondary) !important;
        font-weight: 500 !important;
        font-size: 13px !important;
        padding: 10px 20px !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        outline: none !important;
    }
    .stTabs [data-baseweb="tab-list"] button:hover {
        color: var(--text-primary) !important;
        border-bottom-color: transparent !important;
    }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        color: var(--text-primary) !important;
        border-bottom: 2px solid var(--accent) !important;
        background: transparent !important;
        font-weight: 600 !important;
    }
    .stTabs [data-baseweb="tab-panel"] {
        border: none !important;
        outline: none !important;
    }

    /* --- Inputs --- */
    .stSelectbox label, .stMultiSelect label, .stTextInput label {
        color: var(--text-secondary) !important;
        font-weight: 500 !important;
        font-size: 12px !important;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .stTextInput input,
    .stTextInput input:focus,
    .stTextInput input:hover,
    .stTextInput input:active,
    .stTextInput > div > div > input {
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        padding: 10px 14px !important;
        font-size: 13px !important;
        background: var(--bg-primary) !important;
        color: var(--text-primary) !important;
        -webkit-text-fill-color: var(--text-primary) !important;
        box-shadow: none !important;
        outline: none !important;
    }
    .stTextInput input:focus {
        background: #f3f4f6 !important;
    }
    .stTextInput input::placeholder {
        color: var(--text-tertiary) !important;
    }
    .stTextInput > div,
    .stTextInput > div > div {
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
    }

    /* Dropdown menus (selectbox options) */
    [data-baseweb="popover"],
    [data-baseweb="menu"],
    [data-baseweb="menu"] ul,
    [data-baseweb="menu"] li {
        background: var(--bg-primary) !important;
        color: var(--text-primary) !important;
    }
    [data-baseweb="menu"] li:hover,
    [data-baseweb="menu"] li[aria-selected="true"] {
        background: var(--bg-hover) !important;
        color: var(--text-primary) !important;
    }
    .stSelectbox > div > div,
    .stSelectbox > div > div:hover,
    .stSelectbox > div > div:focus,
    .stSelectbox > div > div:focus-within,
    .stSelectbox [data-baseweb="select"] > div {
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        font-size: 13px !important;
        background: var(--bg-primary) !important;
        color: var(--text-primary) !important;
        box-shadow: none !important;
        outline: none !important;
    }
    .stSelectbox [data-baseweb="select"],
    .stSelectbox [data-baseweb="select"] span,
    .stSelectbox [data-baseweb="select"] div,
    .stSelectbox [data-baseweb="select"] input {
        color: var(--text-primary) !important;
        -webkit-text-fill-color: var(--text-primary) !important;
    }
    .stSelectbox svg {
        fill: var(--text-secondary) !important;
    }
    section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] > div {
        background: var(--bg-primary) !important;
    }

    /* --- Remove Streamlit default black/dark borders (white theme) --- */
    [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stVerticalBlock"] > div,
    [data-testid="stHorizontalBlock"] > div,
    [data-testid="stColumn"],
    [data-testid="stExpander"],
    [data-testid="stExpander"] details,
    [data-testid="stExpander"] summary,
    [data-testid="stWidgetLabel"],
    .stTabs,
    .stTabs > div,
    [data-testid="stMarkdownContainer"],
    div[data-testid="stMetric"],
    [data-testid="stDataFrame"],
    [data-testid="stDataFrame"] > div,
    [data-testid="stElementContainer"],
    .element-container {
        border-color: var(--border) !important;
        outline: none !important;
        box-shadow: none !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        border: none !important;
    }
    [data-testid="stExpander"] details {
        border: none !important;
        background: var(--bg-secondary) !important;
    }
    [data-testid="stExpander"] summary {
        border: none !important;
    }
    [data-testid="stDataFrame"] {
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
    }
    [data-testid="stDataFrame"] [data-testid="glideDataEditor"],
    [data-testid="stDataFrame"] canvas {
        border: none !important;
    }

    /* --- Buttons --- */
    .stButton > button {
        background-color: var(--accent);
        color: white;
        border: none;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 500;
        padding: 6px 16px;
        transition: background-color 0.15s ease;
    }
    .stButton > button:hover {
        background-color: var(--accent-hover);
        color: white;
    }

    /* --- Dataframe --- */
    .stDataFrame {
        border: none;
        border-radius: 10px;
        overflow: hidden;
    }

    /* --- Expander --- */
    .streamlit-expanderHeader {
        font-size: 13px !important;
        font-weight: 500 !important;
        color: var(--text-secondary) !important;
        background: var(--bg-secondary) !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 10px 16px !important;
    }
    .streamlit-expanderContent {
        border: none !important;
        border-top: none !important;
        border-radius: 0 0 8px 8px !important;
    }

    /* --- Custom Components --- */
    .breadcrumb {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 24px;
        flex-wrap: wrap;
    }
    .breadcrumb-item {
        font-size: 14px;
        font-weight: 500;
        color: var(--text-secondary);
    }
    .breadcrumb-item.active {
        color: var(--accent);
        font-weight: 600;
    }
    .breadcrumb-sep {
        color: var(--text-tertiary);
        font-size: 13px;
    }

    .stat-card {
        background: var(--bg-secondary);
        border: none !important;
        border-radius: 10px;
        padding: 18px 22px;
        outline: none !important;
        box-shadow: none !important;
    }
    [data-testid="stVerticalBlock"] > div:has(.stat-card),
    [data-testid="column"] {
        border: none !important;
        outline: none !important;
    }
    .stat-label {
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--text-secondary);
        margin-bottom: 6px;
    }
    .stat-value {
        font-size: 30px;
        font-weight: 700;
        color: var(--text-primary);
        line-height: 1.1;
    }

    .summary-text {
        font-size: 14px;
        color: var(--text-secondary);
        line-height: 1.6;
        margin-bottom: 20px;
    }
    .summary-text strong {
        color: var(--text-primary);
        font-weight: 600;
    }

    /* Recommendation table */
    .rec-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        font-size: 13px;
        border: none;
        border-radius: 10px;
        overflow: hidden;
    }
    .rec-table thead th {
        text-align: left;
        padding: 10px 14px;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--text-secondary);
        background: var(--bg-secondary);
        border-bottom: 1px solid #f3f4f6;
    }
    .rec-table tbody td {
        padding: 12px 14px;
        color: var(--text-primary);
        border-bottom: 1px solid #f3f4f6;
        vertical-align: middle;
    }
    .rec-table tbody tr:last-child td {
        border-bottom: none;
    }
    .rec-table tbody tr:hover td {
        background: var(--bg-secondary);
    }
    .rec-table .rank-cell {
        color: var(--text-tertiary);
        font-weight: 600;
        font-size: 12px;
        width: 40px;
        text-align: center;
    }
    .rec-table .product-cell {
        font-weight: 500;
        color: var(--text-primary);
        max-width: 320px;
    }
    .rec-table .meta-cell {
        color: var(--text-secondary);
        font-size: 12px;
    }
    .rec-table .price-cell {
        font-weight: 600;
        font-variant-numeric: tabular-nums;
    }

    /* Signal badges */
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 9999px;
        font-size: 11px;
        font-weight: 500;
        line-height: 1.4;
        white-space: nowrap;
    }
    .badge-bestseller {
        background: #d1fae5;
        color: #065f46;
    }
    .badge-high-rated {
        background: #dbeafe;
        color: #1d4ed8;
    }
    .badge-empty {
        color: var(--text-tertiary);
        font-size: 13px;
    }

    /* Source dots */
    .source-tag {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        font-size: 12px;
        color: var(--text-secondary);
        margin-right: 6px;
    }
    .source-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        display: inline-block;
    }

    /* Score bar */
    .score-bar-wrap {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .score-bar-track {
        width: 64px;
        height: 6px;
        background: #e5e7eb;
        border-radius: 3px;
        overflow: hidden;
    }
    .score-bar-fill {
        height: 100%;
        background: var(--accent);
        border-radius: 3px;
        transition: width 0.3s ease;
    }
    .score-num {
        font-size: 12px;
        font-weight: 600;
        color: var(--text-secondary);
        font-variant-numeric: tabular-nums;
        min-width: 18px;
    }

    /* Empty state */
    .empty-state {
        text-align: center;
        padding: 72px 24px;
    }
    .empty-state-icon {
        font-size: 44px;
        margin-bottom: 14px;
        opacity: 0.6;
    }
    .empty-state-title {
        font-size: 16px;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 6px;
    }
    .empty-state-desc {
        font-size: 13px;
        color: var(--text-secondary);
        max-width: 420px;
        margin: 0 auto;
        line-height: 1.6;
    }

    /* Sidebar wordmark */
    .sidebar-wordmark {
        font-size: 15px;
        font-weight: 700;
        color: var(--text-primary);
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 4px;
    }
    .sidebar-wordmark-icon {
        width: 24px;
        height: 24px;
        background: var(--accent);
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 13px;
    }
    .sidebar-context {
        font-size: 12px;
        color: var(--text-secondary);
        line-height: 1.5;
    }
    .sidebar-stat {
        font-size: 12px;
        color: var(--text-tertiary);
        line-height: 1.8;
    }
    .sidebar-section-label {
        font-size: 10px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--text-tertiary);
        margin-bottom: 8px;
        margin-top: 4px;
    }

    /* Scoring table */
    .scoring-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
    }
    .scoring-table td {
        padding: 6px 0;
        color: var(--text-secondary);
    }
    .scoring-table td:last-child {
        text-align: right;
        font-weight: 600;
        color: var(--text-primary);
        font-variant-numeric: tabular-nums;
    }

    /* Info box */
    .info-box {
        background: var(--bg-secondary);
        border: none;
        border-radius: 8px;
        padding: 12px 16px;
        font-size: 13px;
        color: var(--text-secondary);
        line-height: 1.5;
    }

    /* Sources bar */
    .sources-bar {
        display: flex;
        align-items: center;
        gap: 20px;
        margin-bottom: 20px;
        padding: 12px 18px;
        background: var(--bg-secondary);
        border-radius: 10px;
    }
    .sources-bar-label {
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--text-tertiary);
    }
    .source-chip {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        font-size: 13px;
        font-weight: 500;
        color: var(--text-primary);
    }
    .source-chip-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
    }

    /* Result count */
    .result-count {
        font-size: 13px;
        color: var(--text-secondary);
        margin-bottom: 12px;
    }
    .result-count strong {
        color: var(--text-primary);
        font-weight: 600;
    }

    /* MoM metric cards */
    .mom-card {
        background: var(--bg-secondary);
        border: none;
        border-radius: 10px;
        padding: 16px 20px;
        text-align: center;
    }
    .mom-card-value {
        font-size: 26px;
        font-weight: 700;
        color: var(--text-primary);
    }
    .mom-card-label {
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--text-secondary);
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)


# --- Helper functions ---
SOURCE_COLORS = {
    "Home Depot": "#f97316",
    "Target": "#ef4444",
    "Walmart": "#3b82f6",
    "Lowes": "#8b5cf6",
}


def signal_badge(signal: str) -> str:
    if signal == "bestseller":
        return '<span class="badge badge-bestseller">Bestseller</span>'
    elif signal == "high_rated":
        return '<span class="badge badge-high-rated">High Rated</span>'
    return '<span class="badge-empty">&mdash;</span>'


def source_tags(sources: list) -> str:
    parts = []
    for s in sources:
        color = SOURCE_COLORS.get(s, "#9ca3af")
        parts.append(
            f'<span class="source-tag">'
            f'<span class="source-dot" style="background:{color};"></span>{s}</span>'
        )
    return "".join(parts)


def score_bar(score: int, max_score: int = 30) -> str:
    pct = min(score / max_score * 100, 100)
    return (
        f'<div class="score-bar-wrap">'
        f'<div class="score-bar-track">'
        f'<div class="score-bar-fill" style="width:{pct:.0f}%;"></div>'
        f'</div>'
        f'<span class="score-num">{score}</span>'
        f'</div>'
    )


def stat_card(label: str, value) -> str:
    return (
        f'<div class="stat-card">'
        f'<div class="stat-label">{label}</div>'
        f'<div class="stat-value">{value}</div>'
        f'</div>'
    )


def render_recommendations_table(recs: list, category_filter: str = "All") -> str:
    rows_html = []
    for i, r in enumerate(recs, 1):
        sig = r.get("signal", "")
        sources = r.get("sources", [r.get("source", "")])
        cat = r.get("category", "")

        if category_filter != "All" and cat != category_filter:
            continue

        price_str = f"${r['price']:.2f}" if r.get("price") else "&mdash;"
        product_name = r["name"][:75]

        rows_html.append(
            f'<tr>'
            f'<td class="rank-cell">{i}</td>'
            f'<td class="product-cell">{product_name}</td>'
            f'<td class="meta-cell">{r.get("brand", "")}</td>'
            f'<td class="meta-cell">{cat}</td>'
            f'<td class="price-cell">{price_str}</td>'
            f'<td>{source_tags(sources)}</td>'
            f'<td>{signal_badge(sig)}</td>'
            f'<td>{score_bar(r["score"])}</td>'
            f'</tr>'
        )

    if not rows_html:
        return '<div class="info-box">No recommendations match the current filters.</div>'

    return (
        '<table class="rec-table">'
        "<thead><tr>"
        '<th style="width:40px;">#</th>'
        "<th>Product</th>"
        "<th>Brand</th>"
        "<th>Category</th>"
        '<th style="width:80px;">Price</th>'
        "<th>Carried By</th>"
        "<th>Signal</th>"
        '<th style="width:110px;">Score</th>'
        "</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        "</table>"
    )


def find_similar_ace_products(product_name, brand, category, ace_products):
    """Find the closest Jerry's products to show what he carries in the same space."""
    name_lower = product_name.lower()
    brand_lower = brand.lower() if brand else ""
    matches = []
    for p in ace_products:
        ace_name = p.get("name", "").lower()
        ace_cat = p.get("category", "")
        # Match by category
        if category and ace_cat == category:
            # Score relevance by shared words
            words = set(name_lower.split()) - {"the", "a", "an", "and", "or", "for", "with", "in", "of", "to"}
            ace_words = set(ace_name.split()) - {"the", "a", "an", "and", "or", "for", "with", "in", "of", "to"}
            overlap = len(words & ace_words)
            if overlap >= 1:
                matches.append({"product": p, "overlap": overlap})
    matches.sort(key=lambda x: x["overlap"], reverse=True)
    return [m["product"] for m in matches[:5]]


# --- Data loading ---
@st.cache_data
def load_snapshot(snapshot_dir="data/snapshots"):
    snap_dir = Path(snapshot_dir)
    if not snap_dir.exists():
        return None, None, None

    comp_files = sorted(snap_dir.glob("*_competitors.json"))
    ace_files = sorted(snap_dir.glob("*_ace_catalog.json"))

    if not comp_files:
        return None, None, None

    latest_comp = comp_files[-1]
    snap_date = latest_comp.stem.split("_")[0]

    with open(latest_comp) as f:
        competitors = json.load(f)

    ace_products = []
    if ace_files:
        with open(ace_files[-1]) as f:
            ace_products = json.load(f)

    return competitors, ace_products, snap_date


@st.cache_data
def load_diff(diff_dir="data/diffs"):
    d = Path(diff_dir)
    if not d.exists():
        return None
    diffs = sorted(d.glob("*_diff.json"))
    if not diffs:
        return None
    with open(diffs[-1]) as f:
        return json.load(f)


# --- Load data ---
competitors, ace_products, snap_date = load_snapshot()

if not competitors:
    st.markdown(
        '<div class="breadcrumb">'
        '<span class="breadcrumb-item active">MysteryScraper</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="empty-state">'
        '<div class="empty-state-icon" style="font-size:32px; color:#9ca3af;">--</div>'
        '<div class="empty-state-title">No snapshot data found</div>'
        '<div class="empty-state-desc">'
        'Run <code>python run_snapshot.py</code> to scrape competitor data and generate your first intelligence report.'
        '</div></div>',
        unsafe_allow_html=True,
    )
    st.stop()

# --- Analysis ---
gaps = find_gaps(ace_products, competitors)
recommendations = rank_recommendations(gaps)
diff_data = load_diff()

# Format date nicely
try:
    date_display = datetime.strptime(snap_date, "%Y-%m-%d").strftime("%b %d, %Y")
except ValueError:
    date_display = snap_date

num_competitors = len(set(p["source"] for p in competitors))
num_categories = len(set(p["category"] for p in competitors if p.get("category")))

# --- Sidebar ---
with st.sidebar:
    st.markdown(
        '<div class="sidebar-wordmark">'
        '<div class="sidebar-wordmark-icon">M</div>'
        'MysteryScraper'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="sidebar-context">'
        f"Jerry's Ace Hardware #17892<br>"
        f"2101 N Humboldt St, Denver CO"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    st.markdown('<div class="sidebar-section-label">Filters</div>', unsafe_allow_html=True)
    cat_options = ["All"] + list(CATEGORIES.keys())
    selected_cat = st.selectbox("Category", cat_options, label_visibility="collapsed")

    source_options = ["All"] + sorted(set(p["source"] for p in competitors))
    selected_source = st.selectbox("Competitor", source_options, label_visibility="collapsed")

    st.markdown("---")

    st.markdown(
        f'<div class="sidebar-section-label">Snapshot</div>'
        f'<div class="sidebar-stat">'
        f"{date_display}<br>"
        f"{len(competitors):,} competitor products<br>"
        f"{len(ace_products):,} Jerry's products<br>"
        f"{num_competitors} competitors tracked"
        f"</div>",
        unsafe_allow_html=True,
    )

# --- Breadcrumb header ---
st.markdown(
    f'<div class="breadcrumb">'
    f'<span class="breadcrumb-item active">Jerry\'s Ace #17892</span>'
    f'<span class="breadcrumb-sep">/</span>'
    f'<span class="breadcrumb-item">Competitive Intelligence</span>'
    f'<span class="breadcrumb-sep">/</span>'
    f'<span class="breadcrumb-item">{date_display}</span>'
    f'</div>',
    unsafe_allow_html=True,
)

# --- Stat cards ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(stat_card("Total Gaps", f"{len(gaps):,}"), unsafe_allow_html=True)
with col2:
    st.markdown(stat_card("Recommended Adds", len(recommendations)), unsafe_allow_html=True)
with col3:
    st.markdown(stat_card("Competitors Tracked", num_competitors), unsafe_allow_html=True)
with col4:
    st.markdown(stat_card("Categories", num_categories), unsafe_allow_html=True)

# --- Sources bar ---
all_sources = sorted(set(p["source"] for p in competitors))
source_chips = []
for s in all_sources:
    color = SOURCE_COLORS.get(s, "#9ca3af")
    count = sum(1 for p in competitors if p["source"] == s)
    source_chips.append(
        f'<span class="source-chip">'
        f'<span class="source-chip-dot" style="background:{color};"></span>'
        f'{s} <span style="color:#9ca3af; font-weight:400;">({count})</span></span>'
    )
st.markdown(
    f'<div class="sources-bar">'
    f'<span class="sources-bar-label">Sources</span>'
    f'{"".join(source_chips)}'
    f'</div>',
    unsafe_allow_html=True,
)

# --- Tabs ---
tab1, tab2, tab3 = st.tabs(["Gaps & Recommendations", "Competitor Catalog", "Changes"])

# --- Tab 1: Recommendations ---
with tab1:
    if not recommendations:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-state-icon" style="font-size:32px; color:#9ca3af;">--</div>'
            '<div class="empty-state-title">No gap recommendations found</div>'
            '<div class="empty-state-desc">'
            "All competitor products appear to be covered by Jerry's current catalog."
            '</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="summary-text">'
            f'Found <strong>{len(gaps):,} gaps</strong> across '
            f'<strong>{num_competitors} competitors</strong> in '
            f'<strong>{num_categories} categories</strong>. '
            f'Here are the top <strong>{len(recommendations)}</strong> products '
            f"Jerry's should consider stocking, ranked by competitive signal strength."
            f'</div>',
            unsafe_allow_html=True,
        )

        table_html = render_recommendations_table(recommendations, selected_cat)
        st.markdown(table_html, unsafe_allow_html=True)

        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

        filtered_recs = recommendations
        if selected_cat != "All":
            filtered_recs = [r for r in recommendations if r.get("category") == selected_cat]

        if filtered_recs:
            st.markdown(
                '<div style="font-size:13px; font-weight:600; color:#6b7280; '
                'text-transform:uppercase; letter-spacing:0.05em; margin-bottom:10px;">'
                'Product Details — click to expand</div>',
                unsafe_allow_html=True,
            )

            for i, r in enumerate(filtered_recs, 1):
                sources = r.get("sources", [r.get("source", "")])
                sig = r.get("signal", "")
                price_str = f"${r['price']:.2f}" if r.get("price") else "N/A"

                with st.expander(f"#{i}  {r['name'][:70]}"):
                    dcol1, dcol2 = st.columns(2)

                    with dcol1:
                        rating_str = f"{r['rating']:.1f}" if r.get("rating") else "N/A"
                        reviews_str = f"{int(r['reviews']):,}" if r.get("reviews") else "N/A"
                        st.markdown(
                            f'<div style="font-size:13px; font-weight:600; color:#111827; margin-bottom:12px;">'
                            f'Competitor Signal</div>'
                            f'<table class="scoring-table">'
                            f'<tr><td>Brand</td><td>{r.get("brand", "Unknown")}</td></tr>'
                            f'<tr><td>Category</td><td>{r.get("category", "N/A")}</td></tr>'
                            f'<tr><td>Price</td><td>{price_str}</td></tr>'
                            f'<tr><td>Rating</td><td>{rating_str}</td></tr>'
                            f'<tr><td>Reviews</td><td>{reviews_str}</td></tr>'
                            f'<tr><td>Signal</td><td>{signal_badge(sig)}</td></tr>'
                            f'<tr><td>Score</td><td><strong>{r["score"]}</strong> / 30</td></tr>'
                            f'<tr><td>Carried By</td><td>{source_tags(sources)}</td></tr>'
                            f'</table>',
                            unsafe_allow_html=True,
                        )
                        if r.get("url"):
                            st.markdown(
                                f'<a href="{r["url"]}" target="_blank" style="font-size:12px; '
                                f'color:#059669; text-decoration:none; font-weight:500;">'
                                f'View at competitor &rarr;</a>',
                                unsafe_allow_html=True,
                            )

                    with dcol2:
                        similar = find_similar_ace_products(
                            r["name"], r.get("brand", ""), r.get("category", ""), ace_products
                        )
                        st.markdown(
                            '<div style="font-size:13px; font-weight:600; color:#111827; margin-bottom:12px;">'
                            "Jerry's Closest Products</div>",
                            unsafe_allow_html=True,
                        )
                        if similar:
                            st.markdown(
                                '<div style="font-size:12px; color:#6b7280; margin-bottom:8px;">'
                                "These are the closest items Jerry's currently stocks. "
                                "None are an exact match for this competitor product.</div>",
                                unsafe_allow_html=True,
                            )
                            for sp in similar:
                                sp_price = f"${sp['price']:.2f}" if sp.get("price") else "N/A"
                                st.markdown(
                                    f'<div style="padding:8px 12px; background:#f9fafb; border-radius:6px; '
                                    f'margin-bottom:6px; font-size:13px;">'
                                    f'<div style="font-weight:500; color:#111827;">{sp["name"][:65]}</div>'
                                    f'<div style="font-size:12px; color:#9ca3af; margin-top:2px;">'
                                    f'Price: {sp_price}</div>'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )
                        else:
                            st.markdown(
                                '<div style="padding:16px; background:#fef2f2; border-radius:8px; '
                                'text-align:center;">'
                                '<div style="font-size:14px; font-weight:600; color:#991b1b; margin-bottom:4px;">'
                                'Gap Confirmed</div>'
                                '<div style="font-size:12px; color:#6b7280;">'
                                "Jerry's carries no similar products in this space. "
                                "This is a clear assortment gap.</div>"
                                '</div>',
                                unsafe_allow_html=True,
                            )



        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

        with st.expander("How scores are calculated"):
            st.markdown(
                '<table class="scoring-table">'
                "<tr><td>Bestseller badge at competitor</td><td>+10</td></tr>"
                "<tr><td>High Rated badge at competitor</td><td>+5</td></tr>"
                "<tr><td>Customer rating 4.0+</td><td>+3</td></tr>"
                "<tr><td>100+ customer reviews</td><td>+2</td></tr>"
                "<tr><td>500+ customer reviews</td><td>+3</td></tr>"
                "<tr><td>Has listed price</td><td>+1</td></tr>"
                "<tr><td>Each additional competitor carrying it</td><td>+3</td></tr>"
                "</table>"
                '<div style="margin-top:10px; font-size:12px; color:var(--text-tertiary);">'
                "Products are de-duplicated across competitors. Higher scores indicate stronger "
                "competitive signals — products that multiple big-box retailers are actively pushing."
                "</div>",
                unsafe_allow_html=True,
            )

# --- Tab 2: Competitor Catalog ---
with tab2:
    search_term = st.text_input(
        "Search",
        placeholder="Search products, brands, sources...",
        label_visibility="collapsed",
    )

    comp_data = []
    for p in competitors:
        comp_data.append({
            "Source": p["source"],
            "Name": p["name"][:80],
            "Brand": p.get("brand", ""),
            "Price": round(p["price"], 2) if p.get("price") else None,
            "Rating": round(p["rating"], 1) if p.get("rating") else None,
            "Reviews": int(p["reviews"]) if p.get("reviews") else None,
            "Category": p.get("category", ""),
            "Signal": p.get("signal", "").replace("_", " ").title() or "\u2014",
        })

    df_comp = pd.DataFrame(comp_data)

    if selected_cat != "All":
        df_comp = df_comp[df_comp["Category"] == selected_cat]
    if selected_source != "All":
        df_comp = df_comp[df_comp["Source"] == selected_source]
    if search_term:
        mask = df_comp.apply(lambda row: search_term.lower() in str(row).lower(), axis=1)
        df_comp = df_comp[mask]

    st.markdown(
        f'<div class="result-count">Showing <strong>{len(df_comp):,}</strong> products</div>',
        unsafe_allow_html=True,
    )

    st.dataframe(
        df_comp,
        use_container_width=True,
        hide_index=True,
        height=560,
        column_config={
            "Name": st.column_config.TextColumn(width="large"),
            "Price": st.column_config.NumberColumn(format="$%.2f"),
            "Rating": st.column_config.NumberColumn(format="%.1f"),
            "Reviews": st.column_config.NumberColumn(format="%d"),
        },
    )

# --- Tab 3: Changes (Month-over-Month) ---
with tab3:
    if not diff_data:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-state-icon" style="font-size:32px; color:#9ca3af;">--</div>'
            '<div class="empty-state-title">No comparison data yet</div>'
            '<div class="empty-state-desc">'
            "Run the scraper again next month to see month-over-month changes: "
            "new products at competitors, removed items, and price movements. "
            "This is where the mystery-shopper model shines — tracking what's "
            "changing on competitors' shelves over time."
            '</div></div>',
            unsafe_allow_html=True,
        )
    else:
        # MoM metric cards
        new_items = diff_data.get("new_items", [])
        removed_items = diff_data.get("removed_items", [])
        price_changes = diff_data.get("price_changes", [])

        mcol1, mcol2, mcol3 = st.columns(3)
        with mcol1:
            st.markdown(
                f'<div class="mom-card">'
                f'<div class="mom-card-value">{len(new_items)}</div>'
                f'<div class="mom-card-label">New Items</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with mcol2:
            st.markdown(
                f'<div class="mom-card">'
                f'<div class="mom-card-value">{len(removed_items)}</div>'
                f'<div class="mom-card-label">Removed Items</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with mcol3:
            st.markdown(
                f'<div class="mom-card">'
                f'<div class="mom-card-value">{len(price_changes)}</div>'
                f'<div class="mom-card-label">Price Changes</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

        if new_items:
            st.markdown(
                '<div style="font-size:14px; font-weight:600; color:#111827; margin-bottom:12px;">'
                'New at Competitors</div>',
                unsafe_allow_html=True,
            )
            df_new = pd.DataFrame([{
                "Source": i["source"],
                "Name": i["name"][:80],
                "Brand": i.get("brand", ""),
                "Price": round(i["price"], 2) if i.get("price") else None,
                "Signal": i.get("signal", "").replace("_", " ").title() or "\u2014",
            } for i in new_items[:50]])
            st.dataframe(
                df_new,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Name": st.column_config.TextColumn(width="large"),
                    "Price": st.column_config.NumberColumn(format="$%.2f"),
                },
            )

        if price_changes:
            st.markdown(
                '<div style="font-size:14px; font-weight:600; color:#111827; margin:20px 0 12px;">'
                'Price Movements (5%+)</div>',
                unsafe_allow_html=True,
            )
            df_price = pd.DataFrame([{
                "Source": i["source"],
                "Name": i["name"][:60],
                "Old Price": round(i["previous_price"], 2) if i.get("previous_price") else None,
                "New Price": round(i["price"], 2) if i.get("price") else None,
                "Change": f"{i['price_change_pct']:+.1f}%",
            } for i in price_changes[:50]])
            st.dataframe(
                df_price,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Name": st.column_config.TextColumn(width="large"),
                    "Old Price": st.column_config.NumberColumn(format="$%.2f"),
                    "New Price": st.column_config.NumberColumn(format="$%.2f"),
                },
            )
