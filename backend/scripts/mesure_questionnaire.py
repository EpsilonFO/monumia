"""Banc de mesure du questionnaire et audit du fail-open.

Sert à chiffrer l'effet d'un lot de retypage sur ce que voit un propriétaire
ordinaire, et à repérer les aides qui ne conservent plus aucune condition
vérifiable (fail-open : elles s'afficheraient « éligible » sans qu'aucun
critère n'ait été contrôlé).

    uv run python scripts/mesure_questionnaire.py
    uv run python scripts/mesure_questionnaire.py --retypages avant.json

`--retypages` attend un JSON {"<slug>/<condition-id>": {"kind": ..., "effect": ...}}
décrivant un état ANTÉRIEUR du typage : le banc rejoue alors les deux états et
affiche le delta. Le format est celui produit par un simple parcours du
catalogue, cf. la fiche de review du lot 2.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aides_schema import AIDES_DIR, load_aide, load_facts, load_pending_facts  # noqa: E402
from eligibility_engine import run_deterministic_diagnostic  # noqa: E402

# Faits de périmètre d'aide : le banc les répond « non » pour simuler un
# propriétaire dont le projet est une pure restauration de monument.
PERIMETRES = (
    "projet_hebergement_touristique",
    "projet_developpement_touristique",
    "projet_equipement_culturel",
    "projet_lieu_diffusion_culturelle",
    "porteur_compagnie_artistique",
    "porteur_ecole_art",
    "projet_valorisation_historique",
)

PROFILS: dict[str, dict] = {
    "privé, inscrit, Pays de la Loire": dict(
        protection="inscrit",
        proprietaire="prive_personne_physique",
        region="pays-de-la-loire",
        departement_num="44",
        etat_conservation="mauvais",
        travaux_envisages=["toiture", "facade"],
    ),
    "commune, non protégé, Nouvelle-Aquitaine": dict(
        protection="non_protege",
        proprietaire="public_commune",
        region="nouvelle-aquitaine",
        departement_num="33",
        etat_conservation="moyen",
        travaux_envisages=["toiture"],
    ),
    "association, inscrit, Centre-Val de Loire": dict(
        protection="inscrit",
        proprietaire="association",
        region="centre-val-de-loire",
        departement_num="37",
        etat_conservation="moyen",
        travaux_envisages=["maconnerie"],
    ),
}
POPULATION = 3000


def charge_aides() -> dict:
    return {p.stem: load_aide(p) for p in sorted(AIDES_DIR.glob("*.yaml"))}


def rejoue_typage(aides: dict, retypages: dict) -> dict:
    """Reconstruit un état antérieur du typage à partir d'un snapshot."""
    out = {}
    for slug, aide in aides.items():
        conds = []
        change = False
        for c in aide.conditions:
            ancien = retypages.get(f"{slug}/{c.id}")
            if ancien and ancien["kind"] in ("info", "discretionary"):
                # Le schéma coerce l'effect par défaut de ces deux kinds en `info`
                # ([aides_schema.py:_coherence]) : un snapshot lu sur le YAML brut
                # les voit « gate » faute de clé explicite. Sans cette
                # normalisation, l'état AVANT rejoué transforme 874 conditions
                # info en gates et fausse toute la mesure.
                ancien = {**ancien, "effect": "info"}
            if ancien and (ancien["kind"], ancien["effect"]) != (c.kind, c.effect):
                maj = {"kind": ancien["kind"], "effect": ancien["effect"]}
                if ancien["kind"] not in ("auto", "user_fact"):
                    maj |= {
                        "fact": None,
                        "field": None,
                        "predicate": None,
                        "derogation_possible": False,
                    }
                conds.append(c.model_copy(update=maj))
                change = True
            else:
                conds.append(c)
        out[slug] = aide.model_copy(update={"conditions": conds}) if change else aide
    return out


def mesure(aides: dict, facts: dict, monument: dict, answers: dict) -> dict:
    res = run_deterministic_diagnostic(aides, facts, monument, POPULATION, answers)
    lignes = [
        *res["aidesEligibles"],
        *res["aidesPotentiellementEligibles"],
        *res["aidesAtteignables"],
        *res["aidesNonEligibles"],
    ]
    retenues = [r for r in lignes if r["statut"] != "non_eligible"]
    mc = sum(
        1
        for r in retenues
        for e in r["llmEvaluation"]["evaluations"]
        if e.get("nature") == "manual_check" and e.get("verdict") == "incertitude"
    )
    return {
        "retenues": len(retenues),
        "eligibles": sum(1 for r in retenues if r["statut"] == "eligible"),
        "mc": mc,
        "questions": len(res["qcmQuestions"]),
        "slugs_eligibles": {r["aide"]["id"] for r in retenues if r["statut"] == "eligible"},
    }


def audit_fail_open(aides: dict) -> list[tuple[str, int]]:
    """Aides sans aucune condition vérifiable : ni gate auto/user_fact, ni manual_check.

    Renvoie (slug, nombre de hard_filters renseignés) : sans condition ET sans
    hard_filter, l'aide s'affiche « éligible » à tout le monde, partout.
    """
    lignes = []
    for slug, aide in sorted(aides.items()):
        verifiables = sum(
            1
            for c in aide.conditions
            if c.kind in ("auto", "user_fact", "manual_check") and c.effect == "gate"
        )
        if verifiables:
            continue
        hf = aide.hard_filters
        n_hf = sum(
            1
            for champ in ("protections", "proprietaires", "travaux", "regions", "departements")
            if getattr(hf, champ, None)
        ) + (1 if hf.commune_max_population else 0)
        lignes.append((slug, n_hf))
    return lignes


def snapshot(aides: dict, cible: Path) -> None:
    """Enregistre le typage courant, à passer plus tard en `--retypages`."""
    etat = {
        f"{slug}/{c.id}": {"kind": c.kind, "effect": c.effect}
        for slug, aide in aides.items()
        for c in aide.conditions
    }
    cible.write_text(json.dumps(etat, ensure_ascii=False, indent=1))
    print(f"{len(etat)} conditions enregistrées dans {cible}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--retypages", type=Path, help="snapshot JSON d'un typage antérieur")
    ap.add_argument("--snapshot", type=Path, help="enregistre le typage courant et sort")
    args = ap.parse_args()

    facts = {**load_facts(), **load_pending_facts()}
    apres = charge_aides()
    if args.snapshot:
        snapshot(apres, args.snapshot)
        return
    avant = rejoue_typage(apres, json.loads(args.retypages.read_text())) if args.retypages else None
    non = dict.fromkeys(PERIMETRES, False)

    print("Banc de mesure — colonnes : aides non écartées par un hard_filter, dont")
    print("éligibles, conditions manual_check en incertitude, questions posées.")
    print("Les faits de périmètre sont répondus « non » (restauration pure).\n")
    for nom, monument in PROFILS.items():
        print(f"  {nom}")
        m_apres = mesure(apres, facts, monument, non)
        if avant is not None:
            m_avant = mesure(avant, facts, monument, non)
            for etiquette, m in (("AVANT", m_avant), ("APRÈS", m_apres)):
                print(
                    f"    {etiquette}  aides={m['retenues']:3d}  éligibles={m['eligibles']:2d}"
                    f"  mc={m['mc']:3d}  questions={m['questions']:2d}"
                )
            gagnees = m_apres["slugs_eligibles"] - m_avant["slugs_eligibles"]
            if gagnees:
                print(f"    ⚠ deviennent éligibles : {', '.join(sorted(gagnees))}")
        else:
            print(
                f"    aides={m_apres['retenues']:3d}  éligibles={m_apres['eligibles']:2d}"
                f"  mc={m_apres['mc']:3d}  questions={m_apres['questions']:2d}"
            )
        print()

    trous = audit_fail_open(apres)
    print(f"Audit fail-open : {len(trous)} aide(s) sans aucune condition vérifiable")
    for slug, n_hf in trous:
        print(f"  ⚠ {slug} (hard_filters renseignés : {n_hf})")


if __name__ == "__main__":
    main()
