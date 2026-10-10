"""Second avis sur le doute d'entrée : extraction légère, puis Jev (I0, option (d)).

Commandes, depuis backend/ :

    uv run python -m catalogue.mesures.second_avis mesurer <dossier du jeu E>
    uv run python -m catalogue.mesures.second_avis evaluer <dossier du jeu E> <etiquettes.json>

`mesurer` (payant, plafond 1 $) prend les pages du jeu E que la règle de
production (`regle-1/`) laisse au doute, ni écartées ni promues. Pour chacune :
une extraction légère par `or-glm` (JSON validé : nature de la page, porteur,
bénéficiaires, dépenses éligibles, conditions d'activité, exclusions, montant,
chaque élément avec sa citation), sans jugement d'entrée ; le code ne garde que
les citations retrouvées dans le texte de la page (`veille_text.find_quote`) ;
puis Jev sur un état fait de la tête de l'étape 3 du skill et de cette
extraction, avec les questions de `combinaison.QUESTIONS`. Le coût de chaque
appel est celui que facture OpenRouter dans la réponse. Sortie dans un
sous-dossier neuf second-avis-<k>/ : reponses.jsonl.

`evaluer` mesure, sur ces seules pages au doute, ce que le second avis permet
de trancher dans les budgets : validation croisée de `combinaison.valider`,
signaux existants (Jev de production et LLM de lecture) contre les mêmes plus
le second avis. Le critère d'adoption de l'option (d) est écrit au journal du
2026-10-10. Sortie : second-avis.json et second-avis.txt dans le dossier du jeu E.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Literal

from pipeline import llm
from pipeline.decision import ClientDecision, ErreurDecision
from pydantic import BaseModel, Field
from veille_text import find_quote

from catalogue.mesures.combinaison import (
    EXCLUSIONS,
    QUESTIONS,
    _issue_production,
    _probabilites,
    _variables,
    criteres,
    lignes_configurations,
    valider,
)
from catalogue.mesures.jeu_e import (
    MODELE_LECTURE,
    _cout_facture,
    _lire_jsonl,
    _sous_dossier_neuf,
    pages_sans_contenu,
    verdict,
)

PLAFOND_USD = 1.0
RESERVE_PAGE_USD = 0.006

CONSIGNE = """Tu relèves, sans juger, ce qu'une page dit d'un dispositif d'aide.

Pour chaque élément, `citation` est une copie EXACTE d'un passage de la page,
caractère pour caractère, sans reformulation ni coupe au milieu d'un mot ; un
élément sans passage qui le dise n'est pas relevé. `quoi` le résume en quelques
mots. Une liste reste vide quand la page ne dit rien sur le sujet.

- nature : ce qu'est la page (un dispositif qu'on peut demander, un portail ou
  une liste de dispositifs, une actualité, un programme ou une politique sans
  aide à demander, un formulaire, autre chose).
- porteur : l'organisme qui finance ou attribue, tel que la page le nomme.
- beneficiaires : qui peut déposer, en quelle qualité, avec les passages qui le
  disent (« les communes de moins de 2 000 habitants », « les associations
  gestionnaires d'un site », « les compagnies professionnelles »).
- depenses_eligibles : ce que l'aide finance.
- conditions_activite : les conditions qui réservent l'aide à un métier, un
  statut ou une activité professionnelle (licence, label professionnel,
  affiliation, inscription au registre, ancienneté d'activité).
- exclusions : ce que la page exclut explicitement.
- montant : le montant, le taux ou le plafond, s'il est écrit."""


class Passage(BaseModel):
    quoi: str = Field(description="Ce que dit le passage, en quelques mots")
    citation: str = Field(description="Copie exacte d'un passage de la page")


class ExtractionLegere(BaseModel):
    nature: Literal[
        "dispositif", "portail_ou_liste", "actualite", "programme", "formulaire", "autre"
    ]
    porteur: str | None = Field(description="Organisme qui finance, tel que la page le nomme")
    beneficiaires: list[Passage]
    depenses_eligibles: list[Passage]
    conditions_activite: list[Passage]
    exclusions: list[Passage]
    montant: Passage | None


def _pages_au_doute(dossier: Path) -> list[str]:
    regle = _lire_jsonl(dossier / "regle-1" / "reponses.jsonl")
    return [r["id"] for r in regle if "panne" not in r and _issue_production(r) == "doute"]


def _filtrer(extraction: ExtractionLegere, texte: str) -> tuple[dict[str, Any], int, int]:
    """L'extraction, privée des passages dont la citation ne se retrouve pas."""
    gardees = rejetees = 0

    def garder(p: Passage | None) -> dict[str, str] | None:
        nonlocal gardees, rejetees
        if p is None:
            return None
        if find_quote(p.citation, texte).status == "absente":
            rejetees += 1
            return None
        gardees += 1
        return {"quoi": p.quoi, "citation": p.citation}

    def liste(ps: list[Passage]) -> list[dict[str, str]]:
        return [g for p in ps if (g := garder(p)) is not None]

    filtre = {
        "nature": extraction.nature,
        "porteur": extraction.porteur,
        "beneficiaires": liste(extraction.beneficiaires),
        "depenses_eligibles": liste(extraction.depenses_eligibles),
        "conditions_activite": liste(extraction.conditions_activite),
        "exclusions": liste(extraction.exclusions),
        "montant": garder(extraction.montant),
    }
    return filtre, gardees, rejetees


def mesurer(args: argparse.Namespace) -> int:
    dossier = Path(args.dossier)
    sortie = _sous_dossier_neuf(dossier, "second-avis")
    llm.charger_env()
    lecteur = llm.client_pour("lecture", MODELE_LECTURE)
    jev = ClientDecision()
    texte_criteres = criteres()
    telechargements = {t["id"]: t for t in _lire_jsonl(dossier / "telechargements.jsonl")}
    depense = 0.0
    n = pannes = 0
    with (sortie / "reponses.jsonl").open("w", encoding="utf-8") as f:
        for i in _pages_au_doute(dossier):
            if depense + RESERVE_PAGE_USD > PLAFOND_USD:
                print(f"plafond atteint avant {i} ({depense:.4f} $)")
                break
            t = telechargements[i]
            texte = (dossier / "pages" / f"{i}.md").read_text(encoding="utf-8")
            prompt = "\n\n".join(
                [
                    f"URL : {t['url_finale']}",
                    "Documents liés depuis cette page :\n"
                    + ("\n".join(f"  {u}" for u in t["documents"]) or "  (aucun)"),
                    "--- Texte du document PDF ---"
                    if t["est_pdf"]
                    else "--- Contenu de la page ---",
                    texte,
                ]
            )
            ligne: dict[str, Any] = {"id": i}
            debut = time.monotonic()
            essai = lecteur.try_complete_json(ExtractionLegere, prompt, system=CONSIGNE)
            reponse = essai.response
            facture = _cout_facture(reponse)
            ligne.update(
                modele_llm=getattr(getattr(reponse, "raw", None), "model", None),
                cout_llm_facture=facture,
                cout_llm_estime=getattr(reponse, "cost_usd", None),
                duree_llm_s=round(time.monotonic() - debut, 2),
            )
            # Un coût inconnu ne compte jamais pour zéro.
            depense += facture if facture is not None else RESERVE_PAGE_USD
            if essai.data is None:
                ligne["panne"] = f"extraction : {getattr(reponse, 'error', None)}"
            else:
                filtre, gardees, rejetees = _filtrer(essai.data, texte)
                ligne.update(
                    extraction=filtre, citations_gardees=gardees, citations_rejetees=rejetees
                )
                etat = {"criteres": texte_criteres, "aide": {"url": t["url_finale"], **filtre}}
                for tentative in range(2):
                    try:
                        d = jev.decider(etat, QUESTIONS)
                        ligne.update(
                            probabilites=_probabilites(d),
                            modele_jev=d.modele,
                            cout_jev=d.cout_usd,
                            jetons_jev=d.jetons_entree,
                        )
                        ligne.pop("panne", None)
                        break
                    except ErreurDecision as exc:
                        ligne["panne"] = f"jev (essai {tentative + 1}) : {exc}"
                        time.sleep(5)
                cout_jev = ligne.get("cout_jev")
                depense += cout_jev if isinstance(cout_jev, int | float) else 0.002
            ligne["duree_s"] = round(time.monotonic() - debut, 2)
            pannes += "panne" in ligne
            n += 1
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
            f.flush()
    jev.fermer()
    print(f"{sortie} : {n} pages, {pannes} pannes, dépense comptée {depense:.4f} $")
    return 0


def _variables_second_avis(p: dict[str, float]) -> list[float]:
    exclusions = [p[f"exclusion_{nom}"] for nom in EXCLUSIONS]
    return [
        p["dispositif"],
        max(exclusions),
        p["qualite_proprietaire"],
        p["reserve_metier"],
        p["objet_lieu"],
        p["beneficiaires_mixtes"],
        p["deposable"],
    ]


def evaluer(args: argparse.Namespace) -> int:
    dossier = Path(args.dossier)
    echantillon = {e["id"]: e for e in _lire_jsonl(dossier / "echantillon.jsonl")}
    etiquettes: dict[str, str] = {}
    brut = json.loads(Path(args.etiquettes).read_text(encoding="utf-8"))
    # Les pages sans contenu jugeable sortent des mesures (`jeu_e.pages_sans_contenu`).
    vides = {} if args.avec_pages_vides else pages_sans_contenu(dossier, brut)
    for e in brut:
        if e.get("final") and e["id"] not in vides:
            f = e["final"]
            etiquettes[e["id"]] = verdict(f["destinataire"], f["objet"], f.get("categorie_ecart"))
    regle = {r["id"]: r for r in _lire_jsonl(dossier / "regle-1" / "reponses.jsonl")}
    second = {r["id"]: r for r in _lire_jsonl(dossier / "second-avis-1" / "reponses.jsonl")}

    ids: list[str] = []
    variables: dict[str, dict[str, list[float]]] = {}
    exclues: dict[str, str] = {}
    for i in _pages_au_doute(dossier):
        if i not in etiquettes:
            exclues[i] = "sans étiquette"
            continue
        s = second.get(i)
        if s is None or "panne" in s:
            exclues[i] = "second avis en panne ou absent"
            continue
        base = _variables(regle[i], None)["jev_production_et_llm"]
        v_second = _variables_second_avis(s["probabilites"])
        variables[i] = {"existants": base, "existants_et_second_avis": base + v_second}
        ids.append(i)
    poids = {i: 1.0 / echantillon[i]["p_inclusion"] for i in ids}
    # Sur ces pages, la règle de production ne tranche rien : sa référence est
    # le doute partout.
    reference = dict.fromkeys(ids, "doute")
    configurations = valider(
        ids, variables, etiquettes, poids, reference, ["existants", "existants_et_second_avis"]
    )
    comptes = {
        e: sum(poids[i] for i in ids if etiquettes[i] == e)
        for e in ("retenue", "indeterminee", "ecartee")
    }
    resultat = {
        "pages": len(ids),
        "exclues": exclues,
        "etiquettes_brutes": {
            e: sum(1 for i in ids if etiquettes[i] == e)
            for e in ("retenue", "indeterminee", "ecartee")
        },
        "etiquettes_ponderees": comptes,
        "citations": {
            "gardees": sum(second[i].get("citations_gardees", 0) for i in ids),
            "rejetees": sum(second[i].get("citations_rejetees", 0) for i in ids),
        },
        "cout_llm_facture": sum(second[i].get("cout_llm_facture") or 0.0 for i in ids),
        "cout_jev": sum(second[i].get("cout_jev") or 0.0 for i in ids),
        "configurations": configurations,
    }
    for nom, bloc in configurations.items():
        resultat.setdefault("part_tranchee", {})[nom] = 1.0 - bloc["taux_cumules"]["part_doute"]
    (dossier / "second-avis.json").write_text(
        json.dumps(resultat, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    lignes = [
        f"pages au doute évaluées : {len(ids)} ; exclues : {len(exclues)}",
        f"étiquettes : {resultat['etiquettes_brutes']}",
        f"citations gardées {resultat['citations']['gardees']}, rejetées {resultat['citations']['rejetees']}",
        f"coût facturé : LLM {resultat['cout_llm_facture']:.4f} $, Jev {resultat['cout_jev']:.4f} $",
        *lignes_configurations(configurations),
        *(f"part tranchée, {k} : {v:.3f}" for k, v in resultat["part_tranchee"].items()),
    ]
    (dossier / "second-avis.txt").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print("\n".join(lignes))
    return 0


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sous = parseur.add_subparsers(dest="commande", required=True)
    p = sous.add_parser("mesurer")
    p.add_argument("dossier")
    p.set_defaults(fonction=mesurer)
    p = sous.add_parser("evaluer")
    p.add_argument("dossier")
    p.add_argument("etiquettes")
    p.add_argument("--avec-pages-vides", action="store_true")
    p.set_defaults(fonction=evaluer)
    args = parseur.parse_args()
    return args.fonction(args)


if __name__ == "__main__":
    raise SystemExit(main())
