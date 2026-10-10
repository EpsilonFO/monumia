"""Ligne de base du test du destinataire, hors ligne, sur les caches du banc.

    cd backend && PYTHONDONTWRITEBYTECODE=1 uv run python scripts/mesures/destinataire.py

Aucun appel réseau, aucun modèle, aucune écriture hors du dossier de sortie
`data/reviews/logs/refonte/2026-10-10-destinataire-1/` (option `--sortie`).
Les étiquettes se reconstruisent depuis git (`git ls-tree`, `git show`,
`git cat-file --batch`), jamais depuis l'arbre de travail ; les verdicts des
modèles viennent des caches copiés dans `data/reviews/logs/benchmark-destinataire/`.

Produit :

- `resultats.json` : tous les chiffres de la note, chacun avec k, n et son
  intervalle de Wilson à 95 % ;
- `rapport.txt` : les mêmes chiffres, lisibles ;
- `etiquettes-<commit>.csv` : le jeu étiqueté à chaque état (slug, étiquette,
  origine, motif, provenance) ;
- `changements.csv` : les cas qui changent d'étiquette entre 4ae34348 et fb918d57 ;
- `cas.csv` : une ligne par cas du banc (notes de Jev, issues du LLM, bande de
  production, issue simulée, sous-groupes, taille du texte, jetons) ;
- `validation-croisee.csv` : chaque pli de chaque tirage.

La logique d'étiquetage est celle de `benchmark_destinataire.cas_etiquetes`,
rejouée à un commit donné ; la règle de production est celle de
`prospection.arbitre.bande` et `prospection.lecture._appliquer_arbitrage`.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import statistics
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS.parent))
sys.path.insert(0, str(SCRIPTS))

import benchmark_destinataire as banc
from ingestion.contexte import section
from prospection import arbitre
from veille_collect import _pdftotext

BACKEND = SCRIPTS.parent
RACINE = BACKEND.parent
CACHE = BACKEND / "data" / "reviews" / "logs" / "benchmark-destinataire"
ENTREES = BACKEND / "data" / "reviews" / "logs" / "refonte-entrees"
REQUALIF = ENTREES / "d2ecd4a8-requalification-2026-10-04"
SORTIE_DEFAUT = BACKEND / "data" / "reviews" / "logs" / "refonte" / "2026-10-10-destinataire-1"

AVANT = "4ae34348"  # veille de la requalification 88d46d5d
APRES = "fb918d57"
BANC_0410 = "52bf6963"  # HEAD quand le banc du 2026-10-04 a tourné (16 h 14)
BANC_1007 = "b9f3f43e"  # HEAD de main quand le banc du 2026-10-07 a tourné
SKILL = ".claude/skills/prospecter-aides-region/SKILL.md"

TIRAGES = 20
PRODUCTION = arbitre.Seuils(arbitre.SEUIL_BAS, arbitre.SEUIL_HAUT)


# --------------------------------------------------------------------------
# Statistiques
# --------------------------------------------------------------------------


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d, (c + m) / d)


def taux(k: int, n: int) -> dict[str, Any]:
    bas, haut = wilson(k, n)
    return {
        "k": k,
        "n": n,
        "taux": round(k / n, 4) if n else None,
        "ic95": [round(bas, 4), round(haut, 4)] if n else None,
    }


def fmt(t: dict[str, Any]) -> str:
    if not t["n"]:
        return "0/0"
    a, b = t["ic95"]
    return f"{t['k']}/{t['n']} = {100 * t['k'] / t['n']:.1f} % [IC95 {100 * a:.1f} ; {100 * b:.1f}]"


def disp(valeurs: list[float]) -> dict[str, float]:
    return {
        "moyenne": round(statistics.mean(valeurs), 4),
        "ecart_type": round(statistics.pstdev(valeurs), 4),
        "min": round(min(valeurs), 4),
        "max": round(max(valeurs), 4),
    }


def fmt_disp(d: dict[str, float]) -> str:
    return (
        f"moyenne {100 * d['moyenne']:.1f} %, écart-type {100 * d['ecart_type']:.1f} pt, "
        f"de {100 * d['min']:.1f} à {100 * d['max']:.1f} %"
    )


# --------------------------------------------------------------------------
# Git, en lecture seule
# --------------------------------------------------------------------------


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(RACINE), *args], capture_output=True, text=True, check=True
    ).stdout


def ls_tree(commit: str, chemin: str, recursif: bool = False) -> list[str]:
    opts = ["ls-tree", "--name-only"] + (["-r"] if recursif else [])
    return git(*opts, commit, chemin).split("\n")[:-1]


class Blobs:
    """`git cat-file --batch` : lit des milliers de `commit:chemin` sans arbre de travail."""

    def __init__(self) -> None:
        self.proc = subprocess.Popen(
            ["git", "-C", str(RACINE), "cat-file", "--batch"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

    def lire(self, ref: str) -> bytes | None:
        assert self.proc.stdin and self.proc.stdout
        self.proc.stdin.write(ref.encode() + b"\n")
        self.proc.stdin.flush()
        entete = self.proc.stdout.readline().decode()
        if entete.endswith("missing\n"):
            return None
        taille = int(entete.split()[2])
        contenu = self.proc.stdout.read(taille)
        self.proc.stdout.read(1)
        return contenu

    def fermer(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        self.proc.wait()


# --------------------------------------------------------------------------
# Étiquettes à un commit (même logique que banc.cas_etiquetes)
# --------------------------------------------------------------------------


@dataclass
class Cas:
    slug: str
    garde: bool
    origine: str
    motif: str = ""


@dataclass
class Jeu:
    commit: str
    cas: list[Cas]
    file: dict[str, dict[str, Any]]
    gardes: set[str]
    echecs: set[str]
    snapshots: dict[str, list[str]]

    @property
    def par_slug(self) -> dict[str, Cas]:
        return {c.slug: c for c in self.cas}


def jeu_etiquete(commit: str) -> Jeu:
    noms = ls_tree(commit, "backend/data/aides/")
    gardes = {Path(p).name.removesuffix(".yaml") for p in noms if p.endswith(".yaml")}
    echecs = {Path(p).name.removesuffix(".yaml.echec") for p in noms if p.endswith(".yaml.echec")}
    fa = yaml.safe_load(git("show", f"{commit}:backend/data/prospection/file-attente.yaml")) or {}
    snapshots: dict[str, list[str]] = defaultdict(list)
    for p in ls_tree(commit, "backend/data/sources/", recursif=True):
        parts = p.split("/")
        if len(parts) == 5:  # backend/data/sources/<slug>/<fichier> : enfants directs
            snapshots[parts[3]].append(parts[4])

    def a_snap(slug: str) -> bool:
        return any(Path(f).suffix in (".md", ".pdf") for f in snapshots.get(slug, []))

    cas = [
        Cas(s, True, "prospection" if s in fa else "catalogue") for s in sorted(gardes) if a_snap(s)
    ]
    for slug, tache in sorted(fa.items()):
        motif = tache.get("motif_ignore") or ""
        if tache.get("statut") != "ignore" or "oublon" in motif:
            continue
        if not motif.startswith(("test du destinataire", "tri humain")):
            continue
        if slug in gardes or slug not in echecs:
            continue
        if a_snap(slug):
            cas.append(Cas(slug, False, "prospection", motif))
    return Jeu(commit, cas, fa, gardes, echecs, dict(snapshots))


def sections_tri_0922() -> dict[str, str]:
    """Le classement de chaque slug dans la fiche de requalification du 2026-09-22."""
    texte = git("show", f"{APRES}:backend/data/reviews/2026-09-22-tri-catalogue.md")
    section = ""
    out: dict[str, str] = {}
    for ligne in texte.splitlines():
        if ligne.startswith("## "):
            section = {
                "## À écarter": "a_ecarter",
                "## À trancher à la main": "a_trancher",
                "## Retenues": "retenue",
            }.get(ligne.strip(), "")
            continue
        if section and (m := re.match(r"- `([^`]+)`", ligne)):
            out.setdefault(m.group(1), section)
    return out


def liste_ecarter_0922() -> set[str]:
    """Le bloc « Slugs à écarter » de la fiche du 2026-09-22 (la liste à appliquer)."""
    texte = git("show", f"{APRES}:backend/data/reviews/2026-09-22-tri-catalogue.md")
    bloc = texte.split("## Slugs à écarter")[1].split("## Notes")[0]
    return {ligne.split()[0] for ligne in bloc.splitlines() if len(ligne.split()) == 2}


LISTE_0922: set[str] = set()


def provenance(c: Cas, jeu: Jeu, tri0922: dict[str, str], requalif: dict[str, str]) -> str:
    """D'où vient l'étiquette, telle que l'historique git et les fiches la montrent."""
    t = jeu.file.get(c.slug) or {}
    if c.garde:
        base = "gardée : YAML présent au commit"
        if c.origine == "catalogue":
            base += ", ingérée hors file (skill)"
        else:
            base += f", file {t.get('statut')}"
        s = tri0922.get(c.slug)
        if s:
            base += f", tri LLM 2026-09-22 : {s}"
        if c.slug in LISTE_0922:
            base += ", listée « à écarter » le 2026-09-22 mais jamais renommée"
        if c.slug in requalif:
            base += f", relecture Claude 2026-10-04 : {requalif[c.slug]}"
        if (t.get("motif_ignore") or "").startswith("tri humain"):
            base += ", rouverte par 88d46d5d malgré un motif « tri humain »"
        return base
    if c.motif.startswith("test du destinataire"):
        base = "écartée : verdict LLM du tri du 2026-09-22, validé sur fiche"
    else:
        base = "écartée : « tri humain du 2026-09-30 » (commit 1d94a758)"
    if c.slug in requalif:
        base += f", relecture Claude 2026-10-04 : {requalif[c.slug]}"
    return base


# --------------------------------------------------------------------------
# Textes envoyés aux juges (reconstruits depuis git, comme texte_du_snapshot)
# --------------------------------------------------------------------------


def texte_au_commit(blobs: Blobs, jeu: Jeu, slug: str) -> tuple[str, str]:
    fichiers = jeu.snapshots.get(slug, [])
    base = Path("backend/data/sources") / slug
    url = ""
    morceaux: list[str] = []
    for f in banc._derniers(base / n for n in fichiers if n.endswith(".md")):
        brut = (blobs.lire(f"{jeu.commit}:{f}") or b"").decode("utf-8", errors="replace")
        if not url and (m := re.search(r"^url: (\S+)", brut, re.M)):
            url = m.group(1)
        morceaux.append(f"## {f.name}\n\n{banc._FRONTMATTER.sub('', brut).strip()}")
    if sum(len(m) for m in morceaux) < banc.SEUIL_TEXTE_PAGES:
        for f in banc._derniers(base / n for n in fichiers if n.endswith(".pdf")):
            contenu = blobs.lire(f"{jeu.commit}:{f}")
            texte = _pdftotext(contenu) if contenu else None
            if texte:
                morceaux.append(f"## {f.name}\n\n{texte.strip()}")
    return url, "\n\n".join(morceaux)[: banc.MAX_CAR_PAGE]


def nom_au_commit(blobs: Blobs, commit: str, slug: str) -> str:
    for suffixe in (".yaml", ".yaml.echec"):
        brut = blobs.lire(f"{commit}:backend/data/aides/{slug}{suffixe}")
        if brut:
            m = re.search(r"^nom: *(.+)$", brut.decode("utf-8", errors="replace"), re.M)
            return m.group(1).strip().strip("'\"") if m else ""
    return ""


# --------------------------------------------------------------------------
# Juges
# --------------------------------------------------------------------------


def lire_jsonl(nom: str) -> tuple[dict[str, dict[str, Any]], int]:
    lignes = [json.loads(x) for x in (CACHE / nom).read_text().splitlines() if x.strip()]
    return {r["slug"]: r for r in lignes}, len(lignes)


@dataclass
class Notes:
    deposable: float
    structure: float
    destinataire: str
    objet: str
    dispositif: float
    ecarte: bool  # arbitre.structure_ecarte

    @classmethod
    def depuis(cls, r: dict[str, Any]) -> Notes:
        rep = r["reponses"]
        sc = banc.scores_jev(r)
        dest = rep["destinataire"].get("choice") or ""
        obj = rep["objet"].get("choice") or ""
        disp_ = banc._proba(rep["dispositif"], "true")
        return cls(
            sc["deposable"],
            sc["structure"],
            dest,
            obj,
            disp_,
            arbitre.structure_ecarte(dest, obj, disp_),
        )


def issue_llm(r: dict[str, Any] | None) -> str:
    return "absent" if r is None else banc._issue_llm(r)


def issue_production(n: Notes, llm: dict[str, Any] | None, s: arbitre.Seuils) -> str:
    """lecture.lire + _appliquer_arbitrage, en trois issues (et `erreur`)."""
    b = arbitre.bande(n.deposable, n.ecarte, s)
    if b == "ecartee":
        return "ecartee"  # sans appel au LLM
    if llm is None:
        return "erreur"  # lecture impossible : la page reste sans verdict
    if b == "retenue":
        return "retenue"  # un écart ou une indétermination du LLM est corrigé en retenue
    i = issue_llm(llm)
    return "retenue" if i == "retenue" else "humain"  # écart du LLM → renvoyé


def issue_jev_seul(p: float, bas: float, haut: float) -> str:
    return "ecartee" if p < bas else "retenue" if p > haut else "humain"


def bilan(issues: Iterable[tuple[bool, str]]) -> dict[str, Any]:
    """issues : (gardée, issue). Pertes, admissions, part humaine, tranchés seuls."""
    xs = list(issues)
    g = [i for garde, i in xs if garde]
    e = [i for garde, i in xs if not garde]
    return {
        "gardees_perdues": taux(sum(i == "ecartee" for i in g), len(g)),
        "ecartees_admises": taux(sum(i == "retenue" for i in e), len(e)),
        "humain": taux(sum(i in ("humain", "erreur") for _, i in xs), len(xs)),
        "erreur_lecture": sum(i == "erreur" for _, i in xs),
        "n": len(xs),
    }


def fmt_bilan(b: dict[str, Any]) -> str:
    return (
        f"gardées perdues {fmt(b['gardees_perdues'])} ; écartées admises "
        f"{fmt(b['ecartees_admises'])} ; humain {fmt(b['humain'])}"
    )


# --------------------------------------------------------------------------
# Réglage de seuils et validation croisée
# --------------------------------------------------------------------------

GRILLE = [i / 100 for i in range(0, 102)]


@dataclass
class Point:
    p: float
    garde: bool
    cond_e: bool  # la bande basse est-elle permise (cohérence)
    cond_r: bool
    milieu: str  # issue dans la bande du milieu : "humain" ou "retenue"


def evaluer(pts: list[Point], bas: float, haut: float) -> tuple[int, int, int, int, int]:
    """(perdues, n_gardees, admises, n_ecartees, humain)."""
    perdues = admises = humain = ng = 0
    for x in pts:
        ng += x.garde
        if x.cond_e and x.p < bas:
            perdues += x.garde
        elif (x.cond_r and x.p > haut) or x.milieu == "retenue":
            admises += not x.garde
        else:
            humain += 1
    return perdues, ng, admises, len(pts) - ng, humain


def regler(pts: list[Point], charge: float) -> tuple[float, float]:
    """Seuils (bas, haut) qui minimisent pertes% + admissions% sous une part humaine ≤ charge.

    Décomposition : la bande basse ne dépend que de `bas`, la haute que de
    `haut`, et elles sont disjointes (bas ≤ haut, ou cohérence) : on précalcule
    chaque bord séparément, puis on combine.
    """
    ng = sum(x.garde for x in pts) or 1
    ne = (len(pts) - sum(x.garde for x in pts)) or 1
    hum_base = sum(x.milieu == "humain" for x in pts)
    adm_base = sum(x.milieu == "retenue" and not x.garde for x in pts)
    par_bas = {}
    for b in GRILLE:
        perd = adm_sub = hum_sub = 0
        for x in pts:
            if x.cond_e and x.p < b:
                perd += x.garde
                adm_sub += x.milieu == "retenue" and not x.garde
                hum_sub += x.milieu == "humain"
        par_bas[b] = (perd, adm_sub, hum_sub)
    par_haut = {}
    for h in GRILLE:
        adm_add = adm_sub = hum_sub = 0
        for x in pts:
            if x.cond_r and x.p > h:
                adm_add += not x.garde
                adm_sub += x.milieu == "retenue" and not x.garde
                hum_sub += x.milieu == "humain"
        par_haut[h] = (adm_add, adm_sub, hum_sub)
    meilleur: tuple[float, float, float, float] | None = None
    for b in GRILLE:
        pb = par_bas[b]
        for h in GRILLE:
            if h < b:
                continue
            ph = par_haut[h]
            humain = hum_base - pb[2] - ph[2]
            if humain > charge * len(pts):
                continue
            admises = adm_base - pb[1] - ph[1] + ph[0]
            cout = pb[0] / ng + admises / ne
            cle = (cout, humain, b, h)
            if meilleur is None or cle < meilleur:
                meilleur = cle
    assert meilleur is not None
    return meilleur[2], meilleur[3]


def plis(cas: list[Cas], tirage: int) -> tuple[list[Cas], list[Cas]]:
    rng = random.Random(tirage)
    g = sorted((c for c in cas if c.garde), key=lambda c: c.slug)
    e = sorted((c for c in cas if not c.garde), key=lambda c: c.slug)
    rng.shuffle(g)
    rng.shuffle(e)
    a = g[: len(g) // 2] + e[: len(e) // 2]
    b = g[len(g) // 2 :] + e[len(e) // 2 :]
    return a, b


# --------------------------------------------------------------------------
# Sous-groupes
# --------------------------------------------------------------------------


def _plat(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


MOTIFS_GROUPES: dict[str, str] = {
    "cinema": r"cinema",
    "office_tourisme": r"office.{0,4}(de.)?tourisme",
    "station": r"\bstations?\b",
    "menage_habitat": r"habitat|logement|menage|france.renov|anah\b|particulier|chauffage|chaudiere|assainissement.non.collectif",
    "communes_generique": r"commune|territoir|solidarit|contrat|dotation|developpement.local|bourg|ruralit|cohesion|appui.aux|fonds.departemental|investissement.local",
    "spectacle_festival": r"festival|spectacle|diffusion|manifestation|residence|artist|musique|theatre",
    "agricole_foret": r"agricol|agricult|elevage|bovin|forest|foret|semence|maec|feader|vigne|peuplier",
    "entreprise": r"entreprise|pme|artisan|commerce|economi|innovation|startup|tpe\b",
    "energie": r"energ|solaire|photovolta|chaleur|bois.energie|climat",
}


def groupes(
    c: Cas, nom: str, requalif_raison: str | None, tri0922: str, liste0922: bool
) -> list[str]:
    s = _plat(f"{c.slug.replace('-', ' ')} {nom}")
    out = [g for g, rx in MOTIFS_GROUPES.items() if re.search(rx, s)]
    m = c.motif
    if (
        "non_dispositif" in m
        or "pas un dispositif" in m
        or requalif_raison in ("page_programme", "non_dispositif")
        or re.search(r"\bportail|page.hub|guide.des.aides|formulaire", _plat(m))
    ):
        out.append("page_portail")
    if not c.garde:
        cat = m.split(":", 1)[1].strip().split()[0] if m.startswith("test du destinataire") else ""
        out.append(f"motif:{cat or 'tri_humain_0930'}")
    out.append(f"origine:{c.origine}")
    out.append(f"tri0922:{tri0922 or 'absent'}")
    if c.garde and liste0922:
        out.append("liste_a_ecarter_0922_jamais_renommee")
    out.append("niveau:departement" if re.match(r"^\d{2}-", c.slug) else "niveau:autre")
    return out


# --------------------------------------------------------------------------
# Programme
# --------------------------------------------------------------------------


@dataclass
class Rapport:
    lignes: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    def __call__(self, *xs: str) -> None:
        for x in xs:
            print(x)
            self.lignes.append(x)


def ols(xs: list[float], ys: list[float]) -> tuple[float, float]:
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    pente = sxy / sxx
    return my - pente * mx, pente


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--sortie", type=Path, default=SORTIE_DEFAUT)
    ap.add_argument("--tirages", type=int, default=TIRAGES)
    args = ap.parse_args(argv)
    out: Path = args.sortie
    out.mkdir(parents=True, exist_ok=True)
    R = Rapport()

    # --- caches
    jev_brut, jev_lignes = lire_jsonl("jev.jsonl")
    glm, glm_lignes = lire_jsonl("llm-or-glm.jsonl")
    mis, mis_lignes = lire_jsonl("llm-or-mistral-large.jsonl")
    var_brut, var_lignes = lire_jsonl("variante.jsonl")
    jev = {s: Notes.depuis(r) for s, r in jev_brut.items()}
    var = {s: float(r["p"]) for s, r in var_brut.items()}
    R(
        "# Caches (data/reviews/logs/benchmark-destinataire/)",
        f"jev.jsonl : {jev_lignes} lignes, {len(jev)} slugs ; llm-or-glm : {glm_lignes} / {len(glm)} ; "
        f"llm-or-mistral-large : {mis_lignes} / {len(mis)} ; variante : {var_lignes} / {len(var)}",
        f"modèles Jev : {Counter(r['modele'] for r in jev_brut.values())}",
        f"questions posées à Jev dans le cache : {Counter(tuple(sorted(r['reponses'])) for r in jev_brut.values())}",
    )
    R.data["caches"] = {
        "jev": [jev_lignes, len(jev)],
        "or_glm": [glm_lignes, len(glm)],
        "or_mistral_large": [mis_lignes, len(mis)],
        "variante": [var_lignes, len(var)],
    }

    # --- 1. étiquettes
    requalif_c = json.loads((REQUALIF / "croisement.json").read_text())
    requalif = {x[2]: x[1] for x in requalif_c}
    requalif_raison = {x[2]: x[3] for x in requalif_c}
    tri0922 = sections_tri_0922()
    liste0922 = liste_ecarter_0922()
    LISTE_0922.update(liste0922)
    jeux = {c: jeu_etiquete(c) for c in (BANC_0410, AVANT, BANC_1007, APRES)}
    R("", "# 1. Étiquettes")
    R.data["etiquettes"] = {}
    for c, j in jeux.items():
        ng = sum(x.garde for x in j.cas)
        dans_jev = sum(x.slug in jev for x in j.cas)
        R(
            f"{c} : {len(j.cas)} cas, {ng} gardées, {len(j.cas) - ng} écartées ; "
            f"{dans_jev} notés par Jev ; {sum(x.slug in glm for x in j.cas)} jugés par or-glm"
        )
        R.data["etiquettes"][c] = {
            "n": len(j.cas),
            "gardees": ng,
            "ecartees": len(j.cas) - ng,
            "notes_jev": dans_jev,
        }
    for c in (AVANT, APRES):
        j = jeux[c]
        prov = Counter(provenance(x, j, tri0922, requalif).split(",")[0] for x in j.cas)
        prov_fine = Counter(
            (
                x.garde,
                x.origine,
                tri0922.get(x.slug, "absent du tri 0922"),
                x.motif.split(" : ")[0] if not x.garde else "",
            )
            for x in j.cas
        )
        R(f"provenance à {c} : {dict(prov)}")
        for k, v in sorted(prov_fine.items(), key=lambda kv: -kv[1]):
            R(f"   {v:4d}  gardée={k[0]} origine={k[1]} tri0922={k[2]} motif={k[3]}")
        R.data["etiquettes"][c]["provenance"] = {
            " | ".join(map(str, k)): v for k, v in prov_fine.items()
        }
        with (out / f"etiquettes-{c}.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["slug", "garde", "origine", "motif", "provenance"])
            for x in j.cas:
                w.writerow(
                    [x.slug, int(x.garde), x.origine, x.motif, provenance(x, j, tri0922, requalif)]
                )
    for c in (AVANT, APRES):
        g_l = sum(x.garde and x.slug in liste0922 for x in jeux[c].cas)
        R(f"{c} : gardées listées « à écarter » le 2026-09-22 et jamais renommées : {g_l}")
        R.data["etiquettes"][c]["gardees_listees_a_ecarter_0922"] = g_l
    R(
        f"liste « Slugs à écarter » du 2026-09-22 : {len(liste0922)} slugs ; à {AVANT} : "
        f"{sum(s_ in jeux[AVANT].gardes for s_ in liste0922)} encore en .yaml, "
        f"{sum(s_ in jeux[AVANT].echecs for s_ in liste0922)} en .yaml.echec"
    )
    R(
        f"slugs du cache Mistral hors étiquettes {BANC_1007} : {sorted(set(mis) - set(jeux[BANC_1007].par_slug))}"
    )
    R(f"cas sans verdict or-glm (lecture impossible) : {sorted(set(jev) - set(glm))}")
    # Changements
    a, b = jeux[AVANT].par_slug, jeux[APRES].par_slug

    def etat(d: dict[str, Cas], s: str) -> str:
        return "absent" if s not in d else "gardee" if d[s].garde else "ecartee"

    changes = []
    for s in sorted(set(a) | set(b)):
        ea, eb = etat(a, s), etat(b, s)
        if ea != eb:
            t = jeux[APRES].file.get(s) or {}
            raison = "?"
            if s in requalif and ea == "gardee" and eb == "absent":
                raison = f"requalification 88d46d5d (B1, {requalif[s]}) : motif « requalification », hors du jeu"
            elif ea == "ecartee" and eb == "gardee":
                raison = f"rouverte puis ingérée (file : {t.get('statut')})"
            elif ea == "absent" and eb == "gardee":
                raison = "nouvelle aide au catalogue après 4ae34348"
            elif ea == "absent" and eb == "ecartee":
                raison = "nouvel écart"
            elif eb == "absent":
                in_aides = s in jeux[APRES].gardes
                raison = (
                    f"sortie du jeu (yaml={in_aides}, echec={s in jeux[APRES].echecs}, "
                    f"file={t.get('statut')}, motif={(t.get('motif_ignore') or '')[:60]})"
                )
            changes.append((s, ea, eb, s in jev, raison))
    R("", f"changements d'étiquette {AVANT} → {APRES} : {len(changes)}")
    cpt = Counter((ea, eb, j_) for _, ea, eb, j_, _ in changes)
    for k, v in sorted(cpt.items(), key=lambda kv: -kv[1]):
        R(f"   {v:4d}  {k[0]} → {k[1]} (noté par Jev : {k[2]})")
    for s, ea, eb, j_, r in changes:
        if j_:
            R(f"   - {s} : {ea} → {eb} ; {r}")
    with (out / "changements.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["slug", AVANT, APRES, "note_par_jev", "raison"])
        w.writerows(changes)
    R.data["changements"] = {"n": len(changes), "par_type": {str(k): v for k, v in cpt.items()}}

    # Biais de la requalification : choisie là où Jev contredisait l'étiquette
    rq = Counter((x[0], x[1]) for x in requalif_c)
    R("", f"relecture du 2026-10-04 (croisement.json, Claude à l'aveugle) : {dict(rq)}")

    # --- 2. reproduction des chiffres publiés, état 4ae34348
    R("", f"# 2. Reproduction, étiquettes à {AVANT}")
    J = jeux[AVANT]
    cas_j = [c for c in J.cas if c.slug in jev]
    R.data["reproduction"] = rep = {}

    def auc_de(score: Callable[[str], float], cas: list[Cas]) -> float:
        return banc.auc([(score(c.slug), c.garde) for c in cas])

    for nom, cs in (
        ("tout", cas_j),
        ("prospection", [c for c in cas_j if c.origine == "prospection"]),
    ):
        r_ = {
            "deposable": round(auc_de(lambda s: jev[s].deposable, cs), 4),
            "structure": round(auc_de(lambda s: jev[s].structure, cs), 4),
            "variante": round(auc_de(lambda s: var[s], [c for c in cs if c.slug in var]), 4),
            "n": len(cs),
        }
        rep[f"auc_{nom}"] = r_
        R(f"AUC ({nom}, {len(cs)} cas) : {r_}")

    # LLM seul (or-glm)
    llm_cas = [c for c in J.cas if c.slug in glm]
    b_llm = bilan((c.garde, issue_llm(glm[c.slug])) for c in llm_cas)
    rep["llm_seul_or_glm"] = b_llm
    R(f"LLM seul or-glm ({len(llm_cas)} cas) : {fmt_bilan(b_llm)}")
    ret_g = sum(issue_llm(glm[c.slug]) == "retenue" for c in llm_cas if c.garde)
    R(f"   gardées retenues par le LLM : {ret_g}")

    # Tête-à-tête Jev / LLM sur les cas communs
    communs = [c for c in J.cas if c.slug in jev and c.slug in glm]
    couples = [(jev[c.slug].deposable, c.garde) for c in communs]
    part_llm = sum(issue_llm(glm[c.slug]) == "humain" for c in communs) / len(communs)
    bt = banc.ajuster(couples)
    bc = banc.ajuster_a_charge(couples, part_llm)
    for nom, bb in (("tolerance", bt), ("charge_egale", bc)):
        bi = bilan(
            (c.garde, issue_jev_seul(jev[c.slug].deposable, bb.bas, bb.haut)) for c in communs
        )
        rep[f"jev_seul_{nom}"] = {"bas": bb.bas, "haut": bb.haut, **bi}
        R(
            f"Jev seul, réglage {nom} ({bb.bas:.3f} / {bb.haut:.3f}, {len(communs)} cas) : {fmt_bilan(bi)}"
        )
    # Moitié de contrôle du rapport
    for score in ("deposable", "structure"):
        moit_a = [
            (getattr(jev[c.slug], score), c.garde) for c in cas_j if banc._moitie(c.slug) == 0
        ]
        moit_b = [c for c in cas_j if banc._moitie(c.slug) == 1]
        bb = banc.ajuster(moit_a)
        bi = bilan(
            (c.garde, issue_jev_seul(getattr(jev[c.slug], score), bb.bas, bb.haut)) for c in moit_b
        )
        rep[f"moitie_{score}"] = {"bas": bb.bas, "haut": bb.haut, "n_reglage": len(moit_a), **bi}
        R(
            f"Moitié de contrôle `{score}` (réglé sur {len(moit_a)} : {bb.bas:.3f} / {bb.haut:.3f}, "
            f"mesuré sur {len(moit_b)}) : {fmt_bilan(bi)}"
        )
    # Jev seul aux seuils de production, sans et avec la règle de cohérence
    bi = bilan((c.garde, issue_jev_seul(jev[c.slug].deposable, 0.12, 0.57)) for c in cas_j)
    rep["jev_seul_012_057_sans_coherence"] = bi
    R(f"Jev seul 0,12/0,57 sans cohérence ({len(cas_j)} cas) : {fmt_bilan(bi)}")

    def bande_jev(c: Cas, s: arbitre.Seuils = PRODUCTION) -> str:
        n = jev[c.slug]
        return {"ecartee": "ecartee", "retenue": "retenue", "milieu": "humain"}[
            arbitre.bande(n.deposable, n.ecarte, s)
        ]

    bi = bilan((c.garde, bande_jev(c)) for c in cas_j)
    rep["jev_seul_012_057_avec_coherence"] = bi
    R(f"Jev seul 0,12/0,57 avec cohérence ({len(cas_j)} cas) : {fmt_bilan(bi)}")

    # Variante (question reformulée) : la docstring de modeles.md parle de 0,18 / 0,80
    cas_v = [c for c in J.cas if c.slug in var and c.slug in glm and c.slug in jev]
    for bas_, haut_ in ((0.18, 0.80),):
        bi = bilan(
            (
                c.garde,
                "ecartee"
                if var[c.slug] < bas_ and jev[c.slug].ecarte
                else "retenue"
                if var[c.slug] > haut_ and not jev[c.slug].ecarte
                else ("retenue" if issue_llm(glm[c.slug]) == "retenue" else "humain"),
            )
            for c in cas_v
        )
        bi["tranche_par_jev_seul"] = taux(
            sum(
                (var[c.slug] < bas_ and jev[c.slug].ecarte)
                or (var[c.slug] > haut_ and not jev[c.slug].ecarte)
                for c in cas_v
            ),
            len(cas_v),
        )
        rep[f"variante_production_{bas_}_{haut_}"] = bi
        R(
            f"Variante + LLM, règle de production à {bas_}/{haut_} ({len(cas_v)} cas) : "
            f"{fmt_bilan(bi)} ; tranchés par Jev seul {fmt(bi['tranche_par_jev_seul'])}"
        )

    # Échantillon du 2026-10-07
    R("", "Échantillon du 2026-10-07 (banc.echantillon(cas, 200), graine 0)")
    rep["echantillon_1007"] = {}
    for c_ in (BANC_1007, APRES):
        ech = banc.echantillon(jeux[c_].cas, 200)
        slugs = {x.slug for x in ech}
        recouvre = len(slugs & set(mis))
        R(
            f"  étiquettes à {c_} : {len(ech)} cas ({sum(x.garde for x in ech)} gardées) ; "
            f"{recouvre} des {len(mis)} slugs du cache Mistral y sont ; "
            f"{sum(x.slug in jev for x in ech)} notés par Jev, {sum(x.slug in glm for x in ech)} par or-glm"
        )
        rep["echantillon_1007"][c_] = {"n": len(ech), "recouvrement_mistral": recouvre}
    ech = banc.echantillon(jeux[BANC_1007].cas, 200)
    for nom, cache in (("or-glm", glm), ("or-mistral-large", mis)):
        cs = [x for x in ech if x.slug in cache]
        bi = bilan((x.garde, issue_llm(cache[x.slug])) for x in cs)
        rep["echantillon_1007"][nom] = bi
        R(f"  {nom} ({len(cs)} cas) : {fmt_bilan(bi)}")
    com = [x for x in ech if x.slug in mis and x.slug in glm]
    for nom, cache in (("or-glm", glm), ("or-mistral-large", mis)):
        bi = bilan((x.garde, issue_llm(cache[x.slug])) for x in com)
        rep["echantillon_1007"][f"{nom}_communs"] = bi
        R(f"  {nom} sur les {len(com)} communs : {fmt_bilan(bi)}")
    cs = [x for x in ech if x.slug in jev]
    rep["echantillon_1007"]["auc_deposable"] = round(
        banc.auc([(jev[x.slug].deposable, x.garde) for x in cs]), 4
    )
    cpl = [(jev[x.slug].deposable, x.garde) for x in cs]
    bt2 = banc.ajuster(cpl)
    part2 = sum(issue_llm(glm[x.slug]) == "humain" for x in cs) / len(cs)
    bc2 = banc.ajuster_a_charge(cpl, part2)
    for nom, bb in (("tolerance", bt2), ("charge_egale", bc2), ("production", None)):
        if bb is None:
            bi = bilan((x.garde, issue_jev_seul(jev[x.slug].deposable, 0.12, 0.57)) for x in cs)
            lab = "0.12 / 0.57"
        else:
            bi = bilan(
                (x.garde, issue_jev_seul(jev[x.slug].deposable, bb.bas, bb.haut)) for x in cs
            )
            lab = f"{bb.bas:.3f} / {bb.haut:.3f}"
        rep["echantillon_1007"][f"jev_{nom}"] = {"seuils": lab, **bi}
        R(f"  Jev seul {nom} ({lab}) : {fmt_bilan(bi)}")
    R(f"  AUC deposable sur l'échantillon : {rep['echantillon_1007']['auc_deposable']}")

    # --- 3. Règle de production complète
    R("", "# 3. Règle de production simulée (bandes 0,12/0,57, cohérence, LLM hors bande basse)")
    R.data["production"] = prod = {}
    for c_ in (AVANT, APRES):
        cs = [c for c in jeux[c_].cas if c.slug in jev]
        issues = [(c.garde, issue_production(jev[c.slug], glm.get(c.slug), PRODUCTION)) for c in cs]
        bi = bilan(issues)
        bandes = Counter(
            arbitre.bande(jev[c.slug].deposable, jev[c.slug].ecarte, PRODUCTION) for c in cs
        )
        appels_llm = len(cs) - bandes["ecartee"]
        corr = Counter()
        for c in cs:
            n = jev[c.slug]
            bnd = arbitre.bande(n.deposable, n.ecarte, PRODUCTION)
            i = issue_llm(glm.get(c.slug))
            if bnd == "retenue" and i != "retenue" and i != "absent":
                corr[f"retenue_par_jev_contre_llm_{i}_{'g' if c.garde else 'e'}"] += 1
            if bnd == "milieu" and i == "ecartee":
                corr[f"ecart_llm_renvoye_{'g' if c.garde else 'e'}"] += 1
            if bnd == "ecartee" and i == "retenue":
                corr[f"ecart_jev_contre_llm_retenue_{'g' if c.garde else 'e'}"] += 1
        tranche_jev = taux(bandes["ecartee"] + bandes["retenue"], len(cs))
        prod[c_] = {
            **bi,
            "bandes": dict(bandes),
            "appels_llm": taux(appels_llm, len(cs)),
            "tranche_par_jev_seul": tranche_jev,
            "corrections": dict(corr),
        }
        R(
            f"{c_} ({len(cs)} cas) : {fmt_bilan(bi)}",
            f"   bandes : {dict(bandes)} ; appels LLM {fmt(taux(appels_llm, len(cs)))} ; "
            f"tranchés par Jev seul {fmt(tranche_jev)} ; lectures en erreur {bi['erreur_lecture']}",
            f"   corrections : {dict(corr)}",
        )
        perdues = [
            c.slug
            for c in cs
            if c.garde and issue_production(jev[c.slug], glm.get(c.slug), PRODUCTION) == "ecartee"
        ]
        admises = [
            c.slug
            for c in cs
            if not c.garde
            and issue_production(jev[c.slug], glm.get(c.slug), PRODUCTION) == "retenue"
        ]
        R(f"   gardées perdues : {perdues}")
        R(f"   écartées admises ({len(admises)}) : {admises}")
        prod[c_]["perdues"] = perdues
        prod[c_]["admises"] = admises

    # --- 3 bis. Sensibilité aux étiquettes : la relecture a été choisie là où Jev contredisait
    R("", "# 3 bis. Sensibilité aux étiquettes (relecture choisie sur les désaccords de Jev)")
    R.data["sensibilite"] = sens = {}
    flips = {x[2]: x[0] == "écartée" for x in requalif_c if x[1].startswith("Jev a raison")}
    relus = {x[2] for x in requalif_c}
    base = [c for c in jeux[AVANT].cas if c.slug in jev]
    variantes_etiq = {
        f"{AVANT} tel quel": base,
        f"{APRES} tel quel": [c for c in jeux[APRES].cas if c.slug in jev],
        f"{AVANT} corrigé (36 « Jev a raison » inversés)": [
            Cas(c.slug, flips.get(c.slug, c.garde), c.origine, c.motif) for c in base
        ],
        f"{AVANT} sans les 78 relus": [c for c in base if c.slug not in relus],
    }
    for nom, cs in variantes_etiq.items():
        r_ = {
            "production": bilan(
                (c.garde, issue_production(jev[c.slug], glm.get(c.slug), PRODUCTION)) for c in cs
            ),
            "llm_seul": bilan((c.garde, issue_llm(glm[c.slug])) for c in cs if c.slug in glm),
            "jev_bandes_prod": bilan((c.garde, bande_jev(c)) for c in cs),
            "jev_seuil_020": bilan(
                (c.garde, "retenue" if jev[c.slug].deposable >= 0.20 else "ecartee") for c in cs
            ),
            "auc_deposable": round(banc.auc([(jev[c.slug].deposable, c.garde) for c in cs]), 4),
        }
        sens[nom] = r_
        R(
            f"{nom} ({len(cs)} cas, {sum(c.garde for c in cs)} gardées), AUC {r_['auc_deposable']} :",
            f"   règle de production : {fmt_bilan(r_['production'])}",
            f"   LLM seul : {fmt_bilan(r_['llm_seul'])}",
            f"   Jev seul aux bandes de production : {fmt_bilan(r_['jev_bandes_prod'])}",
            f"   Jev seuil unique 0,20 : perdues {fmt(r_['jev_seuil_020']['gardees_perdues'])} ; "
            f"admises {fmt(r_['jev_seuil_020']['ecartees_admises'])}",
        )

    # --- 5. Mode dégradé : LLM seul (Jev en panne)
    R("", "# 5. Mode dégradé « Jev en panne, LLM seul »")
    R.data["degrade"] = {}
    for c_ in (AVANT, APRES):
        cs = [c for c in jeux[c_].cas if c.slug in glm]
        bi = bilan((c.garde, issue_llm(glm[c.slug])) for c in cs)
        R.data["degrade"][c_] = bi
        R(f"{c_} ({len(cs)} cas) : {fmt_bilan(bi)}")

    # --- 4. Validation croisée à deux plis, 20 tirages
    R("", f"# 4. Validation croisée stratifiée à deux plis, {args.tirages} tirages")
    R.data["validation_croisee"] = vc = {}
    lignes_vc: list[list[Any]] = []
    for c_ in (AVANT, APRES):
        cs = [c for c in jeux[c_].cas if c.slug in jev and c.slug in glm]
        part_llm_c = sum(issue_llm(glm[c.slug]) == "humain" for c in cs) / len(cs)
        part_prod = sum(
            issue_production(jev[c.slug], glm[c.slug], PRODUCTION) in ("humain", "erreur")
            for c in cs
        ) / len(cs)

        def points(sous: list[Cas], regle: str) -> list[Point]:
            pts = []
            for c in sous:
                n = jev[c.slug]
                if regle == "jev_seul":
                    pts.append(Point(n.deposable, c.garde, True, True, "humain"))
                elif regle == "jev_coherence":
                    pts.append(Point(n.deposable, c.garde, n.ecarte, not n.ecarte, "humain"))
                else:  # production : LLM au milieu
                    i = issue_llm(glm[c.slug])
                    pts.append(
                        Point(
                            n.deposable,
                            c.garde,
                            n.ecarte,
                            not n.ecarte,
                            "retenue" if i == "retenue" else "humain",
                        )
                    )
            return pts

        vc[c_] = {"n": len(cs), "charges": {"llm": part_llm_c, "production": part_prod}}
        for regle in ("jev_seul", "jev_coherence", "production"):
            for nom_charge, charge in (("llm", part_llm_c), ("production", part_prod)):
                mes: dict[str, list[float]] = defaultdict(list)
                pool_k = Counter()
                seuils_vus: list[tuple[float, float]] = []
                for t in range(args.tirages):
                    pa, pb = plis(cs, t)
                    for sens, (tr, te) in enumerate(((pa, pb), (pb, pa))):
                        bas, haut = regler(points(tr, regle), charge)
                        perd, ng, adm, ne, hum = evaluer(points(te, regle), bas, haut)
                        seuils_vus.append((bas, haut))
                        mes["perdues"].append(perd / ng)
                        mes["admises"].append(adm / ne)
                        mes["humain"].append(hum / len(te))
                        if t == 0:
                            pool_k["perd"] += perd
                            pool_k["ng"] += ng
                            pool_k["adm"] += adm
                            pool_k["ne"] += ne
                            pool_k["hum"] += hum
                            pool_k["n"] += len(te)
                        lignes_vc.append(
                            [
                                c_,
                                regle,
                                nom_charge,
                                round(charge, 4),
                                t,
                                sens,
                                bas,
                                haut,
                                perd,
                                ng,
                                adm,
                                ne,
                                hum,
                                len(te),
                            ]
                        )
                cle = f"{regle}|charge_{nom_charge}"
                vc[c_][cle] = {
                    "perdues": disp(mes["perdues"]),
                    "admises": disp(mes["admises"]),
                    "humain": disp(mes["humain"]),
                    "tirage0_pooled": {
                        "perdues": taux(pool_k["perd"], pool_k["ng"]),
                        "admises": taux(pool_k["adm"], pool_k["ne"]),
                        "humain": taux(pool_k["hum"], pool_k["n"]),
                    },
                    "seuils": dict(
                        Counter(f"{b:.2f}/{h:.2f}" for b, h in seuils_vus).most_common(5)
                    ),
                }
                R(
                    f"{c_} {regle}, charge {nom_charge} ≤ {100 * charge:.1f} % ({len(cs)} cas, plis de ~{len(cs) // 2}) :",
                    f"   perdues {fmt_disp(vc[c_][cle]['perdues'])}",
                    f"   admises {fmt_disp(vc[c_][cle]['admises'])}",
                    f"   humain  {fmt_disp(vc[c_][cle]['humain'])}",
                    f"   tirage 0, deux plis réunis : perdues {fmt(vc[c_][cle]['tirage0_pooled']['perdues'])} ; "
                    f"admises {fmt(vc[c_][cle]['tirage0_pooled']['admises'])}",
                    f"   seuils les plus choisis : {vc[c_][cle]['seuils']}",
                )
    # Le réglage qui a produit 0,12 / 0,57 (banc.ajuster, tolérance 1 %), rejoué hors échantillon
    for c_ in (AVANT, APRES):
        cs = [c for c in jeux[c_].cas if c.slug in jev and c.slug in glm]
        mes = defaultdict(list)
        vus = []
        for t in range(args.tirages):
            pa, pb = plis(cs, t)
            for tr, te in ((pa, pb), (pb, pa)):
                bb = banc.ajuster([(jev[c.slug].deposable, c.garde) for c in tr])
                vus.append(f"{bb.bas:.2f}/{bb.haut:.2f}")
                s_ = arbitre.Seuils(bb.bas, bb.haut)
                for regle, issues in (
                    (
                        "jev_seul",
                        [
                            (c.garde, issue_jev_seul(jev[c.slug].deposable, bb.bas, bb.haut))
                            for c in te
                        ],
                    ),
                    (
                        "production",
                        [(c.garde, issue_production(jev[c.slug], glm[c.slug], s_)) for c in te],
                    ),
                ):
                    bi = bilan(issues)
                    for k in ("gardees_perdues", "ecartees_admises", "humain"):
                        mes[f"{regle}|{k}"].append(bi[k]["k"] / bi[k]["n"])
        cle = f"tolerance_1pc|{c_}"
        vc[cle] = {k: disp(v) for k, v in mes.items()}
        vc[cle]["seuils"] = dict(Counter(vus).most_common(6))
        R(f"{c_} réglage tolérance 1 % (banc.ajuster) sur un pli, mesuré sur l'autre :")
        for k, v in mes.items():
            R(f"   {k} : {fmt_disp(disp(v))}")
        R(f"   seuils les plus choisis : {vc[cle]['seuils']}")
    with (out / "validation-croisee.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "etat",
                "regle",
                "charge",
                "charge_val",
                "tirage",
                "sens",
                "bas",
                "haut",
                "perdues",
                "n_gardees",
                "admises",
                "n_ecartees",
                "humain",
                "n",
            ]
        )
        w.writerows(lignes_vc)

    # --- 7. Sans humain, seuil unique
    R("", "# 7. Sans humain, un seul seuil (retenir si p ≥ t)")
    R.data["sans_humain"] = sh = {}
    JA = jeux[APRES]
    cs = [c for c in JA.cas if c.slug in jev]
    cs_v = [c for c in cs if c.slug in var]
    R(f"jeu {APRES} noté par Jev : {len(cs)} cas ({sum(c.garde for c in cs)} gardées)")

    def seuil_unique(cas: list[Cas], score: Callable[[str], float], t: float) -> dict[str, Any]:
        g = [c for c in cas if c.garde]
        e = [c for c in cas if not c.garde]
        return {
            "perdues": taux(sum(score(c.slug) < t for c in g), len(g)),
            "admises": taux(sum(score(c.slug) >= t for c in e), len(e)),
        }

    for nom, score, cas_ in (
        ("deposable", lambda s: jev[s].deposable, cs),
        ("variante", lambda s: var[s], cs_v),
    ):
        sh[nom] = {}
        for t in (0.15, 0.18, 0.20, 0.22, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50):
            r_ = seuil_unique(cas_, score, t)
            sh[nom][f"{t:.2f}"] = r_
            R(f"  {nom} ≥ {t:.2f} : perdues {fmt(r_['perdues'])} ; admises {fmt(r_['admises'])}")
    # Les mêmes seuils sur les étiquettes de 4ae34348 (la cartographie cite ces chiffres-là)
    cs_av = [c for c in jeux[AVANT].cas if c.slug in jev]
    sh["a_" + AVANT] = {}
    for nom, score, t in (
        ("deposable", lambda s: jev[s].deposable, 0.20),
        ("deposable", lambda s: jev[s].deposable, 0.25),
        ("variante", lambda s: var[s], 0.40),
    ):
        r_ = seuil_unique([c for c in cs_av if c.slug in var], score, t)
        sh["a_" + AVANT][f"{nom}_{t:.2f}"] = r_
        R(
            f"  à {AVANT} ({len(cs_av)} cas) {nom} ≥ {t:.2f} : perdues {fmt(r_['perdues'])} ; "
            f"admises {fmt(r_['admises'])}"
        )

    # Politiques sans humain d'autonomie.py (bandes + LLM au milieu)
    def pol(c: Cas, regle: str) -> str:
        n = jev[c.slug]
        p = n.deposable
        if p < 0.12:
            return "ecartee"
        if p > 0.57:
            return "retenue"
        i = issue_llm(glm.get(c.slug))
        if regle == "ret_ou_indet":
            return "retenue" if i in ("retenue", "humain", "absent") else "ecartee"
        if regle == "ret_seul":
            return "retenue" if i == "retenue" else "ecartee"
        if regle.startswith("indet_jev_"):
            t = float(regle.removeprefix("indet_jev_"))
            return (
                "retenue" if i == "retenue" or (i in ("humain", "absent") and p >= t) else "ecartee"
            )
        return "retenue"

    sh["autonomie_py"] = {}
    for regle in ("ret_ou_indet", "ret_seul", "indet_jev_0.25", "indet_jev_0.20", "tout"):
        bi = bilan((c.garde, pol(c, regle)) for c in cs)
        sh["autonomie_py"][regle] = bi
        R(
            f"  autonomie.py B « {regle} » : perdues {fmt(bi['gardees_perdues'])} ; admises {fmt(bi['ecartees_admises'])}"
        )

    # Hors échantillon : t réglé sur un pli, mesuré sur l'autre
    def regler_t(cas: list[Cas], score: Callable[[str], float], critere: str) -> float:
        g = [score(c.slug) for c in cas if c.garde]
        e = [score(c.slug) for c in cas if not c.garde]
        best: tuple[float, float] | None = None
        for t in GRILLE:
            perd = sum(x < t for x in g) / len(g)
            adm = sum(x >= t for x in e) / len(e)
            if critere == "equilibre":
                cle = (perd + adm, t)
            else:  # pertes ≤ 10 %, le moins d'admissions
                if perd > 0.10:
                    continue
                cle = (adm, -t)
            if best is None or cle < best:
                best = (cle[0], t)
        assert best is not None
        return best[1]

    sh["hors_echantillon"] = {}
    for nom, score, cas_ in (
        ("deposable", lambda s: jev[s].deposable, cs),
        ("variante", lambda s: var[s], cs_v),
    ):
        for critere in ("equilibre", "pertes_max_10"):
            mes = defaultdict(list)
            ts = []
            for t_ in range(args.tirages):
                pa, pb = plis(cas_, t_)
                for tr, te in ((pa, pb), (pb, pa)):
                    t = regler_t(tr, score, critere)
                    ts.append(t)
                    r_ = seuil_unique(te, score, t)
                    mes["perdues"].append(r_["perdues"]["taux"])
                    mes["admises"].append(r_["admises"]["taux"])
            cle = f"{nom}|{critere}"
            sh["hors_echantillon"][cle] = {
                "perdues": disp(mes["perdues"]),
                "admises": disp(mes["admises"]),
                "seuils": dict(Counter(f"{t:.2f}" for t in ts).most_common(6)),
            }
            R(
                f"  hors échantillon {nom}, critère {critere} : perdues {fmt_disp(sh['hors_echantillon'][cle]['perdues'])} ; "
                f"admises {fmt_disp(sh['hors_echantillon'][cle]['admises'])} ; seuils {sh['hors_echantillon'][cle]['seuils']}"
            )

    # --- 6. Coût et taille par page
    R("", "# 6. Coût et taille par page")
    blobs = Blobs()
    textes: dict[str, tuple[str, str]] = {}
    noms: dict[str, str] = {}
    tous = sorted({c.slug for c in jeux[AVANT].cas} | {c.slug for c in jeux[APRES].cas})
    for s in tous:
        j_ = jeux[AVANT] if s in jeux[AVANT].snapshots else jeux[APRES]
        textes[s] = texte_au_commit(blobs, j_, s)
        noms[s] = nom_au_commit(blobs, AVANT, s) or nom_au_commit(blobs, APRES, s)
    skills = {}
    for c_ in ("57f054d7", AVANT):
        md = git("show", f"{c_}:{SKILL}")

        doct = "\n\n".join([section(md, "Étape 2").rstrip(), section(md, "Étape 3").rstrip()])
        skills[c_] = f"{arbitre.INTRO}\n\n{doct}"
    blobs.fermer()
    questions_bench = {k: v for k, v in arbitre.QUESTIONS.items() if k != "categorie_ecart"}
    fixe_car = {
        c_: len(json.dumps({"doctrine": d, "page": {"url": "", "texte": ""}}, ensure_ascii=False))
        + len(json.dumps(questions_bench, ensure_ascii=False))
        for c_, d in skills.items()
    }
    q_car = len(json.dumps(questions_bench, ensure_ascii=False))
    q5_car = len(json.dumps(arbitre.QUESTIONS, ensure_ascii=False))
    xs, ys = [], []
    for s, r in jev_brut.items():
        if s in textes and r.get("jetons_entree"):
            url, t = textes[s]
            xs.append(len(json.dumps(t, ensure_ascii=False)) + len(url))
            ys.append(r["jetons_entree"])
    inter, pente = ols(xs, ys)
    jetons = [r["jetons_entree"] for r in jev_brut.values() if r.get("jetons_entree")]
    couts_jev = [r["cout_usd"] for r in jev_brut.values() if r.get("cout_usd")]
    couts_glm = [r["cout_usd"] for r in glm.values() if r.get("cout_usd")]
    jet_glm = [r["jetons_entree"] for r in glm.values() if r.get("jetons_entree")]
    couts_mis = [r["cout_usd"] for r in mis.values() if r.get("cout_usd")]
    lat_jev = [r["latence_s"] for r in jev_brut.values() if r.get("latence_s")]
    lat_glm = [r["latence_s"] for r in glm.values() if r.get("latence_s")]
    car_page = sorted(len(t) for _, t in (textes[s] for s in jev_brut if s in textes))
    tronques = sum(x >= banc.MAX_CAR_PAGE for x in car_page)
    q = statistics.quantiles(jetons, n=10)
    R.data["cout"] = cout = {
        "jetons_entree_jev": {
            "n": len(jetons),
            "mediane": statistics.median(jetons),
            "min": min(jetons),
            "p10": q[0],
            "p90": q[-1],
            "max": max(jetons),
        },
        "regression_jetons_sur_caracteres_json_page": {
            "n": len(xs),
            "ordonnee_origine": round(inter, 1),
            "jetons_par_caractere": round(pente, 4),
        },
        "caracteres_part_fixe": fixe_car,
        "caracteres_questions_4": q_car,
        "caracteres_questions_5_production": q5_car,
        "caracteres_page_mediane": statistics.median(car_page),
        "pages_tronquees_25000": taux(tronques, len(car_page)),
        "jev_cout_usd": {
            "n": len(couts_jev),
            "mediane": statistics.median(couts_jev),
            "moyenne": statistics.mean(couts_jev),
            "total": sum(couts_jev),
        },
        "or_glm_cout_usd": {
            "n": len(couts_glm),
            "mediane": statistics.median(couts_glm),
            "moyenne": statistics.mean(couts_glm),
            "total": sum(couts_glm),
        },
        "or_glm_jetons_entree_mediane": statistics.median(jet_glm),
        "mistral_cout_usd": {
            "n": len(couts_mis),
            "mediane": statistics.median(couts_mis),
            "total": sum(couts_mis),
        },
        "latence_mediane_s": {
            "jev": statistics.median(lat_jev),
            "or_glm": statistics.median(lat_glm),
        },
    }
    R(json.dumps(cout, ensure_ascii=False, indent=1))
    # Coût de la règle de production pour 1 000 pages, d'après la répartition des bandes
    bnd = R.data["production"][AVANT]["bandes"]
    nb = sum(bnd.values())
    part_llm_appel = 1 - bnd.get("ecartee", 0) / nb
    c1000 = {
        "jev_seul": 1000 * cout["jev_cout_usd"]["moyenne"],
        "llm_seul": 1000 * cout["or_glm_cout_usd"]["moyenne"],
        "production": 1000
        * (cout["jev_cout_usd"]["moyenne"] + part_llm_appel * cout["or_glm_cout_usd"]["moyenne"]),
        "part_appels_llm": part_llm_appel,
    }
    cout["pour_1000_pages_usd"] = c1000
    R(f"pour 1 000 pages : {c1000}")

    # --- 6 bis. Résidu réel `a_valider` du 2026-10-04 (session d6fb7845) : pas d'étiquette
    # humaine, mais la répartition par bande et les jetons à 5 questions (production).
    R("", "# 6 bis. Bandes de Jev sur le résidu réel a_valider (sans étiquettes)")
    reel = ENTREES / "d6fb7845-jev-reel-2026-10-04"
    R.data["residu_reel"] = rr = {}
    for lot in ("jev113_259", "jev113_ho"):
        lignes = [json.loads(x) for x in (reel / f"{lot}.jsonl").read_text().splitlines() if x]
        bandes = Counter(
            arbitre.bande(
                x["deposable"],
                arbitre.structure_ecarte(x["destinataire"], x["objet"], x["dispositif"]),
                PRODUCTION,
            )
            for x in lignes
        )
        xs_ = [x["car_page"] for x in lignes if x.get("jetons_entree")]
        ys_ = [x["jetons_entree"] for x in lignes if x.get("jetons_entree")]
        i_, p_ = ols(xs_, ys_)
        rr[lot] = {
            "n": len(lignes),
            "milieu": taux(bandes["milieu"], len(lignes)),
            "ecartee": taux(bandes["ecartee"], len(lignes)),
            "retenue": taux(bandes["retenue"], len(lignes)),
            "bande_enregistree_identique": sum(
                x["bande"]
                == arbitre.bande(
                    x["deposable"],
                    arbitre.structure_ecarte(x["destinataire"], x["objet"], x["dispositif"]),
                    PRODUCTION,
                )
                for x in lignes
            ),
            "jetons_mediane": statistics.median(ys_),
            "regression": {"ordonnee_origine": round(i_, 1), "jetons_par_caractere": round(p_, 4)},
            "cout_moyen_usd": statistics.mean(x["cout_usd"] for x in lignes if x.get("cout_usd")),
        }
        R(
            f"{lot} ({len(lignes)} pages) : milieu {fmt(rr[lot]['milieu'])} ; écartée "
            f"{fmt(rr[lot]['ecartee'])} ; retenue {fmt(rr[lot]['retenue'])} ; jetons médians "
            f"{rr[lot]['jetons_mediane']} ; régression {rr[lot]['regression']} ; "
            f"coût moyen {rr[lot]['cout_moyen_usd']:.6f} $"
        )

    # --- 8. Sous-groupes
    R("", "# 8. Sous-groupes (erreurs par groupe, étiquettes à 4ae34348)")
    J = jeux[AVANT]
    cs = [c for c in J.cas if c.slug in jev]
    R.data["sous_groupes"] = sg = {}
    par_g: dict[str, list[Cas]] = defaultdict(list)
    tags: dict[str, list[str]] = {}
    for c in cs:
        tags[c.slug] = groupes(
            c,
            noms.get(c.slug, ""),
            requalif_raison.get(c.slug),
            tri0922.get(c.slug, ""),
            c.slug in liste0922,
        )
        for t in tags[c.slug]:
            par_g[t].append(c)
    R(
        "groupe | gardées | écartées | Jev prod : g perdues, e admises | LLM : g écartées, e retenues | règle prod : g perdues, e admises"
    )
    for t, membres in sorted(par_g.items(), key=lambda kv: -len(kv[1])):
        g = [c for c in membres if c.garde]
        e = [c for c in membres if not c.garde]
        jev_perd = sum(bande_jev(c) == "ecartee" for c in g)
        jev_adm = sum(bande_jev(c) == "retenue" for c in e)
        llm_perd = sum(issue_llm(glm.get(c.slug)) == "ecartee" for c in g)
        llm_adm = sum(issue_llm(glm.get(c.slug)) == "retenue" for c in e)
        pr_perd = sum(
            issue_production(jev[c.slug], glm.get(c.slug), PRODUCTION) == "ecartee" for c in g
        )
        pr_adm = sum(
            issue_production(jev[c.slug], glm.get(c.slug), PRODUCTION) == "retenue" for c in e
        )
        s020_perd = sum(jev[c.slug].deposable < 0.20 for c in g)
        s020_adm = sum(jev[c.slug].deposable >= 0.20 for c in e)
        sg[t] = {
            "gardees": len(g),
            "ecartees": len(e),
            "jev_bande_prod": {"perdues": taux(jev_perd, len(g)), "admises": taux(jev_adm, len(e))},
            "llm": {"perdues": taux(llm_perd, len(g)), "admises": taux(llm_adm, len(e))},
            "production": {"perdues": taux(pr_perd, len(g)), "admises": taux(pr_adm, len(e))},
            "jev_seuil_020": {
                "perdues": taux(s020_perd, len(g)),
                "admises": taux(s020_adm, len(e)),
            },
        }
        R(
            f"{t} | {len(g)} | {len(e)} | {jev_perd}/{len(g)}, {jev_adm}/{len(e)} | "
            f"{llm_perd}/{len(g)}, {llm_adm}/{len(e)} | {pr_perd}/{len(g)}, {pr_adm}/{len(e)} | "
            f"seuil 0,20 : {s020_perd}/{len(g)}, {s020_adm}/{len(e)}"
        )
    # Les 26 cas où la relecture a donné tort à Jev, par raison et par mot-clé
    tort = [x for x in requalif_c if x[1].startswith("étiquette confirmée")]
    R(f"relecture : {len(tort)} cas « Jev a tort » ; raisons {dict(Counter(x[3] for x in tort))}")
    mots = Counter()
    for x in tort:
        txt = _plat(f"{x[2]} {x[5]}")
        for g_, rx in MOTIFS_GROUPES.items():
            if re.search(rx, txt):
                mots[g_] += 1
    R(f"   mots-clés dans le slug et la justification : {dict(mots)}")
    sg["_relecture_jev_a_tort"] = {
        "n": len(tort),
        "raisons": dict(Counter(x[3] for x in tort)),
        "mots_cles": dict(mots),
    }
    # Sélection des 78 désaccords
    des = json.loads((REQUALIF / "desaccords.json").read_text())
    R(
        f"désaccords.json : {len(des)} ; gardées max jev_actuelle {max(x['jev_actuelle'] for x in des if x['label'] == 'gardée')}, "
        f"écartées min jev_actuelle {min(x['jev_actuelle'] for x in des if x['label'] != 'gardée')} ; "
        f"gardées max reformulée {max(x['jev_reformulee'] for x in des if x['label'] == 'gardée')}, "
        f"écartées min reformulée {min(x['jev_reformulee'] for x in des if x['label'] != 'gardée')}"
    )

    # --- cas.csv
    with (out / "cas.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "slug",
                "etiquette_" + AVANT,
                "etiquette_" + APRES,
                "origine",
                "motif",
                "nom",
                "deposable",
                "structure",
                "variante",
                "jev_destinataire",
                "jev_objet",
                "jev_dispositif",
                "coherence_ecarte",
                "bande_prod",
                "llm_or_glm",
                "llm_mistral",
                "issue_production",
                "relecture_1004",
                "groupes",
                "car_page",
                "jetons_jev",
                "cout_jev",
                "cout_glm",
            ]
        )
        A_, B_ = jeux[AVANT].par_slug, jeux[APRES].par_slug
        for s in sorted(set(A_) | set(B_)):
            c = A_.get(s) or B_[s]
            n = jev.get(s)
            w.writerow(
                [
                    s,
                    etat(A_, s),
                    etat(B_, s),
                    c.origine,
                    c.motif[:120],
                    noms.get(s, ""),
                    n and n.deposable,
                    n and round(n.structure, 4),
                    var.get(s),
                    n and n.destinataire,
                    n and n.objet,
                    n and n.dispositif,
                    n and int(n.ecarte),
                    n and arbitre.bande(n.deposable, n.ecarte, PRODUCTION),
                    issue_llm(glm.get(s)),
                    issue_llm(mis.get(s)),
                    n and issue_production(n, glm.get(s), PRODUCTION),
                    requalif.get(s, ""),
                    ";".join(tags.get(s, [])),
                    len(textes.get(s, ("", ""))[1]),
                    (jev_brut.get(s) or {}).get("jetons_entree"),
                    (jev_brut.get(s) or {}).get("cout_usd"),
                    (glm.get(s) or {}).get("cout_usd"),
                ]
            )

    (out / "resultats.json").write_text(
        json.dumps(R.data, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8"
    )
    (out / "rapport.txt").write_text("\n".join(R.lignes) + "\n", encoding="utf-8")
    print(f"\nsorties : {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
