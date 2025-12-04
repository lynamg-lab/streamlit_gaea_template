#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Streamlit Dashboard Template — Totals & Stocks (Example)
=======================================================

Purpose
-------
A clean, well-documented template other teams (transport, energy, industry, etc.)
can copy to make dashboards **as long as the prepared dataset uses the same schema**:
columns like Area, Item, Year, Metric, Value, item_kind, and region flags
(`region_europe`, `region_EU`, `region_EUEEAUK`).

Scope (intentionally narrow)
----------------------------
- **Metrics supported**: "Total_CO2e" and "Stocks" only.
- **Tabs**:
  1) Time trends — line charts for countries or regional totals (computed on the fly from boolean flags).
  2) Composition — a pie of aggregate groups for a *single year* (Total_CO2e only).
  3) Map — a choropleth of **Total_CO2e** for Europe-only countries (All group only).

How to adapt for other domains
------------------------------
- Replace the CSV path (DEFAULT_PREPARED) with your sector’s prepared file.
- Ensure your preprocessor produces the same column names and boolean region flags.
- Keep "item_kind" categories: "All" | "aggregated" | "atomic" to re-use the grouping UI.
* "All" refers to a total sum of all item categories (in this example it will be all animals)
** "aggregated" refers to high-level groups (e.g., Cattle, Poultry Birds, etc.)
*** "atomic" refers to the most detailed items (e.g., Dairy Cattle, Beef Cattle, etc.) 

Run (PowerShell)
----------------
py -m streamlit run .\2_Scriptes\streamlit_dashboard_template_totals_stocks_example.py
"""

from __future__ import annotations
import streamlit as st, pandas as pd, altair as alt
from pathlib import Path

# --- Optional dependency for the map tab ---------------------------------------------------------
# We prefer Plotly for the choropleth map. If it's not installed, we set a flag and later provide
# a friendly error message in the Map tab. This lets the rest of the app work without Plotly.
try:
    import plotly.express as px
    HAS_PLOTLY = True
    # Corporate color scale (kept from GAEA theme) used only for the Plotly choropleth
    CORP_SCALE = [
        [0.00, "#ABDDA4"],
        [0.11, "#66C2A5"],
        [0.22, "#3288BD"],
        [0.33, "#5E4FA2"],
        [0.44, "#FEE08B"],
        [0.56, "#FDAE61"],
        [0.67, "#F46D43"],
        [0.78, "#D53E4F"],
        [1.00, "#9E0142"]
    ]
except Exception:
    HAS_PLOTLY = False

# ---------------------------
# 0) Page / theme / palette
# ---------------------------
# Configure Streamlit page and apply a friendly title. Use layout="wide" for dashboard feel.
st.set_page_config(page_title="Emissions Dashboard — Totals & Stocks", layout="wide")
# This specific title is for the example domain (livestock). Change it when cloning the template.
st.title("Emissions Dashboard — Template example of Livestock Emissions & Stocks ")

# Path to the prepared long CSV. For your own thematic app, update this to your prepared file.
# The prepared file must follow the documented schema so all UI logic keeps working.
DEFAULT_PREPARED = r"C:\Users\lynam\Documents\01_steamlit_gaea\1_Donnees\livestock_PREPARED_long.csv"

# Region options exposed to users. Internally, we map each human label to its boolean flag column
# in the dataset. Your preprocessor is responsible for computing these booleans.
REGION_OPTIONS = ["Europe", "EU", "EU/EEA+UK"]
FLAG_MAP = {"Europe":"region_europe","EU":"region_EU","EU/EEA+UK":"region_EUEEAUK"}

# Simple corporate palette used across the app (backgrounds, text, accents). Adjust to your brand.
CORP = {
    "bg":      "#f5f0e6",
    "panel":   "#e7dfcf",
    "text":    "#2e2b26",
    "accent":  "#6b8e23",
    "accent2": "#8f9779",
    "brown":   "#8b6b4a",
}

# A tiny CSS injection to align Streamlit widgets with the house style (background, tabs, buttons).
# Keep this minimal; prefer app-level theming or a design system if you need something complex.
st.markdown(f"""
<style>
.stApp {{ background-color: {CORP["bg"]}; color: {CORP["text"]}; }}
section[data-testid="stSidebar"] > div:first-child {{ background-color: {CORP["panel"]} !important; }}
.stButton button, .stDownloadButton button {{ background-color: {CORP["accent"]} !important; color: white !important; border: 0 !important; border-radius: 10px !important; }}
.stButton button:hover, .stDownloadButton button:hover {{ filter: brightness(0.95); }}
.stTabs [role="tablist"] button[role="tab"] {{ color: {CORP["text"]}; }}
.stTabs [role="tablist"] button[aria-selected="true"] {{ border-bottom: 3px solid {CORP["accent"]}; }}
.block-container {{ background: transparent; }}
label, .stSelectbox label, .stRadio label {{ color: {CORP["text"]} !important; }}
</style>
""", unsafe_allow_html=True)

# Altair theme for consistent charts (line and pie). We register a theme once and enable it.
ALT_CATEGORY = ["#9E0142","#D53E4F","#F46D43","#FDAE61","#FEE08B","#E6F598","#ABDDA4","#66C2A5","#3288BD","#5E4FA2"]*4

def _corp_altair_theme():
    return {
        "config": {
            "range": {"category": ALT_CATEGORY},
            "view": {"stroke": "transparent"},
            "axis": {"labelColor": CORP["text"], "titleColor": CORP["text"]},
            "legend": {"labelColor": CORP["text"], "titleColor": CORP["text"]},
            "title": {"color": CORP["text"]},
            "mark": {"strokeWidth": 2},
        }
    }

alt.themes.register("corp", _corp_altair_theme)
alt.themes.enable("corp")

# Helper to convert metric codes into human-friendly y-axis labels.
# If you add more metrics in the future, extend this mapping.
def metric_unit_label(metric: str) -> str:
    if metric == "Total_CO2e": return "Total (kt CO₂e)"
    if metric == "Stocks":     return "Headcount (head)"
    return metric

# ---------------------------
# 1) Load data
# ---------------------------
# We cache loading so repeated UI interactions are fast. The function also validates the schema
# and restricts the app to the two supported metrics for this template.
@st.cache_data
def load_prepared(path: Path) -> pd.DataFrame:
    """
    Load the prepared long CSV.

    Expected columns
    ----------------
    - Area, Item, Year (int), Metric, Value
    - item_kind (categorical: 'All' | 'aggregated' | 'atomic')
    - region flags: region_europe, region_EU, region_EUEEAUK
    """
    df = pd.read_csv(path)

    # Validate that the minimum required columns are present; stop early with a clear message if not.
    need = {"Area","Item","Year","Metric","Value","item_kind",
            "region_europe","region_EU","region_EUEEAUK"}
    miss = need.difference(df.columns)
    if miss:
        st.error(f"Prepared CSV missing columns: {', '.join(sorted(miss))}"); st.stop()

    # Keep only the two metrics in scope for this template to keep the UI simple and predictable.
    df = df[df["Metric"].isin(["Total_CO2e","Stocks"])].copy()
    # Ensure item_kind is string-typed to avoid issues when normalizing values later.
    df["item_kind"] = df["item_kind"].astype(str)
    return df

# Either read from the default path or let the user upload a CSV interactively.
path = Path(DEFAULT_PREPARED)
if not path.exists():
    # If the default file is missing, guide the user to upload one and stop the script until they do.
    st.warning(f"Prepared CSV not found at:\n{path}\nUpload below or update DEFAULT_PREPARED.")
    uploaded = st.file_uploader("Upload the prepared CSV", type=["csv"])
    if uploaded is None: st.stop()
    df = pd.read_csv(uploaded)
    # If someone uploads a larger dataset with extra metrics, we still enforce the template scope.
    df = df[df["Metric"].isin(["Total_CO2e","Stocks"])].copy()
else:
    df = load_prepared(path)

# Determine the available year range from the data and set sensible defaults for sliders.
year_min, year_max = int(df["Year"].min()), int(df["Year"].max())
DEFAULT_START = max(1990, year_min)   # Avoid very early years by default if present
DEFAULT_END   = min(2022, year_max)   # Cap default at 2022 to reflect typical latest year in examples

# Helper to normalize free-text / variant values of item_kind to the three canonical buckets used by the UI.
# This allows the app to accept small naming inconsistencies from upstream processors.
def normalize_kind_value(v: str) -> str:
    s = str(v).strip().lower()
    if s in {"all","all animals","all_animals"}: return "All"
    if s in {"aggregated","aggregate"}: return "aggregated"
    return "atomic"

# ---------------------------
# 2) Tabs
# ---------------------------
# Three tabs:
#  - Time trends: line chart of a metric over time by country or computed regional total
#  - Composition: pie chart of aggregated groups for one year
#  - Map: choropleth of Total_CO2e for Europe for the All-items group
# Reuse these patterns when cloning for another domain.
tab_ts, tab_pie, tab_map = st.tabs(["Time trends", "Composition", "Map"])

# =========================
# Time Series TAB
# =========================
# What this tab shows
# -------------------
# Interactive line charts of a chosen metric (Total_CO2e or Stocks) over a selected year range.
# You can visualize either:
#   • Regional totals (computed on the fly from country-level rows using boolean region flags), or
#   • Individual countries (either a Top-10 preset for a region, or a custom list you pick).
#
# Key inputs in the sidebar
# -------------------------
#   • Metric: choose the y-axis series (units auto-label via metric_unit_label).
#   • Year range: restricts the time window for the chart and data export.
#   • Item group: choose among "All" (single total), "Aggregated" (high-level groups), or "Atomic" (most detailed items).
#   • View mode: toggle between a computed regional total or multiple countries.
#
# How grouping works
# ------------------
# The dataset carries an "item_kind" column. We normalize free-text values to one of three buckets.
# For kind="All", the app enforces selecting at most one item (the domain-wide total) to avoid double-counting.
# For other kinds, you can compare multiple items simultaneously.
#
# Country selection logic
# -----------------------
# • Preset (Top 10): ranks countries in the chosen region by the latest year in-view and keeps the top 10;
#   optional checkbox adds Switzerland even if it's not in the top 10.
# • Custom: you pick countries manually (max 12 to keep charts readable).
#
# Data aggregation rules
# ----------------------
# • Regional totals: sum country rows flagged True for the selected region (and drop any legacy "(group total)" rows).
# • Countries mode: group by [Area, Year] and sum Value to collapse duplicate rows.
#
# UX and export
# -------------
# • Legend is ordered by the latest-year value so more impactful lines appear first.
# • A Download button exports the exact aggregated time series behind the chart as CSV.
#
# Notes & limits
# --------------
# • This template intentionally limits metrics to Total_CO2e and Stocks to keep the example focused.
# • If filters return no data, the tab shows a friendly message and stops downstream rendering.
with tab_ts:
    # --- Controls in the sidebar: choose metric and time window -----------------
    with st.sidebar:
        st.header("Metric & period")
        metric = st.selectbox("Metric", ["Total_CO2e","Stocks"], index=0)
        year_range = st.slider(
            "Year range",
            min_value=year_min,
            max_value=year_max,
            value=(DEFAULT_START, DEFAULT_END),
            step=1,
        )

    # --- Item grouping control (All / aggregated / atomic) ----------------------
    # We detect which kinds exist in the data, then pick a sensible default order.
    kinds_present = sorted({normalize_kind_value(v) for v in df["item_kind"].unique()})
    kind_label_to_value = {"All": "All", "Aggregated": "aggregated", "Atomic": "atomic"}
    default_kind_label = (
        "All" if "All" in kinds_present else ("Aggregated" if "aggregated" in kinds_present else "Atomic")
    )

    with st.sidebar:
        st.header("Item group")
        kind_label = st.radio(
            "Choose one group",
            ["All","Aggregated","Atomic"],
            index=["All","Aggregated","Atomic"].index(default_kind_label)
        )
    kind_value = kind_label_to_value[kind_label]

    # Build the list of items available for the chosen kind. For kind="All" we restrict selection to one
    # item by design (the global total), so we also constrain the defaults accordingly.
    subset = df[df["item_kind"].apply(lambda x: normalize_kind_value(x) == kind_value)]
    items_all = sorted(subset["Item"].dropna().unique().tolist())

    # We use st.session_state to preserve multiselect choices when users tweak other controls.
    ITEMS_KEY = "items_template_multiselect"
    if ITEMS_KEY not in st.session_state:
        st.session_state[ITEMS_KEY] = (items_all[:1] if kind_value=="All" else items_all)

    # If the kind changes (e.g., Aggregated → Atomic), reset defaults to a sensible value for that kind.
    if st.session_state.get("last_kind_value") != kind_value:
        st.session_state[ITEMS_KEY] = (items_all[:1] if kind_value=="All" else items_all)
    st.session_state["last_kind_value"] = kind_value

    # Guard against stale defaults when the available items list changes due to filters.
    valid_defaults = [d for d in st.session_state[ITEMS_KEY] if d in items_all]
    if not valid_defaults:
        valid_defaults = (items_all[:1] if kind_value=="All" else items_all)
    st.session_state[ITEMS_KEY] = valid_defaults

    st.write(f"**Items — {kind_label}**")
    c1,c2,c3 = st.columns(3)
    with c1:
        if st.button("Select all"):
            st.session_state[ITEMS_KEY] = (items_all[:1] if kind_value=="All" else items_all)
    with c2:
        if st.button("Clear"):
            st.session_state[ITEMS_KEY] = []
    with c3:
        if kind_value=="All":
            st.caption("‘All’ is exclusive by design")

    # The multiselect enforces max_selections=1 for kind="All" to avoid double-counting totals.
    items = st.multiselect(
        "",
        options=items_all,
        default=st.session_state[ITEMS_KEY],
        key=ITEMS_KEY,
        max_selections=(1 if kind_value=="All" else None)
    )
    if not items:
        st.info("Select at least one item."); st.stop()

    # --- View mode: regional total vs countries ---------------------------------
    with st.sidebar:
        st.header("View mode")
        show_region = st.checkbox("Show regional total instead of countries", value=False)
        region_choice = st.selectbox("Region", REGION_OPTIONS, index=0, disabled=not show_region)

    # Prepare the base dataframe for plotting: filter metric, period, item_kind, and chosen items.
    base = df[(df["Metric"]==metric) & (df["Year"]>=year_range[0]) & (df["Year"]<=year_range[1])]
    base = base[base["item_kind"].apply(lambda x: normalize_kind_value(x) == kind_value)]
    base = base[base["Item"].isin(items)]
    if base.empty: st.info("No data for current filters."); st.stop()

    if show_region:
        # Compute regional totals directly from the boolean flags in the data (e.g., region_EU==True).
        # We also drop any legacy "(group total)" rows to avoid double-counting.
        flag_col = FLAG_MAP[region_choice]
        sub = base[base[flag_col] & ~base["Area"].str.contains("(group total)", case=False, na=False)].copy()
        if sub.empty:
            st.info(f"No countries flagged for region: {region_choice}."); st.stop()
        totals = (
            sub.groupby(["Year"], as_index=False)["Value"].sum()
               .assign(Area=region_choice)[["Area","Year","Value"]]
               .rename(columns={"Value":"SeriesValue"})
        )
    else:
        # Country series mode. We offer two ways to pick countries:
        #  - Preset (Top 10) from a region pool (optionally adding Switzerland), ranked by latest-year totals
        #  - Custom: free multiselect up to 12 countries
        with st.sidebar:
            st.header("Countries")
            mode = st.radio("Country selection mode", ["Preset (Top 10)", "Custom (pick countries)"])
            add_ch = False
            preset_choice = None
            available_countries = sorted(
                base[~base["Area"].str.contains("(group total)", case=False, na=False)]["Area"].dropna().unique().tolist()
            )
            if mode == "Preset (Top 10)":
                preset_choice = st.selectbox("Preset group", REGION_OPTIONS, index=0)
                add_ch = st.checkbox("Add Switzerland 🇨🇭", value=False)
            else:
                selected_countries = st.multiselect("Countries (max 12)", options=available_countries, max_selections=12)

        sub = base.copy()
        if mode == "Preset (Top 10)":
            # Build the pool of countries for the chosen region, rank by latest-year value, keep top 10.
            flag_col = FLAG_MAP[preset_choice]
            pool = sorted(sub.loc[sub[flag_col] & ~sub["Area"].str.contains("(group total)", case=False, na=False), "Area"].unique().tolist())
            latest_year = sub["Year"].max()
            latest = sub[(sub["Year"]==latest_year) & (sub["Area"].isin(pool))]
            ranked = (
                latest.groupby("Area", as_index=False)["Value"].sum()
                      .sort_values("Value", ascending=False)["Area"].tolist()
            )
            keep = ranked[:10]
            # A tiny UX flourish: optionally include Switzerland if it's not in the top 10 but in the region.
            if add_ch and "Switzerland" in pool and "Switzerland" not in keep:
                keep.append("Switzerland")
        else:
            keep = selected_countries if 'selected_countries' in locals() and selected_countries else []

        if keep: sub = sub[sub["Area"].isin(keep)]
        if sub.empty: st.info("No data after country selection."); st.stop()
        totals = sub.groupby(["Area","Year"], as_index=False)["Value"].sum().rename(columns={"Value":"SeriesValue"})

    # --- Chart ------------------------------------------------------------------
    y_label = metric_unit_label(metric)
    subtitle = f"{y_label} — {year_range[0]}–{year_range[1]}"
    if show_region: subtitle += f" — {region_choice}"
    st.subheader(subtitle); st.caption(f"Group: {kind_label}")

    # Order legend by the latest-year value so the most important lines appear first.
    order_latest = (
        totals[totals["Year"]==totals["Year"].max()].sort_values("SeriesValue", ascending=False)["Area"].tolist()
    )
    chart = (
        alt.Chart(totals)
           .mark_line(point=True)
           .encode(
               x=alt.X("Year:O", title="Year"),
               y=alt.Y("SeriesValue:Q", title=y_label),
               color=alt.Color("Area:N", sort=order_latest, legend=alt.Legend(title="Region" if show_region else "Country")),
               tooltip=[
                   alt.Tooltip("Area:N", title="Region" if show_region else "Country"),
                   alt.Tooltip("Year:O", title="Year"),
                   alt.Tooltip("SeriesValue:Q", title=y_label, format=",.0f"),
               ],
           )
           .properties(height=520)
    )
    st.altair_chart(chart, use_container_width=True)

    # Let users export the aggregated time series powering the chart.
    csv_bytes = totals.to_csv(index=False).encode("utf-8")
    fname = f"timeseries_{metric}_{kind_value}_{year_range[0]}_{year_range[1]}"
    fname += f"_{region_choice}_REGION.csv" if show_region else ".csv"
    st.download_button("Download series as CSV", data=csv_bytes, file_name=fname, mime="text/csv")

# =========================
# Composition (Pie) TAB
# =========================
# What this tab shows
# -------------------
# A single-year composition (shares) of Total_CO2e by aggregated groups (e.g., Cattle, Poultry, etc.).
# This answers "what contributes how much in the selected area for that year?".
#
# Why only Total_CO2e and aggregated groups?
# -----------------------------------------
# • Shares are most meaningful for a "total" metric.
# • Using item_kind == aggregated keeps the number of slices manageable and interpretable.
#
# Area selection
# --------------
# • You can choose a computed region (Europe/EU/EU-EEA-UK) or a single country.
# • For regions, the app sums member countries flagged True (and excludes any "(group total)" rows).
#
# Data safety checks
# ------------------
# • If the filtered subset is empty or sums to ≤ 0, the app shows an info message and avoids plotting.
# • Shares are computed as Value / total, but we only round for display so exports remain precise.
#
# Outputs & exports
# -----------------
# • An Altair pie chart with tooltips (group, absolute value, share).
# • A table sorted by value with a Download button to export the same data as CSV.
with tab_pie:
    st.subheader("Shares by aggregate group (pie)")
    st.caption("Pick a country or region and a single year. Metric is fixed to Total_CO2e in this template.")

    # The pie is intentionally limited to Total_CO2e because shares are most meaningful for totals.
    metric_pie = "Total_CO2e"
    year_pie = st.slider("Pie year", min_value=year_min, max_value=year_max, value=min(2022, year_max), step=1)

    # Only use the 'aggregated' item_kind (domain-specific groups like Cattle / Poultry / etc.).
    agg = df[(df["item_kind"].apply(lambda x: str(x).strip().lower() in {"aggregated","aggregate"})) &
             (df["Metric"]==metric_pie) & (df["Year"]==year_pie)].copy()
    if agg.empty:
        st.info("No aggregated rows found for that year."); st.stop()

    # Build the selection list: first show computed regions, then countries from the data (exclude any
    # legacy pre-aggregated 'group total' rows to avoid double-counting).
    areas = sorted(agg["Area"].dropna().unique().tolist())
    countries = [a for a in areas if "group total" not in str(a).lower()]
    area_choice = st.selectbox("Choose country or region", REGION_OPTIONS + countries, index=0)

    # Compute the pie slice values either by summing flagged countries for a region or by picking a single country.
    if area_choice in REGION_OPTIONS:
        flag_col = FLAG_MAP[area_choice]
        pie_df = (
            agg[agg[flag_col] & ~agg["Area"].str.contains("(group total)", case=False, na=False)][["Item","Value"]]
               .groupby("Item", as_index=False)["Value"].sum()
        )
        title_area = area_choice
    else:
        pie_df = agg[agg["Area"]==area_choice][["Item","Value"]].groupby("Item", as_index=False)["Value"].sum()
        title_area = area_choice

    # Validate we have something positive to plot; avoid division by zero.
    total_val = float(pie_df["Value"].sum()) if not pie_df.empty else 0.0
    if total_val <= 0 or pie_df.empty:
        st.info("No positive values to plot for this selection."); st.stop()

    # Compute shares for tooltips and the table; round only for display to keep accurate sums internally.
    pie_df["Share"] = pie_df["Value"] / total_val
    pie_df["Share (%)"] = (pie_df["Share"] * 100).round(1)
    pie_df_display = pie_df[["Item","Value","Share (%)"]].sort_values("Value", ascending=False)
    pie_df_display = pie_df_display.rename(columns={"Value": "Value (kt CO₂e)"})
    pie_df_display["Value (kt CO₂e)"] = pie_df_display["Value (kt CO₂e)"].round(0)

    # Altair pie chart. We intentionally set a fixed outerRadius for consistent sizing.
    pie = (
        alt.Chart(pie_df)
           .mark_arc(outerRadius=160)
           .encode(
               theta=alt.Theta(field="Value", type="quantitative", stack=True),
               color=alt.Color(field="Item", type="nominal", scale=alt.Scale(range=ALT_CATEGORY[:12]), legend=alt.Legend(title="Aggregated group")),
               tooltip=[
                   alt.Tooltip("Item:N", title="Group"),
                   alt.Tooltip("Value:Q", title="Value (kt CO₂e)", format=",.0f"),
                   alt.Tooltip("Share:Q", title="Share", format=".1%"),
               ],
           )
           .properties(width=520, height=520, title=f"{metric_unit_label(metric_pie)} — {title_area} — {year_pie}")
    )
    st.altair_chart(pie, use_container_width=False)

    # Show and allow download of the table behind the pie for transparency and reuse.
    st.write("Data behind the pie:")
    st.dataframe(pie_df_display, use_container_width=True)
    st.download_button(
        "Download pie data as CSV",
        data=pie_df_display.to_csv(index=False).encode("utf-8"),
        file_name=f"pie_{metric_pie}_{title_area.replace(' ','_')}_{year_pie}.csv",
        mime="text/csv",
    )

# =========================
# Map TAB (Total_CO2e only)
# =========================
# What this tab shows
# -------------------
# A Europe-only choropleth of Total_CO2e for the "All" item group in a chosen year.
# This is useful for spotting spatial patterns (who emits more/less across Europe).
#
# Tech stack and fallback
# -----------------------
# • Uses Plotly Express for the choropleth (preferred here for interactivity and built-in country mapping).
# • If Plotly isn't available, we display a clear install hint and skip just this tab.
#
# Data preparation rules
# ----------------------
# • Filter to item_kind == "All" to avoid double counting.
# • Exclude any rows whose Area contains "(group total)".
# • Keep only rows with region_europe == True so the map scope matches the dataset flags.
# • Normalize a few country names (e.g., UK → United Kingdom) to match Plotly's expectations.
#
# Styling & UX
# ------------
# • Uses a consistent corporate color scale and background to match the other tabs.
# • Below the map, we show the exact values used and provide a CSV export for transparency and reuse.
with tab_map:
    st.subheader("Map of totals — Europe (All items only)")
    year_map = st.slider("Map year", min_value=year_min, max_value=year_max, value=min(2022, year_max), step=1)
    metric_map = "Total_CO2e"

    # If Plotly isn't installed, we show a clear, actionable message and stop just this tab's logic.
    if not HAS_PLOTLY:
        st.error("Plotly is not installed. In a terminal, run:\n\n  py -m pip install plotly\n\nThen rerun the app.")
        st.stop()

    # The map only uses the 'All' item-kind to avoid double-counting. We also drop any '(group total)'
    # rows and restrict to countries flagged as European based on the region_europe boolean.
    sub_all = df[df["item_kind"].apply(lambda v: str(v).strip().lower() in {"all","all animals","all_animals"})]
    sub = sub_all[(sub_all["Metric"]==metric_map) & (sub_all["Year"]==year_map)].copy()
    sub = sub[~sub["Area"].str.contains("(group total)", case=False, na=False)].copy()

    # Keep only countries flagged as Europe (computed via boolean in the data)
    sub = sub[sub["region_europe"]==True]

    map_df = sub.groupby(["Area"], as_index=False)["Value"].sum()

    # Normalize some country names to match Plotly's expectations (tune for your domain if needed).
    name_fix = {"UK": "United Kingdom", "Russia": "Russian Federation"}
    map_df["Area"] = map_df["Area"].replace(name_fix)

    label = "Total (kt CO₂e)"
    fig = px.choropleth(
        map_df,
        locations="Area",
        locationmode="country names",
        color="Value",
        scope="europe",
        color_continuous_scale=CORP_SCALE,
        labels={"Value": label, "Area": "Country"},
        title=f"{label} — Europe — {year_map}",
    )
    # Set margins and apply the same background/text colors for a cohesive look.
    fig.update_layout(
        margin=dict(l=10,r=10,t=50,b=10),
        paper_bgcolor=CORP["bg"],
        plot_bgcolor=CORP["panel"],
        font_color=CORP["text"],
    )
    st.plotly_chart(fig, use_container_width=True)

    # Expose the mapped values and let users download them.
    st.write("Mapped values:")
    map_df_display = map_df.rename(columns={"Value": "Value (kt CO₂e)"})
    map_df_display["Value (kt CO₂e)"] = map_df_display["Value (kt CO₂e)"].round(0)
    st.dataframe(map_df_display.sort_values("Value (kt CO₂e)", ascending=False), use_container_width=True)
    st.download_button(
        "Download map data as CSV",
        data=map_df_display.to_csv(index=False).encode("utf-8"),
        file_name=f"map_Total_CO2e_{year_map}.csv",
        mime="text/csv",
    )
