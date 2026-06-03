"""
MysteryScraper — Streamlit UI
Competitive intelligence dashboard for Jerry's Ace Hardware #17892.
"""

import io
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime
import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.enums import TA_LEFT, TA_CENTER

from analyze import find_gaps, rank_recommendations, diff_snapshots
from config import BRAND_ALIASES

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

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    section[data-testid="stSidebar"] {
        background-color: var(--bg-secondary);
        border-right: none;
        width: 260px !important;
    }
    section[data-testid="stSidebar"] > div { padding-top: 1.5rem; }
    section[data-testid="stSidebar"] .block-container { padding: 0.5rem 1.25rem !important; }
    section[data-testid="stSidebar"] hr { border-color: var(--border); margin: 0.75rem 0; }

    .stTabs [data-baseweb="tab-list"] {
        gap: 0; border-bottom: 1px solid var(--border); background: transparent;
    }
    .stTabs [data-baseweb="tab-highlight"] { display: none !important; }
    .stTabs [data-baseweb="tab-list"] button {
        background: transparent !important; border: none !important;
        border-bottom: 2px solid transparent !important;
        color: var(--text-secondary) !important; font-weight: 500 !important;
        font-size: 13px !important; padding: 10px 20px !important;
        border-radius: 0 !important; box-shadow: none !important; outline: none !important;
    }
    .stTabs [data-baseweb="tab-list"] button:hover {
        color: var(--text-primary) !important; border-bottom-color: transparent !important;
    }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        color: var(--text-primary) !important; border-bottom: 2px solid var(--accent) !important;
        background: transparent !important; font-weight: 600 !important;
    }

    .stSelectbox label, .stMultiSelect label, .stTextInput label {
        color: var(--text-secondary) !important; font-weight: 500 !important;
        font-size: 12px !important; text-transform: uppercase; letter-spacing: 0.04em;
    }
    .stTextInput input, .stTextInput input:focus, .stTextInput input:hover {
        border: 1px solid var(--border) !important; border-radius: 8px !important;
        padding: 10px 14px !important; font-size: 13px !important;
        background: var(--bg-primary) !important; color: var(--text-primary) !important;
        box-shadow: none !important; outline: none !important;
    }
    .stTextInput > div, .stTextInput > div > div {
        border: none !important; box-shadow: none !important; outline: none !important;
    }

    [data-baseweb="popover"], [data-baseweb="menu"], [data-baseweb="menu"] ul, [data-baseweb="menu"] li {
        background: var(--bg-primary) !important; color: var(--text-primary) !important;
    }
    [data-baseweb="menu"] li:hover { background: var(--bg-hover) !important; }
    .stSelectbox > div > div, .stSelectbox [data-baseweb="select"] > div {
        border: 1px solid var(--border) !important; border-radius: 8px !important;
        font-size: 13px !important; background: var(--bg-primary) !important;
        color: var(--text-primary) !important; box-shadow: none !important;
    }
    .stSelectbox [data-baseweb="select"], .stSelectbox [data-baseweb="select"] span,
    .stSelectbox [data-baseweb="select"] div {
        color: var(--text-primary) !important; -webkit-text-fill-color: var(--text-primary) !important;
    }

    [data-testid="stVerticalBlockBorderWrapper"] { border: none !important; }
    [data-testid="stExpander"] details { border: none !important; background: var(--bg-secondary) !important; }
    [data-testid="stDataFrame"] {
        border: 1px solid var(--border) !important; border-radius: 10px !important;
    }

    .stButton > button {
        background-color: var(--accent); color: white; border: none; border-radius: 8px;
        font-size: 13px; font-weight: 500; padding: 6px 16px;
    }
    .stButton > button:hover { background-color: var(--accent-hover); color: white; }

    .stat-card {
        background: var(--bg-secondary); border: none !important; border-radius: 10px;
        padding: 18px 22px; outline: none !important; box-shadow: none !important;
    }
    .stat-label {
        font-size: 11px; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.06em; color: var(--text-secondary); margin-bottom: 6px;
    }
    .stat-value { font-size: 30px; font-weight: 700; color: var(--text-primary); line-height: 1.1; }

    .summary-text {
        font-size: 14px; color: var(--text-secondary); line-height: 1.6; margin-bottom: 20px;
    }
    .summary-text strong { color: var(--text-primary); font-weight: 600; }

    .rec-table {
        width: 100%; border-collapse: separate; border-spacing: 0; font-size: 13px;
        border: none; border-radius: 10px; overflow: hidden;
    }
    .rec-table thead th {
        text-align: left; padding: 10px 14px; font-size: 11px; font-weight: 600;
        text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary);
        background: var(--bg-secondary); border-bottom: 1px solid #f3f4f6;
    }
    .rec-table tbody td {
        padding: 12px 14px; color: var(--text-primary); border-bottom: 1px solid #f3f4f6;
    }
    .rec-table tbody tr:last-child td { border-bottom: none; }
    .rec-table tbody tr:hover td { background: var(--bg-secondary); }
    .rec-table .rank-cell { color: var(--text-tertiary); font-weight: 600; font-size: 12px; width: 40px; text-align: center; }
    .rec-table .product-cell { font-weight: 500; max-width: 320px; }
    .rec-table .meta-cell { color: var(--text-secondary); font-size: 12px; }
    .rec-table .price-cell { font-weight: 600; font-variant-numeric: tabular-nums; }

    .badge { display: inline-block; padding: 3px 10px; border-radius: 9999px; font-size: 11px; font-weight: 500; }
    .badge-bestseller { background: #d1fae5; color: #065f46; }
    .badge-high-rated { background: #dbeafe; color: #1d4ed8; }
    .badge-empty { color: var(--text-tertiary); font-size: 13px; }

    .source-tag { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: var(--text-secondary); margin-right: 6px; }
    .source-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }

    .score-bar-wrap { display: flex; align-items: center; gap: 10px; }
    .score-bar-track { width: 64px; height: 6px; background: #e5e7eb; border-radius: 3px; overflow: hidden; }
    .score-bar-fill { height: 100%; background: var(--accent); border-radius: 3px; }
    .score-num { font-size: 12px; font-weight: 600; color: var(--text-secondary); min-width: 18px; }

    .breadcrumb { display: flex; align-items: center; gap: 8px; margin-bottom: 24px; flex-wrap: wrap; }
    .breadcrumb-item { font-size: 14px; font-weight: 500; color: var(--text-secondary); }
    .breadcrumb-item.active { color: var(--accent); font-weight: 600; }
    .breadcrumb-sep { color: var(--text-tertiary); font-size: 13px; }

    .sources-bar {
        display: flex; align-items: center; gap: 20px; margin-bottom: 20px;
        padding: 12px 18px; background: var(--bg-secondary); border-radius: 10px;
    }
    .sources-bar-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-tertiary); }
    .source-chip { display: inline-flex; align-items: center; gap: 7px; font-size: 13px; font-weight: 500; color: var(--text-primary); }
    .source-chip-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }

    .result-count { font-size: 13px; color: var(--text-secondary); margin-bottom: 12px; }
    .result-count strong { color: var(--text-primary); font-weight: 600; }

    .scoring-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .scoring-table td { padding: 6px 0; color: var(--text-secondary); }
    .scoring-table td:last-child { text-align: right; font-weight: 600; color: var(--text-primary); }

    .info-box { background: var(--bg-secondary); border: none; border-radius: 8px; padding: 12px 16px; font-size: 13px; color: var(--text-secondary); }

    .sidebar-wordmark { font-size: 15px; font-weight: 700; color: var(--text-primary); display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
    .sidebar-wordmark-icon { width: 24px; height: 24px; background: var(--accent); border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 13px; }
    .sidebar-context { font-size: 12px; color: var(--text-secondary); line-height: 1.5; }
    .sidebar-stat { font-size: 12px; color: var(--text-tertiary); line-height: 1.8; }
    .sidebar-section-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-tertiary); margin-bottom: 8px; margin-top: 4px; }

    .empty-state { text-align: center; padding: 72px 24px; }
    .empty-state-title { font-size: 16px; font-weight: 600; color: var(--text-primary); margin-bottom: 6px; }
    .empty-state-desc { font-size: 13px; color: var(--text-secondary); max-width: 420px; margin: 0 auto; line-height: 1.6; }

    .mom-card { background: var(--bg-secondary); border: none; border-radius: 10px; padding: 16px 20px; text-align: center; }
    .mom-card-value { font-size: 26px; font-weight: 700; color: var(--text-primary); }
    .mom-card-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); margin-top: 4px; }
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


def generate_gaps_pdf(recs: list, gaps_count: int, num_comp: int, snap_dt: str, cat_filter: str = "All") -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    accent = colors.HexColor("#059669")
    light_bg = colors.HexColor("#f9fafb")
    border_color = colors.HexColor("#e5e7eb")
    text_secondary = colors.HexColor("#6b7280")

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Normal"], fontSize=18, fontName="Helvetica-Bold", textColor=colors.HexColor("#111827"), spaceAfter=8)
    subtitle_style = ParagraphStyle("subtitle", parent=styles["Normal"], fontSize=10, fontName="Helvetica", textColor=text_secondary, spaceAfter=20)
    section_style = ParagraphStyle("section", parent=styles["Normal"], fontSize=11, fontName="Helvetica-Bold", textColor=colors.HexColor("#111827"), spaceBefore=24, spaceAfter=10)
    small_style = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, fontName="Helvetica", textColor=text_secondary)

    story = []

    # Header
    story.append(Paragraph("Gaps & Recommendations", title_style))
    filter_note = f" — Category: {cat_filter}" if cat_filter != "All" else ""
    story.append(Paragraph(
        f"Jerry's Ace Hardware #17892 · Denver, CO · {snap_dt}{filter_note}",
        subtitle_style,
    ))

    # Summary line
    story.append(Paragraph(
        f"Found <b>{gaps_count:,} gaps</b> across <b>{num_comp} competitors</b>. "
        f"Top <b>{len(recs)}</b> products ranked by score descending.",
        ParagraphStyle("summary", parent=styles["Normal"], fontSize=10, fontName="Helvetica",
                       textColor=colors.HexColor("#374151"), spaceAfter=14),
    ))

    # Recommendations table
    story.append(Paragraph("Top Recommendations", section_style))

    header = ["#", "Product", "Brand", "Category", "Price", "Sources", "Signal", "Score"]
    # Total = 7.0" to fit within letter page at 0.75" margins each side
    col_widths = [0.25 * inch, 2.15 * inch, 0.95 * inch, 0.85 * inch, 0.6 * inch, 0.9 * inch, 0.75 * inch, 0.45 * inch]

    cell_style = ParagraphStyle("cell", fontSize=8, fontName="Helvetica", leading=10)

    table_data = [header]
    filtered_recs = [r for r in recs if cat_filter == "All" or r.get("category") == cat_filter]

    for i, r in enumerate(filtered_recs, 1):
        sources = r.get("sources", [r.get("source", "")])
        price_str = f"${r['price']:.2f}" if r.get("price") else "—"
        signal = r.get("signal", "").replace("_", " ").title() or "—"
        sources_str = ", ".join(s.replace("Home Depot", "Home Dep") for s in sources[:2])
        table_data.append([
            str(i),
            Paragraph(r["name"][:75], cell_style),
            Paragraph(r.get("brand", ""), cell_style),
            Paragraph(r.get("category", ""), cell_style),
            price_str,
            Paragraph(sources_str, cell_style),
            signal,
            str(r["score"]),
        ])

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), accent),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, light_bg]),
        ("GRID", (0, 0), (-1, -1), 0.4, border_color),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (4, 0), (4, -1), "RIGHT"),
        ("ALIGN", (7, 0), (7, -1), "CENTER"),
    ]))
    story.append(tbl)

    # Scoring legend
    story.append(Spacer(1, 20))
    story.append(Paragraph("Scoring Guide", section_style))
    scoring_rows = [
        ["Bestseller badge at competitor", "+5"],
        ["High Rated badge at competitor", "+4"],
        ["Customer rating 4.0+", "+3"],
        ["100+ customer reviews", "+2"],
        ["500+ customer reviews", "+2"],
        ["Has listed price", "+2"],
        ["Each additional competitor carrying it", "+3"],
        ["Final ordering", "Score descending"],
    ]
    score_tbl = Table(scoring_rows, colWidths=[4.5 * inch, 0.6 * inch])
    score_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#374151")),
        ("TEXTCOLOR", (1, 0), (1, -1), accent),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, border_color),
    ]))
    story.append(score_tbl)

    # Footer
    story.append(Spacer(1, 24))
    story.append(Paragraph(
        f"Generated by MysteryScraper · {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
        small_style,
    ))

    doc.build(story)
    return buf.getvalue()


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


# --- Data loading ---
@st.cache_data
def load_jerrys_md():
    """Parse verified Jerry's inventory from markdown."""
    md_path = Path("/Users/Welcome123/.superset/worktrees/MysteryScraper/clarification-needed/output/ace/jerrys_paint_products.md")
    if not md_path.exists():
        return pd.DataFrame(), []

    text = md_path.read_text()
    rows = []
    current_cat = ""
    for line in text.splitlines():
        if line.startswith("## "):
            m = re.match(r"## (.+?) \((\d+)\)", line)
            if m:
                current_cat = m.group(1)
        if line.startswith("| ") and not line.startswith("| Brand") and not line.startswith("|---"):
            parts = [c.strip() for c in line.split("|")[1:-1]]
            if len(parts) >= 4:
                price_str = parts[2].replace("$", "").replace(",", "")
                try:
                    price = float(price_str)
                except ValueError:
                    price = 0.0
                try:
                    qty = int(parts[3])
                except ValueError:
                    qty = 0
                rows.append({
                    "brand": parts[0],
                    "product": parts[1],
                    "price": price,
                    "qty": qty,
                    "category": current_cat,
                })

    df = pd.DataFrame(rows)
    # Also build list format for gap analysis
    ace_products = [{"name": r["product"], "brand": r["brand"], "price": r["price"],
                     "category": r["category"], "qty": r["qty"]} for r in rows]
    return df, ace_products


@st.cache_data
def list_snapshot_dates(snapshot_dir="data/snapshots"):
    snap_dir = Path(snapshot_dir)
    if not snap_dir.exists():
        return []

    comp_files = sorted(snap_dir.glob("*_competitors.json"))
    if not comp_files:
        return []

    return [p.stem.split("_")[0] for p in comp_files]


@st.cache_data
def load_snapshot(snapshot_date=None, snapshot_dir="data/snapshots"):
    snap_dir = Path(snapshot_dir)
    if not snap_dir.exists():
        return None, None

    comp_files = sorted(snap_dir.glob("*_competitors.json"))
    if not comp_files:
        return None, None

    if snapshot_date:
        selected_comp = snap_dir / f"{snapshot_date}_competitors.json"
        if not selected_comp.exists():
            selected_comp = comp_files[-1]
    else:
        selected_comp = comp_files[-1]
    snap_date = selected_comp.stem.split("_")[0]

    with open(selected_comp) as f:
        competitors = json.load(f)

    return competitors, snap_date


@st.cache_data
def load_diff(snapshot_date=None, diff_dir="data/diffs"):
    d = Path(diff_dir)
    if not d.exists():
        return None
    if snapshot_date:
        selected_diff = d / f"{snapshot_date}_diff.json"
        if selected_diff.exists():
            with open(selected_diff) as f:
                return json.load(f)
        return None
    diffs = sorted(d.glob("*_diff.json"))
    if not diffs:
        return None
    with open(diffs[-1]) as f:
        return json.load(f)


@st.cache_data
def load_serpapi_data():
    """Load scraped SerpAPI data from output/serpapi/."""
    serpapi_dir = Path("output/serpapi")
    if not serpapi_dir.exists():
        return pd.DataFrame()

    store_files = {
        "Home Depot": "home_depot.json",
        "Target": "target.json",
        "Lowes": "lowes.json",
        "Walmart": "walmart.json",
        "Home Depot (Native)": "home_depot_native.json",
        "Walmart (Apify)": "walmart_apify.json",
        "Target (Redsky)": "target_redsky.json",
        "Ace Hardware": "ace_hardware.json",
    }

    all_rows = []
    for store, filename in store_files.items():
        filepath = serpapi_dir / filename
        if not filepath.exists():
            continue
        try:
            with open(filepath) as f:
                items = json.load(f)
            for item in items:
                # Extract price from various formats
                price_raw = item.get("price", item.get("extracted_price"))
                # Target Redsky nests price differently
                if price_raw is None and "price" in item.get("item", {}):
                    offer = item.get("item", {}).get("price", {}).get("formatted_current_price")
                    if offer:
                        price_raw = offer
                # Walmart Apify uses different fields
                if price_raw is None:
                    price_raw = item.get("priceInfo", {}).get("currentPrice", {}).get("price") if isinstance(item.get("priceInfo"), dict) else None
                # Ace uses retailPrice
                if price_raw is None:
                    price_raw = item.get("retailPrice")

                price = None
                if price_raw is not None:
                    if isinstance(price_raw, (int, float)):
                        price = float(price_raw)
                    elif isinstance(price_raw, str):
                        cleaned = re.sub(r'[^\d.]', '', price_raw)
                        try:
                            price = float(cleaned)
                        except ValueError:
                            pass

                # Extract name from various formats
                name = (
                    item.get("title")
                    or item.get("name")
                    or item.get("item", {}).get("product_description", {}).get("title", "")
                    or item.get("productName", "")
                    or ""
                )

                # Extract rating
                rating = (
                    item.get("rating")
                    or item.get("item", {}).get("ratings_and_reviews", {}).get("statistics", {}).get("rating", {}).get("average")
                )

                # Extract reviews
                reviews = (
                    item.get("reviews")
                    or item.get("total_reviews")
                    or item.get("item", {}).get("ratings_and_reviews", {}).get("statistics", {}).get("rating", {}).get("count")
                )

                if not name:
                    continue

                all_rows.append({
                    "Source": store,
                    "Name": str(name)[:100],
                    "Price": price,
                    "Rating": float(rating) if rating else None,
                    "Reviews": int(reviews) if reviews else None,
                    "Link": item.get("link", item.get("product_link", item.get("url", ""))),
                    "Thumbnail": item.get("thumbnail", item.get("image", "")),
                })
        except Exception:
            continue

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# --- Load data ---
snapshot_dates = list_snapshot_dates()
latest_snapshot_date = snapshot_dates[-1] if snapshot_dates else None
previous_snapshot_date = snapshot_dates[-2] if len(snapshot_dates) >= 2 else None

if latest_snapshot_date and st.session_state.get("selected_snapshot_date") not in snapshot_dates:
    st.session_state["selected_snapshot_date"] = latest_snapshot_date

selected_snapshot_date = st.session_state.get("selected_snapshot_date")
jerrys_df, ace_products = load_jerrys_md()
competitors, snap_date = load_snapshot(selected_snapshot_date)
has_jerrys = not jerrys_df.empty
has_snapshot = bool(competitors)

# --- Analysis ---
if has_jerrys and has_snapshot:
    gaps = find_gaps(ace_products, competitors)
    recommendations = rank_recommendations(gaps)
else:
    gaps = []
    recommendations = []

diff_data = load_diff(snap_date)

if snap_date:
    try:
        date_display = datetime.strptime(snap_date, "%Y-%m-%d").strftime("%b %d, %Y")
    except ValueError:
        date_display = snap_date
else:
    date_display = datetime.now().strftime("%b %d, %Y")

num_competitors = len(set(p["source"] for p in competitors)) if competitors else 0
comp_categories = set(p["category"] for p in competitors if p.get("category")) if competitors else set()
jerry_categories = sorted(jerrys_df["category"].unique()) if has_jerrys else []

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
        '<div class="sidebar-context">'
        "Jerry's Ace Hardware #17892<br>"
        "2101 N Humboldt St, Denver CO 80205"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    st.markdown('<div class="sidebar-section-label">Filters</div>', unsafe_allow_html=True)
    cat_options = ["All"] + jerry_categories
    selected_cat = st.selectbox("Category", cat_options, label_visibility="collapsed")

    all_comp_sources = sorted(set(p["source"] for p in competitors)) if competitors else []
    source_options = ["All"] + all_comp_sources
    selected_source = st.selectbox("Competitor", source_options, label_visibility="collapsed")

    st.markdown("---")

    if snapshot_dates:
        st.markdown('<div class="sidebar-section-label">Run Version</div>', unsafe_allow_html=True)
        selected_index = snapshot_dates.index(snap_date) if snap_date in snapshot_dates else len(snapshot_dates) - 1
        selected_run = st.selectbox(
            "Snapshot run",
            options=snapshot_dates,
            index=selected_index,
            format_func=lambda d: f"{d} (latest)" if d == latest_snapshot_date else d,
            label_visibility="collapsed",
            key="snapshot_run_selector",
        )
        if selected_run != st.session_state.get("selected_snapshot_date"):
            st.session_state["selected_snapshot_date"] = selected_run
            st.rerun()

        if previous_snapshot_date and snap_date == latest_snapshot_date:
            if st.button("Use Previous Run", use_container_width=True):
                st.session_state["selected_snapshot_date"] = previous_snapshot_date
                st.rerun()
        elif latest_snapshot_date and snap_date != latest_snapshot_date:
            if st.button("Use Latest Run", use_container_width=True):
                st.session_state["selected_snapshot_date"] = latest_snapshot_date
                st.rerun()

        st.markdown("---")

    snapshot_count = len(competitors) if competitors else 0
    st.markdown(
        f'<div class="sidebar-section-label">Snapshot</div>'
        f'<div class="sidebar-stat">'
        f"{date_display}<br>"
        f"{snapshot_count:,} competitor products<br>"
        f"{len(ace_products):,} Jerry's verified products<br>"
        f"{len(jerry_categories)} categories<br>"
        f"{num_competitors} competitors tracked"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    st.markdown('<div class="sidebar-section-label">Scraper Settings</div>', unsafe_allow_html=True)

    from config import CATEGORIES as _ALL_CATEGORIES
    available_cats = list(_ALL_CATEGORIES.keys())
    scrape_categories = st.multiselect(
        "Categories to scrape",
        options=available_cats,
        default=available_cats,
        key="scrape_cats",
    )

    max_budget = st.number_input(
        "Apify budget ($)",
        min_value=1,
        max_value=100,
        value=5,
        step=1,
        help="Max Apify spend for this scrape run. Actors are aborted if budget is exceeded.",
        key="max_budget",
    )

    max_total = st.number_input(
        "Max total products",
        min_value=10,
        max_value=2000,
        value=400,
        step=50,
        help="Target total products across all stores. Divided evenly across stores and search terms.",
        key="max_total",
    )

    st.markdown("---")

    st.markdown('<div class="sidebar-section-label">Actions</div>', unsafe_allow_html=True)
    if st.button("Re-run Scrapers", use_container_width=True):
        cmd = ["python3", "-u", "run_snapshot.py"]
        if scrape_categories and set(scrape_categories) != set(available_cats):
            cmd += ["--categories"] + scrape_categories
        cmd += ["--max-results", str(max_total)]
        cmd += ["--budget", str(max_budget)]
        with st.spinner("Running scrapers (Apify + Direct APIs)... This takes ~2 min."):
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=1200,
                cwd=str(Path(__file__).parent),
            )
        if result.returncode == 0:
            st.success("Scrape complete! Refreshing data & analysis...")
            with st.expander("Scraper output"):
                st.code(result.stdout, language="text")
            st.cache_data.clear()
            st.session_state.pop("selected_snapshot_date", None)
            st.rerun()
        else:
            st.error("Scraper failed!")
            with st.expander("Error log"):
                st.code(result.stderr or result.stdout, language="text")

# --- Filter Jerry's data ---
jf = jerrys_df.copy() if has_jerrys else pd.DataFrame()
if has_jerrys and selected_cat != "All":
    jf = jf[jf["category"] == selected_cat]

# --- Breadcrumb ---
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
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    val = f"{len(jf):,}" if has_jerrys else "—"
    st.markdown(stat_card("Jerry's Products", val), unsafe_allow_html=True)
with col2:
    val = f"{jf['qty'].sum():,}" if has_jerrys and 'qty' in jf.columns else "—"
    st.markdown(stat_card("Total Units", val), unsafe_allow_html=True)
with col3:
    val = f"{len(jf['brand'].unique())}" if has_jerrys and 'brand' in jf.columns else "—"
    st.markdown(stat_card("Jerry's Brands", val), unsafe_allow_html=True)
with col4:
    st.markdown(stat_card("Gaps Found", f"{len(gaps):,}"), unsafe_allow_html=True)
with col5:
    scraped_total = len(competitors) if has_snapshot else 0
    st.markdown(stat_card("Scraped Products", f"{scraped_total:,}"), unsafe_allow_html=True)

# --- Sources bar ---
all_sources = sorted(set(p["source"] for p in competitors)) if competitors else []
source_chips = []
for s in all_sources:
    color = SOURCE_COLORS.get(s, "#9ca3af")
    count = sum(1 for p in (competitors or []) if p.get("source") == s)
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
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Jerry's Inventory", "Gaps & Recommendations", "Competitor Catalog", "Changes", "Scraped Data"])

# --- Tab 1: Jerry's Inventory ---
with tab1:
  if not has_jerrys:
    st.markdown(
        '<div class="empty-state">'
        '<div class="empty-state-title">No Jerry\'s inventory data loaded</div>'
        '<div class="empty-state-desc">Check the inventory file path.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
  else:
    st.markdown(
        f'<div class="summary-text">'
        f'<strong>{len(jf):,} verified in-stock products</strong> across '
        f'<strong>{len(jf["brand"].unique())} brands</strong> and '
        f'<strong>{len(jf["category"].unique())} categories</strong> at '
        f"Jerry's Ace Hardware #17892, Denver CO."
        f'</div>',
        unsafe_allow_html=True,
    )

    # Brand breakdown
    st.markdown("**Brand Summary**")
    brand_stats = jf.groupby("brand").agg(
        products=("product", "count"),
        total_units=("qty", "sum"),
        avg_price=("price", "mean"),
        min_price=("price", "min"),
        max_price=("price", "max"),
    ).sort_values("products", ascending=False).reset_index()

    st.dataframe(
        brand_stats,
        use_container_width=True,
        hide_index=True,
        column_config={
            "brand": "Brand",
            "products": st.column_config.NumberColumn("Products"),
            "total_units": st.column_config.NumberColumn("Units"),
            "avg_price": st.column_config.NumberColumn("Avg Price", format="$%.2f"),
            "min_price": st.column_config.NumberColumn("Min", format="$%.2f"),
            "max_price": st.column_config.NumberColumn("Max", format="$%.2f"),
        },
    )

    # Full product table
    st.markdown("**Full Product List**")
    st.dataframe(
        jf[["category", "brand", "product", "price", "qty"]].sort_values(["category", "brand"]),
        use_container_width=True,
        hide_index=True,
        height=500,
        column_config={
            "category": "Category",
            "brand": "Brand",
            "product": st.column_config.TextColumn("Product", width="large"),
            "price": st.column_config.NumberColumn("Price", format="$%.2f"),
            "qty": st.column_config.NumberColumn("Stock"),
        },
    )

    # Low stock alert
    low_stock = jf[jf["qty"] <= 3].sort_values("qty")
    if not low_stock.empty:
        st.markdown(f"**Low Stock Alert** ({len(low_stock)} items with 3 or fewer units)")
        st.dataframe(
            low_stock[["category", "brand", "product", "price", "qty"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                "qty": st.column_config.NumberColumn("Stock"),
            },
        )


# --- Tab 2: Gaps & Recommendations ---
with tab2:
    if not recommendations:
        st.markdown(
            '<div class="empty-state">'
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
            f'<strong>{num_competitors} competitors</strong>. '
            f'Top <strong>{len(recommendations)}</strong> products '
            f"Jerry's should consider stocking, ranked by score descending."
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
                'Product Details</div>',
                unsafe_allow_html=True,
            )

            for i, r in enumerate(filtered_recs[:15], 1):
                sources = r.get("sources", [r.get("source", "")])
                price_str = f"${r['price']:.2f}" if r.get("price") else "N/A"

                with st.expander(f"#{i}  {r['name'][:70]}"):
                    dcol1, dcol2 = st.columns(2)
                    with dcol1:
                        rating_str = f"{r['rating']:.1f}" if r.get("rating") else "N/A"
                        reviews_str = f"{int(r['reviews']):,}" if r.get("reviews") else "N/A"
                        st.markdown(
                            f'<table class="scoring-table">'
                            f'<tr><td>Brand</td><td>{r.get("brand", "Unknown")}</td></tr>'
                            f'<tr><td>Category</td><td>{r.get("category", "N/A")}</td></tr>'
                            f'<tr><td>Price</td><td>{price_str}</td></tr>'
                            f'<tr><td>Rating</td><td>{rating_str}</td></tr>'
                            f'<tr><td>Reviews</td><td>{reviews_str}</td></tr>'
                            f'<tr><td>Signal</td><td>{signal_badge(r.get("signal", ""))}</td></tr>'
                            f'<tr><td>Score</td><td><strong>{r["score"]}</strong> / 30</td></tr>'
                            f'<tr><td>Carried By</td><td>{source_tags(sources)}</td></tr>'
                            f'</table>',
                            unsafe_allow_html=True,
                        )

                    with dcol2:
                        # Find similar Jerry's products
                        comp_brand = r.get("brand", "").lower()
                        comp_name = r.get("name", "").lower()
                        similar = []
                        for p in ace_products:
                            ace_name = p.get("name", "").lower()
                            words = set(comp_name.split()) - {"the", "a", "an", "and", "or", "for", "with", "in", "of", "to"}
                            ace_words = set(ace_name.split()) - {"the", "a", "an", "and", "or", "for", "with", "in", "of", "to"}
                            overlap = len(words & ace_words)
                            if overlap >= 2:
                                similar.append((p, overlap))
                        similar.sort(key=lambda x: x[1], reverse=True)
                        similar = [s[0] for s in similar[:5]]

                        st.markdown(
                            "<div style='font-size:13px; font-weight:600; color:#111827; margin-bottom:12px;'>"
                            "Jerry's Closest Products</div>",
                            unsafe_allow_html=True,
                        )
                        if similar:
                            for sp in similar:
                                sp_price = f"${sp['price']:.2f}" if sp.get("price") else "N/A"
                                st.markdown(
                                    f'<div style="padding:8px 12px; background:#f9fafb; border-radius:6px; '
                                    f'margin-bottom:6px; font-size:13px;">'
                                    f'<div style="font-weight:500;">{sp["name"][:65]}</div>'
                                    f'<div style="font-size:12px; color:#9ca3af; margin-top:2px;">'
                                    f'{sp.get("brand", "")} | {sp_price}</div>'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )
                        else:
                            st.markdown(
                                '<div style="padding:16px; background:#fef2f2; border-radius:8px; text-align:center;">'
                                '<div style="font-size:14px; font-weight:600; color:#991b1b; margin-bottom:4px;">'
                                'Gap Confirmed</div>'
                                '<div style="font-size:12px; color:#6b7280;">'
                                "Jerry's carries no similar products in this space.</div>"
                                '</div>',
                                unsafe_allow_html=True,
                            )

        with st.expander("How scores are calculated"):
            st.markdown(
                '<table class="scoring-table">'
                "<tr><td>Bestseller badge at competitor</td><td>+5</td></tr>"
                "<tr><td>High Rated badge at competitor</td><td>+4</td></tr>"
                "<tr><td>Customer rating 4.0+</td><td>+3</td></tr>"
                "<tr><td>100+ customer reviews</td><td>+2</td></tr>"
                "<tr><td>500+ customer reviews</td><td>+2</td></tr>"
                "<tr><td>Has listed price</td><td>+2</td></tr>"
                "<tr><td>Each additional competitor carrying it</td><td>+3</td></tr>"
                "<tr><td>Final ordering</td><td>Score descending</td></tr>"
                "</table>",
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        pdf_bytes = generate_gaps_pdf(
            recommendations, len(gaps), num_competitors, date_display, selected_cat
        )
        st.download_button(
            label="Download PDF",
            data=pdf_bytes,
            file_name=f"gaps_recommendations_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
        )


# --- Tab 3: Competitor Catalog ---
with tab3:
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

    # Price comparison by retailer
    st.markdown("**Average Price by Retailer**")
    price_rows = []
    for src in all_sources:
        src_items = [p for p in competitors if p["source"] == src and p.get("price")]
        if src_items:
            prices = [p["price"] for p in src_items]
            price_rows.append({
                "Retailer": src,
                "Products": len(src_items),
                "Avg Price": sum(prices) / len(prices),
                "Min": min(prices),
                "Max": max(prices),
            })
    # Add Jerry's
    jerry_prices = jf["price"].dropna()
    if not jerry_prices.empty:
        price_rows.insert(0, {
            "Retailer": "Jerry's Ace #17892",
            "Products": len(jf),
            "Avg Price": jerry_prices.mean(),
            "Min": jerry_prices.min(),
            "Max": jerry_prices.max(),
        })

    st.dataframe(
        pd.DataFrame(price_rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Avg Price": st.column_config.NumberColumn(format="$%.2f"),
            "Min": st.column_config.NumberColumn(format="$%.2f"),
            "Max": st.column_config.NumberColumn(format="$%.2f"),
        },
    )


# --- Tab 4: Changes ---
with tab4:
    if not diff_data:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-state-title">No comparison data yet</div>'
            '<div class="empty-state-desc">'
            "Run the scraper again next month to see month-over-month changes: "
            "new products at competitors, removed items, and price movements."
            '</div></div>',
            unsafe_allow_html=True,
        )
    else:
        new_items = diff_data.get("new_items", [])
        removed_items = diff_data.get("removed_items", [])
        price_changes = diff_data.get("price_changes", [])

        mcol1, mcol2, mcol3 = st.columns(3)
        with mcol1:
            st.markdown(f'<div class="mom-card"><div class="mom-card-value">{len(new_items)}</div><div class="mom-card-label">New Items</div></div>', unsafe_allow_html=True)
        with mcol2:
            st.markdown(f'<div class="mom-card"><div class="mom-card-value">{len(removed_items)}</div><div class="mom-card-label">Removed</div></div>', unsafe_allow_html=True)
        with mcol3:
            st.markdown(f'<div class="mom-card"><div class="mom-card-value">{len(price_changes)}</div><div class="mom-card-label">Price Changes</div></div>', unsafe_allow_html=True)

        if new_items:
            st.markdown("**New at Competitors**")
            df_new = pd.DataFrame([{
                "Source": i["source"], "Name": i["name"][:80], "Brand": i.get("brand", ""),
                "Price": round(i["price"], 2) if i.get("price") else None,
            } for i in new_items[:50]])
            st.dataframe(df_new, use_container_width=True, hide_index=True,
                         column_config={"Price": st.column_config.NumberColumn(format="$%.2f")})

        if price_changes:
            st.markdown("**Price Movements (5%+)**")
            df_price = pd.DataFrame([{
                "Source": i["source"], "Name": i["name"][:60],
                "Old Price": round(i["previous_price"], 2) if i.get("previous_price") else None,
                "New Price": round(i["price"], 2) if i.get("price") else None,
                "Change": f"{i['price_change_pct']:+.1f}%",
            } for i in price_changes[:50]])
            st.dataframe(df_price, use_container_width=True, hide_index=True,
                         column_config={
                             "Old Price": st.column_config.NumberColumn(format="$%.2f"),
                             "New Price": st.column_config.NumberColumn(format="$%.2f"),
                         })


# --- Tab 5: Scraped Data ---
with tab5:
    if not has_snapshot:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-state-title">No scraped data yet</div>'
            '<div class="empty-state-desc">'
            'Click <strong>Re-run Scrapers</strong> in the sidebar to scrape all stores.'
            '</div></div>',
            unsafe_allow_html=True,
        )
    else:
        scraped_df = pd.DataFrame([{
            "Source": p.get("source", ""),
            "Name": str(p.get("name", ""))[:100],
            "Price": p.get("price"),
            "Rating": float(p["rating"]) if p.get("rating") else None,
            "Reviews": int(p["reviews"]) if p.get("reviews") else None,
            "Brand": p.get("brand", ""),
            "Signal": p.get("signal", ""),
            "Search Term": p.get("search_term", ""),
        } for p in competitors if p.get("name")])

        # Store breakdown stats
        store_counts = scraped_df["Source"].value_counts()
        st.markdown(
            f'<div class="summary-text">'
            f'<strong>{len(scraped_df):,} products</strong> scraped across '
            f'<strong>{scraped_df["Source"].nunique()} sources</strong> via Apify.'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Stat cards per store
        store_cols = st.columns(min(len(store_counts), 5))
        for col, (store, count) in zip(store_cols, store_counts.items()):
            with col:
                st.markdown(stat_card(store, f"{count:,}"), unsafe_allow_html=True)

        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

        # Filter by store
        store_filter = st.selectbox(
            "Filter by store",
            ["All"] + sorted(scraped_df["Source"].unique().tolist()),
            key="scraped_store_filter",
        )

        filtered = scraped_df.copy()
        if store_filter != "All":
            filtered = filtered[filtered["Source"] == store_filter]

        # Search
        search = st.text_input(
            "Search products",
            placeholder="Search by name...",
            key="scraped_search",
            label_visibility="collapsed",
        )
        if search:
            filtered = filtered[filtered["Name"].str.contains(search, case=False, na=False)]

        st.markdown(
            f'<div class="result-count">Showing <strong>{len(filtered):,}</strong> products</div>',
            unsafe_allow_html=True,
        )

        st.dataframe(
            filtered[["Source", "Name", "Brand", "Price", "Rating", "Reviews", "Signal"]],
            use_container_width=True,
            hide_index=True,
            height=560,
            column_config={
                "Name": st.column_config.TextColumn("Product", width="large"),
                "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
                "Rating": st.column_config.NumberColumn("Rating", format="%.1f"),
                "Reviews": st.column_config.NumberColumn("Reviews", format="%d"),
            },
        )

        # Price comparison
        st.markdown("**Average Price by Store**")
        price_summary = (
            filtered[filtered["Price"].notna()]
            .groupby("Source")["Price"]
            .agg(["count", "mean", "min", "max"])
            .reset_index()
            .rename(columns={"Source": "Store", "count": "Products", "mean": "Avg Price", "min": "Min", "max": "Max"})
            .sort_values("Products", ascending=False)
        )
        st.dataframe(
            price_summary,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Avg Price": st.column_config.NumberColumn(format="$%.2f"),
                "Min": st.column_config.NumberColumn(format="$%.2f"),
                "Max": st.column_config.NumberColumn(format="$%.2f"),
            },
        )
