"""
Seed: FEADER / LEADER — Soutien au développement rural et patrimoine.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_feader_leader.py
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
            "nom": "FEADER / LEADER — Fonds européen agricole pour le développement rural",
            "nom_court": "FEADER LEADER",
            "description": "Subvention européenne pour des projets de développement rural portés localement, incluant la valorisation du patrimoine culturel et le tourisme rural, via les Groupes d'Action Locale (GAL).",
            "description_longue": (
                "LEADER (Liaison Entre Actions de Développement de l'Économie Rurale) est une "
                "initiative de l'Union européenne financée par le FEADER. Elle soutient des projets "
                "de développement local portés par des Groupes d'Action Locale (GAL), structures de "
                "partenariat public-privé qui définissent une stratégie locale de développement. "
                "Le patrimoine culturel et naturel, le tourisme rural, la valorisation des savoir-faire "
                "locaux et l'identité collective font partie des thématiques fréquemment retenues "
                "par les GAL. Pour la programmation 2023-2027 (Plan Stratégique National PAC), "
                "LEADER dispose de 5 % minimum de l'enveloppe FEADER nationale. Le taux de "
                "cofinancement LEADER peut atteindre 80 % des dépenses éligibles. Chaque GAL "
                "définit ses propres critères de sélection et calendriers d'appels à projets. "
                "Les zones éligibles sont les territoires ruraux de moins de 150 000 habitants "
                "(hors aires urbaines de plus de 50 000 habitants)."
            ),
            "categorie": "europe",
            "type": "subvention",
            "organisme": "Commission européenne / Régions (autorités de gestion) / Groupes d'Action Locale (GAL)",
            "montant_max": None,
            "taux_max": 80,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": 150000,
            "cofinancement_requis": True,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Le projet doit être situé sur le périmètre d'un Groupe d'Action Locale (GAL) "
                "et s'inscrire dans la stratégie locale de développement de ce GAL.\n"
                "- Les GAL couvrent des territoires ruraux de 10 000 à 150 000 habitants, hors "
                "aires urbaines de plus de 50 000 habitants.\n"
                "- Le porteur de projet doit disposer d'un numéro SIRET.\n"
                "- Bénéficiaires éligibles : collectivités territoriales, EPCI, établissements "
                "publics, associations, entreprises (y compris individuelles), SCI dans certains GAL.\n"
                "- Les particuliers personnes physiques ne sont généralement pas éligibles directement, "
                "sauf via une structure (association, SCI, entreprise).\n"
                "- Cofinancement public obligatoire : principe du « 1 € de cofinancement public = "
                "4 € de LEADER » dans de nombreux GAL.\n"
                "- Le projet ne doit pas avoir débuté avant le dépôt de la demande (principe de "
                "non-démarrage anticipé).\n"
                "- Types de projets patrimoniaux éligibles : restauration et valorisation du "
                "patrimoine bâti (protégé ou non protégé), création de circuits de découverte, "
                "signalétique patrimoniale, aménagement de sites, hébergement touristique en "
                "zone rurale, équipements culturels.\n"
                "- Dépenses éligibles : investissement (travaux, équipements, aménagements) et "
                "fonctionnement (études, animation, communication, ingénierie).\n"
                "- Le taux de cofinancement LEADER varie selon le GAL, généralement entre 40 % "
                "et 80 % des dépenses éligibles HT.\n"
                "- Les projets à vocation touristique ou patrimoniale bénéficient souvent d'une "
                "bonification dans les critères de sélection du GAL.\n"
                "- Le cumul avec d'autres aides européennes (FEDER, FSE+) est possible mais "
                "interdit sur la même dépense (interdiction du double financement).\n"
                "- Programmation en cours : 2023-2027 (PSN PAC). Les derniers paiements sont prévus fin 2029.\n"
                "- L'approbation du projet par le comité de programmation du GAL est requise "
                "avant tout engagement de dépense.\n"
                "- Obligation de publicité européenne sur le projet financé."
            ),
            "demarche_description": (
                "1. Identifier le GAL de votre territoire sur le site de la Région ou du Réseau rural\n"
                "2. Contacter l'animateur du GAL pour vérifier l'éligibilité et la cohérence du projet "
                "avec la stratégie locale\n"
                "3. Monter le dossier de demande (description du projet, plan de financement, devis, "
                "calendrier prévisionnel)\n"
                "4. Déposer le dossier auprès du GAL (plateforme e-Synergie ou dépôt papier selon la région)\n"
                "5. Passage du dossier en comité de programmation du GAL\n"
                "6. Notification de l'aide et convention d'attribution\n"
                "7. Réalisation du projet et demande de paiement sur justificatifs"
            ),
            "documents_requis": [
                "Numéro SIRET du porteur de projet",
                "Statuts de la structure",
                "Bilan financier (pour les associations et entreprises)",
                "Description détaillée du projet",
                "Devis ou estimations financières",
                "Plan de financement prévisionnel",
                "Calendrier prévisionnel",
                "Autorisations administratives (permis de construire, autorisation ABF si MH)",
                "Attestation de non-démarrage du projet",
                "RIB du porteur de projet",
            ],
            "delai_instruction": "2 à 6 mois (selon le calendrier du comité de programmation du GAL)",
            "permanent": False,
            "url_officielle": "https://www.reseaurural.fr/leader",
            "formulaire_url": None,
            "tags": [
                "FEADER",
                "LEADER",
                "Europe",
                "développement rural",
                "GAL",
                "patrimoine rural",
                "tourisme rural",
                "valorisation",
                "cofinancement",
                "2023-2027",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte formelle (patrimoine non protégé aussi éligible)

# Propriétaires : collectivités, associations, entreprises, SCI
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "mixte"},
    ]
).execute()
print("  ✓ Propriétaires éligibles insérés")

# Travaux : large spectre orienté valorisation et restauration
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "couverture"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "accessibilite"},
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
        {"aide_id": aide_id, "travaux_code": "parcs_jardins"},
    ]
).execute()
print("  ✓ Travaux éligibles insérés")

# Régions : aide nationale (tous GAL de France) → pas de contrainte

# Segments : communes et privés (via structures)
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
        {"aide_id": aide_id, "segment_code": "prive"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ FEADER / LEADER inséré avec succès (id: {aide_id})")
