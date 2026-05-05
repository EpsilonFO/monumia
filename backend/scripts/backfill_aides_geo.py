"""
Backfill `aides_departements` and `aides_regions` for aides ingested from
aides-territoires.beta.gouv.fr that are missing their geo constraints.

This is a one-shot data fix complementing the change in sync_aides_territoires.py:
historical aids inserted before the sync script handled perimeters end up as
"national" aids (no row in either join table) and surface for every monument.

Strategy per aide:
  1. Re-fetch the API payload by `source_at_slug` → use `perimeter_scale` /
     `perimeter_code` / `perimeter` / `region` (authoritative).
  2. If that yields nothing, parse the `organisme` string.
  3. Skip aids that already have rows (don't overwrite curated seeds).

Usage:
    cd backend && uv run python3 scripts/backfill_aides_geo.py [--dry-run] [--all]

  --dry-run : print actions without writing
  --all     : re-process every aid_v2 with a source_at_slug (re-syncs even if
              join rows already exist). Default: only process orphan aids.
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env.local", override=True)

import httpx
from _geo_perimeter import derive_geo_constraints, parse_perimeter_from_organisme
from supabase import create_client

AT_BASE_URL = "https://aides-territoires.beta.gouv.fr"
AT_API_TOKEN = os.environ.get("AIDES_TERRITOIRES_API_TOKEN")
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SECRET_KEY"]

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("backfill_geo")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_jwt() -> str | None:
    """Exchange the X-AUTH-TOKEN for a short-lived JWT. Returns None when no token."""
    if not AT_API_TOKEN:
        log.warning("AIDES_TERRITOIRES_API_TOKEN absent — only the organisme fallback will be used")
        return None
    resp = httpx.get(
        f"{AT_BASE_URL}/api/aids/",
        headers={"X-AUTH-TOKEN": AT_API_TOKEN, "Accept": "application/json"},
        params={"itemsPerPage": 1, "page": 1},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("token")


def fetch_at_aid(client: httpx.Client, jwt: str, slug: str) -> dict | None:
    """Fetch one aid's details by slug. Returns None on 404."""
    resp = client.get(
        f"{AT_BASE_URL}/api/aids/{slug}/",
        headers={"Authorization": f"Bearer {jwt}", "Accept": "application/json"},
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def list_target_aides(process_all: bool) -> list[dict]:
    """Return aides_v2 rows to process (orphans by default, or everything with --all)."""
    rows = (
        supabase.table("aides_v2")
        .select("id, nom_court, organisme, source_at_slug")
        .not_.is_("source_at_slug", "null")
        .execute()
        .data
        or []
    )
    if process_all:
        return rows

    # Filter: keep only aides that have neither a department nor a region row
    # We do two batched lookups to avoid N+1 queries.
    ids = [r["id"] for r in rows]
    if not ids:
        return []
    deps_rows = (
        supabase.table("aides_departements").select("aide_id").in_("aide_id", ids).execute().data
        or []
    )
    regs_rows = (
        supabase.table("aides_regions").select("aide_id").in_("aide_id", ids).execute().data or []
    )
    has_geo = {r["aide_id"] for r in deps_rows} | {r["aide_id"] for r in regs_rows}
    return [r for r in rows if r["id"] not in has_geo]


def replace_geo(aide_id: str, depts: list[str], regions: list[str], dry_run: bool) -> None:
    if dry_run:
        return
    supabase.table("aides_departements").delete().eq("aide_id", aide_id).execute()
    supabase.table("aides_regions").delete().eq("aide_id", aide_id).execute()
    if depts:
        supabase.table("aides_departements").insert(
            [{"aide_id": aide_id, "departement_code": c} for c in depts]
        ).execute()
    if regions:
        supabase.table("aides_regions").insert(
            [{"aide_id": aide_id, "region_code": c} for c in regions]
        ).execute()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    parser.add_argument(
        "--all", action="store_true", help="Re-process every aide with a source_at_slug"
    )
    args = parser.parse_args()

    targets = list_target_aides(args.all)
    log.info("=== Backfill geo for %d aide(s) ===", len(targets))
    if not targets:
        log.info("Nothing to do.")
        return

    jwt = get_jwt()
    stats = {"matched_api": 0, "matched_fallback": 0, "no_match": 0, "api_404": 0}

    with httpx.Client(timeout=20) as client:
        for i, row in enumerate(targets, start=1):
            slug = row["source_at_slug"]
            organisme = row["organisme"]
            api_aid = None
            if jwt:
                try:
                    api_aid = fetch_at_aid(client, jwt, slug)
                except httpx.HTTPError as exc:
                    log.warning("  ⚠ API error for %s: %s", slug, exc)
                if api_aid is None:
                    stats["api_404"] += 1

            if api_aid:
                depts, regions = derive_geo_constraints(api_aid, organisme=organisme)
                source = "api"
            else:
                depts, regions = parse_perimeter_from_organisme(organisme)
                source = "fallback"

            if depts or regions:
                stats["matched_api" if source == "api" else "matched_fallback"] += 1
                log.info(
                    "  [%d/%d] %s [%s] depts=%s regions=%s — %s",
                    i,
                    len(targets),
                    "DRY" if args.dry_run else "OK",
                    source,
                    depts,
                    regions,
                    row["nom_court"][:60],
                )
                replace_geo(row["id"], depts, regions, args.dry_run)
            else:
                stats["no_match"] += 1
                log.info(
                    "  [%d/%d] no geo derivable — %s (organisme: %s)",
                    i,
                    len(targets),
                    row["nom_court"][:60],
                    organisme[:60],
                )

            # Gentle rate-limit when hitting the API
            if jwt:
                time.sleep(0.2)

    log.info("=== Stats: %s ===", stats)


if __name__ == "__main__":
    main()
