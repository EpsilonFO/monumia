"""
Seed the `aides` table in Supabase with all 16 aids.

Run:
    cd backend && python scripts/seed_aides.py

Requires SUPABASE_URL and SUPABASE_SECRET_KEY in .env (or environment).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from supabase import create_client
from aids import AIDES

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SECRET_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------------------------------------------------------------
# All 16 aids — columns are snake_case, criteres JSONB keeps camelCase keys
# ---------------------------------------------------------------------------


def main():
    print(f"Seeding {len(AIDES)} aides into Supabase...")

    for aide in AIDES:
        supabase.table("aides").upsert(aide, on_conflict="id").execute()
        print(f"  ✓ {aide['id']} — {aide['nom_court']}")

    print(f"\nDone! {len(AIDES)} aides upserted.")


if __name__ == "__main__":
    main()
