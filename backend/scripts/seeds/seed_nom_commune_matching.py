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
        resp = (
            client.table("communes")
            .select("code_insee, nom_commune")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = resp.data
        if not rows:
            break
        all_communes.extend(rows)
        offset += page_size
    print(f"  {len(all_communes)} communes fetched.")

    # 2. Update each commune
    total = len(all_communes)
    print(f"Updating nom_commune_matching for {total} communes...")
    for i, row in enumerate(all_communes):
        client.table("communes").update(
            {"nom_commune_matching": normalize(row["nom_commune"])}
        ).eq("code_insee", row["code_insee"]).execute()
        if (i + 1) % 500 == 0 or i + 1 == total:
            print(f"  {i + 1}/{total}", end="\r")

    print(f"\nDone. {total} communes updated.")


if __name__ == "__main__":
    main()
