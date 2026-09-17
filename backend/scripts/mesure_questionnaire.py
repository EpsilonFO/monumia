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
from profils_questionnaire import (  # noqa: E402
    PROFILS,
    Mesure,
    Profil,
    mesurer,
    parcours_simule,
)

# Ratchet du tronc commun : le fichier que le test de CI compare au catalogue.
BASELINE_FILE = Path(__file__).resolve().parent.parent / "data" / "questionnaire_baseline.json"


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


def mesure(aides: dict, facts: dict, profil: Profil) -> Mesure:
    return mesurer(aides, facts, profil)


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


def baseline_courante(aides: dict, facts: dict) -> dict:
    """État du tronc commun profil par profil, au format du ratchet.

    `tronc_ids` est là pour le message d'échec : sans lui, un test rouge dirait
    « 27 au lieu de 25 » sans nommer les deux questions entrées, et il faudrait
    relancer le banc à la main pour relire le diff. `parcours_ids` joue le même
    rôle pour le parcours simulé.

    Le PARCOURS est la grandeur que vit l'utilisateur : le tronc dit ce que le
    questionnaire pourrait poser, le parcours ce qu'il pose réellement une fois
    que les réponses ont écarté des aides. Les deux sont enregistrés, parce que
    le second seul masquerait un tronc qui gonfle derrière une première réponse
    très éliminante.
    """
    out = {}
    for nom, profil in PROFILS.items():
        m = mesurer(aides, facts, profil)
        parcours = parcours_simule(aides, facts, profil)
        out[nom] = {
            "tronc": len(m.tronc),
            "tronc_ids": sorted(q["id"] for q in m.tronc),
            "parcours": len(parcours),
            "parcours_ids": parcours,
            # Informatif : le total croît avec le catalogue, c'est justement ce
            # dont le tronc commun affranchit l'utilisateur.
            "total": len(m.questions),
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--retypages", type=Path, help="snapshot JSON d'un typage antérieur")
    ap.add_argument("--snapshot", type=Path, help="enregistre le typage courant et sort")
    ap.add_argument(
        "--update-baseline",
        action="store_true",
        help="réécrit data/questionnaire_baseline.json (le diff fait partie de la revue)",
    )
    args = ap.parse_args()

    facts = {**load_facts(), **load_pending_facts()}
    apres = charge_aides()
    if args.snapshot:
        snapshot(apres, args.snapshot)
        return
    if args.update_baseline:
        etat = baseline_courante(apres, facts)
        BASELINE_FILE.write_text(
            json.dumps(etat, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"baseline réécrit : {BASELINE_FILE.name} ({len(etat)} profil(s)) — à relire au diff")
        return
    avant = rejoue_typage(apres, json.loads(args.retypages.read_text())) if args.retypages else None

    print("Banc de mesure — colonnes : aides non écartées par un hard_filter, dont")
    print("éligibles, conditions manual_check en incertitude, questions posées.")
    print("« tronc » = questions partagées par au moins deux aides (le questionnaire")
    print("général) ; « propres » = questions d'une seule aide, posées sur sa carte.\n")
    for nom, profil in PROFILS.items():
        print(f"  {nom}")
        m_apres = mesure(apres, facts, profil)
        if avant is not None:
            m_avant = mesure(avant, facts, profil)
            for etiquette, m in (("AVANT", m_avant), ("APRÈS", m_apres)):
                print(
                    f"    {etiquette}  aides={m.retenues:3d}  éligibles={m.eligibles:2d}"
                    f"  mc={m.manual_check:3d}  questions={len(m.questions):3d}"
                    f"  tronc={len(m.tronc):3d}  propres={len(m.propres):3d}"
                )
            gagnees = m_apres.slugs_eligibles - m_avant.slugs_eligibles
            if gagnees:
                print(f"    ⚠ deviennent éligibles : {', '.join(sorted(gagnees))}")
        else:
            print(
                f"    aides={m_apres.retenues:3d}  éligibles={m_apres.eligibles:2d}"
                f"  mc={m_apres.manual_check:3d}  questions={len(m_apres.questions):3d}"
                f"  tronc={len(m_apres.tronc):3d}  propres={len(m_apres.propres):3d}"
            )
        print()

    trous = audit_fail_open(apres)
    print(f"Audit fail-open : {len(trous)} aide(s) sans aucune condition vérifiable")
    for slug, n_hf in trous:
        print(f"  ⚠ {slug} (hard_filters renseignés : {n_hf})")


if __name__ == "__main__":
    main()
