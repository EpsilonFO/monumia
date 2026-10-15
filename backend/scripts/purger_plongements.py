"""Purge du cache des vecteurs : ne garde que ce que le catalogue actuel réclame.

Depuis backend/ :

    uv run python scripts/purger_plongements.py            # simulation, ne touche à rien
    uv run python scripts/purger_plongements.py --appliquer

`plongements.sqlite` est un cache à ajout seul : chaque texte que l'agent
d'ingestion soumet à `conditions_voisines` y laisse un vecteur, retenu ou non.
Les brouillons écartés ou reformulés s'y accumulent (mesuré le 2026-10-15 : trois
textes plongés sur quatre pendant une veille n'étaient plus dans le catalogue à
la fin du run). Ces orphelins ne faussent aucune famille, qui ne lit que les
textes des YAML actuels, mais ils font grossir le fichier.

Sont gardés : les conditions des aides, les faits (validés et en attente), et
les requêtes avec consigne sur ces mêmes textes. Les requêtes par mots-clés des
mesures ne peuvent pas se reconstituer : elles se recalculent si on rejoue une
mesure.

Ne jamais lancer pendant un run de la veille ou de l'ingestion : les agents
écrivent dans la même base.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from aides_schema import load_facts, load_pending_facts  # noqa: E402
from catalogue import coherence as co  # noqa: E402
from catalogue import plongements as pl  # noqa: E402
from catalogue import registre as registre_mod  # noqa: E402

CONSIGNES = (
    pl.CONSIGNE_CONDITION_VERS_FAIT,
    pl.CONSIGNE_MOTS_VERS_FAIT,
    pl.CONSIGNE_FAIT_VERS_FAIT,
)


def cles_a_garder() -> set[str]:
    modele = registre_mod.charger().modele(pl.ROLE).nom
    empreinte = lambda t: pl._empreinte(modele, t)  # noqa: E731

    conditions = {ln.texte for ln in co.charger()}
    faits = {**load_facts(), **load_pending_facts()}
    textes_faits = {pl.texte_fait(k, f) for k, f in faits.items()}

    gardees = {empreinte(t) for t in conditions | textes_faits}
    gardees |= {empreinte(pl.avec_consigne(c, t)) for c in CONSIGNES for t in conditions}
    gardees |= {empreinte(pl.avec_consigne(pl.CONSIGNE_FAIT_VERS_FAIT, t)) for t in textes_faits}
    return gardees


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--appliquer", action="store_true", help="supprimer vraiment")
    args = parser.parse_args()

    base = pl.CACHE
    gardees = cles_a_garder()
    avec_ro = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    existantes = {c for (c,) in avec_ro.execute("select cle from vecteurs")}
    avec_ro.close()
    a_supprimer = existantes - gardees

    taille = base.stat().st_size
    print(f"cache : {len(existantes)} vecteurs, {taille / 1e6:.0f} Mo")
    print(f"à garder : {len(existantes & gardees)} (réclamés : {len(gardees)})")
    print(f"à supprimer : {len(a_supprimer)}")
    if not args.appliquer:
        print("Simulation : relancer avec --appliquer pour supprimer.")
        return 0

    sauvegarde = base.with_suffix(".sqlite.bak")
    if sauvegarde.exists():
        print(f"{sauvegarde} existe déjà : je ne l'écrase pas. Déplacez-la d'abord.")
        return 1
    shutil.copy2(base, sauvegarde)
    print(f"copie de sécurité : {sauvegarde}")

    db = sqlite3.connect(base, timeout=60)
    with db:
        liste = list(a_supprimer)
        for i in range(0, len(liste), 500):
            morceau = liste[i : i + 500]
            db.execute(
                f"delete from vecteurs where cle in ({','.join('?' * len(morceau))})", morceau
            )
    db.execute("vacuum")
    restant = db.execute("select count(*) from vecteurs").fetchone()[0]
    db.close()
    print(f"après : {restant} vecteurs, {base.stat().st_size / 1e6:.0f} Mo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
