"""Plafonds et suppressions : les garde-fous des offres, côté serveur.

Le frontend masque déjà les boutons que l'offre ne permet pas, mais masquer un
bouton ne protège rien — un POST à la main suffit à le contourner. Ces
vérifications sont la vraie frontière ; l'affichage n'en est que le reflet.

Sur QUI porte le droit, c'est la seule question délicate, et la réponse suit le
principe déjà retenu pour les monuments partagés : c'est le BIEN qui est
couvert, pas le spectateur.

  * Enregistrer un NOUVEAU monument se juge sur le seul compte qui le crée : le
    bien n'existe pas encore, il n'a pas de propriétaire à consulter. Un
    monument partagé avec lui ne consomme pas son quota — il appartient à
    quelqu'un d'autre.
  * Tout ce qui touche à un monument EXISTANT (ses projets, son calendrier, sa
    suppression) se juge sur l'union des offres de son propriétaire et de
    l'appelant. Sans le propriétaire, un architecte invité sur le chantier d'un
    client abonné se verrait refuser la création d'un projet parce que lui-même
    est au gratuit : le client paierait un service que son équipe ne peut pas
    rendre. Sans l'appelant, on retirerait à un abonné un droit qu'il paye,
    juste parce qu'il travaille sur le bien de quelqu'un d'autre. Union, donc —
    on ne retire jamais un droit acquis par ailleurs, exactement comme
    `max_role` sur les deux niveaux de partage.

402 et non 403 : la demande est légitime, il manque une offre. Le frontend
distingue les deux — un 403 est un problème de droits d'équipe, un 402 mène à
la page Tarifs.
"""

from fastapi import HTTPException, status
from supabase import Client

from services import stripe_billing as billing
from services.offres import Offre, offre_pour

# Message unique : l'offre qui débloque est nommée, parce que « quota atteint »
# sans la suite laisse l'utilisateur chercher.
_PASSER_A = "Passez à l'offre {offre} pour {action}."


def _refus(offre_requise: str, action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail=_PASSER_A.format(offre=offre_requise, action=action),
    )


def _au_moins(supabase: Client, table: str, colonne: str, valeur: str, plafond: int) -> bool:
    """Y a-t-il déjà `plafond` lignes ou plus ?

    On rapatrie les identifiants, bornés à `plafond + 1`, plutôt que de demander
    à PostgREST son en-tête `count`. Deux raisons : le plafond n'est consulté
    que sur des offres à très petit volume (un monument, deux projets), et un
    `count` absent de la réponse se lirait comme un zéro — un défaut de comptage
    ouvrirait alors le quota au lieu de le fermer.
    """
    res = supabase.table(table).select("id").eq(colonne, valeur).limit(plafond + 1).execute()
    return len((res.data if res else None) or []) >= plafond


# ---------------------------------------------------------------------------
# Quelle offre gouverne un monument
# ---------------------------------------------------------------------------


def _proprietaires(supabase: Client, monument_ids: list[str]) -> dict[str, str]:
    """`monuments.user_id` par monument — le compte qui a enregistré le bien."""
    if not monument_ids:
        return {}
    rows = (
        (supabase.table("monuments").select("id, user_id").in_("id", monument_ids).execute()).data
    ) or []
    return {r["id"]: r["user_id"] for r in rows if r.get("user_id")}


def offres_des_monuments(
    supabase: Client, monument_ids: list[str], user_id: str
) -> dict[str, Offre]:
    """L'offre qui gouverne chacun de ces biens, en deux requêtes au total.

    Sert à la fois aux vérifications d'écriture et à l'affichage : la liste
    « Mes monuments » et le tableau de bord renvoient cette offre au frontend,
    qui décide quels boutons montrer. Un aller-retour par monument se paierait
    sinon à chaque ouverture de la liste.
    """
    proprietaires = _proprietaires(supabase, monument_ids)
    # Le compte de l'appelant est toujours interrogé : c'est l'autre moitié de
    # l'union, et il couvre aussi le cas d'un monument dont le propriétaire a
    # disparu entre-temps.
    comptes = {user_id, *proprietaires.values()}
    plans = billing.plans_par_compte(supabase, comptes)
    siens = plans.get(user_id, set())
    return {
        monument_id: offre_pour(siens | plans.get(proprietaires.get(monument_id, ""), set()))
        for monument_id in monument_ids
    }


def offre_du_monument(supabase: Client, monument_id: str, user_id: str) -> Offre:
    """Version unitaire de `offres_des_monuments`, pour les routes d'écriture."""
    return offres_des_monuments(supabase, [monument_id], user_id)[monument_id]


# ---------------------------------------------------------------------------
# Monuments
# ---------------------------------------------------------------------------


def verifier_creation_monument(supabase: Client, user_id: str) -> None:
    """Le compte peut-il enregistrer un monument de plus ?"""
    offre = billing.offre_du_compte(supabase, user_id)
    if offre.monuments_max is None:
        return

    if _au_moins(supabase, "monuments", "user_id", user_id, offre.monuments_max):
        raise _refus(
            "Multi-monuments",
            "enregistrer plusieurs monuments"
            if offre.monuments_max == 1
            else f"dépasser {offre.monuments_max} monuments",
        )


def verifier_suppression_monument(supabase: Client, monument_id: str, user_id: str) -> None:
    """La suppression d'un monument est réservée à l'offre Multi-monuments.

    Un compte limité à un seul monument qui pourrait le supprimer contournerait
    son plafond en boucle : supprimer, recréer, autant de fois que voulu.
    """
    if not offre_du_monument(supabase, monument_id, user_id).suppression_monument:
        raise _refus("Multi-monuments", "supprimer un monument")


def verifier_invitation(supabase: Client, monument_id: str, user_id: str) -> None:
    """Inviter quelqu'un suppose au moins l'offre Veille.

    Le contrôle est le même pour les deux portées de partage — l'équipe du
    monument et celle d'un chantier — parce que c'est le même service qui se
    vend : travailler à plusieurs. Gouverner l'une sans l'autre n'aurait aucun
    sens, l'équipe du monument étant la plus large des deux.

    RETIRER un membre reste toujours possible, y compris au gratuit : couper un
    accès qu'on ne contrôle plus n'est pas un service, c'est une sécurité. Une
    offre résiliée laisse donc l'équipe en place et gérable, sans pouvoir
    l'agrandir.
    """
    if not offre_du_monument(supabase, monument_id, user_id).equipe:
        raise _refus("Veille", "inviter des collaborateurs")


# ---------------------------------------------------------------------------
# Projets
# ---------------------------------------------------------------------------


def verifier_creation_projet(supabase: Client, monument_id: str, user_id: str) -> None:
    """Le monument peut-il porter un chantier de plus ?

    Le plafond se compte par monument, et non par compte : c'est l'offre qui
    gouverne le bien qui l'accorde. Sur l'offre gratuite — un seul monument
    possible — les deux formulations donnent le même résultat.
    """
    offre = offre_du_monument(supabase, monument_id, user_id)
    if offre.projets_max is None:
        return

    if _au_moins(supabase, "projets", "monument_id", monument_id, offre.projets_max):
        raise _refus("Veille", f"mener plus de {offre.projets_max} projets sur un monument")


def verifier_suppression_projet(supabase: Client, monument_id: str, user_id: str) -> None:
    """La suppression d'un projet suppose au moins l'offre Veille.

    Même raison que pour les monuments : sans elle, le plafond de deux projets
    de l'offre gratuite se recyclerait indéfiniment.
    """
    if not offre_du_monument(supabase, monument_id, user_id).suppression_projet:
        raise _refus("Veille", "supprimer un projet")
