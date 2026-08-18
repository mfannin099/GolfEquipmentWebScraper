"""Streamlit UI for the golf club price tracker.

Sits directly on top of club_price_tracker: search and compare the latest
tracked prices, and trigger a filtered scrape/save run. No new scraping or
persistence logic lives here - everything goes through run_final_scrape and
database.

Run with:
    uv run streamlit run apps/streamlit_app.py
"""

import pandas as pd
import streamlit as st

from club_price_tracker import config, database, run_final_scrape

st.set_page_config(page_title="Golf Club Price Tracker", layout="wide")


# --------------------------------------------------------------------------
# Data access
# --------------------------------------------------------------------------

@st.cache_data(ttl=60)
def load_latest_prices() -> pd.DataFrame:
    """One row per listing (site, brand, club_type, name, variant) at its
    most recent price, with full column detail. Mirrors the windowing logic
    in database.latest_prices() but selects every column instead of that
    function's narrow projection, since the UI wants description/image/sku
    too.
    """
    with database.connect() as conn:
        cols = ", ".join(f'"{c}"' for c in database.COLUMNS)
        partition = ", ".join(
            f'COALESCE("{c}", \'\')' if c == "variant" else f'"{c}"'
            for c in database.PRODUCT_COLUMNS
        )
        query = f"""
            SELECT {cols} FROM (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY {partition}
                    ORDER BY run_timestamp DESC, id DESC
                ) AS recency
                FROM "{database.TABLE}"
                WHERE price IS NOT NULL
            ) WHERE recency = 1
        """
        return pd.read_sql_query(query, conn)


def row_id(row) -> str:
    return "|".join(str(row[c] or "") for c in database.PRODUCT_COLUMNS)


# --------------------------------------------------------------------------
# Tabs
# --------------------------------------------------------------------------

_DISPLAY_COLUMNS = [
    "site", "brand", "club_type", "name", "variant",
    "price", "original_price", "discount_pct", "on_sale", "stock_status", "link",
]


def render_search_tab() -> None:
    df = load_latest_prices()

    col1, col2, col3 = st.columns([2, 1, 1])
    keyword = col1.text_input("Keyword", placeholder="e.g. Newport, Stealth, adjustable")
    club_type = col2.selectbox("Club type", ["Any"] + list(config.CLUB_TYPES))
    brand_filter = col3.text_input("Brand contains", placeholder="e.g. Titleist")

    filtered = df
    if club_type != "Any":
        filtered = filtered[filtered["club_type"] == club_type]
    if brand_filter:
        filtered = filtered[filtered["brand"].str.contains(brand_filter, case=False, na=False)]
    if keyword:
        search_cols = [c for c in ("name", "brand", "variant", "description") if c in filtered.columns]
        mask = filtered[search_cols].apply(
            lambda col: col.str.contains(keyword, case=False, na=False)
        ).any(axis=1)
        filtered = filtered[mask]

    st.caption(f"{len(filtered)} of {len(df)} listings")
    st.dataframe(
        filtered[_DISPLAY_COLUMNS] if not filtered.empty else filtered.reindex(columns=_DISPLAY_COLUMNS),
        use_container_width=True,
        hide_index=True,
        column_config={
            "price": st.column_config.NumberColumn("Price", format="$%.2f"),
            "original_price": st.column_config.NumberColumn("Original", format="$%.2f"),
            "discount_pct": st.column_config.NumberColumn("Discount", format="%.0f%%"),
            "link": st.column_config.LinkColumn("Link"),
        },
    )


def render_compare_tab() -> None:
    df = load_latest_prices()

    if df.empty:
        st.info("No data yet - run a scrape first.")
        return

    label_map = {
        row_id(row): f"{row['brand']} — {row['name']} ({row['variant'] or row['site']})"
        for _, row in df.iterrows()
    }
    selected_ids = st.multiselect(
        "Clubs to compare",
        options=list(label_map),
        format_func=lambda k: label_map[k],
        max_selections=6,
    )

    if len(selected_ids) < 2:
        st.info("Select at least two clubs to compare.")
        return

    df = df.assign(_row_id=df.apply(row_id, axis=1))
    selected_rows = [df[df["_row_id"] == rid].iloc[0] for rid in selected_ids]

    columns = st.columns(len(selected_rows))
    for column, row in zip(columns, selected_rows):
        with column:
            if pd.notna(row.get("image_url")):
                st.image(row["image_url"], use_container_width=True)
            st.subheader(row["name"])
            st.caption(f"{row['brand']} · {row['club_type']} · {row['site']}")
            if pd.notna(row.get("variant")):
                st.caption(f"Variant: {row['variant']}")
            st.metric(
                "Price",
                f"${row['price']:.2f}" if pd.notna(row["price"]) else "N/A",
                delta=f"-{row['discount_pct']:.0f}%" if row.get("on_sale") and pd.notna(row.get("discount_pct")) else None,
                delta_color="inverse",
            )
            if pd.notna(row.get("stock_status")):
                st.caption(f"Stock: {row['stock_status']}")
            if pd.notna(row.get("link")):
                st.markdown(f"[View listing →]({row['link']})")


def render_scrape_tab() -> None:
    st.subheader("Run a filtered scrape")

    brands = st.multiselect("Brands", options=config.BRANDS, default=config.BRANDS)
    extra_brand = st.text_input("Add a brand not listed above (optional)")
    if extra_brand:
        brands = brands + [extra_brand]

    club_types = st.multiselect(
        "Club types", options=list(config.CLUB_TYPES), default=list(config.CLUB_TYPES)
    )
    sites = st.multiselect(
        "Sites", options=list(run_final_scrape.SCRAPERS), default=list(run_final_scrape.SCRAPERS)
    )
    max_lookups = st.number_input(
        "Max product-page lookups per combination",
        min_value=0, value=config.MAX_VARIANT_LOOKUPS, step=1,
    )

    can_run = bool(brands and club_types and sites)
    if st.button("Preview scrape", disabled=not can_run):
        with st.spinner(
            f"Scraping {len(brands)} brand(s) x {len(club_types)} club type(s) "
            f"x {len(sites)} site(s)..."
        ):
            rows = run_final_scrape.scrape(
                brands, club_types, sites, max_variant_lookups=int(max_lookups),
            )
        st.session_state["preview_rows"] = rows
        st.session_state.pop("save_summary", None)

    preview_rows = st.session_state.get("preview_rows")
    if preview_rows is not None:
        if not preview_rows:
            st.warning("No results scraped - nothing to save.")
        else:
            st.caption(f"{len(preview_rows)} row(s) scraped - not yet saved")
            st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
            if st.button("Save to database"):
                with st.spinner("Saving..."):
                    summary = run_final_scrape.save(preview_rows)
                st.session_state["save_summary"] = summary
                del st.session_state["preview_rows"]
                load_latest_prices.clear()
                st.rerun()

    summary = st.session_state.get("save_summary")
    if summary is not None:
        st.success(
            f"Inserted {summary.inserted} new row(s) ({summary.duplicates} duplicate, "
            f"{summary.drops} price drop(s) flagged). History: {summary.history_rows} rows total."
        )


# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------

def main() -> None:
    st.title("Golf Club Price Tracker")

    search_tab, compare_tab, scrape_tab = st.tabs(["Search", "Compare", "Run Scraper"])
    with search_tab:
        render_search_tab()
    with compare_tab:
        render_compare_tab()
    with scrape_tab:
        render_scrape_tab()


if __name__ == "__main__":
    main()
