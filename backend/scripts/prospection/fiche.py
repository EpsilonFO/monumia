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
    indeterminees = [le for le in lectures if le.indeterminee]
    hors_perimetre = [le for le in lectures if le.ecartee]
    ecartees = [t for t in tries if t.decision == "ecarter"]
    en_erreur = [le for le in lectures if le.erreur]

    lignes = [
        f"# Prospection — {territoire.nom} — {jour.isoformat()}",
        "",
        f"Guide balayé : {', '.join(territoire.guides) or '(aucun)'}",
        f"Stratégie : {territoire.strategie.type} (recette `{territoire.statut}`)",
        f"Déjà dans le corpus : {len(existantes)} aide(s)"
        + (f" — {', '.join(f'`{s}`' for s in sorted(existantes))}" if existantes else ""),
        "",
    ]
    if collecte.plafonnee:
        lignes += [
            f"> ⚠ **Balayage plafonné** à {territoire.strategie.max_candidats} candidates :",
            "> ce qui suit n'est pas tout ce que le guide contient. La recette est à",
            "> préciser dans `territoires.yaml` avant de conclure quoi que ce soit du",
            "> volume.",
            "",
        ]
    lignes += [
        "> Fiche produite par `scripts/prospecter.py`. Elle ne crée aucun YAML : elle",
        "> pose des candidates en `a_valider` dans `data/prospection/file-attente.yaml`.",
        "> Relire, corriger les slugs si besoin, puis `prospecter.py valider`.",
        "",
        "## Candidates retenues",
        "",
        "| # | Dispositif | URL | Famille | Destinataire | Objet | Montant / taux | "
        "Bénéficiaires | Note |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    if not retenues:
        lignes.append("| — | _aucune_ | | | | | | | |")
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
            f"{f.destinataire} | {f.objet} | {_cellule(f.montant_taux)} | "
            f"{_cellule(f.beneficiaires)} | {note} |"
        )

    lignes += [
        "",
        "## À trancher à la main (destinataire ou objet indéterminé)",
        "",
        "Ni retenues ni écartées : la page ne permettait pas de dire à qui l'aide",
        "s'adresse. Elles restent `a_valider` dans la file et `promouvables` les",
        "retient — les valider revient à trancher.",
        "",
    ]
    if not indeterminees:
        lignes.append("- _aucune_")
    for lecture in indeterminees:
        f = lecture.fiche
        assert f is not None
        slug = slugs.get(lecture.candidat.url, "")
        lignes.append(
            f"- `{slug}` **{_cellule(f.titre)}** — {lecture.candidat.url} — "
            f"destinataire `{f.destinataire}`, objet `{f.objet}` — {_cellule(f.note)}"
        )

    lignes += [
        "",
        "## Écartées par le test du destinataire",
        "",
        "Entrées en `ignore` dans la file avec leur motif : elles ne reviendront pas",
        "au balayage suivant. Rouvrir l'une d'elles se fait à la main",
        "(`prospecter.py valider <slug>`).",
        "",
    ]
    if not hors_perimetre:
        lignes.append("- _aucune_")
    for lecture in sorted(
        hors_perimetre,
        key=lambda le: (le.fiche.categorie_ecart or "", le.fiche.titre),  # type: ignore[union-attr]
    ):
        f = lecture.fiche
        assert f is not None
        lignes.append(
            f"- [{f.categorie_ecart or 'objet_hors_lieu'}] **{_cellule(f.titre)}** — "
            f"{lecture.candidat.url} — destinataire `{f.destinataire}`, objet "
            f"`{f.objet}` — {_cellule(f.note)}"
        )

    lignes += ["", "## Écartées au tri, sans ouvrir la page", ""]
    if not ecartees:
        lignes.append("- _aucune_")
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
    """Toutes les candidates lues entrent dans la file — leur statut les distingue.

    Trois sorts, et il est important que les trois soient TRACÉS :

    - retenue par le test du destinataire → `a_valider`, comme avant ;
    - indéterminée → `a_valider` aussi, mais `promouvables` la retiendra : elle
      attend un arbitrage humain, pas une ingestion ;
    - écartée par le test → `ignore` + `motif_ignore`, et elle n'en bougera
      plus. C'est ce qui l'empêche de revenir au balayage suivant : jusqu'ici
      une candidate non retenue n'entrait simplement pas dans la file, donc
      `dedoublonner` ne la connaissait pas et la re-proposait à chaque passage.

    Les documents vus à la collecte rejoignent `urls_pdf` : la page ouverte par
    l'étage 1 a pu montrer un règlement que la lecture, qui ne connaissait que
    `.pdf`, ne savait pas nommer.
    """
    sortie: dict[str, Tache] = {}
    for lecture in lectures:
        f = lecture.fiche
        if f is None:
            continue
        slug = slugs.get(lecture.candidat.url)
        if not slug:
            continue
        documents = list(dict.fromkeys([*f.urls_pdf, *lecture.candidat.documents]))
        ecartee = lecture.ecartee
        motif = _motif_ecart(lecture)
        sortie[slug] = Tache(
            titre=f.titre or lecture.candidat.titre or slug,
            url=lecture.candidat.url,
            urls_pdf=documents,
            territoire=cle,
            departements=territoire.codes_departements(cle),
            famille=f.famille,
            beneficiaires=f.beneficiaires,
            destinataire=f.destinataire,
            objet=f.objet,
            categorie_ecart=f.categorie_ecart,
            note=f.note or None,
            doublon_probable=f.doublon_probable,
            source_unique_vulgarisation=f.source_unique_vulgarisation,
            priorite=f.priorite if f.priorite in ("haute", "normale", "basse") else "normale",
            statut="ignore" if ecartee else "a_valider",
            motif_ignore=motif,
            ajoute_le=jour,
            fiche=chemin_fiche,
        )
    return sortie


def _motif_ecart(lecture: Lecture) -> str | None:
    """Le `motif_ignore` d'une lecture écartée par le test, None sinon."""
    f = lecture.fiche
    if f is None or not lecture.ecartee:
        return None
    categorie = f.categorie_ecart or "objet_hors_lieu"
    return f"hors périmètre : {categorie} (destinataire {f.destinataire}, objet {f.objet})"


def requalifier(tache: Tache, lecture: Lecture) -> Tache | None:
    """Une tâche existante, repassée par la lecture : le verdict remplace l'ancien.

    Sert aux échecs de panne lus avant le test du destinataire
    (`pipeline.etat.echecs_a_relire`). Mêmes trois sorts qu'à la prospection :
    écartée → `ignore` avec son motif, retenue ou indéterminée → `a_valider`, où
    `promouvables` fait le tri. Le slug, la fiche d'origine et l'historique
    d'ingestion sont gardés. Une lecture en erreur rend None : la tâche reste
    en `echec` et repassera à la relecture suivante.
    """
    f = lecture.fiche
    if f is None:
        return None
    motif = _motif_ecart(lecture)
    return tache.model_copy(
        update={
            "urls_pdf": list(
                dict.fromkeys([*tache.urls_pdf, *f.urls_pdf, *lecture.candidat.documents])
            ),
            "famille": f.famille,
            "beneficiaires": f.beneficiaires or tache.beneficiaires,
            "destinataire": f.destinataire,
            "objet": f.objet,
            "categorie_ecart": f.categorie_ecart,
            "note": f.note or tache.note,
            "doublon_probable": f.doublon_probable,
            "source_unique_vulgarisation": f.source_unique_vulgarisation,
            "statut": "ignore" if motif else "a_valider",
            "motif_ignore": motif,
        }
    )


def attribuer_slugs(
    territoire: Territoire, lectures: list[Lecture], occupes: set[str]
) -> dict[str, str]:
    """URL → slug définitif, uniques entre eux et contre le catalogue.

    TOUTES les lectures abouties en reçoivent un, écartées comprises : leur
    slug est la clé sous laquelle la file les mémorise en `ignore`, et sans lui
    elles reviendraient à chaque balayage. Les retenues passent EN PREMIER,
    pour qu'une écartée au titre voisin ne leur vole pas le slug propre et ne
    les pousse pas en `-2`.
    """
    pris = set(occupes)
    attribue: dict[str, str] = {}
    abouties = [le for le in lectures if le.fiche is not None]
    for lecture in sorted(abouties, key=lambda le: not le.retenue):
        f = lecture.fiche
        assert f is not None
        slug = slug_final(territoire, f.slug_propose, f.titre or lecture.candidat.titre, pris)
        pris.add(slug)
        attribue[lecture.candidat.url] = slug
    return attribue


__all__ = [
    "LIGNE_SLUG_RE",
    "attribuer_slugs",
    "parser_slugs",
    "rendre_fiche",
    "requalifier",
    "taches",
]
