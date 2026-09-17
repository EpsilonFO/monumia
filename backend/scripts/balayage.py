#!/usr/bin/env python
"""Balayage séquentiel de plusieurs territoires, sans surveillance.

    uv run python scripts/balayage.py grand-est nouvelle-aquitaine pays-de-la-loire hauts-de-france

Enchaîne, POUR CHAQUE territoire l'un après l'autre, la prospection complète
(collecte, tri, lecture) ; puis, UNE SEULE FOIS à la fin, l'ingestion de tout ce
qui a été retenu.

Pourquoi ce découpage plutôt qu'un `prospecter.py --auto` par région
-------------------------------------------------------------------
La prospection écrit dans `data/prospection/<territoire>/`, un dossier par
territoire : deux prospections ne peuvent pas se marcher dessus. L'ingestion,
elle, écrit dans `data/facts_pending.yaml`, que les agents modifient sans
verrou — c'est là, et seulement là, que la concurrence casse des choses (des
faits proposés par un agent écrasés par un autre, sans laisser de trace).

Une seule ingestion finale donne en plus **un seul audit d'ontologie**, et cet
audit voit alors les faits de tous les territoires d'un coup. Un audit par
région ne verrait jamais qu'un doublon entre deux régions — c'est précisément
ce qui avait laissé passer la moitié des 471 faits de la vague précédente.

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
import time
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "scripts"))

from pipeline.etat import FILE_ATTENTE, charger, mettre_a_jour  # noqa: E402
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


def valider_en_attente(cles: list[str]) -> int:
    """Passe les `a_valider` des territoires balayés en `valide`.

    C'est le point de contrôle humain que `--auto` saute. On le saute aussi,
    volontairement : le tri se fera sur les fiches de review, à la fin.
    """
    etat = charger(FILE_ATTENTE)
    a_valider = [s for s, t in etat.items() if t.territoire in cles and t.statut == "a_valider"]
    for slug in a_valider:
        mettre_a_jour(FILE_ATTENTE, slug, statut="valide")
    return len(a_valider)


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
        print("\n⚠ un run est déjà vivant — deux ingestions en parallèle écrasent des faits :")
        for li in vivants[:4]:
            print(f"    {li[:110]}")
        print("  Attends sa fin, ou tue-le, puis relance avec --reprendre.")
        return 1

    if etat["debut"] is None:
        etat["debut"] = horodatage
    debut = time.monotonic()

    # --- phase 1 : prospection, un territoire à la fois ---------------------
    for i, cle in enumerate(a_faire, 1):
        journal = DOSSIER_LOGS / f"{horodatage}-prospection-{cle}.log"
        t0 = time.monotonic()
        print(f"\n[{i}/{len(a_faire)}] prospection {cle} …", flush=True)
        try:
            code = prospecter(cle, args, journal)
        except KeyboardInterrupt:
            print("\n  interrompu — état enregistré, relancer avec --reprendre")
            ecrire_etat(etat)
            return 130
        duree = time.monotonic() - t0
        if code == 0:
            etat["faits"].append(cle)
            ecrire_etat(etat)
            print(f"      terminé en {duree / 60:.1f} min — {journal.name}")
        else:
            print(f"      ÉCHEC (code {code}) en {duree / 60:.1f} min — voir {journal.name}")
            print("      le balayage continue ; ce territoire sera retenté par --reprendre")

    # --- phase 2 : validation puis ingestion unique -------------------------
    if args.sans_ingestion:
        print("\n--sans-ingestion : la file reste en `a_valider`, rien n'a été ingéré.")
        return 0

    n = valider_en_attente(retenus)
    print(f"\n=== {n} candidate(s) passée(s) en `valide` sans relecture")
    if n == 0:
        print("    rien à ingérer.")
        return 0

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

    total = (time.monotonic() - debut) / 60
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
