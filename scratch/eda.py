"""Quick EDA over data/club_prices.db. Run: uv run python scratch/eda.py"""

from pathlib import Path

import duckdb

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "club_prices.db"

con = duckdb.connect()
con.execute("INSTALL sqlite; LOAD sqlite;")
con.execute(f"ATTACH '{DB_PATH}' AS db (TYPE sqlite);")
t = "db.club_prices"


def counts_by(column: str) -> None:
    print(f"\n{column}:")
    for value, n in con.execute(f"SELECT {column}, COUNT(*) FROM {t} GROUP BY 1 ORDER BY 2 DESC").fetchall():
        print(f"  {value}: {n}")


print("record count:", con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
counts_by("extracted_date")
counts_by("site")
counts_by("brand")
counts_by("club_type")
