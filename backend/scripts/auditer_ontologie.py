"""Audite l'ontologie et écrit une fiche. Hors de tout run d'ingestion.

    uv run python scripts/auditer_ontologie.py --sans-modele
    uv run python scripts/auditer_ontologie.py
    uv run python scripts/auditer_ontologie.py --table data/fusions/2026-09-21-fusions.yaml

`ingerer.py` lance déjà cet audit en fin de run, et son rendu défile avec le
journal. Ce qu'il dit — 90 quasi-doublons, 37 orphelins, 8 polarités inversées —
est pourtant un travail de plusieurs heures qui commence le lendemain : il lui
faut un fichier, et il faut pouvoir le relancer sans repayer une ingestion.

`--sans-modele` est l'usage courant : le pré-filtre déterministe seul, aucun
appel, aucun coût. Il rend les orphelins et les polarités — qui sont exacts par
construction — et LISTE les paires proches sans les juger. Un appel de modèle
(sans l'option) tranche ces paires-là, et c'est la seule chose qu'il apporte.

Le rapport ne modifie RIEN. Une fusion se fait à la main, dans
`facts_pending.yaml` ET dans les aides qui citent le fait retiré :
`fusionner_faits.py` prend une table, `retyper_faits.py` retype les conditions
d'un fait qu'on retire. `--table` produit la première au format de la seconde.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ingestion import ontologie
from ingestion.atelier import atelier_standard
from pipeline.llm import Compteur, charger_env, client_pour

from aides_schema import AIDES_DIR, DATA_DIR, load_facts, load_pending_facts

REVIEWS_DIR = DATA_DIR / "reviews"


def auditer(
    *,
    sans_modele: bool = False,
    modele: str | None = None,
    aides_dir: Path = AIDES_DIR,
    compteur: Compteur | None = None,
) -> ontologie.RapportOntologie:
    """L'audit, avec ou sans modèle. Ne lève jamais — comme celui de fin de run."""
    load_facts.cache_clear()
    load_pending_facts.cache_clear()
    facts = load_facts()
    pending = load_pending_facts()
    # L'atelier ne sert qu'à porter les dossiers de catalogue que l'audit
    # balaye pour compter les orphelins : le slug est décoratif.
    atelier = atelier_standard("audit-ontologie")
    if aides_dir != AIDES_DIR:
        import dataclasses

        atelier = dataclasses.replace(atelier, aides_dir=aides_dir)
    client = None if sans_modele else client_pour("audit", modele)
    return ontologie.auditer(atelier, facts, pending, client, compteur=compteur)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="auditer_ontologie.py",
        description="Audite facts_pending.yaml et écrit une fiche de review.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "--sans-modele",
        action="store_true",
        help="pré-filtre déterministe seul : orphelins, polarités, paires non jugées",
    )
    ap.add_argument("--model", help="modèle d'audit (défaut : LLM_MODEL_AUDIT)")
    ap.add_argument("--sortie", type=Path, help="chemin de la fiche produite")
    ap.add_argument(
        "--table",
        type=Path,
        help="écrire aussi la table de fusion, au format de fusionner_faits.py",
    )
    args = ap.parse_args(argv)
    charger_env()

    compteur = Compteur()
    rapport = auditer(sans_modele=args.sans_modele, modele=args.model, compteur=compteur)
    print(ontologie.rendre(rapport))

    jour = date.today()
    cible = args.sortie or (REVIEWS_DIR / f"{jour.isoformat()}-audit-ontologie.md")
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text(ontologie.rendre_markdown(rapport, jour=jour), encoding="utf-8")
    print(f"\nFiche écrite : {cible}")

    if args.table:
        args.table.parent.mkdir(parents=True, exist_ok=True)
        args.table.write_text(ontologie.table_de_fusion(rapport), encoding="utf-8")
        print(f"Table de fusion : {args.table}")
        print(f"  uv run python scripts/fusionner_faits.py {args.table} --dry-run")
    if not args.sans_modele:
        print(f"Coût : {compteur.resume()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
