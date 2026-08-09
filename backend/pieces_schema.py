"""
Référentiel des pièces canoniques de dossier.

Source de vérité : backend/data/pieces.yaml — un dictionnaire indexé par id,
sur le modèle de data/facts.yaml.

Les organismes demandent la même pièce sous des libellés différents (« RIB »,
« relevé d'identité bancaire », « relevé d'identité bancaire ou postal avec
IBAN »…). Ce référentiel donne à chacune un identifiant unique, ce qui permet
de reconnaître qu'une pièce déjà déposée répond à la demande d'une autre aide.

`portee` — jusqu'où une pièce peut être réutilisée :
  porteur    le demandeur lui-même (RIB, SIRET, statuts, bilan) : réutilisable
             sur tous ses dossiers, tous projets confondus
  monument   le bâti (titre de propriété, cadastre, arrêté de protection) :
             réutilisable dans le projet, donc partagée avec les co-propriétaires
  operation  les travaux en cours (devis, plan de financement, courrier de
             demande) : propre à un dossier, jamais reproposée ailleurs

`perissable` — la pièce se démode et doit être revérifiée passé
`seuil_alerte_mois`. On n'encode PAS de durée de validité juridique : le seuil
sert à alerter, pas à décider.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

DATA_DIR = Path(__file__).resolve().parent / "data"
PIECES_FILE = DATA_DIR / "pieces.yaml"

PORTEES = ("porteur", "monument", "operation")

# Miroir de DocumentType (frontend/src/types/document.types.ts). Un type
# inconnu ici produirait une pièce que l'interface ne saurait pas étiqueter.
TYPE_DOCUMENTS = (
    "photo",
    "plan",
    "devis",
    "facture",
    "attestation",
    "extrait_cadastral",
    "cerfa",
    "arrete",
    "diagnostic",
    "rapport",
    "correspondance",
    "autre",
)


class Piece(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nom: str
    description: str | None = None
    portee: Literal["porteur", "monument", "operation"]
    perissable: bool = False
    seuil_alerte_mois: int | None = None
    type_document: Literal[
        "photo",
        "plan",
        "devis",
        "facture",
        "attestation",
        "extrait_cadastral",
        "cerfa",
        "arrete",
        "diagnostic",
        "rapport",
        "correspondance",
        "autre",
    ] = "autre"

    @model_validator(mode="after")
    def _coherence_peremption(self) -> Piece:
        if self.perissable and self.seuil_alerte_mois is None:
            raise ValueError("une pièce périssable doit porter un seuil_alerte_mois")
        if not self.perissable and self.seuil_alerte_mois is not None:
            raise ValueError("seuil_alerte_mois n'a de sens que sur une pièce périssable")
        if self.seuil_alerte_mois is not None and self.seuil_alerte_mois <= 0:
            raise ValueError("seuil_alerte_mois doit être strictement positif")
        return self


# Caché comme les loaders d'aides_schema : le YAML ne change qu'au déploiement.
# Corollaire : la structure retournée est PARTAGÉE, ne jamais la modifier en place.
@cache
def load_pieces(path: Path = PIECES_FILE) -> dict[str, Piece]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {key: Piece.model_validate(val) for key, val in raw.items()}
