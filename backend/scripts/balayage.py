#!/usr/bin/env python
"""Balayage de plusieurs territoires, sans surveillance.

    uv run python scripts/balayage.py grand-est nouvelle-aquitaine pays-de-la-loire hauts-de-france

Prospection de tous les territoires (collecte, tri, lecture), plusieurs en
parallèle ; puis, UNE SEULE FOIS à la fin, l'ingestion de tout ce qui a été
retenu.

Pourquoi ce découpage plutôt qu'un `prospecter.py --auto` par région
-------------------------------------------------------------------
Ce n'est PAS une question de corruption de fichier : les trois fichiers
partagés (`file-attente.yaml`, `facts_pending.yaml`, les fiches d'état) passent
tous par le `flock` inter-processus de `pipeline/verrou.py`, posé après
l'incident du 2026-04 où deux ingestions s'étaient écrasées. Plusieurs runs
concurrents ne se détruisent pas.

La raison est l'AUDIT. Une seule ingestion finale donne **un seul audit
d'ontologie**, et cet audit voit alors les faits de tous les territoires d'un
coup. Un audit par région ne pourrait jamais voir un doublon entre deux
régions — c'est précisément ce qui avait laissé passer la moitié des 471 faits
de la vague précédente.

D'où l'asymétrie : la prospection se parallélise librement
(`--parallele-prospection`, chaque territoire ayant son propre dossier), mais
l'ingestion reste un run unique, dont `--parallele` règle le débit interne.

Reprise
-------
Le script note les territoires terminés dans `data/prospection/balayage.json`.
`--reprendre` repart de là : utile après un Ctrl-C, une coupure réseau ou une
nuit trop courte. Un territoire déjà balayé n'est pas rebalayé.

Ce que le script ne fait JAMAIS
------------------------------
`git add`, un commit, ou `load_aides_yaml.py`. Il écrit dans le working tree et
imprime, à la fin, les commandes qui restent à lancer à la main.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "scripts"))

from pipeline.etat import (  # noqa: E402
    FILE_ATTENTE,
    charger,
    doublons_par_url,
    ecrire,
    motif_non_promotion,
    promouvables,
)
from pipeline.verrou import verrou_fichier  # noqa: E402
from prospection.territoires import charger_territoires  # noqa: E402

ETAT_BALAYAGE = RACINE / "data" / "prospection" / "balayage.json"
DOSSIER_LOGS = RACINE / "data" / "reviews" / "logs" / "balayage"


# --------------------------------------------------------------------------- #
# Sélection des territoires
# --------------------------------------------------------------------------- #
def territoires_a_balayer(cles: list[str], *, avec_departements: bool, forcer: bool):
    """(retenus, ignorés) — les régions demandées, puis leurs départements.

    Un territoire `sans_point_entree` n'a pas de guide identifié : le balayer
    consomme un run pour ne rien rendre. 92 des 101 départements sont dans ce
    cas, d'où le filtre par défaut.
    """
    tous = charger_territoires()
    inconnues = [c for c in cles if c not in tous]
    if inconnues:
        raise SystemExit(f"territoire(s) inconnu(s) : {', '.join(inconnues)}")

    retenus: list[str] = []
    ignores: list[tuple[str, str]] = []

    def ajouter(cle: str) -> None:
        t = tous[cle]
        if t.statut == "sans_point_entree" and not forcer:
            ignores.append((cle, "sans point d'entrée — ne rendrait rien"))
            return
        retenus.append(cle)

    for cle in cles:
        ajouter(cle)
        if not avec_departements:
            continue
        enfants = sorted(
            k for k, t in tous.items() if t.type != "region" and getattr(t, "region", None) == cle
        )
        for k in enfants:
            ajouter(k)
    return retenus, ignores


# --------------------------------------------------------------------------- #
# Garde-fous
# --------------------------------------------------------------------------- #
def runs_en_cours() -> list[str]:
    """Les prospections/ingestions déjà vivantes — en lancer une de plus est l'erreur à éviter."""
    try:
        sortie = subprocess.run(
            ["pgrep", "-fl", "prospecter.py|ingerer.py|balayage.py"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
    except FileNotFoundError:
        return []
    moi = str(os.getpid())
    lignes = [
        li
        for li in sortie.splitlines()
        if li.strip() and not li.startswith(moi + " ") and "pgrep" not in li
    ]
    return lignes


def charger_etat() -> dict:
    if ETAT_BALAYAGE.exists():
        return json.loads(ETAT_BALAYAGE.read_text(encoding="utf-8"))
    return {"faits": [], "debut": None}


def ecrire_etat(etat: dict) -> None:
    ETAT_BALAYAGE.parent.mkdir(parents=True, exist_ok=True)
    ETAT_BALAYAGE.write_text(json.dumps(etat, indent=2, ensure_ascii=False), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Étapes
# --------------------------------------------------------------------------- #
def prospecter(cle: str, args, journal: Path) -> int:
    """Prospection complète d'un territoire, SANS `--auto` : on n'ingère pas ici."""
    cmd = [
        sys.executable,
        "scripts/prospecter.py",
        cle,
        "--model-tri",
        args.model_tri,
        "--model-lecture",
        args.model_lecture,
    ]
    if args.rejouer:
        cmd.append("--rejouer")
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("w", encoding="utf-8") as sortie:
        proc = subprocess.run(cmd, cwd=RACINE, stdout=sortie, stderr=subprocess.STDOUT)
    return proc.returncode


@dataclass
class Promotion:
    """Ce qu'une passe de validation a fait, et ce qu'elle a laissé de côté."""

    promus: list[str] = field(default_factory=list)
    doublons: dict[str, str] = field(default_factory=dict)
    restants: dict[str, str] = field(default_factory=dict)

    def rendre(self) -> str:
        """Le compte rendu imprimé — c'est lui qui remplace le contrôle humain."""
        lignes = [f"{len(self.promus)} candidate(s) passée(s) en `valide`"]
        if self.doublons:
            lignes.append(
                f"  {len(self.doublons)} écartée(s) comme doublon d'URL : "
                + ", ".join(f"{a} → {b}" for a, b in sorted(self.doublons.items())[:6])
                + (" …" if len(self.doublons) > 6 else "")
            )
        if self.restants:
            par_motif: dict[str, int] = {}
            for motif in self.restants.values():
                par_motif[motif.split(" —")[0].split(" (")[0]] = (
                    par_motif.get(motif.split(" —")[0].split(" (")[0], 0) + 1
                )
            lignes.append(f"  {len(self.restants)} laissée(s) en `a_valider` :")
            for motif, n in sorted(par_motif.items(), key=lambda kv: -kv[1]):
                lignes.append(f"    {n:4d}  {motif}")
            lignes.append("  `prospecter.py valider <territoire>` les liste une par une.")
        return "\n".join(lignes)


def valider_en_attente(cles: list[str], *, tout: bool = False) -> Promotion:
    """Passe en `valide` les `a_valider` des territoires balayés QUI PASSENT LE TEST.

    Deux filtres, dans cet ordre, et ils sont le point de contrôle qui
    manquait :

    1. les doublons d'URL sur la file ENTIÈRE (`ignore` + `doublon_de`) — 51
       aides déjà au catalogue sont revenues en `-2` avec la même URL ;
    2. le test du destinataire et la famille (`promouvables`) — 140 candidates
       rangées `adjacente` et 5 dites `hors_perimetre` par le tri ont été
       ingérées quand même, parce que cette fonction promouvait tout ce qui
       était `a_valider`.

    Ce qui n'est pas promu N'EST PAS perdu : il reste `a_valider`, et
    `prospecter.py valider` le liste avec son motif. `--promouvoir-tout` rend
    l'ancien comportement, pour une file relue et corrigée à la main.

    UN SEUL verrou et UNE SEULE écriture pour tout le lot. La version
    précédente appelait `mettre_a_jour` slug par slug, et chaque appel relisait
    puis réécrivait le fichier entier : sur les 936 candidates du balayage du
    2026-09-18, cela faisait 936 réécritures d'un YAML de 1 200 entrées, à
    1,6 promotion par seconde — dix minutes de promotion pure, qui grandissent
    avec le carré de la file.
    """
    resultat = Promotion()
    with verrou_fichier(FILE_ATTENTE):
        taches = charger(FILE_ATTENTE)
        # Le dédoublonnage regarde TOUTE la file, pas seulement les territoires
        # de ce run : le doublon d'une aide du Grand Est peut venir d'un
        # balayage des Pays de la Loire, et c'est arrivé.
        for slug, survivant in doublons_par_url(taches).items():
            if taches[slug].statut != "a_valider":
                continue
            resultat.doublons[slug] = survivant
            taches[slug] = taches[slug].model_copy(
                update={
                    "statut": "ignore",
                    "doublon_de": survivant,
                    "motif_ignore": f"doublon d'URL de {survivant}",
                }
            )
        candidats = [s for s, t in taches.items() if t.territoire in cles]
        resultat.promus = promouvables(taches, candidats, tout=tout)
        for slug in resultat.promus:
            taches[slug] = taches[slug].model_copy(update={"statut": "valide"})
        for slug in candidats:
            if slug in resultat.promus or taches[slug].statut != "a_valider":
                continue
            motif = motif_non_promotion(taches[slug])
            if motif:
                resultat.restants[slug] = motif
        if resultat.promus or resultat.doublons:
            ecrire(FILE_ATTENTE, taches)
    return resultat


#: `phase_ingestion` n'a rien trouvé à promouvoir — ce n'est pas une erreur.
RIEN_A_INGERER = -1


def phase_ingestion(cles: list[str], args, horodatage: str) -> int:
    """Promotion filtrée puis ingestion unique. Extraite pour `--reprendre-ingestion`.

    Les 351 tâches perdues en panne réseau le 2026-09-18 n'avaient aucun moyen
    de repartir sans rebalayer les quatre régions : la prospection et
    l'ingestion étaient soudées dans `main`.
    """
    promotion = valider_en_attente(cles, tout=args.promouvoir_tout)
    print("\n=== promotion")
    print("    " + promotion.rendre().replace("\n", "\n    "))
    if not promotion.promus:
        print("    rien à ingérer.")
        return RIEN_A_INGERER

    journal = DOSSIER_LOGS / f"{horodatage}-ingestion.log"
    print(f"=== ingestion unique, {args.parallele} en parallèle — {journal.name}", flush=True)
    t0 = time.monotonic()
    try:
        code = ingerer(args, journal)
    except KeyboardInterrupt:
        print("\n  interrompu — relancer `ingerer.py --reprendre` APRÈS avoir vérifié qu'aucun")
        print("  processus ne tourne, puis `ingerer.py --file-attente`.")
        return 130
    print(f"    ingestion terminée (code {code}) en {(time.monotonic() - t0) / 60:.1f} min")
    return code


def ingerer(args, journal: Path) -> int:
    """UNE ingestion pour tous les territoires — un seul audit d'ontologie à la fin."""
    cmd = [
        sys.executable,
        "scripts/ingerer.py",
        "--file-attente",
        "--parallele",
        str(args.parallele),
        "--budget-aide",
        str(args.budget_aide),
        "--budget-total",
        str(args.budget_total),
        "--model",
        args.model_ingestion,
        "--model-verif",
        args.model_verif,
    ]
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("w", encoding="utf-8") as sortie:
        proc = subprocess.run(cmd, cwd=RACINE, stdout=sortie, stderr=subprocess.STDOUT)
    return proc.returncode


# --------------------------------------------------------------------------- #
# Bilan
# --------------------------------------------------------------------------- #
def bilan_balayage(
    horodatage: str,
    cles: list[str],
    avant: dict,
    *,
    lint=None,
    tronc=None,
    audit=None,
    etat_path: Path | None = None,
    sortie: Path | None = None,
) -> Path:
    """Écrit `data/reviews/<date>-bilan-balayage.md` : ce qu'un run a produit.

    Le balayage du 2026-09-18 s'est terminé sans qu'aucun fichier ne dise ce
    qu'il avait fait. Il a fallu trois jours d'analyse pour découvrir 643 aides
    nouvelles, 563 faits, 130 URL partagées, 351 échecs réseau jamais rejoués
    et un cliquet de questionnaire rouge sur cinq profils. Chacun de ces
    chiffres se calcule en quelques secondes — il manquait juste de les écrire.

    Les quatre sources sont INJECTÉES (`lint`, `tronc`, `audit`) : elles coûtent
    de dix secondes à deux minutes chacune, et le bilan doit rester testable
    sans elles. `avant` est l'état du catalogue relevé au démarrage — sans lui,
    le bilan dirait « 1 079 aides » là où l'information est « +643 ».
    """
    from datetime import date as _date

    jour = _date.today()
    cible = sortie or (RACINE / "data" / "reviews" / f"{jour.isoformat()}-bilan-balayage.md")
    etat = charger(etat_path or FILE_ATTENTE)
    concernes = {s: t for s, t in etat.items() if t.territoire in cles}
    par_statut: dict[str, int] = {}
    for tache in concernes.values():
        par_statut[tache.statut] = par_statut.get(tache.statut, 0) + 1
    a_relire = sorted(s for s, t in concernes.items() if t.a_relire)
    echecs = {
        s: (t.ingestion.motif_echec if t.ingestion else None) or "(sans motif)"
        for s, t in concernes.items()
        if t.statut == "echec"
    }

    lignes = [
        f"# Bilan de balayage — {jour.isoformat()} ({horodatage})",
        "",
        f"Territoires : {', '.join(cles)}",
        "",
        "## Ce que le run a produit",
        "",
        "| mesure | valeur |",
        "|---|---:|",
        f"| Aides au catalogue | {avant.get('aides', 0)} → {_aides_du_catalogue()} |",
        f"| Faits en attente | {avant.get('pending', 0)} → {_compter_pending()} |",
        f"| Candidates de ces territoires | {len(concernes)} |",
    ]
    for statut in ("ingere", "valide", "a_valider", "ignore", "echec", "en_cours"):
        if par_statut.get(statut):
            lignes.append(f"| dont `{statut}` | {par_statut[statut]} |")
    lignes += [
        "",
        "## À relire en priorité",
        "",
        f"{len(a_relire)} aide(s) livrée(s) avec un bloquant adversarial non re-vérifié "
        "(plafond de 3 passages). 132 aides étaient dans ce cas le 2026-09-18, sans que "
        "rien ne le dise.",
        "",
    ]
    lignes += [f"- `{s}`" for s in a_relire] or ["_aucune_"]

    lignes += ["", "## Échecs", ""]
    if not echecs:
        lignes.append("_aucun_")
    for slug, motif in sorted(echecs.items()):
        lignes.append(f"- `{slug}` — {motif[:140]}")
    lignes += [
        "",
        "Une panne du fournisseur rend la tâche `valide` : elle repartira au passage "
        "suivant. Ce qui est `echec` demande une décision humaine.",
        "",
        "  uv run python scripts/ingerer.py --relancer-echecs --seulement-sans-yaml",
    ]

    lignes += ["", "## Lint", ""]
    lignes.append(lint() if lint else "_non lancé_")

    lignes += ["", "## Doublons d'URL", ""]
    doublons = _doublons_du_catalogue()
    lignes.append(
        f"{len(doublons)} groupe(s) d'aides partagent une URL de fiche. "
        "`uv run python scripts/dedoublonner_aides.py --dry-run`"
        if doublons
        else "_aucun_"
    )
    for li in doublons[:10]:
        lignes.append(f"- {li}")
    if len(doublons) > 10:
        lignes.append(f"- … et {len(doublons) - 10} autre(s)")

    lignes += ["", "## Questionnaire — ce que le lot coûte à tous les propriétaires", ""]
    lignes.append(tronc() if tronc else "_non mesuré_")

    lignes += ["", "## Ontologie", ""]
    lignes.append(audit() if audit else "_non audité_")

    lignes += [
        "",
        "## Ce qu'il reste à faire à la main",
        "",
        "```bash",
        "uv run python scripts/lint_aides_data.py",
        "uv run python scripts/auditer_ontologie.py --sans-modele",
        "uv run python scripts/dedoublonner_aides.py --dry-run",
        "uv run python scripts/retyper_faits.py --retirer-orphelins --dry-run",
        "# relire les fiches de review, puis :",
        "git add -A && git commit",
        "uv run python scripts/load_aides_yaml.py",
        "```",
    ]
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return cible


def _aides_du_catalogue() -> int:
    return len(list((RACINE / "data" / "aides").glob("*.yaml")))


def _compter_pending() -> int:
    from aides_schema import load_pending_facts

    load_pending_facts.cache_clear()
    return len(load_pending_facts())


def _doublons_du_catalogue() -> list[str]:
    """Les groupes d'URL partagées, vus par la même règle que le lint."""
    try:
        from lint_aides_data import check_urls_partagees

        from aides_schema import load_all_aides

        return check_urls_partagees(list(load_all_aides().values()))
    except Exception as exc:  # noqa: BLE001 — un bilan raté ne casse pas un run réussi
        return [f"(mesure indisponible : {exc})"]


def _ecrire_bilan(horodatage: str, cles: list[str], avant: dict) -> Path:
    """Le bilan avec ses trois mesures réelles. Ne lève jamais.

    Chacune peut échouer pour une raison qui n'a rien à voir avec le run (une
    migration pas appliquée, un modèle d'audit mal configuré) : un bilan
    partiel vaut mieux qu'un run qui se termine sur une exception après six
    heures de travail.
    """

    def _lint() -> str:
        from lint_aides_data import lint as lancer_lint

        rapport = lancer_lint()
        tete = "✓ lint OK" if rapport.ok else f"✗ {len(rapport.erreurs)} erreur(s)"
        return "\n".join([tete, *(f"- {e}" for e in rapport.erreurs[:20])])

    def _tronc() -> str:
        import subprocess

        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_questionnaire_tronc_commun.py", "-q"],
            cwd=RACINE,
            capture_output=True,
            text=True,
            check=False,
        )
        verdict = (
            "✓ le tronc commun ne regrossit pas"
            if proc.returncode == 0
            else (
                "✗ **le cliquet du questionnaire est ROUGE** — des questions sont entrées dans "
                "le tronc commun de tous les propriétaires"
            )
        )
        return "\n".join([verdict, "", "```", proc.stdout.strip()[-3000:], "```"])

    def _audit() -> str:
        from auditer_ontologie import auditer as lancer_audit
        from ingestion import ontologie as onto

        return onto.rendre_markdown(lancer_audit(sans_modele=True), jour=date.today())

    def _sur(fn):
        def _essai() -> str:
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001
                return f"_mesure indisponible : {type(exc).__name__}: {exc}_"

        return _essai

    return bilan_balayage(
        horodatage,
        cles,
        avant,
        lint=_sur(_lint),
        tronc=_sur(_tronc),
        audit=_sur(_audit),
    )


def etat_du_catalogue() -> dict:
    """Le relevé d'avant-run : ce à quoi le bilan comparera."""
    return {"aides": _aides_du_catalogue(), "pending": _compter_pending()}


# --------------------------------------------------------------------------- #
def main() -> int:
    p = argparse.ArgumentParser(
        description="Balaye plusieurs territoires l'un après l'autre, puis ingère le tout.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("territoires", nargs="*", help="clés de territoires.yaml (des régions)")
    p.add_argument(
        "--sans-departements",
        action="store_true",
        help="ne balayer que les régions nommées, sans leurs départements",
    )
    p.add_argument(
        "--forcer",
        action="store_true",
        help="inclure les territoires `sans_point_entree` (ne rendra rien)",
    )
    p.add_argument("--reprendre", action="store_true", help="sauter les territoires déjà balayés")
    p.add_argument("--rejouer", action="store_true", help="réutiliser les .jsonl de prospection")
    p.add_argument(
        "--sans-ingestion",
        action="store_true",
        help="s'arrêter après la prospection, sans rien ingérer",
    )
    p.add_argument("--dry-run", action="store_true", help="afficher le plan, ne rien lancer")
    p.add_argument(
        "--bilan-seul",
        action="store_true",
        help="ne rien balayer : écrire le bilan de ce que la file contient déjà",
    )
    p.add_argument(
        "--sans-bilan",
        action="store_true",
        help="ne pas écrire le bilan de fin de run (il coûte une minute de mesures)",
    )
    p.add_argument(
        "--promouvoir-tout",
        action="store_true",
        help="promouvoir TOUT ce qui est `a_valider`, sans appliquer le test du "
        "destinataire (ancien comportement : pour une file relue à la main)",
    )
    p.add_argument(
        "--reprendre-ingestion",
        action="store_true",
        help="sauter la prospection et reprendre directement à la promotion puis "
        "l'ingestion (après une panne réseau)",
    )
    p.add_argument(
        "--parallele-prospection",
        type=int,
        default=4,
        help="territoires prospectés en même temps (défaut : 4)",
    )
    p.add_argument("--parallele", type=int, default=6, help="ingestions simultanées (défaut : 6)")
    p.add_argument("--budget-aide", type=float, default=1.50, help="plafond $ par aide")
    p.add_argument("--budget-total", type=float, default=60.0, help="plafond $ pour l'ingestion")
    p.add_argument("--model-tri", default="ds-v41")
    p.add_argument("--model-lecture", default="ds-v41")
    p.add_argument("--model-ingestion", default="ds-v41")
    p.add_argument("--model-verif", default="ds-v41")
    args = p.parse_args()

    if not args.territoires:
        p.error("nommer au moins un territoire (ex. : grand-est nouvelle-aquitaine)")

    retenus, ignores = territoires_a_balayer(
        args.territoires,
        avec_departements=not args.sans_departements,
        forcer=args.forcer,
    )

    if args.bilan_seul:
        horodatage = datetime.now().strftime("%Y-%m-%d-%H%M")
        cible = _ecrire_bilan(horodatage, retenus, etat_du_catalogue())
        print(f"Bilan écrit : {cible}")
        return 0

    etat = charger_etat()
    deja = set(etat["faits"]) if args.reprendre else set()
    a_faire = [c for c in retenus if c not in deja]

    horodatage = datetime.now().strftime("%Y-%m-%d-%H%M")
    print(f"=== balayage séquentiel — {len(a_faire)} territoire(s)")
    for c in a_faire:
        print(f"    · {c}")
    if deja:
        print(f"    ({len(deja)} déjà balayé(s), sautés par --reprendre)")
    if ignores:
        print(f"\n    {len(ignores)} territoire(s) ignoré(s) :")
        for c, motif in ignores[:6]:
            print(f"      - {c} : {motif}")
        if len(ignores) > 6:
            print(f"      … et {len(ignores) - 6} autre(s)")
    print(
        f"\n    ingestion finale : {'SAUTÉE' if args.sans_ingestion else ''}"
        f"{'' if args.sans_ingestion else f'{args.parallele} en parallèle, ${args.budget_total:.0f} max'}"
    )
    print(f"    journaux : {DOSSIER_LOGS.relative_to(RACINE)}/")

    if args.dry_run:
        print("\n--dry-run : rien n'a été lancé.")
        return 0

    vivants = runs_en_cours()
    if vivants:
        print("\n⚠ un run est déjà vivant — deux balayages se disputeraient la file :")
        for li in vivants[:4]:
            print(f"    {li[:110]}")
        print("  Attends sa fin, ou tue-le, puis relance avec --reprendre.")
        return 1

    if etat["debut"] is None:
        etat["debut"] = horodatage
    debut = time.monotonic()
    # Relevé AVANT : sans lui le bilan dirait « 1 079 aides » là où
    # l'information est « +643 ».
    avant = etat_du_catalogue()

    if args.reprendre_ingestion:
        print("\n=== --reprendre-ingestion : prospection sautée")
        code = phase_ingestion(retenus, args, horodatage)
        return 0 if code in (0, RIEN_A_INGERER) else code

    # --- phase 1 : prospection ----------------------------------------------
    # Parallélisable sans risque : chaque territoire écrit dans son propre
    # `data/prospection/<clé>/`, et les deux fichiers partagés qu'il touche —
    # `file-attente.yaml` et la fiche de prospection — passent par le `flock`
    # de `pipeline/verrou.py`, qui est inter-processus.
    verrou_etat = threading.Lock()

    def un_territoire(indice_cle: tuple[int, str]) -> tuple[str, int, float]:
        i, cle = indice_cle
        journal = DOSSIER_LOGS / f"{horodatage}-prospection-{cle}.log"
        t0 = time.monotonic()
        print(f"  [{i}/{len(a_faire)}] {cle} — démarre", flush=True)
        code = prospecter(cle, args, journal)
        duree = time.monotonic() - t0
        with verrou_etat:
            if code == 0:
                etat["faits"].append(cle)
                ecrire_etat(etat)
                print(f"  [{i}/{len(a_faire)}] {cle} — terminé en {duree / 60:.1f} min", flush=True)
            else:
                print(
                    f"  [{i}/{len(a_faire)}] {cle} — ÉCHEC (code {code}) en {duree / 60:.1f} min,"
                    f" voir {journal.name}",
                    flush=True,
                )
        return cle, code, duree

    print(f"\n=== prospection — {args.parallele_prospection} territoire(s) à la fois\n")
    try:
        with ThreadPoolExecutor(max_workers=args.parallele_prospection) as pool:
            resultats = list(pool.map(un_territoire, enumerate(a_faire, 1)))
    except KeyboardInterrupt:
        print("\n  interrompu — état enregistré, relancer avec --reprendre")
        ecrire_etat(etat)
        return 130
    echecs = [c for c, code, _ in resultats if code != 0]
    if echecs:
        print(
            f"\n  {len(echecs)} territoire(s) en échec, retentés par --reprendre : {', '.join(echecs)}"
        )

    # --- phase 2 : validation puis ingestion unique -------------------------
    if args.sans_ingestion:
        print("\n--sans-ingestion : la file reste en `a_valider`, rien n'a été ingéré.")
        return 0

    code = phase_ingestion(retenus, args, horodatage)
    if code == 130:
        return 130
    if code == RIEN_A_INGERER:
        return 0

    total = (time.monotonic() - debut) / 60
    if not args.sans_bilan:
        print("\n=== bilan (lint, tronc commun, audit d'ontologie)…", flush=True)
        cible = _ecrire_bilan(horodatage, retenus, avant)
        print(f"    {cible}")
    print(f"\n=== balayage terminé en {total / 60:.1f} h")
    print(f"    journaux : {DOSSIER_LOGS.relative_to(RACINE)}/{horodatage}-*.log")
    print("\nCe qu'il reste à faire à la main :")
    print("    uv run python scripts/lint_aides_data.py")
    print("    # relire les fiches de review, puis :")
    print("    git add -A && git commit")
    print("    uv run python scripts/load_aides_yaml.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
