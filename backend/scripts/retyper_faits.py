"""Retype les conditions qui citent un fait, puis retire le fait. Table YAML.

Script de MIGRATION, jumeau de `fusionner_faits.py` et jetable comme lui : il
sert à résorber le lot du 2026-09-18 (563 faits proposés pour 643 aides, dont
431 cités par UNE seule aide). Les gardes posées à l'écriture — plafond de trois
faits par aide, refus des booléens à seuil, refus des questions de 500
caractères — sont là pour que le passif ne se reconstitue pas.

    uv run python scripts/retyper_faits.py data/fusions/lot-s-engage.yaml --dry-run
    uv run python scripts/retyper_faits.py --s-engage --dry-run
    uv run python scripts/retyper_faits.py data/fusions/lot-s-engage.yaml

Le mandat est ÉTROIT, comme celui de `fusionner_faits.py`, et pour la même
raison : une condition qu'on retype garde son `text` et sa `quote` — ce qui
change, c'est son STATUT dans le moteur, pas ce que la source dit.

  - un `s_engage_*` devient `kind: info` + `effect: info` : un engagement du
    demandeur se vérifie au dossier, pas au questionnaire. 48 faits du lot, 59
    gates, et personne ne répond « non » à « acceptez-vous la charte ? » ;
  - tout autre fait devient `kind: manual_check` + `effect: info` : une exigence
    propre à une aide, qu'aucun fait partageable ne porte, s'affiche « à
    confirmer avec l'organisme » plutôt que de poser une question à tous les
    propriétaires.

Dans les deux cas, `fact`, `predicate` et `derogation_possible` disparaissent,
et `notes` gagne une ligne de provenance. Le fait est ensuite retiré de
`facts_pending.yaml`.

Format de la table :

    retypages:
      - fait: s_engage_charte_qualite
        motif: Engagement du demandeur, vérifié au dossier.
      - fait: itineraire_eligible_pdipr
        motif: Liste d'exclusions propre au règlement, aucune portée partagée.

Ce que le script REFUSE, et rien de ce qui suit n'est négociable :

  - un fait approuvé (`facts.yaml`) : le retirer est une décision humaine ;
  - un fait cité par un `applies_if` : c'est un périmètre, pas une condition —
    le retyper changerait la portée de l'aide, pas le statut d'un critère ;
  - un fichier d'aide que `safe_dump(safe_load(t)) != t`, c'est-à-dire porteur
    de commentaires ou d'une mise en forme qu'une réécriture détruirait. Les
    YAML du lot sont tous écrits par `ecrire_aide`, donc stables ; ceux qu'un
    humain a annotés ne le sont pas, et ce sont précisément ceux qu'il ne faut
    pas toucher à la machine.

Neutre pour le cliquet `manual_check` : celui-ci ne compte que les `gate` et les
`manual_check` sans `notes`, et ce script produit des `effect: info` avec notes.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import date
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
    Aide,
    load_facts,
    load_pending_facts,
)

#: Préfixe des faits d'ENGAGEMENT. Un `s_engage_*` décrit ce que le demandeur
#: promet de faire, pas une propriété du bien ou du porteur : il n'a jamais sa
#: place dans le questionnaire, parce que la réponse est toujours « oui ».
PREFIXE_ENGAGEMENT = "s_engage_"


@dataclass(frozen=True)
class Retypage:
    """Une ligne de la table."""

    fait: str
    motif: str = ""

    @property
    def kind(self) -> str:
        """`info` pour un engagement, `manual_check` sinon.

        La distinction n'est pas cosmétique : une `info` ne s'affiche pas comme
        un critère à vérifier (l'utilisateur n'a rien à faire d'un engagement
        qu'il prendra en signant), un `manual_check` si.
        """
        return "info" if self.fait.startswith(PREFIXE_ENGAGEMENT) else "manual_check"


@dataclass
class Rapport:
    """Ce que la migration a fait, ou ferait. `erreurs` non vide = rien n'est écrit."""

    erreurs: list[str] = field(default_factory=list)
    #: fait → [slug/condition] retypés
    retypages: dict[str, list[str]] = field(default_factory=dict)
    retires: list[str] = field(default_factory=list)
    fichiers_touches: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.erreurs

    @property
    def conditions(self) -> int:
        return sum(len(v) for v in self.retypages.values())

    def texte(self) -> str:
        lignes: list[str] = []
        for fait, cibles in sorted(self.retypages.items()):
            lignes.append(f"  {fait}  →  {len(cibles)} condition(s) : {', '.join(cibles)}")
        lignes.append(
            f"  TOTAL : {self.conditions} condition(s) retypée(s), "
            f"{len(self.fichiers_touches)} fichier(s) d'aide, "
            f"{len(self.retires)} fait(s) retiré(s)"
        )
        for e in self.erreurs:
            lignes.append(f"  ERREUR : {e}")
        return "\n".join(lignes)


# ---------------------------------------------------------------------------
# Lecture et validation de la table
# ---------------------------------------------------------------------------


def charger_table(chemin: Path) -> tuple[list[Retypage], list[str]]:
    """Lit la table YAML. Rend (retypages, erreurs de forme)."""
    try:
        brut = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return [], [f"table illisible : {exc}"]
    if not isinstance(brut, dict) or not isinstance(brut.get("retypages"), list):
        return [], ["la table doit être un objet avec une liste `retypages`"]
    retypages, erreurs = [], []
    for i, ligne in enumerate(brut["retypages"], 1):
        if not isinstance(ligne, dict) or not ligne.get("fait"):
            erreurs.append(f"retypage n° {i} : `fait` manquant")
            continue
        retypages.append(Retypage(fait=str(ligne["fait"]), motif=str(ligne.get("motif") or "")))
    return retypages, erreurs


def table_des_engagements(pending: dict) -> list[Retypage]:
    """Tous les `s_engage_*` du fichier en attente, sans distinction.

    Les EXCEPTIONS se retirent à la main de la table produite : un engagement qui
    porte une contrainte durable et réutilisable — « conserver 15 ans »,
    « maintenir la plantation 7 ans », « ouvrir au public » — mérite de rester
    un fait, de préférence sous la forme d'un integer (`duree_*_ans`) qui porte
    sa durée dans le prédicat. Le script ne sait pas les reconnaître, et
    prétendre le contraire ferait perdre en silence des critères qui comptent.
    """
    return [
        Retypage(fait=cle, motif="Engagement du demandeur, affiché dans le dossier.")
        for cle in sorted(pending)
        if cle.startswith(PREFIXE_ENGAGEMENT)
    ]


def _round_trip_stable(chemin: Path) -> bool:
    """Le fichier survit-il à `safe_load` puis `safe_dump` sans rien perdre ?

    C'est le seul test qui distingue un YAML écrit par `ecrire_aide` — que l'on
    peut réécrire sans dommage — d'un fichier annoté à la main, dont les
    commentaires seraient effacés en silence.
    """
    texte = chemin.read_text(encoding="utf-8")
    try:
        charge = yaml.safe_load(texte)
    except yaml.YAMLError:
        return False
    return yaml.safe_dump(charge, allow_unicode=True, sort_keys=False, width=100) == texte


def verifier(
    retypages: list[Retypage],
    facts: dict,
    pending: dict,
    *,
    aides_dir: Path = AIDES_DIR,
) -> list[str]:
    """Tout ce qui doit être vrai AVANT d'écrire quoi que ce soit.

    Le refus porte sur la table ENTIÈRE : une migration à moitié appliquée
    laisserait des aides citant un fait supprimé, et le lint ne dirait pas
    lesquelles rattraper.
    """
    erreurs: list[str] = []
    vus: set[str] = set()
    for r in retypages:
        if r.fait in facts:
            erreurs.append(
                f"« {r.fait} » est APPROUVÉ (facts.yaml) — le retirer est une décision "
                "humaine, pas une migration."
            )
        elif r.fait not in pending:
            erreurs.append(f"« {r.fait} » n'est pas dans facts_pending.yaml — déjà retypé ?")
        if r.fait in vus:
            erreurs.append(f"« {r.fait} » apparaît deux fois dans la table")
        vus.add(r.fait)

    cles = {r.fait for r in retypages}
    for chemin in sorted(aides_dir.glob("*.yaml")):
        try:
            aide = Aide.model_validate(yaml.safe_load(chemin.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001 — le lint le dira mieux
            erreurs.append(f"{chemin.stem} : illisible ({exc})")
            continue
        vises = _conditions_visees(aide, cles)
        if aide.applies_if and aide.applies_if.fact in cles:
            erreurs.append(
                f"{chemin.stem} : `applies_if` d'aide sur « {aide.applies_if.fact} » — c'est un "
                "PÉRIMÈTRE, pas une condition. Le retyper changerait la portée de l'aide : "
                "hors du mandat de ce script."
            )
        for cond in aide.conditions:
            if cond.applies_if and cond.applies_if.fact in cles:
                erreurs.append(
                    f"{chemin.stem} / {cond.id} : `applies_if` de condition sur "
                    f"« {cond.applies_if.fact} » — clause d'applicabilité, hors mandat."
                )
        if vises and not _round_trip_stable(chemin):
            erreurs.append(
                f"{chemin.stem} : le fichier ne survit pas à une réécriture YAML (commentaires "
                "ou mise en forme manuelle). Conditions visées : "
                f"{', '.join(vises)}. À retyper à la main — c'est justement un fichier "
                "qu'on n'écrase pas à la machine."
            )
    return erreurs


def _conditions_visees(aide: Aide, cles: set[str]) -> list[str]:
    """Les ids de condition qui gatent (ou citent) l'un des faits de la table."""
    return [c.id for c in aide.conditions if c.fact in cles]


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


def _retyper_condition(brut: dict, r: Retypage, jour: date) -> dict:
    """La condition réécrite : `text` et `quote` intacts, le reste effacé.

    `text` et `quote` sont ce que la SOURCE dit, et ce script ne lit aucune
    source : il n'a rien à en dire. Ce qu'il change est le statut de la
    condition dans le moteur.
    """
    notes = str(brut.get("notes") or "").strip()
    provenance = (
        f"Retypé le {jour.isoformat()} : {r.motif or 'exigence propre à cette aide'} "
        f"(ex-fait {r.fait})."
    )
    sortie = {
        cle: val
        for cle, val in brut.items()
        if cle not in ("fact", "predicate", "derogation_possible", "kind", "effect", "notes")
    }
    # L'ordre des clés suit celui d'`ecrire_aide` : id, text, kind, effect, …
    ordonne: dict = {}
    for cle in ("id", "text"):
        if cle in sortie:
            ordonne[cle] = sortie.pop(cle)
    ordonne["kind"] = r.kind
    ordonne["effect"] = "info"
    ordonne["notes"] = f"{notes} {provenance}".strip() if notes else provenance
    ordonne.update(sortie)
    return ordonne


def appliquer(
    retypages: list[Retypage],
    *,
    aides_dir: Path = AIDES_DIR,
    pending_path: Path = FACTS_PENDING_FILE,
    facts_path: Path = FACTS_FILE,
    jour: date | None = None,
    ecrire: bool = False,
) -> Rapport:
    """Applique (ou simule) la table. N'écrit RIEN si la vérification échoue."""
    jour = jour or date.today()
    load_facts.cache_clear()
    load_pending_facts.cache_clear()
    facts = load_facts(facts_path)
    pending = load_pending_facts(pending_path)
    rapport = Rapport(erreurs=verifier(retypages, facts, pending, aides_dir=aides_dir))
    if not rapport.ok:
        return rapport

    par_cle = {r.fait: r for r in retypages}
    nouveaux: dict[Path, str] = {}
    for chemin in sorted(aides_dir.glob("*.yaml")):
        texte = chemin.read_text(encoding="utf-8")
        brut = yaml.safe_load(texte)
        conditions = brut.get("conditions") or []
        touche = False
        for i, cond in enumerate(conditions):
            r = par_cle.get(cond.get("fact") or "")
            if r is None:
                continue
            conditions[i] = _retyper_condition(cond, r, jour)
            rapport.retypages.setdefault(r.fait, []).append(f"{chemin.stem}/{cond['id']}")
            touche = True
        if not touche:
            continue
        try:
            Aide.model_validate(brut)
        except Exception as exc:  # noqa: BLE001
            rapport.erreurs.append(f"{chemin.stem} : le retypage produit un YAML invalide — {exc}")
            continue
        nouveaux[chemin] = yaml.safe_dump(brut, allow_unicode=True, sort_keys=False, width=100)
        rapport.fichiers_touches.append(chemin.stem)
    if not rapport.ok:
        return rapport

    texte_pending = pending_path.read_text(encoding="utf-8")
    for cle in par_cle:
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

    # Le même invariant que `fusionner_faits` : le fichier réécrit porte
    # exactement les faits d'avant, moins ceux qu'on retire. Un découpage
    # textuel qui aurait mordu sur un voisin se voit ici, avant l'écriture.
    attendu = set(pending) - set(par_cle)
    obtenu = set(yaml.safe_load(texte_pending) or {})
    if obtenu != attendu:
        rapport.erreurs.append(
            "le retrait aurait emporté d'autres faits (perdus : "
            f"{sorted(attendu - obtenu) or 'aucun'}, "
            f"en trop : {sorted(obtenu - attendu) or 'aucun'})"
        )
        return rapport

    if ecrire:
        for chemin, contenu in nouveaux.items():
            chemin.write_text(contenu, encoding="utf-8")
        pending_path.write_text(
            (texte_pending.rstrip("\n") + "\n") if texte_pending.strip() else "", encoding="utf-8"
        )
    return rapport


# ---------------------------------------------------------------------------
# Retrait des orphelins
# ---------------------------------------------------------------------------


def orphelins(pending: dict, *, aides_dir: Path = AIDES_DIR) -> list[str]:
    """Les faits proposés qu'aucune aide du catalogue ne référence.

    37 dans le lot du 2026-09-18 : l'agent a changé d'avis et laissé le
    brouillon derrière lui. Ils ne posent de question à personne — ils
    encombrent la relecture.
    """
    from lint_aides_data import faits_references_dans

    return sorted(set(pending) - faits_references_dans(aides_dir))


def retirer_orphelins(
    *,
    aides_dir: Path = AIDES_DIR,
    pending_path: Path = FACTS_PENDING_FILE,
    facts_path: Path = FACTS_FILE,
    jour: date | None = None,
    ecrire: bool = False,
) -> Rapport:
    """Retire les orphelins. Aucune condition n'est touchée — il n'y en a aucune."""
    load_pending_facts.cache_clear()
    pending = load_pending_facts(pending_path)
    cles = orphelins(pending, aides_dir=aides_dir)
    if not cles:
        return Rapport()
    table = [Retypage(fait=c, motif="Orphelin : aucune aide ne le référence.") for c in cles]
    return appliquer(
        table,
        aides_dir=aides_dir,
        pending_path=pending_path,
        facts_path=facts_path,
        jour=jour,
        ecrire=ecrire,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="retyper_faits.py",
        description="Retype les conditions qui citent un fait, puis retire le fait.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("table", type=Path, nargs="?", help="table de retypage YAML")
    ap.add_argument(
        "--s-engage",
        action="store_true",
        help="table implicite : tous les `s_engage_*` de facts_pending.yaml "
        "(retirer à la main ceux qui portent une contrainte durable)",
    )
    ap.add_argument(
        "--retirer-orphelins",
        action="store_true",
        help="table implicite : les faits proposés qu'aucune aide ne référence",
    )
    ap.add_argument("--dry-run", action="store_true", help="afficher sans rien écrire")
    ap.add_argument(
        "--sans-lint", action="store_true", help="ne pas rejouer le lint après écriture"
    )
    args = ap.parse_args(argv)

    modes = sum(bool(x) for x in (args.table, args.s_engage, args.retirer_orphelins))
    if modes != 1:
        ap.error("donner une table, ou --s-engage, ou --retirer-orphelins — un seul des trois")

    if args.retirer_orphelins:
        rapport = retirer_orphelins(ecrire=not args.dry_run)
        print(f"{len(rapport.retires)} orphelin(s)")
        print(rapport.texte())
    else:
        if args.s_engage:
            load_pending_facts.cache_clear()
            retypages = table_des_engagements(load_pending_facts())
            erreurs: list[str] = []
            print(f"{len(retypages)} fait(s) `{PREFIXE_ENGAGEMENT}*` dans facts_pending.yaml")
            print("  ⚠ Relire la liste : un engagement qui porte une contrainte DURABLE")
            print("    (conservation 15 ans, ouverture au public) mérite de rester un fait,")
            print("    de préférence en integer `duree_*_ans`. Le script ne les distingue pas.")
        else:
            retypages, erreurs = charger_table(args.table)
        if erreurs:
            for e in erreurs:
                print(f"ERREUR : {e}")
            return 2
        rapport = appliquer(retypages, ecrire=not args.dry_run)
        print(rapport.texte())

    if not rapport.ok:
        print("\nRien n'a été écrit.")
        return 1
    if args.dry_run:
        print("\n--dry-run : rien n'a été écrit.")
        return 0

    if args.sans_lint:
        return 0
    print("\nLint du catalogue après retypage :")
    resultat = lint()
    for e in resultat.erreurs[:20]:
        print(f"  {e}")
    print("  ✓ lint OK" if resultat.ok else f"  ✗ {len(resultat.erreurs)} erreur(s)")
    return 0 if resultat.ok else 1


if __name__ == "__main__":
    sys.exit(main())
