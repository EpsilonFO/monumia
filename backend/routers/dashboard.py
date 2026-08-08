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
from routers.aides import LOCKED_AIDE_LABEL, deterministic_diagnostic_for
from routers.monuments import fetch_user_monuments
from services import stripe_billing as billing

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Les trois seaux « positifs » : le dashboard et la liste des projets comptent
# les aides identifiées et lisent leurs dates limites. Les non éligibles ne sont
# affichées que sur la page d'un projet, qui recalcule son diagnostic complet.
_DIGEST_BUCKETS = ("aidesEligibles", "aidesPotentiellementEligibles", "aidesAtteignables")


def build_digest(result: dict, monument_id: str, *, locked: bool = False) -> dict:
    """Réduit un diagnostic complet à ce que les vignettes de projet affichent.

    Un diagnostic complet pèse ~1,7 Mo : l'essentiel vient des ~95 aides non
    éligibles et de leurs conditions détaillées, dont le dashboard ne lit rien.
    Il n'en a besoin que de compteurs, de deux montants et des dates limites.
    """
    digest: dict = {
        "monumentId": monument_id,
        "montantPotentielTotal": result.get("montantPotentielTotal"),
        "montantAtteignableTotal": result.get("montantAtteignableTotal"),
    }
    for bucket in _DIGEST_BUCKETS:
        digest[bucket] = [
            {
                "aide": {
                    "id": match["aide"]["id"],
                    # Le nom alimente l'échéancier du projet : sur un projet non
                    # débloqué, il ne doit pas plus sortir d'ici que du
                    # diagnostic complet.
                    "nom": LOCKED_AIDE_LABEL if locked else match["aide"]["nom"],
                    "categorie": match["aide"]["categorie"],
                    "permanent": match["aide"].get("permanent", False),
                    "dateLimite": match["aide"].get("dateLimite"),
                    "montantMax": match["aide"].get("montantMax"),
                },
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
    monuments, population_by_code = fetch_user_monuments(supabase, user_id)
    if not monuments:
        return {"monuments": [], "dossiers": [], "digests": {}, "suivis": {}}

    monument_ids = [m["id"] for m in monuments]

    dossiers = (
        supabase.table("dossiers")
        .select("*")
        .in_("monument_id", monument_ids)
        .order("date_derniere_modification", desc=True)
        .execute()
        .data
    ) or []

    # Les suivis restent filtrés par utilisateur, comme /monuments/{id}/aide-suivis.
    suivi_rows = (
        supabase.table("aide_suivis")
        .select("*")
        .in_("monument_id", monument_ids)
        .eq("user_id", user_id)
        .execute()
        .data
    ) or []
    suivis: dict[str, list[dict]] = {mid: [] for mid in monument_ids}
    for row in suivi_rows:
        suivis.setdefault(row["monument_id"], []).append(row)

    # Droits d'accès lus UNE fois pour tout le dashboard : un abonnement ouvre
    # tous les projets, sinon seuls les projets payés à l'unité sont nommés.
    access = billing.access_snapshot(supabase, user_id)
    unlocked = set(access["unlockedMonumentIds"])
    all_access = access["allAccess"]

    # Un diagnostic par projet, avec les réponses déjà enregistrées du
    # questionnaire — exactement ce que le frontend demandait monument par
    # monument, puis réduit à son digest avant de partir sur le réseau.
    digests = {
        m["id"]: build_digest(
            deterministic_diagnostic_for(
                m,
                population_by_code.get(m.get("code_insee") or ""),
                m.get("questionnaire") or {},
            ),
            m["id"],
            locked=not all_access and m["id"] not in unlocked,
        )
        for m in monuments
    }

    return {
        "monuments": monuments,
        "dossiers": dossiers,
        "digests": digests,
        "suivis": suivis,
    }
