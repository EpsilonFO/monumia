"""Ligne de base de la veille des aides (phase 1 de la refonte, mesure seule).

    cd backend && uv run python scripts/mesures/veille.py

Ne lance AUCUN étage de la veille ni aucun banc, n'appelle aucun modèle et ne
touche pas au réseau. Lit seulement : les caches du banc Jev et du banc de
l'étage C (`data/reviews/logs/veille-jev/`), la fiche d'étiquetage et les
rapports de veille (`data/reviews/`), le manifeste `data/veille-state.yaml`, le
journal complet du 2026-10-04 (`data/reviews/logs/depuis-veille-hebdo/`), les
journaux de ré-ingestion, les snapshots de `data/sources/` et l'historique git
(`git log`, `git show`). L'extraction des PDF passe par `pdftotext` SANS écrire
le cache disque de `veille_collect` (fonction remplacée par une version en
lecture seule).

Produit, dans `data/reviews/logs/refonte/2026-10-10-veille-1/` :

    q1_manques.json      changements manqués, avec et sans la garde Jev
    q2_retouches.json    fausses retouches, contrôle des valeurs retouchées
    q3_cout.json         coût, durée, statuts, escalades, gabarit (proxy)
    q4_devenir.json      sort des escalades, échéances, erreurs, retouches
    q5_pannes.json       pannes mémorisées comme refus, garde en panne, noul vide
    q6_j6_j7.json        matière disponible pour J6 et J7
    resume.txt           les chiffres clés, une ligne chacun, avec leur source
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import UTC, date
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[2]
RACINE = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

import veille_collect  # noqa: E402


def _pdf_lecture_seule(content: bytes) -> str | None:
    """`pdf_bytes_to_text` sans écriture du cache disque (consigne : lecture seule)."""
    import hashlib

    cache = veille_collect.PDFTEXT_CACHE_DIR / f"{hashlib.sha256(content).hexdigest()}.txt"
    if cache.is_file():
        return cache.read_text(encoding="utf-8")
    return veille_collect._pdftotext(content)


veille_collect.pdf_bytes_to_text = _pdf_lecture_seule

from veille_analyze import ligne_de_reglement, lignes_de_chrome  # noqa: E402
from veille_arbitre import SEUIL_GARDE, empreinte_etat, etat_mandat  # noqa: E402
from veille_benchmark_jev import collect_depuis_snapshots  # noqa: E402
from veille_text import normalize_line, normalized_diff, parse_front_matter  # noqa: E402

from aides_schema import charger_yaml  # noqa: E402

DATA = BACKEND / "data"
REVIEWS = DATA / "reviews"
LOGS = REVIEWS / "logs"
JEV_DIR = LOGS / "veille-jev"
SORTIE = LOGS / "refonte" / "2026-10-10-veille-1"
JOUR = "2026-10-04"
AUJOURDHUI = date(2026, 10, 10)
COMMIT_PASSAGE = "c36cbfd9"  # commit qui porte les retouches du 2026-10-04

# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    demi = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centre - demi), min(1.0, centre + demi)


def taux(k: int, n: int) -> dict[str, Any]:
    ic = wilson(k, n)
    return {
        "k": k,
        "n": n,
        "p": round(k / n, 4) if n else None,
        "wilson95": [round(ic[0], 4), round(ic[1], 4)] if ic else None,
        "texte": (
            f"{k}/{n} = {100 * k / n:.1f} % [IC95 {100 * ic[0]:.1f} ; {100 * ic[1]:.1f}]"
            if n and ic
            else f"{k}/{n}"
        ),
    }


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(RACINE), *args], capture_output=True, text=True, check=False
    ).stdout


def lire_jsonl(chemin: Path) -> list[dict[str, Any]]:
    return [json.loads(ligne) for ligne in chemin.read_text(encoding="utf-8").splitlines() if ligne]


def sans_accents(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[   ]", " ", s)
    return re.sub(r"\s+", " ", s.lower())


def ecrire(nom: str, contenu: Any) -> None:
    (SORTIE / nom).write_text(
        json.dumps(contenu, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Lecture des sources
# ---------------------------------------------------------------------------


def lire_etiquettes() -> dict[str, str]:
    """Même lecture que `veille_benchmark_jev.lire_etiquettes`."""
    chemin = REVIEWS / f"{JOUR}-etiquettes-veille-jev.md"
    out, courant = {}, None
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        if ligne.startswith("### "):
            courant = ligne[4:].strip()
        elif courant and (m := re.match(r"- \[[xX]\] (.+?)\s*$", ligne)):
            out[courant] = m.group(1)
    return out


def sections_rapport(chemin: Path) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = defaultdict(list)
    titre = "_entete"
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        if ligne.startswith("## "):
            titre = ligne[3:].strip()
        elif ligne.startswith("### ") and titre.startswith("Étage C"):
            titre = "Étage C / " + ligne[4:].strip()
        else:
            sections[titre].append(ligne)
    return sections


def puces(lignes: list[str]) -> dict[str, str]:
    out = {}
    for ligne in lignes:
        if m := re.match(r"- \*\*([^*]+)\*\* \u2014 (.*)$", ligne):
            out[m.group(1)] = m.group(2)
    return out


def statuts_rapport(chemin: Path) -> dict[str, int]:
    out = {}
    for ligne in chemin.read_text(encoding="utf-8").splitlines()[:15]:
        if m := re.match(r"\| `([A-Z_]+)` \| (\d+) \|", ligne):
            out[m.group(1)] = int(m.group(2))
    return out


def jetons(s: str) -> float:
    if s.endswith("k"):
        return float(s[:-1]) * 1e3
    if s.endswith("M"):
        return float(s[:-1]) * 1e6
    return float(s)


LIGNE_ETAGE_C = re.compile(
    r"^\s+\[(\d+)/(\d+)\]\s+(\S)\s+(\S+)\s+([\d.]+)¢\s+([\d.]+)s\s+([\d.]+[kM]?)↑\s*([\d.]+[kM]?)↓"
)


def lignes_etage_c(chemin: Path) -> list[dict[str, Any]]:
    out = []
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        if m := LIGNE_ETAGE_C.match(ligne):
            out.append(
                {
                    "symbole": m.group(3),
                    "slug": m.group(4),
                    "cout_usd": float(m.group(5)) / 100,
                    "latence_s": float(m.group(6)),
                    "jetons_in": jetons(m.group(7)),
                    "jetons_out": jetons(m.group(8)),
                }
            )
    return out


def mediane(xs: list[float]) -> float | None:
    xs = sorted(xs)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


def quantile(xs: list[float], q: float) -> float | None:
    xs = sorted(xs)
    if not xs:
        return None
    return xs[min(len(xs) - 1, int(math.ceil(q * len(xs))) - 1)]


# ---------------------------------------------------------------------------
# Q1 : changements manqués
# ---------------------------------------------------------------------------


def q1(
    cas: list[dict], lab: dict[str, str], jev: dict[str, dict], jev_l: list[dict], etc: list[dict]
) -> dict:
    snap = [c for c in cas if c["origine"] == "snapshots"]
    reels = [c for c in snap if lab.get(c["id"]) == "touche"]
    inch = [c for c in snap if c["verdict_llm"] == "inchange"]
    faux_inch = [c for c in inch if lab.get(c["id"]) == "touche"]

    # Notes de la garde sur le résumé de PRODUCTION (cache du banc Jev). La clé
    # du cache dépend du diff : le filtre Jalios du 2026-10-05 a changé le diff
    # de certains cas après leur notation. On retient donc la DERNIÈRE note
    # écrite pour chaque cas (ordre du fichier), et on compte à part les cas
    # dont la clé recalculée retombe sur le cache.
    gardes = [r for r in jev_l if r["usage"] == "garde"]
    notes: dict[str, float] = {}
    for r in gardes:
        notes[r["cas"]] = r["p"]
    cles_exactes = sum(
        "garde:" + empreinte_etat(etat_mandat(c["fiche"], c["diff"], c["resume_llm"])) in jev
        for c in inch
    )
    ids_inch = {c["id"] for c in inch}
    retires = sorted((p, i) for i, p in notes.items() if i not in ids_inch)
    plusieurs = {
        i: [r["p"] for r in gardes if r["cas"] == i]
        for i in {r["cas"] for r in gardes}
        if sum(r["cas"] == i for r in gardes) > 1
    }

    pos = sorted((notes[c["id"]], c["slug"]) for c in faux_inch if c["id"] in notes)
    neg_actuel = sorted(
        (notes[c["id"]], c["slug"])
        for c in inch
        if lab.get(c["id"]) == "ne touche pas" and c["id"] in notes
    )
    # Jeu du 2026-10-04 (72) : les cas retirés depuis sont des « ne touche
    # pas » (le rapport du banc nomme ses 9 positifs, tous encore présents).
    neg_banc = sorted(neg_actuel + [(p, i.removeprefix("A · ")) for p, i in retires])

    def evaluer(neg: list) -> dict:
        out = {}
        for s in (0.08, 0.10, 0.20, 0.30, 0.40, 0.45, 0.50, 0.60):
            perdus = sum(p < s for p, _ in pos)
            out[f"{s:.2f}"] = {
                "perdus_parmi_faux_inchange": taux(perdus, len(pos)),
                "perdus_parmi_changements_reels": taux(perdus, len(reels)),
                "fausses_alertes": taux(sum(p >= s for p, _ in neg), len(neg)),
            }
        return out

    # Validation croisée « un cas positif mis de côté » de la règle du banc
    # (seuil = 80 % de la note du pire positif restant).
    loo = []
    for i, (p, slug) in enumerate(pos):
        autres = [q for j, (q, _) in enumerate(pos) if j != i]
        s = round(0.8 * min(autres), 3)
        loo.append({"slug": slug, "note": p, "seuil_sans_lui": s, "rattrape": p >= s})
    # Moitié de contrôle : seuil réglé sur les positifs de rang pair, évalué sur
    # les impairs (et inversement), même règle.
    moities = []
    for parite in (0, 1):
        reglage = [p for j, (p, _) in enumerate(pos) if j % 2 == parite]
        controle = [p for j, (p, _) in enumerate(pos) if j % 2 != parite]
        s = round(0.8 * min(reglage), 3)
        moities.append(
            {
                "reglage_n": len(reglage),
                "controle_n": len(controle),
                "seuil": s,
                "perdus_controle": sum(p < s for p in controle),
            }
        )

    # Banc de l'étage C : 10 configurations sur les 87 cas reconstruits.
    par_cfg: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in etc:
        par_cfg[r["modele"]][r["cas"]] = r
    ids_snap = {c["id"] for c in snap}
    bancs = {}
    perdus_par_cas: Counter = Counter()
    perdus_garde_par_cas: Counter = Counter()
    notes_garde_par_cas: dict[str, list[float | None]] = defaultdict(list)
    notes_pos_inch: list[float | None] = []
    notes_neg_inch: list[float | None] = []
    n_neg_total = 0
    for cfg, rs in sorted(par_cfg.items()):
        p_ids = [i for i in rs if i in ids_snap and lab.get(i) == "touche"]
        n_ids = [i for i in rs if i in ids_snap and lab.get(i) == "ne touche pas"]
        etats_pos = Counter(rs[i]["etat"] for i in p_ids)
        perdus = [i for i in p_ids if rs[i]["etat"] == "inchange"]
        perdus_g = [
            i
            for i in perdus
            if rs[i].get("garde") is None or rs[i]["garde"] < SEUIL_GARDE  # panne = ré-archivage
        ]
        for i in perdus:
            perdus_par_cas[i] += 1
            notes_garde_par_cas[i].append(rs[i].get("garde"))
        for i in perdus_g:
            perdus_garde_par_cas[i] += 1
        notes_pos_inch += [rs[i].get("garde") for i in perdus]
        notes_neg_inch += [rs[i].get("garde") for i in n_ids if rs[i]["etat"] == "inchange"]
        n_neg_total += len(n_ids)
        bancs[cfg] = {
            "touche": len(p_ids),
            "ne_touche_pas": len(n_ids),
            "etats_touche": dict(etats_pos),
            "perdus_sans_garde": taux(len(perdus), len(p_ids)),
            "perdus_avec_garde_045": taux(len(perdus_g), len(p_ids)),
            "rattrapes_par_garde": len(perdus) - len(perdus_g),
            "fausses_retouches": taux(sum(rs[i]["etat"] == "applique" for i in n_ids), len(n_ids)),
            "reingestions_inutiles": sum(rs[i]["etat"] == "escalade" for i in n_ids),
            "fausses_alertes_garde_045": sum(
                rs[i]["etat"] == "inchange" and (rs[i].get("garde") or 0) >= SEUIL_GARDE
                for i in n_ids
            ),
            "echecs": sum(rs[i]["etat"] == "echec" for i in rs if i in ids_snap),
            "cout_usd": round(sum(rs[i]["cout"] for i in rs), 4),
            "perdus_avec_garde_slugs": sorted(perdus_g),
        }
    total_p = sum(b["touche"] for b in bancs.values())
    seuils_banc = {
        f"{t:.2f}": {
            "perdus": taux(sum(x is None or x < t for x in notes_pos_inch), total_p),
            "fausses_alertes": taux(
                sum(x is not None and x >= t for x in notes_neg_inch), n_neg_total
            ),
        }
        for t in (0.08, 0.10, 0.20, 0.30, 0.45, 0.60)
    }
    return {
        "provenance_etiquettes": {
            "fiche": f"data/reviews/{JOUR}-etiquettes-veille-jev.md",
            "cochees_d_office_regle_de_code": {
                "retouche appliquée (applique => touche)": sum(
                    c["etiquette_auto"] == "touche" and c["verdict_llm"] == "applique" for c in cas
                ),
                "faux inchangé constaté au plan (TOUCHE_CONSTATEES)": sum(
                    c["etiquette_auto"] == "touche" and c["verdict_llm"] == "inchange" for c in cas
                ),
                "golds": sum(c["origine"] == "gold" for c in cas),
            },
            "posees_sans_case_d_office": sum(not c["etiquette_auto"] for c in cas),
            "auteur_selon_memoire": "Claude (6 agents + relecture, prudence = touche), "
            "à la demande de Félix ; le code et le plan exigent une étiquette humaine",
        },
        "production_2026_10_04_sans_garde": {
            "inchange_reconstruits": len(inch),
            "faux_inchange": taux(len(faux_inch), len(inch)),
            "faux_inchange_slugs": sorted(c["slug"] for c in faux_inch),
            "changements_reels_vus_par_etage_c": len(reels),
            "perdus_parmi_changements_reels": taux(len(faux_inch), len(reels)),
            "denominateur_du_banc_jev_le_2026_10_04": "72 (9 faux, 63 vrais), avant le filtre "
            "Jalios du 2026-10-05 qui a vidé le diff de 9 cas « ne touche pas »",
            "faux_inchange_sur_72": taux(len(faux_inch), 72),
        },
        "garde_sur_resume_de_production": {
            "notes_par_cas": f"{sum(c['id'] in notes for c in inch)}/{len(inch)}",
            "cles_recalculees_retrouvees": f"{cles_exactes}/{len(inch)}",
            "cas_notes_plusieurs_fois": plusieurs,
            "positifs": pos,
            "negatifs_retires_depuis_le_banc": retires,
            "seuils_jeu_du_banc_72": evaluer(neg_banc),
            "seuils_jeu_actuel_63": evaluer(neg_actuel),
            "seuil_045_choisi_sur_ce_jeu": "oui : veille_arbitre.py:53-58 cite ce même banc",
            "loo_regle_du_banc": loo,
            "loo_perdus": sum(not x["rattrape"] for x in loo),
            "moities_de_controle": moities,
        },
        "banc_etage_c": bancs,
        "banc_etage_c_cumule": {
            "configurations": len(bancs),
            "essais_touche": total_p,
            "perdus_sans_garde": taux(
                sum(b["perdus_sans_garde"]["k"] for b in bancs.values()), total_p
            ),
            "perdus_avec_garde": taux(
                sum(b["perdus_avec_garde_045"]["k"] for b in bancs.values()), total_p
            ),
            "avertissement": "les 10 configurations rejouent les MEMES 33 cas : essais non indépendants",
            "seuils_garde_sur_resumes_du_banc": seuils_banc,
            "cas_perdus_sans_garde_nb_configs": dict(perdus_par_cas.most_common()),
            "cas_perdus_avec_garde_nb_configs": dict(perdus_garde_par_cas.most_common()),
            "notes_garde_des_perdus_par_config": dict(notes_garde_par_cas),
        },
    }


# ---------------------------------------------------------------------------
# Q2 : retouches
# ---------------------------------------------------------------------------

MOIS = [
    "janvier",
    "fevrier",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "aout",
    "septembre",
    "octobre",
    "novembre",
    "decembre",
]


def formes_date(d: date) -> tuple[list[str], list[str]]:
    jour = "1er" if d.day == 1 else str(d.day)
    avec = [
        f"{jour} {MOIS[d.month - 1]} {d.year}",
        f"{d.day} {MOIS[d.month - 1]} {d.year}",
        f"{d.day:02d}/{d.month:02d}/{d.year}",
        f"{d.day}/{d.month}/{d.year}",
        f"{d.day:02d}.{d.month:02d}.{d.year}",
        d.isoformat(),
    ]
    sans = [
        f"{jour} {MOIS[d.month - 1]}",
        f"{d.day} {MOIS[d.month - 1]}",
        f"{d.day:02d}/{d.month:02d}",
    ]
    return avec, sans


def formes_nombre(x: float) -> list[str]:
    n = int(x) if float(x).is_integer() else x
    if isinstance(n, int):
        groupe = f"{n:,}".replace(",", " ")
        return [groupe, str(n), f"{n:,}".replace(",", ".")]
    return [str(n), str(n).replace(".", ",")]


def texte_snapshots(slug: str, prefixe: str) -> str:
    morceaux = []
    dossier = DATA / "sources" / slug
    if not dossier.is_dir():
        return ""
    for p in sorted(dossier.iterdir()):
        if not p.name.startswith(prefixe):
            continue
        if p.suffix == ".md":
            morceaux.append(parse_front_matter(p.read_text(encoding="utf-8"))[1])
        elif p.suffix == ".pdf":
            morceaux.append(_pdf_lecture_seule(p.read_bytes()) or "")
    return sans_accents("\n".join(morceaux))


def yaml_a(rev: str, slug: str) -> dict | None:
    brut = git("show", f"{rev}:backend/data/aides/{slug}.yaml")
    return charger_yaml(brut) if brut else None


def champs_changes(avant: dict, apres: dict) -> list[tuple[str, Any, Any]]:
    out = []
    for section in ("calendrier", "financement", "cumul"):
        a, b = avant.get(section) or {}, apres.get(section) or {}
        for cle in sorted(set(a) | set(b)):
            if a.get(cle) != b.get(cle):
                out.append((f"{section}.{cle}", a.get(cle), b.get(cle)))
    return out


def trouve(valeur: Any, texte: str) -> str:
    """« avec année », « sans année », « oui », « non » ou « non vérifiable »."""
    if isinstance(valeur, bool) or valeur is None:
        return "non vérifiable"
    if isinstance(valeur, date):
        avec, sans = formes_date(valeur)
        if any(f in texte for f in avec):
            return "avec année"
        return "sans année" if any(f in texte for f in sans) else "non"
    if isinstance(valeur, (int, float)):
        return (
            "oui"
            if any(
                re.search(rf"(?<![\d]){re.escape(f)}(?![\d])", texte) for f in formes_nombre(valeur)
            )
            else "non"
        )
    return "non vérifiable"


def formes_texte(valeur: Any) -> list[str]:
    if isinstance(valeur, date):
        return formes_date(valeur)[0]
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
        return formes_nombre(valeur)
    return []


def q2(cas: list[dict], lab: dict[str, str], etc: list[dict], manifest: dict) -> dict:
    appliquees = sorted(c["slug"] for c in cas if c["verdict_llm"] == "applique")
    parent = git("rev-parse", f"{COMMIT_PASSAGE}^").strip()
    controle, fiches = [], []
    for slug in appliquees:
        avant, apres = yaml_a(parent, slug), yaml_a(COMMIT_PASSAGE, slug)
        if not (avant and apres):
            continue
        frais = texte_snapshots(slug, JOUR)
        changes = champs_changes(avant, apres)
        for champ, a, b in changes:
            controle.append(
                {
                    "slug": slug,
                    "champ": champ,
                    "avant": a,
                    "apres": b,
                    "dans_page": trouve(b, frais),
                }
            )
        # Le bloc fiche: d'avant contredit-il la retouche ? Proxy : une ancienne
        # valeur (date, montant) retrouvée telle quelle dans le texte du bloc.
        anciens = [
            f
            for _, a, b in changes
            if a is not None and b is not None and a != b
            for f in formes_texte(a)
        ]
        fiche_av = sans_accents(
            json.dumps(avant.get("fiche") or {}, ensure_ascii=False, default=str)
        )
        fiche_ap = sans_accents(
            json.dumps(apres.get("fiche") or {}, ensure_ascii=False, default=str)
        )
        hors = sans_accents(
            " ".join(
                str(apres.get(k) or "") for k in ("description", "description_longue", "demarche")
            )
        )
        tete = DATA / "aides" / f"{slug}.yaml"
        if not tete.exists():
            tete = DATA / "aides" / f"{slug}.yaml.echec"
        actuel = charger_yaml(tete.read_text(encoding="utf-8")) or {}
        fiche_tete = sans_accents(
            json.dumps(actuel.get("fiche") or {}, ensure_ascii=False, default=str)
        )
        fiches.append(
            {
                "slug": slug,
                "champs_manifeste": (manifest.get(slug) or {}).get("maj", {}).get("champs"),
                "anciennes_valeurs_comparables": len(anciens) > 0,
                "fiche_avant_contient_ancienne_valeur": any(
                    sans_accents(f) in fiche_av for f in anciens
                ),
                "fiche_apres_contient_ancienne_valeur": any(
                    sans_accents(f) in fiche_ap for f in anciens
                ),
                "fiche_head_contient_ancienne_valeur": any(
                    sans_accents(f) in fiche_tete for f in anciens
                ),
                "fichier_head": tete.name,
                "redige_le_avant": (avant.get("fiche") or {}).get("redige_le"),
                "redige_le_apres": (apres.get("fiche") or {}).get("redige_le"),
                "hors_mandat_contient_ancienne_valeur": any(
                    sans_accents(f) in hors for f in anciens
                ),
            }
        )
    verifiables = [x for x in controle if x["dans_page"] != "non vérifiable"]
    retrouves = [x for x in verifiables if x["dans_page"] in ("avec année", "oui")]

    # Cohérence du banc avec la production sur les 24 retouches.
    par_cfg: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in etc:
        par_cfg[r["modele"]][r["cas"]] = r

    def norm_champs(xs: list[str]) -> set[str]:
        return {re.sub(r"\s*\(.*\)$", "", x) for x in xs or []}

    accord = []
    for slug in appliquees:
        prod = norm_champs((manifest.get(slug) or {}).get("maj", {}).get("champs"))
        cid = f"A · {slug}"
        etats = [rs[cid]["etat"] for rs in par_cfg.values() if cid in rs]
        memes = [norm_champs(rs[cid]["champs"]) == prod for rs in par_cfg.values() if cid in rs]
        accord.append(
            {
                "slug": slug,
                "configs": len(etats),
                "appliquee": etats.count("applique"),
                "memes_champs_que_production": sum(memes),
            }
        )
    n_conf = sum(a["configs"] for a in accord)
    fiche_contra = [f for f in fiches if f["fiche_avant_contient_ancienne_valeur"]]
    return {
        "retouches_production": len(appliquees),
        "etiquette_des_retouches": "touche d'office (règle de code, « retouche appliquée et relue ») : "
        "la production ne peut donc pas montrer de fausse retouche dans ce jeu",
        "controle_valeurs_dans_page_fraiche": {
            "champs_changes": len(controle),
            "verifiables": len(verifiables),
            "retrouves_exactement": taux(len(retrouves), len(verifiables)),
            "par_categorie": dict(Counter(x["dans_page"] for x in controle)),
            "detail": controle,
        },
        "accord_banc_production": {
            "essais": n_conf,
            "appliquee": taux(sum(a["appliquee"] for a in accord), n_conf),
            "memes_champs": taux(sum(a["memes_champs_que_production"] for a in accord), n_conf),
            "detail": accord,
        },
        "bloc_fiche": {
            "fiche_avant_contredit_proxy": taux(len(fiche_contra), len(fiches)),
            "fiche_apres_contredit_encore_proxy": sum(
                f["fiche_apres_contient_ancienne_valeur"] for f in fiches
            ),
            "fiche_head_contredit_encore_proxy": [
                f["slug"] for f in fiches if f["fiche_head_contient_ancienne_valeur"]
            ],
            "fiche_regeneree_apres_passage": sum(
                str(f["redige_le_apres"] or "") >= JOUR for f in fiches
            ),
            "description_ou_demarche_porte_ancienne_valeur": sum(
                f["hors_mandat_contient_ancienne_valeur"] for f in fiches
            ),
            "detail": fiches,
        },
    }


# ---------------------------------------------------------------------------
# Q3 : coût, statuts, gabarit
# ---------------------------------------------------------------------------


def classer_escalade(raisons: str) -> str:
    if "page officielle morte" in raisons:
        return "B1 page morte"
    if "contenu utile réduit" in raisons:
        return "B4 page vidée"
    if "document binaire modifié" in raisons:
        return "B5 binaire"
    if "refonte de" in raisons:
        return "B6 refonte"
    if "citations recontrôlables ont disparu" in raisons:
        return "B7 régressions massives"
    if "changement majeur déclaré" in raisons:
        return "C majeur"
    if "condition(s) nouvelle(s)" in raisons or "condition(s) disparue(s)" in raisons:
        return "C structure"
    if "non ancrée" in raisons:
        return "C ancrage"
    return "autre"


def gabarit_proxy(slugs: list[str]) -> dict:
    collects = {s: col for s in slugs if (col := collect_depuis_snapshots(s, JOUR))}
    chrome = lignes_de_chrome(collects)
    brutes = retirees = protegees = 0
    par_url_ligne: dict[str, set[str]] = defaultdict(set)
    for col in collects.values():
        for murl in col.urls:
            res = col.fetched[murl.url]
            texte = res.texte
            if not texte or murl.baseline_body is None:
                continue
            d = normalized_diff(murl.baseline_body, texte)
            for ligne in d.text.splitlines():
                if ligne[:2] in ("+ ", "- ") and (n := normalize_line(ligne[2:])):
                    brutes += 1
                    retirees += n in chrome
                    par_url_ligne[n].add(murl.url)
    for n, urls in par_url_ligne.items():
        if len(urls) >= 2 and ligne_de_reglement(n):
            protegees += 1
    return {
        "aides": len(collects),
        "urls": sum(len(c.urls) for c in collects.values()),
        "lignes_diffees": brutes,
        "lignes_retirees_comme_gabarit": taux(retirees, brutes),
        "lignes_distinctes_partagees_mais_protegees_reglement": protegees,
        "avertissement": "calcul restreint aux pages ré-archivées le 2026-10-04, code du "
        "worktree (filtre Jalios du 2026-10-05 compris) : la production calcule le gabarit "
        "sur les 1 439 URL du parc",
    }


def q3(sec: dict[str, list[str]], log_c: list[dict], manifest: dict, gabarit: dict) -> dict:
    statuts = statuts_rapport(REVIEWS / f"{JOUR}-veille.md")
    esc = puces(sec["Escalades \u2014 ré-ingestion complète"])
    cls = Counter(classer_escalade(r) for r in esc.values())
    couts = [x["cout_usd"] for x in log_c]
    lat = [x["latence_s"] for x in log_c]
    ete = {}
    for f in sorted(REVIEWS.glob("2026-0[89]-[0-9][0-9]-veille.md")) + [
        REVIEWS / f"{JOUR}-veille.md"
    ]:
        tete = f.read_text(encoding="utf-8").splitlines()[:20]
        m = re.search(r"(\d+) aide\(s\) contrôlée\(s\) en ([\d.]+) min", tete[2])
        c = next(
            (
                re.search(r"(\d+) aide\(s\) soumise\(s\) au modèle pour ([\d.]+) \$", t)
                for t in tete
                if "soumise(s)" in t
            ),
            None,
        )
        ete[f.name] = {
            "aides": int(m.group(1)) if m else None,
            "minutes": float(m.group(2)) if m else None,
            "soumises": int(c.group(1)) if c else 0,
            "cout_usd": float(c.group(2)) if c else 0.0,
            "statuts": statuts_rapport(f),
        }
    log_0828 = lignes_etage_c(LOGS / "veille-2026-08-28.log")
    return {
        "statuts_rapport_2026_10_04": statuts,
        "statuts_manifeste": dict(Counter(e.get("status") for e in manifest.values())),
        "escalades_par_regle": dict(cls),
        "etage_c_journal": {
            "appels": len(log_c),
            "cout_usd_somme": round(sum(couts), 4),
            "cout_usd_mediane": mediane(couts),
            "cout_usd_p90": quantile(couts, 0.9),
            "cout_usd_max": max(couts) if couts else None,
            "latence_s_mediane": mediane(lat),
            "latence_s_p90": quantile(lat, 0.9),
            "latence_s_max": max(lat) if lat else None,
            "latence_s_somme": round(sum(lat), 1),
            "jetons_in_somme": sum(x["jetons_in"] for x in log_c),
            "jetons_out_somme": sum(x["jetons_out"] for x in log_c),
            "symboles": dict(Counter(x["symbole"] for x in log_c)),
        },
        "etage_c_2026_08_28": {
            "appels": len(log_0828),
            "latence_s_mediane": mediane([x["latence_s"] for x in log_0828]),
            "latence_s_max": max((x["latence_s"] for x in log_0828), default=None),
        },
        "passages": ete,
        "gabarit_proxy": gabarit,
    }


# ---------------------------------------------------------------------------
# Q4 : devenir après le passage
# ---------------------------------------------------------------------------


def devenir(slug: str, manifest: dict) -> dict:
    yaml_p = DATA / "aides" / f"{slug}.yaml"
    commits = git(
        "log",
        "--since=2026-10-04T16:42",
        "--format=%h %ad %s",
        "--date=short",
        "--",
        f"backend/data/aides/{slug}.yaml",
    ).splitlines()
    sources = DATA / "sources" / slug
    apres = (
        sorted(p.name for p in sources.iterdir() if p.name[:10] > JOUR) if sources.is_dir() else []
    )
    reviews = sorted(p.name for p in REVIEWS.glob(f"2026-10-*{slug}*.md") if p.name[:10] > JOUR)
    ent = manifest.get(slug) or {}
    aide = charger_yaml(yaml_p.read_text(encoding="utf-8")) if yaml_p.exists() else {}
    cal = (aide or {}).get("calendrier") or {}
    return {
        "slug": slug,
        "fiche_presente": yaml_p.exists(),
        "fiche_en_echec": (DATA / "aides" / f"{slug}.yaml.echec").exists(),
        "commits_apres_passage": commits,
        "commits_hors_commit_du_passage": [c for c in commits if not c.startswith(COMMIT_PASSAGE)],
        "snapshots_posterieurs": apres,
        "reviews_posterieures": reviews,
        "statut_manifeste": ent.get("status"),
        "ack": ent.get("ack"),
        "maj_refusee": (ent.get("maj_refusee") or {}).get("etat"),
        "date_limite_actuelle": cal.get("date_limite"),
        "permanent_actuel": cal.get("permanent"),
    }


def q4(sec: dict[str, list[str]], manifest: dict, fiches_q2: list[dict]) -> dict:
    esc = puces(sec["Escalades \u2014 ré-ingestion complète"])
    inj = puces(sec["Sources injoignables \u2014 à retenter"])
    ech = []
    for ligne in sec["Échéances passées, source inchangée"]:
        if m := re.match(r"\| ([a-z0-9-]+) \| (\d{4}-\d\d-\d\d) \| (\d+) j \|", ligne):
            ech.append(m.group(1))
    table_c = [
        re.match(r"\| ([a-z0-9-]+) \|", ligne).group(1)
        for ligne in sec["Étage C"]
        if re.match(r"\| [a-z0-9-]+ \| `", ligne)
    ]
    out: dict[str, Any] = {}
    for nom, slugs in (
        ("escalades", list(esc)),
        ("echeances_perimees", ech),
        ("injoignables", list(inj)),
        ("retouches", table_c),
    ):
        lignes = [devenir(s, manifest) for s in slugs]
        out[nom] = {
            "n": len(slugs),
            "fiche_presente": sum(x["fiche_presente"] for x in lignes),
            "fiche_en_echec": sum(x["fiche_en_echec"] for x in lignes),
            "avec_commit_hors_passage": sum(
                bool(x["commits_hors_commit_du_passage"]) for x in lignes
            ),
            "avec_commit_du_passage": sum(
                any(c.startswith(COMMIT_PASSAGE) for c in x["commits_apres_passage"])
                for x in lignes
            ),
            "avec_snapshot_posterieur": sum(bool(x["snapshots_posterieurs"]) for x in lignes),
            "avec_review_posterieure": sum(bool(x["reviews_posterieures"]) for x in lignes),
            "ack": sum(bool(x["ack"]) for x in lignes),
            "statuts_manifeste": dict(Counter(x["statut_manifeste"] for x in lignes)),
            "detail": lignes,
        }
        if nom == "escalades":
            out[nom]["par_regle"] = dict(Counter(classer_escalade(esc[s]) for s in slugs))
            out[nom]["deja_escaladees_2026_08_06"] = sorted(
                set(
                    puces(
                        sections_rapport(REVIEWS / "2026-08-06-veille.md")[
                            "Escalades \u2014 ré-ingestion complète"
                        ]
                    )
                )
                & set(slugs)
            )
        if nom == "echeances_perimees":
            out[nom]["date_limite_toujours_passee"] = sum(
                isinstance(x["date_limite_actuelle"], date)
                and x["date_limite_actuelle"] < AUJOURDHUI
                for x in lignes
            )
            ete = set()
            for f in ("2026-08-06-veille.md", "2026-08-28-veille.md"):
                for ligne in sections_rapport(REVIEWS / f)["Échéances passées, source inchangée"]:
                    if m := re.match(r"\| ([a-z0-9-]+) \|", ligne):
                        ete.add(m.group(1))
            out[nom]["deja_signalees_en_aout"] = sorted(ete & set(ech))
        if nom == "injoignables":
            out[nom]["motifs"] = dict(
                Counter(
                    "HTTP 403" if "403" in r else "page vide" if "vide" in r else "autre"
                    for r in inj.values()
                )
            )
    out["retouches"]["bloc_fiche_proxy"] = {
        "fiche_avant_contredit": sum(f["fiche_avant_contient_ancienne_valeur"] for f in fiches_q2),
        "fiche_regeneree": sum(str(f["redige_le_apres"] or "") >= JOUR for f in fiches_q2),
        "fiche_apres_contredit_encore": sum(
            f["fiche_apres_contient_ancienne_valeur"] for f in fiches_q2
        ),
    }
    return out


# ---------------------------------------------------------------------------
# Q5 : pannes
# ---------------------------------------------------------------------------


def q5(manifest: dict, jev_l: list[dict], etc: list[dict]) -> dict:
    refus = [e["maj_refusee"] for e in manifest.values() if "maj_refusee" in e]
    journaux = sorted(LOGS.glob("veille-*.log")) + [
        LOGS / "depuis-veille-hebdo" / f"veille-{JOUR}.log"
    ]
    motifs = {
        "appel au modèle en échec": 0,
        "Jev en panne": 0,
        "Jev : actif": 0,
        "Jev : inactif": 0,
        "réponse vide": 0,
    }
    for j in journaux:
        t = j.read_text(encoding="utf-8")
        for m in motifs:
            motifs[m] += t.count(m)
    notes = [r["p"] for r in jev_l] + [r["garde"] for r in etc if r.get("garde") is not None]
    return {
        "panne_api_memorisee_comme_refus": {
            "code": "veille_update.py:217-229 (etat echec, etape appel) puis "
            "veille_aides.py:299-305 (maj_refusee) et 776-806 (non resoumis) ; "
            "rapport : veille_aides.py:553-556 « non traitée (plafond --max-llm atteint) »",
            "maj_refusee_au_manifeste": dict(Counter(r["etat"] for r in refus)),
            "dont_echec": sum(r["etat"] == "echec" for r in refus),
        },
        "garde_jev_en_panne_rearchive": {
            "code": "veille_update.py:294-305 (p None => pas de suspect => rafraichir_snapshots) ; "
            "veille_update.py:362-367 (_juger rend None sur ErreurDecision) ; banc : "
            "veille_benchmark_etage_c.py:110-116 (garde None)",
            "passages_de_production_avec_jev": 0,
        },
        "noul_vide_lu_comme_zero": {
            "code": "pipeline/decision.py:81-85 (proba rend probabilites.get(option, 0.0) "
            "quand noul est None) ; seule l'ABSENCE de la question lève (172-179)",
            "notes_jev_en_cache": len(notes),
            "notes_a_zero": sum(1 for p in notes if p == 0),
            "note_minimale": min(notes) if notes else None,
        },
        "comptes_dans_les_journaux": {
            "journaux": [str(j.relative_to(BACKEND)) for j in journaux],
            **motifs,
        },
        "echecs_banc_etage_c": [
            {
                "modele": r["modele"],
                "cas": r["cas"],
                "etape": r["etape_echec"],
                "raison": r["raison"][:160],
            }
            for r in etc
            if r["etat"] == "echec"
        ],
    }


# ---------------------------------------------------------------------------
# Q6 : J6 et J7
# ---------------------------------------------------------------------------

DATE_FR = re.compile(
    r"\b(\d{1,2}|1er) (janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)( (20\d\d))?"
)


def indices_j6(slug: str, limite: date) -> dict:
    dossier = DATA / "sources" / slug
    if not dossier.is_dir():
        return {"slug": slug, "texte": 0}
    # La baseline de chaque URL est son snapshot le plus récent.
    par_url: dict[str, Path] = {}
    for p in sorted(dossier.iterdir()):
        if p.suffix == ".md":
            url = parse_front_matter(p.read_text(encoding="utf-8"))[0].get("url")
            if url:
                par_url[url] = p
        elif p.name.endswith(".pdf.meta.yaml"):
            url = (charger_yaml(p.read_text(encoding="utf-8")) or {}).get("url")
            if url:
                par_url[url] = p.with_name(p.name.removesuffix(".meta.yaml"))
    morceaux = []
    for p in par_url.values():
        if p.suffix == ".md":
            morceaux.append(parse_front_matter(p.read_text(encoding="utf-8"))[1])
        elif p.is_file():
            morceaux.append(_pdf_lecture_seule(p.read_bytes()) or "")
    t = sans_accents("\n".join(morceaux))
    annees = {int(a) for a in re.findall(r"\b(20[2-3]\d)\b", t)}
    sans_annee = sum(1 for m in DATE_FR.finditer(t) if not m.group(3))
    posterieures = 0
    for m in DATE_FR.finditer(t):
        if m.group(4):
            try:
                j = 1 if m.group(1) == "1er" else int(m.group(1))
                d = date(int(m.group(4)), MOIS.index(m.group(2)) + 1, j)
            except ValueError:
                continue
            posterieures += d > limite
    return {
        "slug": slug,
        "date_limite": limite.isoformat(),
        "texte": len(t),
        "annee_max_citee": max(annees) if annees else None,
        "dates_posterieures_a_la_limite": posterieures,
        "dates_sans_annee": sans_annee,
        "mot_cloture": bool(re.search(r"clotur|\bclos\b|termine|n'est plus|ferme|suspendu", t)),
    }


def conditions_reingerees(cas: list[dict]) -> list[dict]:
    """Conditions avant / après la ré-ingestion du 2026-10-05 des changements perdus."""
    out = []
    parent = git("rev-parse", f"{COMMIT_PASSAGE}^").strip()
    for f in sorted((LOGS / "depuis-veille-hebdo").glob("ingest-*.log")):
        slug = f.stem.removeprefix("ingest-")
        avant, apres = yaml_a(parent, slug), yaml_a(COMMIT_PASSAGE, slug)
        if not (avant and apres):
            continue
        ia = {c.get("id") for c in avant.get("conditions") or []}
        ib = {c.get("id") for c in apres.get("conditions") or []}
        out.append(
            {
                "slug": slug,
                "conditions_avant": len(ia),
                "conditions_apres": len(ib),
                "ids_ajoutes": len(ib - ia),
                "ids_retires": len(ia - ib),
                "calendrier_change": (avant.get("calendrier") != apres.get("calendrier")),
                "financement_change": (avant.get("financement") != apres.get("financement")),
            }
        )
    return out


def q6(sec: dict[str, list[str]], etc: list[dict], log_txt: str) -> dict:
    ech = []
    for ligne in sec["Échéances passées, source inchangée"]:
        if m := re.match(r"\| ([a-z0-9-]+) \| (\d{4}-\d\d-\d\d) \|", ligne):
            ech.append((m.group(1), date.fromisoformat(m.group(2))))
    j6 = [indices_j6(s, d) for s, d in ech]
    circ = sec["Changements circonscrits"]
    maj_perimee = sum("date limite dépassée" in ligne and ligne.startswith("- ") for ligne in circ)
    esc = puces(sec["Escalades \u2014 ré-ingestion complète"])
    esc_perimee = sum("date limite dépassée" in r for r in esc.values())
    # J7 : conditions apparues ou disparues proposées par le modèle.
    structure_prod = {s: r for s, r in esc.items() if classer_escalade(r) == "C structure"}
    ops = Counter()
    ops_structure: dict[str, Counter] = defaultdict(Counter)
    for slug, bloc in re.findall(
        r"\] ✗ (\S+)[^\n]*\n\s+réponse rejetée : (\{.*?\n\})", log_txt, flags=re.S
    ):
        try:
            rep = json.loads(bloc)
        except json.JSONDecodeError:
            continue
        for c in rep.get("conditions") or []:
            ops[c.get("op")] += 1
            if slug in structure_prod and c.get("op") in ("add", "signaler_disparue"):
                ops_structure[slug][c.get("op")] += 1
    struct_banc: Counter = Counter()
    for r in etc:
        if r["etape_echec"] == "structure":
            struct_banc[r["cas"]] += 1
    return {
        "J6": {
            "echeances_perimees_2026_10_04": len(ech),
            "maj_llm_avec_date_depassee_et_page_modifiee": maj_perimee,
            "escalades_avec_date_depassee": esc_perimee,
            "indices_par_regle_de_texte": {
                "au_moins_une_date_posterieure": sum(
                    x.get("dates_posterieures_a_la_limite", 0) > 0 for x in j6
                ),
                "dates_sans_annee": sum(x.get("dates_sans_annee", 0) > 0 for x in j6),
                "mot_de_cloture": sum(bool(x.get("mot_cloture")) for x in j6),
                "sans_texte": sum(x.get("texte", 0) == 0 for x in j6),
            },
            "detail": j6,
        },
        "J7": {
            "escalades_structure_production": len(structure_prod),
            "slugs": sorted(structure_prod),
            "operations_dans_les_reponses_rejetees_du_journal": dict(ops),
            "conditions_apparues_ou_disparues_par_aide": {
                k: dict(v) for k, v in ops_structure.items()
            },
            "cas_du_banc_escalades_structure_nb_configs": dict(struct_banc.most_common()),
        },
    }


# ---------------------------------------------------------------------------
# Ré-ingestions des changements perdus
# ---------------------------------------------------------------------------


def reingestions() -> list[dict]:
    out = []
    for f in sorted((LOGS / "depuis-veille-hebdo").glob("ingest-*.log")):
        t = f.read_text(encoding="utf-8")
        oks = re.findall(r"OK \u2014 (\d+) tour\(s\), (\d+) appel\(s\).*?\$(\d+\.\d+)", t)
        durees = [int(x) for x in re.findall(r"durée (\d+) s", t)]
        debut = re.search(r" \u2014 (2026-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00) \u2014 ", t)
        murale = None
        if debut:
            from datetime import datetime

            t0 = datetime.fromisoformat(debut.group(1))
            t1 = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC)
            murale = round((t1 - t0).total_seconds())
        out.append(
            {
                "slug": f.stem.removeprefix("ingest-"),
                "appels": int(oks[-1][1]) if oks else None,
                "cout_usd": float(oks[-1][2]) if oks else None,
                "lancements": len(re.findall(r"^={20,}$", t, flags=re.M)) // 2,
                "durees_s": durees,
                "duree_murale_s_debut_a_mtime": murale,
            }
        )
    return out


# ---------------------------------------------------------------------------


def main() -> int:
    SORTIE.mkdir(parents=True, exist_ok=True)
    cas = json.loads((JEV_DIR / f"cas-{JOUR}.json").read_text(encoding="utf-8"))
    lab = lire_etiquettes()
    jev_l = lire_jsonl(JEV_DIR / "jev.jsonl")
    jev = {r["cle"]: r for r in jev_l}
    etc = lire_jsonl(JEV_DIR / "etage-c.jsonl")
    manifest = charger_yaml((DATA / "veille-state.yaml").read_text(encoding="utf-8")) or {}
    sec = sections_rapport(REVIEWS / f"{JOUR}-veille.md")
    journal = LOGS / "depuis-veille-hebdo" / f"veille-{JOUR}.log"
    log_c = lignes_etage_c(journal)

    r1 = q1(cas, lab, jev, jev_l, etc)
    ecrire("q1_manques.json", r1)
    r2 = q2(cas, lab, etc, manifest)
    ecrire("q2_retouches.json", r2)
    rearch = sorted({c["slug"] for c in cas if c["origine"] == "snapshots"})
    r3 = q3(sec, log_c, manifest, gabarit_proxy(rearch))
    r3["reingestions_des_perdus"] = reingestions()
    ecrire("q3_cout.json", r3)
    r4 = q4(sec, manifest, r2["bloc_fiche"]["detail"])
    ecrire("q4_devenir.json", r4)
    r5 = q5(manifest, jev_l, etc)
    ecrire("q5_pannes.json", r5)
    r6 = q6(sec, etc, journal.read_text(encoding="utf-8"))
    r6["J7"]["reingestions_du_2026_10_05"] = conditions_reingerees(cas)
    ecrire("q6_j6_j7.json", r6)

    p = r1["production_2026_10_04_sans_garde"]
    g = r1["garde_sur_resume_de_production"]["seuils_jeu_du_banc_72"]["0.45"]
    lignes = [
        f"faux inchangé (prod 2026-10-04, sans garde) : {p['faux_inchange']['texte']}",
        f"faux inchangé sur le dénominateur du banc (72) : {p['faux_inchange_sur_72']['texte']}",
        f"changements réels perdus sans garde : {p['perdus_parmi_changements_reels']['texte']}",
        f"garde 0,45 : perdus parmi faux inchangé {g['perdus_parmi_faux_inchange']['texte']}",
        f"garde 0,45 : perdus parmi changements réels {g['perdus_parmi_changements_reels']['texte']}",
        f"garde 0,45 : fausses alertes {g['fausses_alertes']['texte']}",
        f"banc étage C cumulé, perdus sans garde : {r1['banc_etage_c_cumule']['perdus_sans_garde']['texte']}",
        f"banc étage C cumulé, perdus avec garde : {r1['banc_etage_c_cumule']['perdus_avec_garde']['texte']}",
    ]
    for cfg, b in r1["banc_etage_c"].items():
        lignes.append(
            f"  {cfg} : sans garde {b['perdus_sans_garde']['texte']} ; avec garde "
            f"{b['perdus_avec_garde_045']['texte']} ; fausses retouches {b['fausses_retouches']['texte']}"
        )
    lignes += [
        f"valeurs retouchées retrouvées dans la page fraîche : "
        f"{r2['controle_valeurs_dans_page_fraiche']['retrouves_exactement']['texte']}",
        f"bloc fiche contredit avant régénération (proxy) : {r2['bloc_fiche']['fiche_avant_contredit_proxy']['texte']}",
        f"étage C 2026-10-04 : {r3['etage_c_journal']['appels']} appels, {r3['etage_c_journal']['cout_usd_somme']} $",
        f"gabarit proxy : {r3['gabarit_proxy']['lignes_retirees_comme_gabarit']['texte']}",
    ]
    (SORTIE / "resume.txt").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print("\n".join(lignes))
    print(f"sorties : {SORTIE.relative_to(BACKEND)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
