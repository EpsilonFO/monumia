"""Mesure : les décisions humaines que le pipeline demande, leur trace, leur coût en temps.

Commande (depuis backend/) :

    uv run python scripts/mesures/file_et_humain.py

Lecture seule. Lit la file d'attente (`data/prospection/file-attente.yaml`) et
ses versions dans git (`git show <commit>:...`), le catalogue `data/aides/` et
son historique, les fiches de `data/reviews/`, l'historique de `facts.yaml`, de
`facts_pending.yaml` et de `veille-state.yaml`, et, s'ils existent, les
journaux de session Claude Code de Félix (`~/.claude/projects/-Users-felixollivier-monumia*/*.jsonl`)
pour dater les réponses de Félix. Aucun appel réseau, aucun appel de modèle.

Écrit seulement dans
`data/reviews/logs/refonte/2026-10-10-file-et-humain-1/` :

- `etat_actuel.json` : statuts, motifs, provenance, contrôles des chiffres cités ;
- `commits_file.tsv` et `transitions.tsv` : la file commit par commit ;
- `decisions_ever.json` : chaque famille de motif, comptée sur toute l'histoire ;
- `reouvertures.tsv` : les dix réouvertures de 88d46d5d et leur suite ;
- `j3.tsv` et `j3_resume.json` : le jeu « garder ou écarter » sur aide ingérée ;
- `par_semaine.tsv` : volumes de bout en bout par semaine ISO ;
- `faits_par_commit.tsv` : entrées et sorties de `facts_pending.yaml` ;
- `sessions_felix.tsv` et `sessions_resume.json` : messages et latences de Félix ;
- `episodes.tsv` : les sept épisodes où Félix a tranché, minutes et objets ;
- `charge_par_creation.tsv` : par jour de création, qui a tranché chaque candidate ;
- `estimation.json` : minutes par semaine par poste, hypothèses écrites ;
- `resume.json` : les chiffres repris dans la note
  (docs/refonte-pipeline/notes/file-et-humain.md).

Les journaux de session ne sont lus que pour compter et dater les messages de
Félix ; aucun texte n'en est recopié dans les sorties.
"""

from __future__ import annotations

import csv
import json
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

BACKEND = Path(__file__).resolve().parents[2]
RACINE = BACKEND.parent
sys.path.insert(0, str(BACKEND / "scripts"))

from pipeline.etat import Tache, indetermine, motif_non_promotion  # noqa: E402

SORTIE = BACKEND / "data/reviews/logs/refonte/2026-10-10-file-et-humain-1"
FILE = "backend/data/prospection/file-attente.yaml"
AIDES = BACKEND / "data/aides"
REVIEWS = BACKEND / "data/reviews"
CHARGEUR = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

# Les commits qui touchent la file, avec leurs parents pour la file (DAG non
# linéaire : 88d46d5d sur main et fdde0102 sur prospection-2026-10 partent tous
# deux de 1d94a758, 0a974ed5 les fusionne). Vérifié par `git log --all --
# <file>` et `git rev-parse <c>^1:<file>`.
COMMITS_FILE: list[tuple[str, str | None]] = [
    ("90009f77", None),
    ("2d3096bd", "90009f77"),
    ("836e21cb", "2d3096bd"),
    ("84bdd821", "836e21cb"),
    ("f032af72", "84bdd821"),
    ("25d57a18", "f032af72"),
    ("b4226e37", "25d57a18"),
    ("57f054d7", "b4226e37"),
    ("1d94a758", "57f054d7"),
    ("88d46d5d", "1d94a758"),
    ("fdde0102", "1d94a758"),
    ("0a974ed5", "fdde0102"),
    ("6d6faf13", "0a974ed5"),
]
#: Second parent pour la file : ce que la fusion apporte de main n'est pas une
#: décision nouvelle, il ne faut pas la compter deux fois.
PARENT2 = {"0a974ed5": "88d46d5d"}

# Familles de motif_ignore, et ce que l'on sait de leur provenance. Les
# provenances viennent du code (qui écrit quoi) et des journaux de session
# (qui a décidé) ; elles sont reprises dans la note avec leurs sources.
FAMILLES = [
    ("lecture_llm", r"^hors périmètre : ", "LLM de lecture + règle de code (fiche._motif_ecart)"),
    (
        "tri_2026_09_22",
        r"^test du destinataire : ",
        "LLM (requalification 2026-09-22), validé par Félix par catégorie",
    ),
    (
        "tri_humain_2026_09_30",
        r"^tri humain du 2026-09-30",
        "proposition Claude, Félix : 157 en bloc + 24 une à une",
    ),
    (
        "requalif_2026_10_04",
        r"^requalification du 2026-10-04",
        "relecture à l'aveugle par sous-agents Claude, Félix : « ok » en bloc",
    ),
    (
        "arbitrage_2026_09_24",
        r"arbitrage humain du 2026-09-24",
        "proposition Claude, Félix : « go pour 1 2 3 et 4 »",
    ),
    ("ingestion_llm", r"^hors périmètre à l'ingestion", "LLM de l'agent d'ingestion"),
    (
        "doublon",
        r"^doublon d'URL",
        "code (balayage, dedoublonner_aides), arbitrages à la main compris",
    ),
]


def famille(motif: str | None) -> str:
    if not motif:
        return "sans_motif"
    for nom, motif_re, _ in FAMILLES:
        if re.search(motif_re, motif):
            return nom
    return "autre"


def wilson(k: int, n: int, z: float = 1.959964) -> list[float] | None:
    """Intervalle de Wilson à 95 %, en proportions arrondies à 4 décimales."""
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def taux(k: int, n: int) -> dict:
    return {"k": k, "n": n, "p": round(k / n, 4) if n else None, "ic95": wilson(k, n)}


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(RACINE), *args], capture_output=True, text=True, check=True
    ).stdout


def semaine(d: date | datetime | str) -> str:
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    if isinstance(d, datetime):
        d = d.date()
    a, s, _ = d.isocalendar()
    return f"{a}-W{s:02d}"


def charger_version(commit: str) -> dict:
    return yaml.load(git("show", f"{commit}:{FILE}"), Loader=CHARGEUR) or {}


def statut(v: dict) -> str:
    return v.get("statut", "a_valider")


def ecrire_tsv(nom: str, lignes: list[dict]) -> None:
    if not lignes:
        (SORTIE / nom).write_text("", encoding="utf-8")
        return
    cles = list(lignes[0].keys())
    with (SORTIE / nom).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cles, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        w.writerows(lignes)


def ecrire_json(nom: str, objet: object) -> None:
    (SORTIE / nom).write_text(
        json.dumps(objet, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# 1. État actuel
# ---------------------------------------------------------------------------


def etat_actuel(file: dict) -> dict:
    n = len(file)
    statuts = Counter(statut(v) for v in file.values())
    ignores = {s: v for s, v in file.items() if statut(v) == "ignore"}
    sans_motif = [s for s, v in ignores.items() if not v.get("motif_ignore")]
    fam_ign = Counter(famille(v.get("motif_ignore")) for v in ignores.values())
    motif_hors_ignore = Counter(
        (statut(v), famille(v.get("motif_ignore")))
        for v in file.values()
        if v.get("motif_ignore") and statut(v) != "ignore"
    )
    av = {s: v for s, v in file.items() if statut(v) == "a_valider"}
    motifs_av: Counter[str] = Counter()
    for v in av.values():
        m = motif_non_promotion(Tache.model_validate(v))
        motifs_av[(m or "promouvable").split(" — ")[0].split(" :")[0]] += 1
    dest_ind = sum(1 for v in av.values() if v.get("destinataire", "indetermine") == "indetermine")
    obj_ind = sum(1 for v in av.values() if v.get("objet", "indetermine") == "indetermine")
    un_des_deux = sum(
        1
        for v in av.values()
        if "indetermine" in (v.get("destinataire", "indetermine"), v.get("objet", "indetermine"))
    )
    regle_ind = sum(
        1
        for v in av.values()
        if indetermine(
            v.get("destinataire", "indetermine"),
            v.get("objet", "indetermine"),
            v.get("categorie_ecart"),
        )
    )
    yaml_ = {p.name[: -len(".yaml")] for p in AIDES.glob("*.yaml")}
    echec = {p.name[: -len(".yaml.echec")] for p in AIDES.glob("*.yaml.echec")}
    ingere_sans_yaml = sorted(
        s for s, v in file.items() if statut(v) == "ingere" and s not in yaml_
    )
    champs = Counter(k for v in file.values() for k in v)
    sm_detail = {
        "par_ajoute_le": Counter(str(file[s].get("ajoute_le")) for s in sans_motif),
        "par_territoire": Counter(file[s].get("territoire") for s in sans_motif),
        "destinataire_objet": Counter(
            f"{file[s].get('destinataire')}/{file[s].get('objet')}" for s in sans_motif
        ),
    }
    return {
        "entrees": n,
        "statuts": dict(statuts),
        "ignore_par_famille": dict(fam_ign),
        "ignore_sans_motif": taux(len(sans_motif), len(ignores)),
        "ignore_sans_motif_detail": {k: dict(c) for k, c in sm_detail.items()},
        "motif_ignore_sur_statut_non_ignore": {
            f"{a}|{b}": c for (a, b), c in motif_hors_ignore.items()
        },
        "a_valider": {
            "n": len(av),
            "destinataire_indetermine": taux(dest_ind, len(av)),
            "objet_indetermine": taux(obj_ind, len(av)),
            "l_un_des_deux_indetermine": taux(un_des_deux, len(av)),
            "indetermine_selon_regle_du_code": taux(regle_ind, len(av)),
            "motif_non_promotion": dict(motifs_av),
            "par_ajoute_le": dict(Counter(str(v.get("ajoute_le")) for v in av.values())),
        },
        "ingere_sans_yaml": {
            "n": len(ingere_sans_yaml),
            "dont_yaml_echec": sum(1 for s in ingere_sans_yaml if s in echec),
            "dont_aucun_fichier": sum(1 for s in ingere_sans_yaml if s not in echec),
            "slugs": ingere_sans_yaml,
        },
        "champs_presents": dict(champs),
        "champ_de_provenance_de_decision": "aucun (Tache n'a ni auteur, ni date de décision ; pipeline/etat.py:153-205)",
    }


# ---------------------------------------------------------------------------
# 2. Historique de la file
# ---------------------------------------------------------------------------


def historique(versions: dict[str, dict]) -> tuple[list[dict], list[dict], dict]:
    lignes, trans = [], []
    for c, p in COMMITS_FILE:
        d, avant = versions[c], versions[p] if p else {}
        autre = versions[PARENT2[c]] if c in PARENT2 else {}
        info = git("log", "-1", "--format=%ad|%an|%s", "--date=iso-strict", c).strip().split("|", 2)
        nouveaux = [s for s in d if s not in avant]
        tr: Counter[str] = Counter()
        for s, v in d.items():
            if s not in avant:
                continue
            a, b = statut(avant[s]), statut(v)
            ma, mb = avant[s].get("motif_ignore"), v.get("motif_ignore")
            if s in autre and statut(autre[s]) == b and autre[s].get("motif_ignore") == mb:
                continue  # apporté tel quel par l'autre parent de la fusion
            if a != b or ma != mb:
                if a != b:
                    tr[f"{a}>{b}"] += 1
                trans.append(
                    {
                        "commit": c,
                        "date": info[0][:10],
                        "slug": s,
                        "de": a,
                        "vers": b,
                        "famille_avant": famille(ma),
                        "famille_apres": famille(mb),
                    }
                )
        lignes.append(
            {
                "commit": c,
                "parent_file": p or "",
                "date": info[0][:10],
                "semaine": semaine(info[0]),
                "auteur": info[1],
                "message": info[2],
                "entrees": len(d),
                **{f"n_{k}": v for k, v in sorted(Counter(statut(v) for v in d.values()).items())},
                "nouvelles": len(nouveaux),
                "nouvelles_par_statut": json.dumps(dict(Counter(statut(d[s]) for s in nouveaux))),
                "transitions": json.dumps(dict(tr)),
            }
        )
    # Chaque famille de motif, comptée sur l'union des versions (une entrée
    # comptée une fois, à la première version qui porte la famille).
    ever: dict[str, dict] = {}
    for c, _ in COMMITS_FILE:
        for s, v in versions[c].items():
            f = (
                famille(v.get("motif_ignore"))
                if statut(v) == "ignore" or v.get("motif_ignore")
                else None
            )
            if f is None:
                continue
            e = ever.setdefault(f, {"slugs": set(), "premier_commit": Counter()})
            if s not in e["slugs"]:
                e["slugs"].add(s)
                e["premier_commit"][c] += 1
    ever_out = {
        f: {"n": len(e["slugs"]), "premier_commit": dict(e["premier_commit"])}
        for f, e in ever.items()
    }
    return lignes, trans, ever_out


def reouvertures(
    versions: dict[str, dict], aides_yaml: set[str], aides_echec: set[str]
) -> list[dict]:
    avant, apres, fin = versions["1d94a758"], versions["88d46d5d"], versions["6d6faf13"]
    sortie = []
    for s, v in apres.items():
        if s in avant and statut(avant[s]) == "ignore" and statut(v) == "valide":
            sortie.append(
                {
                    "slug": s,
                    "famille_motif_avant": famille(avant[s].get("motif_ignore")),
                    "motif_garde_apres_88d46d5d": bool(v.get("motif_ignore")),
                    "statut_6d6faf13": statut(fin[s]),
                    "famille_motif_6d6faf13": famille(fin[s].get("motif_ignore")),
                    "yaml": s in aides_yaml,
                    "yaml_echec": s in aides_echec,
                    "ingestion_debut": (fin[s].get("ingestion") or {}).get("debut"),
                }
            )
    return sortie


def changements_de_sens(versions: dict[str, dict]) -> dict:
    """Entrées dont une décision a été contredite par une décision ultérieure."""
    ordre = [c for c, _ in COMMITS_FILE if c not in ("88d46d5d",)]  # chemin fdde0102 -> 0a974ed5
    trajets: dict[str, list[str]] = defaultdict(list)
    for c in ordre:
        for s, v in versions[c].items():
            st = statut(v)
            if not trajets[s] or trajets[s][-1] != st:
                trajets[s].append(st)
    garde = {"valide", "en_cours", "ingere"}
    contredits = Counter()
    for t in trajets.values():
        for a, b in zip(t, t[1:], strict=False):
            if a == "ingere" and b == "ignore":
                contredits["ingere>ignore"] += 1
            if a == "ignore" and b in garde:
                contredits["ignore>reouverte"] += 1
            if a == "a_valider" and b == "ignore":
                contredits["a_valider>ignore"] += 1
            if a == "echec" and b == "ignore":
                contredits["echec>ignore"] += 1
    aller_retour = sorted(
        s
        for s, t in trajets.items()
        if "ignore" in t and any(x in garde for x in t[t.index("ignore") :])
    )
    return {"transitions_de_sens": dict(contredits), "ignore_puis_garde": aller_retour}


# ---------------------------------------------------------------------------
# 3. Jeu J3/J4
# ---------------------------------------------------------------------------


def _slugs_backtick(texte: str) -> list[str]:
    return re.findall(r"^[-|] `([^`]+)`", texte, re.M)


def _section(texte: str, debut: str, fin: str | None) -> str:
    i = texte.index(debut)
    j = texte.index(fin, i + len(debut)) if fin else len(texte)
    return texte[i:j]


def listes_de_tri() -> dict[str, set[str]]:
    """Les listes des fiches de tri, pour dater le dernier jugement de chaque aide."""
    t22 = (REVIEWS / "2026-09-22-tri-catalogue.md").read_text(encoding="utf-8")
    t22b = (REVIEWS / "2026-09-22-tri-ecartees-a-relire.md").read_text(encoding="utf-8")
    t30 = (REVIEWS / "2026-09-30-proposition-tri.md").read_text(encoding="utf-8")
    t04 = (REVIEWS / "2026-10-04-requalification-jev.md").read_text(encoding="utf-8")

    def ecarter_bloc(t: str) -> set[str]:
        bloc = _section(t, "## Slugs à écarter", "## Notes techniques")
        return set(re.findall(r"^([a-z0-9][a-z0-9-]+)\s{2,}\S", bloc, re.M))

    listes = {
        "t22_retenues": set(_slugs_backtick(_section(t22, "## Retenues", "## Slugs à écarter"))),
        "t22_a_trancher": set(
            _slugs_backtick(_section(t22, "## À trancher à la main", "## Retenues"))
        ),
        "t22_ecarter": ecarter_bloc(t22),
        "t22b_retenues": set(_slugs_backtick(_section(t22b, "## Retenues", "## Slugs à écarter"))),
        "t22b_a_trancher": set(
            _slugs_backtick(_section(t22b, "## À trancher à la main", "## Retenues"))
        ),
        "t22b_ecarter": ecarter_bloc(t22b),
        "t30_ecarter": set(_slugs_backtick(_section(t30, "## ÉCARTER", "## À REGARDER"))),
        "t30_garder": set(_slugs_backtick(_section(t30, "## GARDER", None))),
        "t04_b1_sortir": set(_slugs_backtick(_section(t04, "### B1.", "### B2."))),
        "t04_b2_rouvrir": set(_slugs_backtick(_section(t04, "### B2.", "### B3."))),
        "t04_a1_rouvrir": set(_slugs_backtick(_section(t04, "### A1.", "### A2."))),
        "t04_b3_doutes": set(_slugs_backtick(_section(t04, "### B3.", None))),
    }
    # Les 24 « à regarder » du 2026-09-30, dans l'ordre de la fiche, et la
    # réponse de Félix, dans le même ordre (session afbc9d8a, 2026-09-30T07:43:59Z).
    regard = re.findall(r"^\| `([^`]+)` \|", _section(t30, "## À REGARDER", "## GARDER"), re.M)
    reponse = [
        "non",
        "oui",
        "oui",
        "non",
        "non",
        "oui",
        "oui",
        "oui",
        "non",
        "oui",
        "non",
        "oui",
        "oui",
        "oui",
        "oui",
        "oui",
        "non",
        "oui",
        "oui",
        "oui",
        "non",
        "non",
        "oui",
        "oui",
    ]
    if len(regard) == len(reponse):
        listes["t30_regarder_oui_felix"] = {
            s for s, r in zip(regard, reponse, strict=True) if r == "oui"
        }
        listes["t30_regarder_non_felix"] = {
            s for s, r in zip(regard, reponse, strict=True) if r == "non"
        }
    return listes


def jeu_j3(file: dict, listes: dict[str, set[str]]) -> tuple[list[dict], dict]:
    yaml_ = {p.name[: -len(".yaml")] for p in AIDES.glob("*.yaml")}
    echec = {p.name[: -len(".yaml.echec")] for p in AIDES.glob("*.yaml.echec")}
    deux = yaml_ & echec
    lignes = []
    ordre = [
        "t04_b1_sortir",
        "t04_b2_rouvrir",
        "t04_a1_rouvrir",
        "t30_regarder_non_felix",
        "t30_regarder_oui_felix",
        "t30_ecarter",
        "t30_garder",
        "t22b_ecarter",
        "t22b_retenues",
        "t22b_a_trancher",
        "t22_ecarter",
        "t22_retenues",
        "t22_a_trancher",
    ]
    for s in sorted(yaml_ | echec):
        v = file.get(s)
        fam = famille(v.get("motif_ignore")) if v else "hors_file"
        st = statut(v) if v else "hors_file"
        if s in deux:
            nature = "exclue_deux_formes"
        elif s in yaml_:
            nature = "gardee"
        elif v is None:
            nature = "ecartee_hors_file"
        elif fam == "doublon":
            nature = "doublon"
        elif st == "echec":
            nature = "echec_ingestion"
        elif st == "ingere":
            nature = "ecartee_sans_trace_file"
        elif fam == "sans_motif":
            nature = "ecartee_sans_motif"
        else:
            nature = "ecartee"
        dernier = next((n for n in ordre if s in listes.get(n, set())), "")
        lignes.append(
            {
                "slug": s,
                "nature": nature,
                "statut_file": st,
                "famille_motif": fam,
                "dernier_lot_de_tri": dernier,
                "dans_file": v is not None,
            }
        )
    garde = [x for x in lignes if x["nature"] == "gardee"]
    ecart = [x for x in lignes if x["nature"].startswith("ecartee")]
    resume = {
        "yaml": len(yaml_),
        "yaml_echec": len(echec),
        "deux_formes_exclues": len(deux),
        "par_nature": dict(Counter(x["nature"] for x in lignes)),
        "gardees_par_dernier_lot": dict(Counter(x["dernier_lot_de_tri"] or "aucun" for x in garde)),
        "gardees_dans_file": sum(1 for x in garde if x["dans_file"]),
        "ecartees_par_famille": dict(Counter(x["famille_motif"] for x in ecart)),
        "ecartees_par_dernier_lot": dict(
            Counter(x["dernier_lot_de_tri"] or "aucun" for x in ecart)
        ),
    }
    # Bruit connu : ce que la relecture du 2026-10-04 a retourné, rapporté au
    # lot qui avait posé l'étiquette (borne basse : seuls les désaccords
    # francs avec Jev ont été relus).
    retournes = Counter()
    for nom_liste in ("t04_b1_sortir", "t04_b2_rouvrir"):
        for s in listes.get(nom_liste, set()):
            v = file.get(s)
            avant = "hors_file"
            for lot in ordre[3:]:
                if s in listes.get(lot, set()):
                    avant = lot
                    break
            retournes[
                f"{nom_liste}|dernier_lot_avant={avant}|famille_actuelle={famille(v.get('motif_ignore')) if v else 'hors_file'}"
            ] += 1
    resume["retournes_le_2026_10_04"] = dict(retournes)
    resume["taille_listes"] = {k: len(v) for k, v in listes.items()}
    return lignes, resume


# ---------------------------------------------------------------------------
# 4. Volumes par semaine
# ---------------------------------------------------------------------------


def catalogue_par_semaine(debut: date, fin: date) -> dict[str, dict]:
    brut = git("log", "--first-parent", "--format=%H|%ad", "--date=short", "HEAD").split()
    commits = [(h, date.fromisoformat(d)) for h, d in (x.split("|") for x in brut)]
    sortie: dict[str, dict] = {}
    j = debut - timedelta(days=debut.weekday())
    precedent: tuple[set[str], set[str]] | None = None
    while j <= fin:
        fin_sem = j + timedelta(days=6)
        cands = [h for h, d in commits if d <= fin_sem]
        if not cands:
            j += timedelta(days=7)
            continue
        h = cands[0]  # le plus récent sur la lignée first-parent
        noms = git("ls-tree", "--name-only", h, "backend/data/aides/").split()
        y = {Path(n).name[:-5] for n in noms if n.endswith(".yaml")}
        e = {Path(n).name[:-11] for n in noms if n.endswith(".yaml.echec")}
        ligne = {"commit_ref": h[:8], "yaml": len(y), "yaml_echec": len(e)}
        if precedent:
            ligne["yaml_nouveaux"] = len(y - precedent[0])
            ligne["yaml_sortis"] = len(precedent[0] - y)
            ligne["echec_nouveaux"] = len(e - precedent[1])
        sortie[semaine(j)] = ligne
        precedent = (y, e)
        j += timedelta(days=7)
    return sortie


def commits_donnees() -> dict[str, Counter]:
    """Commits sans fusion touchant backend/data, par semaine et auteur, avec lignes du diff."""
    brut = git(
        "log",
        "HEAD",
        "--no-merges",
        "--since=2026-08-01",
        "--format=@@%h|%an|%ad",
        "--date=short",
        "--numstat",
        "--",
        "backend/data",
    )
    par_sem: dict[str, Counter] = defaultdict(Counter)
    courant = None
    for ligne in brut.splitlines():
        if ligne.startswith("@@"):
            h, auteur, d = ligne[2:].split("|")
            cle = "felix" if auteur in ("EpsilonFO", "Félix le vibecodeur") else "autre"
            courant = (semaine(d), cle)
            par_sem[courant[0]][f"commits_{cle}"] += 1
            continue
        if not ligne.strip() or courant is None:
            continue
        a, s, chemin = ligne.split("\t", 2)
        if a == "-":
            continue
        n = int(a) + int(s)
        if "/data/aides/" in chemin:
            par_sem[courant[0]]["lignes_aides"] += n
        elif chemin.endswith(("facts.yaml", "facts_pending.yaml")):
            par_sem[courant[0]]["lignes_faits"] += n
        elif chemin.endswith("file-attente.yaml"):
            par_sem[courant[0]]["lignes_file"] += n
        elif "/data/sources/" in chemin:
            par_sem[courant[0]]["lignes_sources"] += n
        elif "/data/reviews/" in chemin:
            par_sem[courant[0]]["lignes_reviews"] += n
        else:
            par_sem[courant[0]]["lignes_autres"] += n
    return par_sem


def fiches_par_semaine() -> dict[str, Counter]:
    noms = git("ls-files", "backend/data/reviews").split()
    sur_disque = {p.name for p in REVIEWS.glob("*.md")}
    par_sem: dict[str, Counter] = defaultdict(Counter)
    for nom in sur_disque | {Path(n).name for n in noms if n.endswith(".md")}:
        m = re.match(r"(\d{4}-\d{2}-\d{2})-(.*)\.md$", nom)
        if not m:
            continue
        reste = m.group(2)
        if reste.startswith("ingest-"):
            cle = "fiches_ingestion"
        elif reste.startswith("prospection-"):
            cle = "fiches_prospection"
        elif "veille" in reste:
            cle = "fiches_veille"
        elif re.search(r"tri|requalif|proposition|doublon|arbitr", reste):
            cle = "fiches_tri"
        else:
            cle = "fiches_autres"
        par_sem[semaine(m.group(1))][cle] += 1
    return par_sem


def file_par_semaine(versions: dict[str, dict], file: dict) -> dict[str, Counter]:
    par_sem: dict[str, Counter] = defaultdict(Counter)
    for v in file.values():
        par_sem[semaine(str(v.get("ajoute_le")))]["candidates_creees"] += 1
        ing = v.get("ingestion") or {}
        if ing.get("debut"):
            w = semaine(ing["debut"])
            par_sem[w]["ingestions_lancees"] += 1
            par_sem[w]["tentatives"] += int(ing.get("tentatives") or 0)
            par_sem[w][f"ingestion_issue_{statut(v)}"] += 1
    # Décisions d'écart datées par le commit qui les porte (retard possible
    # sur la date réelle : une décision prise dans le working tree n'a de date
    # qu'à son commit).
    for c, p in COMMITS_FILE:
        d, avant = versions[c], versions[p] if p else {}
        autre = versions[PARENT2[c]] if c in PARENT2 else {}
        w = semaine(git("log", "-1", "--format=%ad", "--date=short", c).strip())
        for s, v in d.items():
            if s in autre and statut(autre[s]) == "ignore":
                continue
            if statut(v) == "ignore" and (s not in avant or statut(avant[s]) != "ignore"):
                par_sem[w][f"ignore_{famille(v.get('motif_ignore'))}"] += 1
    return par_sem


# ---------------------------------------------------------------------------
# 5. Faits et veille
# ---------------------------------------------------------------------------


def _cles_yaml(commit: str, chemin: str) -> set[str]:
    try:
        texte = git("show", f"{commit}:{chemin}")
    except subprocess.CalledProcessError:
        return set()
    d = yaml.load(texte, Loader=CHARGEUR) or {}
    return set(d) if isinstance(d, dict) else set()


def faits_par_commit() -> list[dict]:
    brut = git(
        "log",
        "HEAD",
        "--no-merges",
        "--since=2026-08-01",
        "--format=%h|%ad|%an",
        "--date=short",
        "--",
        "backend/data/facts.yaml",
        "backend/data/facts_pending.yaml",
    ).split("\n")
    sortie = []
    for ligne in brut:
        if not ligne.strip():
            continue
        h, d, auteur = ligne.split("|")
        f_apres = _cles_yaml(h, "backend/data/facts.yaml")
        f_avant = _cles_yaml(f"{h}^", "backend/data/facts.yaml")
        p_apres = _cles_yaml(h, "backend/data/facts_pending.yaml")
        p_avant = _cles_yaml(f"{h}^", "backend/data/facts_pending.yaml")
        sortis = p_avant - p_apres
        sortie.append(
            {
                "commit": h,
                "date": d,
                "semaine": semaine(d),
                "auteur": auteur,
                "faits": len(f_apres),
                "pending": len(p_apres),
                "pending_entres": len(p_apres - p_avant),
                "pending_sortis_vers_facts": len(sortis & f_apres),
                "pending_sortis_ailleurs": len(sortis - f_apres),
                "facts_ajoutes": len(f_apres - f_avant),
                "facts_ajoutes_sans_pending": len((f_apres - f_avant) - p_avant),
                "facts_retires": len(f_avant - f_apres),
            }
        )
    return sortie


def veille_acquittements() -> dict:
    brut = git(
        "log", "HEAD", "--format=%h|%ad", "--date=short", "--", "backend/data/veille-state.yaml"
    )
    par_commit = {}
    for ligne in brut.split():
        h, d = ligne.split("|")
        texte = git("show", f"{h}:backend/data/veille-state.yaml")
        par_commit[f"{h} {d}"] = len(re.findall(r"^  ack:", texte, re.M))
    actuel = yaml.load((BACKEND / "data/veille-state.yaml").read_text(), Loader=CHARGEUR) or {}
    return {
        "ack_par_commit": par_commit,
        "statuts_actuels": dict(Counter(v.get("status") for v in actuel.values())),
        "entrees_avec_maj_refusee": sum(1 for v in actuel.values() if v.get("maj_refusee")),
        "rapports_veille": sorted(p.name for p in REVIEWS.glob("*-veille.md")),
    }


# ---------------------------------------------------------------------------
# 6. Sessions de Félix (journaux Claude Code, lecture seule)
# ---------------------------------------------------------------------------

MOTS_PIPELINE = re.compile(
    r"prospecter\.py|ingerer\.py|balayage\.py|veille_aides\.py|dedoublonner_aides\.py|"
    r"fusionner_faits\.py|retyper_faits\.py|requalif|file-attente\.yaml|facts_pending|"
    r"ingest-aide|typer-aides|lint_aides_data\.py|rediger_fiches\.py"
)
SESSION_COURANTE = "2e3e5583-2e50-4f96-aef5-ca962a6eb567"


_BALISES_IDE = re.compile(r"<(ide_opened_file|ide_selection|system-reminder)>.*?</\1>", re.S)


def _texte_utilisateur(m: dict) -> str | None:
    """Le texte tapé par Félix, ou None (résultat d'outil, message d'agent, résumé…)."""
    c = m.get("content")
    if isinstance(c, list):
        if any(b.get("type") == "tool_result" for b in c if isinstance(b, dict)):
            return None
        c = " ".join(
            b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"
        )
    if not isinstance(c, str):
        return None
    if "<command-name>" in c:
        return c  # une commande slash tapée par Félix
    c = _BALISES_IDE.sub("", c).strip()
    exclus = (
        "<",
        "Another Claude session",
        "This session is being continued",
        "[Request interrupted",
        "Caveat:",
        "Base directory for this skill",
        "Continue from where you left off",
        "Your response above was cut off",
    )
    if not c or c.startswith(exclus):
        return None
    return c


#: Fichiers que Félix avait ouverts dans l'éditeur au moment d'écrire à
#: Claude (balises `<ide_opened_file>`), par nature : seul indice, faible, de
#: ce qu'il relit lui-même. Rempli par `sessions_felix`.
OUVERTURES_IDE: Counter[str] = Counter()
_BALISE_OUVERTURE = re.compile(r"<ide_(?:opened_file|selection)>(.*?)</ide_", re.S)


def _compter_ouvertures(m: dict, compteur: Counter[str]) -> None:
    c = m.get("content")
    if isinstance(c, list):
        c = " ".join(
            b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"
        )
    if not isinstance(c, str):
        return
    for t in _BALISE_OUVERTURE.findall(c):
        mm = re.search(r"/(backend/data/\S+)", t)
        if not mm:
            continue
        chemin = mm.group(1)
        if "-ingest-" in chemin:
            compteur["fiche_ingestion"] += 1
        elif "-prospection-" in chemin:
            compteur["fiche_prospection"] += 1
        elif "/reviews/" in chemin:
            compteur["autre_fiche"] += 1
        elif "file-attente" in chemin:
            compteur["file_attente"] += 1
        elif "facts_pending" in chemin:
            compteur["facts_pending"] += 1
        elif "/aides/" in chemin:
            compteur["yaml_aide"] += 1
        else:
            compteur["autre_data"] += 1


def sessions_felix(depuis: str = "2026-08-01") -> tuple[list[dict], dict]:
    racine = Path.home() / ".claude/projects"
    if not racine.exists():
        return [], {"absent": str(racine)}
    lignes = []
    for f in sorted(racine.glob("-Users-felixollivier-monumia*/*.jsonl")):
        if f.stem == SESSION_COURANTE:
            continue
        pipeline = False
        evenements: list[tuple[str, str, str | None]] = []
        with f.open(encoding="utf-8", errors="replace") as fh:
            for brut in fh:
                try:
                    o = json.loads(brut)
                except json.JSONDecodeError:
                    continue
                if o.get("isSidechain"):
                    continue
                m = o.get("message") or {}
                ts = o.get("timestamp")
                if not ts or not isinstance(m, dict):
                    continue
                role = m.get("role")
                if role == "assistant":
                    for b in m.get("content") or []:
                        if (
                            isinstance(b, dict)
                            and b.get("type") == "tool_use"
                            and MOTS_PIPELINE.search(json.dumps(b.get("input"), ensure_ascii=False))
                        ):
                            pipeline = True
                    evenements.append((ts, "assistant", None))
                elif role == "user":
                    _compter_ouvertures(m, OUVERTURES_IDE)
                    t = _texte_utilisateur(m)
                    if t is not None:
                        if MOTS_PIPELINE.search(t):
                            pipeline = True
                        evenements.append((ts, "felix", t))
        for i, (ts, qui, t) in enumerate(evenements):
            if qui != "felix" or ts < depuis:
                continue
            prec = next((e[0] for e in reversed(evenements[:i]) if e[1] == "assistant"), None)
            lat = None
            if prec:
                lat = (
                    datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    - datetime.fromisoformat(prec.replace("Z", "+00:00"))
                ).total_seconds() / 60
            lignes.append(
                {
                    "session": f.stem[:8],
                    "dossier": f.parent.name.replace("-Users-felixollivier-monumia", "")
                    or "(racine)",
                    "horodatage": ts,
                    "semaine": semaine(ts),
                    "session_pipeline": pipeline,
                    "latence_min": round(lat, 2) if lat is not None else "",
                    "caracteres": len(t or ""),
                }
            )
    # Agrégats : les latences sont plafonnées (au-delà, Félix était ailleurs).
    resume: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    for x in lignes:
        r = resume[x["semaine"]]
        cle = "pipeline" if x["session_pipeline"] else "autre"
        r[f"messages_{cle}"] += 1
        if x["latence_min"] != "":
            for plafond in (5, 15, 30):
                r[f"minutes_{cle}_plafond{plafond}"] += min(float(x["latence_min"]), plafond)
    return lignes, {
        k: {kk: round(vv, 1) for kk, vv in v.items()} for k, v in sorted(resume.items())
    }


# Les épisodes où le pipeline a obtenu une décision de Félix, repérés à la
# lecture des journaux (session, fenêtre UTC). `objets` : ce qui a été tranché,
# compté dans la file ou dans la fiche citée. `mode` : comment Félix a tranché.
EPISODES = [
    (
        "7512812b",
        "2026-09-17T14:06",
        "2026-09-17T16:10",
        "doublons de facts_pending (les 502 faits en attente)",
        502,
        "Claude analyse tout, Félix corrige à la main sur ce retour (« J'ai traité le sujet grâce à ton retour »)",
    ),
    (
        "0d752ad2",
        "2026-09-22T07:00",
        "2026-09-22T10:10",
        "tri du catalogue 2026-09-22 (950 lues, puis 471 écartées relues)",
        950,
        "LLM juge, Félix conteste deux catégories (rénovation énergétique, prix), fait relancer, applique",
    ),
    (
        "0b9a25af",
        "2026-09-23T20:37",
        "2026-09-23T20:47",
        "320 problèmes des fiches, dont 18 non-dispositifs et 8 doublons écartés",
        320,
        "« go pour 1 2 3 et 4 », en bloc",
    ),
    (
        "afbc9d8a",
        "2026-09-30T07:22",
        "2026-09-30T07:44",
        "tri des 181 aides du balayage du 2026-09-29",
        181,
        "157 approuvées en bloc, 24 tranchées une à une (8 non, 16 oui)",
    ),
    (
        "d6fb7845",
        "2026-10-04T12:02",
        "2026-10-04T13:00",
        "150 candidates a_valider (BFC 16, Occitanie 77, 29/35/56 57)",
        150,
        "« lis directement et fais moi ton arbitrage », puis « oui et oui » ; Félix lance `ignorer --tout`",
    ),
    (
        "d2ecd4a8",
        "2026-10-04T17:17",
        "2026-10-04T17:22",
        "fiche de requalification Jev (2 + 3 + 28 + 8 + 16 lignes)",
        57,
        "« ok », aucune ligne rayée",
    ),
    (
        "e63976a4",
        "2026-10-07T10:20",
        "2026-10-07T10:48",
        "20 faits en attente + 1 aide écartée",
        21,
        "« je valide. Fais selon toi le plus logique pour la section 3 »",
    ),
]


def episodes(sess: list[dict]) -> list[dict]:
    sortie = []
    for sid, debut, fin, quoi, n, mode in EPISODES:
        msgs = [x for x in sess if x["session"] == sid and debut <= x["horodatage"][:16] <= fin]
        lat = [float(x["latence_min"]) for x in msgs if x["latence_min"] != ""]
        duree = (datetime.fromisoformat(fin) - datetime.fromisoformat(debut)).total_seconds() / 60
        sortie.append(
            {
                "session": sid,
                "debut_utc": debut,
                "fin_utc": fin,
                "objet": quoi,
                "objets_tranches": n,
                "mode": mode,
                "messages_felix": len(msgs),
                "latences_min_plafond15": round(sum(min(x, 15) for x in lat), 1),
                "duree_fenetre_min": round(duree),
                "min_par_objet_plafond15": round(sum(min(x, 15) for x in lat) / n, 3) if n else "",
            }
        )
    return sortie


#: Hypothèses de temps unitaire (minutes), écrites ici pour être discutées.
#: `bas` : Félix approuve une proposition déjà rédigée (ce que les épisodes
#: mesurés montrent : 0,06 à 0,31 min par objet) ; `haut` : Félix fait lui-même
#: le contrôle que la documentation lui attribue.
HYPOTHESES = {
    "file_candidate": {"bas": 0.1, "central": 0.5, "haut": 2.0},
    "fiche_ingestion": {"bas": 0.1, "central": 3.0, "haut": 6.5},
    "fait_en_attente": {"bas": 0.1, "central": 1.0, "haut": 3.0},
    "tri_post_ingestion": {"bas": 0.1, "central": 0.5, "haut": 2.0},
}
#: Part des candidates qu'aucune règle ne tranche, mesurée sur le lot du
#: 2026-10-04 (cf. `charge_par_creation.tsv`) ; recalculée dans `estimation`.
FENETRE = ("2026-W37", "2026-W40")


def estimation(table: list[dict], charge: list[dict], tri_lots: dict[str, int]) -> dict:
    """Minutes par semaine demandées à Félix, sur la fenêtre active, par poste."""
    lignes = [x for x in table if FENETRE[0] <= x["semaine"] <= FENETRE[1]]
    nsem = len(lignes)
    somme = lambda cle: sum(float(x.get(cle, 0) or 0) for x in lignes)  # noqa: E731
    lot = next(x for x in charge if x["ajoute_le"] == "2026-10-04")
    code = sum(
        v
        for k, v in lot.items()
        if k.startswith(("ecart_lecture_llm", "ecart_ingestion_llm", "ecart_doublon"))
    )
    part_humaine = (lot["total"] - code) / lot["total"]
    volumes = {
        "file_candidate": somme("candidates_creees") * part_humaine / nsem,
        "fiche_ingestion": somme("fiches_ingestion") / nsem,
        "fait_en_attente": (somme("pending_sortis_vers_facts") + somme("pending_sortis_ailleurs"))
        / nsem,
        "tri_post_ingestion": sum(tri_lots.values()) / nsem,
    }
    postes = {}
    for cle, vol in volumes.items():
        postes[cle] = {
            "volume_par_semaine": round(vol, 1),
            **{h: round(vol * t, 0) for h, t in HYPOTHESES[cle].items()},
        }
    total = {h: sum(p[h] for p in postes.values()) for h in ("bas", "central", "haut")}
    return {
        "fenetre": FENETRE,
        "semaines": nsem,
        "part_candidates_sans_regle_lot_2026_10_04": taux(lot["total"] - code, lot["total"]),
        "postes": postes,
        "total_minutes_par_semaine": total,
        "hypotheses_min_par_objet": HYPOTHESES,
        "tri_post_ingestion_lots": tri_lots,
    }


def promotion(v: dict) -> str:
    """Qui a fait passer la tâche en `valide`, d'après la date de l'ingestion."""
    ing = v.get("ingestion") or {}
    d = str(ing.get("debut") or "")[:10]
    if not d:
        return ""
    if d <= "2026-09-20":
        return "auto_sans_test (valider_en_attente promouvait tout)"
    if d <= "2026-09-30":
        return "auto_regle_promouvables (balayage.py)"
    if d == "2026-10-04":
        return "commande_valider sur arbitrage de Claude"
    return "reouverture requalification 2026-10-04"


def charge_par_creation(file: dict) -> list[dict]:
    """Par jour de création : qui a tranché chaque candidate."""
    par: dict[str, Counter] = defaultdict(Counter)
    for v in file.values():
        j = str(v.get("ajoute_le"))
        st, fam = statut(v), famille(v.get("motif_ignore"))
        if st == "a_valider":
            cle = "en_attente_humain"
        elif st == "ignore":
            cle = f"ecart_{fam}"
        else:
            cle = f"promue:{promotion(v) or 'sans_bloc_ingestion'}"
        par[j][cle] += 1
    cles = sorted({k for c in par.values() for k in c})
    return [
        {"ajoute_le": j, "total": sum(par[j].values()), **{k: par[j][k] for k in cles}}
        for j in sorted(par)
    ]


# ---------------------------------------------------------------------------


def main() -> int:
    SORTIE.mkdir(parents=True, exist_ok=True)
    versions = {c: charger_version(c) for c, _ in COMMITS_FILE}
    chemin_file = BACKEND / "data/prospection/file-attente.yaml"
    file = yaml.load(chemin_file.read_text(encoding="utf-8"), Loader=CHARGEUR) or {}
    identique_head = (
        git("hash-object", str(chemin_file)).strip() == git("rev-parse", f"HEAD:{FILE}").strip()
    )

    etat = etat_actuel(file)
    etat["fichier_identique_a_HEAD"] = identique_head
    ecrire_json("etat_actuel.json", etat)

    lignes, trans, ever = historique(versions)
    ecrire_tsv("commits_file.tsv", lignes)
    ecrire_tsv("transitions.tsv", trans)
    ecrire_json("decisions_ever.json", ever)

    aides_yaml = {p.name[:-5] for p in AIDES.glob("*.yaml")}
    aides_echec = {p.name[:-11] for p in AIDES.glob("*.yaml.echec")}
    reo = reouvertures(versions, aides_yaml, aides_echec)
    ecrire_tsv("reouvertures.tsv", reo)
    sens = changements_de_sens(versions)

    # Les 25 aides « ingere » sans aucun fichier : supprimées par quel commit ?
    suppressions = Counter()
    for s in etat["ingere_sans_yaml"]["slugs"]:
        if s in aides_echec:
            continue
        log = (
            git(
                "log",
                "HEAD",
                "--diff-filter=D",
                "--format=%h %ad %s",
                "--date=short",
                "--",
                f"backend/data/aides/{s}.yaml",
            )
            .strip()
            .split("\n")[0]
        )
        suppressions[log] += 1

    listes = listes_de_tri()
    j3, j3_resume = jeu_j3(file, listes)
    ecrire_tsv("j3.tsv", j3)
    ecrire_json("j3_resume.json", j3_resume)

    cat = catalogue_par_semaine(date(2026, 8, 1), date(2026, 10, 10))
    com = commits_donnees()
    fic = fiches_par_semaine()
    fps = file_par_semaine(versions, file)
    faits = faits_par_commit()
    ecrire_tsv("faits_par_commit.tsv", faits)
    faits_sem: dict[str, Counter] = defaultdict(Counter)
    for x in faits:
        for k in (
            "pending_entres",
            "pending_sortis_vers_facts",
            "pending_sortis_ailleurs",
            "facts_ajoutes_sans_pending",
        ):
            faits_sem[x["semaine"]][k] += x[k]
    sess, sess_resume = sessions_felix()
    ecrire_tsv("sessions_felix.tsv", sess)
    ecrire_json("sessions_resume.json", sess_resume)
    epi = episodes(sess)
    ecrire_tsv("episodes.tsv", epi)
    charge = charge_par_creation(file)
    ecrire_tsv("charge_par_creation.tsv", charge)

    semaines = sorted(set(cat) | set(com) | set(fic) | set(fps) | set(faits_sem) | set(sess_resume))
    semaines = [w for w in semaines if "2026-W31" <= w <= "2026-W41"]
    cles: list[str] = []
    table = []
    for w in semaines:
        ligne: dict = {"semaine": w}
        for source in (
            cat.get(w, {}),
            fps.get(w, {}),
            fic.get(w, {}),
            com.get(w, {}),
            faits_sem.get(w, {}),
            sess_resume.get(w, {}),
        ):
            ligne.update(source)
        table.append(ligne)
        for k in ligne:
            if k not in cles:
                cles.append(k)
    table = [{k: x.get(k, 0) for k in cles} for x in table]
    ecrire_tsv("par_semaine.tsv", table)

    veille = veille_acquittements()

    # Lots de tri après ingestion dans la fenêtre : aides relues, d'après les
    # fiches (2026-09-22 : 950 puis 471 ; 2026-09-30 : 181 ; 2026-10-04 : 78
    # désaccords relus, cf. 2026-10-04-requalification-jev.md l. 7).
    tri_lots = {
        "2026-09-22 passage 1": 950,
        "2026-09-22 passage 2": 471,
        "2026-09-30": 181,
        "2026-10-04": 78,
    }
    est = estimation(table, charge, tri_lots)
    ecrire_json("estimation.json", est)

    # Ingérées (un YAML a été écrit) puis écartées.
    ing_puis_ecart = Counter(
        famille(v.get("motif_ignore"))
        for v in file.values()
        if statut(v) == "ignore"
        and v.get("ingestion")
        and not (v["ingestion"].get("motif_echec") or "")
    )
    avec_bloc = sum(1 for v in file.values() if v.get("ingestion"))
    sans_echec = sum(
        1 for v in file.values() if v.get("ingestion") and not v["ingestion"].get("motif_echec")
    )

    resume = {
        "file": {
            "entrees": etat["entrees"],
            "statuts": etat["statuts"],
            "ignore_sans_motif": etat["ignore_sans_motif"],
            "a_valider": etat["a_valider"],
            "ingere_sans_yaml": {k: v for k, v in etat["ingere_sans_yaml"].items() if k != "slugs"},
            "suppressions_des_ingere_sans_fichier": dict(suppressions),
            "identique_a_HEAD": identique_head,
        },
        "decisions_ever": ever,
        "reouvertures_88d46d5d": reo,
        "changements_de_sens": {
            "transitions": sens["transitions_de_sens"],
            "ignore_puis_garde_n": len(sens["ignore_puis_garde"]),
            "ignore_puis_garde": sens["ignore_puis_garde"],
        },
        "j3": j3_resume,
        "veille": veille,
        "episodes": epi,
        "charge_par_creation": charge,
        "estimation": est,
        "ouvertures_ide_felix": dict(OUVERTURES_IDE),
        "ingerees_puis_ecartees": {
            "entrees_avec_bloc_ingestion": avec_bloc,
            "dont_sans_motif_echec": sans_echec,
            "dont_ignore_par_famille": dict(ing_puis_ecart),
            "taux": taux(sum(ing_puis_ecart.values()), sans_echec),
        },
    }
    ecrire_json("resume.json", resume)
    print(json.dumps(resume, ensure_ascii=False, indent=1, default=str)[:6000])
    print(f"\nSorties : {SORTIE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
