"""Liste les faits de l'ontologie qu'aucune aide n'utilise, ni directement ni par rebond.

    uv run python scripts/faits_orphelins.py
    uv run python scripts/faits_orphelins.py --json

Couvre `facts.yaml` ET `facts_pending.yaml`. Le lint et `retyper_faits.py
--retirer-orphelins` ne regardent que le second, et seulement les citations
directes.

Un fait est UTILISÉ s'il est atteint depuis le catalogue par l'une de ces voies :

- citation directe dans une aide (`fact`, `levier`, `applies_if.fact` d'une
  condition ou de l'aide entière), à n'importe quelle profondeur ;
- porte d'un fait utilisé (`pertinent_si.fact`) : le moteur la pose avant sa
  dépendante ;
- source d'une déduction dont la cible est utilisée (`FAITS_DEDUITS_DES_FAITS`).

Les deux dernières voies se suivent jusqu'au point fixe. Tout le reste est
orphelin : le moteur ne pose jamais la question.

Deux nuances, rendues à part plutôt que tranchées :

- un orphelin dont la clé apparaît quand même dans un YAML d'aide (commentaire,
  texte) : le balayage permissif du lint le compterait comme référencé ;
- un orphelin dont la clé apparaît dans le code (backend, frontend) : il peut
  être lu ailleurs que par le moteur, à vérifier avant de le retirer.

Le script ne modifie RIEN.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lint_aides_data import faits_references_dans

from aides_schema import AIDES_DIR, load_all_aides, load_facts, load_pending_facts
from eligibility_engine import FAITS_DEDUITS_DES_FAITS

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
# Où chercher une lecture du fait hors moteur. Les tests sont exclus : un test
# qui cite un fait ne l'utilise pas.
DOSSIERS_CODE = [
    (BACKEND_DIR, "*.py"),
    (REPO_DIR / "frontend" / "src", "*.ts"),
    (REPO_DIR / "frontend" / "src", "*.tsx"),
]
EXCLUS_CODE = ("/tests/", "/__tests__/", "/.venv/", "/node_modules/", "/data/")


def _cles_citees(noeud: Any) -> set[str]:
    """Toutes les valeurs de `fact` et de `levier` (chaînes) d'une aide sérialisée."""
    trouvees: set[str] = set()
    if isinstance(noeud, dict):
        for cle, valeur in noeud.items():
            if cle in ("fact", "levier") and isinstance(valeur, str):
                trouvees.add(valeur)
            else:
                trouvees |= _cles_citees(valeur)
    elif isinstance(noeud, list):
        for element in noeud:
            trouvees |= _cles_citees(element)
    return trouvees


def citations_directes(aides: dict) -> dict[str, list[str]]:
    """fait → slugs des aides qui le citent."""
    par_fait: dict[str, list[str]] = {}
    for slug, aide in sorted(aides.items()):
        for cle in _cles_citees(aide.model_dump(mode="python")):
            par_fait.setdefault(cle, []).append(slug)
    return par_fait


def fermeture(racines: set[str], faits: dict) -> tuple[set[str], dict[str, str]]:
    """Ajoute portes et sources de déduction jusqu'au point fixe.

    Rend l'ensemble atteint et, pour chaque fait gagné par rebond, la voie
    qui l'a fait entrer (lisible dans le rapport).
    """
    atteints = set(racines)
    voies: dict[str, str] = {}
    a_traiter = list(racines)
    while a_traiter:
        cle = a_traiter.pop()
        suivants: list[tuple[str, str]] = []
        definition = faits.get(cle)
        if definition is not None and definition.pertinent_si and definition.pertinent_si.fact:
            suivants.append((definition.pertinent_si.fact, f"porte de {cle}"))
        if cle in FAITS_DEDUITS_DES_FAITS:
            source, _ = FAITS_DEDUITS_DES_FAITS[cle]
            suivants.append((source, f"source de la déduction de {cle}"))
        for suivant, voie in suivants:
            if suivant not in atteints:
                atteints.add(suivant)
                voies[suivant] = voie
                a_traiter.append(suivant)
    return atteints, voies


def mentions_dans_le_code(cles: list[str]) -> dict[str, list[str]]:
    """clé → fichiers de code (relatifs au dépôt) qui la citent entre guillemets."""
    if not cles:
        return {}
    alternatives = "|".join(map(re.escape, cles))
    motif = re.compile(rf"""['"`]({alternatives})['"`]""")
    mentions: dict[str, list[str]] = {}
    for dossier, glob in DOSSIERS_CODE:
        if not dossier.is_dir():
            continue
        for chemin in dossier.rglob(glob):
            posix = chemin.as_posix()
            if any(exclu in posix for exclu in EXCLUS_CODE):
                continue
            texte = chemin.read_text(encoding="utf-8", errors="replace")
            for cle in set(motif.findall(texte)):
                mentions.setdefault(cle, []).append(str(chemin.relative_to(REPO_DIR)))
    return mentions


def analyser() -> dict[str, Any]:
    faits = load_facts()
    pending = load_pending_facts()
    aides = load_all_aides(AIDES_DIR)
    tous = {**faits, **pending}

    directes = citations_directes(aides)
    atteints, voies = fermeture(set(directes), tous)
    textuelles = faits_references_dans(AIDES_DIR)

    def orphelins_de(ensemble: dict) -> list[str]:
        return sorted(set(ensemble) - atteints)

    orph_faits = orphelins_de(faits)
    orph_pending = orphelins_de(pending)
    code = mentions_dans_le_code(orph_faits + orph_pending)

    def detail(cle: str) -> dict[str, Any]:
        return {
            "cle": cle,
            "scope": tous[cle].scope,
            "type": tous[cle].type,
            "mention_textuelle_aides": cle in textuelles,
            "code": sorted(code.get(cle, [])),
        }

    return {
        "aides": len(aides),
        "faits": len(faits),
        "pending": len(pending),
        "cites_directement": len(set(directes) & set(tous)),
        "atteints_par_rebond": {c: v for c, v in sorted(voies.items()) if c in tous},
        # Cités par une aide mais absents des deux ontologies : l'inverse d'un
        # orphelin, que le lint signale déjà, repris ici pour mémoire.
        "cites_inconnus": sorted(set(directes) - set(tous)),
        "orphelins_facts": [detail(c) for c in orph_faits],
        "orphelins_pending": [detail(c) for c in orph_pending],
    }


def _rendu_texte(r: dict[str, Any]) -> str:
    lignes = [
        f"Catalogue : {r['aides']} aides — ontologie : {r['faits']} faits validés, "
        f"{r['pending']} proposés",
        f"Cités directement par une aide : {r['cites_directement']}",
        f"Atteints seulement par rebond : {len(r['atteints_par_rebond'])}",
    ]
    for cle, voie in r["atteints_par_rebond"].items():
        lignes.append(f"  {cle:<48} {voie}")

    for titre, liste in (
        ("facts.yaml", r["orphelins_facts"]),
        ("facts_pending.yaml", r["orphelins_pending"]),
    ):
        lignes += ["", f"Orphelins de {titre} : {len(liste)}"]
        for o in liste:
            notes = []
            if o["mention_textuelle_aides"]:
                notes.append("mentionné en texte dans une aide")
            if o["code"]:
                notes.append("cité dans le code : " + ", ".join(o["code"]))
            suffixe = f"  ({' ; '.join(notes)})" if notes else ""
            lignes.append(f"  {o['cle']:<48} {o['scope']:<12} {o['type']:<10}{suffixe}")

    if r["cites_inconnus"]:
        lignes += [
            "",
            f"Pour mémoire, cités par une aide mais absents de l'ontologie : "
            f"{len(r['cites_inconnus'])}",
        ]
        lignes += [f"  {c}" for c in r["cites_inconnus"]]
    return "\n".join(lignes)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="sortie JSON")
    args = ap.parse_args(argv)
    rapport = analyser()
    print(json.dumps(rapport, ensure_ascii=False, indent=2) if args.json else _rendu_texte(rapport))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
