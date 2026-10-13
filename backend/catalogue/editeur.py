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

from aides_schema import charger_yaml
from catalogue.veille_apply import ORDRE_CHAMPS_CONDITION, emit_field, emit_item

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


def _emettre(cle: str, valeur: Any, indent: int) -> list[str]:
    """`emit_field`, plus les conteneurs vides, qu'il ne sait pas écrire."""
    if valeur == {} or valeur == []:
        return [f"{' ' * indent}{cle}: {'{}' if valeur == {} else '[]'}"]
    return emit_field(cle, valeur, indent)


def _neutre_champ(ligne: str, indent: int) -> bool:
    """Ligne vide, ou commentaire au niveau des champs : elle appartient au champ qui suit."""
    nu = ligne.strip()
    return not nu or (nu.startswith("#") and len(ligne) - len(ligne.lstrip()) <= indent)


def _champs(
    lignes: list[str],
    ancien: dict[str, Any],
    cible: dict[str, Any],
    indent: int,
    ordre: tuple[str, ...] = (),
) -> list[str] | None:
    """Les champs d'un mapping indenté de `indent`, remplacés un par un ; `None` si la forme surprend.

    Un champ inchangé reste à l'octet ; un commentaire placé avant un champ lui
    appartient, et survit au remplacement du champ qui le précède.
    """
    pad = " " * indent
    debuts = [
        i
        for i, ligne in enumerate(lignes)
        if ligne.startswith(pad)
        and not ligne.startswith(pad + " ")
        and re.match(r"[\w-]+:", ligne[indent:])
    ]
    if not debuts:
        return None
    cles = [lignes[d][indent:].split(":", 1)[0] for d in debuts]
    if cles != list(ancien):
        return None
    sortie = lignes[: debuts[0]]
    fins: dict[str, int] = {}
    for n, d in enumerate(debuts):
        suivant = debuts[n + 1] if n + 1 < len(debuts) else len(lignes)
        f = suivant
        while f > d + 1 and _neutre_champ(lignes[f - 1], indent):
            f -= 1
        cle = cles[n]
        if cle in cible:
            if _normal(ancien[cle]) == _normal(cible[cle]):
                sortie += lignes[d:f]
            else:
                sortie += _emettre(cle, cible[cle], indent)
            fins[cle] = len(sortie)
        sortie += lignes[f:suivant]
    rang = {k: i for i, k in enumerate(ordre)}
    for cle in [k for k in cible if k not in ancien]:
        rendu = _emettre(cle, cible[cle], indent)
        if ordre:
            # À sa place dans l'ordre des fiches : après le dernier champ gardé qui le précède.
            avant = [k for k in fins if rang.get(k, len(rang)) <= rang.get(cle, len(rang))]
            position = fins[avant[-1]] if avant else len(lignes[: debuts[0]])
        else:
            position = len(sortie)
            while position > 0 and not sortie[position - 1].strip():
                position -= 1
        sortie[position:position] = rendu
        fins = {k: (v + len(rendu) if v >= position else v) for k, v in fins.items()}
        fins[cle] = position + len(rendu)
    return sortie


def _item_par_champs(
    corps: list[str], ancien: dict[str, Any], cible: dict[str, Any], indent: int
) -> list[str]:
    """Un item de liste modifié champ par champ : les champs inchangés restent à l'octet."""
    if not isinstance(ancien, dict) or not isinstance(cible, dict) or not corps:
        return emit_item(_ordonner(cible), indent)
    # Le premier champ porte le tiret : on le lit comme s'il ne le portait pas.
    lignes = [" " * (indent + 2) + corps[0][indent + 2 :]] + corps[1:]
    sortie = _champs(lignes, ancien, cible, indent + 2, ORDRE_CHAMPS_CONDITION)
    if not sortie or not sortie[0].startswith(" " * (indent + 2)):
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


def _bloc(lignes: list[str], p: Plage, avant: Any, apres: Any) -> list[str]:
    """Un bloc de premier niveau changé : champ par champ si c'est un mapping écrit en bloc."""
    fin = _fin_utile(lignes, p)
    if (
        p.cle == "conditions"
        and isinstance(avant, list)
        and isinstance(apres, list)
        and avant
        and apres
    ):
        return lignes[p.debut : p.cle_ligne] + _conditions(lignes, p, avant, apres)
    if isinstance(avant, dict) and isinstance(apres, dict) and avant and apres:
        corps = lignes[p.cle_ligne + 1 : fin]
        premiere = next((x for x in corps if x.strip() and not x.lstrip().startswith("#")), "")
        indent = len(premiere) - len(premiere.lstrip())
        if indent > 0 and lignes[p.cle_ligne].rstrip().endswith(":"):
            champs = _champs(corps, avant, apres, indent)
            if champs is not None:
                return lignes[p.debut : p.cle_ligne + 1] + champs + lignes[fin : p.fin]
    return lignes[p.debut : p.cle_ligne] + _emettre(p.cle or "", apres, 0) + lignes[fin : p.fin]


def editer(texte: str, cible: dict[str, Any]) -> str:
    """Le texte de l'aide modifié par plages pour valoir `cible`. Lève `EditionImpossible`."""
    ancien = charger_yaml(texte) or {}
    if _normal(ancien) == _normal(cible):
        return texte
    if [k for k in ancien if k in cible] != [k for k in cible if k in ancien]:
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
        else:
            sortie += _bloc(lignes, p, avant, apres)
    nouvelles = [k for k in cible if k not in vues]
    if nouvelles:
        while sortie and not sortie[-1].strip():
            sortie.pop()
        for k in nouvelles:
            sortie += ["", *_emettre(k, cible[k], 0)]
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
