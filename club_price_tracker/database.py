"""SQLite persistence for club price history.

Every run appends its full result set, so the table accumulates history
rather than being overwritten.

SCHEMA is the single source of truth: it generates the CREATE TABLE, the
INSERT, and the row validator, so a column can't be added to one and
forgotten in the others.

Appends are idempotent - a UNIQUE index over
(site, brand, club_type, name, variant, run_timestamp) plus INSERT OR
IGNORE, so no dedup pass is needed on the way in.
"""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "club_prices.db"
TABLE = "club_prices"


class SchemaError(ValueError):
    """A row didn't match SCHEMA. Carries a human-readable reason."""


# --------------------------------------------------------------------------
# Value coercion
#
# Scrapers return real Python types, but values lifted from page markup
# arrive as strings ("False", "24.99"). Each coercer handles both and
# raises ValueError with a readable message when it can't.
# --------------------------------------------------------------------------

# Strings meaning "no value" rather than real content.
_NULLISH = {"", "none", "nan", "null", "na", "n/a"}

_TRUTHY = {"true", "1", "yes", "y", "t"}
_FALSY = {"false", "0", "no", "n", "f"}


def _is_null(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and value != value:  # NaN
        return True
    if isinstance(value, str) and value.strip().lower() in _NULLISH:
        return True
    return False


def _as_text(value: Any) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError("empty string")
    return text


def _as_real(value: Any) -> float:
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"not a finite number: {value!r}")
    return number


def _as_int(value: Any) -> int:
    # float() first so "199.0" and 199.0 both land on 199.
    return int(_as_real(value))


def _as_bool(value: Any) -> int:
    """SQLite has no BOOLEAN type - store 0/1."""
    if isinstance(value, bool):
        return int(value)
    text = str(value).strip().lower()
    if text in _TRUTHY:
        return 1
    if text in _FALSY:
        return 0
    raise ValueError(f"not a boolean: {value!r}")


def _as_iso_timestamp(value: Any) -> str:
    text = _as_text(value)
    datetime.fromisoformat(text)  # raises ValueError if malformed
    return text


def _derive_extracted_date(row: dict) -> str:
    """Calendar date the row was pulled, for grouping history by day.
    Derived, so it can't drift from run_timestamp.
    """
    return datetime.fromisoformat(row["run_timestamp"]).date().isoformat()


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Column:
    name: str
    sql_type: str
    coerce: Callable[[Any], Any]
    nullable: bool = True
    # Inclusive range, enforced in Python (readable error) and as a SQL
    # CHECK (so hand-written INSERTs can't bypass it).
    bounds: tuple[float, float] | None = None
    # Fills the column from the rest of the row instead of from input.
    derive: Callable[[dict], Any] | None = None

    def ddl(self) -> str:
        parts = [f'"{self.name}"', self.sql_type]
        if not self.nullable:
            parts.append("NOT NULL")
        if self.bounds:
            low, high = self.bounds
            parts.append(
                f'CHECK ("{self.name}" IS NULL '
                f'OR "{self.name}" BETWEEN {low} AND {high})'
            )
        return " ".join(parts)


SCHEMA: Sequence[Column] = (
    # Shared by every row in a run, so it doubles as the run identifier.
    Column("run_timestamp", "TEXT", _as_iso_timestamp, nullable=False),
    Column("extracted_date", "TEXT", _as_text, nullable=False, derive=_derive_extracted_date),
    Column("site", "TEXT", _as_text, nullable=False),
    Column("brand", "TEXT", _as_text, nullable=False),
    Column("club_type", "TEXT", _as_text, nullable=False),
    Column("name", "TEXT", _as_text, nullable=False),
    Column("variant", "TEXT", _as_text),
    # carlsgolfland's doubles as the MPN - the best handle for matching
    # the same club across sites.
    Column("sku", "TEXT", _as_text),
    Column("price", "REAL", _as_real, bounds=(0, 100_000)),
    Column("original_price", "REAL", _as_real, bounds=(0, 100_000)),
    Column("discount_pct", "REAL", _as_real, bounds=(0, 100)),
    Column("on_sale", "INTEGER", _as_bool, nullable=False, bounds=(0, 1)),
    Column("stock_status", "TEXT", _as_text),
    Column("rating", "REAL", _as_real, bounds=(0, 5)),
    Column("review_count", "INTEGER", _as_int, bounds=(0, 10_000_000)),
    Column("image_url", "TEXT", _as_text),
    Column("description", "TEXT", _as_text),
    Column("link", "TEXT", _as_text, nullable=False),
)

COLUMNS: tuple[str, ...] = tuple(column.name for column in SCHEMA)

# Identifies one listing across runs. price_alerts uses the same grouping
# to find a listing's previous price.
PRODUCT_COLUMNS = ("site", "brand", "club_type", "name", "variant")

# SQLite treats NULLs as distinct in a UNIQUE index, so nullable variant
# is coalesced - otherwise duplicate variant-less listings would insert.
_DEDUP_EXPR = ", ".join(
    f'COALESCE("{c}", \'\')' if c == "variant" else f'"{c}"'
    for c in (*PRODUCT_COLUMNS, "run_timestamp")
)

_CREATE_TABLE = (
    f'CREATE TABLE IF NOT EXISTS "{TABLE}" (\n'
    "  id INTEGER PRIMARY KEY,\n  "
    + ",\n  ".join(column.ddl() for column in SCHEMA)
    + "\n)"
)

_CREATE_INDEXES = (
    f'CREATE UNIQUE INDEX IF NOT EXISTS ux_{TABLE}_row ON "{TABLE}" ({_DEDUP_EXPR})',
    f'CREATE INDEX IF NOT EXISTS ix_{TABLE}_extracted_date ON "{TABLE}" (extracted_date)',
    f'CREATE INDEX IF NOT EXISTS ix_{TABLE}_sku ON "{TABLE}" (sku) WHERE sku IS NOT NULL',
)

_QUOTED_COLUMNS = ", ".join(f'"{name}"' for name in COLUMNS)
_PLACEHOLDERS = ", ".join("?" * len(COLUMNS))
_INSERT = f'INSERT OR IGNORE INTO "{TABLE}" ({_QUOTED_COLUMNS}) VALUES ({_PLACEHOLDERS})'


# --------------------------------------------------------------------------
# Connection
# --------------------------------------------------------------------------

@contextmanager
def connect(db_path: Path | str = DB_PATH) -> Iterator[sqlite3.Connection]:
    """Opens the DB, creating file and schema if needed. Commits on clean
    exit, rolls back on exception, always closes.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        init_db(conn)
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(conn: sqlite3.Connection) -> None:
    """Idempotent - safe to call on every connect."""
    conn.execute(_CREATE_TABLE)
    for statement in _CREATE_INDEXES:
        conn.execute(statement)


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def validate_row(row: Mapping[str, Any], label: str = "row") -> dict[str, Any]:
    """Coerces one input row into a dict holding exactly COLUMNS.

    Raises SchemaError on an unknown key (catching a scraper renaming a
    field), a missing NOT NULL value, an uncoercible value, or one outside
    its bounds.

    Returns a dict rather than an insert-ready tuple so price_alerts can
    compare against normalized values.
    """
    unknown = set(row) - set(COLUMNS)
    if unknown:
        raise SchemaError(f"{label}: unexpected column(s) {sorted(unknown)}")

    validated: dict[str, Any] = {}
    for column in SCHEMA:
        if column.derive is not None:
            validated[column.name] = column.derive(validated)
            continue

        raw = row.get(column.name)
        if _is_null(raw):
            if not column.nullable:
                raise SchemaError(f"{label}: '{column.name}' is required but missing/empty")
            validated[column.name] = None
            continue

        try:
            value = column.coerce(raw)
        except (TypeError, ValueError) as exc:
            raise SchemaError(f"{label}: '{column.name}'={raw!r} is invalid ({exc})") from exc

        if column.bounds and not (column.bounds[0] <= value <= column.bounds[1]):
            raise SchemaError(
                f"{label}: '{column.name}'={value!r} outside allowed range {column.bounds}"
            )
        validated[column.name] = value

    return validated


def validate_rows(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Collects failures rather than stopping at the first, so one bad
    listing doesn't cost a whole run. Callers decide to raise or skip.
    """
    valid: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, row in enumerate(rows):
        try:
            valid.append(validate_row(row, label=f"row {index}"))
        except SchemaError as exc:
            errors.append(str(exc))
    return valid, errors


# --------------------------------------------------------------------------
# Read / write
# --------------------------------------------------------------------------

def insert_rows(conn: sqlite3.Connection, rows: Sequence[Mapping[str, Any]]) -> int:
    """Appends validated rows, skipping duplicates. Returns the number
    actually inserted.
    """
    if not rows:
        return 0
    before = conn.total_changes
    conn.executemany(_INSERT, [tuple(row[name] for name in COLUMNS) for row in rows])
    return conn.total_changes - before


def latest_prices(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """One row per listing with its most recent price. Done in SQL so it
    stays cheap as history grows.
    """
    cursor = conn.execute(
        f"""
        SELECT {", ".join(PRODUCT_COLUMNS)}, price, run_timestamp
        FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY {", ".join(
                    f'COALESCE("{c}", \'\')' if c == "variant" else f'"{c}"'
                    for c in PRODUCT_COLUMNS
                )}
                ORDER BY run_timestamp DESC, id DESC
            ) AS recency
            FROM "{TABLE}"
            WHERE price IS NOT NULL
        )
        WHERE recency = 1
        """
    )
    return [dict(row) for row in cursor]


def row_count(conn: sqlite3.Connection) -> int:
    return conn.execute(f'SELECT COUNT(*) FROM "{TABLE}"').fetchone()[0]
