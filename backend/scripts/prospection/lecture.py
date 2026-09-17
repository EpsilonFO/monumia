"""Étage 3 : ouvrir les fiches retenues et les qualifier.

C'est ici que la fiche de prospection gagne ses colonnes — montant, taux,
bénéficiaires, note — et c'est le seul étage qui lit vraiment les pages. La
règle qui gouverne tout le reste : **rien n'est inventé**. Un montant absent de
la page reste `None` ; il vaut mieux une colonne vide qu'un chiffre plausible
que personne ne vérifiera avant l'ingestion.

Le slug est proposé ici et pas ailleurs, parce que c'est le seul moment où l'on
connaît à la fois le titre du dispositif, le préfixe du territoire et les slugs
déjà pris.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import providall
from pipeline.llm import Compteur
from pipeline.web import Fetcheur

from .collecte import Candidat, liens
from .territoires import Territoire
from .tri import SKILL_PROSPECTION, Famille, doctrine, familles_rendues

MAX_CAR_PAGE = 25_000
MAX_LIENS_DOCUMENTS = 25
MAX_CAR_NOTE = 600

CONSIGNE_EXTRACTION = """\
# Règles d'extraction

Règle absolue : **n'invente rien**. Un montant, un taux, une liste de bénéficiaires
qui ne figurent pas sur la page restent vides. Une colonne vide dans la fiche de
prospection est un fait ; un chiffre plausible est un piège que personne ne
rattrapera avant l'ingestion.

`urls_pdf` : uniquement des liens présents dans la liste fournie (règlement,
cadre d'intervention, formulaire). N'en fabrique aucun.
"""


@lru_cache(maxsize=4)
def consigne(skill_path: Path = SKILL_PROSPECTION) -> str:
    """Doctrine du skill (la même que le tri) + règles d'extraction + familles.

    La lecture portait jusqu'au 2026-09-11 sa propre doctrine, écrite en dur et
    plus étroite que celle du tri : une aide que le tri laissait passer pouvait
    se faire recaler ici sur un critère que personne n'avait relu. Une seule
    source, et c'est le skill.

    Mémoïsé : le prompt système est le même pour toutes les pages d'un passage,
    et relire le skill par fiche ne servirait qu'à le relire 250 fois.
    """
    return "\n\n".join(
        [
            "Tu qualifies UNE page de dispositif d'aide pour le catalogue Monumia, qui "
            "recense ce qu'un propriétaire de monument peut mobiliser pour faire vivre son bien.",
            doctrine(skill_path),
            "# Familles (champ `famille`)\n" + familles_rendues(),
            CONSIGNE_EXTRACTION,
            "`retenir: true` par défaut. `retenir: false` UNIQUEMENT sur l'un des deux "
            "constats certains du test d'admission, et la `note` dit lequel.",
        ]
    )


class LectureFiche(BaseModel):
    retenir: bool
    famille: Famille = "adjacente"
    titre: str = Field(description="Intitulé exact du dispositif, tel qu'il apparaît sur la page")
    montant_taux: str | None = Field(
        default=None, description="Montants et taux TELS QUE la page les écrit ; None si absents"
    )
    beneficiaires: str | None = Field(
        default=None, description="Qui peut déposer, d'après la page ; None si non précisé"
    )
    note: str = Field(
        default="",
        description="Pourquoi c'est (ou non) mobilisable par un propriétaire de monument, "
        "et ce qu'il faudra typer à l'ingestion",
    )
    slug_propose: str = Field(
        default="", description="Identifiant en kebab-case, SANS le préfixe territorial"
    )
    urls_pdf: list[str] = []
    doublon_probable: str | None = Field(
        default=None, description="Slug du catalogue dont ce dispositif semble être un doublon"
    )
    priorite: str = "normale"
    source_unique_vulgarisation: bool = Field(
        default=False,
        description="Vrai si la page est une présentation sans règlement ni modalités précises",
    )


@dataclass
class Lecture:
    """Une fiche lue : le candidat d'origine, le verdict, et ce qui a raté."""

    candidat: Candidat
    fiche: LectureFiche | None = None
    erreur: str | None = None

    @property
    def retenue(self) -> bool:
        return self.fiche is not None and self.fiche.retenir


def _documents_lies(page, territoire: Territoire) -> list[str]:
    """Les liens de la page qui ressemblent à un règlement téléchargeable."""
    trouves: list[str] = []
    for _titre, url, _contexte in liens(page):
        if territoire.pdf_probable(url) and url not in trouves:
            trouves.append(url)
    return trouves[:MAX_LIENS_DOCUMENTS]


def lire(
    candidat: Candidat,
    territoire: Territoire,
    fetcheur: Fetcheur,
    client: providall.Client,
    *,
    compteur: Compteur | None = None,
    skill_path: Path = SKILL_PROSPECTION,
) -> Lecture:
    """Ouvre une page candidate et la qualifie. Ne lève jamais."""
    page = fetcheur.get(candidat.url)
    if not page.ok:
        return Lecture(candidat, erreur=f"{page.erreur or f'HTTP {page.status}'}")
    if page.est_pdf:
        return Lecture(candidat, erreur="PDF — à traiter directement à l'ingestion")
    markdown = page.markdown()
    if len(markdown.strip()) < 500:
        return Lecture(
            candidat,
            erreur=f"page vide ou SPA ({len(markdown.strip())} car.) — source citable à chercher",
        )

    documents = _documents_lies(page, territoire)
    prompt = "\n\n".join(
        [
            f"URL : {page.url_finale}",
            "Documents liés depuis cette page (les seuls que tu peux citer dans `urls_pdf`) :\n"
            + ("\n".join(f"  {u}" for u in documents) or "  (aucun)"),
            "--- Contenu de la page ---",
            markdown[:MAX_CAR_PAGE],
        ]
    )
    essai = client.try_complete_json(LectureFiche, prompt, system=consigne(skill_path))
    if compteur is not None:
        compteur.ajouter(essai.response, "lecture")
    if essai.data is None:
        return Lecture(candidat, erreur=f"lecture impossible : {essai.response.error}")

    fiche = essai.data
    # Un PDF que la page ne porte pas est un PDF inventé : on ne garde que ce
    # qui a été réellement vu, sans quoi l'ingestion partirait sur un 404.
    fiche.urls_pdf = [u for u in fiche.urls_pdf if u in documents]
    fiche.note = " ".join(fiche.note.split())[:MAX_CAR_NOTE]
    return Lecture(candidat, fiche=fiche)


# ---------------------------------------------------------------------------
# Slugs
# ---------------------------------------------------------------------------

_NON_SLUG = re.compile(r"[^a-z0-9]+")


def kebab(texte: str) -> str:
    sans_accent = "".join(
        c for c in unicodedata.normalize("NFD", texte.lower()) if unicodedata.category(c) != "Mn"
    )
    return _NON_SLUG.sub("-", sans_accent).strip("-")


LONGUEUR_MAX_SLUG = 60


def _formes_du_territoire(territoire: Territoire) -> list[str]:
    """Ce que le modèle colle volontiers en tête du slug qu'il propose.

    Le préfixe lui-même, le nom du territoire en kebab (« grand-est »), sans
    tirets (« grandest »), et les suffixes du préfixe (« region-grand-est » →
    « grand-est »). Les plus longs d'abord, pour retirer « region-grand-est »
    avant « grand-est ».
    """
    nom = kebab(territoire.nom)
    formes = {territoire.prefixe_slug, nom, nom.replace("-", "")}
    morceaux = territoire.prefixe_slug.split("-")
    formes.update("-".join(morceaux[i:]) for i in range(1, len(morceaux)))
    return sorted((f for f in formes if f), key=len, reverse=True)


def slug_final(territoire: Territoire, propose: str, titre: str, occupes: set[str]) -> str:
    """Slug définitif : préfixe territorial, unicité, jamais un slug déjà pris.

    `occupes` doit contenir les slugs du CATALOGUE et ceux déjà proposés dans la
    même fiche : deux dispositifs voisins d'une même région produisent
    volontiers le même slug, et un doublon écraserait silencieusement le premier
    fichier à l'ingestion.

    Deux défauts vus au balayage Grand Est du 2026-09-08 (8 et 14 slugs sur
    42) : le modèle met déjà le territoire en tête de sa proposition
    (« grand-est-culture », « grandest-soutien-memoire ») et le préfixe se
    retrouvait doublé ; la coupe à 60 caractères tombait au milieu d'un mot
    (« …-renovation-patrimoine-ar »). Un slug devient un nom de fichier
    définitif : on retire les formes du territoire déjà présentes, et on coupe
    sur un tiret.
    """
    base = kebab(propose or titre) or "aide"
    prefixe = territoire.prefixe_slug
    formes = _formes_du_territoire(territoire)
    retire = True
    while retire:
        retire = False
        for forme in formes:
            if base.startswith(f"{forme}-") and len(base) > len(forme) + 1:
                base = base[len(forme) + 1 :]
                retire = True
    base = f"{prefixe}-{base}"
    if len(base) > LONGUEUR_MAX_SLUG:
        base = base[:LONGUEUR_MAX_SLUG]
        if "-" in base[len(prefixe) + 1 :]:
            base = base.rsplit("-", 1)[0]
    base = base.rstrip("-")
    if base not in occupes:
        return base
    for n in range(2, 100):
        candidat = f"{base}-{n}"
        if candidat not in occupes:
            return candidat
    raise ValueError(f"impossible de trouver un slug libre pour « {base} »")


__all__ = [
    "CONSIGNE_EXTRACTION",
    "MAX_CAR_PAGE",
    "Lecture",
    "LectureFiche",
    "LONGUEUR_MAX_SLUG",
    "consigne",
    "kebab",
    "lire",
    "slug_final",
]
