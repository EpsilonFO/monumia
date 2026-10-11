"""L'éditeur par plages : changer une aide existante par le plus petit diff (section 5.2 du prompt).

Un modèle n'écrit jamais de YAML. Le code part du texte en service et de la
cible (le dictionnaire que l'aide doit devenir), et ne réécrit que ce qui change :

- un bloc de premier niveau (`calendrier:`, `financement:`...) dont la valeur
  change est réémis seul ; les autres, commentaires et bloc `fiche:` compris,
  restent à l'octet ;
- dans `conditions:`, un item inchangé reste à l'octet, un item changé est
  réémis seul, un item retiré disparaît (ses commentaires d'en-tête restent :
  ils titrent souvent la section qui suit), un item nouveau s'ajoute en fin de
  liste ;
- l'émission reprend celle de la veille (`veille_apply.emit_field` et
  `emit_item`), qui vérifie chaque chaîne en la relisant ; `fact:` et `levier:`
  restent en style bloc, comme le lisent le lint, `fusionner_faits.py` et
  `retyper_faits.py`.

Le texte produit est relu : s'il ne redonne pas exactement la cible, rien n'est
écrit (`EditionImpossible`). Une cible égale à l'existant rend le texte
d'origine, octet pour octet.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from veille_apply import ORDRE_CHAMPS_CONDITION, emit_field, emit_item

from aides_schema import charger_yaml

_CLE_HAUT = re.compile(r"^([A-Za-z_][\w-]*):(\s|$)")


class EditionImpossible(Exception):
    """Le texte édité ne redonne pas la cible : on n'écrit rien."""


@dataclass(frozen=True)
class Plage:
    cle: str | None  # None : le préambule avant la première clé
    debut: int  # première ligne (commentaires d'en-tête compris)
    cle_ligne: int  # ligne de la clé
    fin: int  # exclue


def _neutre(ligne: str) -> bool:
    nu = ligne.strip()
    return not nu or (nu.startswith("#") and not ligne.startswith(" "))


def plages(lignes: list[str]) -> list[Plage]:
    """Les blocs de premier niveau ; les commentaires et lignes vides qui précèdent une clé lui appartiennent."""
    cles = [i for i, ligne in enumerate(lignes) if _CLE_HAUT.match(ligne)]
    resultat: list[Plage] = []
    debut_prec = 0
    for n, i in enumerate(cles):
        debut = i
        while debut > debut_prec and _neutre(lignes[debut - 1]):
            debut -= 1
        if n == 0 and debut > 0:
            resultat.append(Plage(None, 0, 0, debut))
        elif n > 0:
            prec = resultat[-1]
            resultat[-1] = Plage(prec.cle, prec.debut, prec.cle_ligne, debut)
        m = _CLE_HAUT.match(lignes[i])
        assert m is not None
        resultat.append(Plage(m.group(1), debut, i, len(lignes)))
        debut_prec = i + 1
    return resultat


def _normal(x: Any) -> Any:
    """Forme comparable : dates en ISO, comme après un aller-retour JSON."""
    return json.loads(json.dumps(x, default=str))


def _ordonner(cond: dict[str, Any]) -> dict[str, Any]:
    rang = {k: i for i, k in enumerate(ORDRE_CHAMPS_CONDITION)}
    return dict(sorted(cond.items(), key=lambda kv: rang.get(kv[0], len(rang))))


def _items(lignes: list[str], debut: int, fin: int) -> tuple[int, list[tuple[int, int, int]]]:
    """(indentation des items, [(début avec en-tête, ligne du tiret, fin)]) d'une liste de premier niveau."""
    tirets = [i for i in range(debut + 1, fin) if lignes[i].lstrip().startswith("- ")]
    if not tirets:
        return 2, []
    indent = len(lignes[tirets[0]]) - len(lignes[tirets[0]].lstrip())
    tirets = [i for i in tirets if len(lignes[i]) - len(lignes[i].lstrip()) == indent]
    items: list[tuple[int, int, int]] = []
    plancher = debut + 1
    for t in tirets:
        tete = t
        while (
            tete > plancher
            and (not lignes[tete - 1].strip() or lignes[tete - 1].lstrip().startswith("#"))
            and len(lignes[tete - 1]) - len(lignes[tete - 1].lstrip()) <= indent
        ):
            tete -= 1
        if items:
            d, ti, _ = items[-1]
            items[-1] = (d, ti, tete)
        items.append((tete, t, fin))
        plancher = t + 1
    # Les lignes neutres en fin de liste n'appartiennent pas au dernier item.
    d, ti, f = items[-1]
    while f > ti + 1 and not lignes[f - 1].strip():
        f -= 1
    items[-1] = (d, ti, f)
    return indent, items


def _fin_utile(lignes: list[str], p: Plage) -> int:
    """La fin du contenu d'un bloc, sans les lignes vides qui le séparent du suivant."""
    f = p.fin
    while f > p.cle_ligne + 1 and not lignes[f - 1].strip():
        f -= 1
    return f


def _item_par_champs(
    corps: list[str], ancien: dict[str, Any], cible: dict[str, Any], indent: int
) -> list[str]:
    """Un item de liste modifié champ par champ : les champs inchangés restent à l'octet."""
    if not isinstance(ancien, dict) or not isinstance(cible, dict) or not corps:
        return emit_item(_ordonner(cible), indent)
    pad = " " * (indent + 2)
    # Le premier champ porte le tiret : on le lit comme s'il ne le portait pas.
    lignes = [pad + corps[0][indent + 2 :]] + corps[1:]
    debuts = [
        i
        for i, ligne in enumerate(lignes)
        if ligne.startswith(pad)
        and not ligne.startswith(pad + " ")
        and re.match(r"[\w-]+:", ligne[len(pad) :])
    ]
    if not debuts or debuts[0] != 0:
        return emit_item(_ordonner(cible), indent)
    spans: dict[str, tuple[int, int]] = {}
    for n, d in enumerate(debuts):
        f = debuts[n + 1] if n + 1 < len(debuts) else len(lignes)
        while f > d + 1 and not lignes[f - 1].strip():
            f -= 1
        cle = lignes[d][len(pad) :].split(":", 1)[0]
        spans[cle] = (d, f)
    if list(spans) != [k for k in ancien if k in spans] or set(spans) != set(ancien):
        return emit_item(_ordonner(cible), indent)
    sortie: list[str] = []
    for cle, (d, f) in spans.items():
        if cle not in cible:
            continue
        if _normal(ancien[cle]) == _normal(cible[cle]):
            sortie += lignes[d:f]
        else:
            sortie += emit_field(cle, cible[cle], indent + 2)
        sortie += [
            x
            for x in lignes[
                f : (debuts[debuts.index(d) + 1] if debuts.index(d) + 1 < len(debuts) else f)
            ]
        ]
    # Champs nouveaux : à leur place dans l'ordre des fiches, sinon en fin d'item.
    rang = {k: i for i, k in enumerate(ORDRE_CHAMPS_CONDITION)}
    for cle in [k for k in cible if k not in ancien]:
        rendu = emit_field(cle, cible[cle], indent + 2)
        apres = [k for k in spans if k in cible and rang.get(k, 99) <= rang.get(cle, 99)]
        if apres:
            # Après le dernier champ gardé qui le précède dans l'ordre.
            ancre = apres[-1]
            ligne_ancre = next(i for i, x in enumerate(sortie) if x.startswith(f"{pad}{ancre}:"))
            fin_ancre = ligne_ancre + 1
            while fin_ancre < len(sortie) and (
                sortie[fin_ancre].startswith(pad + " ") or not sortie[fin_ancre].strip()
            ):
                fin_ancre += 1
            sortie[fin_ancre:fin_ancre] = rendu
        else:
            sortie[0:0] = rendu
    if not sortie:
        return emit_item(_ordonner(cible), indent)
    sortie[0] = " " * indent + "- " + sortie[0][indent + 2 :]
    return sortie


def _conditions(lignes: list[str], p: Plage, anciennes: list[Any], cibles: list[Any]) -> list[str]:
    indent, items = _items(lignes, p.cle_ligne, _fin_utile(lignes, p))
    if len(items) != len(anciennes):
        raise EditionImpossible(
            f"{len(items)} items lus pour {len(anciennes)} conditions : liste non éditable par plages"
        )
    par_id = {
        c.get("id"): (lignes[d:f], lignes[d:t], c)
        for (d, t, f), c in zip(items, anciennes, strict=True)
    }
    sortie = [lignes[p.cle_ligne]]
    vus: set[Any] = set()
    for c in cibles:
        ident = c.get("id")
        vus.add(ident)
        if ident in par_id and _normal(par_id[ident][2]) == _normal(c):
            sortie += par_id[ident][0]
        elif ident in par_id:
            corps = par_id[ident][0][len(par_id[ident][1]) :]
            sortie += par_id[ident][1] + _item_par_champs(corps, par_id[ident][2], c, indent)
        else:
            sortie += emit_item(_ordonner(c), indent)
    # Un item retiré laisse ses commentaires d'en-tête, qui titrent ce qui suit.
    for ident, (_, entete, _) in par_id.items():
        if ident not in vus:
            sortie += [x for x in entete if x.strip()]
    return sortie + lignes[_fin_utile(lignes, p) : p.fin]


def editer(texte: str, cible: dict[str, Any]) -> str:
    """Le texte de l'aide modifié par plages pour valoir `cible`. Lève `EditionImpossible`."""
    ancien = charger_yaml(texte) or {}
    if _normal(ancien) == _normal(cible):
        return texte
    if list(ancien) != [k for k in cible if k in ancien]:
        raise EditionImpossible("l'ordre des clés de premier niveau change")
    lignes = texte.split("\n")
    sortie: list[str] = []
    vues: set[str] = set()
    for p in plages(lignes):
        if p.cle is None:
            sortie += lignes[p.debut : p.fin]
            continue
        vues.add(p.cle)
        avant, apres = ancien.get(p.cle), cible.get(p.cle, _ABSENT)
        if apres is _ABSENT:
            continue  # clé retirée, avec ses commentaires d'en-tête
        if _normal(avant) == _normal(apres):
            sortie += lignes[p.debut : p.fin]
        elif p.cle == "conditions" and isinstance(avant, list) and isinstance(apres, list):
            sortie += lignes[p.debut : p.cle_ligne] + _conditions(lignes, p, avant, apres)
        else:
            fin = _fin_utile(lignes, p)
            sortie += (
                lignes[p.debut : p.cle_ligne] + emit_field(p.cle, apres, 0) + lignes[fin : p.fin]
            )
    nouvelles = [k for k in cible if k not in vues]
    if nouvelles:
        while sortie and not sortie[-1].strip():
            sortie.pop()
        for k in nouvelles:
            sortie += ["", *emit_field(k, cible[k], 0)]
        sortie.append("")
    resultat = "\n".join(sortie)
    try:
        relu = charger_yaml(resultat)
    except Exception as exc:  # noqa: BLE001 — tout échec de relecture refuse l'écriture
        raise EditionImpossible(f"YAML illisible après édition : {exc}") from exc
    if _normal(relu) != _normal(cible):
        raise EditionImpossible("le texte édité ne redonne pas la cible")
    return resultat


_ABSENT = object()
