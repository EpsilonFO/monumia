"""Vérification adversariale : un second modèle essaie de réfuter l'extraction.

C'est l'étape 4 du skill, et sa valeur tient entièrement à une propriété : le
vérificateur N'A PAS VU le raisonnement d'extraction. Il reçoit la source et le
YAML, rien d'autre — pas l'historique de la conversation, pas les hésitations,
pas les justifications. Un `complete` sans historique, donc, et jamais une
question posée au modèle qui vient d'écrire le fichier : il confirmerait ses
propres choix, ce qui ne coûte pas moins cher et ne prouve rien.

La consigne est extraite TELLE QUELLE du bloc de citation de l'étape 4 du
SKILL : c'est la même doctrine que celle appliquée à la main dans Claude Code.

Deux garde-fous encadrent le modèle :
  - l'audit des citations lui est fourni comme un FAIT ÉTABLI, calculé par
    recherche textuelle dans les snapshots. Lui demander de vérifier
    lui-même 34 citations mot à mot, c'est lui demander la seule chose qu'un
    LLM fait mal quand un `grep` la fait parfaitement ;
  - un vérificateur en panne rend un rapport « indisponible » MINEUR, jamais
    bloquant : une API qui tousse ne doit pas condamner une extraction correcte.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import providall
from lint_aides_data import check_quotes
from pipeline.llm import Compteur
from veille_collect import load_baselines

from aides_schema import Aide

from .atelier import Atelier
from .contexte import SKILL_PATH, condense_schema, section

MAX_CAR_PAR_DOC = 120_000

Axe = Literal[
    "condition_manquante",
    "condition_sans_fondement",
    "quote_inexacte",
    "valeur_divergente",
    "typage",
    "hard_filters_financement",
    "manual_check_gate",
    "dossier_demarche",
]

AXES: tuple[str, ...] = (
    "condition_manquante",
    "condition_sans_fondement",
    "quote_inexacte",
    "valeur_divergente",
    "typage",
    "hard_filters_financement",
    "manual_check_gate",
    "dossier_demarche",
)


class Probleme(BaseModel):
    axe: Axe = Field(description="Axe de réfutation concerné")
    severite: Literal["bloquant", "mineur"]
    condition_id: str | None = Field(
        default=None, description="id de la condition en cause, si le problème en vise une"
    )
    citation_source: str | None = Field(
        default=None, description="Passage EXACT de la source qui fonde le reproche"
    )
    description: str
    correction_proposee: str


class RapportVerification(BaseModel):
    problemes: list[Probleme] = []
    axes_sans_probleme: list[str] = Field(
        default=[], description="Axes explicitement contrôlés sans rien trouver"
    )
    qualite_source: Literal["reglement", "page_officielle", "vulgarisation"] = "page_officielle"
    commentaire: str = ""

    @property
    def bloquants(self) -> list[Probleme]:
        return [p for p in self.problemes if p.severite == "bloquant"]


def prompt_verificateur(skill_md: str) -> str:
    """La consigne de l'étape 4, extraite du bloc de citation du SKILL.

    Extraite et non recopiée : c'est le même texte que celui appliqué à la main,
    et il n'y a donc rien à resynchroniser le jour où il évolue.
    """
    etape = section(skill_md, "Étape 4")
    lignes = [
        re.sub(r"^>\s?", "", ligne)
        for ligne in etape.splitlines()
        if ligne.lstrip().startswith(">")
    ]
    if not lignes:
        raise KeyError("bloc de citation introuvable dans l'étape 4 du SKILL")
    return "\n".join(lignes).strip()


# ---------------------------------------------------------------------------
# Documents fournis au vérificateur
# ---------------------------------------------------------------------------


def _documents(atelier: Atelier, max_car: int) -> tuple[str, list[str]]:
    """Le texte des snapshots, tronqué, et la liste des PDF illisibles."""
    documents, illisibles, _provenance = load_baselines(atelier.slug)
    blocs: list[str] = []
    for nom, contenu, _kind in documents:
        corps = contenu[:max_car]
        coupe = "\n\n[… document tronqué ici]" if len(contenu) > max_car else ""
        blocs.append(f"### Snapshot `{nom}`\n\n```\n{corps}{coupe}\n```")
    return "\n\n".join(blocs), illisibles


def _audit_quotes(aide: Aide, atelier: Atelier) -> str:
    documents, illisibles, _ = load_baselines(atelier.slug)
    absentes, degradees, hors_portee = check_quotes(aide, documents, illisibles)
    if not documents:
        return (
            "AUDIT DES CITATIONS : aucun snapshot exploitable — aucune citation "
            "n'a pu être contrôlée automatiquement."
        )
    lignes = [
        "AUDIT DES CITATIONS (fait établi, calculé par recherche textuelle dans les",
        "snapshots — ne le recalcule pas, sers-t'en) :",
        f"  - retrouvées à l'identique : "
        f"{sum(1 for c in aide.conditions if c.quote) - len(absentes) - len(degradees) - len(hors_portee)}",
        f"  - retrouvées après normalisation typographique : {len(degradees)}",
        f"  - INTROUVABLES : {len(absentes)}",
    ]
    for _slug, cond_id, quote in absentes:
        lignes.append(f"      {cond_id} — « {' '.join(quote.split())[:120]} »")
    if hors_portee:
        lignes.append(
            f"  - non vérifiables (PDF illisible ou absent de l'archive) : {len(hors_portee)}"
        )
    return "\n".join(lignes)


# ---------------------------------------------------------------------------
# Appel
# ---------------------------------------------------------------------------


def construire_prompt(
    aide: Aide, atelier: Atelier, *, skill_md: str, max_car_par_doc: int = MAX_CAR_PAR_DOC
) -> str:
    corpus, illisibles = _documents(atelier, max_car_par_doc)
    avertissement = (
        "\n\nATTENTION : PDF non extractibles (scans), leur contenu n'est PAS ci-dessous : "
        + ", ".join(illisibles)
        + ". Ne reproche pas au YAML ce que tu ne peux pas lire."
        if illisibles
        else ""
    )
    return "\n\n".join(
        [
            prompt_verificateur(skill_md),
            "Tu n'as ni outil ni accès au système de fichiers : tout ce qu'il te faut "
            "est ci-dessous. Réponds UNIQUEMENT par le JSON demandé.",
            _audit_quotes(aide, atelier),
            condense_schema(),
            f"## Fichier extrait — {atelier.slug}.yaml\n\n```yaml\n"
            + atelier.yaml_path.read_text(encoding="utf-8").rstrip()
            + "\n```",
            "## Sources archivées" + avertissement + "\n\n" + (corpus or "(aucun snapshot)"),
        ]
    )


def verifier(
    atelier: Atelier,
    client_verif: providall.Client,
    *,
    aide: Aide,
    compteur: Compteur | None = None,
    max_car_par_doc: int = MAX_CAR_PAR_DOC,
    skill_path: Path = SKILL_PATH,
) -> tuple[RapportVerification, str]:
    """(rapport, rendu markdown). Ne lève jamais : une panne devient un rapport mineur."""
    skill_md = skill_path.read_text(encoding="utf-8")
    prompt = construire_prompt(aide, atelier, skill_md=skill_md, max_car_par_doc=max_car_par_doc)
    essai = client_verif.try_complete_json(RapportVerification, prompt)
    if compteur is not None:
        compteur.ajouter(essai.response, "verification")
    if essai.data is None:
        motif = essai.response.error
        rapport = RapportVerification(
            problemes=[
                Probleme(
                    axe="condition_sans_fondement",
                    severite="mineur",
                    description=f"Vérificateur indisponible : {motif}",
                    correction_proposee=(
                        "Relecture humaine indispensable : l'extraction n'a pas été réfutée."
                    ),
                )
            ],
            commentaire="vérificateur indisponible",
        )
        return rapport, rendre(rapport)
    return essai.data, rendre(essai.data)


def rendre(rapport: RapportVerification) -> str:
    """Le rapport tel que l'agent le lit — et tel qu'il ira dans la review."""
    if not rapport.problemes:
        lignes = ["## Vérification adversariale : aucun problème relevé."]
    else:
        bloquants = rapport.bloquants
        lignes = [
            f"## Vérification adversariale : {len(rapport.problemes)} problème(s), "
            f"dont {len(bloquants)} bloquant(s)",
            "",
            "Corrige les bloquants, puis relance `lint`. Si tu es en désaccord avec un",
            "reproche, garde ta version, re-cite la source et consigne l'arbitrage dans",
            "la review — le vérificateur n'a pas toujours raison.",
        ]
        for p in rapport.problemes:
            lignes.append("")
            cible = f" [{p.condition_id}]" if p.condition_id else ""
            lignes.append(f"- **{p.severite.upper()} / {p.axe}**{cible} — {p.description}")
            if p.citation_source:
                lignes.append(f"  Source : « {' '.join(p.citation_source.split())} »")
            lignes.append(f"  Correction proposée : {p.correction_proposee}")
    if rapport.axes_sans_probleme:
        lignes += [
            "",
            "Axes contrôlés sans rien trouver : " + ", ".join(rapport.axes_sans_probleme),
        ]
    lignes += ["", f"Qualité de la source retenue : {rapport.qualite_source}"]
    if rapport.commentaire:
        lignes.append(rapport.commentaire.strip())
    return "\n".join(lignes)


__all__ = [
    "AXES",
    "MAX_CAR_PAR_DOC",
    "Probleme",
    "RapportVerification",
    "construire_prompt",
    "prompt_verificateur",
    "rendre",
    "verifier",
]
