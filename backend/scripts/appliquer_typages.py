"""Applique un plan de retypage, condition par condition. Réécriture TEXTUELLE.

Script de MIGRATION, jumeau de `retyper_faits.py` (dont il reprend le découpage
des blocs) : il sert à appliquer l'arbitrage de la cohérence du typage
(`catalogue/coherence.py`, 2026-10-14) et les fusions de faits qui l'ont suivi.

    uv run python scripts/appliquer_typages.py data/coherence/<plan>.yaml --dry-run
    uv run python scripts/appliquer_typages.py data/coherence/<plan>.yaml

Le plan est une liste d'entrées, une par condition :

    - ref: <slug>#<id de condition>
      kind: user_fact
      effect: gate
      fact: statut_juridique_porteur
      predicate: {in: [association, fondation]}
      derogation_possible: true       # facultatif
      applies_if: {fact: …, predicate: …}   # facultatif ; `null` le retire
      motif: Arbitrage G002, bénéficiaires énumérés.

Le mandat est ÉTROIT. Sur la condition visée, les clés de TYPAGE (`kind`,
`effect`, `fact`, `field`, `predicate`, `derogation_possible`, `levier`) sont
remplacées par celles du plan : une clé de typage absente du plan disparaît.
`applies_if` n'est touché que si le plan le nomme. `text`, `quote` et les
autres clés ne bougent jamais ; `notes` gagne une ligne de provenance. Les
autres conditions et le reste du fichier restent octet pour octet.

Garde-fous : chaque fichier réécrit doit passer le schéma (`Aide`), et sa
relecture ne doit différer de l'original que sur les conditions visées et ces
clés-là. Un fichier qui échoue n'est pas écrit, et le script le nomme ; le
lint (`lint_aides_data.py`) reste à lancer après.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from retyper_faits import _bloc_condition, _detacher_queue, _segments

from aides_schema import AIDES_DIR, Aide

CLES_TYPAGE = ("kind", "effect", "fact", "field", "predicate", "derogation_possible", "levier")
#: L'ordre où les clés de typage sont réécrites, après `text`.
ORDRE = ("kind", "effect", "fact", "field", "predicate", "derogation_possible", "levier")
CLES_PLAN = {*CLES_TYPAGE, "ref", "motif", "applies_if"}


def _bloc(cle: str, valeur: Any, indent: int) -> list[str]:
    """Les lignes YAML d'une clé, indentées. L'échappement vient de PyYAML."""
    brut = yaml.safe_dump({cle: valeur}, allow_unicode=True, sort_keys=False, width=100)
    return [(" " * indent + li) if li.strip() else li for li in brut.splitlines(keepends=True)]


def _notes(ancien: Any, motif: str, jour: date) -> str:
    ligne = f"Retypé le {jour.isoformat()} (cohérence du typage) : {motif}"
    ancien = " ".join(str(ancien).split()) if ancien else ""
    return f"{ancien} {ligne}".strip()


def reecrire_condition(
    lignes: list[str], brut: dict[str, Any], entree: dict[str, Any], jour: date
) -> list[str] | None:
    """Le fichier, bloc de la condition réécrit. None si la forme échappe."""
    trouve = _bloc_condition(lignes, str(brut["id"]))
    if trouve is None:
        return None
    debut, fin, indent = trouve
    typage: list[str] = []
    for cle in ORDRE:
        if cle in entree:
            typage += _bloc(cle, entree[cle], indent)
    nommer_applies_if = "applies_if" in entree
    sortie: list[str] = [lignes[debut]]
    place = False
    notes_vues = False
    queue: list[str] = []
    for cle, segment in _segments(lignes[debut + 1 : fin], indent):
        corps, queue = _detacher_queue(segment, indent)
        if cle in CLES_TYPAGE or (cle == "applies_if" and nommer_applies_if):
            sortie.extend(queue)
            continue
        if cle == "notes":
            notes_vues = True
            sortie += _bloc("notes", _notes(brut.get("notes"), entree["motif"], jour), indent)
            sortie.extend(queue)
            continue
        sortie.extend(corps)
        if cle == "text" and not place:
            sortie += typage
            if nommer_applies_if and entree["applies_if"] is not None:
                sortie += _bloc("applies_if", entree["applies_if"], indent)
            place = True
        sortie.extend(queue)
    if not place:
        return None
    if not notes_vues:
        ajout = _bloc("notes", _notes(None, entree["motif"], jour), indent)
        if queue and sortie[-len(queue) :] == queue:
            sortie[len(sortie) - len(queue) :] = ajout + queue
        else:
            sortie += ajout
    return lignes[:debut] + sortie + lignes[fin:]


def _attendu(brut: dict[str, Any], entree: dict[str, Any], jour: date) -> dict[str, Any]:
    """La condition telle que le plan la veut, pour la vérification par relecture."""
    sortie = {k: v for k, v in brut.items() if k not in CLES_TYPAGE}
    for cle in CLES_TYPAGE:
        if cle in entree:
            sortie[cle] = entree[cle]
    if "applies_if" in entree:
        sortie.pop("applies_if", None)
        if entree["applies_if"] is not None:
            sortie["applies_if"] = entree["applies_if"]
    sortie["notes"] = _notes(brut.get("notes"), entree["motif"], jour)
    return sortie


def _normaliser(valeur: Any) -> Any:
    """Les notes comparées sans la mise en forme du scalaire replié."""
    if isinstance(valeur, dict):
        return {
            k: (" ".join(v.split()) if k == "notes" and isinstance(v, str) else _normaliser(v))
            for k, v in valeur.items()
        }
    if isinstance(valeur, list):
        return [_normaliser(v) for v in valeur]
    return valeur


def appliquer(
    plan: list[dict[str, Any]], *, aides_dir: Path = AIDES_DIR, ecrire: bool, jour: date
) -> tuple[list[str], list[str]]:
    """(fichiers réécrits, erreurs). Rien n'est écrit pour un fichier en erreur."""
    erreurs: list[str] = []
    par_fichier: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entree in plan:
        inconnues = set(entree) - CLES_PLAN
        if inconnues or "#" not in str(entree.get("ref", "")) or not entree.get("motif"):
            erreurs.append(f"entrée invalide : {entree.get('ref')} {sorted(inconnues)}")
            continue
        slug, cid = entree["ref"].split("#", 1)
        par_fichier[slug].append({**entree, "_id": cid})
    ecrits: list[str] = []
    for slug, entrees in sorted(par_fichier.items()):
        chemin = aides_dir / f"{slug}.yaml"
        if not chemin.exists():
            erreurs.append(f"{slug} : fichier absent")
            continue
        texte = chemin.read_text(encoding="utf-8")
        avant = yaml.safe_load(texte)
        conditions = {c["id"]: c for c in avant.get("conditions") or []}
        lignes = texte.splitlines(keepends=True)
        attendu = dict(conditions)
        echec = None
        for entree in entrees:
            brut = conditions.get(entree["_id"])
            if brut is None:
                echec = f"{entree['ref']} : condition absente"
                break
            rendu = reecrire_condition(lignes, brut, entree, jour)
            if rendu is None:
                echec = f"{entree['ref']} : forme inattendue, bloc non réécrit"
                break
            lignes = rendu
            attendu[entree["_id"]] = _attendu(brut, entree, jour)
        if echec:
            erreurs.append(echec)
            continue
        nouveau = "".join(lignes)
        apres = yaml.safe_load(nouveau)
        reste_avant = {k: v for k, v in avant.items() if k != "conditions"}
        reste_apres = {k: v for k, v in apres.items() if k != "conditions"}
        voulu = [_normaliser(attendu[c["id"]]) for c in avant["conditions"]]
        if reste_avant != reste_apres or _normaliser(apres["conditions"]) != voulu:
            erreurs.append(f"{slug} : la relecture ne correspond pas au plan")
            continue
        try:
            Aide.model_validate(apres)
        except ValueError as exc:
            erreurs.append(f"{slug} : schéma refusé ({' '.join(str(exc).split())[:300]})")
            continue
        if ecrire:
            chemin.write_text(nouveau, encoding="utf-8")
        ecrits.append(slug)
    return ecrits, erreurs


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parseur.add_argument("plan", type=Path)
    parseur.add_argument("--dry-run", action="store_true")
    args = parseur.parse_args(argv)
    plan = yaml.safe_load(args.plan.read_text(encoding="utf-8")) or []
    ecrits, erreurs = appliquer(plan, ecrire=not args.dry_run, jour=date.today())
    print(
        f"{len(plan)} entrées, {len(ecrits)} fichiers {'à réécrire' if args.dry_run else 'réécrits'}"
    )
    for e in erreurs:
        print(f"  ERREUR {e}")
    return 1 if erreurs else 0


if __name__ == "__main__":
    raise SystemExit(main())
