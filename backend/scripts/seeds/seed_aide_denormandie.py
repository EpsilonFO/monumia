"""Insert Dispositif Denormandie aid into Supabase aides_v3 tables."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

aide = (
    supabase.table("aides_v3")
    .insert(
        {
            "nom": "Dispositif Denormandie",
            "nom_court": "Denormandie",
            "description": "Réduction d'impôt pour la rénovation d'immeubles anciens dans les communes prioritaires, mis en location.",
            "description_longue": "Le dispositif Denormandie encourage la rénovation de logements anciens situés dans certaines communes prioritaires (Action cœur de ville, ORT, habitat dégradé) en offrant une réduction d'impôt pouvant atteindre 21 % du prix net de revient.",
            "categorie": "fiscalite",
            "type": "deduction_fiscale",
            "organisme": "État français - Ministère des Finances",
            "montant_max": 300000,
            "taux_max": 21,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": """- Périmètre : communes Action cœur de ville, communes avec convention ORT (Opération de Revitalisation de Territoire), ou communes avec besoin particulier de réhabilitation
- Plafond : 300 000 € maximum pour l'investissement (et 5 500 m² de surface habitable)
- Type de bien : logement ancien (non meublé) ou local transformé en habitation
- Travaux requis : amélioration/rénovation du logement
- Mise en location : obligation de louer en tant qu'habitation principale
- Durée de location : 6, 9 ou 12 ans (selon le taux de réduction choisi)
- Réduction d'impôt : jusqu'à 21 % du prix net de revient
- Extension depuis avril 2024 : copropriétés en grande difficulté financière ou COPD (Opération de requalification des copropriétés dégradées)""",
            "demarche_description": "1. Vérifier que la commune est éligible au dispositif\n2. Acquérir le logement ancien à rénover\n3. Réaliser les travaux d'amélioration\n4. Mettre le logement en location non meublée\n5. Respecter la durée de location exigée (6, 9 ou 12 ans)\n6. Déclarer la réduction fiscale auprès des impôts",
            "documents_requis": [
                "contrat_achat",
                "devis_travaux",
                "factures_travaux",
                "contrat_location",
                "attestation_commune_eligible",
            ],
            "delai_instruction": "Variable selon administration locale",
            "date_ouverture": None,
            "date_limite": None,
            "permanent": True,
            "url_officielle": "https://www.economie.gouv.fr/particuliers/gerer-mon-argent/investir-dans-limmobilier/renovation-dun-logement-ancien-tout-savoir",
            "formulaire_url": None,
            "tags": [
                "defiscalisation",
                "immobilier_ancien",
                "location",
                "revitalisation",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]

# Critères structurés
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
        {"aide_id": aide_id, "travaux_code": "electricite"},
        {"aide_id": aide_id, "travaux_code": "plomberie"},
    ]
).execute()

print(f"✓ Aide insérée : Dispositif Denormandie ({aide_id})")
