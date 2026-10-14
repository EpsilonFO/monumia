"""Rappel de la recherche des faits : lexicale contre plongements, sur la population de F1.

Commande, depuis backend/ :

    uv run --no-sync python -m catalogue.mesures.rappel_faits

`F1-doublon-fait` n'a pas été adopté le 2026-10-10 parce que la recherche des
voisins ne montrait pas le bon fait une fois sur quatre : Jev choisissait aussi
bien que l'agent quand le fait lui était montré
(`data/reviews/2026-10-10-faits-jev.md`). Cette mesure ne rejoue que la
recherche, sur la même population (les conditions `user_fact` des aides écrites
par l'agent depuis le 2026-09-23, `faits._population`) et la même ontologie
(celle du commit parent de l'aide).

La cible est le fait que l'agent a choisi, quand il existait déjà : c'est la
définition du rappel du rapport du 10, pas une étiquette. Un fait de l'agent
qui refaisait un fait existant compte donc comme une cible juste ; les
étiquettes du 10 (hors git) l'auraient corrigé dans quelques cas.

Voisinages comparés, rappel à 1, 5, 10 et 20 :

  - `proches`, `recherche` : les deux lexicaux du 10, repris de `faits.py` ;
  - `plongement` : cosinus entre le texte de la condition (avec la consigne
    « condition vers fait ») et `plongements.texte_fait` de chaque fait ;
  - `plongement_citation` : idem, la citation ajoutée au texte ;
  - `hybride` : fusion des rangs (reciprocal rank fusion, k = 60) de
    `recherche` et `plongement`.

Sortie : un dossier neuf sous data/reviews/logs/refonte/ (hors git) avec
`rappel.json` et `rates.jsonl` (les conditions que chaque voisinage manque à
20). Appels : le seul modèle d'embedding du registre, mis en cache.
"""

from __future__ import annotations

import json
import random
from collections.abc import Callable
from typing import Any

from catalogue.mesures.faits import (
    GRAINE,
    TAILLE_F1,
    ConditionEcrite,
    _kind,
    _neuf,
    _population,
    _tous,
    _voisins_proches,
    _voisins_recherche,
)
from catalogue.mesures.jeu_e import _dossier_neuf
from catalogue.plongements import (
    CONSIGNE_CONDITION_VERS_FAIT,
    Plongeur,
    avec_consigne,
    plus_proches,
    texte_fait,
)

PROFONDEURS = (1, 5, 10, 20)
N = max(PROFONDEURS)
RRF_K = 60


def _requete(c: ConditionEcrite, citation: bool) -> str:
    texte = " ".join((c.brute.get("text") or "").split())
    if citation and c.brute.get("quote"):
        texte += "\nCitation : " + " ".join(str(c.brute["quote"]).split())
    return avec_consigne(CONSIGNE_CONDITION_VERS_FAIT, texte)


def _par_plongement(
    plongeur: Plongeur, conditions: list[ConditionEcrite], citation: bool
) -> dict[tuple[str, int], list[str]]:
    """Les N faits les plus proches de chaque condition, dans l'ontologie de son commit parent."""
    requetes = plongeur.vecteurs([_requete(c, citation) for c in conditions])
    par_rev: dict[str | None, list[int]] = {}
    for i, c in enumerate(conditions):
        par_rev.setdefault(c.aide.ajout.parent, []).append(i)
    sortie: dict[tuple[str, int], list[str]] = {}
    for rev, indices in par_rev.items():
        ontologie = _tous(rev)
        cles = list(ontologie)
        corpus = plongeur.vecteurs([texte_fait(k, ontologie[k]) for k in cles])
        rangs, _ = plus_proches(requetes[indices], corpus, N)
        for i, ligne in zip(indices, rangs, strict=True):
            sortie[conditions[i].cle] = [cles[j] for j in ligne]
    return sortie


def _lexical(
    fonction: Callable[[str, str | None], list[tuple[float, str]]],
    conditions: list[ConditionEcrite],
) -> dict[tuple[str, int], list[str]]:
    return {
        c.cle: [cle for _, cle in fonction(c.brute.get("text") or "", c.aide.ajout.parent)]
        for c in conditions
    }


def _hybride(*classements: dict[tuple[str, int], list[str]]) -> dict[tuple[str, int], list[str]]:
    sortie: dict[tuple[str, int], list[str]] = {}
    for cle in classements[0]:
        scores: dict[str, float] = {}
        for classement in classements:
            for rang, fait in enumerate(classement[cle], 1):
                scores[fait] = scores.get(fait, 0.0) + 1 / (RRF_K + rang)
        sortie[cle] = sorted(scores, key=lambda f: -scores[f])[:N]
    return sortie


def _rappel(
    conditions: list[ConditionEcrite], voisins: dict[tuple[str, int], list[str]]
) -> dict[str, Any]:
    cibles = [c for c in conditions if not _neuf(c)]
    sortie: dict[str, Any] = {"conditions_a_fait_existant": len(cibles)}
    for k in PROFONDEURS:
        trouves = sum(1 for c in cibles if c.fait in voisins[c.cle][:k])
        sortie[f"a_{k}"] = f"{trouves}/{len(cibles)}"
        sortie[f"part_a_{k}"] = round(trouves / len(cibles), 4) if cibles else None
    return sortie


def main() -> int:
    _, conditions, _ = _population()
    user_fact = [c for c in conditions if _kind(c.brute) == "user_fact"]
    # Le tirage de `faits.tirer`, rejoué : même graine, même premier appel.
    f1 = random.Random(GRAINE).sample(user_fact, min(TAILLE_F1, len(user_fact)))

    plongeur = Plongeur()
    try:
        voisinages = {
            "proches": _lexical(_voisins_proches, user_fact),
            "recherche": _lexical(_voisins_recherche, user_fact),
            "plongement": _par_plongement(plongeur, user_fact, citation=False),
            "plongement_citation": _par_plongement(plongeur, user_fact, citation=True),
        }
        voisinages["hybride"] = _hybride(voisinages["recherche"], voisinages["plongement"])
    finally:
        plongeur.fermer()

    resultat = {
        "modele": plongeur.modele.nom,
        "population": {nom: _rappel(user_fact, v) for nom, v in voisinages.items()},
        "f1": {nom: _rappel(f1, v) for nom, v in voisinages.items()},
        "cout_usd": round(plongeur.cout_usd, 6),
        "appels": plongeur.appels,
    }
    dossier = _dossier_neuf("rappel-faits")
    (dossier / "rappel.json").write_text(
        json.dumps(resultat, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    with (dossier / "rates.jsonl").open("w", encoding="utf-8") as f:
        for c in user_fact:
            if _neuf(c):
                continue
            rates = [nom for nom, v in voisinages.items() if c.fait not in v[c.cle]]
            if rates:
                ligne = {
                    "aide": c.aide.slug,
                    "rang": c.rang,
                    "text": c.brute.get("text"),
                    "fait_agent": c.fait,
                    "rate_par": rates,
                    "plongement_top5": voisinages["plongement"][c.cle][:5],
                }
                f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    print(dossier)
    print(json.dumps(resultat, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
