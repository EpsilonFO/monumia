"""La fiche de prospection — le livrable, et le point de contrôle humain.

Format repris de `data/reviews/2026-09-04-prospection-hauts-de-france.md`, écrit
à la main : en-tête, tableau des retenues, écartées avec leur motif, bloc de
slugs proposés, et — ajout du pipeline — des notes techniques qui disent ce qui
a résisté (page en erreur, SPA, PDF illisible, coût du passage).

Le bloc « Slugs proposés » se relit à la machine (`slug<espaces>URL`) : c'est
lui qui alimente la file d'attente, et c'est aussi lui que l'humain édite quand
il veut renommer une aide avant ingestion.

Rien de ce que produit ce module n'est ingéré tel quel : la fiche pose les
candidats en `a_valider`, et c'est `prospecter.py valider` qui les fait passer.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.etat import Tache

from aides_schema import Aide

from .collecte import Collecte
from .lecture import Lecture, slug_final
from .territoires import Territoire
from .tri import MOTIF_SANS_TITRE, TriCandidat

# Le bloc de slugs est fait pour être relu : une ligne = un slug, des espaces,
# une URL. Éditable à la main sans rien casser.
LIGNE_SLUG_RE = re.compile(r"^(\S+)\s+(https?://\S+)$", re.M)


def _cellule(valeur: str | None) -> str:
    """Une cellule de tableau markdown : les barres verticales cassent la ligne."""
    if not valeur:
        return "—"
    return " ".join(str(valeur).split()).replace("|", "/")


def parser_slugs(markdown: str) -> list[tuple[str, str]]:
    """Relit le bloc « Slugs proposés » d'une fiche, éditée à la main ou non."""
    if "## Slugs proposés" not in markdown:
        return []
    bloc = markdown.split("## Slugs proposés", 1)[1]
    bloc = bloc.split("\n## ", 1)[0]
    return [(m.group(1), m.group(2)) for m in LIGNE_SLUG_RE.finditer(bloc)]


def rendre_fiche(
    cle: str,
    territoire: Territoire,
    lectures: list[Lecture],
    tries: list[TriCandidat],
    collecte: Collecte,
    existantes: dict[str, Aide],
    slugs: dict[str, str],
    *,
    jour: date,
    cout: str = "",
) -> str:
    """La fiche markdown complète. `slugs` : URL → slug définitif."""
    retenues = [le for le in lectures if le.retenue]
    ecartees = [t for t in tries if t.decision == "ecarter"]
    lues_non_retenues = [le for le in lectures if le.fiche is not None and not le.fiche.retenir]
    en_erreur = [le for le in lectures if le.erreur]

    lignes = [
        f"# Prospection — {territoire.nom} — {jour.isoformat()}",
        "",
        f"Guide balayé : {', '.join(territoire.guides) or '(aucun)'}",
        f"Stratégie : {territoire.strategie.type} (recette `{territoire.statut}`)",
        f"Déjà dans le corpus : {len(existantes)} aide(s)"
        + (f" — {', '.join(f'`{s}`' for s in sorted(existantes))}" if existantes else ""),
        "",
        "> Fiche produite par `scripts/prospecter.py`. Elle ne crée aucun YAML : elle",
        "> pose des candidates en `a_valider` dans `data/prospection/file-attente.yaml`.",
        "> Relire, corriger les slugs si besoin, puis `prospecter.py valider`.",
        "",
        "## Candidates retenues",
        "",
        "| # | Dispositif | URL | Famille | Montant / taux | Bénéficiaires | Note |",
        "|---|---|---|---|---|---|---|",
    ]
    if not retenues:
        lignes.append("| — | _aucune_ | | | | | |")
    for i, lecture in enumerate(retenues, start=1):
        f = lecture.fiche
        assert f is not None
        pdf = (
            f" (+ {len(f.urls_pdf)} document(s) : " + ", ".join(f.urls_pdf) + ")"
            if f.urls_pdf
            else ""
        )
        note = _cellule(f.note)
        if f.doublon_probable:
            note = f"**doublon probable de `{f.doublon_probable}`** — {note}"
        if f.source_unique_vulgarisation:
            note = f"**page de vulgarisation, règlement à trouver** — {note}"
        lignes.append(
            f"| {i} | {_cellule(f.titre)} | {lecture.candidat.url}{pdf} | {f.famille} | "
            f"{_cellule(f.montant_taux)} | {_cellule(f.beneficiaires)} | {note} |"
        )

    lignes += ["", "## Écartées (et pourquoi)", ""]
    if not ecartees and not lues_non_retenues:
        lignes.append("- _aucune_")
    for lecture in lues_non_retenues:
        f = lecture.fiche
        assert f is not None
        lignes.append(f"- **{_cellule(f.titre)}** — {lecture.candidat.url} — {_cellule(f.note)}")
    for tri in ecartees:
        lignes.append(f"- {tri.url} — {_cellule(tri.motif)}")

    lignes += ["", "## Slugs proposés", ""]
    if retenues:
        largeur = max(len(slugs.get(le.candidat.url, "")) for le in retenues) + 2
        for lecture in retenues:
            slug = slugs.get(lecture.candidat.url, "")
            lignes.append(f"{slug.ljust(largeur)}{lecture.candidat.url}")
    else:
        lignes.append("_aucun_")

    lignes += ["", "## Notes techniques", ""]
    for note in collecte.notes:
        lignes.append(f"- {note}")
    for url, slug in collecte.doublons:
        lignes.append(f"- déjà au catalogue : {url} → `{slug}`")
    for url, slug, statut in collecte.en_file:
        lignes.append(f"- déjà en file d'attente (`{statut}`) : {url} → `{slug}`")
    for lecture in en_erreur:
        lignes.append(f"- non lue : {lecture.candidat.url} — {lecture.erreur}")
    douteuses = [t for t in tries if t.decision == "douteux"]
    if douteuses:
        lignes.append(
            f"- {len(douteuses)} candidate(s) douteuse(s) au tri, ouvertes et tranchées "
            "à la lecture"
        )
    requalifiees = [t for t in tries if t.motif.startswith(MOTIF_SANS_TITRE)]
    if requalifiees:
        lignes.append(
            f"- {len(requalifiees)} élimination(s) prise(s) sans titre ni contexte, "
            "requalifiée(s) en douteuses et ouvertes à la lecture"
        )
    if cout:
        lignes.append(f"- coût du passage : {cout}")
    return "\n".join(lignes) + "\n"


def taches(
    cle: str,
    territoire: Territoire,
    lectures: list[Lecture],
    slugs: dict[str, str],
    chemin_fiche: str,
    *,
    jour: date,
) -> dict[str, Tache]:
    """Les candidates retenues, prêtes à entrer en `a_valider` dans la file."""
    sortie: dict[str, Tache] = {}
    for lecture in lectures:
        if not lecture.retenue:
            continue
        f = lecture.fiche
        assert f is not None
        slug = slugs.get(lecture.candidat.url)
        if not slug:
            continue
        sortie[slug] = Tache(
            titre=f.titre or lecture.candidat.titre or slug,
            url=lecture.candidat.url,
            urls_pdf=list(f.urls_pdf),
            territoire=cle,
            famille=f.famille,
            beneficiaires=f.beneficiaires,
            priorite=f.priorite if f.priorite in ("haute", "normale", "basse") else "normale",
            statut="a_valider",
            ajoute_le=jour,
            fiche=chemin_fiche,
        )
    return sortie


def attribuer_slugs(
    territoire: Territoire, lectures: list[Lecture], occupes: set[str]
) -> dict[str, str]:
    """URL → slug définitif, uniques entre eux et contre le catalogue."""
    pris = set(occupes)
    attribue: dict[str, str] = {}
    for lecture in lectures:
        if not lecture.retenue:
            continue
        f = lecture.fiche
        assert f is not None
        slug = slug_final(territoire, f.slug_propose, f.titre or lecture.candidat.titre, pris)
        pris.add(slug)
        attribue[lecture.candidat.url] = slug
    return attribue


__all__ = ["LIGNE_SLUG_RE", "attribuer_slugs", "parser_slugs", "rendre_fiche", "taches"]
