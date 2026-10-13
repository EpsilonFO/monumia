"""Mesure de l'ingestion d'après ses journaux : coût, tours, jetons, refus, vérifications, issues.

Lancement (depuis backend/) :

    uv run python scripts/mesures/ingestion_journaux.py

Lecture seule : lit les journaux `data/reviews/logs/ingest-*.log` (racine,
`depuis-prospection-worktree/`, `depuis-veille-hebdo/`), les fiches
`data/reviews/*-ingest-*.md`, la file `data/prospection/file-attente.yaml`, le
catalogue `data/aides/*.yaml` et `*.yaml.echec`, et l'historique git de
`data/aides/`. Aucun appel réseau, aucun appel de modèle.

Écrit seulement dans `data/reviews/logs/refonte/2026-10-10-ingestion-journaux-1/` :

  - `runs.csv` : une ligne par run (un journal peut en contenir plusieurs) ;
  - `ecritures_refusees.csv` : chaque `ecrire_aide` refusé, avec son motif ;
  - `semaines.csv` : agrégats par semaine ISO ;
  - `devenir_slugs.csv` : chaque slug ingéré, son devenir et sa dépense ;
  - `echec_sens.csv` : chaque `.yaml.echec`, son en-tête, son statut dans la
    file et le commit qui l'a créé ;
  - `homonymes.csv` : runs présents dans plusieurs copies de journaux ;
  - `agregats.json` et `resume.txt` : tous les chiffres de la note.
"""

from __future__ import annotations

import csv
import json
import math
import re
import statistics
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

BACKEND = Path(__file__).resolve().parents[2]
RACINE_GIT = BACKEND.parent
LOGS = BACKEND / "data" / "reviews" / "logs"
REVIEWS = BACKEND / "data" / "reviews"
AIDES = BACKEND / "data" / "aides"
FILE_ATTENTE = BACKEND / "data" / "prospection" / "file-attente.yaml"
SORTIE = LOGS / "refonte" / "2026-10-10-ingestion-journaux-1"

# Ordre de priorité : la racine d'abord, puis les copies venues d'autres worktrees.
SOURCES = [
    ("racine", LOGS),
    ("depuis-prospection-worktree", LOGS / "depuis-prospection-worktree"),
    ("depuis-veille-hebdo", LOGS / "depuis-veille-hebdo"),
]

SEP = "=" * 78
RE_ENTETE = re.compile(r"^(\S+) — (\S+) — ingestion (.+?) / vérification (.+)$")
RE_TOUR = re.compile(
    r"^--- tour (\d+) — entrée (\d+) \(\+(\d+) cache\) / sortie (\d+) — "
    r"cumul \$([\d.]+) — (\S+)"
)
RE_APPEL = re.compile(r"^\[appel\] ([^(]+)\((.*)$")
RE_VERIF = re.compile(r"^vérification(?: (\d+)/(\d+))? : (\d+) problème\(s\), (\d+) bloquant")
RE_DUREE = re.compile(r"durée (\d+) s")
RE_OK = re.compile(
    r"^OK — (\d+) tour\(s\), (\d+) appel\(s\)\s+([\d ]+?) jetons entrée / "
    r"([\d ]+?) sortie\s+\$(\d+\.\d+)(.*)$"
)
RE_FOURNISSEUR = re.compile(r"\[(\w+) · ([\w.-]+)\]\s*$")
DEBUTS_BLOC = ("[appel] ", "[sortie] ", "[*] ", "--- tour ", "[texte] ", "[raisonnement] ")


# ---------------------------------------------------------------------------
# Statistiques
# ---------------------------------------------------------------------------


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    marge = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - marge), min(1.0, centre + marge))


def taux(k: int, n: int) -> dict:
    bas, haut = wilson(k, n)
    return {
        "k": k,
        "n": n,
        "taux": round(k / n, 4) if n else None,
        "ic95": [round(bas, 4), round(haut, 4)] if n else None,
    }


def quantile(valeurs: list[float], q: float) -> float:
    """Quantile par interpolation linéaire (méthode 7, celle de numpy par défaut)."""
    v = sorted(valeurs)
    if not v:
        return float("nan")
    pos = (len(v) - 1) * q
    bas = math.floor(pos)
    haut = math.ceil(pos)
    return v[bas] + (v[haut] - v[bas]) * (pos - bas)


def moindres_carres(x: list[list[float]], y: list[float]) -> list[float]:
    """Régression linéaire par équations normales (pivot de Gauss), sans numpy."""
    k = len(x[0])
    a = [[sum(r[i] * r[j] for r in x) for j in range(k)] for i in range(k)]
    b = [sum(r[i] * v for r, v in zip(x, y, strict=True)) for i in range(k)]
    for c in range(k):
        piv = max(range(c, k), key=lambda i: abs(a[i][c]))
        a[c], a[piv] = a[piv], a[c]
        b[c], b[piv] = b[piv], b[c]
        for i in range(k):
            if i != c and a[c][c]:
                f = a[i][c] / a[c][c]
                a[i] = [ai - f * ac for ai, ac in zip(a[i], a[c], strict=True)]
                b[i] -= f * b[c]
    return [b[i] / a[i][i] for i in range(k)]


def distribution(valeurs: list[float], arrondi: int = 4) -> dict:
    if not valeurs:
        return {"n": 0}
    return {
        "n": len(valeurs),
        "somme": round(sum(valeurs), arrondi),
        "moyenne": round(statistics.fmean(valeurs), arrondi),
        "mediane": round(statistics.median(valeurs), arrondi),
        "p90": round(quantile(valeurs, 0.9), arrondi),
        "max": round(max(valeurs), arrondi),
        "min": round(min(valeurs), arrondi),
    }


# ---------------------------------------------------------------------------
# Lecture des journaux
# ---------------------------------------------------------------------------


@dataclass
class Run:
    slug: str
    debut: str
    source: str
    fichier: str
    ligne: int
    modele_entete: str
    verif_entete: str
    lignes_run: int = 0
    tours: list[tuple[int, int, int, int, float, str]] = field(default_factory=list)
    appels: Counter = field(default_factory=Counter)
    ecritures: int = 0
    refus: list[tuple[str, str, int]] = field(default_factory=list)  # (motif, message, ligne)
    verif_appels: int = 0
    verif_reelles: int = 0
    verif_pannes: int = 0
    verif_plafond: int = 0
    verif_erreur_outil: int = 0
    verif_bloquants: list[int] = field(default_factory=list)
    verif_problemes: list[int] = field(default_factory=list)
    hp_appels: int = 0
    hp_accepte: bool = False
    fin_boucle: str = ""  # termine, sans_review, max_tours, boucle, budget, ""
    duree_s: int | None = None
    ok_ligne: dict | None = None
    echec: str | None = None
    erreurs_appel: list[str] = field(default_factory=list)
    fournisseurs: set = field(default_factory=set)
    transitoires: int = 0
    elagages: int = 0
    rappels: int = 0
    relances_review: int = 0
    sauvetages: int = 0
    faits_proposes: int = 0
    faits_retires: int = 0
    exception: bool = False
    verif_format_plafond: bool = False
    diag_yaml: list[str] = field(default_factory=list)

    # ------------------------------------------------------------- dérivés
    @property
    def nb_tours(self) -> int:
        return len(self.tours)

    @property
    def cumul_ingestion(self) -> float:
        return self.tours[-1][4] if self.tours else 0.0

    @property
    def cout_total(self) -> float | None:
        """Coût complet (extracteur + vérificateur) si la ligne OK l'a écrit."""
        return self.ok_ligne["cout"] if self.ok_ligne else None

    @property
    def cout_inconnu(self) -> bool:
        return bool(self.ok_ligne and self.ok_ligne["inconnu"])

    @property
    def cout_meilleur(self) -> float:
        """Coût total si connu, sinon le cumul de l'extracteur (borne basse)."""
        return self.cout_total if self.cout_total is not None else self.cumul_ingestion

    @property
    def cout_verif(self) -> float | None:
        if self.cout_total is None:
            return None
        return max(0.0, self.cout_total - self.cumul_ingestion)

    @property
    def modele(self) -> str:
        if not self.modele_entete.startswith("(défaut"):
            return self.modele_entete
        return ""

    @property
    def modele_revele(self) -> str:
        """Le modèle tel que le révèle un message d'erreur, à défaut de l'en-tête."""
        return ",".join(sorted(m for _, m in self.fournisseurs))

    @property
    def issue(self) -> str:
        if self.ok_ligne:
            return "hors_perimetre" if self.hp_accepte else "acceptee"
        if self.echec is not None:
            if self.fin_boucle == "termine":
                return "refusee_controles"
            if self.fin_boucle in ("sans_review", "max_tours", "boucle", "budget"):
                return "abandon"
            return "panne"
        return "interrompu"

    @property
    def sous_issue(self) -> str:
        if self.issue == "refusee_controles":
            e = self.echec or ""
            if e.startswith("aucun fichier YAML"):
                return "termine_sans_yaml"
            if e.startswith("lint rouge"):
                return "lint_rouge"
            return "autre_controle"
        if self.issue == "abandon":
            return self.fin_boucle
        if self.issue == "panne":
            classes = Counter(e.split(":")[0] for e in self.erreurs_appel)
            return classes.most_common(1)[0][0] if classes else "sans_trace"
        return ""


def classer_refus(sortie: str) -> str | None:
    if not sortie.startswith("ERREUR"):
        return None
    if sortie.startswith("ERREUR : YAML invalide"):
        return "yaml_invalide"
    if sortie.startswith("ERREUR : le fichier ne respecte pas le schéma"):
        return "hors_schema"
    if sortie.startswith("ERREUR : le slug du fichier"):
        return "slug_errone"
    if sortie.startswith("ERREUR : le contenu doit être un objet YAML"):
        return "pas_un_objet"
    if "TypeError" in sortie[:80]:
        return "appel_mal_forme"
    return "autre"


def lire_fichier(source: str, chemin: Path) -> list[Run]:
    lignes = chemin.read_text(encoding="utf-8", errors="replace").split("\n")
    runs: list[Run] = []
    courant: Run | None = None
    appel_en_cours: str | None = None
    sortie_buf: list[str] = []
    ligne_appel = 0
    args_appel = ""

    def clore_sortie() -> None:
        nonlocal appel_en_cours, sortie_buf, args_appel
        if courant is None or appel_en_cours is None:
            appel_en_cours, sortie_buf = None, []
            return
        texte = "\n".join(sortie_buf)
        traiter_sortie(courant, appel_en_cours, texte, ligne_appel, args_appel)
        appel_en_cours, sortie_buf = None, []

    i = 0
    n = len(lignes)
    while i < n:
        li = lignes[i]
        if li == SEP and i + 2 < n and lignes[i + 2] == SEP and RE_ENTETE.match(lignes[i + 1]):
            clore_sortie()
            m = RE_ENTETE.match(lignes[i + 1])
            assert m
            courant = Run(
                slug=m.group(1),
                debut=m.group(2),
                source=source,
                fichier=str(chemin.relative_to(BACKEND)),
                ligne=i + 2,
                modele_entete=m.group(3).strip(),
                verif_entete=m.group(4).strip(),
            )
            runs.append(courant)
            i += 3
            continue
        if courant is None:
            i += 1
            continue
        courant.lignes_run += 1
        if appel_en_cours is not None:
            if li.startswith("[sortie] ") and not sortie_buf:
                sortie_buf.append(li[len("[sortie] ") :])
                i += 1
                continue
            if sortie_buf and not li.startswith(DEBUTS_BLOC):
                if len(sortie_buf) < 60:
                    sortie_buf.append(li)
                i += 1
                continue
            if sortie_buf:
                clore_sortie()
        if li.startswith("--- tour "):
            m = RE_TOUR.match(li)
            if m:
                courant.tours.append(
                    (
                        int(m.group(1)),
                        int(m.group(2)),
                        int(m.group(3)),
                        int(m.group(4)),
                        float(m.group(5)),
                        m.group(6),
                    )
                )
        elif li.startswith("[appel] "):
            m = RE_APPEL.match(li)
            nom = m.group(1).strip() if m else "?"
            courant.appels[nom] += 1
            appel_en_cours = nom
            sortie_buf = []
            ligne_appel = i + 1
            args_appel = m.group(2) if (m and nom == "ecrire_aide") else ""
        elif li.startswith("[*] "):
            traiter_evenement(courant, li[4:])
        i += 1
    clore_sortie()
    return runs


RE_DEUX_POINTS = re.compile(r"\S\s+:\s|^\s*:\s")


def diagnostic_yaml(args: str) -> str:
    """Pourquoi un `ecrire_aide` a été refusé pour YAML invalide : la ligne fautive.

    `deux_points_francais` : la ligne en faute (ou la précédente, que PyYAML
    signale souvent) contient « mot : » hors guillemets, la typographie
    française qui fait lire une clé à PyYAML dans un scalaire nu.
    """
    brut = args[:-1] if args.endswith(")") else args
    try:
        texte = json.loads(brut)["yaml_texte"]
    except Exception:  # noqa: BLE001 — argument tronqué ou mal formé
        return "arguments_illisibles"
    try:
        yaml.load(texte, Loader=yaml.CSafeLoader)
    except yaml.MarkedYAMLError as exc:
        marque = exc.problem_mark
        if marque is None:
            return "sans_position"
        lignes = texte.split("\n")
        voisines = lignes[max(0, marque.line - 1) : marque.line + 1]
        if any(RE_DEUX_POINTS.search(v.split("#", 1)[0]) for v in voisines):
            return "deux_points_francais"
        return "autre_position"
    except Exception:  # noqa: BLE001
        return "autre_exception"
    return "se_charge_aujourd_hui"


def traiter_sortie(run: Run, nom: str, texte: str, ligne: int, args: str = "") -> None:
    if nom == "ecrire_aide":
        run.ecritures += 1
        motif = classer_refus(texte)
        if motif:
            run.refus.append((motif, texte.split("\n")[0][:300], ligne))
            if motif == "yaml_invalide":
                run.diag_yaml.append(diagnostic_yaml(args))
    elif nom == "verification_adversariale":
        run.verif_appels += 1
        if texte.startswith("## Vérification adversariale"):
            run.verif_reelles += 1
            if "Vérificateur indisponible" in texte:
                run.verif_pannes += 1
        elif texte.startswith("Plafond atteint"):
            run.verif_plafond += 1
        else:
            run.verif_erreur_outil += 1
    elif nom == "declarer_hors_perimetre":
        run.hp_appels += 1
        if texte.startswith("Aide écartée"):
            run.hp_accepte = True


def traiter_evenement(run: Run, ev: str) -> None:
    m = RE_VERIF.match(ev)
    if m:
        run.verif_problemes.append(int(m.group(3)))
        if m.group(2):
            run.verif_format_plafond = True
        run.verif_bloquants.append(int(m.group(4)))
        return
    if ev.startswith("terminé en"):
        run.fin_boucle = "termine"
    elif ev.startswith("arrêt : aucune review"):
        run.fin_boucle = "sans_review"
    elif ev.startswith("arrêt : boucle"):
        run.fin_boucle = "boucle"
    elif ev.startswith("arrêt dur"):
        run.fin_boucle = "budget"
    elif ev.startswith("arrêt :") and "tours atteints" in ev:
        run.fin_boucle = "max_tours"
    if ev.startswith(("terminé en", "arrêt")):
        d = RE_DUREE.search(ev)
        if d:
            run.duree_s = int(d.group(1))
        return
    if ev.startswith("OK — "):
        m = RE_OK.match(ev)
        if m:
            run.ok_ligne = {
                "tours": int(m.group(1)),
                "appels": int(m.group(2)),
                "jetons_entree": int(m.group(3).replace(" ", "")),
                "jetons_sortie": int(m.group(4).replace(" ", "")),
                "cout": float(m.group(5)),
                "inconnu": "coût inconnu" in m.group(6),
            }
        return
    if ev.startswith("ÉCHEC : "):
        run.echec = ev[len("ÉCHEC : ") :]
        return
    if ev.startswith("EXCEPTION"):
        run.exception = True
        return
    if ev.startswith("appel en échec : "):
        corps = ev[len("appel en échec : ") :]
        run.erreurs_appel.append(corps)
        f = RE_FOURNISSEUR.search(corps)
        if f:
            run.fournisseurs.add((f.group(1), f.group(2)))
        return
    if ev.startswith("erreur transitoire"):
        run.transitoires += 1
    elif ev.startswith("élagage"):
        run.elagages += 1
    elif ev.startswith("rappel à l'ordre"):
        run.rappels += 1
    elif ev.startswith("relance "):
        run.relances_review += 1
    elif ev.startswith("sauvetage"):
        run.sauvetages += 1
    elif ev.startswith("fait proposé"):
        run.faits_proposes += 1
    elif ev.startswith("fait retiré"):
        run.faits_retires += 1


# ---------------------------------------------------------------------------
# Catalogue, file d'attente, historique git
# ---------------------------------------------------------------------------


def famille_motif(motif: str | None) -> str:
    m = motif or ""
    if not m:
        return "(sans motif)"
    for prefixe, nom in [
        ("doublon d'URL de", "doublon_url"),
        ("hors périmètre à l'ingestion", "hors_perimetre_ingestion"),
        ("hors périmètre :", "hors_perimetre_lecture"),
        ("test du destinataire :", "test_destinataire"),
        ("requalification du", "requalification_2026-10-04"),
        ("tri humain", "tri_humain"),
        ("pas un dispositif demandable", "pas_un_dispositif"),
    ]:
        if m.startswith(prefixe):
            return nom
    return "autre:" + m[:40]


def historique_echec() -> dict[str, tuple[str, str, str, str]]:
    """Pour chaque chemin `.yaml.echec`, le dernier commit qui l'a créé (A ou R)."""
    sortie = subprocess.run(
        [
            "git",
            "-C",
            str(RACINE_GIT),
            "log",
            "--format=@@%h|%ad|%s",
            "--date=short",
            "--name-status",
            "-M",
            "--",
            "backend/data/aides",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    resultat: dict[str, tuple[str, str, str, str]] = {}
    commit = ("", "", "")
    for ligne in sortie.split("\n"):
        if ligne.startswith("@@"):
            h, d, s = (ligne[2:].split("|", 2) + ["", ""])[:3]
            commit = (h, d, s)
            continue
        if not ligne.strip():
            continue
        parties = ligne.split("\t")
        statut = parties[0]
        if statut.startswith("R"):
            src, dst = parties[1], parties[2]
        elif statut == "A":
            src, dst = "", parties[1]
        else:
            continue
        if not dst.endswith(".yaml.echec"):
            continue
        slug = Path(dst).name[: -len(".yaml.echec")]
        # git log va du plus récent au plus ancien : la première création vue
        # est la plus récente, c'est celle du fichier actuel.
        if slug not in resultat:
            mode = (
                "renomme_depuis_yaml" if src.endswith(".yaml") else ("renomme" if src else "ajoute")
            )
            resultat[slug] = (commit[0], commit[1], commit[2][:80], mode)
    return resultat


def lire_reviews() -> list[dict]:
    re_cmt = re.compile(
        r"Généré par scripts/ingerer\.py le (\S+) — extraction (.+?), vérification (.+?), "
        r"(\d+) appel\(s\), (coût inconnu|\$(\d+\.\d+))"
    )
    out = []
    for p in sorted(REVIEWS.glob("*-ingest-*.md")):
        tete = p.read_text(encoding="utf-8", errors="replace")[:1200]
        m = re_cmt.search(tete)
        slug = p.name.split("-ingest-", 1)[1][:-3]
        out.append(
            {
                "fichier": p.name,
                "slug": slug,
                "date": p.name[:10],
                "pipeline": bool(m),
                "modele": m.group(2) if m else "",
                "appels": int(m.group(4)) if m else None,
                "cout": float(m.group(6)) if m and m.group(6) else None,
                "hors_perimetre": "Écartée à l'ingestion — hors périmètre" in tete
                or "## Écartée à l'ingestion" in p.read_text(encoding="utf-8", errors="replace"),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Programme
# ---------------------------------------------------------------------------


def semaine(debut: str) -> str:
    a, s, _ = date.fromisoformat(debut[:10]).isocalendar()
    return f"{a}-S{s:02d}"


def main() -> None:
    SORTIE.mkdir(parents=True, exist_ok=True)
    resume: list[str] = []

    def dire(*morceaux: object) -> None:
        texte = " ".join(str(m) for m in morceaux)
        resume.append(texte)
        print(texte)

    # ---------------------------------------------------------- journaux
    tous: list[Run] = []
    fichiers_par_source: Counter = Counter()
    for source, dossier in SOURCES:
        for chemin in sorted(dossier.glob("ingest-*.log")):
            fichiers_par_source[source] += 1
            tous.extend(lire_fichier(source, chemin))
    dire("Fichiers lus par source :", dict(fichiers_par_source))
    dire("Blocs d'en-tête (runs bruts, doublons de copie compris) :", len(tous))

    # Dédoublonnage : un run est identifié par (slug, horodatage de début).
    par_cle: dict[tuple[str, str], list[Run]] = defaultdict(list)
    for r in tous:
        par_cle[(r.slug, r.debut)].append(r)
    runs: list[Run] = []
    homonymes = []
    for cle, groupe in par_cle.items():
        # Garder la copie la plus longue (une copie tronquée a perdu sa fin),
        # à égalité la racine.
        ordre = {s: i for i, (s, _) in enumerate(SOURCES)}
        groupe.sort(key=lambda r: (-r.lignes_run, ordre[r.source]))
        runs.append(groupe[0])
        if len(groupe) > 1:
            homonymes.append(
                {
                    "slug": cle[0],
                    "debut": cle[1],
                    "copies": ";".join(f"{r.source}:{r.lignes_run}" for r in groupe),
                    "gardee": groupe[0].source,
                    "identiques": len({r.lignes_run for r in groupe}) == 1,
                }
            )
    runs.sort(key=lambda r: (r.debut, r.slug))
    dire(
        "Runs distincts après dédoublonnage (slug, début) :",
        len(runs),
        "; clés présentes dans plusieurs copies :",
        len(homonymes),
        "; dont copies de même longueur :",
        sum(1 for h in homonymes if h["identiques"]),
    )
    with (SORTIE / "homonymes.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["slug", "debut", "copies", "gardee", "identiques"])
        w.writeheader()
        w.writerows(homonymes)
    # Runs uniques à une copie hors racine (le surplus apporté par les copies).
    apport = Counter(r.source for r in runs)
    dire("Runs gardés par source :", dict(apport))
    # Fichiers homonymes entre la racine et une copie : quels runs chacun porte.
    par_nom = defaultdict(lambda: defaultdict(set))
    for r in tous:
        par_nom[Path(r.fichier).name][r.source].add(r.debut)
    homonymes_fichiers = {}
    for nom, src in sorted(par_nom.items()):
        if len(src) > 1:
            ensembles = list(src.values())
            communs = set.intersection(*ensembles)
            homonymes_fichiers[nom] = {
                **{s: sorted(v) for s, v in src.items()},
                "runs_communs": len(communs),
            }
    dire(
        "Fichiers homonymes entre copies :",
        len(homonymes_fichiers),
        "; runs communs (même slug et même début) :",
        sum(h["runs_communs"] for h in homonymes_fichiers.values()),
    )
    (SORTIE / "homonymes_fichiers.json").write_text(
        json.dumps(homonymes_fichiers, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    # Contrôle : slug d'en-tête égal au nom du fichier
    discordants = [r for r in runs if Path(r.fichier).name != f"ingest-{r.slug}.log"]
    dire("Runs dont le slug d'en-tête diffère du nom de fichier :", len(discordants))

    # ---------------------------------------------------------- runs.csv
    champs = [
        "slug",
        "debut",
        "semaine",
        "source",
        "fichier",
        "ligne",
        "modele_entete",
        "verif_entete",
        "modele_revele",
        "issue",
        "sous_issue",
        "fin_boucle",
        "tours",
        "duree_s",
        "cout_total",
        "cout_inconnu",
        "cumul_ingestion",
        "cout_verif",
        "appels_compteur",
        "jetons_entree_total",
        "jetons_sortie_total",
        "entree_tours",
        "cache_tours",
        "sortie_tours",
        "contexte_moyen",
        "contexte_max",
        "ecritures",
        "refus",
        "refus_yaml",
        "refus_schema",
        "refus_autre",
        "verif_appels",
        "verif_reelles",
        "verif_pannes",
        "verif_plafond",
        "verif_bloquants_premier",
        "verif_bloquants_dernier",
        "hp_appels",
        "hp_accepte",
        "transitoires",
        "erreurs_appel",
        "elagages",
        "rappels",
        "faits_proposes",
        "echec",
    ]
    lignes_csv = []
    for r in runs:
        e = sum(t[1] for t in r.tours)
        c = sum(t[2] for t in r.tours)
        s = sum(t[3] for t in r.tours)
        ctx = [t[1] + t[2] for t in r.tours]
        motifs = Counter(m for m, _, _ in r.refus)
        lignes_csv.append(
            {
                "slug": r.slug,
                "debut": r.debut,
                "semaine": semaine(r.debut),
                "source": r.source,
                "fichier": r.fichier,
                "ligne": r.ligne,
                "modele_entete": r.modele_entete,
                "verif_entete": r.verif_entete,
                "modele_revele": r.modele_revele,
                "issue": r.issue,
                "sous_issue": r.sous_issue,
                "fin_boucle": r.fin_boucle,
                "tours": r.nb_tours,
                "duree_s": r.duree_s,
                "cout_total": r.cout_total,
                "cout_inconnu": r.cout_inconnu,
                "cumul_ingestion": r.cumul_ingestion,
                "cout_verif": None if r.cout_verif is None else round(r.cout_verif, 6),
                "appels_compteur": r.ok_ligne["appels"] if r.ok_ligne else None,
                "jetons_entree_total": r.ok_ligne["jetons_entree"] if r.ok_ligne else None,
                "jetons_sortie_total": r.ok_ligne["jetons_sortie"] if r.ok_ligne else None,
                "entree_tours": e,
                "cache_tours": c,
                "sortie_tours": s,
                "contexte_moyen": round(statistics.fmean(ctx)) if ctx else None,
                "contexte_max": max(ctx) if ctx else None,
                "ecritures": r.ecritures,
                "refus": len(r.refus),
                "refus_yaml": motifs["yaml_invalide"],
                "refus_schema": motifs["hors_schema"],
                "refus_autre": len(r.refus) - motifs["yaml_invalide"] - motifs["hors_schema"],
                "verif_appels": r.verif_appels,
                "verif_reelles": r.verif_reelles,
                "verif_pannes": r.verif_pannes,
                "verif_plafond": r.verif_plafond,
                "verif_bloquants_premier": r.verif_bloquants[0] if r.verif_bloquants else None,
                "verif_bloquants_dernier": r.verif_bloquants[-1] if r.verif_bloquants else None,
                "hp_appels": r.hp_appels,
                "hp_accepte": r.hp_accepte,
                "transitoires": r.transitoires,
                "erreurs_appel": len(r.erreurs_appel),
                "elagages": r.elagages,
                "rappels": r.rappels,
                "faits_proposes": r.faits_proposes,
                "echec": (r.echec or "")[:200],
            }
        )
    with (SORTIE / "runs.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=champs)
        w.writeheader()
        w.writerows(lignes_csv)

    with (SORTIE / "ecritures_refusees.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["slug", "debut", "fichier", "ligne", "motif", "message"])
        for r in runs:
            for motif, msg, ligne in r.refus:
                w.writerow([r.slug, r.debut, r.fichier, ligne, motif, msg])

    ag: dict = {}

    # ---------------------------------------------------------- 1. issues
    issues = Counter(r.issue for r in runs)
    sous = Counter((r.issue, r.sous_issue) for r in runs)
    ag["issues"] = {k: taux(v, len(runs)) for k, v in issues.items()}
    ag["sous_issues"] = {f"{a}/{b}": v for (a, b), v in sorted(sous.items())}
    dire("\n== Issues (n =", len(runs), "runs)")
    for k, v in issues.most_common():
        t = taux(v, len(runs))
        dire(f"  {k}: {v} ({t['taux']:.1%}, IC95 {t['ic95'][0]:.1%}-{t['ic95'][1]:.1%})")
    for (a, b), v in sorted(sous.items()):
        dire(f"    {a}/{b}: {v}")
    dates = [r.debut[:10] for r in runs]
    dire("Période :", min(dates), "à", max(dates))
    ag["periode"] = [min(dates), max(dates)]

    # ---------------------------------------------------------- modèles
    modeles = Counter(r.modele_entete for r in runs)
    sans_modele = [r for r in runs if r.modele_entete.startswith("(défaut")]
    revele = Counter(r.modele_revele or "(rien)" for r in sans_modele)
    ag["modeles_entete"] = dict(modeles)
    ag["sans_modele_trace"] = taux(len(sans_modele), len(runs))
    ag["sans_modele_revele_par_erreur"] = dict(revele)
    dire("\n== Modèle d'extraction tracé dans l'en-tête")
    for k, v in modeles.most_common():
        dire(f"  {k}: {v}")
    dire("  runs sans modèle tracé : ", taux(len(sans_modele), len(runs)))
    dire("  parmi eux, modèle révélé par un message d'erreur :", dict(revele))
    verifs = Counter(r.verif_entete for r in runs)
    ag["modeles_verif_entete"] = dict(verifs)

    # ---------------------------------------------------------- 2. coûts
    ok = [r for r in runs if r.ok_ligne]
    ok_connu = [r for r in ok if not r.cout_inconnu]
    sans_total = [r for r in runs if not r.ok_ligne]
    ag["cout"] = {
        "runs_avec_cout_total": taux(len(ok), len(runs)),
        "runs_cout_total_inconnu_partiel": len(ok) - len(ok_connu),
        "total_connu_par_run": distribution([r.cout_total for r in ok_connu]),
        "total_partiel_runs_inconnus": distribution([r.cout_total for r in ok if r.cout_inconnu]),
        "cumul_extracteur_runs_sans_total": distribution([r.cumul_ingestion for r in sans_total]),
        "somme_meilleure_estimation": round(sum(r.cout_meilleur for r in runs), 2),
    }
    dire("\n== Coût")
    dire("  runs avec ligne OK (coût complet écrit) :", taux(len(ok), len(runs)))
    dire("  dont coût marqué inconnu (somme partielle) :", len(ok) - len(ok_connu))
    dire("  coût total par run (OK, tarif connu) :", distribution([r.cout_total for r in ok_connu]))
    dire(
        "  runs sans total (ÉCHEC, panne, interrompu) : cumul de l'extracteur seul :",
        distribution([r.cumul_ingestion for r in sans_total]),
    )
    dire(
        "  somme sur tous les runs (total si connu, sinon extracteur seul) :",
        ag["cout"]["somme_meilleure_estimation"],
    )
    zero = [r for r in runs if r.cout_meilleur == 0]
    ag["cout"]["runs_a_zero"] = taux(len(zero), len(runs))
    dire("  runs à 0 $ :", taux(len(zero), len(runs)), Counter(r.issue for r in zero))

    # Part du vérificateur
    v_ok = [r for r in ok_connu if r.cout_verif is not None]
    s_tot = sum(r.cout_total for r in v_ok)
    s_ver = sum(r.cout_verif for r in v_ok)
    ag["verificateur_part_cout"] = {
        "runs": len(v_ok),
        "cout_total": round(s_tot, 2),
        "cout_verif": round(s_ver, 2),
        "part": round(s_ver / s_tot, 4) if s_tot else None,
        "part_par_run": distribution(
            [r.cout_verif / r.cout_total for r in v_ok if r.cout_total > 0]
        ),
    }
    dire("  part du vérificateur (runs OK tarif connu) :", ag["verificateur_part_cout"])
    par_jour = defaultdict(lambda: [0.0, 0.0, 0])
    for r in v_ok:
        j = r.debut[:10]
        par_jour[j][0] += r.cout_total
        par_jour[j][1] += r.cout_verif
        par_jour[j][2] += 1
    ag["verificateur_part_par_jour"] = {
        j: {"runs": n, "total": round(t, 3), "part": round(v / t, 3) if t else None}
        for j, (t, v, n) in sorted(par_jour.items())
    }
    parts_j = [x["part"] for x in ag["verificateur_part_par_jour"].values() if x["runs"] >= 5]
    dire(
        "  part par jour (jours >= 5 runs) : min",
        min(parts_j) if parts_j else None,
        "max",
        max(parts_j) if parts_j else None,
        "jours",
        len(parts_j),
    )
    # appels du compteur - tours = appels au vérificateur (contrôle croisé)
    ecarts = Counter(
        (r.ok_ligne["appels"] - r.nb_tours) - r.verif_reelles for r in ok if r.ok_ligne
    )
    ag["controle_appels_moins_tours_egal_verif"] = dict(ecarts)

    # Tours et durée
    ag["tours"] = {
        "tous": distribution([r.nb_tours for r in runs], 1),
        "acceptees": distribution([r.nb_tours for r in runs if r.issue == "acceptee"], 1),
    }
    avec_duree = [r for r in runs if r.duree_s is not None]
    ag["duree_s"] = {
        "couverture": taux(len(avec_duree), len(runs)),
        "tous": distribution([r.duree_s for r in avec_duree], 1),
        "acceptees": distribution([r.duree_s for r in avec_duree if r.issue == "acceptee"], 1),
    }
    dire("\n== Tours :", ag["tours"])
    dire("== Durée de boucle (s) :", ag["duree_s"])

    # Jetons par tour
    tours_tous = [t for r in runs for t in r.tours]
    ctx = [t[1] + t[2] for t in tours_tous]
    s_in = sum(t[1] for t in tours_tous)
    s_cache = sum(t[2] for t in tours_tous)
    ag["jetons_tours"] = {
        "tours": len(tours_tous),
        "contexte_par_tour": distribution(ctx, 0),
        "entree_hors_cache": s_in,
        "lus_en_cache": s_cache,
        "part_cache": round(s_cache / (s_in + s_cache), 4) if s_in + s_cache else None,
        "sortie": sum(t[3] for t in tours_tous),
    }
    par_modele_ctx = defaultdict(list)
    par_modele_cache = defaultdict(lambda: [0, 0])
    for r in runs:
        cle = r.modele_entete if r.modele else ("défaut→" + (r.modele_revele or "?"))
        for t in r.tours:
            par_modele_ctx[cle].append(t[1] + t[2])
            par_modele_cache[cle][0] += t[1]
            par_modele_cache[cle][1] += t[2]
    ag["jetons_tours_par_modele"] = {
        k: {
            "contexte": distribution(v, 0),
            "part_cache": round(par_modele_cache[k][1] / sum(par_modele_cache[k]), 4)
            if sum(par_modele_cache[k])
            else None,
        }
        for k, v in par_modele_ctx.items()
    }
    moy_run = [statistics.fmean([t[1] + t[2] for t in r.tours]) for r in runs if r.tours]
    ag["jetons_tours"]["moyenne_des_moyennes_par_run"] = round(statistics.fmean(moy_run))
    dire("\n== Jetons par tour :", ag["jetons_tours"])
    dire("   par modèle :", json.dumps(ag["jetons_tours_par_modele"], ensure_ascii=False))
    finish = Counter(t[5] for t in tours_tous)
    ag["finish_reason"] = dict(finish)

    # Écritures refusées
    n_ecr = sum(r.ecritures for r in runs)
    refus = Counter(m for r in runs for m, _, _ in r.refus)
    n_refus = sum(refus.values())
    ag["ecritures"] = {
        "ecrire_aide": n_ecr,
        "refusees": taux(n_refus, n_ecr),
        "par_motif": {k: taux(v, n_ecr) for k, v in refus.most_common()},
        "yaml_ou_schema": taux(refus["yaml_invalide"] + refus["hors_schema"], n_ecr),
        "runs_avec_au_moins_un_refus": taux(sum(1 for r in runs if r.refus), len(runs)),
        "runs_avec_ecriture": sum(1 for r in runs if r.ecritures),
    }
    msg_yaml = Counter(
        re.sub(r"\d+", "N", msg.split("—", 1)[-1].strip())[:60]
        for r in runs
        for m, msg, _ in r.refus
        if m == "yaml_invalide"
    )
    ag["ecritures"]["messages_yaml"] = dict(msg_yaml.most_common(6))
    ag["ecritures"]["diagnostic_yaml_invalide"] = dict(
        Counter(d for r in runs for d in r.diag_yaml).most_common()
    )
    par_modele_refus = defaultdict(lambda: [0, 0])
    for r in runs:
        cle = r.modele_entete if r.modele else ("défaut→" + (r.modele_revele or "?"))
        par_modele_refus[cle][0] += len(r.refus)
        par_modele_refus[cle][1] += r.ecritures
    ag["ecritures"]["par_modele"] = {k: taux(a, b) for k, (a, b) in par_modele_refus.items()}
    dire("\n== Écritures :", json.dumps(ag["ecritures"], ensure_ascii=False))

    # Vérificateur
    n_verif = sum(r.verif_appels for r in runs)
    n_reel = sum(r.verif_reelles for r in runs)
    n_panne = sum(r.verif_pannes for r in runs)
    acceptees = [r for r in runs if r.issue == "acceptee"]
    toutes_pannes = [r for r in acceptees if r.verif_reelles and r.verif_pannes == r.verif_reelles]
    ag["verificateur"] = {
        "appels_outil": n_verif,
        "passages_reels": n_reel,
        "pannes": taux(n_panne, n_reel),
        "plafond_atteint": sum(r.verif_plafond for r in runs),
        "erreurs_outil": sum(r.verif_erreur_outil for r in runs),
        "passages_par_run_accepte": distribution([r.verif_reelles for r in acceptees], 1),
        "passages_par_run_accepte_avant_plafond": distribution(
            [r.verif_reelles for r in acceptees if not r.verif_format_plafond], 1
        ),
        "passages_par_run_accepte_avec_plafond": distribution(
            [r.verif_reelles for r in acceptees if r.verif_format_plafond], 1
        ),
        "bloquant_premier_avec_plafond": taux(
            sum(
                1
                for r in acceptees
                if r.verif_format_plafond and r.verif_bloquants and r.verif_bloquants[0] > 0
            ),
            sum(1 for r in acceptees if r.verif_format_plafond and r.verif_bloquants),
        ),
        "bloquant_dernier_avec_plafond": taux(
            sum(
                1
                for r in acceptees
                if r.verif_format_plafond and r.verif_bloquants and r.verif_bloquants[-1] > 0
            ),
            sum(1 for r in acceptees if r.verif_format_plafond and r.verif_bloquants),
        ),
        "acceptees_sans_verification_reelle": sum(1 for r in acceptees if r.verif_reelles == 0),
        "acceptees_dont_toutes_verifs_en_panne": taux(len(toutes_pannes), len(acceptees)),
        "acceptees_avec_au_moins_une_panne": taux(
            sum(1 for r in acceptees if r.verif_pannes), len(acceptees)
        ),
        "bloquant_premier_passage": taux(
            sum(1 for r in acceptees if r.verif_bloquants and r.verif_bloquants[0] > 0),
            sum(1 for r in acceptees if r.verif_bloquants),
        ),
        "bloquant_dernier_passage": taux(
            sum(1 for r in acceptees if r.verif_bloquants and r.verif_bloquants[-1] > 0),
            sum(1 for r in acceptees if r.verif_bloquants),
        ),
    }
    ag["verificateur"]["slugs_toutes_verifs_en_panne"] = [
        f"{r.slug}@{r.debut}" for r in toutes_pannes
    ]
    dire("\n== Vérificateur :", json.dumps(ag["verificateur"], ensure_ascii=False)[:1500])

    # Hors périmètre
    hp = [r for r in runs if r.hp_appels]
    ag["hors_perimetre"] = {
        "runs_appel": len(hp),
        "runs_accepte": sum(1 for r in hp if r.hp_accepte),
        "slugs": [f"{r.slug}@{r.debut[:10]}" for r in hp],
    }
    dire("\n== declarer_hors_perimetre :", ag["hors_perimetre"])

    # Pannes
    classes = Counter(e.split(":")[0] for r in runs for e in r.erreurs_appel)
    ag["erreurs_appel"] = dict(classes)

    # ---------------------------------------------------------- 3. semaines
    sem = defaultdict(list)
    for r in runs:
        sem[semaine(r.debut)].append(r)
    lignes_sem = []
    for s in sorted(sem):
        rs = sem[s]
        iss = Counter(r.issue for r in rs)
        lignes_sem.append(
            {
                "semaine": s,
                "du": min(r.debut[:10] for r in rs),
                "au": max(r.debut[:10] for r in rs),
                "runs": len(rs),
                "aides_distinctes": len({r.slug for r in rs}),
                "cout_somme": round(sum(r.cout_meilleur for r in rs), 2),
                "cout_runs_complets": round(sum(r.cout_total or 0 for r in rs), 2),
                "runs_cout_inconnu_ou_partiel": sum(
                    1 for r in rs if r.cout_inconnu or r.cout_total is None
                ),
                "tours_moyens": round(statistics.fmean([r.nb_tours for r in rs]), 1),
                "modeles": ";".join(
                    f"{k}:{v}"
                    for k, v in Counter(
                        r.modele_entete if r.modele else "defaut" for r in rs
                    ).most_common()
                ),
                **{
                    i: iss.get(i, 0)
                    for i in (
                        "acceptee",
                        "hors_perimetre",
                        "refusee_controles",
                        "abandon",
                        "panne",
                        "interrompu",
                    )
                },
            }
        )
    with (SORTIE / "semaines.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes_sem[0]))
        w.writeheader()
        w.writerows(lignes_sem)
    ag["semaines"] = lignes_sem
    dire("\n== Par semaine ISO")
    for li in lignes_sem:
        dire("  ", li)

    # ---------------------------------------------------------- 4. devenir
    file_attente = yaml.load(FILE_ATTENTE.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)
    yamls = {p.name[: -len(".yaml")] for p in AIDES.glob("*.yaml")}
    echecs = {p.name[: -len(".yaml.echec")]: p for p in AIDES.glob("*.yaml.echec")}
    histo = historique_echec()

    # 4a. reproduction du chiffre de la file : « 72 $ sur 134 $ »
    blocs = {s: t["ingestion"] for s, t in file_attente.items() if t.get("ingestion")}
    cout_fa = {s: b.get("cout_usd") for s, b in blocs.items()}
    tot_fa = sum(c for c in cout_fa.values() if c is not None)
    ign_fa = sum(
        c for s, c in cout_fa.items() if c is not None and file_attente[s].get("statut") == "ignore"
    )
    n_ign = sum(1 for s in blocs if file_attente[s].get("statut") == "ignore")
    fa_defaut = sum(1 for b in blocs.values() if str(b.get("modele", "")).startswith("(défaut"))
    ag["file_attente"] = {
        "entrees": len(file_attente),
        "statuts": dict(Counter(t.get("statut") for t in file_attente.values())),
        "avec_bloc_ingestion": len(blocs),
        "cout_consigne_total": round(tot_fa, 2),
        "cout_consigne_ignore": round(ign_fa, 2),
        "taches_ingerees_puis_ignore": taux(n_ign, len(blocs)),
        "cout_null": sum(1 for c in cout_fa.values() if c is None),
        "modele_defaut": taux(fa_defaut, len(blocs)),
        "modeles": dict(Counter(str(b.get("modele")) for b in blocs.values())),
        "tentatives": dict(Counter(b.get("tentatives") for b in blocs.values())),
    }
    dire("\n== File d'attente (reproduction des chiffres consignés)")
    dire("  ", json.dumps(ag["file_attente"], ensure_ascii=False))
    motifs_fa = Counter(
        famille_motif(file_attente[s].get("motif_ignore"))
        for s in blocs
        if file_attente[s].get("statut") == "ignore"
    )
    cout_motif_fa = defaultdict(float)
    for s in blocs:
        if file_attente[s].get("statut") == "ignore" and cout_fa[s] is not None:
            cout_motif_fa[famille_motif(file_attente[s].get("motif_ignore"))] += cout_fa[s]
    ag["file_attente"]["ignore_par_motif"] = {
        k: {"taches": v, "cout": round(cout_motif_fa[k], 2)} for k, v in motifs_fa.most_common()
    }
    dire("   ingérées puis ignore, par motif :", ag["file_attente"]["ignore_par_motif"])

    # 4b. sens des .yaml.echec
    lignes_echec = []
    for slug, p in sorted(echecs.items()):
        tete = p.read_text(encoding="utf-8", errors="replace").split("\n", 1)[0]
        t = file_attente.get(slug)
        statut = t.get("statut") if t else "(hors file)"
        motif = famille_motif(t.get("motif_ignore")) if t else ""
        h = histo.get(slug, ("", "", "", ""))
        entete = tete.startswith("# ÉCHEC D'INGESTION")
        if slug in yamls:
            sens = "coexiste_avec_yaml"
        elif t and (t.get("doublon_de") or motif == "doublon_url"):
            sens = "doublon"
        elif entete and statut in ("echec", "valide", "en_cours", "a_valider"):
            sens = "echec_pipeline_en_cours"
        elif statut == "ignore":
            sens = "ecartee_apres_ingestion"
        elif entete:
            sens = "echec_pipeline_autre_statut"
        elif statut == "(hors file)":
            sens = "hors_file"
        else:
            sens = f"autre_statut_{statut}"
        lignes_echec.append(
            {
                "slug": slug,
                "entete_echec": entete,
                "entete": tete[:120] if entete else "",
                "statut_file": statut,
                "motif_famille": motif,
                "doublon_de": (t or {}).get("doublon_de") or "",
                "commit": h[0],
                "date_commit": h[1],
                "message_commit": h[2],
                "creation": h[3],
                "sens": sens,
            }
        )
    with (SORTIE / "echec_sens.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes_echec[0]))
        w.writeheader()
        w.writerows(lignes_echec)
    ag["yaml_echec"] = {
        "fichiers": len(echecs),
        "yaml": len(yamls),
        "avec_entete_echec": sum(1 for x in lignes_echec if x["entete_echec"]),
        "sens": dict(Counter(x["sens"] for x in lignes_echec)),
        "ecartees_par_motif": dict(
            Counter(
                x["motif_famille"] for x in lignes_echec if x["sens"] == "ecartee_apres_ingestion"
            )
        ),
        "entete_x_statut": dict(
            Counter(f"{x['entete_echec']}|{x['statut_file']}" for x in lignes_echec)
        ),
        "creation": dict(Counter(x["creation"] for x in lignes_echec)),
        "sens_x_creation": dict(
            Counter(f"{x['sens']}|{x['creation']}" for x in lignes_echec).most_common()
        ),
        "sens_x_commit": dict(
            Counter(f"{x['sens']}|{x['commit']}" for x in lignes_echec).most_common()
        ),
        "commits": dict(
            Counter(f"{x['commit']} {x['date_commit']}" for x in lignes_echec).most_common(12)
        ),
    }
    dire("\n== .yaml.echec :", json.dumps(ag["yaml_echec"], ensure_ascii=False))

    # 4c. dépense des journaux par devenir du slug
    par_slug = defaultdict(list)
    for r in runs:
        par_slug[r.slug].append(r)
    lignes_dev = []
    for slug, rs in sorted(par_slug.items()):
        t = file_attente.get(slug)
        if slug in yamls:
            devenir = "au_catalogue"
        elif slug in echecs:
            devenir = "yaml_echec:" + next(x["sens"] for x in lignes_echec if x["slug"] == slug)
        else:
            devenir = "aucun_fichier"
        lignes_dev.append(
            {
                "slug": slug,
                "runs": len(rs),
                "premier": rs[0].debut,
                "dernier": rs[-1].debut,
                "cout_journaux": round(sum(r.cout_meilleur for r in rs), 4),
                "runs_cout_partiel": sum(1 for r in rs if r.cout_total is None or r.cout_inconnu),
                "issue_derniere": rs[-1].issue,
                "devenir": devenir,
                "statut_file": t.get("statut") if t else "(hors file)",
                "motif_famille": famille_motif(t.get("motif_ignore")) if t else "",
                "cout_file": (t.get("ingestion") or {}).get("cout_usd") if t else None,
            }
        )
    with (SORTIE / "devenir_slugs.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes_dev[0]))
        w.writeheader()
        w.writerows(lignes_dev)
    dev = defaultdict(lambda: [0, 0, 0.0])
    for x in lignes_dev:
        cle = (x["devenir"], x["statut_file"])
        dev[cle][0] += 1
        dev[cle][1] += x["runs"]
        dev[cle][2] += x["cout_journaux"]
    ag["devenir"] = {
        f"{a} | {b}": {"slugs": n, "runs": rr, "cout": round(c, 2)}
        for (a, b), (n, rr, c) in sorted(dev.items(), key=lambda kv: -kv[1][2])
    }
    tot_j = sum(x["cout_journaux"] for x in lignes_dev)
    ecarte = sum(
        x["cout_journaux"]
        for x in lignes_dev
        if x["statut_file"] == "ignore" and x["devenir"] != "au_catalogue"
    )
    ag["devenir_synthese"] = {
        "slugs": len(lignes_dev),
        "cout_journaux_total": round(tot_j, 2),
        "cout_slugs_ignore_hors_catalogue": round(ecarte, 2),
        "cout_slugs_au_catalogue": round(
            sum(x["cout_journaux"] for x in lignes_dev if x["devenir"] == "au_catalogue"), 2
        ),
        "slugs_au_catalogue": sum(1 for x in lignes_dev if x["devenir"] == "au_catalogue"),
        "slugs_ignore_hors_catalogue": sum(
            1 for x in lignes_dev if x["statut_file"] == "ignore" and x["devenir"] != "au_catalogue"
        ),
    }
    dev_motif = defaultdict(lambda: [0, 0.0])
    for x in lignes_dev:
        if x["statut_file"] == "ignore":
            dev_motif[x["motif_famille"]][0] += 1
            dev_motif[x["motif_famille"]][1] += x["cout_journaux"]
    ag["devenir_ignore_par_motif_journaux"] = {
        k: {"slugs": n, "cout": round(c, 2)} for k, (n, c) in sorted(dev_motif.items())
    }
    dire(
        "\n== Devenir des slugs (coût des journaux) :",
        json.dumps(ag["devenir"], ensure_ascii=False),
    )
    dire("   synthèse :", ag["devenir_synthese"])
    dire("   ignore par motif :", ag["devenir_ignore_par_motif_journaux"])

    # Dépense par semaine selon le devenir d'aujourd'hui du slug
    groupe_slug = {}
    for x in lignes_dev:
        if x["devenir"] == "au_catalogue":
            g = "catalogue"
        elif x["statut_file"] == "ignore":
            g = "doublon" if x["motif_famille"] == "doublon_url" else "ecartee"
        else:
            g = "autre"
        groupe_slug[x["slug"]] = g
    sem_dev = defaultdict(lambda: defaultdict(float))
    for r in runs:
        sem_dev[semaine(r.debut)][groupe_slug[r.slug]] += r.cout_meilleur
    ag["semaines_cout_par_devenir"] = {
        s: {g: round(v, 2) for g, v in d.items()} for s, d in sorted(sem_dev.items())
    }
    dire("   coût par semaine et devenir :", ag["semaines_cout_par_devenir"])
    # Dépense des runs « acceptés » sur des aides écartées ensuite
    acc_ecarte = [
        r for r in runs if r.issue == "acceptee" and groupe_slug[r.slug] in ("ecartee", "doublon")
    ]
    ag["acceptees_puis_ecartees"] = {
        "runs": taux(len(acc_ecarte), sum(1 for r in runs if r.issue == "acceptee")),
        "cout": round(sum(r.cout_meilleur for r in acc_ecarte), 2),
    }
    dire("   runs acceptés dont l'aide est écartée aujourd'hui :", ag["acceptees_puis_ecartees"])

    # File vs journaux : slugs couverts
    fa_slugs = set(blocs)
    j_slugs = set(par_slug)
    ag["couverture_file_journaux"] = {
        "slugs_file_avec_bloc": len(fa_slugs),
        "slugs_journaux": len(j_slugs),
        "communs": len(fa_slugs & j_slugs),
        "file_sans_journal": len(fa_slugs - j_slugs),
        "journal_sans_bloc_file": len(j_slugs - fa_slugs),
    }
    # comparaison du coût de la dernière tentative
    ecarts_cout = []
    for s in fa_slugs & j_slugs:
        c = cout_fa[s]
        d = blocs[s].get("debut")
        r = next((x for x in par_slug[s] if d and x.debut == d), None)
        if r is not None and c is not None and r.cout_total is not None:
            ecarts_cout.append(abs(round(r.cout_total, 4) - c))
    ag["couverture_file_journaux"]["cout_derniere_tentative_apparie"] = len(ecarts_cout)
    ag["couverture_file_journaux"]["ecart_max"] = max(ecarts_cout) if ecarts_cout else None
    dire("\n== Couverture file / journaux :", ag["couverture_file_journaux"])

    # Fiches de review
    revs = lire_reviews()
    ag["reviews"] = {
        "fiches": len(revs),
        "avec_entete_pipeline": sum(1 for x in revs if x["pipeline"]),
        "cout_somme_entetes": round(sum(x["cout"] or 0 for x in revs), 2),
        "cout_inconnu": sum(1 for x in revs if x["pipeline"] and x["cout"] is None),
        "modeles": dict(Counter(x["modele"] for x in revs if x["pipeline"])),
        "hors_perimetre": sum(1 for x in revs if x["hors_perimetre"]),
    }
    dire("\n== Fiches de review :", ag["reviews"])

    # ---------------------------------------------------------- 5. durées
    extremes = sorted(avec_duree, key=lambda r: -r.duree_s)[:10]
    lignes_ext = []
    for r in extremes:
        lignes_ext.append(
            {
                "slug": r.slug,
                "debut": r.debut,
                "fichier": f"{r.fichier}:{r.ligne}",
                "duree_s": r.duree_s,
                "tours": r.nb_tours,
                "issue": r.issue,
                "fin_boucle": r.fin_boucle,
                "cout": r.cout_meilleur,
                "modele": r.modele_entete,
                "transitoires": r.transitoires,
                "erreurs_appel": len(r.erreurs_appel),
                "elagages": r.elagages,
                "rappels": r.rappels,
                "ecritures": r.ecritures,
                "refus": len(r.refus),
                "verif": r.verif_reelles,
                "sortie_tokens": sum(t[3] for t in r.tours),
                "s_par_tour": round(r.duree_s / max(r.nb_tours, 1)),
                "appels_top": ";".join(f"{k}:{v}" for k, v in r.appels.most_common(4)),
            }
        )
    with (SORTIE / "durees_extremes.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes_ext[0]))
        w.writeheader()
        w.writerows(lignes_ext)
    ag["durees_extremes"] = lignes_ext
    dire("\n== 10 durées les plus longues")
    for li in lignes_ext:
        dire("  ", li)
    ag["s_par_tour"] = distribution([r.duree_s / r.nb_tours for r in avec_duree if r.nb_tours], 1)
    ag["s_par_sortie_1k"] = distribution(
        [
            r.duree_s / (sum(t[3] for t in r.tours) / 1000)
            for r in avec_duree
            if sum(t[3] for t in r.tours) > 1000
        ],
        1,
    )
    dire("  secondes par tour :", ag["s_par_tour"])
    # Ce qui explique la durée : régression sur une moitié, R2 sur l'autre.
    obs = [
        (
            [sum(t[3] for t in r.tours) / 1000, float(r.verif_reelles), float(r.nb_tours), 1.0],
            float(r.duree_s),
        )
        for r in avec_duree
    ]
    app = [o for i, o in enumerate(obs) if i % 2 == 0]
    ctl = [o for i, o in enumerate(obs) if i % 2 == 1]
    coef = moindres_carres([o[0] for o in app], [o[1] for o in app])
    pred = [sum(c * v for c, v in zip(coef, o[0], strict=True)) for o in ctl]
    moy = statistics.fmean(o[1] for o in ctl)
    r2 = 1 - sum((o[1] - p) ** 2 for o, p in zip(ctl, pred, strict=True)) / sum(
        (o[1] - moy) ** 2 for o in ctl
    )
    ag["regression_duree"] = {
        "variables": ["k_jetons_sortie_extracteur", "passages_verif", "tours", "constante"],
        "coefficients_s": [round(c, 2) for c in coef],
        "n_apprentissage": len(app),
        "n_controle": len(ctl),
        "r2_controle": round(r2, 3),
    }
    dire("  régression de la durée :", ag["regression_duree"])

    (SORTIE / "agregats.json").write_text(
        json.dumps(ag, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    (SORTIE / "resume.txt").write_text("\n".join(resume) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
