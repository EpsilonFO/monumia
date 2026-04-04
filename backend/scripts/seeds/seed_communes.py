"""
Seed the public.communes table in Supabase from the COG CSV files.

Usage:
    pip install supabase python-dotenv
    python scripts/seed_communes.py

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

load_dotenv(Path(__file__).parent.parent / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

COG_ZIP_URL = "https://www.insee.fr/fr/statistiques/fichier/8740222/cog_ensemble_2026_csv.zip"
COG_DIR = Path(__file__).parent / "cog_ensemble_2026_csv"
POPULATION_ZIP_URL = "https://www.insee.fr/fr/statistiques/fichier/7739582/ensemble.zip"
POPULATION_FILE = Path(__file__).parent / "ensemble" / "donnees_communes.csv"

BATCH_SIZE = 500


def download_cog():
    if COG_DIR.exists() and any(COG_DIR.iterdir()):
        print(f"COG data already present at {COG_DIR}, skipping download.")
        return
    print("Downloading COG data from INSEE...")
    with urllib.request.urlopen(COG_ZIP_URL) as response:
        data = response.read()
    print(f"  Downloaded {len(data) / 1024 / 1024:.1f} MB, extracting...")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(COG_DIR)
    print(f"  Extracted to {COG_DIR}")


def download_population():
    if POPULATION_FILE.exists():
        print(f"Population data already present at {POPULATION_FILE}, skipping download.")
        return
    print("Downloading population data from INSEE...")
    with urllib.request.urlopen(POPULATION_ZIP_URL) as response:
        data = response.read()
    print(f"  Downloaded {len(data) / 1024 / 1024:.1f} MB, extracting...")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(POPULATION_FILE.parent)
    print(f"  Extracted to {POPULATION_FILE.parent}")


def load_regions() -> dict[str, str]:
    regions = {}
    with open(COG_DIR / "v_region_2026.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            regions[row["REG"]] = row["LIBELLE"]
    return regions


def load_departements(regions: dict[str, str]) -> dict[str, dict]:
    deps = {}
    with open(COG_DIR / "v_departement_2026.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            deps[row["DEP"]] = {
                "nom": row["LIBELLE"],
                "region": regions.get(row["REG"], ""),
            }
    return deps


def load_population() -> dict[str, int]:
    """Returns code_insee -> population municipale (PMUN).

    Special case: Paris arrondissements (75101–75120) are summed
    and assigned to the commune code 75056.
    """
    pop: dict[str, int] = {}
    paris_total = 0
    lyon_total = 0
    marseille_total = 0
    with open(POPULATION_FILE, encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter=";"):
            code = row["COM"].strip()
            try:
                pmun = int(row["PMUN"])
            except (ValueError, KeyError):
                continue
            if code.startswith("751") and len(code) == 5:
                paris_total += pmun
            elif code.startswith("693") and len(code) == 5:
                lyon_total += pmun
            elif code.startswith("132") and len(code) == 5:
                marseille_total += pmun
            else:
                pop[code] = pmun
    if paris_total:
        pop["75056"] = paris_total
    if lyon_total:
        pop["69123"] = lyon_total
    if marseille_total:
        pop["13055"] = marseille_total
    return pop


def load_communes(deps: dict[str, dict], population: dict[str, int]) -> list[dict]:
    communes = []
    with open(COG_DIR / "v_commune_2026.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["TYPECOM"] != "COM":
                continue
            dep_code = row["DEP"]
            dep_info = deps.get(dep_code, {})
            code_insee = row["COM"]
            communes.append(
                {
                    "code_insee": code_insee,
                    "nom_commune": row["LIBELLE"],
                    "departement": dep_info.get("nom", ""),
                    "departement_num": dep_code,
                    "region": dep_info.get("region", ""),
                    "population": population.get(code_insee),
                }
            )
    return communes


def upsert_batch(client, rows: list[dict]) -> None:
    client.table("communes").upsert(rows).execute()


def main():
    download_cog()
    download_population()

    print("Connecting to Supabase...")
    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("Loading COG data...")
    regions = load_regions()
    print(f"  {len(regions)} regions")
    deps = load_departements(regions)
    print(f"  {len(deps)} departements")
    population = load_population()
    print(f"  {len(population)} communes avec données de population")
    communes = load_communes(deps, population)
    print(f"  {len(communes)} communes")

    print(f"Inserting in batches of {BATCH_SIZE}...")
    for i in range(0, len(communes), BATCH_SIZE):
        batch = communes[i : i + BATCH_SIZE]
        upsert_batch(client, batch)
        print(f"  {min(i + BATCH_SIZE, len(communes))}/{len(communes)}", end="\r")

    print(f"\nDone. {len(communes)} communes inserted.")


if __name__ == "__main__":
    main()
