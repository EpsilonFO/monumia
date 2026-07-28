"""
Test local du diagnostic déterministe sur un profil de monument, SANS base ni
serveur. Lit les YAML, applique le moteur, imprime le résultat lisible.

Sert à valider la donnée d'aides en itération (ex. après avoir rédigé des aides
IDF). Aucune écriture, aucun appel réseau.

Exemples :
    uv run python scripts/try_diagnostic.py --region ile-de-france
    uv run python scripts/try_diagnostic.py --region ile-de-france \\
        --proprietaire public_commune --protection inscrit \\
        --travaux toiture,facade --population 4000
    # avec des réponses déjà connues (lève des incertitudes) :
    uv run python scripts/try_diagnostic.py --region ile-de-france \\
        --answer travaux_commences=false --answer usage_batiment=activite_culturelle
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aides_schema import load_all_aides, load_facts, load_pending_facts
from eligibility_engine import engine_ready_aides, run_deterministic_diagnostic


def _parse_answer(raw: str):
    """k=v → (k, v) en coerçant true/false/entier.

    Les clés réservées (`_raisons`) attendent une liste : « a,b » → ["a", "b"].
    """
    key, _, val = raw.partition("=")
    key = key.strip()
    if key.startswith("_"):
        return key, [v.strip() for v in val.split(",") if v.strip()]
    low = val.strip().lower()
    if low in ("true", "vrai", "oui"):
        coerced = True
    elif low in ("false", "faux", "non"):
        coerced = False
    else:
        try:
            coerced = int(val)
        except ValueError:
            coerced = val
    return key, coerced


def main() -> int:
    p = argparse.ArgumentParser(description="Diagnostic déterministe local")
    p.add_argument("--region", default="ile-de-france")
    p.add_argument("--departement", default="75", help="code INSEE département")
    p.add_argument("--proprietaire", default="prive_personne_physique")
    p.add_argument("--protection", default="classe")
    p.add_argument("--etat", default="moyen")
    p.add_argument("--travaux", default="toiture,facade", help="codes séparés par des virgules")
    p.add_argument("--population", type=int, default=5000)
    p.add_argument("--siecle", default="XIXe siècle")
    p.add_argument(
        "--answer", action="append", default=[], help="fait=valeur (répétable)", metavar="K=V"
    )
    args = p.parse_args()

    monument = {
        "id": "local-test",
        "nom": "Monument de test",
        "protection": args.protection,
        "proprietaire": args.proprietaire,
        "region": args.region,
        "departement_num": args.departement,
        "etat_conservation": args.etat,
        "travaux_envisages": [t for t in args.travaux.split(",") if t],
        "siecle_construction": args.siecle,
    }
    answers = dict(_parse_answer(a) for a in args.answer)

    aides = load_all_aides()
    facts = {**load_facts(), **load_pending_facts()}
    res = run_deterministic_diagnostic(aides, facts, monument, args.population, answers)

    print(
        f"Profil : {args.protection} / {args.proprietaire} / {args.region} "
        f"/ {args.population} hab. / travaux={monument['travaux_envisages']}"
    )
    if answers:
        print(f"Réponses : {answers}")
    print(f"Aides engine-ready analysées : {len(engine_ready_aides(aides))}\n")

    def show(title, bucket, with_reason=False, with_leviers=False):
        print(f"── {title} ({len(bucket)}) ──")
        for m in bucket:
            montant = m["aide"].get("montant_max")
            line = f"  {m['aide']['id']}"
            if montant:
                line += f"  ({montant:,.0f} €)".replace(",", " ")
            if with_reason and m.get("raisonIneligibilite"):
                line += f"  ✗ {m['raisonIneligibilite']}"
            print(line)
            if with_leviers:
                for levier in m.get("leviers") or []:
                    ecart = f" [{levier['ecart']}]" if levier.get("ecart") else ""
                    print(f"      → {levier['resume']}{ecart}")
                    if levier.get("organisme"):
                        print(f"        {levier['organisme']} · {levier.get('delai') or 'délai ?'}")
        print()

    show("ÉLIGIBLES", res["aidesEligibles"])
    show("À DÉBLOQUER", res["aidesAtteignables"], with_leviers=True)
    show("POTENTIELLES", res["aidesPotentiellementEligibles"])
    show("NON ÉLIGIBLES", res["aidesNonEligibles"], with_reason=True)

    print(f"── QUESTIONS ({len(res['qcmQuestions'])}) ──")
    for q in res["qcmQuestions"]:
        enjeu = f"{q['enjeuMax']:,.0f} €".replace(",", " ") if q["enjeuMax"] else "-"
        dep = q.get("dependsOn")
        suffix = f"  ⤷ si {dep['questionId']} ∈ {dep['showForOptionIds']}" if dep else ""
        print(f"  [{q['categorie']}] {q['question']}")
        print(f"      enjeu {enjeu} · {len(q['aideIds'])} aide(s){suffix}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
