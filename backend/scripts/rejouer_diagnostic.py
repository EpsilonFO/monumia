"""
Rejoue le diagnostic d'un projet RÉEL à partir de ses lignes en base, exportées
en JSON (Supabase Studio : « Copy row as JSON », ou un `select row_to_json(...)`).

Passe par le même funnel que la route (`deterministic_diagnostic_for` après
`merge_projet_into_monument`), donc mêmes seaux et même QCM que la page projet,
au paywall près (rien n'est caviardé ici). Aucune écriture.

Le client Supabase est celui du `.env.local` (base locale en dev) : il sert à
lire la commune (région, département, population) et la surcouche `/admin`.
`--sans-base` rend le moteur nu sur les YAML ; il faut alors que la ligne
monument porte déjà `region` et `departement_num`, et passer `--population`.

Exemples :
    uv run python scripts/rejouer_diagnostic.py --monument m.json --projet p.json
    # réponses modifiées à la main, sans toucher à l'export du projet :
    uv run python scripts/rejouer_diagnostic.py --monument m.json --answers q.json
    uv run python scripts/rejouer_diagnostic.py --monument m.json --projet p.json --json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from routers.aides import deterministic_diagnostic_for, merge_projet_into_monument
from routers.monuments import enrich_monument_with_population


def _decoder(valeur: object) -> object:
    """Rend sa forme à une colonne exportée en texte.

    Selon l'outil, un `jsonb` sort en chaîne JSON (`"{\\"etat_travaux\\": ...}"`)
    et un `text[]` en littéral Postgres (`"{toiture,facade}"`) : le moteur attend
    un dict et des listes.
    """
    if not isinstance(valeur, str):
        return valeur
    brut = valeur.strip()
    if brut[:1] in "{[":
        try:
            return json.loads(brut)
        except json.JSONDecodeError:
            pass
    if brut.startswith("{") and brut.endswith("}"):
        interieur = brut[1:-1]
        return [v.strip().strip('"') for v in interieur.split(",") if v.strip()]
    return valeur


def _lire(chemin: str | None) -> dict | None:
    if not chemin:
        return None
    data = _decoder(Path(chemin).read_text(encoding="utf-8"))
    # Un export de Studio ou un `json_agg` rend une liste d'une ligne.
    if isinstance(data, list):
        if len(data) != 1:
            sys.exit(f"{chemin} : une seule ligne attendue, {len(data)} trouvées")
        data = data[0]
    if not isinstance(data, dict):
        sys.exit(f"{chemin} : un objet JSON attendu")
    return {cle: _decoder(valeur) for cle, valeur in data.items()}


def _montant(aide: dict) -> str:
    montant = aide.get("montantMax")
    return f"  ({montant:,.0f} €)".replace(",", " ") if montant else ""


def main() -> int:
    p = argparse.ArgumentParser(description="Rejoue le diagnostic d'un projet exporté")
    p.add_argument("--monument", required=True, help="ligne `monuments` en JSON")
    p.add_argument("--projet", help="ligne `projets` en JSON (cadrage + questionnaire)")
    p.add_argument("--answers", help="questionnaire en JSON, prime sur celui du projet")
    p.add_argument("--population", type=int, help="avec --sans-base seulement")
    p.add_argument("--sans-base", action="store_true", help="moteur nu, sans Supabase")
    p.add_argument("--json", action="store_true", help="imprime la réponse brute de la route")
    args = p.parse_args()

    monument = _lire(args.monument) or {}
    projet = _lire(args.projet)
    answers = _lire(args.answers)
    if answers is None:
        answers = (projet or {}).get("questionnaire") or {}

    supabase = None
    population = args.population
    if not args.sans_base:
        from db import get_supabase

        supabase = get_supabase()
        monument, population = enrich_monument_with_population(supabase, monument)

    result = deterministic_diagnostic_for(
        merge_projet_into_monument(monument, projet), population, answers, supabase=supabase
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0

    print(
        f"{monument.get('nom') or '?'} : {monument.get('protection')} / "
        f"{monument.get('proprietaire')} / {monument.get('region')} / {population} hab. / "
        f"travaux={(projet or monument).get('travaux_envisages')}"
    )
    print(f"Réponses : {len(answers)} clé(s)\n")

    seaux = (
        ("ÉLIGIBLES", "aidesEligibles"),
        ("À DÉBLOQUER", "aidesAtteignables"),
        ("POTENTIELLES", "aidesPotentiellementEligibles"),
    )
    for titre, cle in seaux:
        bucket = result.get(cle, [])
        print(f"── {titre} ({len(bucket)}) ──")
        for match in bucket:
            aide = match["aide"]
            # Une aide dont le guichet n'est pas ouvert : « Disponibles bientôt » à l'écran.
            bientot = "  [bientôt]" if match.get("disponibilite") == "bientot" else ""
            print(f"  {aide['id']}  {aide.get('nom', '')}{_montant(aide)}{bientot}")
        print()

    ecartees = [m for m in result.get("aidesNonEligibles", []) if m.get("elimineParReponse")]
    print(f"── ÉCARTÉES PAR UNE RÉPONSE ({len(ecartees)}) ──")
    for match in ecartees:
        print(f"  {match['aide']['id']}  {match['aide'].get('nom', '')}")
    print(f"\nNon éligibles en tout : {len(result.get('aidesNonEligibles', []))}")
    print(f"Questions encore ouvertes : {len(result.get('qcmQuestions', []))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
