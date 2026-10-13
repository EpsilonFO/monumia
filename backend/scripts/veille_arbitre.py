"""Jev dans la veille : trois décisions fermées, des probabilités.

Jev est un modèle de DÉCISION (`pipeline/decision.py`) : il ne rédige rien et
rend des probabilités sur des questions fermées. Il ne remplace rien de ce qui
est déterministe dans la veille (édition YAML, lint d'écriture, manifeste,
clés d'URL, `ligne_de_reglement`). Il tranche trois décisions que des seuils
faits main tranchent mal (plan : `data/reviews/2026-10-04-plan-jev-veille.md`) :

    filtre   avant l'étage C : un diff sous SEUIL_FILTRE est du bruit, l'aide
             passe `inchange` sans appel au LLM et sa page est ré-archivée ;
    garde    après un « inchangé » du LLM : au-dessus de SEUIL_GARDE, la page
             n'est PAS ré-archivée et l'aide sort `suspect`. C'est le cas du
             2026-10-04 : le résumé du LLM décrivait lui-même le report d'une
             date limite (`88-musee-centre-interpretation`,
             `01-pactes-de-territoire-…`) et concluait « inchangé » — la
             baseline ré-archivée, le changement était perdu pour de bon ;
    refonte  entre l'étage B et l'étage C : une escalade de la règle 6
             (pourcentage de lignes changées) dont Jev juge le règlement
             identique au-dessus de SEUIL_REFONTE est RÉTROGRADÉE en MAJ_LLM,
             jamais classée inchangée. L'étage C la lit avec son mandat et la
             garde s'applique : une erreur de Jev coûte une retouche rattrapée,
             pas une fiche qui diverge en silence.

**Les seuils viennent du banc d'essai, pas d'une intuition**
(`scripts/veille_benchmark_jev.py`). Tant qu'un seuil vaut `None`, sa décision
n'est pas branchée : la veille se comporte exactement comme avant. Une étape
n'est branchée que si le banc montre, sur son jeu, un seuil sans aucun faux
manquant. Réglables sans toucher au code par `JEV_VEILLE_FILTRE`,
`JEV_VEILLE_GARDE` et `JEV_VEILLE_REFONTE` (`off` coupe une décision).

Jev en panne ou clé absente : comportement actuel, signalé au rapport.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.decision import ClientDecision, ErreurDecision, choix, noul

from aides_schema import Aide

# Sous ce seuil, le diff ne touche pas le mandat : pas d'appel au LLM.
SEUIL_FILTRE: float | None = None
# Au-dessus, un « inchangé » du LLM est suspect : pas de ré-archivage.
# Banc du 2026-10-04 (72 « inchangé » d'or-glm, dont 9 faux) : à 0,45 la garde
# en attrape 5 (notes 0,47 à 0,93) pour 2 fausses alertes, deux pages savoie.fr
# depuis filtrées comme bruit ; à 0,08 elle les attrapait toutes, mais avec 35
# fausses alertes sur 63. Choix de Félix : peu de relecture.
SEUIL_GARDE: float | None = 0.45
# Au-dessus, une refonte de la règle 6 est rétrogradée en MAJ_LLM.
SEUIL_REFONTE: float | None = None

# Jev lit 32 k jetons. Le diff est déjà plafonné en lignes (MAX_LIGNES_DIFF),
# pas en caractères : une ligne de PDF mal extrait peut faire des milliers de
# caractères.
MAX_CAR_DIFF = 40_000
MAX_CAR_PAGE = 60_000

INTRO_MANDAT = (
    "Tu surveilles la page source d'une aide au financement du patrimoine. `fiche` est ce "
    "que le catalogue affiche aujourd'hui pour cette aide. `diff` liste les lignes de la "
    "page qui ont changé depuis la dernière visite : « - » ligne retirée, « + » ligne "
    "ajoutée, une URL en tête de chaque page."
)
INTRO_RESUME = (
    "`resume_lecteur` est le résumé d'un premier lecteur qui a lu la page fraîche en "
    "entier. Ce qu'il DÉCRIT est dans la page ; son verdict, lui, peut être faux."
)
INTRO_REFONTE = (
    "Tu compares une fiche d'aide au financement du patrimoine (`fiche`, ce que le "
    "catalogue affiche aujourd'hui) à la page officielle telle qu'elle est servie "
    "aujourd'hui (`pages`). La page a été largement réécrite : refonte du site, ou "
    "nouveau règlement ?"
)

# Ne pas reformuler à la légère : les seuils sont mesurés sur ces textes.
QUESTIONS_MANDAT: dict[str, Any] = {
    "touche": noul(
        "Ce changement de la page modifie-t-il une échéance, un montant, un taux, un "
        "plafond de cumul ou une condition d'éligibilité de la fiche ?",
        vrai=(
            "Oui : une date de dépôt ou d'ouverture, un montant, un taux, un plafond, un "
            "bénéficiaire, une dépense éligible ou un critère a changé, est apparu ou a "
            "disparu, et la fiche ne le dit pas encore."
        ),
        faux=(
            "Non : le changement porte sur autre chose (navigation, actualités, horaires "
            "d'accueil, date de mise à jour de la page, mise en forme, liens de partage), "
            "ou redit ce que la fiche contient déjà."
        ),
    ),
    # Pour le rapport seulement : la catégorie ne décide de rien.
    "section": choix(
        "Quelle partie de la fiche ce changement touche-t-il ?",
        {
            "calendrier": "Dates d'ouverture, date limite, délai d'instruction.",
            "financement": "Montants, taux, plafond, plancher, assiette.",
            "cumul": "Règles de cumul avec d'autres aides, plafond d'aides publiques.",
            "conditions": "Bénéficiaires, dépenses éligibles, critères d'éligibilité.",
            "rien": "Aucune : le changement est hors de la fiche.",
        },
    ),
}

QUESTIONS_REFONTE: dict[str, Any] = {
    "meme_reglement": noul(
        "Le dispositif décrit par la page d'aujourd'hui a-t-il le même règlement que la "
        "fiche (bénéficiaires, dépenses éligibles, montants, calendrier) ?",
        vrai=(
            "Oui : même dispositif, mêmes bénéficiaires, mêmes dépenses, mêmes montants et "
            "mêmes dates ; seule la présentation de la page a changé."
        ),
        faux=(
            "Non : au moins un de ces éléments diffère, ou la page ne décrit plus ce dispositif."
        ),
    ),
}


# --------------------------------------------------------------------------
# Seuils
# --------------------------------------------------------------------------


def _seuil(nom: str, defaut: float | None) -> float | None:
    brut = (os.environ.get(nom) or "").strip().lower()
    if not brut:
        return defaut
    if brut in ("off", "non", "none"):
        return None
    return float(brut)


@dataclass(frozen=True)
class Seuils:
    filtre: float | None = SEUIL_FILTRE
    garde: float | None = SEUIL_GARDE
    refonte: float | None = SEUIL_REFONTE

    @property
    def actif(self) -> bool:
        return any(s is not None for s in (self.filtre, self.garde, self.refonte))

    def decrire(self) -> str:
        def f(s: float | None) -> str:
            return "—" if s is None else f"{s:.2f}"

        return f"filtre {f(self.filtre)} · garde {f(self.garde)} · refonte {f(self.refonte)}"


def seuils() -> Seuils:
    """Les seuils de production, réglables par l'environnement."""
    return Seuils(
        filtre=_seuil("JEV_VEILLE_FILTRE", SEUIL_FILTRE),
        garde=_seuil("JEV_VEILLE_GARDE", SEUIL_GARDE),
        refonte=_seuil("JEV_VEILLE_REFONTE", SEUIL_REFONTE),
    )


# --------------------------------------------------------------------------
# États
# --------------------------------------------------------------------------


def fiche_pour_jev(aide: Aide) -> dict[str, Any]:
    """Ce que la veille a le droit de retoucher, et rien d'autre."""
    return {
        "nom": aide.nom,
        "calendrier": aide.calendrier.model_dump(mode="json", exclude_none=True),
        "financement": aide.financement.model_dump(mode="json", exclude_none=True),
        "cumul": aide.cumul.model_dump(mode="json", exclude_none=True),
        "conditions": [c.text for c in aide.conditions],
    }


def _fiche(aide: Aide | dict[str, Any]) -> dict[str, Any]:
    # Le banc d'essai passe une fiche déjà réduite : celle d'AVANT le passage
    # étudié, quand le working tree porte déjà la retouche.
    return aide if isinstance(aide, dict) else fiche_pour_jev(aide)


def etat_mandat(
    aide: Aide | dict[str, Any], diff: str, resume: str | None = None
) -> dict[str, Any]:
    etat: dict[str, Any] = {
        "consigne": INTRO_MANDAT + (" " + INTRO_RESUME if resume else ""),
        "fiche": _fiche(aide),
        "diff": diff[:MAX_CAR_DIFF],
    }
    if resume:
        etat["resume_lecteur"] = resume
    return etat


def etat_refonte(aide: Aide | dict[str, Any], pages: list[tuple[str, str]]) -> dict[str, Any]:
    budget = MAX_CAR_PAGE // max(len(pages), 1)
    return {
        "consigne": INTRO_REFONTE,
        "fiche": _fiche(aide),
        "pages": [{"url": url, "texte": texte[:budget]} for url, texte in pages],
    }


# --------------------------------------------------------------------------
# Jugements
# --------------------------------------------------------------------------


def note(p: float) -> str:
    """« p = 0,03 » : la forme du rapport et du journal."""
    return f"p = {p:.2f}".replace(".", ",")


@dataclass(frozen=True)
class Jugement:
    p: float
    section: str | None
    modele: str
    cout_usd: float

    @property
    def note(self) -> str:
        return note(self.p)


@dataclass
class Arbitre:
    """Le client Jev, les seuils, et le compte du passage (appels, coût, pannes)."""

    client: ClientDecision
    seuils: Seuils
    appels: int = 0
    cout_usd: float = 0.0
    pannes: list[str] = field(default_factory=list)

    def _decider(self, etat: dict[str, Any], questions: dict[str, Any]):
        try:
            d = self.client.decider(etat, questions)
        except ErreurDecision as exc:
            self.pannes.append(str(exc))
            raise
        self.appels += 1
        self.cout_usd += d.cout_usd or 0.0
        return d

    def mandat(self, aide: Aide, diff: str, resume: str | None = None) -> Jugement:
        """Ce diff touche-t-il le mandat ? Lève `ErreurDecision`."""
        d = self._decider(etat_mandat(aide, diff, resume), QUESTIONS_MANDAT)
        return Jugement(
            p=d.reponses["touche"].proba("true"),
            section=d.reponses["section"].choix,
            modele=d.modele,
            cout_usd=d.cout_usd or 0.0,
        )

    def refonte(self, aide: Aide, pages: list[tuple[str, str]]) -> Jugement:
        """La page réécrite porte-t-elle le même règlement ? Lève `ErreurDecision`."""
        d = self._decider(etat_refonte(aide, pages), QUESTIONS_REFONTE)
        return Jugement(
            p=d.reponses["meme_reglement"].proba("true"),
            section=None,
            modele=d.modele,
            cout_usd=d.cout_usd or 0.0,
        )

    def bilan(self) -> str:
        texte = f"{self.appels} appel(s) Jev, {self.cout_usd:.3f} $"
        if self.pannes:
            texte += (
                f", {len(self.pannes)} en panne (comportement sans Jev) : {self.pannes[0][:120]}"
            )
        return texte


def construire(s: Seuils | None = None) -> tuple[Arbitre | None, str]:
    """L'arbitre du passage, ou `None` et la raison pour laquelle Jev ne joue pas."""
    s = s or seuils()
    if not s.actif:
        return None, "aucun seuil réglé (banc d'essai à faire : scripts/veille_benchmark_jev.py)"
    try:
        client = ClientDecision()
    except ErreurDecision as exc:
        return None, str(exc)
    return Arbitre(client=client, seuils=s), s.decrire()


def empreinte_etat(etat: dict[str, Any]) -> str:
    """Clé de cache du banc d'essai : deux états identiques, un seul appel."""
    brut = json.dumps(etat, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(brut.encode()).hexdigest()[:16]


__all__ = [
    "QUESTIONS_MANDAT",
    "QUESTIONS_REFONTE",
    "Arbitre",
    "ErreurDecision",
    "Jugement",
    "Seuils",
    "construire",
    "empreinte_etat",
    "etat_mandat",
    "etat_refonte",
    "fiche_pour_jev",
    "note",
    "seuils",
]
