"""Appliquer le test du destinataire à des aides DÉJÀ ingérées.

Le test du §6.1 du skill (« à qui la source s'adresse-t-elle, et en quelle
qualité ? ») décide désormais de ce qui entre au catalogue. Il reste à
l'appliquer à ce qui y est déjà : 643 aides écrites dans la nuit du 2026-09-18
sans aucun point de contrôle entre le tri LLM et l'écriture des YAML, plus les
436 antérieures, dont les ~90 aides économiques du lot Grand Est.

Ce module ne renomme RIEN et n'écrit aucun YAML d'aide. Il produit une FICHE de
tri, triée par catégorie d'écart puis par famille, que l'utilisateur valide
avant tout renommage. C'est le seul point de contrôle humain du chantier, et il
serait sans objet si le script décidait lui-même.

    uv run python scripts/prospecter.py requalifier --lot data/reviews/…/slugs.txt
    uv run python scripts/prospecter.py requalifier --territoire grand-est
    uv run python scripts/prospecter.py requalifier --catalogue

La lecture se fait sur le YAML de l'aide (titre, description, bénéficiaires lus
à la prospection, gate porteur, familles) et sur sa fiche de review — PAS sur la
page. Deux raisons : la page a pu changer ou disparaître, et surtout c'est le
contenu ingéré qu'on juge. Une aide dont le YAML ne dit pas à qui elle s'adresse
est un problème en soi, et la fiche le dira.

Le comptage lexical ne suffit pas, et c'est mesuré : le champ « bénéficiaires »
lu à la prospection classe 67 aides comme destinées à des tiers seulement, 184
mixtes, 173 sans bénéficiaires lus, et 203 « propriétaire » — dont des chorales
et des fanfares, parce que le mot « association » ne dit pas la qualité. D'où un
appel de modèle par aide, avec la même consigne que la lecture.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from threading import Lock

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import providall
from pipeline.etat import (
    FILE_ATTENTE,
    CategorieEcart,
    Destinataire,
    Objet,
    charger,
    mettre_a_jour,
)
from pipeline.etat import indetermine as issue_indeterminee
from pipeline.etat import retenir as test_du_destinataire
from pipeline.llm import Compteur

from aides_schema import AIDES_DIR, FAIT_PORTEUR, Aide

from .lecture import CONSIGNE_DESTINATAIRE
from .tri import SKILL_PROSPECTION, doctrine

#: Au-delà, la fiche de review pèse plus lourd que l'aide elle-même dans le
#: prompt, et ce qu'on juge est le dispositif, pas la qualité de sa relecture.
MAX_CAR_REVIEW = 4_000
#: Une description de règlement complète tient largement dedans.
MAX_CAR_DESCRIPTION = 2_000


class Requalification(BaseModel):
    """Le verdict du modèle sur une aide déjà ingérée."""

    destinataire: Destinataire = Field(
        default="indetermine", description="À qui la source s'adresse (cf. consigne)"
    )
    objet: Objet = Field(default="indetermine", description="Sur quoi porte la dépense")
    categorie_ecart: CategorieEcart | None = Field(
        default=None, description="Quand le destinataire n'est pas le bon : laquelle des sept"
    )
    motif: str = Field(
        default="",
        description=(
            "Une phrase, OBLIGATOIRE : ce qui fonde le verdict. Une écartée sans motif "
            "est inrelisable, donc irrecevable."
        ),
    )

    @property
    def retenir(self) -> bool:
        return (
            test_du_destinataire(self.destinataire, self.objet)
            and self.categorie_ecart != "non_dispositif"
        )

    @property
    def indeterminee(self) -> bool:
        return issue_indeterminee(self.destinataire, self.objet, self.categorie_ecart)


@dataclass
class Verdict:
    """Une aide jugée : son slug, ce que le modèle en dit, et ce qui a raté."""

    slug: str
    aide: Aide
    resultat: Requalification | None = None
    erreur: str | None = None

    @property
    def sort(self) -> str:
        """`retenir`, `ecarter`, `indetermine` ou `erreur`. L'axe de la fiche."""
        if self.resultat is None:
            return "erreur"
        if self.resultat.retenir:
            return "retenir"
        return "indetermine" if self.resultat.indeterminee else "ecarter"


@dataclass
class Rapport:
    verdicts: list[Verdict] = field(default_factory=list)
    cout: str = ""

    def par_sort(self, sort: str) -> list[Verdict]:
        return [v for v in self.verdicts if v.sort == sort]


CONSIGNE_REQUALIFICATION = """\
# Ce qu'on te demande

Cette aide est DÉJÀ au catalogue. On la relit pour savoir si elle aurait dû y
entrer, au regard du test du destinataire ci-dessous — un test qui n'existait
pas quand elle a été ingérée.

Tu ne vois pas la page d'origine, et c'est voulu : ce qu'on juge est le contenu
INGÉRÉ. Une fiche qui ne permet pas de dire à qui l'aide s'adresse est un
problème en soi — réponds alors `indetermine`, un humain tranchera.

Ne juge pas la QUALITÉ de l'extraction (conditions mal typées, quotes
manquantes, description pauvre) : ce n'est pas la question posée ici, et une
aide mal ingérée mais bien destinée se corrige, alors qu'une aide bien ingérée
mais mal destinée se retire.
"""


def _rendre_aide(aide: Aide, review: str | None) -> str:
    """Ce que le modèle voit d'une aide déjà ingérée."""
    gate = next(
        (
            c
            for c in aide.conditions
            if c.effect == "gate" and c.fact == FAIT_PORTEUR and c.predicate
        ),
        None,
    )
    beneficiaires = (
        f"{gate.text}\n  prédicat : {gate.predicate.root}" if gate else "(aucun gate porteur)"
    )
    morceaux = [
        f"## {aide.nom}",
        f"- organisme : {aide.organisme} ({aide.categorie})",
        f"- familles : {', '.join(aide.familles) or '(aucune)'}",
        f"- raison : {', '.join(aide.raison) or '(aucune)'}",
        f"- type : {aide.type}",
        "",
        "### Description",
        " ".join((aide.description or "").split())[:MAX_CAR_DESCRIPTION],
        "",
        "### Qui peut déposer, d'après la fiche",
        beneficiaires,
    ]
    if aide.applies_if:
        morceaux += ["", f"### Périmètre déclaré\n{aide.applies_if.fact}"]
    if review:
        morceaux += ["", "### Fiche de review de l'ingestion", review[:MAX_CAR_REVIEW]]
    return "\n".join(morceaux)


def consigne(skill_path: Path = SKILL_PROSPECTION) -> str:
    """La MÊME doctrine que la lecture : le test ne change pas parce qu'on relit."""
    return "\n\n".join(
        [
            "Tu relis une aide du catalogue Monumia, qui recense ce qu'un propriétaire de "
            "monument peut mobiliser pour faire vivre son bien.",
            doctrine(skill_path),
            CONSIGNE_REQUALIFICATION,
            CONSIGNE_DESTINATAIRE,
        ]
    )


def requalifier_une(
    slug: str,
    aide: Aide,
    client: providall.Client,
    *,
    review: str | None = None,
    compteur: Compteur | None = None,
    skill_path: Path = SKILL_PROSPECTION,
) -> Verdict:
    """Juge UNE aide. Ne lève jamais : une panne devient un verdict en erreur."""
    essai = client.try_complete_json(
        Requalification, _rendre_aide(aide, review), system=consigne(skill_path)
    )
    if compteur is not None:
        compteur.ajouter(essai.response, "requalification")
    if essai.data is None:
        return Verdict(slug, aide, erreur=f"requalification impossible : {essai.response.error}")
    return Verdict(slug, aide, resultat=essai.data)


#: Requalifications simultanées. Chaque aide est un appel INDÉPENDANT — aucun
#: fichier partagé, aucun ordre à respecter, et le `Compteur` est sûr entre
#: threads. Séquentiellement, 950 aides à quelques secondes l'appel font plus
#: d'une heure ; c'est le genre de run qu'on n'ose plus relancer, et un run
#: qu'on n'ose plus relancer est un point de contrôle qu'on saute.
#:
#: Huit et pas trente : au-delà, c'est le fournisseur qui limite, et les
#: `RateLimitError` coûtent plus de temps qu'elles n'en font gagner. Même
#: ordre de grandeur que le `--parallele` de l'ingestion (6 par défaut), dont
#: chaque tâche est pourtant bien plus lourde.
PARALLELE_DEFAUT = 8


def requalifier(
    aides: dict[str, Aide],
    client: providall.Client,
    *,
    reviews: dict[str, str] | None = None,
    compteur: Compteur | None = None,
    skill_path: Path = SKILL_PROSPECTION,
    progression: Callable[[int, int, Verdict], None] | None = None,
    parallele: int = PARALLELE_DEFAUT,
) -> Rapport:
    """Juge un lot d'aides. Le rapport est TRIÉ par slug, quel que soit l'ordre d'arrivée.

    Le tri du résultat n'est pas cosmétique : la fiche produite se relit et se
    compare d'un passage à l'autre, et un ordre qui dépend de l'ordonnancement
    des threads rendrait tout diff illisible.

    `parallele=1` rend l'exécution séquentielle — c'est ce que font les tests,
    qui comptent sur l'ordre des réponses du faux fournisseur.
    """
    rapport = Rapport()
    items = sorted(aides.items())
    total = len(items)

    def juger(item: tuple[str, Aide]) -> Verdict:
        slug, aide = item
        return requalifier_une(
            slug,
            aide,
            client,
            review=(reviews or {}).get(slug),
            compteur=compteur,
            skill_path=skill_path,
        )

    if parallele <= 1:
        resultats = [juger(item) for item in items]
        for i, verdict in enumerate(resultats, 1):
            if progression is not None:
                progression(i, total, verdict)
        rapport.verdicts = resultats
        return rapport

    faits = 0
    verrou = Lock()
    with ThreadPoolExecutor(max_workers=parallele) as pool:
        for verdict in pool.map(juger, items):
            rapport.verdicts.append(verdict)
            if progression is not None:
                with verrou:
                    faits += 1
                    progression(faits, total, verdict)
    # `pool.map` préserve déjà l'ordre d'entrée ; le tri le dit explicitement,
    # pour que la propriété ne dépende pas d'un détail d'implémentation.
    rapport.verdicts.sort(key=lambda v: v.slug)
    return rapport


# ---------------------------------------------------------------------------
# La fiche
# ---------------------------------------------------------------------------


#: Le modèle laisse parfois `motif` vide. Le verdict reste valide, mais une
#: écartée sans motif ne se relit pas : on le dit dans la fiche plutôt que de
#: rendre une ligne qui a l'air tronquée.
SANS_MOTIF = "_(motif non rendu par le modèle — à relire sur pièce)_"


def _motif(resultat: Requalification) -> str:
    """Le motif reployé sur une ligne, ou la mention qui signale son absence."""
    return " ".join(resultat.motif.split()) or SANS_MOTIF


def rendre_fiche(rapport: Rapport, *, nom: str, jour: date) -> str:
    """La fiche de tri, triée par catégorie d'écart puis par famille.

    Elle est faite pour être VALIDÉE ligne par ligne : c'est le seul point de
    contrôle humain du chantier, et les renommages viennent après. Le tri par
    catégorie n'est pas cosmétique — il regroupe les décisions de même nature,
    et c'est ce qui rend relisible une liste de trois cents aides.
    """
    lignes = [
        f"# Requalification — {nom} — {jour.isoformat()}",
        "",
        f"{len(rapport.verdicts)} aide(s) relue(s) au test du destinataire "
        "(SKILL prospecter, étape 3).",
        "",
        "> **Rien n'a été renommé.** Cette fiche est une PROPOSITION. Après validation :",
        "> renommer les écartées en `<slug>.yaml.echec` avec leur motif, passer leur tâche",
        "> `ignore` dans la file d'attente, puis",
        "> `retyper_faits.py --retirer-orphelins` pour les faits devenus sans emploi.",
        "> Les snapshots de `data/sources/` restent en place : preuve et réversibilité.",
        "",
        "| sort | aides |",
        "|---|---:|",
    ]
    for sort, libelle in (
        ("retenir", "Retenues"),
        ("ecarter", "À écarter"),
        ("indetermine", "À trancher à la main"),
        ("erreur", "Non jugées (panne du modèle)"),
    ):
        lignes.append(f"| {libelle} | {len(rapport.par_sort(sort))} |")

    lignes += ["", "## À écarter", ""]
    ecartees = rapport.par_sort("ecarter")
    if not ecartees:
        lignes.append("_aucune_")
    par_categorie: dict[str, list[Verdict]] = {}
    for v in ecartees:
        assert v.resultat is not None
        par_categorie.setdefault(v.resultat.categorie_ecart or "objet_hors_lieu", []).append(v)
    for categorie, lot in sorted(par_categorie.items()):
        lignes += [f"### `{categorie}` — {len(lot)} aide(s)", ""]
        for v in sorted(lot, key=lambda v: (v.aide.familles[:1], v.slug)):
            assert v.resultat is not None
            familles = ", ".join(v.aide.familles) or "—"
            lignes.append(
                f"- `{v.slug}` **{v.aide.nom}** — {familles} — destinataire "
                f"`{v.resultat.destinataire}`, objet `{v.resultat.objet}` — "
                f"{_motif(v.resultat)}"
            )
        lignes.append("")

    lignes += ["## À trancher à la main", ""]
    indeterminees = rapport.par_sort("indetermine")
    if not indeterminees:
        lignes.append("_aucune_")
    for v in sorted(indeterminees, key=lambda v: v.slug):
        assert v.resultat is not None
        lignes.append(
            f"- `{v.slug}` **{v.aide.nom}** — destinataire `{v.resultat.destinataire}`, "
            f"objet `{v.resultat.objet}` — {_motif(v.resultat)}"
        )

    lignes += ["", "## Retenues", ""]
    retenues = rapport.par_sort("retenir")
    if not retenues:
        lignes.append("_aucune_")
    for v in sorted(retenues, key=lambda v: (v.aide.familles[:1], v.slug)):
        assert v.resultat is not None
        familles = ", ".join(v.aide.familles) or "—"
        lignes.append(f"- `{v.slug}` **{v.aide.nom}** — {familles}")

    erreurs = rapport.par_sort("erreur")
    if erreurs:
        lignes += ["", "## Non jugées", ""]
        for v in sorted(erreurs, key=lambda v: v.slug):
            lignes.append(f"- `{v.slug}` — {v.erreur}")

    lignes += ["", "## Slugs à écarter", ""]
    if ecartees:
        for v in sorted(ecartees, key=lambda v: v.slug):
            assert v.resultat is not None
            lignes.append(f"{v.slug}  {v.resultat.categorie_ecart or 'objet_hors_lieu'}")
    else:
        lignes.append("_aucun_")

    if rapport.cout:
        lignes += ["", "## Notes techniques", "", f"- coût du passage : {rapport.cout}"]
    return "\n".join(lignes) + "\n"


def parser_ecarts(markdown: str) -> list[tuple[str, str]]:
    """Relit le bloc « Slugs à écarter » d'une fiche, éditée à la main ou non.

    Même idiome que `fiche.parser_slugs` : c'est ce bloc que l'humain corrige
    (retirer une ligne = garder l'aide), et c'est lui qui pilotera les
    renommages.
    """
    if "## Slugs à écarter" not in markdown:
        return []
    bloc = markdown.split("## Slugs à écarter", 1)[1].split("\n## ", 1)[0]
    sorties: list[tuple[str, str]] = []
    for ligne in bloc.splitlines():
        morceaux = ligne.split()
        if len(morceaux) == 2 and not ligne.startswith(("#", "_", "-", "|")):
            sorties.append((morceaux[0], morceaux[1]))
    return sorties


@dataclass
class RapportApplication:
    """Ce qu'un passage de `appliquer` a fait, ou refusé de faire."""

    renommes: list[str] = field(default_factory=list)
    erreurs: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.erreurs

    def texte(self) -> str:
        lignes = [f"{len(self.renommes)} aide(s) renommée(s) en `.yaml.echec`."]
        for e in self.erreurs:
            lignes.append(f"ERREUR : {e}")
        return "\n".join(lignes)


def appliquer(
    ecarts: Sequence[tuple[str, str]],
    *,
    aides_dir: Path = AIDES_DIR,
    etat_path: Path = FILE_ATTENTE,
    ecrire: bool = False,
) -> RapportApplication:
    """Renomme les écartées en `.yaml.echec` et passe leur tâche `ignore`.

    Même discipline que `dedoublonner_aides.appliquer` : TOUT est vérifié avant
    la première écriture. Un lot à moitié appliqué laisserait un catalogue dont
    on ne sait plus quelle moitié a été relue.

    Rien n'est supprimé : `.yaml.echec` sort du glob `*.yaml` (invisible au
    lint, au moteur et au loader) et un simple renommage inverse le geste. Les
    snapshots de `data/sources/` restent en place.
    """
    rapport = RapportApplication()
    vus: set[str] = set()
    for slug, _ in ecarts:
        if slug in vus:
            rapport.erreurs.append(f"« {slug} » écarté deux fois par la fiche")
        vus.add(slug)
        if not (aides_dir / f"{slug}.yaml").exists():
            rapport.erreurs.append(f"aide introuvable : {slug}.yaml — déjà écartée ?")
    if not rapport.ok or not ecrire:
        return rapport

    # Toutes les aides du catalogue ne viennent pas de la prospection : les
    # antérieures n'ont pas de tâche, et `mettre_a_jour` lèverait sur leur slug.
    en_file = charger(etat_path) if etat_path.exists() else {}
    for slug, categorie in ecarts:
        (aides_dir / f"{slug}.yaml").rename(aides_dir / f"{slug}.yaml.echec")
        rapport.renommes.append(slug)
        if slug not in en_file:
            continue
        try:
            mettre_a_jour(
                etat_path,
                slug,
                statut="ignore",
                motif_ignore=f"test du destinataire : {categorie}",
            )
        except Exception as exc:  # noqa: BLE001 — la file est un fichier partagé
            rapport.erreurs.append(f"{slug} : statut non consigné ({exc})")
    return rapport


def slugs_du_fichier(chemin: Path) -> list[str]:
    """Une liste de slugs, un par ligne, `#` en commentaire."""
    return [
        ligne.split()[0]
        for ligne in chemin.read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.lstrip().startswith("#")
    ]


def _porte_le_slug(stem: str, slug: str) -> bool:
    """Le nom de fichier désigne-t-il ce slug, sur des frontières de segment ?

    `slug in stem` ne suffit pas : les noms ne sont pas normalisés
    (`<date>-ingest-<territoire>-<slug>.md`, `<date>-<slug>.md`, `<slug>.md`,
    `<slug>-deepseek-review.md`), et un tiret perdu rapproche n'importe quoi.
    """
    return (
        stem == slug
        or stem.endswith(f"-{slug}")
        or stem.startswith(f"{slug}-")
        or f"-{slug}-" in stem
    )


def reviews_de(
    slugs: Sequence[str],
    reviews_dir: Path,
    *,
    univers: Sequence[str] | None = None,
) -> dict[str, str]:
    """Les fiches de review des aides, quand elles existent. La plus récente gagne.

    `univers` est l'ensemble des slugs connus — tout le catalogue, pas seulement
    les aides demandées. Un fichier va au slug le PLUS LONG qui le désigne, et
    c'est ce qui manquait : `region-normandie` est un préfixe de
    `normandie-region-normandie-droits-culturels`, il a reçu la fiche de cette
    aide-là, et le modèle a requalifié quelqu'un d'autre. L'aide en question est
    la subvention MH de la Région Normandie à 20-30 %, écartée du catalogue sur
    un motif qui parlait de droits culturels. Deux autres slugs courts
    (`region-occitanie`, `35-faat`) étaient dans le même cas.

    Sans `univers`, la comparaison se fait entre les seuls slugs demandés — un
    lot d'une aide reprendrait donc le fichier de sa voisine plus longue.
    """
    trouvees: dict[str, str] = {}
    if not reviews_dir.is_dir():
        return trouvees
    connus = sorted(set(univers if univers is not None else slugs), key=len, reverse=True)
    demandes = set(slugs)
    # Du plus récent au plus ancien : le premier fichier attribué à un slug est
    # le sien, les suivants sont des passages antérieurs.
    for chemin in sorted(reviews_dir.glob("*.md"), reverse=True):
        proprietaire = next((s for s in connus if _porte_le_slug(chemin.stem, s)), None)
        if proprietaire is None or proprietaire not in demandes:
            continue
        trouvees.setdefault(proprietaire, chemin.read_text(encoding="utf-8", errors="replace"))
    return trouvees


__all__ = [
    "CONSIGNE_REQUALIFICATION",
    "PARALLELE_DEFAUT",
    "MAX_CAR_REVIEW",
    "Rapport",
    "RapportApplication",
    "Requalification",
    "Verdict",
    "appliquer",
    "consigne",
    "parser_ecarts",
    "rendre_fiche",
    "requalifier",
    "requalifier_une",
    "reviews_de",
    "slugs_du_fichier",
]
