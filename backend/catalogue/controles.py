"""Contrôles de code d'une retouche de veille, avant toute écriture (section 6.3 d'`architecture.md`).

- `C-valeur-litterale` : une date ou un nombre retouché doit figurer tel quel
  dans les pages fraîches. Au passage du 2026-10-04, 7 des 27 valeurs
  vérifiables ne s'y trouvaient pas : 5 dates dont le modèle avait déduit
  l'année, 2 calculées d'après une règle récurrente. Une valeur déduite, même
  juste, va à Félix. Booléens et textes libres ne se vérifient pas ainsi.
- `C-residus` : l'ancienne valeur reste-t-elle écrite ailleurs dans l'aide
  (démarche, conditions, bloc `fiche:`) ? Le 2026-10-04, l'ancienne valeur
  restait écrite dans 10 des 24 aides retouchées. La veille n'a pas mandat pour
  ces champs : la retouche s'écrit, et le résidu devient une case.
- `C-surcharges` : sans export de la surcouche admin, aucune retouche du `text`
  ni du `predicate` d'une condition (`conditions_predicats` et les réponses de
  `faits_surcharges` vivent en production) ; la proposition devient une case.

Les formes de dates et de nombres sont celles de la mesure du 2026-10-10
(`scripts/mesures/veille.py`), qui a produit le chiffre ci-dessus.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from typing import Any

from catalogue.veille_apply import VeilleLLMOutput

MOIS = (
    "janvier",
    "fevrier",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "aout",
    "septembre",
    "octobre",
    "novembre",
    "decembre",
)
SECTIONS = ("calendrier", "financement", "cumul")
CHAMPS_CONDITION_PROTEGES = ("text", "predicate")


def sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFKD", texte.lower())
    return "".join(c for c in decompose if not unicodedata.combining(c))


def formes_date(d: dt.date) -> list[str]:
    """Les écritures d'une date AVEC son année : sans elle, l'année serait déduite."""
    jour = "1er" if d.day == 1 else str(d.day)
    return [
        f"{jour} {MOIS[d.month - 1]} {d.year}",
        f"{d.day} {MOIS[d.month - 1]} {d.year}",
        f"{d.day:02d}/{d.month:02d}/{d.year}",
        f"{d.day}/{d.month}/{d.year}",
        f"{d.day:02d}.{d.month:02d}.{d.year}",
        d.isoformat(),
    ]


def formes_nombre(x: float) -> list[str]:
    if float(x).is_integer():
        n = int(x)
        return [f"{n:,}".replace(",", " "), str(n), f"{n:,}".replace(",", ".")]
    return [str(x), str(x).replace(".", ",")]


def _date(valeur: Any) -> dt.date | None:
    if isinstance(valeur, dt.date):
        return valeur
    if isinstance(valeur, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", valeur):
        try:
            return dt.date.fromisoformat(valeur)
        except ValueError:
            return None
    return None


def figure(valeur: Any, texte: str) -> bool | None:
    """La valeur est-elle écrite telle quelle dans `texte` (déjà sans accents) ? `None` : invérifiable."""
    if isinstance(valeur, bool) or valeur is None:
        return None
    if (d := _date(valeur)) is not None:
        return any(f in texte for f in formes_date(d))
    if isinstance(valeur, int | float):
        return any(
            re.search(rf"(?<![\d]){re.escape(f)}(?![\d])", texte) for f in formes_nombre(valeur)
        )
    return None


def valeurs_retouchees(out: VeilleLLMOutput) -> list[tuple[str, Any]]:
    """(chemin, valeur) des champs de section que la proposition change."""
    valeurs: list[tuple[str, Any]] = []
    for nom in SECTIONS:
        section = getattr(out, nom)
        if section is None:
            continue
        for cle_champ, valeur in section.champs.items():
            valeurs.append((f"{nom}.{cle_champ}", valeur))
    return valeurs


def valeurs_deduites(out: VeilleLLMOutput, documents: list[tuple[str, str, str]]) -> list[str]:
    """Les champs retouchés dont la date ou le nombre ne figure pas dans les pages fraîches."""
    texte = sans_accents("\n".join(contenu for _, contenu, _ in documents))
    return [
        f"{chemin} = {valeur}"
        for chemin, valeur in valeurs_retouchees(out)
        if figure(valeur, texte) is False
    ]


def conditions_protegees(out: VeilleLLMOutput) -> list[str]:
    """Les retouches de `text` ou de `predicate` d'une condition existante."""
    touchees: list[str] = []
    for chg in out.conditions:
        if chg.op == "update" and chg.champs:
            for champ in CHAMPS_CONDITION_PROTEGES:
                if champ in chg.champs:
                    touchees.append(f"{chg.id}.{champ}")
    return touchees


def notes_non_ancrees(out: VeilleLLMOutput) -> list[str]:
    """Les notes de condition réécrites sans citation.

    `veille_apply` n'ancre une retouche de condition que par sa `quote` : une
    note réécrite seule n'est jamais confrontée au diff. Au rejeu du
    2026-10-11, c'est la seule fausse retouche (`prix-sesame-fondation-patrimoine`,
    une note qui commentait le nombre de lauréats), déjà vue au banc du
    2026-10-05.
    """
    return [
        f"{chg.id}.notes"
        for chg in out.conditions
        if chg.op == "update" and chg.champs and "notes" in chg.champs and "quote" not in chg.champs
    ]


def residus(ancien: dict[str, Any], out: VeilleLLMOutput, texte_yaml: str) -> list[str]:
    """Anciennes dates et anciens nombres retouchés qui restent écrits ailleurs dans l'aide.

    `texte_yaml` est le YAML APRÈS retouche : les sections retouchées y portent
    la valeur neuve, donc une ancienne valeur encore présente est ailleurs
    (démarche, texte d'une condition, bloc `fiche:`).
    """
    texte = sans_accents(texte_yaml)
    trouves: list[str] = []
    for chemin, nouvelle in valeurs_retouchees(out):
        section, _, champ = chemin.partition(".")
        vieille = (ancien.get(section) or {}).get(champ)
        if vieille is None or vieille == nouvelle or isinstance(vieille, bool):
            continue
        if (d := _date(vieille)) is not None:
            formes = formes_date(d)
        elif isinstance(vieille, int | float):
            formes = formes_nombre(vieille)
        else:
            continue
        if any(re.search(rf"(?<![\d]){re.escape(f)}(?![\d])", texte) for f in formes):
            trouves.append(f"{chemin} : l'ancienne valeur {vieille} reste écrite dans l'aide")
    return trouves
