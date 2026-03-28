"""
Seed: Événementiel et festivals — Soutien aux festivals et manifestations
culturelles dans les monuments historiques et sites patrimoniaux.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_evenementiel_festivals.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Soutien aux festivals et manifestations culturelles dans le patrimoine — DRAC",
    "nom_court": "DRAC Festivals patrimoine",
    "description": "Subvention de la DRAC pour les festivals et événements culturels organisés dans des monuments historiques ou sites patrimoniaux, couvrant le spectacle vivant, les arts visuels et les manifestations littéraires.",
    "description_longue": (
        "Le Ministère de la Culture, via les Directions Régionales des Affaires Culturelles "
        "(DRAC), soutient les festivals et manifestations culturelles qui se déroulent dans "
        "des monuments historiques ou contribuent à la valorisation du patrimoine. Trois types "
        "d'aide sont proposés : une aide ponctuelle (aide au projet), une aide pluriannuelle "
        "triennale (aide au fonctionnement global), et une aide transversale (aide à la "
        "transition du festival). Les festivals doivent programmer majoritairement des œuvres "
        "présentées par des professionnels, avoir une durée définie et être récurrents. "
        "Les manifestations patrimoniales (colloques, expositions, journées portes ouvertes "
        "thématiques, chantiers de bénévoles) sont également éligibles à des subventions "
        "de valorisation du patrimoine. Les Journées Européennes du Patrimoine constituent "
        "un temps fort annuel avec un soutien dédié pour les monuments participants. "
        "Les organisateurs doivent avoir engagé une démarche de prévention et de lutte "
        "contre les violences sexistes et sexuelles."
    ),
    "categorie": "etat_drac",
    "type": "subvention",
    "organisme": "Ministère de la Culture — DRAC / DAC",
    "montant_max": None,
    "taux_max": 80,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": False,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Un festival éligible doit être une manifestation circonscrite dans le temps et dans "
        "l'espace, avec un projet artistique et culturel dans une logique éditoriale de "
        "programmation formant une unité.\n"
        "- Le festival doit répondre à trois critères cumulatifs : programmation d'œuvres "
        "artistiques et de créations proposées majoritairement par des professionnels, "
        "durée définie, et récurrence (annuelle, biennale, etc.).\n"
        "- Trois types d'aide : aide ponctuelle (au projet), aide triennale (au fonctionnement), "
        "aide transversale (à la transition du festival, ex : éco-responsabilité).\n"
        "- Le festival doit contribuer à au moins deux enjeux dans chacun des champs suivants : "
        "artistique, coopération et structuration des filières professionnelles, inscription "
        "territoriale et accessibilité, ouverture aux publics.\n"
        "- Les organisateurs doivent avoir engagé une démarche de prévention et de lutte contre "
        "les violences sexistes et sexuelles (VSS).\n"
        "- Pour les manifestations patrimoniales (hors festival de spectacle vivant) : "
        "études, publications, colloques, expositions, chantiers de bénévoles liés à un "
        "monument historique ou un site patrimonial remarquable.\n"
        "- Bénéficiaires éligibles : associations, collectivités, établissements publics, "
        "structures privées gestionnaires d'un monument ou site patrimonial.\n"
        "- La demande est déposée exclusivement en ligne via le portail Démarches Simplifiées "
        "auprès de la DRAC/DAC de la région concernée.\n"
        "- Chaque DRAC/DAC fixe son propre calendrier et ses modalités d'instruction. "
        "Date limite indicative : 15 mars de l'année N pour les festivals de l'année N.\n"
        "- Le cumul avec d'autres aides publiques est possible dans la limite de 80 % du coût "
        "total du projet.\n"
        "- Les festivals se déroulant dans des monuments historiques classés ou inscrits, "
        "ou dans des Sites Patrimoniaux Remarquables (SPR), bénéficient d'une attention "
        "particulière dans les critères de sélection.\n"
        "- L'utilisation d'un monument historique pour un festival requiert l'accord du "
        "propriétaire et le respect des prescriptions de l'Architecte des Bâtiments de France."
    ),
    "demarche_description": (
        "1. Identifier la DRAC de votre région et vérifier le calendrier de dépôt\n"
        "2. Préparer le dossier artistique et le budget prévisionnel du festival ou de la manifestation\n"
        "3. Déposer la demande en ligne sur le portail Démarches Simplifiées\n"
        "4. Instruction par la DRAC (évaluation artistique, territoriale et financière)\n"
        "5. Notification de l'attribution et convention de financement\n"
        "6. Réalisation de l'événement\n"
        "7. Envoi du bilan artistique, financier et de fréquentation"
    ),
    "documents_requis": [
        "Projet artistique et culturel détaillé",
        "Budget prévisionnel de l'événement",
        "Programmation prévisionnelle",
        "Bilan de l'édition précédente (si renouvellement)",
        "Statuts de la structure organisatrice",
        "Numéro SIRET",
        "RIB de la structure",
        "Accord du propriétaire du monument (si applicable)",
        "Attestation de démarche de prévention VSS",
    ],
    "delai_instruction": "2 à 4 mois",
    "permanent": True,
    "url_officielle": "https://www.culture.gouv.fr/catalogue-des-demarches-et-subventions/subvention/soutien-aux-festivals-dans-le-champ-de-la-creation-artistique-spectacle-vivant-et-arts-visuels",
    "formulaire_url": "https://demarche.numerique.gouv.fr",
    "tags": [
        "festival", "événementiel", "spectacle vivant", "arts visuels",
        "patrimoine", "DRAC", "valorisation", "manifestation culturelle",
        "monument historique", "JEP",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte stricte (patrimoine protégé ou non)

# Propriétaires : collectivités, associations, structures privées
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "public_departement"},
    {"aide_id": aide_id, "proprietaire_code": "public_region"},
    {"aide_id": aide_id, "proprietaire_code": "public_etat"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
    {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
    {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
    {"aide_id": aide_id, "proprietaire_code": "mixte"},
]).execute()
print("  ✓ Propriétaires éligibles insérés")

# Travaux : pas de travaux physiques, mais valorisation
supabase.table("aides_travaux").insert([
    {"aide_id": aide_id, "travaux_code": "restauration_generale"},
    {"aide_id": aide_id, "travaux_code": "accessibilite"},
    {"aide_id": aide_id, "travaux_code": "etude_prealable"},
]).execute()
print("  ✓ Travaux éligibles insérés")

# Régions : aide nationale → pas de contrainte

# Segments : tous segments
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "commune"},
    {"aide_id": aide_id, "segment_code": "prive"},
]).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ Événementiel et festivals inséré avec succès (id: {aide_id})")
