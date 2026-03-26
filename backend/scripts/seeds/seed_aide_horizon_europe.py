"""
Seed: Horizon Europe — Patrimoine culturel (Cluster 2).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_horizon_europe.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Horizon Europe — Patrimoine culturel (Cluster 2 : Culture, créativité et société inclusive)",
    "nom_court": "Horizon Europe Patrimoine",
    "description": "Programme-cadre européen de recherche et innovation finançant des projets collaboratifs de préservation et valorisation du patrimoine culturel. Taux jusqu'à 100 % pour les actions de recherche.",
    "description_longue": (
        "Horizon Europe est le programme-cadre de l'Union européenne pour la recherche et "
        "l'innovation (2021-2027), doté de 95,5 milliards d'euros. Le Cluster 2 « Culture, "
        "créativité et société inclusive » du Pilier 2 finance des projets collaboratifs portant "
        "sur la préservation du patrimoine culturel européen, la numérisation, les technologies "
        "innovantes de restauration, et les industries culturelles et créatives. Les projets "
        "doivent être portés par un consortium transnational (minimum 3 entités de 3 pays UE "
        "différents). Le taux de financement atteint 100 % pour les Research and Innovation "
        "Actions (RIA) et jusqu'à 70 % pour les Innovation Actions (IA), sauf entités à but "
        "non lucratif (100 %). Les appels à propositions sont publiés sur le portail Funding & "
        "Tenders de la Commission européenne."
    ),
    "categorie": "europe",
    "type": "appel_a_projets",
    "organisme": "Commission européenne — Direction générale Recherche et Innovation",
    "montant_max": 4000000,
    "taux_max": 100,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": False,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Programme-cadre européen Horizon Europe 2021-2027, Pilier 2, Cluster 2 : « Culture, créativité et société inclusive »\n"
        "- Le projet doit porter sur la préservation, la restauration, la numérisation ou la valorisation du patrimoine culturel européen\n"
        "- Consortium transnational obligatoire : minimum 3 entités juridiques indépendantes établies dans 3 États membres ou pays associés différents\n"
        "- Types d'actions et taux de financement :\n"
        "  • RIA (Research and Innovation Actions) : jusqu'à 100 % des coûts éligibles\n"
        "  • IA (Innovation Actions) : jusqu'à 70 % des coûts éligibles (100 % pour les entités à but non lucratif)\n"
        "  • CSA (Coordination and Support Actions) : jusqu'à 100 % des coûts éligibles\n"
        "- Budget moyen par projet : 3 à 4 millions d'euros (variable selon les appels)\n"
        "- Entités éligibles : universités, centres de recherche, entreprises, PME, collectivités, associations, fondations, musées, organismes culturels\n"
        "- Les propriétaires privés individuels ne sont PAS directement éligibles en tant que porteurs, mais peuvent être partenaires associés d'un consortium\n"
        "- Le projet doit avoir un impact européen démontrable (pas seulement local)\n"
        "- Dimension innovation requise : technologies nouvelles de restauration, numérisation 3D, intelligence artificielle, sciences participatives, etc.\n"
        "- Les candidatures répondent à des topics spécifiques publiés dans les Work Programmes annuels\n"
        "- Évaluation par des experts indépendants sur 3 critères : excellence, impact, qualité de la mise en œuvre\n"
        "- Seuil d'excellence requis pour chaque critère (généralement 3/5) et seuil global (généralement 10/15)\n"
        "- Procédure en une ou deux étapes selon les appels\n"
        "- Pas de contrainte sur le type de protection du patrimoine (classé, inscrit, ou non protégé)\n"
        "- Le patrimoine bâti, mobilier, immatériel et paysager est éligible\n"
        "- Cumul avec d'autres financements possible mais pas de double financement sur les mêmes dépenses\n"
        "- Point de contact national (PCN) Cluster 2 géré par le Ministère de l'Enseignement Supérieur et de la Recherche\n"
        "- Appels publiés sur le portail Funding & Tenders : https://ec.europa.eu/info/funding-tenders/\n"
        "- Programmation en cours jusqu'à 2027, derniers appels prévus en 2027"
    ),
    "demarche_description": (
        "1. Identifier un appel à propositions pertinent sur le portail Funding & Tenders de la Commission européenne\n"
        "2. Contacter le Point de Contact National (PCN) Cluster 2 pour un accompagnement\n"
        "3. Constituer un consortium transnational (min. 3 entités de 3 pays différents)\n"
        "4. Rédiger la proposition selon le template officiel (Part A : données administratives, Part B : description technique)\n"
        "5. Soumettre la proposition en ligne sur le portail avant la date limite\n"
        "6. Attendre l'évaluation par les experts (4 à 6 mois)\n"
        "7. En cas de sélection, négocier la Grant Agreement avec la Commission"
    ),
    "documents_requis": [
        "Formulaire Part A (données administratives et financières)",
        "Part B (description technique et scientifique du projet)",
        "Budget détaillé par partenaire",
        "Lettres d'engagement des partenaires du consortium",
        "PIC (Participant Identification Code) de chaque partenaire",
        "Validation financière de l'entité coordinatrice",
    ],
    "delai_instruction": "6 à 12 mois (de la soumission à la signature du Grant Agreement)",
    "permanent": False,
    "url_officielle": "https://ec.europa.eu/info/funding-tenders/",
    "formulaire_url": None,
    "tags": [
        "Horizon Europe", "Europe", "recherche", "innovation",
        "patrimoine culturel", "consortium", "Cluster 2", "2021-2027",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte (tout patrimoine éligible)

# Propriétaires : principalement collectivités, associations, établissements publics
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "public_departement"},
    {"aide_id": aide_id, "proprietaire_code": "public_region"},
    {"aide_id": aide_id, "proprietaire_code": "public_etat"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
    {"aide_id": aide_id, "proprietaire_code": "mixte"},
]).execute()
print("  ✓ Propriétaires insérés")

# Travaux : large spectre (recherche & innovation sur patrimoine)
supabase.table("aides_travaux").insert([
    {"aide_id": aide_id, "travaux_code": "restauration_generale"},
    {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    {"aide_id": aide_id, "travaux_code": "facade"},
    {"aide_id": aide_id, "travaux_code": "maconnerie"},
    {"aide_id": aide_id, "travaux_code": "vitraux"},
    {"aide_id": aide_id, "travaux_code": "peintures_murales"},
]).execute()
print("  ✓ Travaux insérés")

# Régions : aide européenne (toutes régions) → pas de contrainte
# Segments : principalement communes et associations
# État de conservation : pas de contrainte

print(f"\n✅ Horizon Europe Patrimoine inséré avec succès (id: {aide_id})")
