"""Price-drop detection against prior history.

Deliberately logger-only for now (no email/Slack) - see TODO.md's
"Price-drop/deal alerting" backlog item, which calls out a logged
summary as the starting point.
"""

import pandas as pd

# A "product" is the same real-world listing across runs. run_timestamp
# is intentionally excluded here (unlike test_scrapers.py's DEDUP_KEY) -
# this key is for matching a listing to its *previous* run, not for
# deduping rows within a single run.
PRODUCT_KEY = ["site", "brand", "club_type", "variant", "name"]


def _product_key(row) -> tuple:
    return tuple(row.get(col) if pd.notna(row.get(col)) else "" for col in PRODUCT_KEY)


def log_price_drops(history_df: pd.DataFrame, new_df: pd.DataFrame, logger) -> None:
    """For every row in new_df, looks up that same product's most recent
    prior price in history_df (by run_timestamp) and logs an alert if the
    new price is lower.
    """
    if history_df.empty:
        return

    latest_price = {}
    for _, row in history_df.sort_values("run_timestamp").iterrows():
        latest_price[_product_key(row)] = row["price"]

    for _, row in new_df.iterrows():
        previous_price = latest_price.get(_product_key(row))
        new_price = row["price"]
        if previous_price is None or pd.isna(previous_price) or pd.isna(new_price):
            continue
        if new_price < previous_price:
            drop_pct = round((previous_price - new_price) / previous_price * 100, 1)
            logger.info(
                "PRICE DROP: %s | %s %s [%s] $%.2f -> $%.2f (-%.1f%%)",
                row["site"], row["brand"], row["name"], row["variant"] or "-",
                previous_price, new_price, drop_pct,
            )
