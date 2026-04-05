"""
Seed: Fonds Chaleur (ADEME) — aide à l'installation de chauffage renouvelable.

Run:
    cd backend && python scripts/seed_aide_fonds_chaleur.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = (
    supabase.table("aides_v2")
    .insert(
        {
            "nom": "Fonds Chaleur — Contrat Chaleur Renouvelable (ADEME)",
            "nom_court": "Fonds Chaleur ADEME",
            "description": "Subvention de l'ADEME pour les installations de production de chaleur ou de froid à partir d'énergies renouvelables et de récupération (biomasse, géothermie, solaire thermique, réseaux de chaleur).",
            "description_longue": (
                "Le Fonds Chaleur, géré par l'ADEME depuis 2009, est le principal dispositif "
                "national de soutien à la production de chaleur et de froid renouvelables. "
                "Il finance les études de faisabilité et les investissements dans les "
                "installations utilisant la biomasse, la géothermie, le solaire thermique, "
                "l'aérothermie, la récupération de chaleur fatale et les réseaux de chaleur/froid. "
                "Les bénéficiaires sont les collectivités territoriales, les entreprises et "
                "les associations (les particuliers ne sont pas éligibles directement). "
                "Le Contrat Chaleur Renouvelable (patrimonial ou territorial) permet de "
                "regrouper plusieurs projets en un seul dossier, y compris pour des bâtiments "
                "patrimoniaux nécessitant une rénovation de leur système de chauffage."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "ADEME (Agence de la Transition Écologique)",
            "montant_max": None,
            "taux_max": 60,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Bénéficiaires : collectivités territoriales, entreprises (TPE, PME, ETI, grandes entreprises), associations. Les particuliers ne sont PAS éligibles.\n"
                "- Le bâtiment doit être un bâtiment collectif (habitat collectif, tertiaire, industriel, agricole). Les maisons individuelles sont exclues.\n"
                "- Taux d'aide variable selon la technologie :\n"
                "  • Réseaux de chaleur et de froid : jusqu'à 60 % des investissements\n"
                "  • Biomasse, solaire thermique, géothermie : jusqu'à 45 % des investissements\n"
                "  • Récupération de chaleur fatale : jusqu'à 30 % des investissements\n"
                "- Bonus PME : +10 à +20 % supplémentaires pour les petites et moyennes entreprises\n"
                "- Seuils techniques minimaux par technologie :\n"
                "  • Biomasse/bois : production minimale de 1 200 MWh/an (collectif/tertiaire) ou 1 200 à 12 000 MWh/an (industrie/agriculture)\n"
                "  • Solaire thermique : surface de capteurs ≥ 25 m² (≥ 10 m² en DOM)\n"
                "  • Géothermie : production EnR minimale de 25 MWh/an\n"
                "  • Réseaux de chaleur : alimentation globale d'au moins 65 % en EnR&R\n"
                "- Le Contrat Chaleur Renouvelable patrimonial (durée max 6 ans) permet de regrouper au moins 3 installations sur un même patrimoine\n"
                "- Le Contrat Chaleur Renouvelable territorial (durée max 4 ans) regroupe des projets à l'échelle d'un territoire\n"
                "- Cumul possible avec les aides régionales (FEDER), les Certificats d'Économies d'Énergie (CEE), sous réserve du respect des règles d'encadrement des aides publiques\n"
                "- Le demandeur doit être à jour de ses obligations fiscales et sociales\n"
                "- Pour les monuments historiques : l'installation de chauffage renouvelable doit être compatible avec les contraintes de conservation du bâtiment et validée par l'ABF/DRAC si le bâtiment est protégé\n"
                "- Les études de faisabilité, l'assistance à maîtrise d'ouvrage et les investissements en équipements sont tous finançables"
            ),
            "demarche_description": (
                "1. Contacter la direction régionale de l'ADEME pour vérifier l'éligibilité du projet\n"
                "2. Réaliser une étude de faisabilité (finançable par le Fonds Chaleur)\n"
                "3. Créer un compte sur la plateforme AGIR (agirpourlatransition.ademe.fr)\n"
                "4. Déposer le dossier de demande en ligne avec les pièces justificatives\n"
                "5. Instruction par la direction régionale ADEME\n"
                "6. Notification de la décision et conventionnement\n"
                "7. Réalisation des travaux puis demande de versement sur justificatifs"
            ),
            "documents_requis": [
                "Formulaire de demande ADEME complété",
                "Étude de faisabilité énergétique",
                "Devis détaillés des équipements et travaux",
                "Plan de financement prévisionnel",
                "Justificatifs de situation fiscale et sociale à jour",
                "Attestation de propriété ou bail du bâtiment",
                "Pour les MH : avis de l'ABF ou autorisation DRAC si bâtiment protégé",
            ],
            "delai_instruction": "3 à 6 mois",
            "permanent": True,
            "url_officielle": "https://fondschaleur.ademe.fr/",
            "formulaire_url": "https://agirpourlatransition.ademe.fr/entreprises/aides-financieres/catalogue/2026/contrat-chaleur-renouvelable",
            "tags": [
                "chauffage",
                "énergie renouvelable",
                "biomasse",
                "géothermie",
                "solaire thermique",
                "réseau de chaleur",
                "transition énergétique",
                "ADEME",
                "décarbonation",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte spécifique (tous types de bâtiments)
# → on n'insère rien dans aides_protections

# Propriétaires : collectivités, entreprises, associations (pas les particuliers)
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "mixte"},
    ]
).execute()
print("  ✓ Propriétaires éligibles insérés")

# Travaux : chauffage, ventilation, étude préalable
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "chauffage"},
        {"aide_id": aide_id, "travaux_code": "ventilation"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    ]
).execute()
print("  ✓ Travaux éligibles insérés")

# Régions : aide nationale, pas de contrainte → on n'insère rien

# Départements : pas de contrainte → on n'insère rien

# Segments : communes et BTP (pas les particuliers)
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
        {"aide_id": aide_id, "segment_code": "btp"},
    ]
).execute()
print("  ✓ Segments éligibles insérés")

# État de conservation : pas de contrainte → on n'insère rien

print(f"\n✅ Fonds Chaleur ADEME inséré avec succès (id: {aide_id})")
