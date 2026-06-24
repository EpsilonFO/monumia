"""
Seed: Subvention DRAC — Travaux d'urgence sur Monuments Historiques.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_drac_travaux_urgence.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = (
    supabase.table("aides_v3")
    .insert(
        {
            "nom": "Subvention DRAC — Travaux d'urgence sur Monuments Historiques",
            "nom_court": "DRAC Urgence MH",
            "description": "Subvention d'urgence de l'État (DRAC) pour les travaux de sauvegarde immédiate sur monuments historiques en péril : étaiement, consolidation, couverture provisoire, mise hors d'eau.",
            "description_longue": (
                "La DRAC peut accorder une subvention d'urgence pour des travaux de sauvegarde immédiate "
                "sur des monuments historiques classés ou inscrits en situation de péril. Contrairement "
                "aux subventions classiques, la procédure est simplifiée et les travaux peuvent commencer "
                "dès que nécessaire, sans attendre l'accord formel de la DRAC. Le taux de subvention "
                "est de 40 % pour les classés et de 15 % pour les inscrits. Les travaux éligibles sont "
                "strictement limités aux interventions de sauvegarde : clôture de chantier, étaiement, "
                "consolidation d'urgence, couverture provisoire, purges, dépose d'éléments en péril. "
                "La programmation peut intervenir en année n-1 ou en début d'année n, offrant un "
                "traitement plus rapide que la procédure standard."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "Ministère de la Culture — Direction Régionale des Affaires Culturelles (DRAC)",
            "montant_max": None,
            "taux_max": 40,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": True,
            "conditions_eligibilite_detail": (
                "- Immeuble classé ou inscrit au titre des monuments historiques\n"
                "- Le monument doit être en situation de péril ou d'urgence sanitaire avérée\n"
                "- Taux de subvention pour les travaux d'urgence :\n"
                "  • Monument classé : jusqu'à 40 % des dépenses éligibles\n"
                "  • Monument inscrit : jusqu'à 15 % des dépenses éligibles\n"
                "- EXCEPTION à la règle de non-commencement : contrairement aux subventions classiques, les travaux d'urgence PEUVENT commencer dès que nécessaire, sans attendre l'accord de la DRAC\n"
                "- La date de début des travaux n'a pas d'impact sur l'attribution de la subvention\n"
                "- Le versement de la subvention intervient dès l'approbation (procédure accélérée)\n"
                "- Travaux éligibles strictement limités aux interventions de sauvegarde :\n"
                "  • Clôture de chantier et mise en sécurité du site\n"
                "  • Étaiement et consolidation d'urgence\n"
                "  • Couverture provisoire (bâchage, mise hors d'eau)\n"
                "  • Purges de matériaux dangereux\n"
                "  • Dépose et mise à l'abri d'éléments en péril (sculptures, vitraux, etc.)\n"
                "  • Maçonnerie d'urgence, charpente d'urgence, menuiserie d'urgence\n"
                "- Travaux NON éligibles : restauration définitive, aménagements, travaux de confort\n"
                "- Procédure simplifiée par rapport à la subvention classique\n"
                "- Documents requis : demande écrite du propriétaire, devis visés par l'architecte du patrimoine, photos attestant l'état de péril, plan de financement, RIB\n"
                "- Pour les collectivités : délibération du conseil municipal (ou décision de l'assemblée)\n"
                "- La programmation peut intervenir en année n-1 ou en début d'année n\n"
                "- Cumul possible avec d'autres aides d'urgence (département, région, Fondation du patrimoine)\n"
                "- Le caractère d'urgence doit être attesté par l'UDAP ou la CRMH\n"
                "- Assiette de calcul : HT pour les publics, TTC pour les privés"
            ),
            "demarche_description": (
                "1. Constater la situation de péril et alerter immédiatement l'UDAP (Unité Départementale de l'Architecture et du Patrimoine)\n"
                "2. Faire constater l'urgence par l'architecte du patrimoine ou l'ACMH\n"
                "3. Engager les travaux de sauvegarde dès que nécessaire (pas besoin d'attendre l'accord DRAC)\n"
                "4. Constituer le dossier en parallèle : demande écrite, devis visés par l'architecte, photos de l'état de péril, plan de financement\n"
                "5. Déposer la demande de subvention auprès de la DRAC\n"
                "6. Transmettre les justificatifs de dépenses pour versement"
            ),
            "documents_requis": [
                "Demande écrite du propriétaire",
                "Délibération du conseil municipal (si collectivité)",
                "Devis visés par l'architecte du patrimoine",
                "Photos attestant l'état de péril du monument",
                "Plan de financement",
                "RIB du maître d'ouvrage",
            ],
            "delai_instruction": "1 à 3 mois (procédure accélérée)",
            "permanent": True,
            "url_officielle": "https://www.culture.gouv.fr/thematiques/monuments-sites/interventions-demarches/subventions-et-dispositifs-fiscaux/les-immeubles-subventions-depenses-eligibles-et-non-eligibles",
            "formulaire_url": "https://demarche.numerique.gouv.fr/commencer/mh_subvention-etudes-travaux/dossier_vide",
            "tags": [
                "DRAC",
                "monuments historiques",
                "urgence",
                "péril",
                "sauvegarde",
                "mise hors d'eau",
                "étaiement",
                "subvention État",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : classé ET inscrit (les deux sont éligibles aux travaux d'urgence)
supabase.table("aides_protections").insert(
    [
        {"aide_id": aide_id, "protection_code": "classe"},
        {"aide_id": aide_id, "protection_code": "inscrit"},
    ]
).execute()
print("  ✓ Protections insérées")

# Propriétaires : tous types éligibles
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
        {"aide_id": aide_id, "proprietaire_code": "mixte"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : uniquement travaux d'urgence / sauvegarde
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "couverture"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
        {"aide_id": aide_id, "travaux_code": "vitraux"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale → pas de contrainte
# Segments : tous → pas de contrainte

# État de conservation : urgence = mauvais ou péril
supabase.table("aides_etats_conservation").insert(
    [
        {"aide_id": aide_id, "etat_conservation_code": "mauvais"},
        {"aide_id": aide_id, "etat_conservation_code": "peril"},
    ]
).execute()
print("  ✓ États de conservation insérés")

print(f"\n✅ DRAC Travaux d'urgence inséré avec succès (id: {aide_id})")
