"""Endpoint agrégé du dashboard.

Le dashboard réclamait 4 + 2N requêtes HTTP pour N projets (monuments, aides,
dossiers, puis un diagnostic et une liste de suivis par monument), chacune
repayant la vérification du token et sa propre poignée de main TLS vers
Supabase. Tout est ici regroupé en un seul appel, à nombre d'allers-retours
Supabase constant : le moteur déterministe est purement CPU, donc l'exécuter
pour tous les projets d'un coup ne coûte rien de plus qu'un aller-retour évité.
"""

from fastapi import APIRouter, Depends
from supabase import Client

from db import get_current_user_id, get_supabase
from routers.aides import (
    LOCKED_AIDE_LABEL,
    deterministic_diagnostic_for,
    merge_projet_into_monument,
)
from routers.monuments import fetch_user_monuments, sign_photos
from services import aides_fermees
from services.parallele import en_parallele
from services.pieces_demandees import pieces_demandees
from services.project_access import projet_role_depuis

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Les trois seaux « positifs » : le dashboard et la liste des projets comptent
# les aides identifiées et lisent leurs dates limites. Les non éligibles ne sont
# affichées que sur la page d'un projet, qui recalcule son diagnostic complet.
_DIGEST_BUCKETS = ("aidesEligibles", "aidesPotentiellementEligibles", "aidesAtteignables")


def _est_resolue(question: dict, answers: dict) -> bool:
    """Miroir d'`estResolue` (frontend/src/lib/diagnostic-bilan.ts) : une
    question est tranchée dès qu'une réponse autre que « passer » ou qu'une
    option inconnue du moteur a été donnée."""
    answer = answers.get(question.get("id"))
    given = [
        a
        for a in (answer if isinstance(answer, list) else [answer])
        if isinstance(a, str) and a != "skip"
    ]
    inconnues = {o.get("id") for o in question.get("options") or [] if o.get("unknown")}
    return any(a not in inconnues for a in given)


def questions_restantes_par_aide(result: dict) -> dict[str, int]:
    """Nombre de questions encore ouvertes, par aide (source : `aideIds` des
    questions du moteur, comme `questionsPourAide` côté front)."""
    answers = result.get("qcmAnswers") or {}
    compte: dict[str, int] = {}
    for question in result.get("qcmQuestions") or []:
        if _est_resolue(question, answers):
            continue
        for aide_id in question.get("aideIds") or []:
            compte[aide_id] = compte.get(aide_id, 0) + 1
    return compte


def build_digest(
    result: dict, monument_id: str, projet_id: str, *, masquer_bientot: bool = False
) -> dict:
    """Réduit un diagnostic complet à ce que les vignettes de projet affichent.

    Un diagnostic complet pèse ~1,7 Mo : l'essentiel vient des ~95 aides non
    éligibles et de leurs conditions détaillées, dont le dashboard ne lit rien.
    Il n'en a besoin que de compteurs, de deux montants et des dates limites.

    Porte les deux identifiants : `projetId` parce que le digest décrit un
    chantier, `monumentId` parce que le paywall et les liens d'échéance restent
    clés monument.
    """
    digest: dict = {
        "projetId": projet_id,
        "monumentId": monument_id,
        "montantPotentielTotal": result.get("montantPotentielTotal"),
        "montantAtteignableTotal": result.get("montantAtteignableTotal"),
        "tauxTravauxMaxPct": result.get("tauxTravauxMaxPct"),
        # Les pièces que demandent ses aides à portée : la liste « À déposer
        # pour vos aides » de Mes documents (cf. services/pieces_demandees).
        "piecesDemandees": pieces_demandees(result, masquer_bientot=masquer_bientot),
    }
    restantes = questions_restantes_par_aide(result)
    for bucket in _DIGEST_BUCKETS:
        digest[bucket] = [
            {
                "aide": {
                    "id": match["aide"]["id"],
                    # Le nom alimente l'échéancier du projet : une aide dont le
                    # guichet n'est pas encore ouvert ne doit pas plus sortir
                    # d'ici que du diagnostic complet (cf.
                    # redact_bientot_hors_offre).
                    "nom": (
                        LOCKED_AIDE_LABEL
                        if masquer_bientot and match.get("disponibilite") == "bientot"
                        else match["aide"]["nom"]
                    ),
                    "categorie": match["aide"]["categorie"],
                    "permanent": match["aide"].get("permanent", False),
                    "dateLimite": match["aide"].get("dateLimite"),
                    "montantMax": match["aide"].get("montantMax"),
                    # De quoi rédiger « À faire maintenant » sur le tableau de
                    # bord : la carte (titre, chapeau, montant écrit) et le taux
                    # qui sert de repli au montant. Retenus avec le nom quand
                    # le guichet n'est pas ouvert et l'offre ne le couvre pas.
                    **(
                        {}
                        if masquer_bientot and match.get("disponibilite") == "bientot"
                        else {
                            "nomCourt": match["aide"].get("nomCourt"),
                            "carte": match["aide"].get("carte"),
                            "tauxMax": match["aide"].get("tauxMax"),
                        }
                    ),
                },
                # Questions qui séparent encore l'aide d'un verdict : elles se
                # posent sur sa fiche, le tableau de bord n'en donne que le nombre.
                "questionsRestantes": restantes.get(match["aide"]["id"], 0),
                # Fenêtre de candidature du jour : le digest reste un
                # sous-ensemble structurel du diagnostic complet, que les
                # fonctions de project-stats consomment indifféremment.
                "disponibilite": match.get("disponibilite", "maintenant"),
            }
            for match in result.get(bucket, [])
        ]
    return digest


@router.get("")
def get_dashboard(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    monuments, population_by_code, roles_propres = fetch_user_monuments(supabase, user_id)
    if not monuments:
        return {
            "monuments": [],
            "projets": [],
            "dossiers": [],
            "digests": {},
            "suivis": {},
        }

    monument_ids = [m["id"] for m in monuments]
    monuments_by_id = {m["id"]: m for m in monuments}

    # Une seule vague une fois les monuments connus : les photos à signer, les
    # projets, les dossiers et les suivis ne dépendent que de `monument_ids`.
    # Les filtres de visibilité s'appliquent APRÈS, en mémoire.
    #
    # Les photos vivent dans un bucket privé : sans lien signé, les vignettes de
    # « Mes monuments » et du tableau de bord seraient cassées.
    _, projet_rows, dossier_rows, suivi_rows = en_parallele(
        lambda: sign_photos(supabase, monuments),
        lambda: (
            supabase.table("projets")
            .select("*")
            .in_("monument_id", monument_ids)
            .order("created_at", desc=True)
            .execute()
            .data
        ),
        lambda: (
            supabase.table("dossiers")
            .select("*")
            .in_("monument_id", monument_ids)
            .order("date_derniere_modification", desc=True)
            .execute()
            .data
        ),
        # Les suivis restent filtrés par utilisateur, comme /projets/{id}/aide-suivis.
        lambda: (
            supabase.table("aide_suivis")
            .select("*")
            .in_("monument_id", monument_ids)
            .eq("user_id", user_id)
            .execute()
            .data
        ),
    )

    # Les projets visibles. Sur un monument dont l'utilisateur est membre, tous ;
    # sur un monument atteint par un seul chantier (`my_role` None), ce chantier
    # et lui seul — c'est ici que se joue le « ils ne voient pas le reste ».
    equipe_monument = {m["id"] for m in monuments if m.get("my_role")}
    projets = [
        p
        for p in projet_rows or []
        if p["monument_id"] in equipe_monument or p["id"] in roles_propres
    ]
    # Le rôle EFFECTIF sur chaque projet, comme toute réponse de routers/projets :
    # le front lit les droits d'une page projet sur `Projet.myRole`, et ce payload
    # remplace les projets du store — sans ce champ, il effacerait le rôle posé
    # par `GET /projets/{id}` et retirerait l'onglet Aides à son chef de projet.
    for p in projets:
        monument_role = (monuments_by_id.get(p["monument_id"]) or {}).get("my_role")
        p["my_role"] = projet_role_depuis(p, monument_role, roles_propres, user_id)
    projets_visibles = {p["id"] for p in projets}

    dossiers_bruts = [d for d in dossier_rows or [] if d["projet_id"] in projets_visibles]
    # Une aide sortie du catalogue : ses dossiers portent l'explication, et
    # disparaissent avec leurs suivis une fois le panneau lu.
    dossiers = aides_fermees.appliquer_aux_dossiers(supabase, user_id, dossiers_bruts)
    suivi_rows = aides_fermees.filtrer_suivis(supabase, user_id, suivi_rows or [], dossiers_bruts)

    # Les lignes PostgREST ne sont pas typées : on resserre la clé en str.
    suivis: dict[str, list[dict]] = {str(p["id"]): [] for p in projets}
    for row in suivi_rows:
        if row["projet_id"] in projets_visibles:
            suivis.setdefault(row["projet_id"], []).append(row)

    # Un diagnostic par PROJET : la fiche du monument fusionnée avec le cadrage
    # du chantier, et les réponses déjà enregistrées de SON questionnaire. Un
    # monument sans projet n'a pas de digest — le front y affiche le CTA de
    # création. Le masquage des aides à venir, lui, se décide par monument :
    # `fetch_user_monuments` a déjà résolu l'offre qui gouverne chaque bien, il
    # n'y a donc aucune requête de droits à refaire ici.
    digests = {}
    for projet in projets:
        monument = monuments_by_id.get(projet["monument_id"])
        if monument is None:
            continue
        digests[projet["id"]] = build_digest(
            deterministic_diagnostic_for(
                merge_projet_into_monument(monument, projet),
                population_by_code.get(monument.get("code_insee") or ""),
                projet.get("questionnaire") or {},
                supabase=supabase,
            ),
            monument["id"],
            projet["id"],
            masquer_bientot=not (monument.get("offre") or {}).get("aidesBientot", False),
        )

    return {
        "monuments": monuments,
        "projets": projets,
        "dossiers": dossiers,
        "digests": digests,
        "suivis": suivis,
    }
