"""
Seed: Prêt Tourisme BPI France — Financement des projets touristiques et patrimoniaux.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_bpi_pret_tourisme.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Prêt Tourisme BPI France — Financement des projets touristiques et patrimoniaux",
    "nom_court": "Prêt Tourisme BPI",
    "description": "Prêt sans garantie de 50 000 à 5 000 000 € pour les TPE/PME du tourisme, couvrant la rénovation, modernisation et mise aux normes des hébergements et sites patrimoniaux à vocation touristique.",
    "description_longue": (
        "Le Prêt Tourisme est un dispositif de BPI France, en partenariat avec la Banque "
        "des Territoires, destiné aux TPE, PME et indépendants du secteur touristique. "
        "Il finance les projets de rénovation, modernisation, mise aux normes et "
        "développement durable des établissements touristiques. Le prêt va de 50 000 € "
        "à 5 000 000 €, sur une durée de 2 à 10 ans, à taux fixe, sans garantie sur les "
        "actifs de l'entreprise ni caution personnelle du dirigeant. Les frais de dossier "
        "s'élèvent à 0,40 % du montant du prêt. Le Prêt Tourisme intervient en cofinancement "
        "avec un prêt bancaire ou participatif d'un montant au moins équivalent. "
        "Il s'adresse à tous les acteurs contribuant à l'attractivité touristique : "
        "hébergement, restauration, bien-être, loisirs, culture, transport touristique, "
        "événementiel. Les monuments historiques ouverts au public à vocation touristique "
        "peuvent être éligibles via la structure d'exploitation (SCI, SARL, association)."
    ),
    "categorie": "etat_drac",
    "type": "pret",
    "organisme": "BPI France / Banque des Territoires",
    "montant_max": 5000000,
    "taux_max": None,
    "montant_min": 50000,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": True,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- L'entreprise doit être une TPE, PME ou un indépendant immatriculé en France.\n"
        "- L'entreprise doit exercer depuis au moins 3 ans (ancienneté minimale).\n"
        "- L'activité doit contribuer à l'attractivité touristique du territoire : "
        "hébergement touristique, restauration, bien-être et thermalisme, voyagistes, "
        "transport touristique, événementiel, culture, loisirs.\n"
        "- Les monuments historiques exploités à vocation touristique (visites, "
        "hébergement, événementiel) sont éligibles via la structure d'exploitation.\n"
        "- Montant du prêt : de 50 000 € à 5 000 000 €.\n"
        "- Durée : 2 à 10 ans, avec possibilité de différé de remboursement.\n"
        "- Taux fixe, sans garantie sur les actifs ni caution personnelle du dirigeant.\n"
        "- Cofinancement obligatoire : un prêt bancaire ou participatif d'un montant "
        "au moins équivalent doit être obtenu en parallèle.\n"
        "- Frais de dossier : 0,40 % du montant du prêt.\n"
        "- Dépenses éligibles : travaux de rénovation et modernisation, mise aux normes "
        "(sécurité, accessibilité, hygiène), équipements, communication et marketing, "
        "recrutement et formation pour le développement durable.\n"
        "- Les SCI, SARL, EURL, associations gestionnaires de sites patrimoniaux "
        "à vocation touristique sont éligibles.\n"
        "- Les personnes physiques (particuliers) ne sont pas directement éligibles : "
        "il faut une structure avec SIRET et activité professionnelle.\n"
        "- Le dispositif s'inscrit dans le Plan Destination France (1,9 milliard d'euros "
        "pour relancer le secteur touristique)."
    ),
    "demarche_description": (
        "1. Vérifier l'éligibilité sur bpifrance.fr/catalogue-offres/pret-tourisme\n"
        "2. Obtenir un accord de principe d'un prêt bancaire d'accompagnement\n"
        "3. Constituer le dossier de demande (business plan, prévisionnel, devis travaux)\n"
        "4. Déposer la demande auprès de BPI France (en ligne ou via la direction régionale)\n"
        "5. Instruction du dossier par BPI France\n"
        "6. Signature du contrat de prêt et déblocage des fonds"
    ),
    "documents_requis": [
        "Kbis ou extrait d'immatriculation de moins de 3 mois",
        "Bilans et comptes de résultats des 3 derniers exercices",
        "Prévisionnel d'exploitation sur la durée du prêt",
        "Business plan du projet touristique",
        "Devis des travaux ou investissements prévus",
        "Accord de principe du prêt bancaire d'accompagnement",
        "RIB de l'entreprise",
    ],
    "delai_instruction": "2 à 4 semaines",
    "permanent": True,
    "url_officielle": "https://www.bpifrance.fr/catalogue-offres/pret-tourisme",
    "formulaire_url": None,
    "tags": [
        "BPI France", "prêt tourisme", "Banque des Territoires",
        "Destination France", "hébergement touristique", "rénovation",
        "modernisation", "TPE", "PME", "sans garantie",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte (MH ou non)

# Propriétaires : entreprises et associations (pas les particuliers ni collectivités)
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
    {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
]).execute()
print("  ✓ Propriétaires éligibles insérés")

# Travaux : rénovation, modernisation, mise aux normes
supabase.table("aides_travaux").insert([
    {"aide_id": aide_id, "travaux_code": "toiture"},
    {"aide_id": aide_id, "travaux_code": "facade"},
    {"aide_id": aide_id, "travaux_code": "maconnerie"},
    {"aide_id": aide_id, "travaux_code": "menuiserie"},
    {"aide_id": aide_id, "travaux_code": "electricite"},
    {"aide_id": aide_id, "travaux_code": "plomberie"},
    {"aide_id": aide_id, "travaux_code": "chauffage"},
    {"aide_id": aide_id, "travaux_code": "accessibilite"},
    {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
    {"aide_id": aide_id, "travaux_code": "restauration_generale"},
]).execute()
print("  ✓ Travaux éligibles insérés")

# Régions : aide nationale → pas de contrainte

# Segments : privé uniquement (entreprises)
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "prive"},
]).execute()
print("  ✓ Segments insérés")

print(f"\n✅ Prêt Tourisme BPI France inséré avec succès (id: {aide_id})")
