"""
Add a nom_commune_matching column to the communes table,
populated with lowercased + unaccented versions of nom_commune.

Usage:
    python scripts/seeds/seed_nom_commune_matching.py

Requires a .env file in the backend/ directory (or env vars):
    SUPABASE_URL=https://xxx.supabase.co
    SUPABASE_SERVICE_KEY=eyJ...   (service_role key, not anon)
"""

import os
import unicodedata
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path(__file__).parent.parent.parent / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

BATCH_SIZE = 500


def normalize(name: str) -> str:
    """Lowercase and strip accents from a commune name."""
    nfkd = unicodedata.normalize("NFKD", name)
    without_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return without_accents.lower()


def main():
    print("Connecting to Supabase...")
    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 1. Fetch all communes
    print("Fetching communes...")
    all_communes = []
    offset = 0
    page_size = 1000
    while True:
        resp = client.table("communes").select("*").range(offset, offset + page_size - 1).execute()
        rows = resp.data
        if not rows:
            break
        all_communes.extend(rows)
        offset += page_size
    print(f"  {len(all_communes)} communes fetched.")

    # 2. Update in batches via upsert (include all fetched columns to avoid nulling them)
    total = len(all_communes)
    print(f"Updating nom_commune_matching in batches of {BATCH_SIZE}...")
    for i in range(0, total, BATCH_SIZE):
        batch = all_communes[i : i + BATCH_SIZE]
        updates = [{**row, "nom_commune_matching": normalize(row["nom_commune"])} for row in batch]
        client.table("communes").upsert(updates, on_conflict="code_insee").execute()
        done = min(i + BATCH_SIZE, total)
        print(f"  {done}/{total}", end="\r")

    print(f"\nDone. {total} communes updated.")


if __name__ == "__main__":
    main()
