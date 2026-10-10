"""Recompte adverse de la note `carte-et-decisions` (2026-10-10).

Commande (depuis backend/) :

    uv run python scripts/mesures/carte_et_decisions_recompte.py

Écrit dans data/reviews/logs/refonte/2026-10-10-carte-et-decisions-recompte-1/ :
  - recompte.json : chaque chiffre recompté, avec k, n et l'intervalle de Wilson ;
  - ancres_ambigues.tsv : les ancres du mesureur dont le motif a plusieurs lignes ;
  - citations_texte.tsv : chaque `fichier:ligne` cité dans le texte de la note,
    avec la ligne trouvée (vérification de présence seulement) ;
  - decisions_absentes.tsv : décisions du schéma absentes de l'inventaire, avec
    leur volume au catalogue (volume seulement : le catalogue n'est pas une vérité).

Lecture seule. Aucun appel réseau ni de modèle. Ne relance pas le script du
mesureur : relit ses sorties (pour recompter ses propres tableaux) et les
données brutes (pour recompter les volumes), avec un code écrit à part.
Importe `pipeline.etat` (fonctions pures, `charger` ne fait que lire) pour
appliquer la vraie règle de promotion au lieu d'une copie.
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

BACKEND = Path(__file__).resolve().parents[2]
RACINE = BACKEND.parent
DATA = BACKEND / "data"
LOGS = DATA / "reviews" / "logs"
MESUREUR = LOGS / "refonte" / "2026-10-10-carte-et-decisions-1"
SORTIE = LOGS / "refonte" / "2026-10-10-carte-et-decisions-recompte-1"
NOTE = RACINE / "docs" / "refonte-pipeline" / "notes" / "carte-et-decisions.md"
CHARGEUR = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

sys.path.insert(0, str(BACKEND / "scripts"))
from pipeline import etat  # noqa: E402


def wilson(k: int, n: int, z: float = 1.959964) -> list[float]:
    if n == 0:
        return [0.0, 1.0]
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    d = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(100 * max(0.0, c - d), 1), round(100 * min(1.0, c + d), 1)]


def taux(k: int, n: int) -> dict:
    return {"k": k, "n": n, "pct": round(100 * k / n, 1) if n else None, "ic95": wilson(k, n)}


def tsv(nom: str) -> list[dict[str, str]]:
    with open(MESUREUR / nom, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


R: dict = {}


# --- 1. Tableaux du mesureur : étages, décisions, décideurs, vérités ----------


def recompter_tableaux() -> None:
    et = tsv("etages.tsv")
    R["etages"] = {"n": len(et), "par_chaine": dict(Counter(e["chaine"] for e in et))}
    de = tsv("decisions.tsv")
    R["decisions"] = {
        "n": len(de),
        "ids_uniques": len({d["id"] for d in de}),
        "par_chaine": dict(Counter(d["chaine"] for d in de)),
    }

    # Premier décideur nommé, par ma propre lecture de la cellule.
    def premier(cellule: str) -> str:
        c = cellule.lower()
        pos = {
            "felix": min(
                [i for i in (c.find("félix"), c.find("claude"), c.find("humain")) if i >= 0]
                or [10**6]
            ),
            "code": c.find("code") if c.find("code") >= 0 else 10**6,
            "llm": c.find("llm") if c.find("llm") >= 0 else 10**6,
            "jev": c.find("jev") if c.find("jev") >= 0 else 10**6,
        }
        return min(pos, key=lambda k: pos[k])

    prem = Counter(premier(d["decideur"]) for d in de)
    R["decideur_premier_nomme"] = dict(prem)
    # Décideur qui tranche EFFECTIVEMENT aujourd'hui, si l'on retire les
    # étages Jev qui n'ont jamais tourné hors banc (prospection) ou qui sont à
    # None (filtre, refonte de la veille).
    jamais_en_service = {
        "jev-deposable",
        "jev-destinataire",
        "jev-objet",
        "jev-dispositif",
        "jev-categorie_ecart",
        "filtre-jev",
    }
    R["jev_premier_nomme"] = sorted(d["id"] for d in de if premier(d["decideur"]) == "jev")
    R["jev_jamais_exerce_hors_banc"] = sorted(d["id"] for d in de if d["id"] in jamais_en_service)

    # Granularité : décisions qui ne sont que des sous-questions d'une même
    # décision d'un même décideur.
    R["sous_questions_jev_prospection"] = [
        "jev-deposable",
        "jev-destinataire",
        "jev-objet",
        "jev-dispositif",
        "jev-categorie_ecart",
    ]

    ve = {v["cle"]: v for v in tsv("verites.tsv")}
    avec = [d for d in de if d["verite"].strip().lower() != "aucune"]
    R["avec_verite"] = taux(len(avec), len(de))
    rang = {"felix": 3, "bloc": 2, "claude": 1, "regle": 0}
    meilleure = Counter()
    cites_catalogue = []
    cites_banc = []
    seulement_regle = []
    for d in avec:
        cles = [c.strip() for c in d["verite"].split(";") if c.strip()]
        classes = [ve[c]["classe"] for c in cles if c in ve]
        inconnues = [c for c in cles if c not in ve]
        if inconnues:
            R.setdefault("verites_inconnues", []).append((d["id"], inconnues))
        best = max(classes, key=lambda x: rang[x]) if classes else "?"
        meilleure[best] += 1
        if "catalogue-yaml" in cles:
            cites_catalogue.append(d["id"])
        if any(c.startswith("banc-destinataire") for c in cles):
            cites_banc.append(d["id"])
        if classes and all(c == "regle" for c in classes):
            seulement_regle.append(d["id"])
    R["meilleure_provenance"] = dict(meilleure)
    R["decisions_citant_catalogue"] = cites_catalogue
    R["decisions_citant_banc_destinataire"] = cites_banc
    R["decisions_verite_seulement_regle"] = seulement_regle

    # Sensibilité : le banc du destinataire tire sa classe « gardée » de la
    # présence d'un YAML au commit (le catalogue) et 412 des 465 « écartées »
    # d'un tri LLM validé en bloc. Si on le reclasse « bloc » :
    reclasse = dict(ve)
    for c in ("banc-destinataire", "banc-destinataire-llm", "banc-destinataire-variante"):
        reclasse[c] = {**ve[c], "classe": "bloc"}
    m2 = Counter()
    for d in avec:
        cles = [c.strip() for c in d["verite"].split(";") if c.strip()]
        classes = [reclasse[c]["classe"] for c in cles if c in reclasse]
        m2[max(classes, key=lambda x: rang[x]) if classes else "?"] += 1
    R["meilleure_provenance_si_banc_bloc"] = dict(m2)
    # Plus strict : lot-3 est un INVENTAIRE de cas à trancher (en-tête du
    # fichier), et la requalification du 2026-10-04 une PROPOSITION de
    # sous-agents Claude (l. 3 du fichier) : aucune décision de Félix lisible.
    reclasse["fusions-lot-3"] = {**ve["fusions-lot-3"], "classe": "claude"}
    reclasse["requalif-2026-10-04"] = {**ve["requalif-2026-10-04"], "classe": "claude"}
    m3 = Counter()
    felix_restants = []
    for d in avec:
        cles = [c.strip() for c in d["verite"].split(";") if c.strip()]
        classes = [reclasse[c]["classe"] for c in cles if c in reclasse]
        b = max(classes, key=lambda x: rang[x]) if classes else "?"
        m3[b] += 1
        if b == "felix":
            felix_restants.append(d["id"])
    R["meilleure_provenance_stricte"] = dict(m3)
    R["felix_restants_strict"] = felix_restants

    # Échantillons sans vérité : somme des minutes et des dollars.
    lignes = (MESUREUR / "sans_verite.md").read_text(encoding="utf-8").splitlines()
    minutes = 0.0
    dollars = 0.0
    n = 0
    sans_objet = 0
    for li in lignes:
        cel = [c.strip() for c in li.strip().strip("|").split("|")]
        if len(cel) == 6 and cel[0] not in ("id", "total") and not cel[0].startswith("---"):
            try:
                minutes += float(cel[3].replace(",", "."))
                dollars += float(cel[4].replace(",", "."))
                n += 1
            except ValueError:
                pass
        if len(cel) == 3 and cel[1].startswith("sans objet :"):
            sans_objet += 1
    R["echantillons"] = {
        "decisions": n,
        "minutes": minutes,
        "heures": round(minutes / 60, 1),
        "dollars": round(dollars, 2),
        "sans_objet": sans_objet,
    }
    # La note dit qu'une population < 100 est échantillonnée en entier, mais
    # chiffre 100 cas : recalcul sur la population annoncée (19, 31, 41).
    stock = {"deja-refuse": 19, "acquittement": 31, "lancer-reingestion": 41}
    corr = 0.0
    for li in lignes:
        cel = [c.strip() for c in li.strip().strip("|").split("|")]
        if len(cel) == 6 and cel[0] in stock:
            mpc = float(cel[2].replace(",", "."))
            corr += float(cel[3].replace(",", ".")) - mpc * stock[cel[0]]
    R["echantillons"]["minutes_si_stock_entier"] = minutes - corr
    aucune = sum(1 for d in de if d["verite"].strip().lower() == "aucune")
    R["decisions_aucune_verite"] = aucune


# --- 2. Données brutes ----------------------------------------------------------


def recompter_file() -> None:
    taches = etat.charger(DATA / "prospection" / "file-attente.yaml")
    R["file_total"] = len(taches)
    statuts = Counter(t.statut for t in taches.values())
    R["file_statuts"] = dict(statuts)
    motifs = Counter()
    for t in taches.values():
        if t.statut != "a_valider":
            continue
        m = etat.motif_non_promotion(t)
        if m is None:
            motifs["promouvable"] += 1
        elif m.startswith("destinataire ou objet"):
            motifs["indetermine"] += 1
        elif m.startswith("famille"):
            motifs["famille"] += 1
        else:
            motifs["hors_perimetre"] += 1
    R["a_valider_motifs_vraie_regle"] = dict(motifs)
    R["a_valider_indetermine"] = taux(motifs["indetermine"], statuts["a_valider"])
    ign = [t for t in taches.values() if t.statut == "ignore"]
    nd = sum(1 for t in ign if t.categorie_ecart == "non_dispositif")
    R["ignore_non_dispositif"] = taux(nd, len(ign))
    # Combien de ces non_dispositif auraient été retenus ou indéterminés sans
    # la règle non_dispositif ? C'est la mesure de « la catégorie décide ».
    bascule_retenue = sum(
        1
        for t in ign
        if t.categorie_ecart == "non_dispositif" and etat.retenir(t.destinataire, t.objet)
    )
    bascule_indet = sum(
        1
        for t in ign
        if t.categorie_ecart == "non_dispositif" and etat.indetermine(t.destinataire, t.objet, None)
    )
    R["non_dispositif_ou_la_categorie_change_l_issue"] = {
        "retenue_sans_la_regle": bascule_retenue,
        "indeterminee_sans_la_regle": bascule_indet,
        "sur": nd,
    }
    ing = [t.ingestion for t in taches.values() if t.ingestion is not None]
    valeurs = Counter(str(i.modele) for i in ing)
    trace = sum(n for v, n in valeurs.items() if not v.startswith("(défaut") and v != "None")
    R["ingestion_modele"] = {"valeurs": dict(valeurs), **taux(trace, len(ing))}


def recompter_veille() -> None:
    m = yaml.load((DATA / "veille-state.yaml").read_text(encoding="utf-8"), Loader=CHARGEUR)
    ack = sum(1 for v in m.values() if (v or {}).get("ack"))
    perimees = sum(
        1 for v in m.values() if (v or {}).get("status") == "date_perimee_source_inchangee"
    )
    R["veille_ack_sur_manifeste"] = taux(ack, len(m))
    R["veille_ack_sur_eligibles"] = taux(ack, perimees)


def recompter_lectures() -> None:
    n = avec_cle = avec_valeur = ancien_schema = 0
    for f in sorted((DATA / "prospection").glob("*/lectures.jsonl")):
        for li in f.read_text(encoding="utf-8").splitlines():
            if not li.strip():
                continue
            o = json.loads(li)
            n += 1
            if "arbitrage" in o:
                avec_cle += 1
                if o["arbitrage"]:
                    avec_valeur += 1
            if "retenir" in (o.get("fiche") or {}):
                ancien_schema += 1
    R["lectures"] = {
        "n": n,
        "avec_cle_arbitrage": avec_cle,
        "avec_arbitrage_non_nul": avec_valeur,
        "fiche_portant_retenir_ancien_schema": ancien_schema,
        "taux_arbitrage": taux(avec_valeur, n),
        "taux_arbitrage_sur_lectures_ecrites_par_un_code_qui_le_trace": taux(avec_valeur, avec_cle),
    }


def recompter_reviews() -> None:
    fiches = sorted((DATA / "reviews").glob("*-ingest-*.md"))
    par_jour = Counter(p.name[:10] for p in fiches)
    hp = [
        p.name
        for p in fiches
        if "## Écartée à l'ingestion — hors périmètre" in p.read_text(errors="replace")
    ]
    # L'outil `declarer_hors_perimetre` apparaît dans les journaux d'ingestion
    # à partir du 2026-09-18 (voir la note) : avant, la décision n'existait pas.
    depuis = sum(n for j, n in par_jour.items() if j >= "2026-09-18")
    R["ingest_fiches"] = {"n": len(fiches), "par_jour": dict(sorted(par_jour.items()))}
    R["hors_perimetre_toutes_fiches"] = taux(len(hp), len(fiches))
    R["hors_perimetre_depuis_outil"] = taux(len(hp), depuis)
    R["hors_perimetre_fiches"] = hp
    jours_outil = Counter()
    for f in LOGS.glob("ingest-*.log"):
        t = f.read_text(errors="replace")
        if "declarer_hors_perimetre" in t:
            d = re.search(r"2026-\d\d-\d\d", t)
            jours_outil[d.group(0) if d else "?"] += 1
    R["journaux_citant_outil_hors_perimetre_par_jour"] = dict(jours_outil)


def recompter_couts() -> None:
    bal = LOGS / "balayage"
    rx = re.compile(r"(\d+) appel\(s\)[^\n]*?\$([\d.]+)")
    for run in ("2026-09-18-0052", "2026-09-29-0053"):
        n = a = 0
        c = 0.0
        sans = []
        for f in sorted(bal.glob(f"{run}-prospection-*.log")):
            n += 1
            tr = rx.findall(f.read_text(errors="replace"))
            if not tr:
                sans.append(f.name)
            for x, y in tr:
                a += int(x)
                c += float(y)
        R[f"prospection_{run}"] = {
            "journaux": n,
            "appels": a,
            "cout": round(c, 4),
            "sans_total": sans,
        }
    n = a = 0
    c = 0.0
    for f in sorted((DATA / "reviews").glob("2026-09-29-prospection-*.md")):
        m = re.search(r"coût du passage : (\d+) appel\(s\)[^\n]*?\$([\d.]+)", f.read_text())
        if m:
            n += 1
            a += int(m.group(1))
            c += float(m.group(2))
    R["fiches_prospection_2026-09-29"] = {"fiches": n, "appels": a, "cout": round(c, 4)}
    # 2026-10-04 : `prospecter.py` partage UN Compteur entre les territoires
    # d'une même commande (prospecter.py:911) et chaque fiche imprime le total
    # CUMULÉ. Sommer les fiches compte plusieurs fois les mêmes appels.
    fiches = []
    for f in sorted((DATA / "reviews").glob("2026-10-04-prospection-*.md")):
        m = re.search(r"coût du passage : (\d+) appel\(s\)[^\n]*?\$([\d.]+)([^\n]*)", f.read_text())
        if m:
            fiches.append((f.name, int(m.group(1)), float(m.group(2)), "inconnu" in m.group(3)))
    somme_a = sum(x[1] for x in fiches)
    somme_c = sum(x[2] for x in fiches)
    # Chaîne des fiches marquées « coût inconnu » : strictement croissante,
    # signe d'un compteur cumulé sur une seule commande.
    chaine = [x for x in fiches if x[3]]
    croissante = all(a[1] < b[1] for a, b in zip(chaine, chaine[1:], strict=False))
    reste = [x for x in fiches if not x[3]]
    borne_haute_a = sum(x[1] for x in reste) + (chaine[-1][1] if chaine else 0)
    borne_haute_c = sum(x[2] for x in reste) + (chaine[-1][2] if chaine else 0)
    R["fiches_prospection_2026-10-04"] = {
        "fiches": len(fiches),
        "somme_naive_appels": somme_a,
        "somme_naive_cout": round(somme_c, 4),
        "chaine_cout_inconnu": [(x[0], x[1], x[2]) for x in chaine],
        "chaine_strictement_croissante": croissante,
        "borne_haute_sans_double_compte_appels": borne_haute_a,
        "borne_haute_sans_double_compte_cout": round(borne_haute_c, 4),
    }
    t = (bal / "2026-09-29-0053-ingestion.log").read_text(errors="replace")
    m = re.search(
        r"(\d+)/(\d+) aide\(s\) ingérée\(s\)\. (\d+) appel\(s\)[^\n]*\$([\d.]+)([^\n]*)", t
    )
    R["ingestion_2026-09-29"] = (
        {
            "ok": int(m.group(1)),
            "aides": int(m.group(2)),
            "appels": int(m.group(3)),
            "cout": float(m.group(4)),
            "mention": m.group(5).strip(),
        }
        if m
        else None
    )
    banc = LOGS / "benchmark-destinataire"
    for nom in ("jev", "llm-or-glm"):
        rows = [json.loads(li) for li in (banc / f"{nom}.jsonl").read_text().splitlines() if li]
        R[f"banc_{nom}"] = {
            "lignes": len(rows),
            "cout": round(sum(r.get("cout_usd") or 0 for r in rows), 4),
        }
    veille = (DATA / "reviews" / "2026-10-04-veille.md").read_text().splitlines()
    R["veille_2026-10-04_ligne_16"] = veille[15]


# --- 3. Ancres et citations -----------------------------------------------------


def recompter_ancres() -> None:
    lignes = tsv("ancres.tsv")
    R["ancres"] = {
        "lignes": len(lignes),
        "uniques": len({(a["fichier"], a["motif"]) for a in lignes}),
        "manquantes": sum(1 for a in lignes if a["resultat"].startswith("MANQUANT")),
    }
    ambigues = []
    for fichier, motif in sorted({(a["fichier"], a["motif"]) for a in lignes}):
        chemin = RACINE / fichier
        if not chemin.exists():
            ambigues.append((fichier, motif, "FICHIER ABSENT", ""))
            continue
        rx = re.compile(motif)
        hits = [
            i
            for i, li in enumerate(chemin.read_text(errors="replace").splitlines(), 1)
            if rx.search(li)
        ]
        if len(hits) != 1:
            ambigues.append((fichier, motif, str(len(hits)), ",".join(map(str, hits[:8]))))
    R["ancres"]["motifs_a_plusieurs_lignes_ou_aucune"] = len(ambigues)
    with open(SORTIE / "ancres_ambigues.tsv", "w", encoding="utf-8") as f:
        f.write("fichier\tmotif\tnb_lignes\tlignes\n")
        for a in ambigues:
            f.write("\t".join(a) + "\n")

    # Citations du texte libre de la note : `chemin:ligne` hors des tableaux.
    note = NOTE.read_text(encoding="utf-8")
    cit = set(
        re.findall(
            r"`?((?:scripts|data|backend|\.claude)/[\w./-]+\.(?:py|md|log|yaml)):(\d+)", note
        )
    )
    resultats = []
    for chemin, ligne in sorted(cit):
        candidats = [BACKEND / chemin, RACINE / chemin]
        p = next((c for c in candidats if c.exists()), None)
        if p is None:
            resultats.append((chemin, ligne, "FICHIER ABSENT"))
            continue
        ls = p.read_text(errors="replace").splitlines()
        i = int(ligne)
        resultats.append(
            (chemin, ligne, ls[i - 1].strip()[:140] if i <= len(ls) else "HORS FICHIER")
        )
    R["citations_texte"] = {
        "n": len(resultats),
        "hors_fichier_ou_absent": sum(
            1 for r in resultats if r[2] in ("HORS FICHIER", "FICHIER ABSENT")
        ),
    }
    with open(SORTIE / "citations_texte.tsv", "w", encoding="utf-8") as f:
        f.write("chemin\tligne\tcontenu\n")
        for r in resultats:
            f.write("\t".join(r) + "\n")


# --- 4. Décisions du schéma absentes de l'inventaire ---------------------------


def decisions_absentes() -> None:
    aides = []
    for p in sorted((DATA / "aides").glob("*.yaml")):
        aides.append(yaml.load(p.read_text(encoding="utf-8"), Loader=CHARGEUR) or {})
    hf = Counter()
    for a in aides:
        for k, v in (a.get("hard_filters") or {}).items():
            if v not in (None, [], ""):
                hf[k] += 1
    pred = Counter()
    ops = Counter()
    for a in aides:
        for c in a.get("conditions") or []:
            if c.get("predicate") is not None:
                pred[c.get("kind")] += 1
                p = c["predicate"]
                if isinstance(p, dict):
                    ops.update(list(p))
    R["catalogue_aides"] = len(aides)
    R["hard_filters_non_vides"] = dict(hf)
    R["conditions_avec_predicat_par_kind"] = dict(pred)
    R["operateurs_de_predicat"] = dict(ops.most_common(15))
    de = {d["id"] for d in tsv("decisions.tsv")}
    absentes = [
        (
            "predicat",
            "Opérateur et valeur du prédicat d'une condition user_fact ou auto (eq / in / gte / lte...)",
            "LLM (agent d'ingestion) ; forme au lint",
            f"{sum(pred.values())} conditions à prédicat",
        ),
        (
            "auto-field",
            "Chemin FIELD_REGISTRY d'une condition auto",
            "LLM (agent d'ingestion)",
            f"{pred.get('auto', 0)} conditions auto à prédicat",
        ),
        (
            "hard-filters-portee",
            "hard_filters regions / departements / protections / proprietaires / etats_conservation / commune_max_population",
            "LLM (agent d'ingestion)",
            ", ".join(f"{k} {v}" for k, v in sorted(hf.items()) if k != "travaux"),
        ),
        (
            "applies-if-condition",
            "Restreindre une condition à une sous-population (applies_if de condition)",
            "LLM (agent d'ingestion)",
            f"{sum(1 for a in aides for c in a.get('conditions') or [] if c.get('applies_if'))}"
            " conditions à applies_if",
        ),
    ]
    R["decisions_absentes"] = [a[0] for a in absentes if a[0] not in de]
    with open(SORTIE / "decisions_absentes.tsv", "w", encoding="utf-8") as f:
        f.write("id\tquestion\tdecideur\tvolume_catalogue\n")
        for a in absentes:
            f.write("\t".join(a) + "\n")


def main() -> None:
    SORTIE.mkdir(parents=True, exist_ok=True)
    recompter_tableaux()
    recompter_file()
    recompter_veille()
    recompter_lectures()
    recompter_reviews()
    recompter_couts()
    recompter_ancres()
    decisions_absentes()
    (SORTIE / "recompte.json").write_text(
        json.dumps(R, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    print(json.dumps(R, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
