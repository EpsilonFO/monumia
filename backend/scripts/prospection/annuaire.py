"""Le site officiel d'un conseil départemental, depuis l'annuaire de l'État.

92 départements sur 101 n'ont aucun point d'entrée dans `territoires.yaml`, et
demander son site à un modèle pour chacun d'eux est le plus mauvais des moyens :
c'est précisément le genre de question où une réponse plausible et fausse
(`www.<departement>.fr` n'existe pas toujours) coûte un balayage entier dans le
vide.

L'annuaire de l'administration (`api-lannuaire.service-public.fr`, jeu de
données ouvert d'Opendatasoft) publie ces sites, tenus à jour par les
administrations elles-mêmes. C'est une source DÉTERMINISTE et gratuite : elle
passe avant tout modèle, qui ne sert plus que de repli.

Vérifié le 2026-09-06 : 569 enregistrements de type `cg` (conseil général /
départemental), chacun portant son `site_internet` et le code INSEE de sa
commune de siège — c'est ce code qui donne le numéro du département.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from pipeline.web import Fetcheur

API = "https://api-lannuaire.service-public.fr/api/explore/v2.1/catalog/datasets"
DATASET = "api-lannuaire-administration"
# Le jeu de données rend un enregistrement par service ; on ne veut que les
# conseils départementaux, identifiés par leur `type_service_local`.
REQUETE = (
    f"{API}/{DATASET}/records"
    "?where=search(nom%2C'conseil%20d%C3%A9partemental')"
    "&select=nom%2Csite_internet%2Cpivot"
    "&limit=100&offset={offset}"
)
MAX_PAGES = 8


@dataclass(frozen=True)
class SiteDepartemental:
    departement: str
    nom: str
    url: str


def _departement_de(code_insee: str) -> str | None:
    """Numéro de département depuis un code INSEE de commune.

    Deux chiffres, sauf outre-mer (trois) ; la Corse porte déjà ses lettres
    (`2A004` → `2A`), il n'y a donc rien à traiter à part.
    """
    code = (code_insee or "").strip().upper()
    if len(code) < 3:
        return None
    return code[:3] if code.startswith("97") else code[:2]


def _champ_json(valeur: object) -> list[dict]:
    """Les colonnes composites de l'annuaire arrivent en JSON DANS une chaîne."""
    if isinstance(valeur, list):
        return [v for v in valeur if isinstance(v, dict)]
    if isinstance(valeur, str) and valeur.strip():
        try:
            charge = json.loads(valeur)
        except ValueError:
            return []
        return [v for v in charge if isinstance(v, dict)] if isinstance(charge, list) else []
    return []


def sites_departementaux(fetcheur: Fetcheur) -> dict[str, SiteDepartemental]:
    """{numéro de département : site officiel}. Dictionnaire vide si l'API est muette."""
    trouves: dict[str, SiteDepartemental] = {}
    for page in range(MAX_PAGES):
        reponse = fetcheur.get(REQUETE.format(offset=page * 100))
        if not reponse.ok:
            break
        try:
            charge = json.loads(reponse.texte)
        except ValueError:
            break
        resultats = charge.get("results") or []
        if not resultats:
            break
        for enregistrement in resultats:
            pivots = _champ_json(enregistrement.get("pivot"))
            if not any(p.get("type_service_local") == "cg" for p in pivots):
                continue
            codes = [c for p in pivots for c in (p.get("code_insee_commune") or [])]
            numero = next((d for c in codes if (d := _departement_de(c))), None)
            sites = _champ_json(enregistrement.get("site_internet"))
            url = next((s.get("valeur", "") for s in sites if s.get("valeur")), "")
            if numero and url and numero not in trouves:
                trouves[numero] = SiteDepartemental(
                    departement=numero, nom=enregistrement.get("nom", ""), url=url
                )
    return trouves


__all__ = ["MAX_PAGES", "REQUETE", "SiteDepartemental", "sites_departementaux"]
