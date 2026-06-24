"""
Seed: Aide régionale patrimoine — Auvergne-Rhône-Alpes.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_region_auvergne_rhone_alpes.py
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
            "nom": "Fonds Patrimoine Remarquable — Région Auvergne-Rhône-Alpes",
            "nom_court": "Patrimoine Remarquable AURA",
            "description": "Subvention de la Région AURA pour la restauration du patrimoine non protégé, en partenariat avec la Fondation du patrimoine. Jusqu'à 80 % pour les petits projets (< 20 000 €), 70 % plafonné à 50 000 € au-delà.",
            "description_longue": (
                "La Région Auvergne-Rhône-Alpes intervient via le fonds « Patrimoine Remarquable » "
                "(délibération CP-2022-12/13-84-7187, règlement 2023-2025), en partenariat avec la "
                "Fondation du patrimoine. Ce dispositif cible principalement le patrimoine non protégé "
                "situé dans les communes rurales et centres-bourgs de moins de 20 000 habitants. "
                "Les projets sont sélectionnés par un jury annuel, avec un budget de 600 000 € par an. "
                "Pour les travaux inférieurs à 20 000 €, l'aide peut atteindre 80 % du montant. "
                "Au-delà, le taux descend à 70 %, plafonné à 50 000 €. Une souscription publique "
                "ayant collecté au moins 5 % du montant des travaux est un prérequis. Les propriétaires "
                "privés doivent présenter un projet d'ouverture au public et d'animation. "
                "Pour le patrimoine protégé MH (édifices, jardins, mobilier), la Région étudie des aides "
                "complémentaires au cas par cas tout au long de l'année (travaux > 40 000 € pour les "
                "édifices, > 5 000 € pour le mobilier)."
            ),
            "categorie": "region",
            "type": "subvention",
            "organisme": "Région Auvergne-Rhône-Alpes",
            "montant_max": 50000,
            "taux_max": 80,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": 20000,
            "cofinancement_requis": True,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Patrimoine situé en Auvergne-Rhône-Alpes (12 départements : 01, 03, 07, 15, 26, 38, 42, 43, 63, 69, 73, 74)\n"
                "- DISPOSITIF PRINCIPAL — Patrimoine non protégé :\n"
                "  • Communes rurales et centres-bourgs de moins de 20 000 habitants (prioritaires)\n"
                "  • Travaux < 20 000 € : aide pouvant atteindre 80 % du montant des travaux\n"
                "  • Travaux > 20 000 € : aide jusqu'à 70 %, plafonnée à 50 000 €\n"
                "  • Prérequis : une souscription publique Fondation du patrimoine doit avoir collecté au moins 5 % du montant des travaux\n"
                "  • Les propriétaires privés doivent impérativement présenter un projet d'ouverture au public et d'animation\n"
                "  • Budget annuel du fonds : 600 000 € répartis entre les dossiers sélectionnés par un jury annuel\n"
                "  • Le bien doit présenter un intérêt architectural reconnu\n"
                "- AIDES COMPLÉMENTAIRES — Patrimoine protégé MH :\n"
                "  • Édifices, jardins et objets mobiliers classés ou inscrits MH\n"
                "  • Étudiées au cas par cas tout au long de l'année (pas de jury)\n"
                "  • Seuil minimum : 40 000 € pour les édifices, 5 000 € pour le mobilier\n"
                "- Le cumul des aides publiques directes ne peut excéder 80 % du coût total\n"
                "- Autofinancement minimum de 20 % requis pour les communes\n"
                "- Les travaux ne doivent pas avoir commencé avant la date de réception de la demande\n"
                "- Contacter l'UDAP départementale et le service patrimoine de la Région AVANT de signer tout devis"
            ),
            "demarche_description": (
                "1. Contacter l'UDAP départementale et le service patrimoine de la Région Auvergne-Rhône-Alpes\n"
                "2. Lancer une souscription publique via la Fondation du patrimoine (collecter au moins 5 % du montant des travaux)\n"
                "3. Constituer le dossier : descriptif du patrimoine, programme de travaux, devis, plan de financement, preuves de la collecte\n"
                "4. Déposer le dossier auprès de la Région\n"
                "5. Sélection par un jury annuel (patrimoine non protégé) ou instruction au fil de l'eau (patrimoine protégé MH)\n"
                "6. Notification et convention de subvention\n"
                "7. Réalisation des travaux et versement de la subvention sur justificatifs"
            ),
            "documents_requis": [
                "Formulaire de demande de subvention régionale",
                "Descriptif du patrimoine et de son intérêt",
                "Programme détaillé des travaux",
                "Devis des entreprises (au moins 2 devis comparatifs)",
                "Plan de financement prévisionnel",
                "Photos du site avant travaux",
                "Autorisation de travaux (selon le niveau de protection)",
                "Preuve de propriété ou convention d'affectation",
                "Délibération du conseil municipal (si commune)",
                "RIB",
            ],
            "delai_instruction": "3 à 6 mois",
            "permanent": True,
            "url_officielle": "https://www.auvergnerhonealpes.fr/aides/restauration-patrimoine",
            "formulaire_url": None,
            "tags": [
                "Auvergne-Rhône-Alpes",
                "AURA",
                "région",
                "patrimoine",
                "restauration",
                "subvention régionale",
                "monuments historiques",
                "patrimoine rural",
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

# Propriétaires : communes, associations, privés
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : large gamme
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
        {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
        {"aide_id": aide_id, "travaux_code": "mobilier"},
        {"aide_id": aide_id, "travaux_code": "orgues"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Région : AURA uniquement
supabase.table("aides_regions").insert(
    [
        {"aide_id": aide_id, "region_code": "auvergne-rhone-alpes"},
    ]
).execute()
print("  ✓ Région insérée")

# Départements AURA
supabase.table("aides_departements").insert(
    [
        {"aide_id": aide_id, "departement_code": "01"},
        {"aide_id": aide_id, "departement_code": "03"},
        {"aide_id": aide_id, "departement_code": "07"},
        {"aide_id": aide_id, "departement_code": "15"},
        {"aide_id": aide_id, "departement_code": "26"},
        {"aide_id": aide_id, "departement_code": "38"},
        {"aide_id": aide_id, "departement_code": "42"},
        {"aide_id": aide_id, "departement_code": "43"},
        {"aide_id": aide_id, "departement_code": "63"},
        {"aide_id": aide_id, "departement_code": "69"},
        {"aide_id": aide_id, "departement_code": "73"},
        {"aide_id": aide_id, "departement_code": "74"},
    ]
).execute()
print("  ✓ Départements insérés")

# Segments : communes et privés
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
        {"aide_id": aide_id, "segment_code": "prive"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ Aide régionale AURA insérée avec succès (id: {aide_id})")
