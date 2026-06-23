"""Insert Exonération Taxe Foncière aid into Supabase aides_v3 tables."""

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
            "nom": "Exonération de taxe foncière pour les monuments historiques",
            "nom_court": "Exo. Taxe Foncière MH",
            "description": "Exemption de taxe foncière pendant 25 ans pour les propriétaires de monuments historiques effectuant des travaux de restauration.",
            "description_longue": "Les propriétaires de monuments classés ou inscrits qui effectuent des travaux de restauration bénéficient d'une exonération complète de taxe foncière pendant 25 ans à compter de l'année suivant celle de la fin des travaux.",
            "categorie": "fiscalite",
            "type": "exoneration",
            "organisme": "État français - Collectivités locales",
            "montant_max": None,
            "taux_max": 100,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": True,
            "conditions_eligibilite_detail": """- Classification : immeuble classé au titre des monuments historiques ou inscrit à l'inventaire supplémentaire des monuments historiques (ISMH)
- Ou : immeuble ayant le label Fondation du Patrimoine
- Ou : immeuble non classé mais ouvert au public :
  • 50 jours par an minimum (dont 25 non ouvrables d'avril à septembre inclus)
  • OU 40 jours pendant les mois de juillet, août et septembre
- Durée minimale de conservation : 15 ans
- Travaux : réalisés sous le contrôle des architectes des bâtiments de France (ABF)
- Durée d'exonération : 25 ans à compter de l'année suivant celle de fin des travaux
- Exonération complète : 100 % de la taxe foncière""",
            "demarche_description": "1. Vérifier le classement ou l'inscription de l'immeuble\n2. Engager un ABF pour superviser les travaux\n3. Réaliser les travaux de restauration\n4. Déclarer la fin des travaux auprès de la mairie et de la DRAC\n5. Déposer une demande d'exonération auprès des services fiscaux locaux\n6. Bénéficier de l'exonération pendant 25 ans",
            "documents_requis": [
                "certificat_architecte",
                "decision_classement_ou_inscription",
                "factures_travaux",
                "attestation_fin_travaux",
            ],
            "delai_instruction": "3 à 6 mois",
            "date_ouverture": None,
            "date_limite": None,
            "permanent": True,
            "url_officielle": "https://www.legifrance.gouv.fr/codes/section_lc/LEGITEXT000006069574/LEGISCTA000006179305/",
            "formulaire_url": None,
            "tags": ["exoneration_fiscale", "monument_historique", "taxe_fonciere"],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]

# Critères structurés
supabase.table("aides_protections").insert(
    [
        {"aide_id": aide_id, "protection_code": "classe"},
        {"aide_id": aide_id, "protection_code": "inscrit"},
    ]
).execute()

supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()

supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
    ]
).execute()

print(f"✓ Aide insérée : Exonération de taxe foncière pour MH ({aide_id})")
