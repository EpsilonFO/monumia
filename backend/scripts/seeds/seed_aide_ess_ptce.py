"""
Seed: ESS et PTCE (Pôles Territoriaux de Coopération Économique).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_ess_ptce.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Pôles Territoriaux de Coopération Économique (PTCE) — AMI État",
    "nom_court": "PTCE — AMI ESS",
    "description": "Subvention de l'État pour soutenir les Pôles Territoriaux de Coopération Économique (PTCE), regroupements d'acteurs ESS et d'entreprises coopérant sur un territoire.",
    "description_longue": (
        "Les Pôles Territoriaux de Coopération Économique (PTCE) sont des regroupements d'acteurs "
        "de l'Économie Sociale et Solidaire (ESS) — associations, coopératives, mutuelles — "
        "d'entreprises commerciales, de collectivités locales, de centres de recherche et d'organismes "
        "de formation, sur un même territoire. L'État soutient leur développement via des Appels à "
        "Manifestation d'Intérêt (AMI) réguliers. Le financement varie de 30 000 € à 80 000 € par "
        "lauréat pour une période de 2 ans. Les PTCE centrés sur la valorisation du patrimoine "
        "(restauration, tourisme culturel, métiers d'art, circuits courts) peuvent être particulièrement "
        "pertinents pour les propriétaires de monuments historiques souhaitant structurer un écosystème "
        "économique autour de leur bien."
    ),
    "categorie": "etat_drac",
    "type": "subvention",
    "organisme": "Ministère de l'Économie — Secrétariat d'État à l'ESS",
    "montant_max": 80000,
    "taux_max": None,
    "montant_min": 30000,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": False,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Le PTCE doit être porté par une structure de l'Économie Sociale et Solidaire (association, coopérative, mutuelle, fondation, entreprise sociale)\n"
        "- Le PTCE doit regrouper au minimum des acteurs ESS et des entreprises classiques sur un même territoire\n"
        "- Le PTCE ne doit pas avoir bénéficié d'une subvention PTCE État sur les 2 dernières années\n"
        "- Ancrage territorial requis : zone rurale ou Quartier Prioritaire de la Politique de la Ville (QPV)\n"
        "- Le PTCE doit adhérer à la Charte nationale des PTCE (version 2021)\n"
        "- Montant de la subvention : entre 30 000 € et 80 000 € par lauréat, pour une période de 2 ans\n"
        "- Les demandes en dehors de cette fourchette sont irrecevables\n"
        "- 5 à 10 lauréats sélectionnés par AMI\n"
        "- Le projet doit démontrer une dynamique de coopération effective entre les membres du pôle\n"
        "- Les PTCE orientés patrimoine, tourisme culturel, métiers d'art, circuits courts sont éligibles\n"
        "- Le volet « communautés apprenantes » fait l'objet d'un AMI complémentaire (subvention max 30 000 €)\n"
        "- La candidature se fait en réponse à l'AMI publié sur le site du ministère de l'Économie\n"
        "- Le porteur doit justifier d'une gouvernance partagée et démocratique\n"
        "- Le projet doit avoir un impact territorial mesurable (emploi, inclusion, développement local)"
    ),
    "demarche_description": (
        "1. Vérifier l'ouverture d'un AMI PTCE sur le site du ministère de l'Économie\n"
        "2. Constituer le pôle : identifier les acteurs ESS et partenaires du territoire\n"
        "3. Adhérer à la Charte nationale des PTCE (2021)\n"
        "4. Élaborer le projet de coopération territoriale et le budget prévisionnel\n"
        "5. Déposer la candidature en réponse à l'AMI avant la date limite\n"
        "6. Instruction et sélection par un jury national\n"
        "7. Conventionnement sur 2 ans et versement de la subvention"
    ),
    "documents_requis": [
        "Dossier de candidature AMI complété",
        "Statuts de la structure porteuse",
        "Liste des membres du PTCE et lettres d'engagement",
        "Projet de coopération territoriale",
        "Budget prévisionnel sur 2 ans",
        "Charte nationale des PTCE signée",
        "Diagnostic territorial",
    ],
    "delai_instruction": "3 à 6 mois",
    "permanent": False,
    "url_officielle": "https://www.economie.gouv.fr/actualites/ess-deux-appels-manifestation-dinteret-ami-pour-soutenir-le-developpement-des-poles",
    "formulaire_url": None,
    "tags": [
        "ESS", "PTCE", "coopération territoriale", "économie sociale",
        "ruralité", "QPV", "métiers d'art", "développement local",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte

# Propriétaires : associations et collectivités
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
]).execute()
print("  ✓ Propriétaires insérés")

# Travaux : pas de contrainte (aide au fonctionnement du pôle)

# Segments
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "commune"},
]).execute()
print("  ✓ Segments insérés")

# Régions : aide nationale → pas de contrainte

print(f"\n✅ PTCE — AMI ESS inséré avec succès (id: {aide_id})")
