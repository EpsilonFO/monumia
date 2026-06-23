"""
Seed: Subvention DRAC — Monuments Historiques Classés.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_drac_mh_classes.py
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
            "nom": "Subvention DRAC — Monuments Historiques Classés",
            "nom_court": "DRAC MH Classés",
            "description": "Subvention de l'État (DRAC) pour les travaux de conservation, restauration et mise en valeur des immeubles classés au titre des monuments historiques. Taux moyen de 40 %.",
            "description_longue": (
                "Les propriétaires (publics ou privés) d'immeubles classés au titre des monuments "
                "historiques peuvent solliciter une subvention auprès de la Direction Régionale des "
                "Affaires Culturelles (DRAC) pour financer des travaux de conservation, de restauration "
                "et de mise en valeur des parties protégées. Le taux de base est de 40 % des dépenses "
                "éligibles (jusqu'à 50 % dans certains cas exceptionnels). L'assiette est calculée HT "
                "pour les propriétaires publics (TVA récupérable) et TTC pour les propriétaires privés. "
                "La maîtrise d'œuvre est obligatoirement assurée par un Architecte en Chef des Monuments "
                "Historiques (ACMH) pour les immeubles classés. Les travaux ne doivent pas commencer "
                "avant l'obtention de l'accord de la DRAC. L'aide n'est pas versée de plein droit et "
                "dépend des crédits budgétaires disponibles."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "Ministère de la Culture — Direction Régionale des Affaires Culturelles (DRAC)",
            "montant_max": None,
            "taux_max": 50,
            "montant_min": 1000,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": True,
            "conditions_eligibilite_detail": (
                "- Immeuble classé au titre des monuments historiques (classement total ou partiel)\n"
                "- Taux de base : 40 % des dépenses éligibles (moyenne nationale)\n"
                "- Taux modulable selon les critères suivants :\n"
                "  • Urgence sanitaire du bâtiment (état de péril)\n"
                "  • Existence d'un plan de gestion validé par la DRAC\n"
                "  • Contractualisation pluriannuelle avec la DRAC\n"
                "  • Ouverture au public (minimum 40 jours/an incluant les Journées Européennes du Patrimoine)\n"
                "  • Intérêt patrimonial exceptionnel de l'édifice\n"
                "- Taux maximum théorique : 50 % (cas exceptionnels)\n"
                "- Montant minimum de subvention : 1 000 € (sauf objets mobiliers)\n"
                "- La subvention n'est pas un droit : elle dépend des crédits budgétaires disponibles\n"
                "- Les travaux ne doivent PAS avoir commencé avant réception de l'accusé de réception de la demande par la DRAC\n"
                "- La demande doit être déposée l'année précédant le début des travaux (année n-1)\n"
                "- Maîtrise d'œuvre obligatoire par un Architecte en Chef des Monuments Historiques (ACMH)\n"
                "- Autorisation de travaux sur monument classé obligatoire (délivrée par le Préfet de région)\n"
                "- Assiette de calcul : HT pour les propriétaires publics (TVA récupérable via FCTVA), TTC pour les propriétaires privés\n"
                "- Dépenses éligibles : travaux d'entretien, réparation, restauration, mise en sécurité incendie strictement nécessaire à la conservation, études préalables, maîtrise d'œuvre\n"
                "- Dépenses NON éligibles : aménagements intérieurs non patrimoniaux, création de mobilier, installations électriques / chauffage / plomberie courantes, ascenseurs, rampes d'accessibilité, éclairages décoratifs, extensions\n"
                "- Les collectivités territoriales doivent assurer un autofinancement minimum de 20 % du financement public total (sauf dérogation préfectorale)\n"
                "- Plafond annuel pour les propriétaires privés : 300 000 € par an (en région Auvergne-Rhône-Alpes, variable selon les régions)\n"
                "- Cumul possible avec d'autres aides publiques (région, département, Fondation du patrimoine, mécénat) dans la limite de 80 % du coût total\n"
                "- Contrôle scientifique et technique obligatoire par l'UDAP et la CRMH\n"
                "- Versement sur justificatifs après réalisation des travaux (avance possible sous conditions)"
            ),
            "demarche_description": (
                "1. Prendre contact avec l'Unité Départementale de l'Architecture et du Patrimoine (UDAP) pour un conseil en amont\n"
                "2. Obtenir l'autorisation de travaux sur monument classé auprès du Préfet de région\n"
                "3. Constituer le dossier : devis détaillés par lots, photos de l'état existant, rapports techniques, plan de financement\n"
                "4. Déposer la demande de subvention auprès de la DRAC (année n-1 par rapport au début des travaux)\n"
                "5. Attendre l'accusé de réception et la décision d'attribution avant de commencer les travaux\n"
                "6. Réaliser les travaux sous maîtrise d'œuvre ACMH et contrôle de la CRMH\n"
                "7. Transmettre les justificatifs de dépenses pour obtenir le versement de la subvention"
            ),
            "documents_requis": [
                "Preuve de propriété du bien",
                "Autorisation de travaux sur monument classé",
                "Devis détaillés par lots de travaux",
                "Photos de l'état existant du monument",
                "Rapport technique ou étude préalable (si nécessaire)",
                "Plan de financement prévisionnel",
                "Délibération du conseil municipal (si collectivité)",
                "RIB du maître d'ouvrage",
            ],
            "delai_instruction": "3 à 12 mois",
            "permanent": True,
            "url_officielle": "https://www.culture.gouv.fr/thematiques/monuments-sites/interventions-demarches/subventions-et-dispositifs-fiscaux/les-immeubles-subventions-depenses-eligibles-et-non-eligibles",
            "formulaire_url": "https://demarche.numerique.gouv.fr/commencer/mh_subvention-etudes-travaux/dossier_vide",
            "tags": [
                "DRAC",
                "monuments historiques",
                "classé",
                "restauration",
                "conservation",
                "subvention État",
                "ACMH",
                "patrimoine protégé",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : uniquement classé
supabase.table("aides_protections").insert(
    [
        {"aide_id": aide_id, "protection_code": "classe"},
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

# Travaux éligibles : conservation, restauration, études
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "couverture"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "vitraux"},
        {"aide_id": aide_id, "travaux_code": "peintures_murales"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
        {"aide_id": aide_id, "travaux_code": "mobilier"},
        {"aide_id": aide_id, "travaux_code": "orgues"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale → pas de contrainte (aucune insertion)

# Segments : tous segments éligibles → pas de contrainte (aucune insertion)

# État de conservation : pas de contrainte (aucune insertion)

print(f"\n✅ DRAC MH Classés inséré avec succès (id: {aide_id})")
