"""Le catalogue en chiffres : combien d'aides, sur quel territoire, à quel taux.

Lecture seule, pour la page d'administration `/admin/statistiques`. Cinq
décisions portent tout le module :

- **Le corpus compté est celui qui est SERVI**, `catalogue_effectif` — YAML
  moins les aides retirées. Une page qui compterait des aides qu'aucun
  diagnostic ne propose mentirait sur la couverture réelle. Les retirées ne
  disparaissent pas pour autant : elles sont comptées à part, sur leur propre
  territoire, parce qu'un retrait est une décision qu'on doit pouvoir relire.

- **La portée d'une aide est son PÉRIMÈTRE, pas son financeur.** Les deux ne se
  recouvrent pas : une aide de la Fondation du Patrimoine peut n'être ouverte
  qu'à huit départements, et un appel à projets régional s'appliquer partout
  dans la région. Le financeur, lui, vit dans `categorie` — d'où les colonnes
  « Conseil régional » et « Conseil départemental », qui répondent à l'autre
  question : cette collectivité-ci finance-t-elle quelque chose chez nous ?

- **Une énumération qui couvre toute la région ne restreint rien.** Beaucoup
  d'aides RÉGIONALES du corpus listent en plus les douze départements de leur
  région (convention de la colonne `aides_v3.departements`). Les compter comme
  locales ferait afficher « 0 aide régionale » à une région qui en a douze, et
  ferait lire « 11 aides départementales » là où il n'y a aucune aide de
  Conseil départemental. Le test `PorteeTests` fige cette règle.

- **Une aide au périmètre local compte dans sa région** (`REGION_DEPARTEMENTS`) :
  sans ce rattachement, une région dont toutes les aides nomment un département
  apparaîtrait vide alors qu'elle est la mieux couverte du catalogue.

- **Rien n'est sommé sur l'argent.** Un « total des plafonds » n'existe pas :
  les aides ne s'additionnent pas, elles se cumulent sous plafond public. On
  publie des bornes et des médianes, jamais une enveloppe.

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
from eligibility_engine import disponibilite, engine_ready_aides
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

#: Périmètre d'une aide. « locale » = plus étroit qu'une région entière : un
#: département, une poignée de départements, le ressort d'une délégation. Ce
#: n'est PAS « aide du Conseil départemental », qui se lit sur `categorie`.
Portee = Literal["nationale", "region", "locale"]

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
    """Une aide du corpus et les trois booléens qui la classent."""

    aide: Aide
    retiree: bool
    typee: bool
    bientot: bool

    @property
    def portee(self) -> Portee:
        """Le périmètre réel, une fois l'énumération redondante neutralisée.

        Une aide qui déclare sa région ET tous les départements de cette région
        reste RÉGIONALE : la liste ne retire rien, elle sert au filtrage en
        base. C'est le cas de la plupart des dispositifs régionaux du corpus —
        les lire comme locaux affichait « 0 régionale, 20 départementales » sur
        Auvergne-Rhône-Alpes, et faisait passer dix appels à projets de la
        Région pour des aides de Conseil départemental.

        Une énumération STRICTEMENT plus étroite, elle, restreint pour de bon
        (huit départements sur douze pour une délégation de fondation) : la
        portée est locale, et l'aide n'apparaît que sur ces départements-là.
        """
        filtres = self.aide.hard_filters
        if not filtres.departements:
            return "region" if filtres.regions else "nationale"
        if filtres.regions and set(filtres.departements) >= _departements_de(filtres.regions):
            return "region"
        return "locale"

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


def _bloc(entrees: Iterable[Entree]) -> dict:
    """Le chiffrage d'un groupe : ce que la même ligne de tableau montre
    partout, que le groupe soit une région, un département ou une catégorie.

    Les aides RETIRÉES sont comptées à part et sortent de tout le reste : elles
    ne sont plus servies, les inclure dans les taux gonflerait des chiffres que
    plus personne ne voit.
    """
    entrees = list(entrees)
    servies = [e for e in entrees if not e.retiree]
    aides = [e.aide for e in servies]

    taux = _nombres(_taux(a) for a in aides)
    taux_min = _nombres(
        a.financement.taux_min if a.financement.taux_min is not None else _taux(a) for a in aides
    )
    montants = _nombres(a.financement.montant_max for a in aides)

    return {
        "nb": len(servies),
        "retirees": len(entrees) - len(servies),
        "typees": sum(1 for e in servies if e.typee),
        "bientot": sum(1 for e in servies if e.bientot),
        "nbAvecTaux": len(taux),
        "tauxMin": min(taux_min) if taux_min else None,
        "tauxMax": max(taux) if taux else None,
        "tauxMedian": median(taux) if taux else None,
        "nbAvecMontant": len(montants),
        "montantMedian": median(montants) if montants else None,
        "montantMax": max(montants) if montants else None,
    }


def _collectivite(entrees: Iterable[Entree], categorie: str) -> int:
    """Combien de ces aides sont financées par la collectivité de cet échelon.

    Réponse à la question que le périmètre ne donne PAS : « le Conseil
    départemental de l'Isère finance-t-il quelque chose ? ». Onze aides
    applicables en Isère et zéro ici veut dire qu'il reste un financeur entier
    à prospecter.
    """
    return sum(1 for e in entrees if not e.retiree and e.aide.categorie == categorie)


def _ligne_region(code: str, entrees: list[Entree], nationales: int) -> dict:
    """Une région : ses aides à périmètre régional, celles à périmètre plus
    étroit, et ce qu'un monument y voit au mieux.

    `couvertureMax` est un MAXIMUM, pas un acquis : les aides locales ne valent
    que sur leurs départements. La page le dit, la clé le rappelle.
    """
    return {
        "code": code,
        "label": REGION_LABELS.get(code, code),
        "regionales": sum(1 for e in entrees if not e.retiree and e.portee == "region"),
        "locales": sum(1 for e in entrees if not e.retiree and e.portee == "locale"),
        "conseilRegional": _collectivite(entrees, "region"),
        "conseilsDepartementaux": _collectivite(entrees, "departement"),
        "nationales": nationales,
        "couvertureMax": sum(1 for e in entrees if not e.retiree) + nationales,
        **_bloc(entrees),
    }


def _ligne_departement(
    code: str, locales: list[Entree], regionales: list[Entree], nationales: int
) -> dict:
    """Un département : les aides qui le nomment, celles de sa région, les
    nationales.

    Ici la couverture est EXACTE — un monument de ce département voit les trois
    étages. C'est le chiffre de prospection : il dit où le catalogue est encore
    creux. Le chiffrage (taux, plafonds) reste calculé sur les seules aides
    locales : les régionales sont déjà chiffrées sur leur propre ligne.

    `conseilDepartemental` ne compte que les aides du Conseil départemental
    lui-même. Ce n'est pas un sous-ensemble cosmétique de `locales` : une
    délégation de fondation ou un dispositif régional restreint y sont locaux
    sans qu'un euro vienne du Département.
    """
    locales_servies = sum(1 for e in locales if not e.retiree)
    regionales_servies = sum(1 for e in regionales if not e.retiree)
    region = DEPARTEMENT_REGION.get(code)
    return {
        "code": code,
        "label": DEPARTEMENT_LABELS.get(code, code),
        "region": region,
        "regionLabel": REGION_LABELS.get(region or "", ""),
        "locales": locales_servies,
        "conseilDepartemental": _collectivite(locales, "departement"),
        "regionales": regionales_servies,
        "nationales": nationales,
        "couverture": locales_servies + regionales_servies + nationales,
        **_bloc(locales),
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
    typees = engine_ready_aides(servies)

    entrees = [
        Entree(
            # La version SERVIE quand elle existe (surcharges de prédicats
            # appliquées) ; le YAML brut pour une retirée, qui n'y est plus.
            aide=servies.get(slug, aide),
            retiree=slug in catalogue.retirees,
            typee=slug in typees,
            bientot=disponibilite(servies.get(slug, aide)) == "bientot",
        )
        for slug, aide in sorted(toutes.items())
    ]

    nationales = [e for e in entrees if e.portee == "nationale"]
    nb_nationales = sum(1 for e in nationales if not e.retiree)

    par_region = {
        code: [e for e in entrees if code in e.regions] for code in sorted(REGION_DEPARTEMENTS)
    }
    regions = [
        _ligne_region(code, groupe, nb_nationales) for code, groupe in sorted(par_region.items())
    ]
    # Le `portee == "locale"` n'est pas une précaution de style : une aide
    # régionale énumère souvent tous les départements de sa région, et sans ce
    # filtre elle serait comptée DEUX FOIS sur chacun d'eux — une fois en local,
    # une fois en régional. La couverture d'un département est une somme de
    # trois étages disjoints, ou elle ne veut rien dire.
    departements = [
        _ligne_departement(
            code,
            [
                e
                for e in entrees
                if e.portee == "locale" and code in e.aide.hard_filters.departements
            ],
            [e for e in par_region[region] if e.portee == "region"],
            nb_nationales,
        )
        for region, codes in sorted(REGION_DEPARTEMENTS.items())
        for code in codes
    ]

    return {
        "genereLe": datetime.now(UTC).isoformat(),
        "corpus": {
            "total": len(entrees),
            "nationales": nb_nationales,
            "regionales": sum(1 for e in entrees if not e.retiree and e.portee == "region"),
            "locales": sum(1 for e in entrees if not e.retiree and e.portee == "locale"),
            **_bloc(entrees),
        },
        "national": _bloc(nationales),
        "regions": regions,
        "departements": departements,
        "categories": [
            {
                "code": code,
                "label": CATEGORIE_LABELS.get(code, code),
                **_bloc(e for e in entrees if e.aide.categorie == code),
            }
            for code in CATEGORIES
        ],
        "types": [
            {
                "code": code,
                "label": TYPE_LABELS.get(code, code),
                **_bloc(e for e in entrees if e.aide.type == code),
            }
            for code in TYPES
        ],
        "synchronisation": _synchronisation(supabase, servies),
    }
