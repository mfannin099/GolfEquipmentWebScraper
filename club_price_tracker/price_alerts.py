"""Price-drop detection against prior history. Logger-only for now.

Works off database.latest_prices(), so comparing a run against history
costs one indexed query rather than scanning every row recorded.
"""

from typing import Any, Iterable, Mapping

# The same listing across runs. run_timestamp is excluded: this matches a
# listing to its *previous* run, not to rows within one run. Same grouping
# database.latest_prices() partitions on.
PRODUCT_KEY = ("site", "brand", "club_type", "variant", "name")


def product_key(row: Mapping[str, Any]) -> tuple[str, ...]:
    """None collapses to "" to match the COALESCE(variant, '') that
    latest_prices() partitions by, so a row read back from SQL keys
    identically to a freshly scraped one.
    """
    return tuple("" if row.get(column) is None else str(row[column]) for column in PRODUCT_KEY)


def log_price_drops(
    previous_rows: Iterable[Mapping[str, Any]],
    new_rows: Iterable[Mapping[str, Any]],
    logger,
) -> int:
    """Logs an alert for every row cheaper than that listing's last
    recorded price. Returns the number of drops found.

    previous_rows is database.latest_prices() output; new_rows are
    validated rows from the current run.
    """
    last_price = {product_key(row): row["price"] for row in previous_rows}
    if not last_price:
        return 0

    drops = 0
    for row in new_rows:
        previous = last_price.get(product_key(row))
        current = row["price"]
        if previous is None or current is None or current >= previous:
            continue

        drops += 1
        logger.info(
            "PRICE DROP: %s | %s %s [%s] $%.2f -> $%.2f (-%.1f%%)",
            row["site"], row["brand"], row["name"], row["variant"] or "-",
            previous, current, (previous - current) / previous * 100,
        )

    return drops
