"""Le catalogue en chiffres : combien d'aides, et lesquelles, sur quel territoire.

Lecture seule, pour la page d'administration `/admin/statistiques`. Cinq
décisions portent tout le module :

- **Un seul chiffre par ligne, et la liste des noms derrière.** La page répond
  à « combien d'aides pour la Bretagne ? », puis « lesquelles ? » quand on
  déplie. Tout le reste (financeur, typage, guichet) se lit ailleurs dans
  `/admin` : le répéter ici faisait treize colonnes que personne ne lisait.

- **Le corpus compté est celui qui est SERVI**, `catalogue_effectif` — YAML
  moins les aides retirées. Une page qui compterait des aides qu'aucun
  diagnostic ne propose mentirait sur la couverture réelle. Les retirées ne
  sont donc listées nulle part ; seul le total du corpus dit combien il y en a.

- **Les lignes classent par FINANCEUR, pas par périmètre.** « Les aides du
  département de l'Isère » veut dire « celles que le Conseil départemental de
  l'Isère finance » — pas « celles qui s'appliquent en Isère », qui sont aussi
  celles de la Région et de l'État. Un dispositif régional limité à trois
  départements reste une aide de la RÉGION, et la délégation Rhône-Alpes d'une
  fondation reste une aide de FONDATION. C'est `categorie` qui tranche, et
  `hard_filters` ne sert plus qu'à savoir sur quelle ligne l'accrocher.

- **Quatre échelons DISJOINTS**, ce qui rend les chiffres de tête
  additionnables : Conseil régional, Conseil départemental, périmètre national
  (État, fiscalité, fondations nationales), et tout le reste — les financeurs
  qui n'ont pas d'échelon territorial mais un périmètre local (fondations,
  Europe, mécénat). Une aide tombe dans exactement un seau, et les quatre
  somment au corpus servi. Le quatrième n'est pas une poubelle : sans lui, une
  aide de fondation ouverte à huit départements serait soit invisible, soit
  comptée comme une aide du Département, ce qu'elle n'est pas.

- **Le périmètre sert encore à deux choses** : accrocher une aide régionale à
  sa région même quand elle n'énumère que des départements, et écrire en clair
  sur quel territoire elle porte. `Entree.portee` neutralise pour cela
  l'énumération redondante — beaucoup d'aides régionales listent en plus les
  douze départements de leur région (convention de la colonne
  `aides_v3.departements`), et les lire comme départementales rattacherait un
  appel à projets de Région à douze lignes de département.

- **Rien n'est sommé sur l'argent.** Un « total des plafonds » n'existe pas :
  les aides ne s'additionnent pas, elles se cumulent sous plafond public. Le
  dépliant publie des bornes et une médiane, jamais une enveloppe.

Le compte des aides absentes d'`aides_v3` est la seule lecture de la base
métier : une aide présente en YAML mais absente de la table répond « Aide
introuvable » à la création de dossier (cf. l'étape de sync de `deploy.sh`), et
c'est précisément le genre de panne qu'une page d'exploitation doit montrer.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import median
from typing import Literal

from aides_schema import CATEGORIES, TYPES, Aide, load_all_aides
from labels import (
    DEPARTEMENT_LABELS,
    DEPARTEMENT_REGION,
    REGION_DEPARTEMENTS,
    REGION_LABELS,
)
from services.catalogue_admin import catalogue_effectif

#: Nom lisible des catégories et des types, pour éviter au front de tenir un
#: second dictionnaire : la page n'affiche que ce que le serveur lui donne.
CATEGORIE_LABELS = {
    "etat_drac": "État (DRAC)",
    "region": "Région",
    "departement": "Département",
    "fondation": "Fondation",
    "europe": "Europe",
    "mecenat": "Mécénat",
    "fiscalite": "Fiscalité",
    "autre": "Autre",
}

TYPE_LABELS = {
    "subvention": "Subvention",
    "appel_a_projets": "Appel à projets",
    "pret": "Prêt",
    "deduction_fiscale": "Déduction fiscale",
    "exoneration": "Exonération",
    "label": "Label",
    "mecenat": "Mécénat",
    "souscription": "Souscription publique",
}

#: Périmètre d'une aide. « departement » veut dire « périmètre d'un ou quelques
#: départements nommés » — pas « aide du Conseil départemental », qui se lit
#: sur `categorie` et n'est pas la même question (la délégation régionale d'une
#: fondation a un périmètre départemental sans qu'un euro vienne du Département).
Portee = Literal["nationale", "region", "departement"]

#: Qui finance, et à quel étage. C'est l'axe des tableaux — pas `Portee`.
#: « autre » = un financeur sans échelon territorial (fondation, Europe,
#: mécénat) dont l'aide ne vaut pourtant pas partout.
Echelon = Literal["national", "region", "departement", "autre"]

#: Au-delà, la liste des slugs désynchronisés n'est plus une liste mais un
#: symptôme : on donne le compte et les premiers, le reste tient dans les logs
#: du loader.
MANQUANTES_MAX = 25


def _departements_de(regions: Iterable[str]) -> set[str]:
    """Tous les départements des régions citées. Une région inconnue (que le
    validateur du schéma interdit déjà) n'apporte rien plutôt que de faire
    échouer le calcul."""
    return {code for region in regions for code in REGION_DEPARTEMENTS.get(region, ())}


@dataclass(frozen=True)
class Entree:
    """Une aide du corpus, et si elle a été retirée du catalogue."""

    aide: Aide
    retiree: bool

    @property
    def portee(self) -> Portee:
        """Le périmètre réel, une fois l'énumération redondante neutralisée.

        Une aide qui déclare sa région ET tous les départements de cette région
        reste RÉGIONALE : la liste ne retire rien, elle sert au filtrage en
        base. C'est le cas de la plupart des dispositifs régionaux du corpus —
        les lire comme départementaux affichait « 0 régionale » sur
        Auvergne-Rhône-Alpes, et faisait passer dix appels à projets de la
        Région pour des aides de Conseil départemental.

        Une énumération STRICTEMENT plus étroite, elle, restreint pour de bon
        (huit départements sur douze pour une délégation de fondation) : la
        portée est départementale, et l'aide n'apparaît que sur ces
        départements-là.
        """
        filtres = self.aide.hard_filters
        if not filtres.departements:
            return "region" if filtres.regions else "nationale"
        if filtres.regions and set(filtres.departements) >= _departements_de(filtres.regions):
            return "region"
        return "departement"

    @property
    def echelon(self) -> Echelon:
        """Qui finance, et à quel étage — l'axe des tableaux.

        `categorie` tranche en premier, et c'est tout le point : « les aides du
        département de l'Isère » veut dire celles du Conseil départemental, pas
        celles qui s'appliquent en Isère. Un dispositif régional limité à trois
        départements reste une aide de la Région.

        Le territoire n'intervient qu'en garde-fou : une aide de collectivité
        sans territoire où l'accrocher n'aurait aucune ligne pour l'afficher,
        et disparaîtrait de la page. Elle retombe alors sur son périmètre, où
        elle reste visible.
        """
        categorie = self.aide.categorie
        if categorie == "region" and self.regions:
            return "region"
        if categorie == "departement" and self.aide.hard_filters.departements:
            return "departement"
        return "national" if self.portee == "nationale" else "autre"

    @property
    def regions(self) -> set[str]:
        """Les régions que l'aide touche, ses départements compris.

        Un département hors table (code inconnu, que le validateur du schéma
        interdit déjà) est ignoré plutôt que rattaché à une région arbitraire.
        """
        filtres = self.aide.hard_filters
        depuis_departements = {
            DEPARTEMENT_REGION[code] for code in filtres.departements if code in DEPARTEMENT_REGION
        }
        return set(filtres.regions) | depuis_departements


def _nombres(valeurs: Iterable[float | None]) -> list[float]:
    return [v for v in valeurs if v is not None]


def _taux(aide: Aide) -> float | None:
    """Le taux qui représente l'aide : son maximum, sinon son minimum.

    Beaucoup de dispositifs n'annoncent qu'une borne ; retenir le plafond
    quand il existe donne la même lecture partout — « jusqu'à combien ».
    """
    fin = aide.financement
    return fin.taux_max if fin.taux_max is not None else fin.taux_min


def _groupe(entrees: Iterable[Entree]) -> dict:
    """Un groupe d'aides : son compte, ses slugs, et son chiffrage.

    Les aides RETIRÉES en sortent entièrement — elles ne sont plus servies, et
    les garder dans les taux gonflerait des chiffres que plus personne ne voit.
    Le total du corpus dit à lui seul combien il y en a.

    Les slugs sont triés par NOM et non par slug : c'est l'ordre dans lequel le
    dépliant les affiche, et le front n'a pas à retrier une liste que le
    serveur connaît déjà.
    """
    servies = sorted((e.aide for e in entrees if not e.retiree), key=lambda a: a.nom)

    taux = _nombres(_taux(a) for a in servies)
    taux_min = _nombres(
        a.financement.taux_min if a.financement.taux_min is not None else _taux(a) for a in servies
    )
    montants = _nombres(a.financement.montant_max for a in servies)

    return {
        "nb": len(servies),
        "slugs": [a.slug for a in servies],
        "nbAvecTaux": len(taux),
        "tauxMin": min(taux_min) if taux_min else None,
        "tauxMax": max(taux) if taux else None,
        "tauxMedian": median(taux) if taux else None,
        "nbAvecMontant": len(montants),
        "montantMedian": median(montants) if montants else None,
        "montantMax": max(montants) if montants else None,
    }


def _slugs_en_base(supabase) -> set[str] | None:
    """Les slugs présents dans `aides_v3`, ou `None` si la table est illisible.

    Même principe que la surcouche : une lecture qui échoue ne fait pas tomber
    la page, elle retire le bloc. Distinguer « illisible » de « vide » compte —
    annoncer 211 aides manquantes parce que la base n'a pas répondu ferait
    chercher une panne qui n'existe pas.
    """
    try:
        res = supabase.table("aides_v3").select("slug").execute()
    except Exception:
        return None
    lignes = (res.data if res else None) or []
    return {ligne["slug"] for ligne in lignes if isinstance(ligne.get("slug"), str)}


def _synchronisation(supabase, servies: Iterable[str]) -> dict:
    """L'écart entre le corpus servi et `aides_v3`.

    Une aide absente de la table répond « Aide introuvable » à la création de
    dossier : le diagnostic la propose, le bouton échoue. C'est le seul point
    où le YAML et la base doivent être d'accord, et le seul qu'on surveille.
    """
    en_base = _slugs_en_base(supabase)
    if en_base is None:
        return {"lisible": False, "enBase": None, "nbManquantes": 0, "manquantes": []}
    manquantes = sorted(set(servies) - en_base)
    return {
        "lisible": True,
        "enBase": len(en_base),
        "nbManquantes": len(manquantes),
        "manquantes": manquantes[:MANQUANTES_MAX],
    }


def statistiques_catalogue(supabase) -> dict:
    """Le catalogue servi, agrégé : corpus, territoires, nature, synchronisation.

    Tout est recalculé à chaque appel, sur le catalogue en cache : le balayage
    de deux cents aides ne justifie pas un second cache, qui aurait sa propre
    date de péremption à expliquer.
    """
    catalogue = catalogue_effectif(supabase)
    toutes = load_all_aides()
    servies = catalogue.aides

    entrees = [
        # La version SERVIE quand elle existe (surcharges de prédicats
        # appliquées) ; le YAML brut pour une retirée, qui n'y est plus.
        Entree(aide=servies.get(slug, aide), retiree=slug in catalogue.retirees)
        for slug, aide in sorted(toutes.items())
    ]
    debout = [e for e in entrees if not e.retiree]

    national = _groupe(e for e in entrees if e.echelon == "national")
    autres = _groupe(e for e in entrees if e.echelon == "autre")
    # Une aide de Région accrochée à SA région, y compris quand elle n'énumère
    # que des départements : `regions` recouvre les deux écritures.
    regions = [
        {
            "code": code,
            "label": REGION_LABELS.get(code, code),
            **_groupe(e for e in entrees if e.echelon == "region" and code in e.regions),
        }
        for code in sorted(REGION_DEPARTEMENTS)
    ]
    departements = [
        {
            "code": code,
            "label": DEPARTEMENT_LABELS.get(code, code),
            "region": region,
            "regionLabel": REGION_LABELS.get(region, region),
            **_groupe(
                e
                for e in entrees
                if e.echelon == "departement" and code in e.aide.hard_filters.departements
            ),
        }
        for region, codes in sorted(REGION_DEPARTEMENTS.items())
        for code in codes
    ]

    return {
        "genereLe": datetime.now(UTC).isoformat(),
        "corpus": {
            "total": len(entrees),
            "nb": len(debout),
            "retirees": len(entrees) - len(debout),
            "nationales": national["nb"],
            "regionales": sum(1 for e in debout if e.echelon == "region"),
            "departementales": sum(1 for e in debout if e.echelon == "departement"),
            "autres": autres["nb"],
        },
        # slug → nom, envoyé une fois : les groupes ne portent que des slugs, et
        # une aide de fondation ouverte à huit départements verrait sinon son
        # nom recopié huit fois.
        "aides": {e.aide.slug: e.aide.nom for e in debout},
        "national": national,
        "autres": autres,
        "regions": regions,
        "departements": departements,
        "categories": [
            {
                "code": code,
                "label": CATEGORIE_LABELS.get(code, code),
                **_groupe(e for e in entrees if e.aide.categorie == code),
            }
            for code in CATEGORIES
        ],
        "types": [
            {
                "code": code,
                "label": TYPE_LABELS.get(code, code),
                **_groupe(e for e in entrees if e.aide.type == code),
            }
            for code in TYPES
        ],
        "synchronisation": _synchronisation(supabase, servies),
    }
