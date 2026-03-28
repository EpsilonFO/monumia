"""
Seed: Fonds Barnier — Fonds de Prévention des Risques Naturels Majeurs (FPRNM).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_fonds_barnier.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Fonds Barnier — Fonds de Prévention des Risques Naturels Majeurs (FPRNM)",
    "nom_court": "Fonds Barnier",
    "description": "Subvention pour les travaux de réduction de la vulnérabilité aux risques naturels (inondation, mouvement de terrain, etc.) des bâtiments situés en zone couverte par un PPRN. Jusqu'à 80 % pour les particuliers.",
    "description_longue": (
        "Le Fonds de Prévention des Risques Naturels Majeurs (FPRNM), dit « fonds Barnier », "
        "finance les études et travaux de réduction de la vulnérabilité des biens exposés aux "
        "risques naturels majeurs (inondations, mouvements de terrain, séismes, avalanches, etc.). "
        "Il s'adresse aux particuliers, collectivités et petites entreprises dont les biens sont "
        "situés dans des communes couvertes par un Plan de Prévention des Risques Naturels (PPRN) "
        "approuvé ou prescrit. Pour les particuliers, le taux de subvention atteint 80 % des "
        "dépenses éligibles, plafonné à 36 000 € par bien à usage d'habitation. Pour les "
        "collectivités, le taux varie de 40 à 50 %. Le fonds est doté de 300 M€ en 2026. "
        "Ce dispositif peut être particulièrement pertinent pour les monuments et bâtiments "
        "patrimoniaux situés en zone de risque naturel nécessitant des travaux de mise en sécurité."
    ),
    "categorie": "etat_drac",
    "type": "subvention",
    "organisme": "Ministère de la Transition Écologique — Préfectures (DDT/DDTM)",
    "montant_max": 36000,
    "taux_max": 80,
    "montant_min": None,
    "plancher": None,
    "base_ttc": True,
    "commune_max_population": None,
    "cofinancement_requis": False,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Le bien doit être situé dans une commune couverte par un Plan de Prévention des Risques Naturels (PPRN) approuvé ou prescrit\n"
        "- Risques couverts : inondation, mouvement de terrain, séisme, avalanche, feu de forêt, cyclone, volcanisme, submersion marine\n"
        "- Taux de subvention pour les particuliers (biens à usage d'habitation ou mixte) :\n"
        "  • 80 % des dépenses éligibles pour les travaux rendus obligatoires par le PPRN\n"
        "  • Plafond : 36 000 € de subvention par bien\n"
        "  • Le coût des travaux ne doit pas dépasser 10 % de la valeur vénale du bien (seuil de base)\n"
        "  • Au-delà de 10 %, financement possible dans la limite de 36 000 € et de 50 % de la valeur vénale\n"
        "- Taux de subvention pour les collectivités :\n"
        "  • 40 % pour les études (50 % si PPRN approuvé)\n"
        "  • 40 à 50 % pour les travaux de prévention\n"
        "  • 50 % pour les actions d'information préventive (DICRIM, repères de crues)\n"
        "- Taux de subvention pour les entreprises (< 20 salariés) :\n"
        "  • 20 % des dépenses éligibles\n"
        "  • Plafond : 10 % de la valeur vénale du bien\n"
        "- Les travaux doivent être prescrits ou recommandés par le PPRN, ou identifiés dans un diagnostic de vulnérabilité\n"
        "- Les travaux inscrits dans un PAPI (Programme d'Actions de Prévention des Inondations) validé sont également éligibles à 80 %\n"
        "- Les travaux ne doivent pas avoir commencé avant le dépôt de la demande\n"
        "- Un diagnostic de vulnérabilité préalable peut être financé par le fonds\n"
        "- Les bâtiments patrimoniaux sont éligibles s'ils sont en zone PPRN et que les travaux visent la réduction de la vulnérabilité\n"
        "- Non éligible : travaux de confort, d'embellissement, d'extension ou de changement de destination\n"
        "- Le cumul des aides publiques ne doit pas dépasser 80 % du coût total\n"
        "- Budget national 2026 : 300 M€ en autorisations d'engagement"
    ),
    "demarche_description": (
        "1. Vérifier que le bien est situé en zone couverte par un PPRN (consulter georisques.gouv.fr)\n"
        "2. Réaliser un diagnostic de vulnérabilité du bâtiment (finançable par le fonds)\n"
        "3. Identifier les travaux de réduction de vulnérabilité prescrits ou recommandés par le PPRN\n"
        "4. Obtenir des devis détaillés pour les travaux envisagés\n"
        "5. Déposer la demande de subvention auprès de la DDT ou DDTM du département\n"
        "6. Attendre l'accord de subvention avant de commencer les travaux\n"
        "7. Réaliser les travaux et transmettre les justificatifs de dépenses\n"
        "8. Obtenir le versement de la subvention sur présentation des factures acquittées"
    ),
    "documents_requis": [
        "Formulaire de demande de subvention FPRNM",
        "Preuve de propriété du bien",
        "Diagnostic de vulnérabilité du bâtiment",
        "Devis détaillés des travaux de réduction de vulnérabilité",
        "Plan de situation du bien (zonage PPRN)",
        "Photos du bien et des désordres constatés",
        "Plan de financement prévisionnel",
        "RIB du demandeur",
    ],
    "delai_instruction": "3 à 6 mois",
    "permanent": True,
    "url_officielle": "https://www.georisques.gouv.fr/minformer-sur-la-prevention-des-risques/le-fonds-barnier",
    "formulaire_url": None,
    "tags": [
        "Fonds Barnier", "FPRNM", "risques naturels", "inondation", "PPRN",
        "vulnérabilité", "prévention", "mise en sécurité",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (tous types de bâtiments, protégés ou non)

# Propriétaires : tous types
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "public_departement"},
    {"aide_id": aide_id, "proprietaire_code": "public_region"},
    {"aide_id": aide_id, "proprietaire_code": "public_etat"},
    {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
    {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
    {"aide_id": aide_id, "proprietaire_code": "mixte"},
]).execute()
print("  ✓ Propriétaires insérés")

# Travaux : mise en sécurité, maçonnerie, restauration générale
supabase.table("aides_travaux").insert([
    {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
    {"aide_id": aide_id, "travaux_code": "maconnerie"},
    {"aide_id": aide_id, "travaux_code": "restauration_generale"},
    {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    {"aide_id": aide_id, "travaux_code": "toiture"},
    {"aide_id": aide_id, "travaux_code": "charpente"},
    {"aide_id": aide_id, "travaux_code": "facade"},
]).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale → pas de contrainte

# Segments : tous segments
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "commune"},
    {"aide_id": aide_id, "segment_code": "prive"},
]).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ Fonds Barnier inséré avec succès (id: {aide_id})")
