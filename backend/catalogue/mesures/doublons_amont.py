"""Les doublons de faits que la recherche par embedding aurait évités en amont.

Commande, depuis backend/ :

    uv run --no-sync --env-file .env.local python -m catalogue.mesures.doublons_amont

Suite de `famille_fait.py`, sur le même jeu : les 70 faits proposés que Félix a
fusionnés dans un fait existant le 2026-09-17 (commit 97d79b1a). Un doublon
naît quand l'agent cherche un fait pour une condition, ne voit pas le jumeau,
et en propose un. La question : la recherche d'aujourd'hui (`chercher_faits`
par embedding) lui aurait-elle montré le jumeau, là où celle de l'époque
(`rechercher`, par mots) ne le montrait pas ?

Pour chaque doublon X fusionné dans Y :

  - la condition : celle de l'aide qui a proposé X (en-tête « --- slug --- »
    de `facts_pending.yaml`) et qui cite X ; à défaut, toutes celles qui le citent ;
  - l'ontologie : celle que voyait l'agent à ce moment, `facts.yaml` et les faits
    proposés AVANT X (ordre du fichier, en ajout seul). Un jumeau proposé après
    X n'existait pas encore : le doublon n'était pas évitable par la recherche,
    il est compté à part ;
  - le jumeau est vu si Y, ou un autre fait fusionné dans Y qui existait déjà,
    est parmi les 15 faits que montre chaque recherche (`LIMITE_DEFAUT`).

Requête : le texte de la condition, pour les deux recherches. L'agent tape des
mots-clés, qu'on n'a pas gardés ; c'est l'approximation de la mesure du
2026-10-14 (`2026-10-14-rappel-faits-plongement.md`).

Sortie : un dossier neuf sous data/reviews/logs/refonte/ (hors git),
`mesure.json` et `doublons.jsonl`. Seul appel réseau : le modèle d'embedding.
"""

from __future__ import annotations

import json
import re
import subprocess
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

import yaml
from ingestion.faits import LIMITE_DEFAUT, _texte_indexe
from veille_text import normalize

from aides_schema import FactDef
from catalogue.mesures.famille_fait import REVUE, _au_commit, _fusions
from catalogue.mesures.jeu_e import _dossier_neuf
from catalogue.plongements import (
    CONSIGNE_MOTS_VERS_FAIT,
    Plongeur,
    avec_consigne,
    plus_proches,
    texte_fait,
)

BACKEND = Path(__file__).resolve().parents[2]
F3 = (
    BACKEND
    / "data"
    / "reviews"
    / "logs"
    / "refonte"
    / "2026-10-14-famille-fait-2"
    / "requetes.jsonl"
)


def _ordre_et_auteurs(rev: str) -> tuple[list[str], dict[str, str]]:
    """Les clés de `facts_pending.yaml` dans l'ordre du fichier, et l'aide qui a proposé chacune."""
    texte = subprocess.run(
        ["git", "show", f"{rev}:backend/data/facts_pending.yaml"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    ordre: list[str] = []
    auteurs: dict[str, str] = {}
    slug = ""
    for ligne in texte.splitlines():
        if m := re.match(r"^# --- (\S+) ---", ligne):
            slug = m.group(1)
        elif m := re.match(r"^([a-z0-9_]+):\s*$", ligne):
            ordre.append(m.group(1))
            auteurs[m.group(1)] = slug
    return ordre, auteurs


def _aides(rev: str, dossier: Path) -> dict[str, Any]:
    archive = subprocess.run(
        ["git", "archive", rev, "data/aides"], cwd=BACKEND, capture_output=True, check=True
    ).stdout
    with tarfile.open(fileobj=BytesIO(archive)) as tar:
        tar.extractall(dossier, filter="data")
    # En YAML brut : une aide de septembre ne passe plus forcément le schéma
    # d'aujourd'hui, et seuls le texte et le fait des conditions servent ici.
    return {
        p.stem: yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for p in sorted((dossier / "data" / "aides").glob("*.yaml"))
    }


def _cite(c: dict[str, Any], cle: str) -> bool:
    return c.get("fact") == cle or f'"{cle}"' in json.dumps(c.get("applies_if") or {})


def _lexical(texte: str, ontologie: dict[str, FactDef]) -> list[str]:
    """`rechercher` telle quelle, le texte de la condition pour mots-clés."""
    jetons = [t for t in normalize(texte.replace("_", " ")).split() if t]
    scores = []
    for cle, fait in ontologie.items():
        indexe = _texte_indexe(cle, fait)
        score = sum(1 for t in jetons if t in indexe)
        if score:
            scores.append((score, cle))
    scores.sort(key=lambda s: (-s[0], s[1]))
    return [cle for _s, cle in scores[:LIMITE_DEFAUT]]


def main() -> int:
    facts = _au_commit(f"{REVUE}^", "facts.yaml")
    pending = _au_commit(f"{REVUE}^", "facts_pending.yaml")
    tous = {**facts, **pending}
    fusions = _fusions(REVUE)
    positifs = {k: v for k, v in fusions.items() if k in pending and v in tous and v not in fusions}
    ordre, auteurs = _ordre_et_auteurs(f"{REVUE}^")
    rang = {k: i for i, k in enumerate(ordre)}
    with tempfile.TemporaryDirectory() as tmp:
        aides = _aides(f"{REVUE}^", Path(tmp))

    f3 = {}
    if F3.exists():
        for ligne in F3.read_text(encoding="utf-8").splitlines():
            x = json.loads(ligne)
            f3[x["cle"]] = x["choisi"] == x["cible"] and x["p"] >= 0.3

    plongeur = Plongeur()
    cles_tous = list(tous)
    corpus = plongeur.vecteurs([texte_fait(k, tous[k]) for k in cles_tous])

    doublons = []

    def date(k: str) -> int:
        """L'ordre d'arrivée : les faits approuvés d'abord, puis l'ordre du fichier."""
        return -1 if k in facts else rang.get(k, 10**6)

    for supprime, garde in sorted(positifs.items()):
        # Le cluster : le fait gardé et tous ceux que Félix y a fusionnés. Le
        # doublon est celui des deux qui est arrivé APRÈS l'autre : quand le fait
        # gardé est le plus récent, c'est lui qui a refait le fait supprimé.
        cluster = {garde} | {k for k, v in fusions.items() if v == garde}
        x = max((supprime, garde), key=date)
        visibles = {k for k in tous if date(k) < date(x)}
        jumeaux = (cluster - {x}) & visibles
        auteur = auteurs.get(x, "")
        conditions = [
            c
            for c in (aides[auteur].get("conditions") or [] if auteur in aides else [])
            if _cite(c, x)
        ]
        repli = not conditions
        if repli:
            conditions = [
                c for a in aides.values() for c in a.get("conditions") or [] if _cite(c, x)
            ]
        entree: dict[str, Any] = {
            "doublon": x,
            "jumeaux": sorted(jumeaux),
            "fait_garde_plus_recent": x == garde,
            "auteur": auteur,
            "conditions": len(conditions),
            "repli_toutes_conditions": repli,
            "f3_retrouve": f3.get(supprime),
        }
        if not jumeaux or not conditions:
            entree.update(vu_lexical=None, vu_plongement=None)
            doublons.append(entree)
            continue
        ontologie = {k: tous[k] for k in visibles if k != x}
        indices = [i for i, k in enumerate(cles_tous) if k in ontologie]
        sous_corpus = corpus[indices]
        textes = [" ".join(str(c.get("text") or "").split()) for c in conditions]
        requetes = plongeur.vecteurs([avec_consigne(CONSIGNE_MOTS_VERS_FAIT, t) for t in textes])
        rangs, _ = plus_proches(requetes, sous_corpus, LIMITE_DEFAUT)
        vu_plongement = [
            bool(jumeaux & {cles_tous[indices[int(j)]] for j in ligne}) for ligne in rangs
        ]
        vu_lexical = [bool(jumeaux & set(_lexical(t, ontologie))) for t in textes]
        # Le doublon est évité si la PREMIÈRE condition (celle qui l'a fait naître)
        # montre le jumeau ; les autres sont gardées pour information.
        entree.update(
            vu_lexical=vu_lexical[0],
            vu_plongement=vu_plongement[0],
            vu_lexical_une_condition=any(vu_lexical),
            vu_plongement_une_condition=any(vu_plongement),
            texte=textes[0][:200],
        )
        doublons.append(entree)

    jugeables = [d for d in doublons if d["vu_lexical"] is not None]
    nouveaux = [d for d in jugeables if d["vu_plongement"] and not d["vu_lexical"]]
    perdus = [d for d in jugeables if d["vu_lexical"] and not d["vu_plongement"]]
    restants = [d for d in doublons if d not in nouveaux]
    resultats = {
        "doublons": len(doublons),
        "fait_garde_plus_recent": sum(d["fait_garde_plus_recent"] for d in doublons),
        "sans_jumeau_anterieur": sum(1 for d in doublons if not d["jumeaux"]),
        "sans_condition": sum(1 for d in doublons if not d["conditions"]),
        "jugeables": len(jugeables),
        "vu_par_mots": sum(d["vu_lexical"] for d in jugeables),
        "vu_par_embedding": sum(d["vu_plongement"] for d in jugeables),
        "vus_seulement_par_embedding": len(nouveaux),
        "vus_seulement_par_mots": len(perdus),
        "restants_apres_amont": len(restants),
        "f3_retrouve_parmi_restants": sum(1 for d in restants if d["f3_retrouve"]),
        "f3_retrouve_parmi_tous": sum(1 for d in doublons if d["f3_retrouve"]),
        "cout_usd": round(plongeur.cout_usd, 4),
    }
    dossier = _dossier_neuf("doublons-amont")
    (dossier / "mesure.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=2))
    with (dossier / "doublons.jsonl").open("w", encoding="utf-8") as f:
        for d in doublons:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(json.dumps(resultats, ensure_ascii=False, indent=2))
    print(f"Sorties : {dossier}")
    plongeur.fermer()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
