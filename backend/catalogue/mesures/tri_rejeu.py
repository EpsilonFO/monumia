"""Le tri sur titre rejoué sous sa consigne actuelle sur l'échantillon CS1 (I0, mesure M2).

Commandes, depuis backend/ :

    uv run python -m catalogue.mesures.tri_rejeu rejouer
    uv run python -m catalogue.mesures.tri_rejeu analyser <dossier>

`rejouer` (payant, plafond 0,20 $) fait trier les 150 URL de CS1 (100 écartées
au tri lors des balayages de septembre et d'octobre, 50 gardées) par le tri de
production d'aujourd'hui : `prospection.tri.trier_lot`, consigne de HEAD
(`prompt_systeme`, doctrine des étapes 2 et 3 et aides déjà au catalogue du
territoire, `aides_existantes` sur le catalogue de HEAD), modèle `or-glm`, un lot
par territoire comme en production. Le titre vient de CS1, le contexte de la
collecte d'origine (`candidats.jsonl` des quatre checkouts) quand on le
retrouve. Sortie dans backend/data/reviews/logs/refonte/<date>-tri-rejeu-<n>/
(une exécution par dossier) : decisions.jsonl et resume.txt.

`analyser` lit toutes les exécutions passées en argument par leur dossier,
croise les décisions avec les étiquettes à l'aveugle de CS1, et écrit
analyse.txt dans le premier dossier : pertes rapportées aux pages à revoir et
aux pages à retenir, part écartée dans chaque groupe, accord avec le tri
d'origine et entre exécutions.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pipeline import llm
from prospection import tri
from prospection.collecte import Candidat
from prospection.territoires import aides_existantes, charger_territoires
from veille_collect import cle_url

from aides_schema import load_all_aides
from catalogue.mesures.jeu_e import RACINES, verdict
from catalogue.mesures.stats import wilson

BACKEND = Path(__file__).resolve().parents[2]
LOGS = BACKEND / "data" / "reviews" / "logs" / "refonte"
CS1_TIRAGE = LOGS / "2026-10-10-tri-titre-1"
CS1_ETIQUETTES = LOGS / "2026-10-10-tri-titre-echantillon-1" / "etiquettes.json"
MODELE_TRI = "or-glm"
PLAFOND_USD = 0.20
RESERVE_LOT_USD = 0.01


def _lire_jsonl(chemin: Path) -> list[dict[str, Any]]:
    return [json.loads(ligne) for ligne in chemin.read_text(encoding="utf-8").splitlines() if ligne]


def _contextes() -> dict[str, str]:
    """Le contexte vu à la collecte, par URL, dans tous les `candidats.jsonl`."""
    contextes: dict[str, str] = {}
    for racine in RACINES:
        for fichier in (racine / "data" / "prospection").glob("*/candidats.jsonl"):
            for ligne in fichier.read_text(encoding="utf-8").splitlines():
                if not ligne.strip():
                    continue
                c = json.loads(ligne)
                if c.get("extrait"):
                    contextes.setdefault(cle_url(c["url"]), c["extrait"])
    return contextes


def _cs1() -> list[dict[str, Any]]:
    cas = []
    for fichier, groupe in (
        ("echantillon_controle.jsonl", "ecartee_au_tri"),
        ("leurres.jsonl", "gardee_au_tri"),
    ):
        for r in _lire_jsonl(CS1_TIRAGE / fichier):
            cas.append({**r, "groupe": groupe})
    return cas


def rejouer(_: argparse.Namespace) -> int:
    llm.charger_env()
    client = llm.client_pour("tri", MODELE_TRI)
    territoires = charger_territoires()
    corpus = load_all_aides()
    contextes = _contextes()
    cas = _cs1()
    par_territoire: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in cas:
        par_territoire[c["territoire"]].append(c)

    date = dt.date.today().isoformat()
    n = 1
    while (LOGS / f"{date}-tri-rejeu-{n}").exists():
        n += 1
    sortie = LOGS / f"{date}-tri-rejeu-{n}"
    sortie.mkdir(parents=True)

    depense = 0.0
    sans_territoire: list[str] = []
    lignes: list[dict[str, Any]] = []
    with (sortie / "decisions.jsonl").open("w", encoding="utf-8") as f:
        for cle, groupe in sorted(par_territoire.items()):
            territoire = territoires.get(cle)
            if territoire is None:
                sans_territoire.append(cle)
                continue
            if depense + RESERVE_LOT_USD > PLAFOND_USD:
                print(f"plafond atteint avant le territoire {cle} ({depense:.4f} $)")
                break
            systeme = tri.prompt_systeme(territoire, aides_existantes(cle, territoire, corpus))
            candidats = [
                Candidat(
                    url=c["url"],
                    titre=c["titre"] or "",
                    extrait=contextes.get(cle_url(c["url"]), ""),
                )
                for c in groupe
            ]
            for lot in tri.lots(candidats):
                essai_lot = _trier(lot, client, systeme)
                depense += essai_lot["cout"]
                for t, c in zip(essai_lot["resultats"], lot, strict=True):
                    origine = next(x for x in groupe if x["url"] == c.url)
                    ligne = {
                        "id_aveugle": origine["id_aveugle"],
                        "groupe": origine["groupe"],
                        "territoire": cle,
                        "contexte_retrouve": bool(c.extrait),
                        "decision": t.decision,
                        "famille": t.famille,
                        "motif": t.motif,
                        "decision_origine": origine["verdict_tri"],
                    }
                    lignes.append(ligne)
                    f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    resume = [
        f"URL triées : {len(lignes)} ; dépense comptée : {depense:.4f} $ ; modèle {MODELE_TRI}",
        f"territoires inconnus de territoires.yaml : {sans_territoire}",
        f"contexte retrouvé : {sum(x['contexte_retrouve'] for x in lignes)}/{len(lignes)}",
        f"décisions : {dict(Counter((x['groupe'], x['decision']) for x in lignes))}",
    ]
    (sortie / "resume.txt").write_text("\n".join(resume) + "\n", encoding="utf-8")
    print(sortie)
    print("\n".join(resume))
    return 0


def _trier(lot: list[Candidat], client: Any, systeme: str) -> dict[str, Any]:
    """`tri.trier_lot`, avec le coût de l'appel relevé au passage."""
    compteur = llm.Compteur()
    resultats = tri.trier_lot(lot, client, systeme, compteur=compteur)
    cout = RESERVE_LOT_USD if compteur.cout_inconnu else compteur.cout_usd
    return {"resultats": resultats, "cout": cout}


def _sans_accent(texte: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texte.lower()) if unicodedata.category(c) != "Mn"
    )


def _au_catalogue(executions: list[dict[str, dict[str, Any]]]) -> dict[str, str]:
    """Les pages que le tri écarte en citant une aide qui est bel et bien au catalogue.

    Une page gardée lors d'un balayage de septembre a pu entrer au catalogue
    depuis : le tri d'aujourd'hui a raison de l'écarter (« déjà au catalogue »),
    ce n'est pas une perte. On ne le croit que si le slug cité existe dans
    `data/aides/`.
    """
    slugs = {f.stem for f in (BACKEND / "data" / "aides").glob("*.yaml")}
    trouves: dict[str, str] = {}
    for decisions in executions:
        for i, d in decisions.items():
            if d["decision"] != "ecarter" or i in trouves:
                continue
            motif = _sans_accent(d["motif"])
            cites = [slug for slug in slugs if slug in motif]
            if cites:
                trouves[i] = max(cites, key=len)
    return trouves


def analyser(args: argparse.Namespace) -> int:
    dossiers = [Path(d) for d in args.dossiers]
    etiquettes: dict[str, str] = {}
    for e in json.loads(CS1_ETIQUETTES.read_text(encoding="utf-8")):
        final = e.get("final")
        if final:
            etiquettes[e["id"]] = verdict(
                final["destinataire"], final["objet"], final.get("categorie_ecart")
            )
    executions = [
        {d["id_aveugle"]: d for d in _lire_jsonl(dossier / "decisions.jsonl")}
        for dossier in dossiers
    ]
    catalogue = _au_catalogue(executions)
    texte = [
        f"étiquettes : {dict(Counter(etiquettes.values()))}",
        f"pages écartées comme déjà au catalogue (slug vérifié) : {len(catalogue)} : {catalogue}",
    ]
    for dossier, decisions in zip(dossiers, executions, strict=True):
        ids = [i for i in decisions if i in etiquettes]
        a_revoir = [i for i in ids if etiquettes[i] in ("retenue", "indeterminee")]
        a_retenir = [i for i in ids if etiquettes[i] == "retenue"]
        hors_catalogue_revoir = [i for i in a_revoir if i not in catalogue]
        hors_catalogue_retenir = [i for i in a_retenir if i not in catalogue]

        def perdue(i: str, decisions: dict[str, dict[str, Any]] = decisions) -> bool:
            return decisions[i]["decision"] == "ecarter"

        texte.append(f"== {dossier.name}")
        for nom, liste in (
            ("pertes brutes, pages à revoir", a_revoir),
            ("pertes brutes, pages à retenir", a_retenir),
            ("pertes, pages à revoir hors catalogue", hors_catalogue_revoir),
            ("pertes, pages à retenir hors catalogue", hors_catalogue_retenir),
        ):
            perdues = [i for i in liste if perdue(i)]
            texte.append(f"  {nom} : {wilson(len(perdues), len(liste)).texte()} {perdues}")
        for groupe in ("ecartee_au_tri", "gardee_au_tri"):
            g = [i for i in ids if decisions[i]["groupe"] == groupe]
            ecartees = sum(perdue(i) for i in g)
            texte.append(f"  {groupe} : écartées aujourd'hui {wilson(ecartees, len(g)).texte()}")
            texte.append(f"    décisions : {dict(Counter(decisions[i]['decision'] for i in g))}")
            accord = sum(perdue(i) == (decisions[i]["decision_origine"] == "ecarter") for i in g)
            texte.append(f"    accord avec le tri d'origine (écarter ou non) : {accord}/{len(g)}")
        texte.append(
            f"  contexte retrouvé : {sum(d['contexte_retrouve'] for d in decisions.values())}/{len(decisions)}"
        )
    if len(executions) >= 2:
        a, b = executions[:2]
        communs = [i for i in a if i in b]
        accord = sum(a[i]["decision"] == b[i]["decision"] for i in communs)
        texte.append(
            f"accord des décisions entre les deux premières exécutions : {accord}/{len(communs)}"
        )
    (dossiers[0] / "analyse.txt").write_text("\n".join(texte) + "\n", encoding="utf-8")
    print("\n".join(texte))
    return 0


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sous = parseur.add_subparsers(dest="commande", required=True)
    sous.add_parser("rejouer").set_defaults(fonction=rejouer)
    p = sous.add_parser("analyser")
    p.add_argument("dossiers", nargs="+")
    p.set_defaults(fonction=analyser)
    args = parseur.parse_args()
    return args.fonction(args)


if __name__ == "__main__":
    raise SystemExit(main())
