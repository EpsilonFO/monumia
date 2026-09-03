"""Les trois offres et ce que chacune ouvre.

Module PUR : aucune base, aucun réseau, aucun Stripe. C'est la table de vérité
des droits, et elle se lit d'un coup d'œil — l'intérêt étant qu'on puisse
répondre à « qu'est-ce que l'offre gratuite permet ? » en regardant une seule
constante, plutôt qu'en cherchant des `if` dans huit routeurs.

Trois offres, et la troisième contient la deuxième :

  * GRATUIT          — un monument, deux projets, le détail de toutes les aides.
                       Le compte y travaille SEUL : pas d'invitation.
  * VEILLE           — projets illimités, une équipe, le calendrier (échéancier,
                       aides à venir) et les rappels par email.
  * MULTI_MONUMENTS  — tout ce qui précède, monuments illimités, tableau de bord.

Le détail des aides n'est PAS dans cette table : il est gratuit. Ce qui se vend,
c'est le volume, le calendrier et la veille.

Le miroir côté frontend est `frontend/src/lib/offres.ts`, et les deux doivent
rester d'accord — les tests de chaque côté figent la même table.
"""

from collections.abc import Iterable
from dataclasses import dataclass, replace

PLAN_VEILLE = "veille"
PLAN_MULTI_MONUMENTS = "multi_monuments"

#: Toutes les offres connues, dans l'ordre d'affichage sur la page Tarifs.
PLANS = (PLAN_VEILLE, PLAN_MULTI_MONUMENTS)

#: Celles qui s'achètent en autonomie, par Stripe Checkout. VIDE aujourd'hui :
#: les deux offres payantes se négocient, la page Tarifs n'affiche aucun montant
#: et renvoie vers contact@monumia.fr. Elles restent des offres de plein droit,
#: et Stripe reste l'outil de facturation — c'est seulement le tunnel d'achat en
#: libre-service qui est fermé.
#:
#: Ouvrir la vente en ligne d'une offre = l'ajouter ici, poser son prix dans
#: `STRIPE_PRICE_*`, et rendre son bouton à `startCheckout` sur la page Tarifs.
PLANS_VENDABLES: tuple[str, ...] = ()


@dataclass(frozen=True)
class Offre:
    """Ce qu'un compte peut faire. `None` sur un plafond = illimité.

    Les plafonds portent sur ce que le compte POSSÈDE, pas sur ce qu'il voit :
    un monument partagé par quelqu'un d'autre ne consomme pas le quota de
    l'invité (cf. services/quotas.py).
    """

    #: Nom de l'offre, tel qu'il s'écrit dans un message d'erreur.
    nom: str
    #: Monuments que le compte peut enregistrer. None = illimité.
    monuments_max: int | None
    #: Projets par monument. None = illimité.
    projets_max: int | None
    #: Le tableau de bord agrégé (`/app`).
    dashboard: bool
    #: Inviter quelqu'un sur un monument ou sur un de ses chantiers.
    equipe: bool
    #: Supprimer un monument.
    suppression_monument: bool
    #: Supprimer un projet.
    suppression_projet: bool
    #: Voir en clair les aides dont le guichet n'est pas encore ouvert
    #: (« Disponibles bientôt »). Sinon elles sont caviardées comme le reste
    #: du contenu payant : montants et dates visibles, financeur masqué.
    aides_bientot: bool
    #: L'échéancier d'un projet (dates limites d'aides et de dossiers).
    echeancier: bool
    #: Les emails : ouverture de guichet, et rappels avant échéance.
    rappels_email: bool


GRATUIT = Offre(
    nom="Gratuit",
    monuments_max=1,
    projets_max=2,
    dashboard=False,
    equipe=False,
    suppression_monument=False,
    suppression_projet=False,
    aides_bientot=False,
    echeancier=False,
    rappels_email=False,
)

VEILLE = replace(
    GRATUIT,
    nom="Veille",
    projets_max=None,
    equipe=True,
    suppression_projet=True,
    aides_bientot=True,
    echeancier=True,
    rappels_email=True,
)

MULTI_MONUMENTS = replace(
    VEILLE,
    nom="Multi-monuments",
    monuments_max=None,
    dashboard=True,
    suppression_monument=True,
)

#: L'offre attachée à chaque plan Stripe. Un plan absent de ce dict — un
#: abonnement souscrit avant les trois offres, dont `plan` est NULL — n'ouvre
#: rien : le compte retombe sur GRATUIT.
_OFFRE_PAR_PLAN: dict[str, Offre] = {
    PLAN_VEILLE: VEILLE,
    PLAN_MULTI_MONUMENTS: MULTI_MONUMENTS,
}


def offre_pour(plans: Iterable[str] | str | None) -> Offre:
    """L'offre effective d'un compte, à partir des plans qu'il détient.

    Cumuler est permis (Veille + Multi-monuments) et sans effet utile, puisque
    Multi-monuments contient Veille — mais un compte peut se retrouver dans cet
    état après une montée en gamme, le temps que l'ancien abonnement expire. On
    prend donc le meilleur droit de chaque colonne plutôt que le premier plan
    trouvé : ne jamais retirer un droit déjà acquis par ailleurs.
    """
    offres = [_OFFRE_PAR_PLAN[p] for p in _iter_plans(plans) if p in _OFFRE_PAR_PLAN]
    if not offres:
        return GRATUIT
    if len(offres) == 1:
        return offres[0]

    return Offre(
        # Le nom affiché est celui de l'offre la plus large détenue.
        nom=max(offres, key=_rang).nom,
        monuments_max=_plafond_max(o.monuments_max for o in offres),
        projets_max=_plafond_max(o.projets_max for o in offres),
        dashboard=any(o.dashboard for o in offres),
        equipe=any(o.equipe for o in offres),
        suppression_monument=any(o.suppression_monument for o in offres),
        suppression_projet=any(o.suppression_projet for o in offres),
        aides_bientot=any(o.aides_bientot for o in offres),
        echeancier=any(o.echeancier for o in offres),
        rappels_email=any(o.rappels_email for o in offres),
    )


def _iter_plans(plans: Iterable[str] | str | None) -> list[str]:
    """Accepte un plan seul comme un ensemble — les appelants ont les deux."""
    if plans is None:
        return []
    if isinstance(plans, str):
        return [plans]
    return [str(p) for p in plans]


def _rang(offre: Offre) -> int:
    """Largeur d'une offre : sert à choisir le nom à afficher."""
    return sum(
        (
            offre.monuments_max is None,
            offre.projets_max is None,
            offre.dashboard,
            offre.suppression_monument,
            offre.aides_bientot,
        )
    )


def _plafond_max(valeurs: Iterable[int | None]) -> int | None:
    """Le plus permissif de plusieurs plafonds ; None (illimité) l'emporte."""
    connues = []
    for v in valeurs:
        if v is None:
            return None
        connues.append(v)
    return max(connues) if connues else None


def as_dict(offre: Offre) -> dict:
    """Forme camelCase envoyée au frontend par GET /billing/access."""
    return {
        "nom": offre.nom,
        "monumentsMax": offre.monuments_max,
        "projetsMax": offre.projets_max,
        "dashboard": offre.dashboard,
        "equipe": offre.equipe,
        "suppressionMonument": offre.suppression_monument,
        "suppressionProjet": offre.suppression_projet,
        "aidesBientot": offre.aides_bientot,
        "echeancier": offre.echeancier,
        "rappelsEmail": offre.rappels_email,
    }
