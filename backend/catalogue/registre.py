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
        return self

    def modele(self, role: str) -> Modele:
        return self.modeles[role]


def charger(chemin: Path = REGISTRE) -> Registre:
    """Le registre validé. Lève `ValueError` (ou une erreur de validation) s'il ne l'est pas."""
    brut = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    if not isinstance(brut, dict):
        raise ValueError(f"{chemin} : registre vide ou illisible")
    return Registre.model_validate(brut)
