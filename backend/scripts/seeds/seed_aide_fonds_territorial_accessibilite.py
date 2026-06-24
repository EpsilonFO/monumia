"""
Seed: Fonds Territorial d'Accessibilité (FTA).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_fonds_territorial_accessibilite.py
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
            "nom": "Fonds Territorial d'Accessibilité (FTA)",
            "nom_court": "FTA",
            "description": "Subvention de l'État couvrant jusqu'à 50 % des travaux de mise en accessibilité des ERP privés de 5e catégorie (commerces, restaurants, hôtels), plafonnée à 20 500 €, applicable aux monuments historiques accueillant du public.",
            "description_longue": (
                "Le Fonds Territorial d'Accessibilité (FTA), lancé en novembre 2023, est un dispositif "
                "de l'État qui subventionne à hauteur de 50 % les travaux et équipements de mise en "
                "accessibilité des établissements recevant du public (ERP) privés de 5e catégorie. "
                "Il concerne les micro-entreprises, TPE et PME (moins de 250 salariés, CA < 50 M€). "
                "Le plafond d'aide est de 20 500 € par ERP (20 000 € pour les travaux + 500 € pour "
                "le diagnostic d'accessibilité). Ce fonds est particulièrement intéressant pour les "
                "propriétaires de monuments historiques qui exploitent leur bien comme hébergement "
                "touristique (chambres d'hôtes, hôtel), restaurant, boutique ou espace d'exposition, "
                "car la mise en accessibilité de bâtiments anciens est souvent coûteuse en raison "
                "des contraintes architecturales. Les travaux éligibles incluent les rampes d'accès, "
                "la suppression de marches, les sanitaires adaptés, la signalétique, l'éclairage, "
                "les systèmes d'aide à l'audition, etc. ATTENTION : le guichet FTA a fermé le "
                "7 janvier 2026, plus aucune demande ne peut être déposée depuis le 8 janvier 2026."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "Direction Générale des Entreprises (DGE) / ASP",
            "montant_max": 20500,
            "taux_max": 50,
            "montant_min": None,
            "plancher": None,
            "base_ttc": True,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- ATTENTION : le guichet FTA a fermé le 7 janvier 2026. Aucune nouvelle demande n'est possible depuis le 8 janvier 2026\n"
                "- L'ERP doit être de 5e catégorie (capacité d'accueil la plus faible)\n"
                "- Types d'ERP éligibles de base : M (magasins), N (restaurants/débits de boissons), O (hôtels/pensions de famille), W (banques), U (sanitaire)\n"
                "- Extension possible : d'autres types d'ERP de 5e catégorie peuvent être éligibles sur décision du sous-préfet référent handicap du département\n"
                "- L'exploitant doit être une micro-entreprise, TPE ou PME : moins de 250 salariés ET CA annuel HT < 50 M€ ou total bilan < 43 M€\n"
                "- L'ERP doit être inaccessible ou partiellement accessible avec un projet de mise en accessibilité\n"
                "- Montant de l'aide : 50 % des dépenses éligibles, plafonné à :\n"
                "  • 20 000 € pour les travaux et équipements de mise en accessibilité\n"
                "  • 500 € pour le diagnostic d'accessibilité ou l'assistance à maîtrise d'ouvrage\n"
                "  • Total maximum : 20 500 € par ERP\n"
                "- Dépenses éligibles : rampes d'accès, suppression de marches, élargissement de portes, sanitaires adaptés (barres d'appui, espace de manœuvre), signalétique, éclairage, boucles magnétiques, guidage podotactile\n"
                "- Dépenses NON éligibles : travaux de gros œuvre, rénovation générale, mise aux normes non liée à l'accessibilité\n"
                "- Pour les monuments historiques : les travaux d'accessibilité sont éligibles si l'ERP est de 5e catégorie (chambre d'hôtes, restaurant dans un château, boutique…)\n"
                "- Les dérogations ABF peuvent être nécessaires si les travaux modifient l'aspect extérieur d'un monument protégé\n"
                "- L'aide est cumulable avec d'autres dispositifs (crédit d'impôt accessibilité PME, aides départementales)\n"
                "- Un seul dossier par ERP"
            ),
            "demarche_description": (
                "1. ATTENTION : le guichet est fermé depuis le 8 janvier 2026\n"
                "2. (Historique) Réaliser un diagnostic d'accessibilité de l'ERP\n"
                "3. (Historique) Obtenir des devis pour les travaux de mise en accessibilité\n"
                "4. (Historique) Déposer la demande en ligne sur la plateforme de l'ASP\n"
                "5. (Historique) Instruction par la DDT ou la DDTM du département\n"
                "6. (Historique) Notification de l'aide et réalisation des travaux\n"
                "7. (Historique) Envoi des justificatifs de paiement à l'ASP pour versement de la subvention"
            ),
            "documents_requis": [
                "Diagnostic d'accessibilité de l'ERP",
                "Devis des travaux de mise en accessibilité",
                "Attestation sur l'honneur du statut PME/TPE",
                "Justificatif de propriété ou bail commercial",
                "Photos de l'état existant",
                "Plan de l'ERP",
                "Autorisation ABF si monument protégé",
            ],
            "delai_instruction": "2 à 4 mois",
            "permanent": False,
            "date_limite": "2026-01-07",
            "url_officielle": "https://www.entreprises.gouv.fr/espace-entreprises/appels-a-projets-et-appels-a-manifestation-d-interet/fonds-territorial",
            "formulaire_url": "https://www.asp.gouv.fr/aides/fonds-territorial-accessibilite",
            "tags": [
                "FTA",
                "accessibilité",
                "handicap",
                "ERP",
                "mise aux normes",
                "PME",
                "TPE",
                "rampe",
                "travaux",
                "monuments historiques",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : tous niveaux (l'ERP peut être dans un MH ou non)
supabase.table("aides_protections").insert(
    [
        {"aide_id": aide_id, "protection_code": "classe"},
        {"aide_id": aide_id, "protection_code": "inscrit"},
        {"aide_id": aide_id, "protection_code": "non_protege"},
    ]
).execute()
print("  ✓ Protections insérées")

# Propriétaires : privés uniquement (ERP privés)
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : accessibilité uniquement
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "accessibilite"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : nationale

# Segments : privé
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "prive"},
    ]
).execute()
print("  ✓ Segments insérés")

print(f"\n✅ FTA inséré avec succès (id: {aide_id})")
