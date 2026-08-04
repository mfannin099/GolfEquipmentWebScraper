"""Price-drop detection against prior history.

Deliberately logger-only for now (no email/Slack) - see TODO.md's
"Price-drop/deal alerting" backlog item, which calls out a logged
summary as the starting point.

Works off database.latest_prices(), which resolves each listing's most
recent price in SQL. That means comparing a run against history costs one
indexed query rather than a scan of every row ever recorded.
"""

from typing import Any, Iterable, Mapping

# A "product" is the same real-world listing across runs. run_timestamp is
# deliberately excluded - this key matches a listing to its *previous* run,
# not to other rows within one run (the DB's unique index handles that).
# Same grouping database.latest_prices() partitions on.
PRODUCT_KEY = ("site", "brand", "club_type", "variant", "name")


def product_key(row: Mapping[str, Any]) -> tuple[str, ...]:
    """variant is nullable, so None has to collapse to the same key as an
    empty string - matching the COALESCE(variant, '') that latest_prices()
    partitions by, so a row read back from SQL keys identically to a
    freshly scraped one.
    """
    return tuple("" if row.get(column) is None else str(row[column]) for column in PRODUCT_KEY)


def log_price_drops(
    previous_rows: Iterable[Mapping[str, Any]],
    new_rows: Iterable[Mapping[str, Any]],
    logger,
) -> int:
    """Logs an alert for every row in new_rows that's cheaper than the last
    price recorded for that same listing. Returns the number of drops found.

    previous_rows is what database.latest_prices() returns; new_rows are
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
