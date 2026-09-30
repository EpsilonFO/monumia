"""Fusionne des faits de l'ontologie : une table YAML, des remplacements sûrs.

Script de MIGRATION, jetable par nature : il sert à résorber le passif de
`facts_pending.yaml` (526 faits proposés, dont ~90 refont un fait déjà présent).
Une fois la résorption faite, il n'a plus d'usage courant — les gardes posées à
l'écriture (`retirer_fait`, avertissement de proximité, audit de fin de run)
sont là pour que le passif ne se reconstitue pas.

    uv run python scripts/fusionner_faits.py data/fusions/lot-2.yaml --dry-run
    uv run python scripts/fusionner_faits.py data/fusions/lot-2.yaml

Le mandat est ÉTROIT, et c'est tout ce qui le rend sûr : remplacer une clé de
fait par une autre dans `fact:` et `applies_if.fact`, et retirer l'entrée du
fait absorbé de `facts_pending.yaml`. Rien d'autre — jamais un `predicate`,
jamais un `kind`, jamais un `effect`. Les fusions qui demandent d'inverser un
prédicat (polarité opposée) ou d'élargir un `eq` en `in` (un enum qui absorbe
des booléens) NE SONT PAS de son ressort : il les REFUSE, parce que les
appliquer mécaniquement inverserait un critère d'éligibilité en silence.

Format de la table :

    fusions:
      - garder: porteur_exploitant_agricole
        retirer: porteur_agricole_msa
        motif: Même question, deux formulations issues de deux runs.
      - retirer: brouillon_abandonne          # sans `garder` : suppression sèche,
        motif: Plus aucune aide ne le cite.   # refusée si une aide le cite encore.

88 remplacements à la main, c'est une erreur garantie — et une erreur qu'aucun
test ne rattraperait, puisque le lint accepte n'importe quelle clé qui existe.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ingestion.faits import _decouper_bloc
from lint_aides_data import lint

from aides_schema import (
    AIDES_DIR,
    FACTS_FILE,
    FACTS_PENDING_FILE,
    charger_yaml,
    load_facts,
    load_pending_facts,
)


@dataclass(frozen=True)
class Fusion:
    """Une ligne de la table. `garder` vide = suppression sèche."""

    retirer: str
    garder: str = ""
    motif: str = ""


@dataclass
class Rapport:
    """Ce que la migration a fait, ou ferait. `erreurs` non vide = rien n'est écrit."""

    erreurs: list[str] = field(default_factory=list)
    remplacements: dict[str, list[str]] = field(default_factory=dict)
    retires: list[str] = field(default_factory=list)
    fichiers_touches: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.erreurs

    @property
    def occurrences(self) -> int:
        return sum(len(v) for v in self.remplacements.values())

    def texte(self) -> str:
        lignes: list[str] = []
        for cle, cibles in sorted(self.remplacements.items()):
            lignes.append(
                f"  {cle}  →  {len(cibles)} occurrence(s) dans {len(set(cibles))} aide(s)"
            )
        if self.retires:
            lignes.append(f"  {len(self.retires)} fait(s) retiré(s) de facts_pending.yaml")
        lignes.append(
            f"  TOTAL : {self.occurrences} occurrence(s), "
            f"{len(self.fichiers_touches)} fichier(s) d'aide, {len(self.retires)} fait(s) retiré(s)"
        )
        for e in self.erreurs:
            lignes.append(f"  ERREUR : {e}")
        return "\n".join(lignes)


# ---------------------------------------------------------------------------
# Lecture et validation de la table
# ---------------------------------------------------------------------------


def charger_table(chemin: Path) -> tuple[list[Fusion], list[str]]:
    """Lit la table YAML. Rend (fusions, erreurs de forme)."""
    try:
        brut = charger_yaml(chemin.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return [], [f"table illisible : {exc}"]
    if not isinstance(brut, dict) or not isinstance(brut.get("fusions"), list):
        return [], ["la table doit être un objet avec une liste `fusions`"]
    fusions, erreurs = [], []
    for i, ligne in enumerate(brut["fusions"], 1):
        if not isinstance(ligne, dict) or not ligne.get("retirer"):
            erreurs.append(f"fusion n° {i} : `retirer` manquant")
            continue
        fusions.append(
            Fusion(
                retirer=str(ligne["retirer"]),
                garder=str(ligne.get("garder") or ""),
                motif=str(ligne.get("motif") or ""),
            )
        )
    return fusions, erreurs


def verifier(
    fusions: list[Fusion],
    facts: dict,
    pending: dict,
) -> list[str]:
    """Tout ce qui doit être vrai AVANT d'écrire quoi que ce soit.

    Le refus porte sur la table entière : une migration à moitié appliquée
    laisserait des aides citant un fait supprimé, et le lint ne dirait pas
    lesquelles rattraper.
    """
    erreurs: list[str] = []
    tous = {**facts, **pending}
    vus: set[str] = set()
    for f in fusions:
        if f.retirer in facts:
            erreurs.append(
                f"« {f.retirer} » est APPROUVÉ (facts.yaml) — le retirer est une décision "
                "humaine, pas une migration : le déplacer à la main si c'est bien voulu."
            )
        elif f.retirer not in pending:
            erreurs.append(f"« {f.retirer} » n'est pas dans facts_pending.yaml — déjà fusionné ?")
        if f.retirer in vus:
            erreurs.append(f"« {f.retirer} » apparaît deux fois dans la table")
        vus.add(f.retirer)
        if not f.garder:
            continue
        if f.garder == f.retirer:
            erreurs.append(f"« {f.retirer} » fusionné avec lui-même")
        if f.garder not in tous:
            erreurs.append(f"« {f.garder} » (garder) n'existe ni dans facts.yaml ni dans pending")
            continue
        if f.retirer not in tous:
            # Déjà signalé plus haut ; la compatibilité n'a rien à comparer.
            continue
        erreurs.extend(_verifier_compatibilite(f, tous))
    # Une chaîne A→B→C appliquerait A→B alors que B n'existera plus.
    cibles = {f.garder for f in fusions if f.garder}
    for enchainee in sorted(cibles & vus):
        erreurs.append(
            f"« {enchainee} » est à la fois gardé et retiré — scinder la table en deux lots, "
            "sinon l'ordre d'application décide du résultat."
        )
    return erreurs


# Les mêmes deux négateurs que `ingestion.ontologie` : « non » et « sans »
# seulement, pour ne refuser que ce qui est vraiment une inversion.
_NEGATEURS = frozenset({"non", "sans"})


def _polarite_opposee(a: str, b: str) -> str | None:
    """Le négateur qui sépare deux clés par ailleurs identiques, ou None.

    C'est le SEUL cas dangereux qu'aucun contrôle de type, de scope ou d'options
    ne voit : `chauffage_fioul_apres_travaux` et `chauffage_sans_fioul_apres_travaux`
    sont deux booléens de même scope sans options, donc parfaitement compatibles
    aux yeux de tout le reste — et les fusionner sans inverser le prédicat des
    aides du camp retiré transforme un refus en acceptation, sans rien laisser
    voir au diff.
    """
    jetons_a, jetons_b = a.split("_"), b.split("_")
    reste_a = [j for j in jetons_a if j not in _NEGATEURS]
    reste_b = [j for j in jetons_b if j not in _NEGATEURS]
    if reste_a != reste_b:
        return None
    ecart = ({j for j in jetons_a if j in _NEGATEURS}) ^ ({j for j in jetons_b if j in _NEGATEURS})
    return sorted(ecart)[0] if ecart else None


def _verifier_compatibilite(f: Fusion, tous: dict) -> list[str]:
    """Le mandat étroit, énoncé une seule fois : ce que le remplacement de clé suffit à faire.

    Hors de là, le prédicat des aides doit changer — et un script qui touche à
    un prédicat sans avoir lu la source écrit un critère d'éligibilité faux sans
    que personne ne le voie. Ces cas remontent à l'humain.
    """
    a, b = tous[f.retirer], tous[f.garder]
    erreurs = []
    negateur = _polarite_opposee(f.retirer, f.garder)
    if negateur:
        erreurs.append(
            f"{f.retirer} → {f.garder} : les deux clés ne diffèrent que par « {negateur} » — "
            "polarité opposée. Fusionner impose d'inverser le prédicat des aides du fait "
            "retiré, ce que ce script ne fait pas : à traiter à la main, règlement en main."
        )
    if a.type != b.type:
        erreurs.append(
            f"{f.retirer} ({a.type}) → {f.garder} ({b.type}) : types différents. Les prédicats "
            "des aides passeraient de `eq: true` à `in: [...]` — à relire aide par aide, "
            "hors du mandat de ce script."
        )
    if a.scope != b.scope:
        erreurs.append(
            f"{f.retirer} (scope {a.scope}) → {f.garder} (scope {b.scope}) : le scope dit à QUOI "
            "la question se rattache, c'est une décision de modèle et pas un détail de nommage."
        )
    ids_a = {o.id for o in a.options or []}
    ids_b = {o.id for o in b.options or []}
    if ids_a - ids_b:
        erreurs.append(
            f"{f.retirer} → {f.garder} : option(s) sans équivalent dans le fait gardé "
            f"({', '.join(sorted(ids_a - ids_b))}) — les prédicats qui les citent deviendraient faux."
        )
    return erreurs


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


def _motif(cle: str) -> re.Pattern[str]:
    """`fact: <cle>` en fin de ligne — la forme sous laquelle le YAML est écrit."""
    return re.compile(rf"^(?P<avant>\s*fact:\s*){re.escape(cle)}(?P<apres>\s*)$", re.MULTILINE)


def appliquer(
    fusions: list[Fusion],
    *,
    aides_dir: Path = AIDES_DIR,
    pending_path: Path = FACTS_PENDING_FILE,
    facts_path: Path = FACTS_FILE,
    ecrire: bool = False,
) -> Rapport:
    """Applique (ou simule) la table. N'écrit RIEN si la vérification échoue."""
    load_facts.cache_clear()
    load_pending_facts.cache_clear()
    facts = load_facts(facts_path)
    pending = load_pending_facts(pending_path)
    rapport = Rapport(erreurs=verifier(fusions, facts, pending))
    if not rapport.ok:
        return rapport

    renommages = {f.retirer: f.garder for f in fusions if f.garder}
    suppressions = [f.retirer for f in fusions if not f.garder]

    nouveaux: dict[Path, str] = {}
    for chemin in sorted(aides_dir.glob("*.yaml")):
        texte = chemin.read_text(encoding="utf-8")
        modifie = texte
        for cle, cible in renommages.items():
            modifie, n = _motif(cle).subn(rf"\g<avant>{cible}\g<apres>", modifie)
            if n:
                rapport.remplacements.setdefault(f"{cle} → {cible}", []).extend([chemin.stem] * n)
        # Une suppression sèche ne doit toucher AUCUNE aide : si le fichier en
        # porte encore une trace, c'est que l'inventaire est périmé.
        for cle in suppressions:
            if _motif(cle).search(modifie):
                rapport.erreurs.append(
                    f"« {cle} » est marqué en suppression sèche mais {chemin.stem} le référence "
                    "encore — refaire l'inventaire, ou lui donner un `garder`."
                )
        if modifie != texte:
            nouveaux[chemin] = modifie
            rapport.fichiers_touches.append(chemin.stem)
    if not rapport.ok:
        return rapport

    texte_pending = pending_path.read_text(encoding="utf-8")
    for cle in [f.retirer for f in fusions]:
        bornes = _decouper_bloc(texte_pending, cle)
        if bornes is None:
            rapport.erreurs.append(
                f"« {cle} » introuvable en tête de ligne dans {pending_path.name}"
            )
            continue
        debut, fin = bornes
        lignes = texte_pending.splitlines(keepends=True)
        texte_pending = "".join(lignes[:debut] + lignes[fin:])
        rapport.retires.append(cle)
    if not rapport.ok:
        return rapport

    # L'invariant qui tient toute la migration : le fichier réécrit porte
    # exactement les faits d'avant, moins ceux qu'on retire. Un découpage
    # textuel qui aurait mordu sur un voisin se voit ici, avant l'écriture.
    attendu = set(pending) - {f.retirer for f in fusions}
    obtenu = set(charger_yaml(texte_pending) or {})
    if obtenu != attendu:
        rapport.erreurs.append(
            f"le retrait aurait emporté d'autres faits (perdus : "
            f"{sorted(attendu - obtenu) or 'aucun'}, en trop : {sorted(obtenu - attendu) or 'aucun'})"
        )
        return rapport

    if ecrire:
        for chemin, contenu in nouveaux.items():
            chemin.write_text(contenu, encoding="utf-8")
        pending_path.write_text(texte_pending.rstrip("\n") + "\n", encoding="utf-8")
    return rapport


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="fusionner_faits.py",
        description="Fusionne des faits de l'ontologie d'après une table YAML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("table", type=Path, help="table de fusion YAML")
    ap.add_argument("--dry-run", action="store_true", help="afficher sans rien écrire")
    ap.add_argument(
        "--sans-lint", action="store_true", help="ne pas rejouer le lint après écriture"
    )
    args = ap.parse_args(argv)

    fusions, erreurs = charger_table(args.table)
    if erreurs:
        for e in erreurs:
            print(f"ERREUR : {e}")
        return 2
    print(f"{len(fusions)} fusion(s) dans {args.table}")

    rapport = appliquer(fusions, ecrire=not args.dry_run)
    print(rapport.texte())
    if not rapport.ok:
        print("\nRien n'a été écrit.")
        return 1
    if args.dry_run:
        print("\n--dry-run : rien n'a été écrit.")
        return 0

    if args.sans_lint:
        return 0
    print("\nLint du catalogue après fusion :")
    resultat = lint()
    for e in resultat.erreurs[:20]:
        print(f"  {e}")
    print("  ✓ lint OK" if resultat.ok else f"  ✗ {len(resultat.erreurs)} erreur(s)")
    return 0 if resultat.ok else 1


if __name__ == "__main__":
    sys.exit(main())
