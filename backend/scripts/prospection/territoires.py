"""Les recettes de balayage, une par territoire — `data/prospection/territoires.yaml`.

Chaque guide des aides régional est un site différent, et la seule chose qui
marche vraiment est de le savoir : où est la liste, comment on la pagine, à
quoi ressemble l'URL d'une fiche, et si le domaine exige une identité de
navigateur. Ces recettes se gagnent en ouvrant le site une fois, et se perdent
si personne ne les écrit — c'est ce fichier qui les garde.

Quatre stratégies, de la moins chère à la plus chère :

  - `liste_html`  : la liste complète est déjà dans le HTML d'une page (HDF)
  - `sitemap`     : un sitemap énumère les fiches (Grand Est, 245 fiches)
  - `pagination`  : n pages de résultats à parcourir (Normandie, Occitanie)
  - `decouverte`  : on ne sait pas — un appel LLM cherche la rubrique, puis un
                    parcours borné suit les liens (seul cas qui coûte un modèle)

Le `statut` dit ce qu'on sait de la recette : `pret` (vérifiée sur le site),
`a_verifier` (dérivée d'une fiche de prospection, jamais rejouée par le script),
`decouverte`, `sans_point_entree` (aucune URL fiable — on ne fabrique pas une
URL, on la cherche).
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from aides_schema import DATA_DIR, Aide
from labels import DEPARTEMENT_LABELS, REGION_LABELS

TERRITOIRES_FILE = DATA_DIR / "prospection" / "territoires.yaml"

TypeTerritoire = Literal["region", "departement", "epci"]
Statut = Literal["pret", "a_verifier", "decouverte", "sans_point_entree"]


class Strategie(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["liste_html", "sitemap", "pagination", "decouverte"]
    # sitemap : une URL, ou plusieurs — un site range volontiers ses appels à
    # projets dans un sitemap distinct de son guide (Grand Est : `ge_guide` et
    # `ge_projet`, et le second portait 13 dispositifs que personne ne voyait).
    url: str | list[str] | None = None
    # pagination : patron d'URL contenant {n}, et les bornes du compteur
    patron: str | None = None
    de: int = 0
    a: int = 20
    pas: int = 1
    # decouverte
    max_pages: int = 120
    profondeur: int = 2
    # Toutes stratégies : ce que le balayage peut au plus rendre. Le tri et la
    # lecture n'ont AUCUN plafond propre — celui-ci les borne tous les deux. Un
    # guide régional rend 200 à 300 fiches ; 800 laisse la marge d'un gros
    # département sans laisser passer les 24 185 candidates de la Moselle.
    max_candidats: int = 800

    @property
    def urls_sitemap(self) -> list[str]:
        """Les sitemaps à lire, qu'`url` porte une chaîne ou une liste."""
        if not self.url:
            return []
        return [self.url] if isinstance(self.url, str) else list(self.url)

    @model_validator(mode="after")
    def _coherence(self) -> Strategie:
        if self.type == "sitemap" and not self.urls_sitemap:
            raise ValueError("une stratégie sitemap exige `url` (une chaîne ou une liste non vide)")
        if self.type == "pagination":
            if not self.patron:
                raise ValueError("une stratégie pagination exige `patron`")
            if "{n}" not in self.patron:
                raise ValueError("le patron de pagination doit contenir « {n} »")
            if self.pas < 1 or self.a < self.de:
                raise ValueError("bornes de pagination incohérentes")
        if self.max_candidats < 1:
            raise ValueError("max_candidats doit être strictement positif")
        return self


class Territoire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nom: str
    type: TypeTerritoire
    # Région d'appartenance d'un département — sert au regroupement des runs.
    region: str | None = None
    # Les départements que ce territoire couvre RÉELLEMENT, quand ils ne se
    # déduisent pas de sa clé. La Collectivité européenne d'Alsace instruit pour
    # le 67 et le 68 : sans ce champ, `territoires.yaml` donnait le même guide
    # aux deux clés et 17 dispositifs sont entrés deux fois au catalogue, sous
    # `67-*` ET sous `68-*`. Dicté au modèle pour qu'il écrive
    # `hard_filters.departements: ['67', '68']` sur un seul fichier.
    departements: list[str] = []
    # Préfixe imposé aux slugs proposés (`hdf`, `71`…).
    prefixe_slug: str
    statut: Statut = "sans_point_entree"
    guides: list[str] = []
    strategie: Strategie = Strategie(type="decouverte")
    # Ce à quoi ressemble l'URL d'une fiche : c'est ce motif qui distingue un
    # dispositif d'une page de navigation, et il fait tout le tri de l'étage 1.
    motif_fiche: str | None = None
    motif_pdf: str | None = None
    exclure: list[str] = []
    entetes: Literal["standard", "navigateur"] = "standard"
    notes: str | None = None

    @model_validator(mode="after")
    def _coherence(self) -> Territoire:
        if self.statut == "sans_point_entree":
            if self.guides:
                raise ValueError("un territoire `sans_point_entree` ne peut pas avoir de guide")
        elif not self.guides:
            raise ValueError(
                f"statut « {self.statut} » sans aucun guide — mettre sans_point_entree"
            )
        for motif in (self.motif_fiche, self.motif_pdf, *self.exclure):
            if motif:
                try:
                    re.compile(motif)
                except re.error as exc:
                    raise ValueError(f"expression régulière invalide « {motif} » : {exc}") from exc
        inconnus = [d for d in self.departements if d not in DEPARTEMENT_LABELS]
        if inconnus:
            raise ValueError(f"code(s) de département inconnu(s) : {', '.join(inconnus)}")
        return self

    def codes_departements(self, cle: str) -> list[str]:
        """Les départements couverts : ceux déclarés, sinon la clé si c'en est un.

        C'est ce que l'ingestion doit écrire en `hard_filters.departements`. La
        clé seule ne suffit pas — une collectivité peut instruire pour deux
        départements, et c'est exactement le cas qui a produit 17 doublons.
        """
        if self.departements:
            return list(self.departements)
        return [cle] if self.type == "departement" else []

    def fiche_probable(self, url: str) -> bool:
        """L'URL a-t-elle la forme d'une fiche de dispositif ?"""
        if any(re.search(m, url) for m in self.exclure):
            return False
        return bool(re.search(self.motif_fiche, url)) if self.motif_fiche else True

    def pdf_probable(self, url: str) -> bool:
        if self.motif_pdf and re.search(self.motif_pdf, url):
            return True
        return url.lower().split("?")[0].endswith(".pdf")

    def pages_paginees(self) -> list[str]:
        s = self.strategie
        if s.type != "pagination" or not s.patron:
            return []
        return [s.patron.replace("{n}", str(n)) for n in range(s.de, s.a + 1, s.pas)]


def charger_territoires(chemin: Path = TERRITOIRES_FILE) -> dict[str, Territoire]:
    """Charge et valide le fichier de recettes, clé comprise.

    La cohérence clé ↔ contenu est vérifiée ICI et non dans le modèle : un
    `Territoire` ne connaît pas sa propre clé, et c'est pourtant elle qui sert
    de préfixe de slug pour un département (`71-plan-numerique`).
    """
    if not chemin.exists():
        return {}
    brut = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    territoires: dict[str, Territoire] = {}
    for cle, valeur in brut.items():
        cle = str(cle)
        try:
            territoire = Territoire.model_validate(valeur)
        except Exception as exc:
            raise ValueError(f"territoire « {cle} » invalide : {exc}") from exc
        if territoire.type == "departement":
            if cle not in DEPARTEMENT_LABELS:
                raise ValueError(f"« {cle} » n'est pas un code de département connu")
            if territoire.prefixe_slug != cle:
                raise ValueError(
                    f"département « {cle} » : le préfixe de slug doit être son numéro, "
                    f"reçu « {territoire.prefixe_slug} »"
                )
        elif territoire.type == "region" and cle not in REGION_LABELS:
            raise ValueError(f"« {cle} » n'est pas un code de région connu")
        territoires[cle] = territoire
    return territoires


def selectionner(
    territoires: dict[str, Territoire],
    cles: Sequence[str] = (),
    *,
    regions: bool = False,
    departements: bool = False,
    statuts: Iterable[str] | None = None,
    forcer: bool = False,
) -> list[str]:
    """Les territoires à balayer, dans l'ordre du fichier.

    `sans_point_entree` est exclu par défaut, `--forcer` mis à part : lancer un
    balayage sur un territoire dont on n'a pas d'URL ne produit rien, mais
    remplit la fiche de bruit et coûte un appel de découverte.
    """
    voulus = set(statuts) if statuts else None
    retenus = []
    for cle, t in territoires.items():
        if cles and cle not in cles:
            continue
        if (
            not cles
            and not (regions and t.type == "region")
            and not (departements and t.type == "departement")
        ):
            continue
        if voulus is not None and t.statut not in voulus:
            continue
        if t.statut == "sans_point_entree" and not forcer:
            continue
        retenus.append(cle)
    return retenus


def aides_existantes(cle: str, territoire: Territoire, aides: dict[str, Aide]) -> dict[str, Aide]:
    """Les aides du catalogue qui couvrent déjà ce territoire.

    Deux voies, cumulées : le préfixe de slug (convention du corpus) et les
    `hard_filters` géographiques (la vérité déclarée). Ni l'une ni l'autre n'est
    suffisante seule — `region-grand-est-classe` n'a pas le préfixe `ge-`, et
    une aide toute neuve peut n'avoir pas encore ses filtres.

    Les codes cherchés sont TOUS ceux que le territoire couvre : le guide de la
    Collectivité européenne d'Alsace est celui du 67 comme du 68, et ne
    chercher que sous `68` faisait re-proposer les 17 dispositifs déjà ingérés
    sous `67-*`.
    """
    dimension = "departements" if territoire.type == "departement" else "regions"
    codes = set(territoire.codes_departements(cle)) if dimension == "departements" else {cle}
    codes.add(cle)
    retenues = {}
    for slug, aide in aides.items():
        filtres = set(getattr(aide.hard_filters, dimension))
        if slug.startswith(f"{territoire.prefixe_slug}-") or codes & filtres:
            retenues[slug] = aide
    return retenues


__all__ = [
    "TERRITOIRES_FILE",
    "Statut",
    "Strategie",
    "Territoire",
    "TypeTerritoire",
    "aides_existantes",
    "charger_territoires",
    "selectionner",
]
