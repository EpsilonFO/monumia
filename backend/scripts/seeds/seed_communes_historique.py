"""
Seed the public.communes_historique table from INSEE's mvtcommune CSV.

Maps old/fused/renamed commune codes (COM_AV) to their current canonical code
(COM_AP), resolving chains transitively (A→B→C becomes A→C) so each ancien_code
points directly to a commune that still exists in public.communes.

Usage:
    pip install supabase python-dotenv
    python scripts/seeds/seed_communes_historique.py

Requires a .env file in the backend/ directory (or env vars):
    SUPABASE_URL=https://xxx.supabase.co
    SUPABASE_SERVICE_KEY=eyJ...   (service_role key, not anon)
"""

import csv
import io
import os
import urllib.request
import zipfile
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path(__file__).parent.parent.parent / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

COG_ZIP_URL = "https://www.insee.fr/fr/statistiques/fichier/8740222/cog_ensemble_2026_csv.zip"
COG_DIR = Path(__file__).parent / "cog_ensemble_2026_csv"
MVT_FILE = COG_DIR / "v_mvt_commune_2026.csv"

BATCH_SIZE = 500

# MOD codes from INSEE that produce a usable old→new code mapping.
# See https://www.insee.fr/fr/information/2028028 for the full list.
RELEVANT_MOD_CODES = {
    "10",  # changement de nom
    "20",  # création
    "21",  # rétablissement
    "30",  # suppression
    "31",  # fusion simple
    "32",  # création de commune nouvelle
    "33",  # fusion-association
    "34",  # transformation de fusion en commune nouvelle
    "35",  # suppression de commune déléguée
    "41",  # changement de code dû à un changement de département
    "50",  # changement de code dû à un transfert de chef-lieu
    "70",  # transformation de commune associée en commune déléguée
}


def download_cog():
    if MVT_FILE.exists():
        print(f"mvtcommune file already present at {MVT_FILE}, skipping download.")
        return
    print("Downloading COG data from INSEE...")
    with urllib.request.urlopen(COG_ZIP_URL) as response:
        data = response.read()
    print(f"  Downloaded {len(data) / 1024 / 1024:.1f} MB, extracting...")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(COG_DIR)
    print(f"  Extracted to {COG_DIR}")


def load_current_codes(client) -> set[str]:
    """Fetch every code_insee currently present in communes."""
    codes: set[str] = set()
    page = 0
    page_size = 1000
    while True:
        result = (
            client.table("communes")
            .select("code_insee")
            .range(page * page_size, (page + 1) * page_size - 1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            break
        codes.update(r["code_insee"] for r in rows)
        if len(rows) < page_size:
            break
        page += 1
    return codes


def load_movements() -> list[dict]:
    """Parse the mvtcommune CSV and keep rows where COM_AV != COM_AP."""
    rows: list[dict] = []
    with open(MVT_FILE, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("MOD") not in RELEVANT_MOD_CODES:
                continue
            if row.get("TYPECOM_AV") != "COM":
                continue
            com_av = (row.get("COM_AV") or "").strip()
            com_ap = (row.get("COM_AP") or "").strip()
            if not com_av or not com_ap or com_av == com_ap:
                continue
            rows.append(
                {
                    "ancien_code_insee": com_av,
                    "direct_nouveau": com_ap,
                    "ancien_nom": (row.get("LIBELLE_AV") or "").strip() or None,
                    "date_mouvement": (row.get("DATE_EFF") or "").strip() or None,
                    "type_mouvement": row.get("MOD"),
                }
            )
    return rows


def resolve_chain(code: str, direct: dict[str, str], current: set[str]) -> str | None:
    """Follow old→new links until we land on a code that still exists."""
    visited: set[str] = set()
    cur = code
    for _ in range(20):  # safety bound — real chains are <5
        if cur in current:
            return cur
        if cur in visited:
            return None
        visited.add(cur)
        nxt = direct.get(cur)
        if not nxt or nxt == cur:
            return None
        cur = nxt
    return None


def build_final_mapping(movements: list[dict], current_codes: set[str]) -> list[dict]:
    """Collapse A→B→C chains to A→C; keep only codes that resolve to a live commune."""
    # Keep the most recent mapping per ancien_code (DATE_EFF string sorts fine: YYYY-MM-DD).
    direct: dict[str, str] = {}
    meta: dict[str, dict] = {}
    for m in sorted(movements, key=lambda r: r["date_mouvement"] or ""):
        direct[m["ancien_code_insee"]] = m["direct_nouveau"]
        meta[m["ancien_code_insee"]] = m

    resolved: list[dict] = []
    unresolved = 0
    for ancien in direct:
        if ancien in current_codes:
            # Still a live commune — no need to map it.
            continue
        final = resolve_chain(ancien, direct, current_codes)
        if final is None:
            unresolved += 1
            continue
        m = meta[ancien]
        resolved.append(
            {
                "ancien_code_insee": ancien,
                "nouveau_code_insee": final,
                "ancien_nom": m["ancien_nom"],
                "date_mouvement": m["date_mouvement"],
                "type_mouvement": m["type_mouvement"],
            }
        )
    if unresolved:
        print(f"  {unresolved} ancien codes could not be resolved to a current commune (skipped)")
    return resolved


def upsert_batch(client, rows: list[dict]) -> None:
    client.table("communes_historique").upsert(rows).execute()


def main():
    download_cog()

    print("Connecting to Supabase...")
    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("Loading current communes...")
    current_codes = load_current_codes(client)
    print(f"  {len(current_codes)} communes actives")

    print("Parsing mvtcommune...")
    movements = load_movements()
    print(f"  {len(movements)} mouvements pertinents")

    print("Resolving chains...")
    mapping = build_final_mapping(movements, current_codes)
    print(f"  {len(mapping)} anciens codes mappés vers un code actuel")

    print(f"Inserting in batches of {BATCH_SIZE}...")
    for i in range(0, len(mapping), BATCH_SIZE):
        batch = mapping[i : i + BATCH_SIZE]
        upsert_batch(client, batch)
        print(f"  {min(i + BATCH_SIZE, len(mapping))}/{len(mapping)}", end="\r")

    print(f"\nDone. {len(mapping)} mappings inserted.")


if __name__ == "__main__":
    main()
