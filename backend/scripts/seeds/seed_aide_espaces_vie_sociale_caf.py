"""
Seed: Espaces de vie sociale (CAF).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_espaces_vie_sociale_caf.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Espace de vie sociale — Prestation de service Animation locale (CAF)",
    "nom_court": "EVS — CAF",
    "description": "Financement CAF pour les espaces de vie sociale (EVS) : prestation de service animation locale et subventions complémentaires pour l'animation de la vie sociale de proximité.",
    "description_longue": (
        "Les Caisses d'Allocations Familiales (CAF) soutiennent les Espaces de Vie Sociale (EVS), "
        "structures de proximité qui portent un projet d'animation de la vie sociale agréé par la CAF. "
        "L'agrément ouvre droit à la prestation de service « animation locale » financée par le fonds "
        "national de la CNAF, revalorisée annuellement. Des subventions complémentaires peuvent être "
        "accordées sur la dotation d'action sociale de la CAF locale. Les EVS visent à renforcer le "
        "lien social, favoriser la participation des habitants et développer des actions adaptées aux "
        "besoins du territoire. Les monuments historiques ouverts au public peuvent accueillir un EVS, "
        "notamment dans les territoires ruraux où ces lieux patrimoniaux sont des points de rencontre "
        "naturels pour les habitants."
    ),
    "categorie": "etat_drac",
    "type": "subvention",
    "organisme": "Caisse d'Allocations Familiales (CAF) / Caisse Nationale des Allocations Familiales (CNAF)",
    "montant_max": None,
    "taux_max": None,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": False,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Le porteur de projet doit obtenir l'agrément « Espace de vie sociale » délivré par le conseil d'administration de la CAF locale\n"
        "- Structures éligibles : associations, collectivités en gestion directe, entreprises publiques locales, quel que soit le mode de gestion\n"
        "- Le projet social doit être validé pour une durée de 4 ans (renouvelable)\n"
        "- Le projet social doit répondre aux besoins identifiés du territoire et des habitants\n"
        "- L'EVS doit porter au minimum une des missions suivantes : coordination d'une offre d'animation locale, organisation de lieux de rencontre et d'échange, accompagnement de projets collectifs d'habitants\n"
        "- Priorité aux territoires déficitaires en équipements sociaux, zones rurales, QPV\n"
        "- L'agrément donne droit à la prestation de service « animation locale » (fonds national CNAF)\n"
        "- Des subventions complémentaires peuvent être accordées par la CAF locale (dotation d'action sociale)\n"
        "- Le bilan annuel de l'année N est obligatoire pour le versement du solde N et la recevabilité du dossier N+1\n"
        "- Tout nouveau projet nécessite un contact préalable avec l'Antenne de Développement Social (ADS) de la CAF du territoire\n"
        "- L'EVS doit disposer d'un local identifié et accessible, ouvert de manière régulière\n"
        "- Un monument historique ouvert au public peut servir de lieu d'accueil pour l'EVS, en particulier en milieu rural\n"
        "- La gouvernance doit associer les habitants (comité d'usagers, conseil participatif)\n"
        "- Le diagnostic de territoire est obligatoire (identification des besoins sociaux locaux)"
    ),
    "demarche_description": (
        "1. Contacter l'Antenne de Développement Social (ADS) de la CAF de son territoire\n"
        "2. Réaliser un diagnostic de territoire et identifier les besoins sociaux\n"
        "3. Élaborer le projet social de l'EVS (4 ans)\n"
        "4. Déposer la demande d'agrément auprès de la CAF locale\n"
        "5. Passage en commission et validation par le conseil d'administration de la CAF\n"
        "6. Conventionnement et mise en œuvre du projet social\n"
        "7. Bilan annuel obligatoire pour le renouvellement"
    ),
    "documents_requis": [
        "Projet social de l'EVS (4 ans)",
        "Diagnostic de territoire",
        "Statuts de la structure porteuse",
        "Budget prévisionnel",
        "Description du local et des conditions d'accueil",
        "Programme d'activités prévu",
        "Bilan de l'année précédente (si renouvellement)",
    ],
    "delai_instruction": "3 à 6 mois",
    "permanent": True,
    "url_officielle": "https://www.caf.fr/professionnels/offres-et-services/dispositifs-partenaires/espace-de-vie-sociale",
    "formulaire_url": None,
    "tags": [
        "CAF", "espace de vie sociale", "EVS", "animation locale",
        "lien social", "ruralité", "QPV", "vie sociale",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte

# Propriétaires : collectivités et associations
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
]).execute()
print("  ✓ Propriétaires insérés")

# Travaux : pas de contrainte (aide de fonctionnement, pas de travaux)

# Segments
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "commune"},
]).execute()
print("  ✓ Segments insérés")

# Régions : aide nationale → pas de contrainte

print(f"\n✅ EVS CAF inséré avec succès (id: {aide_id})")
