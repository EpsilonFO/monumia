"""Calibration de `F3-famille-fait` sur la revue humaine des faits proposés du 2026-09-17.

Commande, depuis backend/ :

    uv run --no-sync --env-file .env.local python -m catalogue.mesures.famille_fait \\
        --jugements <copie de data/catalogue/coherence/jugements.jsonl>

Le 2026-09-17, Félix a arbitré d'un bloc les 471 faits de `facts_pending.yaml`
(commit 97d79b1a) : 370 approuvés tels quels, les autres fusionnés dans un fait
existant, la table « fait supprimé → fait conservé » en tête de la section
« Faits approuvés le 2026-09-17 » de `facts.yaml`. C'est un jeu étiqueté par un
humain, sans étiquetage à refaire :

  - POSITIF : un fait proposé fusionné dans un fait qui existait déjà au commit
    parent (approuvé ou proposé). Jev doit le désigner. Les fusions vers un fait
    créé ce jour-là (renommages, faits neufs de synthèse) sont hors d'atteinte
    et écartées.
  - NÉGATIF : un fait proposé approuvé sous sa clé. Jev doit répondre « aucun ».

Chaque fait est soumis comme `espace.famille_du_fait` le fait à l'ingestion :
les 5 plus proches dans l'espace (consigne fait vers fait), puis la question
`QUESTIONS_FAIT` de Jev, dont on garde la distribution brute pour balayer le
seuil. L'ontologie de chaque requête est celle du commit parent, sans le fait
lui-même et sans aucun des faits fusionnés ce jour-là : sinon un fait approuvé
retrouverait le doublon qu'on a fusionné DANS lui, et compterait comme une
fausse alerte alors qu'il est juste.

Deux décisions automatiques en dépendent, et deux erreurs :

  - au-dessus du seuil, l'agent réutilise d'office le fait désigné. Erreur :
    un fait réutilisé à tort (un négatif désigné, ou un positif rattaché au
    mauvais fait) : la condition est posée sur la mauvaise question ;
  - sinon, le fait neuf est accepté sans case (`faits_neufs: auto`). Erreur :
    un doublon qui passe (budget `doublons_faits` du registre).

Sortie : un dossier neuf sous data/reviews/logs/refonte/ (hors git),
`mesure.json` et `requetes.jsonl`.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from aides_schema import FactDef, load_facts, load_pending_facts
from catalogue import coherence as co
from catalogue.espace import AUCUN, CANDIDATS_FAIT, _decrire_fait, questions_fait
from catalogue.mesures.jeu_e import _dossier_neuf
from catalogue.plongements import (
    CONSIGNE_FAIT_VERS_FAIT,
    Plongeur,
    avec_consigne,
    plus_proches,
    texte_fait,
)

REVUE = "97d79b1a"
SEUILS = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)


def _au_commit(rev: str, fichier: str) -> dict[str, FactDef]:
    texte = subprocess.run(
        ["git", "show", f"{rev}:backend/data/{fichier}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(texte)
    chemin = Path(f.name)
    return load_pending_facts(chemin) if "pending" in fichier else load_facts(chemin)


def _fusions(rev: str) -> dict[str, str]:
    texte = subprocess.run(
        ["git", "show", f"{rev}:backend/data/facts.yaml"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    debut = texte.index("Fusions appliquées (fait supprimé")
    fin = texte.index("\n\n", debut)
    return dict(re.findall(r"^#\s+([a-z0-9_]+) → ([a-z0-9_.]+)", texte[debut:fin], re.M))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jugements", type=Path, required=True, help="copie de jugements.jsonl")
    parser.add_argument("--candidats", type=int, default=CANDIDATS_FAIT)
    args = parser.parse_args()
    questions = questions_fait(args.candidats)

    facts = _au_commit(f"{REVUE}^", "facts.yaml")
    pending = _au_commit(f"{REVUE}^", "facts_pending.yaml")
    apres = _au_commit(REVUE, "facts.yaml")
    fusions = _fusions(REVUE)
    tous = {**facts, **pending}

    fusionnes = {k for k in fusions if k in pending}
    positifs = {
        k: fusions[k] for k in fusionnes if fusions[k] in tous and fusions[k] not in fusions
    }
    negatifs = [k for k in pending if k not in fusions and k in apres]
    hors = sorted(fusionnes - set(positifs))
    print(
        f"{len(pending)} proposés : {len(positifs)} positifs, {len(negatifs)} négatifs, "
        f"{len(hors)} fusions hors d'atteinte, {len(pending) - len(fusionnes) - len(negatifs)} autres"
    )

    ontologie = {k: v for k, v in tous.items() if k not in fusionnes}
    plongeur = Plongeur()
    juge = co.Juge(fichier=args.jugements)
    requetes = [(k, positifs.get(k)) for k in sorted(positifs)] + [(k, None) for k in negatifs]

    cles = list(ontologie)
    corpus = plongeur.vecteurs([texte_fait(k, ontologie[k]) for k in cles])
    requetes_vec = plongeur.vecteurs(
        [avec_consigne(CONSIGNE_FAIT_VERS_FAIT, texte_fait(k, tous[k])) for k, _ in requetes]
    )
    rangs_tous, _ = plus_proches(requetes_vec, corpus, 21)

    def une(n: int) -> dict[str, Any]:
        cle, cible = requetes[n]
        voisins = [cles[int(j)] for j in rangs_tous[n] if cles[int(j)] != cle][:20]
        candidats = voisins[: args.candidats]
        etat = {
            "fait_propose": _decrire_fait(cle, tous[cle]),
            "candidats": {
                f"c{n}": _decrire_fait(k, ontologie[k]) for n, k in enumerate(candidats, 1)
            },
        }
        d = juge.juger(etat, questions, "famille")
        choisi, p = (None, 0.0)
        if d is not None:
            option, p = max(d.items(), key=lambda kv: kv[1])
            if option != AUCUN and option.startswith("c") and int(option[1:]) <= len(candidats):
                choisi = candidats[int(option[1:]) - 1]
        return {
            "cle": cle,
            "cible": cible,
            "rang_cible": voisins.index(cible) + 1 if cible in voisins else None,
            "candidats": candidats,
            "choisi": choisi,
            "p": round(p, 4),
            "p_aucun": round((d or {}).get(AUCUN, 0.0), 4),
            "panne": d is None,
        }

    with ThreadPoolExecutor(co.PARALLELISME_JEV) as pool:
        lignes = list(pool.map(une, range(len(requetes))))

    pos = [x for x in lignes if x["cible"] and not x["panne"]]
    neg = [x for x in lignes if not x["cible"] and not x["panne"]]
    resultats: dict[str, Any] = {
        "positifs": len(pos),
        "negatifs": len(neg),
        "pannes": sum(x["panne"] for x in lignes),
        "hors_atteinte": hors,
        "rappel_recherche": {
            f"k{k}": sum(1 for x in pos if x["rang_cible"] and x["rang_cible"] <= k)
            for k in (1, 5, 10, 20)
        },
        "candidats": args.candidats,
        "jev": {"appels": juge.appels, "cout_usd": round(juge.cout_usd, 4)},
        "seuils": {},
    }
    for s in SEUILS:

        def reutilise(x: dict[str, Any], s: float = s) -> bool:
            return x["choisi"] is not None and x["p"] >= s

        juste = sum(1 for x in pos if reutilise(x) and x["choisi"] == x["cible"])
        mauvais_fait = sum(1 for x in pos if reutilise(x) and x["choisi"] != x["cible"])
        doublons = sum(1 for x in pos if not reutilise(x))
        fausses = sum(1 for x in neg if reutilise(x))
        acceptes = doublons + len(neg) - fausses
        resultats["seuils"][str(s)] = {
            "positifs_rattaches_au_bon_fait": juste,
            "positifs_rattaches_au_mauvais_fait": mauvais_fait,
            "doublons_qui_passent": doublons,
            "negatifs_rattaches_a_tort": fausses,
            "faits_neufs_acceptes": acceptes,
            "part_de_doublons_parmi_acceptes": round(doublons / acceptes, 4) if acceptes else None,
            "part_de_reutilisations_fausses": round(
                (mauvais_fait + fausses) / max(1, juste + mauvais_fait + fausses), 4
            ),
        }

    dossier = _dossier_neuf("famille-fait")
    (dossier / "mesure.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=2))
    with (dossier / "requetes.jsonl").open("w", encoding="utf-8") as f:
        for x in lignes:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    print(json.dumps(resultats, ensure_ascii=False, indent=2))
    print(f"Sorties : {dossier}")
    juge.fermer()
    plongeur.fermer()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
