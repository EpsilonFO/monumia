"""Étage 2 : trier au kilo, sans ouvrir les pages.

Une région rend deux à trois cents URL de dispositifs, dont dix à vingt
intéressent un propriétaire de monument. Les ouvrir toutes coûterait autant que
l'ingestion elle-même : on trie d'abord sur le titre et l'extrait, par lots, et
on n'ouvre (étage 3) que les retenues et les douteuses.

La doctrine du tri n'est pas écrite ici : elle est EXTRAITE du skill
`prospecter-aides-region` (les étapes « Le spectre » et « Le test
d'admission »), comme le prompt d'ingestion l'est du sien. Une seule source de
vérité pour ce qu'on retient et ce qu'on écarte.

Trois précautions, toutes apprises du même travers des modèles en lot :
  - une URL absente de la réponse devient `douteux`, jamais `ecarter` — un
    oubli ne doit pas se lire comme un refus ;
  - une URL inventée est ignorée ;
  - un lot en échec passe en entier en `douteux`, et l'étage 3 tranchera.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import providall
from pipeline.llm import Compteur

from aides_schema import Aide

from .collecte import Candidat
from .territoires import Territoire

TAILLE_LOT = 25

Famille = Literal[
    "restauration_bati",
    "tourisme_hebergement",
    "spectacles_manifestations",
    "parcs_jardins_paysages",
    "mediation_numerique_expositions",
    "accessibilite_publics",
    "etudes_ingenierie",
    "labels_passerelles",
    "adjacente",
    "hors_perimetre",
]

FAMILLES: tuple[str, ...] = (
    "restauration_bati",
    "tourisme_hebergement",
    "spectacles_manifestations",
    "parcs_jardins_paysages",
    "mediation_numerique_expositions",
    "accessibilite_publics",
    "etudes_ingenierie",
    "labels_passerelles",
    "adjacente",
    "hors_perimetre",
)

Decision = Literal["retenir", "ecarter", "douteux"]

SKILL_PROSPECTION = (
    Path(__file__).resolve().parent.parent.parent.parent
    / ".claude"
    / "skills"
    / "prospecter-aides-region"
    / "SKILL.md"
)


class TriCandidat(BaseModel):
    url: str
    decision: Decision
    famille: Famille = "hors_perimetre"
    motif: str = Field(default="", description="Une phrase : pourquoi cette décision")


class Lot(BaseModel):
    resultats: list[TriCandidat] = []


def doctrine(skill_path: Path = SKILL_PROSPECTION) -> str:
    """Le spectre et le test d'admission, extraits du skill de prospection."""
    from ingestion.contexte import section

    md = skill_path.read_text(encoding="utf-8")
    return "\n\n".join(
        [
            section(md, "Étape 2").rstrip(),
            section(md, "Étape 3").rstrip(),
        ]
    )


def prompt_systeme(
    territoire: Territoire, existantes: dict[str, Aide], skill_path: Path = SKILL_PROSPECTION
) -> str:
    """Doctrine du skill + ce que le catalogue contient DÉJÀ pour ce territoire.

    La liste des aides déjà ingérées n'est pas décorative : sans elle, le modèle
    retient consciencieusement des dispositifs que la fiche re-proposera et que
    l'humain devra écarter un par un.
    """
    deja = (
        "\n".join(f"  {slug} — {aide.nom}" for slug, aide in sorted(existantes.items()))
        or "  (aucune)"
    )
    return "\n\n".join(
        [
            doctrine(skill_path),
            "---",
            f"# Territoire prospecté : {territoire.nom}",
            "Aides DÉJÀ présentes dans le catalogue pour ce territoire — les écarter\n"
            "si tu les reconnais (`decision: ecarter`, motif « déjà au catalogue ») :\n" + deja,
            "# Ta tâche\n\n"
            "Pour CHAQUE URL de la liste qui suit, rends une décision. Tu ne vois que\n"
            "le titre du lien et sa ligne de contexte : quand cela ne suffit pas pour\n"
            "trancher, réponds `douteux` — la page sera ouverte et relue à l'étape\n"
            "suivante. `douteux` est une réponse normale et peu coûteuse ; `ecarter`\n"
            "à tort fait perdre une aide définitivement.\n\n"
            "Rends une entrée par URL, avec l'URL RECOPIÉE À L'IDENTIQUE.",
        ]
    )


def lots(candidats: list[Candidat], taille: int = TAILLE_LOT) -> Iterator[list[Candidat]]:
    for debut in range(0, len(candidats), taille):
        yield candidats[debut : debut + taille]


def _rendre_lot(lot: list[Candidat]) -> str:
    return "\n\n".join(
        f"URL : {c.url}\nTitre : {c.titre or '(sans titre)'}\nContexte : {c.extrait or '(aucun)'}"
        for c in lot
    )


def trier_lot(
    lot: list[Candidat],
    client: providall.Client,
    systeme: str,
    *,
    compteur: Compteur | None = None,
) -> list[TriCandidat]:
    """Trie un lot. Ne lève jamais : en cas d'échec, tout le lot devient douteux."""
    essai = client.try_complete_json(Lot, _rendre_lot(lot), system=systeme)
    if compteur is not None:
        compteur.ajouter(essai.response, "tri")
    connues = {c.url for c in lot}
    if essai.data is None:
        return [
            TriCandidat(url=c.url, decision="douteux", motif="lot non trié (modèle indisponible)")
            for c in lot
        ]
    # Les URL inventées sont jetées, les oubliées deviennent douteuses : dans
    # les deux cas le tri ne peut que retarder une décision, jamais en prendre
    # une que le modèle n'a pas prise.
    par_url = {r.url: r for r in essai.data.resultats if r.url in connues}
    return [
        par_url.get(
            c.url,
            TriCandidat(url=c.url, decision="douteux", motif="absente de la réponse du modèle"),
        )
        for c in lot
    ]


def trier(
    candidats: list[Candidat],
    territoire: Territoire,
    existantes: dict[str, Aide],
    client: providall.Client,
    *,
    compteur: Compteur | None = None,
    taille_lot: int = TAILLE_LOT,
    skill_path: Path = SKILL_PROSPECTION,
    progression: Callable[[int, int, list[TriCandidat]], None] | None = None,
) -> list[TriCandidat]:
    """Trie tous les lots. `progression(i, n, tries_du_lot)` est appelé après chacun.

    Dix appels séquentiels de 30 à 40 s sans un mot : le 2026-09-08, un
    balayage de 239 candidats a paru bloqué pendant vingt minutes alors qu'il
    avançait normalement. Le rappel sert à le dire.
    """
    systeme = prompt_systeme(territoire, existantes, skill_path)
    resultats: list[TriCandidat] = []
    tous = list(lots(candidats, taille_lot))
    for i, lot in enumerate(tous, 1):
        tries = trier_lot(lot, client, systeme, compteur=compteur)
        resultats += tries
        if progression is not None:
            progression(i, len(tous), tries)
    return resultats


def a_lire(tries: list[TriCandidat]) -> list[str]:
    """Les URL que l'étage 3 doit ouvrir : retenues et douteuses."""
    return [t.url for t in tries if t.decision in ("retenir", "douteux")]


__all__ = [
    "FAMILLES",
    "SKILL_PROSPECTION",
    "TAILLE_LOT",
    "Decision",
    "Famille",
    "Lot",
    "TriCandidat",
    "a_lire",
    "doctrine",
    "lots",
    "prompt_systeme",
    "trier",
    "trier_lot",
]
