"""
Renseigne communes.epci_siren / epci_nom — le rattachement intercommunal.

Source : l'API Découpage administratif (geo.api.gouv.fr, Etalab), qui expose le
`codeEpci` de chaque commune. Ce code EST le SIREN à 9 chiffres du référentiel
BANATIC, celui que les règlements d'aide citent et que les conditions typées
`field: commune.epci` comparent (ex. CC Moret Seine et Loing = 247700032).

Une seule requête HTTP pour les ~35 000 communes, contre un ZIP à parser côté
BANATIC : c'est aussi pour ça que la source n'est pas l'INSEE ici, dont le COG
(cf. seed_communes.py) ne porte pas l'intercommunalité.

Usage :
    cd backend && uv run python scripts/seeds/seed_communes_epci.py

Requiert un .env dans backend/ (ou les variables d'environnement) :
    SUPABASE_URL=https://xxx.supabase.co
    SUPABASE_SERVICE_KEY=eyJ...   (service_role, pas anon)
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from aides_schema import COMBINATOR_OPS, Predicate, load_all_aides  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

COMMUNES_URL = "https://geo.api.gouv.fr/communes?fields=code,codeEpci&format=json"
EPCIS_URL = "https://geo.api.gouv.fr/epcis?fields=code,nom&format=json"


def fetch_json(url: str):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def load_communes_by_epci() -> tuple[dict[str, list[str]], dict[str, str]]:
    """SIREN de l'EPCI → codes INSEE de ses communes, et SIREN → nom de l'EPCI."""
    epci_names = {e["code"]: e["nom"] for e in fetch_json(EPCIS_URL)}
    communes_by_epci: dict[str, list[str]] = {}
    for commune in fetch_json(COMMUNES_URL):
        siren = commune.get("codeEpci")
        if siren:
            communes_by_epci.setdefault(siren, []).append(commune["code"])
    return communes_by_epci, epci_names


def write_epci(client, siren: str, nom: str | None, codes: list[str]) -> int:
    """UPDATE des communes d'un EPCI. Retourne le nombre de lignes touchées.

    Un UPDATE et non un upsert : Postgres évalue les contraintes NOT NULL à la
    construction du tuple, AVANT de résoudre le ON CONFLICT, donc un upsert ne
    portant que (code_insee, epci_siren, epci_nom) échoue sur nom_commune même
    quand toutes les lignes existent déjà. Grouper par EPCI est gratuit : la
    valeur écrite est constante à l'intérieur d'un groupe.

    Les codes absents de la table (communes créées après le dernier
    seed_communes.py) ne mettent rien à jour — l'écart remonte dans le total.
    """
    updated = (
        client.table("communes")
        .update({"epci_siren": siren, "epci_nom": nom})
        .in_("code_insee", codes)
        .execute()
        .data
    ) or []
    return len(updated)


def referenced_epci_sirens() -> dict[str, list[str]]:
    """SIREN cités par une condition `field: commune.epci` → slugs des aides.

    Sert de contrôle d'intégrité après le seed : un SIREN qui ne rattache
    aucune commune est un SIREN faux (ou un EPCI dissous), et l'aide
    correspondante serait silencieusement inéligible partout.
    """
    refs: dict[str, list[str]] = {}
    for slug, aide in load_all_aides().items():
        for condition in aide.conditions:
            if condition.field != "commune.epci" or condition.predicate is None:
                continue
            for value in _predicate_values(condition.predicate):
                refs.setdefault(value, []).append(slug)
    return refs


def _predicate_values(predicate: Predicate | dict) -> list[str]:
    """Valeurs scalaires citées par un prédicat, combinateurs compris.

    Un `Predicate` est un RootModel {opérateur: valeur} ; les branches d'un
    combinateur sont des dicts nus (cf. Predicate._check).
    """
    root = predicate.root if isinstance(predicate, Predicate) else predicate
    op, value = next(iter(root.items()))
    if op in COMBINATOR_OPS:
        return [v for sub in value for v in _predicate_values(sub)]
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def main() -> int:
    print("Téléchargement du découpage intercommunal (geo.api.gouv.fr)...")
    communes_by_epci, epci_names = load_communes_by_epci()
    attendu = sum(len(codes) for codes in communes_by_epci.values())
    print(f"  {attendu} communes rattachées, {len(communes_by_epci)} EPCI")

    print("Connexion à Supabase...")
    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    print(f"Mise à jour, un EPCI à la fois ({len(communes_by_epci)} requêtes)...")
    updated_by_epci: dict[str, int] = {}
    for done, (siren, codes) in enumerate(sorted(communes_by_epci.items()), start=1):
        updated_by_epci[siren] = write_epci(client, siren, epci_names.get(siren), codes)
        print(f"  {done}/{len(communes_by_epci)} EPCI", end="\r")

    total = sum(updated_by_epci.values())
    print(f"\n{total} communes rattachées.")
    if total < attendu:
        print(
            f"  ⚠️  {attendu - total} communes de l'API absentes de la table "
            "(rejouer seed_communes.py pour rafraîchir le COG)"
        )

    # Contrôle : chaque SIREN cité par une aide doit rattacher des communes.
    print("\nSIREN cités par les aides :")
    orphans = 0
    for siren, slugs in sorted(referenced_epci_sirens().items()):
        count = updated_by_epci.get(siren, 0)
        label = epci_names.get(siren, "EPCI inconnu")
        if not count:
            orphans += 1
        mark = "✓" if count else "✗"
        print(f"  {mark} {siren} — {label} : {count} communes  ({', '.join(sorted(slugs))})")
    if orphans:
        print(f"\n❌ {orphans} SIREN ne rattachent aucune commune — vérifier les YAML.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
