"""Contrôle d'accès : monuments et projets de travaux.

Deux appartenances cohabitent, et leur articulation est la règle centrale du
produit :

  * `project_members` — l'équipe du MONUMENT. Elle voit tout : la fiche, tous
    les projets, les documents du monument et ceux de ses projets.
  * `projet_members` — l'équipe d'un PROJET. Elle ne voit que son chantier, plus
    la fiche sanitaire du monument en lecture seule.

Le rôle effectif sur un projet est le **maximum** des deux (`max_role`) : un
co_owner du monument reste co_owner de chacun de ses projets sans ligne dans
`projet_members`. L'échelle des projets n'a pas de `owner` — la propriété
appartient au monument.

Les fonctions `role_at_least`, `max_role` et `can_delete_document` sont PURES
(testées unitairement) ; celles qui interrogent Supabase s'appuient dessus.
"""

from fastapi import HTTPException
from supabase import Client

from services.parallele import en_parallele

Role = str  # "owner" | "co_owner" | "member"

_ROLE_RANK: dict[str, int] = {"member": 1, "co_owner": 2, "owner": 3}


def role_at_least(role: Role | None, minimum: Role) -> bool:
    """True si `role` est au moins aussi élevé que `minimum` dans la hiérarchie."""
    if role is None:
        return False
    return _ROLE_RANK.get(role, 0) >= _ROLE_RANK[minimum]


def max_role(a: Role | None, b: Role | None) -> Role | None:
    """Le plus élevé des deux rôles, `None` n'étant aucun rôle.

    Sert à combiner l'appartenance au monument et celle au projet : on ne
    RESTREINT jamais un droit déjà acquis plus haut. Un chef de projet du
    monument qu'on ajouterait en simple membre d'un de ses chantiers doit rester
    chef de projet dessus.
    """
    if a is None:
        return b
    if b is None:
        return a
    return a if _ROLE_RANK.get(a, 0) >= _ROLE_RANK.get(b, 0) else b


def can_delete_document(role: Role | None, *, is_uploader: bool) -> bool:
    """Un document est supprimable par son auteur, ou par un owner/co_owner."""
    if is_uploader:
        return True
    return role_at_least(role, "co_owner")


def can_view_document(
    *,
    visibility: str,
    allowed_user_ids: list[str],
    uploader_id: str | None,
    viewer_id: str,
    viewer_role: Role | None,
) -> bool:
    """Qui peut consulter un document.

    L'auteur et le chef de projet (owner) voient toujours. Un non-membre ne voit
    jamais (hormis auteur/owner). Sinon, selon la visibilité : 'team' → tout
    membre ; 'responsables' → owner/co_owner ; 'custom' → uniquement les
    user_id explicitement autorisés (qui doivent rester membres du projet).
    """
    if uploader_id is not None and viewer_id == uploader_id:
        return True
    if viewer_role == "owner":
        return True
    if viewer_role is None:
        return False
    if viewer_id in allowed_user_ids:
        return True
    if visibility == "team":
        return True
    if visibility == "responsables":
        return role_at_least(viewer_role, "co_owner")
    return False


def allowed_visibilities(role: Role | None) -> set[str]:
    """Visibilités qu'un utilisateur de ce rôle a le droit de poser sur un document.

    Un collaborateur ne peut pas rendre un document visible par « toute l'équipe ».
    """
    if role_at_least(role, "co_owner"):
        return {"team", "responsables", "custom"}
    return {"responsables", "custom"}


def can_edit_visibility(role: Role | None, *, is_uploader: bool) -> bool:
    """Changer la visibilité : l'auteur, ou un owner/co_owner du projet."""
    return can_delete_document(role, is_uploader=is_uploader)


def can_modify_document(
    *,
    visibility: str,
    allowed_user_ids: list[str],
    uploader_id: str | None,
    viewer_id: str,
    viewer_role: Role | None,
) -> bool:
    """Modifier / supprimer / déplacer / repartager un document.

    Prérequis ABSOLU : pouvoir le consulter. Un adjoint (co_owner) exclu d'un
    document « personnes choisies » ne peut donc rien en faire — ni le voir, ni
    le supprimer, ni le remplacer. Pour qui peut le voir, les droits sont ceux
    de la suppression : l'auteur, ou un owner/co_owner du projet.
    """
    if not can_view_document(
        visibility=visibility,
        allowed_user_ids=allowed_user_ids,
        uploader_id=uploader_id,
        viewer_id=viewer_id,
        viewer_role=viewer_role,
    ):
        return False
    is_uploader = uploader_id is not None and viewer_id == uploader_id
    return can_delete_document(viewer_role, is_uploader=is_uploader)


def get_project_role(supabase: Client, monument_id: str, user_id: str) -> Role | None:
    """Rôle de l'utilisateur sur le projet, ou None s'il n'est pas membre."""
    result = (
        supabase.table("project_members")
        .select("role")
        .eq("monument_id", monument_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if result and result.data:
        return result.data["role"]

    # Défense en profondeur : le `user_id` du monument est le propriétaire
    # authoritatif et immuable (cf. trigger prevent_owner_change). Même si la ligne
    # d'appartenance 'owner' manque (donnée non rétro-remplie, création hors flux
    # normal…), le propriétaire ne doit jamais perdre l'accès à SON projet.
    owner = (
        supabase.table("monuments")
        .select("id")
        .eq("id", monument_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if owner and owner.data:
        return "owner"
    return None


def require_project_access(
    supabase: Client, monument_id: str, user_id: str, minimum: Role = "member"
) -> Role:
    """Vérifie l'accès et renvoie le rôle, sinon lève 403/404."""
    role = get_project_role(supabase, monument_id, user_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Monument introuvable ou accès refusé")
    if not role_at_least(role, minimum):
        raise HTTPException(status_code=403, detail="Action non autorisée pour votre rôle")
    return role


def get_projet_role(supabase: Client, projet: dict, user_id: str) -> Role | None:
    """Rôle effectif sur un projet : le maximum de ses deux appartenances.

    `projet` est la ligne déjà chargée — l'appelant en a de toute façon besoin
    (travaux, questionnaire), autant ne pas la relire.
    """
    monument_role = get_project_role(supabase, projet["monument_id"], user_id)

    result = (
        supabase.table("projet_members")
        .select("role")
        .eq("projet_id", projet["id"])
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    # Les lignes PostgREST ne sont pas typées : on resserre explicitement.
    projet_role: Role | None = str(result.data["role"]) if result and result.data else None

    # Défense en profondeur : celui qui a créé le projet ne peut pas en perdre
    # l'accès, même si sa ligne d'appartenance manque (création hors flux
    # normal, donnée non rétro-remplie). Même logique que get_project_role.
    if projet.get("user_id") == user_id:
        projet_role = max_role(projet_role, "co_owner")

    return max_role(monument_role, projet_role)


def require_projet_access(
    supabase: Client, projet_id: str, user_id: str, minimum: Role = "member"
) -> tuple[dict, Role]:
    """Accès à un PROJET de travaux. Renvoie `(ligne projet, rôle effectif)`.

    Lève 404 si le projet n'existe pas ou si l'utilisateur n'a de rôle ni sur
    lui ni sur son monument, 403 si son rôle est insuffisant.
    """
    result = supabase.table("projets").select("*").eq("id", projet_id).maybe_single().execute()
    # maybe_single() peut renvoyer None (et pas seulement un `.data` vide).
    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    projet = result.data

    role = get_projet_role(supabase, projet, user_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Projet introuvable ou accès refusé")
    if not role_at_least(role, minimum):
        raise HTTPException(status_code=403, detail="Action non autorisée pour votre rôle")
    return projet, role


def require_projet_access_et_monument(
    supabase: Client, projet_id: str, user_id: str, minimum: Role = "member"
) -> tuple[dict, Role, dict]:
    """`require_projet_access`, plus la ligne complète du monument parent.

    Pour les routes qui ont de toute façon besoin du monument (le diagnostic) :
    la ligne est lue EN MÊME TEMPS que les deux appartenances, et son `user_id`
    tient lieu du contrôle « propriétaire » que `get_project_role` refait par une
    requête à part. Deux vagues au lieu de cinq requêtes en série.

    Même règle, mêmes refus : 404 si le projet ou son monument n'existe pas, ou
    si l'utilisateur n'a de rôle ni sur l'un ni sur l'autre ; 403 si son rôle
    est insuffisant. La ligne du monument n'est rendue qu'une fois l'accès
    tranché.
    """
    result = supabase.table("projets").select("*").eq("id", projet_id).maybe_single().execute()
    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    projet = result.data
    monument_id = projet["monument_id"]

    membre, propre, monument_res = en_parallele(
        lambda: (
            supabase.table("project_members")
            .select("role")
            .eq("monument_id", monument_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        ),
        lambda: (
            supabase.table("projet_members")
            .select("role")
            .eq("projet_id", projet["id"])
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        ),
        lambda: (
            supabase.table("monuments").select("*").eq("id", monument_id).maybe_single().execute()
        ),
    )
    monument = (monument_res.data if monument_res else None) or None

    monument_role: Role | None = str(membre.data["role"]) if membre and membre.data else None
    # Défense en profondeur, comme get_project_role : le propriétaire
    # authoritatif du bien ne perd jamais l'accès, ligne d'équipe ou non.
    if monument_role is None and monument and monument.get("user_id") == user_id:
        monument_role = "owner"
    roles_propres = {str(projet["id"]): str(propre.data["role"])} if propre and propre.data else {}

    role = projet_role_depuis(projet, monument_role, roles_propres, user_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Projet introuvable ou accès refusé")
    if not role_at_least(role, minimum):
        raise HTTPException(status_code=403, detail="Action non autorisée pour votre rôle")
    if monument is None:
        raise HTTPException(status_code=404, detail="Monument introuvable")
    return projet, role, monument


def projet_roles_propres(supabase: Client, user_id: str) -> dict[str, Role]:
    """{projet_id: rôle} des appartenances PROPRES de l'utilisateur (projet_members).

    Une seule requête, pour les appelants qui traitent plusieurs projets d'un
    coup (liste d'un monument, dashboard) — `get_projet_role` en interrogerait
    une par projet.
    """
    rows = (
        supabase.table("projet_members")
        .select("projet_id, role")
        .eq("user_id", user_id)
        .execute()
        .data
    ) or []
    return {str(r["projet_id"]): str(r["role"]) for r in rows}


def projet_role_depuis(
    projet: dict, monument_role: Role | None, roles_propres: dict[str, Role], user_id: str
) -> Role | None:
    """Version PURE de `get_projet_role`, sur des données déjà chargées.

    Même règle : maximum des deux appartenances, et le créateur du projet garde
    au moins co_owner.
    """
    projet_role = roles_propres.get(projet["id"])
    if projet.get("user_id") == user_id:
        projet_role = max_role(projet_role, "co_owner")
    return max_role(monument_role, projet_role)


def projet_ids_membre(supabase: Client, user_id: str) -> list[str]:
    """Les projets où l'utilisateur a une appartenance PROPRE (`projet_members`).

    Volontairement sans les projets hérités du monument : cette liste sert à
    répondre « à quoi cette personne accède-t-elle SANS être dans l'équipe du
    monument ? » — le périmètre restreint, celui qu'on ne doit pas élargir.
    """
    rows = (
        supabase.table("projet_members").select("projet_id").eq("user_id", user_id).execute().data
    ) or []
    return [r["projet_id"] for r in rows]


def monument_ids_via_projets(supabase: Client, projet_ids: list[str]) -> dict[str, str]:
    """{projet_id: monument_id} pour les projets donnés. `{}` si la liste est vide."""
    if not projet_ids:
        return {}
    rows = (
        supabase.table("projets").select("id, monument_id").in_("id", projet_ids).execute().data
    ) or []
    return {r["id"]: r["monument_id"] for r in rows}


def my_scope_roles(supabase: Client, user_id: str) -> tuple[dict[str, Role], dict[str, Role]]:
    """Tout le périmètre de l'utilisateur : `({monument_id: rôle}, {projet_id: rôle})`.

    Les rôles de projets sont EFFECTIFS : ceux hérités des monuments dont
    l'utilisateur est membre, écrasés au besoin par une appartenance propre plus
    élevée. Quatre requêtes en deux vagues, quel que soit le nombre d'objets — les appelants
    qui filtrent une liste de documents ne peuvent pas se permettre une lecture
    par ligne.
    """
    # Deux vagues : les trois lectures clés utilisateur partent ensemble, seuls
    # les projets hérités attendent de connaître les monuments.
    members, owned, propres = en_parallele(
        lambda: (
            supabase.table("project_members")
            .select("monument_id, role")
            .eq("user_id", user_id)
            .execute()
            .data
        ),
        lambda: supabase.table("monuments").select("id").eq("user_id", user_id).execute().data,
        lambda: projet_roles_propres(supabase, user_id),
    )
    monument_roles: dict[str, Role] = {}
    for m in members or []:
        monument_roles[str(m["monument_id"])] = str(m["role"])
    for o in owned or []:
        monument_roles[str(o["id"])] = "owner"

    projet_roles: dict[str, Role] = {}
    if monument_roles:
        herites = (
            supabase.table("projets")
            .select("id, monument_id")
            .in_("monument_id", list(monument_roles))
            .execute()
            .data
        ) or []
        for p in herites:
            projet_roles[str(p["id"])] = monument_roles[str(p["monument_id"])]

    for projet_id, role in propres.items():
        projet_roles[projet_id] = max_role(projet_roles.get(projet_id), role) or role

    return monument_roles, projet_roles


def best_document_role(
    monument_ids: list | None,
    projet_ids: list | None,
    monument_roles: dict[str, Role],
    projet_roles: dict[str, Role],
) -> Role | None:
    """Rôle du viewer sur un document, au vu de tout ce à quoi il est rattaché.

    Un document peut pendre à un monument ET à des projets ; on retient le rôle
    le plus élevé parmi ceux qui donnent accès. Fonction PURE — c'est elle qui
    décide de la visibilité d'une pièce, elle se teste sans base.
    """
    best: Role | None = None
    for mid in monument_ids or []:
        best = max_role(best, monument_roles.get(str(mid)))
    for pid in projet_ids or []:
        best = max_role(best, projet_roles.get(str(pid)))
    return best


def require_monument_read(supabase: Client, monument_id: str, user_id: str) -> Role | None:
    """Droit de LIRE la fiche d'un monument, et rôle sur son équipe.

    Deux populations y accèdent, et la valeur de retour les distingue :
      * l'équipe du monument → son rôle (`owner` / `co_owner` / `member`) ;
      * un membre d'un seul de ses projets → `None`, qui vaut « je peux lire la
        fiche sanitaire, et rien d'autre ». Le `None` n'est donc PAS un refus
        ici — c'est un accès restreint, et tout appelant qui le confond avec un
        droit d'écriture ouvre une faille. Les écritures continuent de passer par
        `require_project_access`, qui, lui, refuse ces gens-là.

    Lève 404 si l'utilisateur n'a aucun des deux accès.
    """
    role = get_project_role(supabase, monument_id, user_id)
    if role is not None:
        return role

    mes_projets = projet_ids_membre(supabase, user_id)
    if mes_projets:
        appartenances = monument_ids_via_projets(supabase, mes_projets)
        if monument_id in appartenances.values():
            return None

    raise HTTPException(status_code=404, detail="Monument introuvable ou accès refusé")


def filter_visible_documents(
    rows: list[dict],
    user_id: str,
    monument_roles: dict[str, Role],
    projet_roles: dict[str, Role],
) -> list[dict]:
    """Ne garde que les documents que `user_id` a le droit de voir.

    Point de passage unique de la règle de visibilité sur une LISTE : la reprise
    des pièces (services/piece_reuse) propose des documents à l'utilisateur et
    doit voir exactement ce que la liste des documents lui montrerait — ni plus,
    ni moins. Construit sur `best_document_role`, donc sur les DEUX périmètres
    (pièces du bien et pièces du chantier).
    """
    return [
        r
        for r in rows
        if can_view_document(
            visibility=r.get("visibility") or "team",
            allowed_user_ids=r.get("allowed_user_ids") or [],
            uploader_id=r.get("user_id"),
            viewer_id=user_id,
            viewer_role=best_document_role(
                r.get("monument_ids"), r.get("projet_ids"), monument_roles, projet_roles
            ),
        )
    ]
