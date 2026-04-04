"""
Seed the public.merimee_buildings table in Supabase from the Merimee CSV file.

Usage:
    pip install supabase python-dotenv
    python scripts/seed_merimee.py

Requires a .env file in the backend/ directory (or env vars):
    SUPABASE_URL=https://xxx.supabase.co
    SUPABASE_SERVICE_KEY=eyJ...   (service_role key, not anon)

First run: the script prints the DDL to create the table — paste it in the
Supabase SQL editor, then re-run to insert the data.
"""

import csv
import os
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path(__file__).parent.parent / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

BATCH_SIZE = 500

MERIMEE_CSV_URL = "https://www.data.gouv.fr/api/1/datasets/r/3a52af4a-f9da-4dcc-8110-b07774dfb3bc"
MERIMEE_DIR = Path(__file__).parent / "merimee_csv"


def download_merimee():
    if MERIMEE_DIR.exists() and any(MERIMEE_DIR.iterdir()):
        print(f"Merimee data already present at {MERIMEE_DIR}, skipping download.")
        return
    print("Downloading Merimee data from data.gouv.fr...")
    with urllib.request.urlopen(MERIMEE_CSV_URL) as response:
        data = response.read()
    print(f"  Downloaded {len(data) / 1024 / 1024:.1f} MB")
    MERIMEE_DIR.mkdir(exist_ok=True)
    csv_path = MERIMEE_DIR / "merimee.csv"
    with open(csv_path, "wb") as f:
        f.write(data)
    print(f"  Saved to {csv_path}")


def print_ddl(headers: list[str]) -> None:
    """Print the SQL DDL to recreate the table with all CSV columns."""
    lines = [
        "DROP TABLE IF EXISTS merimee_buildings;",
        "CREATE TABLE merimee_buildings (",
    ]
    col_defs = []
    for h in headers:
        col = h.lower()
        if col == "reference":
            col_defs.append(f'  "{col}" TEXT PRIMARY KEY')
        else:
            col_defs.append(f'  "{col}" TEXT')
    lines.append(",\n".join(col_defs))
    lines.append(");")
    print("\n".join(lines))


def parse_row(raw: dict, db_cols: list[str]) -> dict:
    """Map lowercased CSV headers to row dict; drop None keys and empty strings."""
    row = {}
    for col in db_cols:
        # DictReader keys are original-case; we stored them as lowercase, so find them
        value = raw.get(col, "")
        row[col] = value if value != "" else None
    return row


def upsert_batch(client, rows: list[dict]) -> None:
    client.table("merimee_buildings").upsert(rows, on_conflict="reference").execute()


def main():
    download_merimee()

    csv_path = MERIMEE_DIR / "merimee.csv"

    # Read headers first
    with open(csv_path, encoding="utf-8") as f:
        raw_headers = f.readline().strip().split("|")

    # Supabase column names = lowercased CSV headers
    db_cols = [h.lower() for h in raw_headers]

    print("\n=== DDL (run once in Supabase SQL editor if table needs to be recreated) ===")
    print_ddl(raw_headers)
    print("=== end DDL ===\n")

    print("Connecting to Supabase...")
    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("Loading Merimee data...")
    with open(csv_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile, delimiter="|")
        # DictReader uses original-case headers; lowercase them for our mapping
        raw_rows = list(reader)
    print(f"  {len(raw_rows)} buildings in CSV")

    # Build rows with lowercased keys, dropping None overflow keys
    rows = []
    for raw in raw_rows:
        row = {}
        for orig_h, db_col in zip(raw_headers, db_cols):
            value = raw.get(orig_h, "")
            row[db_col] = value if value != "" else None
        if row.get("reference"):
            rows.append(row)

    print(f"  {len(rows)} valid rows")

    print(f"Upserting in batches of {BATCH_SIZE}...")
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        upsert_batch(client, batch)
        print(f"  Upserted {i + len(batch)} / {len(rows)}")
    print(f"\nDone. {len(rows)} buildings upserted.")


if __name__ == "__main__":
    main()
