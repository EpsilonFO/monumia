"""Insert Loi Malraux aid into Supabase aides_v2 tables."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

aide = (
    supabase.table("aides_v2")
    .insert(
        {
            "nom": "Loi Malraux",
            "nom_court": "Malraux",
            "description": "Réduction d'impôt sur le revenu pour les travaux de restauration d'immeubles anciens dans les Sites Patrimoniaux Remarquables (SPR).",
            "description_longue": "La loi Malraux offre une réduction d'impôt pour les investisseurs effectuant des travaux de restauration dans les quartiers anciens dégradés (SPR). L'immeuble doit être loué comme habitation principale et les travaux doivent être supervisés par un Architecte des Bâtiments de France.",
            "categorie": "fiscalite",
            "type": "deduction_fiscale",
            "organisme": "État français - Ministère des Finances",
            "montant_max": 400000,
            "taux_max": 30,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": True,
            "conditions_eligibilite_detail": """- Périmètre : immeubles situés dans un Site Patrimonial Remarquable (SPR)
- Architecture obligatoire : travaux supervisés par un Architecte des Bâtiments de France (ABF)
- Plafond de dépenses : 400 000 € maximum sur 4 ans
- Mise en location : obligation de louer la propriété comme habitation principale dans les 12 mois suivant la fin des travaux
- Durée de location : au minimum 9 ans après la fin des travaux
- Réduction d'impôt : jusqu'à 30 % du montant investi""",
            "demarche_description": "1. Vérifier que l'immeuble est situé dans un SPR\n2. Faire établir un dossier par un ABF\n3. Réaliser les travaux sous supervision\n4. Mettre en location en tant qu'habitation principale\n5. Conserver la location pendant 9 ans minimum\n6. Déclarer la réduction fiscale auprès des impôts",
            "documents_requis": [
                "certificat_architecte",
                "justificatif_location",
                "factures_travaux",
                "attestation_spr",
            ],
            "delai_instruction": "Variable selon collectivités",
            "date_ouverture": None,
            "date_limite": None,
            "permanent": True,
            "url_officielle": "https://www.impots.gouv.fr/particulier/immeubles-speciaux-0",
            "formulaire_url": None,
            "tags": ["defiscalisation", "immobilier_ancien", "location", "spr"],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]

# Critères structurés
supabase.table("aides_protections").insert(
    [
        {"aide_id": aide_id, "protection_code": "spr"},
    ]
).execute()

supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
    ]
).execute()

supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "toiture"},
    ]
).execute()

print(f"✓ Aide insérée : Loi Malraux ({aide_id})")
