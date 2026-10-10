"""Analyse de l'échantillon de contrôle du tri sur titre (CS1).

Commande, depuis backend/ :

    uv run python scripts/mesures/tri_titre_echantillon_analyse.py

Entrées, dans backend/data/reviews/logs/refonte/ :

- 2026-10-10-tri-titre-1/echantillon_controle.jsonl (100 URL écartées au tri sur
  titre) et leurres.jsonl (50 URL gardées au même tri), avec le verdict du tri
  que les juges n'ont pas vu ;
- 2026-10-10-tri-titre-echantillon-1/telechargements.jsonl (statut de chaque
  téléchargement) et etiquettes.json (jugements à l'aveugle de sous-agents
  Claude : premier juge, second juge sur les pages retenues ou indéterminées et
  30 % des autres, arbitre sur les désaccords).

Sortie : 2026-10-10-tri-titre-echantillon-1/analyse.json et analyse.txt (taux
avec intervalle de Wilson à 95 %, estimation pondérée par strate, accord entre
juges, liste des pertes candidates avec leur recherche dans le catalogue et la
file). Aucun appel réseau ni de modèle ; rien n'est écrit hors de ce dossier.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

BACKEND = Path(__file__).resolve().parents[2]
LOGS = BACKEND / "data" / "reviews" / "logs" / "refonte"
TIRAGE = LOGS / "2026-10-10-tri-titre-1"
ECH = LOGS / "2026-10-10-tri-titre-echantillon-1"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    demi = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - demi), min(1.0, centre + demi))


def taux(k: int, n: int) -> str:
    bas, haut = wilson(k, n)
    return f"{k}/{n} = {100 * k / n:.1f} % [{100 * bas:.1f} ; {100 * haut:.1f}]" if n else "0/0"


def cle_url(url: str) -> str:
    url = re.sub(r"^https?://(www\.)?", "", url.strip().lower())
    return url.split("#")[0].rstrip("/")


def mots(texte: str) -> set[str]:
    return {m for m in re.findall(r"[a-zà-ÿ0-9]{4,}", texte.lower())}


def lire_jsonl(chemin: Path) -> list[dict]:
    return [json.loads(ligne) for ligne in chemin.read_text(encoding="utf-8").splitlines() if ligne]


def main() -> int:
    ecartees = lire_jsonl(TIRAGE / "echantillon_controle.jsonl")
    gardees = lire_jsonl(TIRAGE / "leurres.jsonl")
    telech = {r["id_aveugle"]: r for r in lire_jsonl(ECH / "telechargements.jsonl")}
    etiquettes = {
        e["id"]: e for e in json.loads((ECH / "etiquettes.json").read_text(encoding="utf-8"))
    }

    # Le catalogue et la file, pour reconnaître une perte qui serait un doublon.
    catalogue: dict[str, str] = {}
    noms: dict[str, set[str]] = {}
    for f in sorted((BACKEND / "data" / "aides").glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        src = data.get("source") or {}
        for champ in ("url_officielle", "formulaire_url"):
            if src.get(champ):
                catalogue[cle_url(src[champ])] = f.stem
        noms[f.stem] = mots(f"{data.get('nom', '')} {data.get('nom_court', '')}")
    file_taches = yaml.safe_load(
        (BACKEND / "data" / "prospection" / "file-attente.yaml").read_text(encoding="utf-8")
    )
    taches = (
        file_taches.get("taches", file_taches) if isinstance(file_taches, dict) else file_taches
    )
    file_urls: dict[str, dict] = {}
    for t in taches if isinstance(taches, list) else []:
        if isinstance(t, dict) and t.get("url"):
            file_urls[cle_url(t["url"])] = t

    def issue(entree: dict) -> str:
        e = etiquettes.get(entree["id_aveugle"])
        if e is None:
            t = telech[entree["id_aveugle"]]
            return "sans_texte" if t["longueur"] == 0 else "sans_jugement"
        return e["verdict_final"] or "desaccord_non_arbitre"

    lignes: list[str] = []
    resultat: dict = {}
    for nom, groupe in (("ecartees_au_tri", ecartees), ("gardees_au_tri", gardees)):
        issues = Counter(issue(x) for x in groupe)
        avec_texte = [x for x in groupe if issue(x) in ("retenue", "indeterminee", "ecartee")]
        n = len(avec_texte)
        k_ret = sum(issue(x) == "retenue" for x in avec_texte)
        k_ind = sum(issue(x) == "indeterminee" for x in avec_texte)
        poids_tot = sum(x.get("poids", 1.0) for x in avec_texte)
        pond_ret = sum(x.get("poids", 1.0) for x in avec_texte if issue(x) == "retenue") / poids_tot
        pond_ri = (
            sum(x.get("poids", 1.0) for x in avec_texte if issue(x) in ("retenue", "indeterminee"))
            / poids_tot
        )
        resultat[nom] = {
            "issues": dict(issues),
            "avec_texte": n,
            "retenues": k_ret,
            "indeterminees": k_ind,
            "taux_retenues": taux(k_ret, n),
            "taux_retenues_ou_indeterminees": taux(k_ret + k_ind, n),
            "pondere_retenues": round(pond_ret, 4),
            "pondere_retenues_ou_indeterminees": round(pond_ri, 4),
        }
        lignes += [
            f"== {nom} ({len(groupe)} URL)",
            f"issues : {dict(issues)}",
            f"retenues : {taux(k_ret, n)} ; pondéré par strate : {100 * pond_ret:.1f} %",
            f"retenues ou indéterminées : {taux(k_ret + k_ind, n)} ; pondéré : {100 * pond_ri:.1f} %",
        ]

    # Par version du modèle de tri : le coût au jeton désigne ds-v41 pour les
    # vagues du 2026-09-18 au 2026-09-29, or-glm pour le 2026-10-04 et avant le 2026-09-12.
    par_vague = Counter()
    for x in ecartees:
        par_vague[(x["balayage"], issue(x))] += 1
    resultat["ecartees_par_balayage"] = {f"{b} {i}": n for (b, i), n in sorted(par_vague.items())}
    lignes.append(f"écartées par balayage et issue : {resultat['ecartees_par_balayage']}")

    # Accord entre juges sur les pages contrôlées.
    controlees = [e for e in etiquettes.values() if e.get("controle")]
    accord = sum(e["verdict1"] == e["verdict2"] for e in controlees)
    resultat["accord_juges"] = taux(accord, len(controlees))
    lignes.append(f"accord des deux juges sur le verdict : {resultat['accord_juges']}")
    desaccords = [
        {
            "id": e["id"],
            "juge1": e["verdict1"],
            "juge2": e["verdict2"],
            "arbitre": e["verdict_arbitre"],
        }
        for e in controlees
        if e["verdict1"] != e["verdict2"]
    ]
    resultat["desaccords"] = desaccords
    lignes.append(f"désaccords : {desaccords}")

    # Pertes candidates : écartées au tri, retenues ou indéterminées par les juges.
    pertes = []
    for x in ecartees:
        if issue(x) not in ("retenue", "indeterminee"):
            continue
        t = telech[x["id_aveugle"]]
        e = etiquettes[x["id_aveugle"]]["final"]
        cles = {cle_url(x["url"]), cle_url(t["url_finale"])}
        au_catalogue = sorted({catalogue[c] for c in cles if c in catalogue})
        en_file = [
            {"slug": file_urls[c].get("slug"), "statut": file_urls[c].get("statut")}
            for c in cles
            if c in file_urls
        ]
        titre_mots = mots(x["titre"])
        proches = sorted(
            (
                (len(titre_mots & m) / max(1, len(titre_mots | m)), s)
                for s, m in noms.items()
                if titre_mots & m
            ),
            reverse=True,
        )[:3]
        pertes.append(
            {
                "id_aveugle": x["id_aveugle"],
                "issue": issue(x),
                "titre": x["titre"],
                "url": x["url"],
                "territoire": x["territoire"],
                "balayage": x["balayage"],
                "motif_tri": x.get("motif_tri"),
                "juge": {
                    k: e[k]
                    for k in ("dispositif", "destinataire", "objet", "categorie_ecart", "confiance")
                },
                "justification": e["justification"],
                "extrait": e["extrait"],
                "au_catalogue_par_url": au_catalogue,
                "dans_la_file_par_url": en_file,
                "aides_au_nom_proche": [{"slug": s, "jaccard": round(j, 2)} for j, s in proches],
            }
        )
    resultat["pertes_candidates"] = pertes
    lignes.append(f"pertes candidates (écartées au tri, retenues ou indéterminées) : {len(pertes)}")
    for p in pertes:
        lignes.append(
            f"- {p['id_aveugle']} [{p['issue']}] {p['territoire']} {p['balayage']} « {p['titre']} » {p['url']}\n"
            f"  tri : {p['motif_tri']}\n  juge : {p['juge']} ; {p['justification']}\n"
            f"  catalogue par URL : {p['au_catalogue_par_url']} ; file : {p['dans_la_file_par_url']} ; "
            f"noms proches : {p['aides_au_nom_proche']}"
        )

    (ECH / "analyse.json").write_text(
        json.dumps(resultat, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (ECH / "analyse.txt").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print("\n".join(lignes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
