"""
Seed: Programme SARE (Service d'Accompagnement pour la Rénovation Énergétique).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_programme_sare.py
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
            "nom": "Programme SARE — Service d'Accompagnement pour la Rénovation Énergétique",
            "nom_court": "Programme SARE",
            "description": "Programme d'accompagnement gratuit pour les particuliers et petits locaux tertiaires souhaitant engager une rénovation énergétique. Conseils, orientation vers les aides, audit énergétique.",
            "description_longue": (
                "Le programme SARE (Service d'Accompagnement pour la Rénovation Énergétique) est un "
                "programme national financé par les Certificats d'Économies d'Énergie (CEE), porté par "
                "l'ADEME et co-porté au niveau régional par les collectivités territoriales. Il finance "
                "le réseau des Espaces Conseil France Rénov' qui offrent un accompagnement gratuit et "
                "indépendant aux ménages souhaitant rénover leur logement : information sur les aides "
                "disponibles, conseils techniques, orientation vers des professionnels qualifiés, aide "
                "au montage de dossiers. Le programme couvre également l'accompagnement des petits locaux "
                "tertiaires privés (commerces, bureaux, restaurants). Aucune condition de ressources "
                "n'est requise. L'enveloppe globale est de 200 millions d'euros (2020-2024), financée "
                "à hauteur de 50 % par les CEE et cofinancée par les collectivités."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "ADEME — Agence de la Transition Écologique / Collectivités territoriales",
            "montant_max": None,
            "taux_max": 50,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": True,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Le programme SARE est un service d'accompagnement (conseil, orientation), pas une aide financière directe aux travaux\n"
                "- Il finance les Espaces Conseil France Rénov' qui accompagnent gratuitement les ménages\n"
                "- Bénéficiaires directs du financement SARE : collectivités territoriales volontaires (porteurs associés)\n"
                "- Bénéficiaires de l'accompagnement : tous les ménages sans condition de ressources\n"
                "  • Propriétaires occupants\n"
                "  • Propriétaires bailleurs\n"
                "  • Copropriétaires\n"
                "  • Petits professionnels du tertiaire (commerces, bureaux, restaurants)\n"
                "- Services proposés aux ménages :\n"
                "  • Information gratuite et indépendante sur la rénovation énergétique\n"
                "  • Conseils techniques sur les travaux à engager\n"
                "  • Orientation vers les aides financières mobilisables (MaPrimeRénov', CEE, éco-PTZ, aides locales)\n"
                "  • Aide au montage des dossiers de demande d'aide\n"
                "  • Orientation vers des professionnels RGE\n"
                "  • Audit énergétique dans certains cas\n"
                "- Pour les monuments historiques : les conseillers France Rénov' peuvent informer sur les aides mobilisables, mais ne sont pas spécialisés patrimoine\n"
                "  • Les travaux de rénovation énergétique sur MH doivent tenir compte des contraintes ABF\n"
                "  • Les conseillers peuvent orienter vers l'UDAP pour les aspects patrimoniaux\n"
                "- Financement du programme :\n"
                "  • Enveloppe globale : 200 millions d'euros\n"
                "  • Source : CEE (40 TWhc) à 5 €/MWhc\n"
                "  • Cofinancement : jusqu'à 50 % par le programme SARE, le reste par les collectivités locales\n"
                "- Modalités pour les collectivités :\n"
                "  • Signature d'une convention entre porteurs associés et financeurs\n"
                "  • Participation à la concertation territoriale préalable\n"
                "- Programme opérationnel depuis le 1er janvier 2020\n"
                "- Contact : réseau France Rénov' (numéro unique 0 808 800 700)"
            ),
            "demarche_description": (
                "1. Contacter l'Espace Conseil France Rénov' le plus proche (0 808 800 700 ou france-renov.gouv.fr)\n"
                "2. Bénéficier d'un rendez-vous gratuit avec un conseiller indépendant\n"
                "3. Recevoir des conseils personnalisés sur les travaux et les aides mobilisables\n"
                "4. Se faire accompagner dans le montage des dossiers d'aide\n"
                "5. Pour les collectivités : candidater comme porteur associé auprès de l'ADEME régionale"
            ),
            "documents_requis": [
                "Aucun document requis pour bénéficier du conseil gratuit",
                "Pour les collectivités porteurs : convention de partenariat avec l'ADEME",
            ],
            "delai_instruction": "Immédiat (prise de rendez-vous avec un conseiller France Rénov')",
            "permanent": True,
            "url_officielle": "https://www.ecologie.gouv.fr/politiques-publiques/sare-service-daccompagnement-renovation-energetique",
            "formulaire_url": None,
            "tags": [
                "SARE",
                "France Rénov",
                "accompagnement",
                "rénovation énergétique",
                "ADEME",
                "conseil gratuit",
                "CEE",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte (accompagnement ouvert à tous)

# Propriétaires : tous types (accompagnement gratuit pour tous)
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
        {"aide_id": aide_id, "proprietaire_code": "mixte"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : accompagnement sur tous travaux de rénovation énergétique
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "chauffage"},
        {"aide_id": aide_id, "travaux_code": "plomberie"},
        {"aide_id": aide_id, "travaux_code": "ventilation"},
        {"aide_id": aide_id, "travaux_code": "electricite"},
        {"aide_id": aide_id, "travaux_code": "protection_solaire"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : national → pas de contrainte
# Segments : tous → pas de contrainte
# État de conservation : pas de contrainte

print(f"\n✅ Programme SARE inséré avec succès (id: {aide_id})")
