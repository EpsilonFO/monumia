"""Les rôles de COMPTE : qui administre le catalogue, qui teste le produit.

À ne pas confondre avec les rôles d'ÉQUIPE (`project_members.role`,
`projet_members.role` : `co_owner` / `member`), qui portent sur un monument ou
un chantier et se gèrent depuis l'onglet Équipe. Ceux-ci portent sur le compte
entier et se gèrent depuis `/admin`.

Deux rôles, et un seul est un droit d'administration :

  * `admin`        — la page `/admin` : retirer une aide, reformuler une
                     question, modifier un critère, nommer les rôles ;
  * `beta_testeur` — AUCUN droit d'administration. Le rôle n'ouvre qu'une
                     chose : l'offre Multi-monuments, sans abonnement ni
                     facturation, le temps des tests.

Les deux ouvrent la même offre aujourd'hui (`ROLES_AVEC_OFFRE`), pour deux
raisons différentes : l'administrateur parce qu'il doit pouvoir regarder le
catalogue depuis le produit, le bêta-testeur parce qu'on lui demande de
l'essayer en entier. Séparer les deux rôles permet d'en changer un sans
l'autre — et surtout, de donner l'offre sans donner le catalogue.

La liste vit en BASE (`comptes_roles`), pas dans une variable d'environnement :
une ligne s'y lit avec un email à côté, elle s'ajoute et se retire depuis
`/admin`, et elle n'exige plus de redéployer pour donner la main à quelqu'un.

`ADMIN_USER_IDS` reste lue, mais comme un SOCLE d'amorçage, et pour le seul
rôle `admin` :

  * c'est elle qui ouvre la porte quand la table est vide — juste après la
    migration, ou sur un environnement neuf ;
  * ses comptes ne se retirent PAS depuis l'application (ils ne sont pas dans la
    table), ce qui garantit qu'on ne peut pas se verrouiller dehors ;
  * elle peut ensuite être vidée du `.env`, une fois les mêmes comptes inscrits
    en base.

L'autorité sur l'administration reste `db.require_admin`, qui interroge l'UNION
des deux. Ce module n'est que la réponse à « ce compte a-t-il tel rôle ? », plus
les trois gestes de la page `/admin`.

Le cache suit le patron de `catalogue_admin` — module-level, TTL court,
invalidation après chaque écriture — mais il ne mémorise QUE les lignes de la
base : le socle est relu de l'environnement à chaque appel (un split sur deux
UUID ne coûte rien, et les tests remplacent la variable à chaud).
"""

from __future__ import annotations

import logging
import time

from supabase import Client

from config import admin_user_ids

logger = logging.getLogger(__name__)

TABLE = "comptes_roles"

ROLE_ADMIN = "admin"
ROLE_BETA_TESTEUR = "beta_testeur"

#: Les rôles connus, dans l'ordre d'affichage. Le lot est fermé : la base porte
#: la même contrainte, et un rôle inventé n'ouvrirait rien.
ROLES: tuple[str, ...] = (ROLE_ADMIN, ROLE_BETA_TESTEUR)

#: Comment chaque rôle se dit, côté serveur (messages d'erreur, journaux). Le
#: frontend a le sien, pour ses libellés d'interface.
LIBELLES = {ROLE_ADMIN: "Administrateur", ROLE_BETA_TESTEUR: "Bêta-testeur"}

#: Les rôles qui ouvrent l'offre Multi-monuments sans facturation. C'est ICI
#: qu'on en décide, pas dans la base ni dans `stripe_billing` : retirer un rôle
#: de cet ensemble lui reprend l'offre partout à la fois.
ROLES_AVEC_OFFRE = frozenset({ROLE_ADMIN, ROLE_BETA_TESTEUR})

#: Durée de validité du cache. Même valeur et même raison que la surcouche du
#: catalogue : c'est le délai maximal entre une ligne ajoutée hors application
#: (Supabase Studio) et sa prise d'effet. Les gestes passés par `/admin`
#: invalident tout de suite.
TTL_SECONDES = 60

#: Motif d'une attribution — même borne que celle d'un retrait d'aide.
MOTIF_MAX = 500


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------

_cache: dict[str, frozenset[str]] | None = None
_expire_a: float = 0.0


def invalider() -> None:
    """Force la prochaine lecture à relire la table. Appelée après chaque
    écriture — et par les tests, en setUp ET en tearDown."""
    global _cache, _expire_a
    _cache = None
    _expire_a = 0.0


def _lignes(supabase: Client) -> list[dict]:
    """Toutes les lignes de la table, ou rien.

    Une lecture qui échoue (migration pas encore appliquée, base injoignable)
    rend une liste VIDE : le socle `ADMIN_USER_IDS` reste alors seul à ouvrir la
    porte. Contrairement à la surcouche du catalogue, où l'échec est bénin, le
    repli va ici dans le sens qui REFUSE — on ne donne jamais la main à quelqu'un
    parce qu'une requête a échoué.
    """
    try:
        res = supabase.table(TABLE).select("*").execute()
        return list((res.data if res else None) or [])
    except Exception:
        logger.warning("rôles : lecture de %s impossible", TABLE, exc_info=True)
        return []


def _en_base(supabase: Client) -> dict[str, frozenset[str]]:
    """Les comptes inscrits en base, par rôle, mis en cache pour le TTL.

    Une ligne dont le rôle est inconnu est ignorée : la contrainte de la base
    l'interdit, mais une valeur écrite à la main dans Supabase Studio ne doit
    pas ouvrir de droit par accident.
    """
    global _cache, _expire_a
    maintenant = time.monotonic()
    if _cache is not None and maintenant < _expire_a:
        return _cache
    par_role: dict[str, set[str]] = {role: set() for role in ROLES}
    for ligne in _lignes(supabase):
        role, user_id = ligne.get("role"), ligne.get("user_id")
        if role in par_role and user_id:
            par_role[role].add(str(user_id))
        else:
            logger.warning("ligne %s au rôle inexploitable : %r", TABLE, ligne)
    _cache = {role: frozenset(ids) for role, ids in par_role.items()}
    _expire_a = maintenant + TTL_SECONDES
    return _cache


def socle() -> frozenset[str]:
    """Les administrateurs du `.env`, indéboulonnables depuis l'application.

    Le socle ne concerne QUE `admin` : un bêta-testeur se nomme depuis la page,
    il n'a jamais rien à amorcer.
    """
    return admin_user_ids()


def comptes_du_role(supabase: Client, role: str) -> frozenset[str]:
    """Les comptes portant ce rôle — socle compris pour `admin`."""
    ids = _en_base(supabase).get(role, frozenset())
    return (ids | socle()) if role == ROLE_ADMIN else ids


def a_le_role(supabase: Client, user_id: str, role: str) -> bool:
    return bool(user_id) and user_id in comptes_du_role(supabase, role)


def est_admin(supabase: Client, user_id: str) -> bool:
    """Ce compte administre-t-il le catalogue ?

    Faux si la table est vide et la variable absente : un environnement non
    configuré n'a AUCUN administrateur, jamais tous. Un bêta-testeur répond
    faux — c'est tout l'intérêt d'avoir deux rôles.
    """
    return a_le_role(supabase, user_id, ROLE_ADMIN)


def comptes_avec_offre(supabase: Client) -> frozenset[str]:
    """Tous les comptes à qui un rôle ouvre l'offre, en une lecture.

    Sert aux deux besoins de `stripe_billing` : la question unitaire (« ce
    compte a-t-il l'offre ? ») et la batch (`plans_par_compte`, appelée à chaque
    affichage de « Mes monuments »).
    """
    return frozenset().union(*(comptes_du_role(supabase, r) for r in ROLES_AVEC_OFFRE))


# ---------------------------------------------------------------------------
# La liste telle que `/admin` l'affiche
# ---------------------------------------------------------------------------

#: Plafond de la liste servie à `/admin`. Le produit compte quelques centaines
#: de comptes : la liste entière tient dans la page et le filtre est côté
#: client, donc instantané. Le plafond n'est qu'un garde-fou pour le jour où ce
#: ne sera plus vrai — et les porteurs de rôle sont ajoutés EN PLUS de lui, pour
#: qu'un droit attribué ne devienne jamais invisible faute de place.
LIMITE_UTILISATEURS = 500

#: Les colonnes de `users` affichées. Rien de plus : cette page sert à donner un
#: rôle, pas à consulter les comptes.
COLONNES_COMPTE = "id, email, prenom, nom, created_at"


def _comptes(supabase: Client, ids: list[str]) -> dict[str, dict]:
    """Les comptes cités, par identifiant, en une requête."""
    if not ids:
        return {}
    try:
        res = supabase.table("users").select(COLONNES_COMPTE).in_("id", sorted(set(ids))).execute()
        lignes = list((res.data if res else None) or [])
    except Exception:
        logger.warning("rôles : comptes illisibles", exc_info=True)
        return {}
    return {str(ligne["id"]): ligne for ligne in lignes if ligne.get("id")}


def _verrou(role: str, user_id: str, appelant: str, actif: bool, dans_socle: bool) -> str | None:
    """Pourquoi cette bascule est bloquée, ou `None` si elle ne l'est pas.

    Miroir EXACT des deux refus de `retirer_role`, et pour la même raison : un
    bouton qui part en 409 est un bouton qui n'aurait pas dû s'afficher. Les
    deux ne portent que sur le RETRAIT de l'administration — attribuer un rôle
    n'est jamais bloqué, et le bêta-test se retire toujours.
    """
    if role != ROLE_ADMIN or not actif:
        return None
    if dans_socle:
        return "Ce rôle vient de la variable ADMIN_USER_IDS du serveur : il se retire du .env."
    if user_id == appelant:
        return "Vous ne pouvez pas retirer votre propre administration."
    return None


def _etat_role(
    role: str,
    user_id: str,
    appelant: str,
    ligne: dict | None,
    auteur: dict | None,
    dans_socle: bool,
) -> dict:
    """L'état d'une bascule pour un compte.

    `source` dit d'où vient le rôle, et le socle l'emporte sur la base quand un
    compte est dans les deux : c'est lui qui décide que la bascule est bloquée,
    et l'afficher autrement promettrait un geste sans effet.
    """
    actif = dans_socle or ligne is not None
    raison = _verrou(role, user_id, appelant, actif, dans_socle)
    return {
        "actif": actif,
        "source": ("socle" if dans_socle else "base") if actif else None,
        "modifiable": raison is None,
        "raison": raison,
        "motif": (ligne or {}).get("motif"),
        "ajouteLe": (ligne or {}).get("created_at"),
        "ajoutePar": (auteur or {}).get("email"),
    }


def _entree(
    user_id: str,
    compte: dict | None,
    appelant: str,
    lignes: dict[tuple[str, str], dict],
    comptes: dict[str, dict],
    du_socle: frozenset[str],
) -> dict:
    """Un compte et l'état de ses deux bascules."""
    return {
        "userId": user_id,
        "email": (compte or {}).get("email"),
        "prenom": (compte or {}).get("prenom"),
        "nom": (compte or {}).get("nom"),
        "createdAt": (compte or {}).get("created_at"),
        # Vrai pour un identifiant du SOCLE sans ligne `users` (la table, elle,
        # a une clé étrangère) : compte supprimé, ou UUID recopié de travers
        # dans le `.env`. La ligne s'affiche quand même, marquée introuvable —
        # la cacher laisserait un administrateur invisible.
        "compteIntrouvable": compte is None,
        "roles": {
            role: _etat_role(
                role,
                user_id,
                appelant,
                lignes.get((user_id, role)),
                comptes.get(str((lignes.get((user_id, role)) or {}).get("ajoute_par") or "")),
                role == ROLE_ADMIN and user_id in du_socle,
            )
            for role in ROLES
        },
    }


def _lignes_par_couple(supabase: Client) -> dict[tuple[str, str], dict]:
    """Les attributions en base, indexées par (compte, rôle)."""
    return {
        (str(ligne["user_id"]), str(ligne["role"])): ligne
        for ligne in _lignes(supabase)
        if ligne.get("user_id") and ligne.get("role") in ROLES
    }


def lister_utilisateurs(supabase: Client, appelant: str) -> dict:
    """Tous les comptes, chacun avec l'état de ses deux bascules.

    La page donne un rôle en cliquant sur une ligne existante, plutôt qu'en
    tapant un email : on ne peut pas se tromper d'adresse, et on voit du même
    coup qui a déjà quoi.

    Deux compléments à la simple liste des comptes, tous deux pour qu'aucun
    droit attribué ne devienne invisible :

      * les porteurs de rôle sont ajoutés même s'ils tombent au-delà du plafond ;
      * les identifiants du socle sans compte `users` apparaissent quand même,
        marqués introuvables.
    """
    lignes = _lignes_par_couple(supabase)
    du_socle = socle()
    connus, tronquee = _premiers_comptes(supabase)
    ordre = [str(ligne["id"]) for ligne in connus if ligne.get("id")]
    comptes = {str(ligne["id"]): ligne for ligne in connus if ligne.get("id")}

    avec_role = {user_id for user_id, _ in lignes} | du_socle
    auteurs = {str(ligne["ajoute_par"]) for ligne in lignes.values() if ligne.get("ajoute_par")}
    manquants = sorted((avec_role | auteurs) - set(comptes))
    comptes.update(_comptes(supabase, manquants))
    # Les porteurs de rôle absents de la première page passent DEVANT : ce sont
    # eux qu'on vient gérer. Les auteurs d'attribution, eux, ne sont résolus que
    # pour afficher leur email, ils n'entrent pas dans la liste.
    ordre = sorted(avec_role - set(ordre)) + ordre

    return {
        "utilisateurs": [
            _entree(user_id, comptes.get(user_id), appelant, lignes, comptes, du_socle)
            for user_id in ordre
        ],
        # Le front le dit à l'écran : une liste tronquée en silence ferait
        # croire qu'un compte n'existe pas.
        "tronquee": tronquee,
        "limite": LIMITE_UTILISATEURS,
    }


def _premiers_comptes(supabase: Client) -> tuple[list[dict], bool]:
    """Les comptes les plus récents, et si la liste a été coupée.

    Un de plus que le plafond est demandé : c'est ce qui permet de dire que la
    liste est tronquée sans payer une requête de comptage.
    """
    try:
        res = (
            supabase.table("users")
            .select(COLONNES_COMPTE)
            .order("created_at", desc=True)
            .limit(LIMITE_UTILISATEURS + 1)
            .execute()
        )
        lignes = list((res.data if res else None) or [])
    except Exception:
        logger.warning("rôles : liste des comptes illisible", exc_info=True)
        return [], False
    return lignes[:LIMITE_UTILISATEURS], len(lignes) > LIMITE_UTILISATEURS


def entree_utilisateur(supabase: Client, user_id: str, appelant: str) -> dict:
    """La ligne À JOUR d'un seul compte, telle que la liste l'affiche.

    C'est ce que rendent les deux écritures : la page remplace sa ligne avec,
    sans relister tous les comptes à chaque bascule.
    """
    lignes = _lignes_par_couple(supabase)
    auteurs = [
        str(lignes[(user_id, role)]["ajoute_par"])
        for role in ROLES
        if lignes.get((user_id, role), {}).get("ajoute_par")
    ]
    comptes = _comptes(supabase, [user_id, *auteurs])
    return _entree(user_id, comptes.get(user_id), appelant, lignes, comptes, socle())


# ---------------------------------------------------------------------------
# Écritures — puis invalidation, pour que l'effet soit immédiat
# ---------------------------------------------------------------------------


def _compte_ou_erreur(supabase: Client, user_id: str) -> dict:
    """Le compte, ou `LookupError`.

    La clé étrangère de `comptes_roles` refuserait déjà un identifiant inconnu,
    mais par une erreur Postgres qui sortirait en 500 : mieux vaut un 404 qui
    dit ce qui s'est passé.
    """
    compte = _comptes(supabase, [user_id]).get(user_id)
    if compte is None:
        raise LookupError(f"Aucun compte Monumia avec l'identifiant « {user_id} »")
    return compte


def ajouter_role(
    supabase: Client, user_id: str, role: str, par: str, motif: str | None = None
) -> dict:
    """Attribue ce rôle à ce compte, et rend sa ligne à jour.

    Idempotent (upsert sur la clé composite) : réattribuer un rôle déjà porté ne
    fait rien de visible et ne se plaint pas — ce qu'exige une bascule, qu'un
    double-clic ou deux onglets ouverts peuvent activer deux fois.
    """
    if role not in ROLES:
        raise ValueError(f"Rôle inconnu « {role} »")
    _compte_ou_erreur(supabase, user_id)
    supabase.table(TABLE).upsert(
        {
            "user_id": user_id,
            "role": role,
            "motif": (motif or "").strip() or None,
            "ajoute_par": par,
        }
    ).execute()
    invalider()
    return entree_utilisateur(supabase, user_id, par)


def retirer_role(supabase: Client, user_id: str, role: str, par: str) -> dict:
    """Retire ce rôle, et rend la ligne du compte à jour.

    Deux refus, tous deux propres au rôle `admin`, et le premier suffit à
    garantir qu'il restera toujours quelqu'un pour administrer :

      * se retirer soi-même l'ADMINISTRATION — c'est le seul geste de cette page
        qui pourrait la fermer définitivement, et il se fait de toute façon à
        deux (l'autre administrateur vous retire). Se retirer son propre rôle de
        bêta-testeur, en revanche, ne ferme rien et reste permis ;
      * retirer l'administration à un compte du SOCLE `ADMIN_USER_IDS` —
        supprimer sa ligne (s'il en a une) le laisserait administrateur quand
        même, et la page mentirait. Ça se retire du `.env`, puis se redéploie.
    """
    if role == ROLE_ADMIN and user_id == par:
        raise ValueError(
            "Vous ne pouvez pas retirer vos propres droits d'administration : "
            "demandez-le à un autre administrateur."
        )
    if role == ROLE_ADMIN and user_id in socle():
        raise ValueError(
            "Ce compte vient de la variable ADMIN_USER_IDS : il se retire du .env, pas d'ici."
        )
    supabase.table(TABLE).delete().eq("user_id", user_id).eq("role", role).execute()
    invalider()
    return entree_utilisateur(supabase, user_id, par)
