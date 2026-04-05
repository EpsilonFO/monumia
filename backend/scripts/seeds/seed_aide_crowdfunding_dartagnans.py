"""
Seed: Crowdfunding Dartagnans — Financement participatif patrimoine.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_crowdfunding_dartagnans.py
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
    supabase.table("aides_v2")
    .insert(
        {
            "nom": "Crowdfunding patrimoine — Dartagnans",
            "nom_court": "Dartagnans",
            "description": "Plateforme de financement participatif (crowdfunding) dédiée à la préservation et la valorisation du patrimoine français : châteaux, monuments historiques, églises, patrimoine vernaculaire.",
            "description_longue": (
                "Dartagnans est la première plateforme française de crowdfunding entièrement dédiée au "
                "patrimoine. Créée en 2015, elle permet aux propriétaires de monuments historiques, "
                "châteaux, églises et tout type de patrimoine de lancer des campagnes de collecte de "
                "dons auprès du grand public. Dartagnans accompagne les porteurs de projet dans la "
                "mise en place de leur campagne (stratégie de communication, contreparties, objectifs). "
                "En cas de succès, Dartagnans prélève une commission de 8 % HT sur les fonds collectés. "
                "Particularité : même si l'objectif de collecte n'est pas atteint, les fonds récoltés sont "
                "versés au porteur de projet. Depuis sa création, Dartagnans a accompagné plus de "
                "1 000 propriétaires et gestionnaires de monuments historiques et collecté plus de "
                "15 millions d'euros pour le patrimoine. La communauté compte plus de 50 000 « sauveurs "
                "de châteaux » dans le monde."
            ),
            "categorie": "mecenat",
            "type": "souscription",
            "organisme": "Dartagnans SAS",
            "montant_max": None,
            "taux_max": None,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Tout propriétaire de monument ou site patrimonial peut déposer un projet sur Dartagnans\n"
                "- Propriétaires éligibles : personnes physiques, SCI, associations, communes, collectivités, fondations\n"
                "- Tous les types de patrimoine sont acceptés : châteaux, manoirs, églises, chapelles, patrimoine industriel, vernaculaire, jardins\n"
                "- Tous les niveaux de protection sont acceptés : classé MH, inscrit MH, non protégé\n"
                "- Les projets doivent concerner la restauration, la sauvegarde ou la valorisation du patrimoine\n"
                "- Le porteur de projet définit librement son objectif de collecte\n"
                "- Des contreparties doivent être proposées aux donateurs (visites, invitations, expériences culturelles)\n"
                "- Commission Dartagnans : 8 % HT sur les fonds collectés en cas de succès\n"
                "- Même si l'objectif n'est pas atteint, les fonds récoltés sont versés au porteur de projet\n"
                "- Les dons effectués via Dartagnans peuvent ouvrir droit à une réduction d'impôt pour les donateurs (si le bénéficiaire est éligible au mécénat)\n"
                "- Le porteur de projet doit fournir un descriptif détaillé du site, des travaux envisagés et un budget\n"
                "- Dartagnans accompagne le porteur de projet dans la stratégie de communication de la campagne\n"
                "- La durée d'une campagne est généralement de 60 à 90 jours\n"
                "- Il n'y a pas de montant minimum ou maximum de collecte imposé par la plateforme"
            ),
            "demarche_description": (
                "1. Créer un compte sur dartagnans.fr et soumettre son projet patrimonial\n"
                "2. Échange avec l'équipe Dartagnans pour définir la stratégie de campagne (objectif, durée, contreparties)\n"
                "3. Préparer les visuels, le descriptif du projet et les contreparties pour les donateurs\n"
                "4. Lancement de la campagne de crowdfunding sur la plateforme\n"
                "5. Communication et mobilisation de la communauté pendant la durée de la campagne\n"
                "6. Collecte des fonds à l'issue de la campagne (versement même si objectif non atteint)\n"
                "7. Réalisation des travaux et envoi des contreparties aux donateurs"
            ),
            "documents_requis": [
                "Descriptif du site patrimonial (photos, historique)",
                "Programme de travaux ou projet de valorisation",
                "Budget prévisionnel",
                "Preuve de propriété ou autorisation du propriétaire",
                "Liste des contreparties proposées aux donateurs",
            ],
            "delai_instruction": "2 à 4 semaines (validation du projet)",
            "permanent": True,
            "url_officielle": "https://dartagnans.fr/",
            "formulaire_url": "https://dartagnans.fr/",
            "tags": [
                "crowdfunding",
                "financement participatif",
                "Dartagnans",
                "patrimoine",
                "dons",
                "mécénat",
                "châteaux",
                "restauration",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : tous niveaux
supabase.table("aides_protections").insert(
    [
        {"aide_id": aide_id, "protection_code": "classe"},
        {"aide_id": aide_id, "protection_code": "inscrit"},
        {"aide_id": aide_id, "protection_code": "non_protege"},
    ]
).execute()
print("  ✓ Protections insérées")

# Propriétaires : tous types
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : tous types de restauration
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "couverture"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "vitraux"},
        {"aide_id": aide_id, "travaux_code": "peintures_murales"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "mobilier"},
        {"aide_id": aide_id, "travaux_code": "parcs_jardins"},
        {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : nationale (pas de contrainte)

# Segments : tous segments
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
        {"aide_id": aide_id, "segment_code": "prive"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ Dartagnans inséré avec succès (id: {aide_id})")
