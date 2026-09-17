"""La file d'attente des aides à ingérer : `data/prospection/file-attente.yaml`.

Un dict YAML à clé = slug, trié, versionné — même idiome que
`data/veille-state.yaml`, et pour la même raison : c'est le diff git qui rend
lisible ce que la prospection a proposé et ce que l'ingestion en a fait.

Le cycle d'un slug :

    a_valider ──(prospecter.py valider)──> valide ──> en_cours ──> ingere
        │                                                │
        └──(prospecter.py ignorer)──> ignore             └──────> echec

`a_valider` est le point de contrôle humain : la prospection ne décide jamais
seule d'ingérer. `--auto` le franchit sans attendre, c'est son seul effet.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict

from .verrou import ecrire_atomique, verrou_fichier

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BACKEND_DIR / "data"
PROSPECTION_DIR = DATA_DIR / "prospection"
FILE_ATTENTE = PROSPECTION_DIR / "file-attente.yaml"

Statut = Literal["a_valider", "valide", "ignore", "en_cours", "ingere", "echec"]
STATUTS: tuple[str, ...] = ("a_valider", "valide", "ignore", "en_cours", "ingere", "echec")

Priorite = Literal["haute", "normale", "basse"]


class Ingestion(BaseModel):
    """Ce que le dernier passage d'ingestion a produit pour ce slug.

    Absent du YAML tant que rien n'a tourné. Toujours FUSIONNÉ et jamais
    remplacé en bloc : `tentatives` doit survivre à une reprise, sinon un slug
    qui échoue en boucle ne se distingue plus d'un slug neuf.
    """

    model_config = ConfigDict(extra="forbid")

    debut: str | None = None
    fin: str | None = None
    modele: str | None = None
    modele_verif: str | None = None
    tours: int | None = None
    cout_usd: float | None = None
    review: str | None = None
    motif_echec: str | None = None
    tentatives: int = 0


class Tache(BaseModel):
    """Une aide candidate : d'où elle vient, où elle en est."""

    model_config = ConfigDict(extra="forbid")

    titre: str
    url: str
    # Documents à snapshoter en plus de la page (règlement, cadre d'intervention).
    urls_pdf: list[str] = []
    territoire: str
    famille: str | None = None
    # Qui peut déposer, d'après la page de prospection. Transmis tel quel à
    # l'ingestion, qui doit le VÉRIFIER sur la source et le typer en gate
    # `statut_juridique_porteur` : cette donnée était lue à la prospection puis
    # perdue entre la fiche markdown et la file.
    beneficiaires: str | None = None
    priorite: Priorite = "normale"
    statut: Statut = "a_valider"
    ajoute_le: date | None = None
    # Fiche de prospection qui l'a proposée, chemin relatif à backend/.
    fiche: str | None = None
    ingestion: Ingestion | None = None


def _en_yaml(taches: dict[str, Tache]) -> str:
    brut: dict[str, Any] = {}
    for slug, tache in taches.items():
        # `mode="json"` pour que les dates sortent en chaînes ISO plutôt qu'en
        # objets `datetime.date`, que `safe_dump` écrirait sans guillemets.
        donnees = tache.model_dump(mode="json")
        # Les champs vides du haut de fiche disparaissent (bruit dans le diff) ;
        # ceux du bloc `ingestion` restent, `motif_echec: null` compris — c'est
        # là qu'on veut lire explicitement « aucun motif d'échec ».
        brut[slug] = {k: v for k, v in donnees.items() if v is not None}
    return yaml.safe_dump(brut, allow_unicode=True, sort_keys=True, width=1000)


def charger(chemin: Path = FILE_ATTENTE) -> dict[str, Tache]:
    """Fichier absent ou vide ⇒ file vide (premier run)."""
    if not chemin.exists():
        return {}
    brut = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    return {slug: Tache.model_validate(valeur) for slug, valeur in brut.items()}


def ecrire(chemin: Path, taches: dict[str, Tache]) -> None:
    ecrire_atomique(chemin, _en_yaml(taches))


def fusionner(chemin: Path, nouvelles: dict[str, Tache]) -> list[str]:
    """Ajoute les slugs inconnus, laisse les connus tranquilles. Renvoie les ajoutés.

    Non destructive par construction : une seconde prospection du même
    territoire re-propose forcément les mêmes dispositifs, et écraser leur
    `statut` remettrait à `a_valider` des aides déjà ingérées — ou pire,
    effacerait un `ignore` que l'utilisateur avait posé à la main.

    Seul `urls_pdf` est COMPLÉTÉ sur une tâche existante : un règlement PDF
    découvert au second passage est une information neuve, et l'ajouter ne
    contredit aucune décision humaine.
    """
    with verrou_fichier(chemin):
        courant = charger(chemin)
        ajoutes: list[str] = []
        for slug, tache in nouvelles.items():
            existante = courant.get(slug)
            if existante is None:
                courant[slug] = tache
                ajoutes.append(slug)
                continue
            manquants = [u for u in tache.urls_pdf if u not in existante.urls_pdf]
            if manquants:
                courant[slug] = existante.model_copy(
                    update={"urls_pdf": [*existante.urls_pdf, *manquants]}
                )
        ecrire(chemin, courant)
    return ajoutes


def mettre_a_jour(chemin: Path, slug: str, **champs: Any) -> Tache:
    """Modifie une tâche sous verrou (relit, modifie, réécrit). Renvoie la tâche à jour.

    `ingestion` est le seul champ FUSIONNÉ plutôt que remplacé : le worker
    n'écrit que ce qu'il vient d'apprendre (le coût à la fin, le motif d'échec
    en cas de rejet) et ne doit pas effacer ce que la tentative précédente
    avait consigné.
    """
    with verrou_fichier(chemin):
        courant = charger(chemin)
        tache = courant.get(slug)
        if tache is None:
            raise KeyError(f"slug absent de la file d'attente : {slug}")
        if "ingestion" in champs:
            fusion = champs["ingestion"]
            if isinstance(fusion, Ingestion):
                fusion = fusion.model_dump(exclude_unset=True)
            base = tache.ingestion.model_dump() if tache.ingestion else {}
            champs = {**champs, "ingestion": Ingestion.model_validate({**base, **(fusion or {})})}
        maj = Tache.model_validate({**tache.model_dump(), **champs})
        courant[slug] = maj
        ecrire(chemin, courant)
    return maj


def transition(chemin: Path, slug: str, vers: Statut, *, depuis: Sequence[str]) -> bool:
    """Change le statut SI le statut courant est l'un de `depuis`, sinon False.

    C'est le jeton qui empêche deux orchestrateurs de prendre la même aide :
    `transition(..., "en_cours", depuis=("valide",))` est atomique sous le
    verrou, donc un seul des deux l'obtient. Un `False` n'est pas une erreur,
    c'est « quelqu'un d'autre l'a déjà ».
    """
    with verrou_fichier(chemin):
        courant = charger(chemin)
        tache = courant.get(slug)
        if tache is None or tache.statut not in depuis:
            return False
        courant[slug] = tache.model_copy(update={"statut": vers})
        ecrire(chemin, courant)
    return True


def selectionner(
    etat: dict[str, Tache],
    *,
    statuts: Iterable[str] = ("valide",),
    territoires: Iterable[str] | None = None,
    slugs: Iterable[str] | None = None,
) -> list[str]:
    """Slugs retenus, triés par priorité (haute d'abord) puis par ordre alphabétique."""
    voulus = set(statuts)
    filtre_terr = set(territoires) if territoires else None
    filtre_slugs = set(slugs) if slugs else None
    rang = {"haute": 0, "normale": 1, "basse": 2}
    retenus = [
        slug
        for slug, t in etat.items()
        if t.statut in voulus
        and (filtre_terr is None or t.territoire in filtre_terr)
        and (filtre_slugs is None or slug in filtre_slugs)
    ]
    return sorted(retenus, key=lambda s: (rang[etat[s].priorite], s))


__all__ = [
    "DATA_DIR",
    "FILE_ATTENTE",
    "PROSPECTION_DIR",
    "STATUTS",
    "Ingestion",
    "Priorite",
    "Statut",
    "Tache",
    "charger",
    "ecrire",
    "fusionner",
    "mettre_a_jour",
    "selectionner",
    "transition",
]
