"""
Seed: AAP Services Numériques Innovants (Ministère de la Culture).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_aap_sni.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Appel à projets « Services Numériques Innovants » (SNI) — Ministère de la Culture",
    "nom_court": "AAP SNI Culture",
    "description": "Subvention du Ministère de la Culture pour expérimenter des solutions numériques innovantes (IA, blockchain, IoT, web sémantique) au sein d'établissements culturels et patrimoniaux.",
    "description_longue": (
        "Lancé en 2012 par le Ministère de la Culture, l'appel à projets « Services Numériques "
        "Innovants » (SNI) finance et accompagne des solutions numériques facilitant l'accès au "
        "patrimoine, à la culture et à la création, tout en répondant aux objectifs de transmission "
        "des savoirs et de démocratisation culturelle. Le ministère soutient des prototypes et "
        "expérimentations concrètes pour évaluer le potentiel de certaines innovations pour les "
        "acteurs culturels : intelligence artificielle, blockchain, internet des objets, web "
        "sémantique, robotique, etc. Les projets doivent avoir une durée maximale de 18 mois. "
        "Les projets portés en partenariat avec plusieurs institutions culturelles ou un réseau "
        "sont prioritaires. Les monuments historiques sont des terrains d'expérimentation privilégiés."
    ),
    "categorie": "etat_drac",
    "type": "appel_a_projets",
    "organisme": "Ministère de la Culture — Service du numérique",
    "montant_max": None,
    "taux_max": None,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": True,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Le porteur de projet doit être un acteur culturel : musée, bibliothèque, archives, monument historique, centre d'art, scène nationale, opéra, etc.\n"
        "- Le projet doit porter sur une solution numérique innovante facilitant l'accès à la culture, au patrimoine ou à la création\n"
        "- Technologies ciblées : intelligence artificielle, blockchain, internet des objets (IoT), web sémantique, robotique, réalité augmentée/virtuelle, etc.\n"
        "- Le projet doit être au stade de prototype ou d'expérimentation (proof of concept)\n"
        "- Durée maximale du projet : 18 mois\n"
        "- Les projets en partenariat avec plusieurs institutions culturelles ou un réseau d'établissements sont prioritaires\n"
        "- Le projet doit démontrer un caractère innovant par rapport aux usages numériques existants dans le secteur culturel\n"
        "- Le porteur doit disposer des compétences techniques ou s'associer à un prestataire technologique\n"
        "- Le cofinancement est requis (fonds propres, partenaires, mécénat)\n"
        "- Le projet doit inclure une phase d'évaluation et de retour d'expérience\n"
        "- Les résultats doivent pouvoir être partagés et essaimés au bénéfice de la communauté culturelle\n"
        "- Les monuments historiques (classés ou inscrits) sont des terrains d'expérimentation particulièrement pertinents\n"
        "- Le projet ne doit pas avoir déjà commencé au moment du dépôt de la candidature\n"
        "- L'édition de l'AAP est annuelle, avec une date limite de dépôt variable (consulter le site du Ministère)"
    ),
    "demarche_description": (
        "1. Consulter l'appel à projets SNI sur le site du Ministère de la Culture\n"
        "2. Identifier le projet innovant et les partenaires technologiques et culturels\n"
        "3. Constituer le dossier : description du projet, budget, planning, équipe, partenariats\n"
        "4. Déposer la candidature avant la date limite de l'édition en cours\n"
        "5. Instruction par le comité d'experts du Ministère de la Culture\n"
        "6. Notification de la sélection et conventionnement\n"
        "7. Réalisation du prototype (18 mois max) et publication des résultats"
    ),
    "documents_requis": [
        "Dossier de candidature AAP SNI",
        "Description détaillée du projet et de l'innovation numérique",
        "Budget prévisionnel",
        "Planning de réalisation (18 mois max)",
        "CV de l'équipe projet et des partenaires techniques",
        "Lettres de partenariat (si multi-institutions)",
        "Plan d'évaluation et de diffusion des résultats",
    ],
    "delai_instruction": "3 à 6 mois",
    "permanent": False,
    "url_officielle": "https://www.culture.gouv.fr/catalogue-des-demarches-et-subventions/appels-a-projets-candidatures/services-numeriques-innovants-sni",
    "formulaire_url": None,
    "tags": [
        "numérique", "innovation", "Ministère Culture", "SNI",
        "IA", "patrimoine numérique", "prototype", "expérimentation",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte

# Propriétaires : collectivités et établissements culturels
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "public_departement"},
    {"aide_id": aide_id, "proprietaire_code": "public_region"},
    {"aide_id": aide_id, "proprietaire_code": "public_etat"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
]).execute()
print("  ✓ Propriétaires insérés")

# Travaux : pas de contrainte (aide numérique, pas travaux physiques)

# Segments
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "commune"},
]).execute()
print("  ✓ Segments insérés")

# Régions : aide nationale → pas de contrainte

print(f"\n✅ AAP SNI Culture inséré avec succès (id: {aide_id})")
