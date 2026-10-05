"""Le test du destinataire par un modèle de DÉCISION (Jev), avant la lecture.

Jev ne rédige rien : il rend des probabilités sur des questions fermées
(`pipeline/decision.py`). Sur les 1 045 aides tranchées à la main du banc
d'essai du 2026-10-04 (`data/reviews/2026-10-04-benchmark-destinataire.md`), le
LLM de lecture écartait à tort 11,4 % des aides gardées — dont
`drac-mh-inscrits`, `fondation-merimee`, `rempart` — et un écart est sans
recours. Jev, à part renvoyée à un humain égale, en écartait 1,2 %.

D'où trois bandes sur la probabilité qu'un propriétaire de monument puisse
déposer (`deposable`) :

    sous SEUIL_BAS    écartée par Jev, sans appel au LLM ;
    au-dessus de      retenue par Jev ; le LLM n'est appelé que pour extraire
    SEUIL_HAUT        (montant, bénéficiaires, slug, PDF, note) ;
    entre les deux    le LLM juge comme avant, MAIS son écart devient une
                      indétermination : c'est dans cette bande que tombaient
                      presque tous ses écarts à tort.

Jev ne tranche seul que si ses réponses détaillées (destinataire, objet,
dispositif) vont dans le sens de son score : une page notée 0,05 qu'il dit
pourtant adressée au propriétaire, pour son bâti, n'est pas un écart sûr.

Mesuré sur le banc avec ces seuils : 0,7 % de gardées écartées à tort, 3,4 %
d'écartées retenues à tort (3,2 % pour le LLM seul), 56 % renvoyées à un
humain (55 %), 34 % des pages tranchées par Jev seul. Les seuils viennent des
données, pas de la plaquette : les probabilités brutes de Jev sont trop
basses (annoncé 0,25, gardé 62 %). Les régler à nouveau = relancer
`benchmark_destinataire.py` et lire la section « Tête-à-tête ».
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.decision import ClientDecision, choix, noul
from pipeline.etat import OBJETS_RETENUS

from .tri import SKILL_PROSPECTION, doctrine

SEUIL_BAS = 0.12
SEUIL_HAUT = 0.57

Bande = Literal["ecartee", "milieu", "retenue"]

INTRO = (
    "Tu juges UNE page de dispositif d'aide pour le catalogue Monumia, qui recense ce "
    "qu'un propriétaire de monument peut mobiliser pour faire vivre son bien. La "
    "doctrine ci-dessous (`doctrine`) décide de l'entrée ; la page est dans `page`."
)

# Les critères reprennent CONSIGNE_DESTINATAIRE (lecture.py) mot pour mot quand
# c'est possible : deux juges sous deux doctrines ne se compareraient pas.
# `indetermine` n'est PAS une option : c'est la bande du milieu qui le porte.
# Ne pas reformuler à la légère : les seuils ont été mesurés sur ces textes.
QUESTIONS: dict[str, Any] = {
    "destinataire": choix(
        "À qui la source s'adresse-t-elle, et en quelle qualité ?",
        {
            "proprietaire_gestionnaire": (
                "À celui qui POSSÈDE ou GÈRE un lieu, pris en cette qualité (particulier, "
                "commune ou EPCI propriétaire, association gestionnaire, SCI, société qui "
                "exploite le lieu). Y compris quand la source liste des bénéficiaires qui "
                "couvrent les deux (« communes, associations et structures culturelles ») "
                "ou ne dit pas en quelle qualité."
            ),
            "activite_tiers": (
                "À quelqu'un POUR SON MÉTIER ou son activité : agriculteur, forestier "
                "producteur, PME en général, artisan, commerçant, compagnie, artiste, "
                "association pour sa pratique sportive ou musicale, bailleur social. "
                "Seulement si la source RÉSERVE l'aide au métier (label professionnel, "
                "licence d'entrepreneur de spectacles, affiliation MSA, RCS)."
            ),
            "personne": (
                "À un individu ou à un ménage pour sa situation (ressources, âge, emploi, "
                "formation, santé, logement)."
            ),
        },
    ),
    "objet": choix(
        "Sur quoi porte la dépense aidée ?",
        {
            "bien_ou_lieu": "Le bien lui-même, son bâti, son domaine, ses abords.",
            "activite_dans_le_lieu": (
                "Ce qui s'y tient et que le propriétaire porte LUI-MÊME (ouvrir, animer, "
                "héberger, installer une activité)."
            ),
            "hors_lieu": (
                "Ailleurs, ou sans lieu (promotion d'une destination, production d'une "
                "œuvre, formation, matériel mobile, réseau public)."
            ),
        },
    ),
    "dispositif": noul(
        "La page décrit-elle un dispositif qu'on peut demander (subvention, prêt, appel "
        "à projets, aide en nature, label ouvrant droit à une aide) ?",
        vrai="Oui : on peut déposer une demande au titre de ce dispositif.",
        faux=(
            "Non : page-portail, liste de dispositifs, actualité, guide, programme qui "
            "renvoie à d'autres fiches : rien à y demander."
        ),
    ),
    "deposable": noul(
        "Un propriétaire de monument peut-il déposer cette demande tel qu'il est, pour "
        "son monument, sans changer de métier ni créer une structure pour l'occasion ?",
        vrai="Oui, il en est un destinataire légitime, en sa qualité de propriétaire ou gestionnaire.",
        faux=(
            "Non : il faudrait qu'il soit aussi agriculteur, entreprise, compagnie, artiste, "
            "ménage aidé, ou que la dépense porte hors de son lieu."
        ),
    ),
    # Seulement pour le motif d'une page écartée sans lecture : la catégorie
    # trie la fiche de prospection, elle ne décide de rien.
    "categorie_ecart": choix(
        "Si un propriétaire de monument ne peut pas déposer cette demande, pourquoi ?",
        {
            "metier_agricole": "Elle vise l'agriculteur, l'éleveur, le forestier producteur.",
            "entreprise_generale": "Elle vise l'entreprise, la PME, l'artisan, le commerçant en général.",
            "organisateur_artiste": "Elle vise la compagnie, l'artiste, l'auteur, le festival pour son œuvre.",
            "pratique_amateur": "Elle vise l'association pour sa pratique sportive, musicale ou de loisir.",
            "aide_personne": "Elle vise un individu ou un ménage pour sa situation.",
            "non_dispositif": "La page n'est pas un dispositif : portail, actualité, guide, liste.",
            "objet_hors_lieu": "La dépense porte ailleurs que sur un lieu ou ce qui s'y tient.",
        },
    ),
}


@dataclass(frozen=True)
class Seuils:
    bas: float = SEUIL_BAS
    haut: float = SEUIL_HAUT


def seuils() -> Seuils:
    """Les seuils de production, réglables par `JEV_SEUIL_BAS` / `JEV_SEUIL_HAUT`."""
    return Seuils(
        bas=float(os.environ.get("JEV_SEUIL_BAS") or SEUIL_BAS),
        haut=float(os.environ.get("JEV_SEUIL_HAUT") or SEUIL_HAUT),
    )


@dataclass(frozen=True)
class Arbitrage:
    """Le jugement de Jev sur une page, et la bande qui en découle."""

    deposable: float
    destinataire: str
    objet: str
    dispositif: float
    categorie_ecart: str
    bande: Bande
    modele: str
    cout_usd: float | None
    jetons_entree: int

    @property
    def structure_ecarte(self) -> bool:
        return structure_ecarte(self.destinataire, self.objet, self.dispositif)

    def resume(self) -> str:
        return f"Jev {self.deposable:.2f}"

    def en_dict(self) -> dict[str, Any]:
        return {
            "deposable": round(self.deposable, 4),
            "destinataire": self.destinataire,
            "objet": self.objet,
            "dispositif": round(self.dispositif, 4),
            "categorie_ecart": self.categorie_ecart,
            "bande": self.bande,
            "modele": self.modele,
        }


def structure_ecarte(destinataire: str, objet: str, dispositif: float) -> bool:
    """Ce que disent les réponses détaillées, lues comme `etat.retenir` les lirait."""
    return (
        destinataire != "proprietaire_gestionnaire"
        or objet not in OBJETS_RETENUS
        or dispositif < 0.5
    )


def bande(deposable: float, ecarte: bool, s: Seuils) -> Bande:
    """La bande d'une page. Hors cohérence, c'est toujours le milieu."""
    if deposable < s.bas and ecarte:
        return "ecartee"
    if deposable > s.haut and not ecarte:
        return "retenue"
    return "milieu"


@lru_cache(maxsize=4)
def _doctrine(skill_path: Path) -> str:
    return f"{INTRO}\n\n{doctrine(skill_path)}"


def etat(url: str, texte: str, skill_path: Path = SKILL_PROSPECTION) -> dict[str, Any]:
    return {"doctrine": _doctrine(skill_path), "page": {"url": url, "texte": texte}}


def arbitrer(
    client: ClientDecision,
    url: str,
    texte: str,
    *,
    s: Seuils | None = None,
    skill_path: Path = SKILL_PROSPECTION,
) -> Arbitrage:
    """Un appel à Jev. Lève `ErreurDecision` : à l'appelant de retomber sur le LLM."""
    d = client.decider(etat(url, texte, skill_path), QUESTIONS)
    r = d.reponses
    deposable = r["deposable"].proba("true")
    destinataire = r["destinataire"].choix or ""
    objet = r["objet"].choix or ""
    dispositif = r["dispositif"].proba("true")
    categorie = r["categorie_ecart"].choix or "objet_hors_lieu"
    if dispositif < 0.5:
        categorie = "non_dispositif"
    return Arbitrage(
        deposable=deposable,
        destinataire=destinataire,
        objet=objet,
        dispositif=dispositif,
        categorie_ecart=categorie,
        bande=bande(deposable, structure_ecarte(destinataire, objet, dispositif), s or seuils()),
        modele=d.modele,
        cout_usd=d.cout_usd,
        jetons_entree=d.jetons_entree,
    )


__all__ = [
    "QUESTIONS",
    "SEUIL_BAS",
    "SEUIL_HAUT",
    "Arbitrage",
    "Seuils",
    "arbitrer",
    "bande",
    "etat",
    "seuils",
    "structure_ecarte",
]
