"""Le registre des pipelines : modèles par rôle, décisions et seuils, réglages, budgets.

Un seul fichier, `backend/data/catalogue/registre.yaml`, versionné : changer de
modèle revient à changer un nom ici puis à recalibrer ce qui en dépend. Le
chargement valide tout ; un registre invalide est une panne de run, jamais un
registre partiel.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

BACKEND = Path(__file__).resolve().parents[1]
REGISTRE = BACKEND / "data" / "catalogue" / "registre.yaml"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Modele(_Strict):
    nom: str
    acceptes: list[str] = Field(min_length=1)
    alias_providall: str | None = None
    effort: Literal["low", "medium", "high"] | None = None
    delai_s: float = Field(gt=0)
    # Tarif en dollars par million de jetons, relevé sur /api/v1/models : il ne
    # sert qu'à RÉSERVER le coût plafond d'un appel avant de le lancer. Le coût
    # compté est toujours celui que la réponse facture.
    prix_entree: float = Field(ge=0)
    prix_sortie: float = Field(ge=0)

    def plafond_usd(self, jetons_entree: int, jetons_sortie: int) -> float:
        """Ce qu'un appel peut coûter au plus, pour une réservation du budget."""
        return (jetons_entree * self.prix_entree + jetons_sortie * self.prix_sortie) / 1e6


class DecisionFermee(_Strict):
    statut: Literal["en_service", "candidat", "non_adopte"]
    decideur: Literal["code", "jev", "llm", "agent", "regle_production", "felix"]
    modele: str | None = None
    empreintes: dict[str, str] = {}
    seuils: dict[str, float] = {}
    budget: dict[str, float] = {}
    mesure: dict[str, Any] = {}
    note: str | None = None


class Reglages(_Strict):
    doute: Literal["a", "b", "c", "d"]
    git: Literal["diff", "commit"]
    faits_neufs: Literal["case", "auto"]
    text: Literal["citation", "reformulation"]
    rebuts: Literal["dossier", "echec"]
    extraction: Literal["agent", "structuree"]
    zone_prudente: Literal["appliquee", "refusee"]
    #: Une condition typée autrement que sa famille : une case pour Félix
    #: (`case`), ou le lint de l'agent l'oblige à s'aligner (`aligner`), sauf
    #: quand la famille retirerait un gate (`espace.garde_son_gate`).
    typage_famille: Literal["case", "aligner"]
    #: Une aide absente de son guide deux listings sains de suite, et dont la
    #: page est morte : retirée sans case (`auto`), ou une case (`case`).
    #: Page vivante ou titre voisin listé ailleurs : une case dans les deux cas.
    sorties: Literal["auto", "case"]


class BudgetsErreur(_Strict):
    pertes_entree: float
    pertes_tri: float
    admissions_a_tort: float
    changements_manques: float
    fausses_retouches: float
    doublons_faits: float
    rapport_cout_perte_admission: float


class BudgetsRun(_Strict):
    plafond_usd: float = Field(gt=0)
    delai_h: float = Field(gt=0)
    parallelisme_ingestion: int = Field(ge=1)


class Budgets(_Strict):
    erreurs: BudgetsErreur
    run: BudgetsRun


class Registre(_Strict):
    version: Literal[1]
    modeles: dict[str, Modele]
    decisions: dict[str, DecisionFermee]
    reglages: Reglages
    proprietaires: dict[
        Literal["veille", "escalades", "prospection", "ingestion"], Literal["ancienne", "nouvelle"]
    ]
    budgets: Budgets

    @model_validator(mode="after")
    def _references(self) -> Registre:
        for nom, d in self.decisions.items():
            if d.modele is not None and d.modele not in self.modeles:
                raise ValueError(f"décision {nom} : rôle de modèle inconnu « {d.modele} »")
        manquants = {"veille", "escalades", "prospection", "ingestion"} - set(self.proprietaires)
        if manquants:
            raise ValueError(f"propriétaire manquant pour : {', '.join(sorted(manquants))}")
        # La prospection admet, l'ingestion écrit ; séparées, l'une laisserait du
        # travail que l'autre ne lit pas (des `valide` sans ingestion, ou des
        # admises jamais projetées dans la file).
        if self.proprietaires["prospection"] != self.proprietaires["ingestion"]:
            raise ValueError("prospection et ingestion doivent appartenir à la même chaîne")
        return self

    def modele(self, role: str) -> Modele:
        return self.modeles[role]


def charger(chemin: Path = REGISTRE) -> Registre:
    """Le registre validé. Lève `ValueError` (ou une erreur de validation) s'il ne l'est pas."""
    brut = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    if not isinstance(brut, dict):
        raise ValueError(f"{chemin} : registre vide ou illisible")
    return Registre.model_validate(brut)


def faits_neufs_en_case() -> bool:
    """Un fait neuf ouvre-t-il une case `H-fait` (réglage `faits_neufs: case`) ?

    En `auto`, il entre dans `facts_pending.yaml`, servi au questionnaire comme
    un fait approuvé, sans attendre Félix.
    """
    return charger().reglages.faits_neufs == "case"


def refus_ancienne(operation: str, chemin: Path | None = None) -> str | None:
    """Le motif de refus d'un ancien script quand le registre donne `operation` à la nouvelle chaîne.

    Pendant la transition, une seule chaîne écrit chaque opération (section 10
    d'`architecture.md`). Sans registre, rien ne change ; un registre illisible
    refuse, puisqu'il ne dit plus qui écrit.
    """
    chemin = chemin or REGISTRE
    if not chemin.exists():
        return None
    try:
        reg = charger(chemin)
    except Exception as exc:  # noqa: BLE001 — tout registre illisible refuse
        return f"registre du catalogue illisible ({chemin}) : {exc}"
    if reg.proprietaires.get(operation) == "nouvelle":  # type: ignore[call-overload]
        return (
            f"l'opération « {operation} » appartient à la nouvelle chaîne (registre du "
            f"catalogue, `proprietaires.{operation}: nouvelle`) : passer par "
            "`uv run python -m catalogue`, ou repasser le registre à `ancienne`"
        )
    return None
