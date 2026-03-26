"""
Seed: Europe Créative — Projets de coopération européenne (volet Culture / Patrimoine).

Run:
    cd backend && uv run python3 scripts/seed_aide_europe_creative.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Europe Créative — Projets de coopération européenne (volet Culture)",
    "nom_court": "Europe Créative",
    "description": "Programme européen finançant des projets de coopération culturelle transnationale, incluant la valorisation et la médiation du patrimoine culturel, avec des partenaires de plusieurs pays européens.",
    "description_longue": (
        "Europe Créative est le programme de l'Union européenne dédié aux secteurs "
        "culturels, créatifs et audiovisuels, doté de 2,44 milliards d'euros pour "
        "2021-2027. Le volet Culture soutient des projets de coopération européenne "
        "impliquant des partenaires de plusieurs pays. Les projets patrimoine éligibles "
        "portent sur la valorisation, la médiation, l'innovation numérique et l'engagement "
        "des publics autour du patrimoine culturel. Attention : Europe Créative ne finance "
        "généralement pas directement la restauration physique de monuments, mais plutôt "
        "les projets de coopération, d'innovation et de médiation culturelle autour du "
        "patrimoine. L'appel Coopération est publié annuellement avec trois échelles de "
        "projets (petite, moyenne, grande) offrant des taux de cofinancement de 60 % à 80 %. "
        "Le Relais Culture Europe (Paris) est le point de contact national pour la France "
        "et propose un accompagnement gratuit aux porteurs de projets."
    ),
    "categorie": "europe",
    "type": "subvention",
    "organisme": "Commission européenne — EACEA (Agence exécutive européenne pour l'éducation et la culture)",
    "montant_max": 2000000,
    "taux_max": 80,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": True,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Le programme fonctionne par appels à projets annuels (pas de guichet permanent). "
        "L'appel Coopération 2026 est ouvert du 5 mars au 5 mai 2026.\n"
        "- Europe Créative ne finance généralement pas la restauration physique de monuments. "
        "Il s'agit de projets de coopération, d'innovation, de médiation culturelle autour "
        "du patrimoine.\n"
        "- Trois échelles de projets :\n"
        "  • Petite échelle : min. 3 partenaires de 3 pays différents, subvention max "
        "200 000 €, cofinancement UE jusqu'à 80 %\n"
        "  • Moyenne échelle : min. 5 partenaires de 5 pays différents, subvention max "
        "1 000 000 €, cofinancement UE jusqu'à 70 %\n"
        "  • Grande échelle : min. 10 partenaires de 10 pays différents, subvention max "
        "2 000 000 €, cofinancement UE jusqu'à 60 %\n"
        "- Bénéficiaires éligibles : personnes morales publiques ou privées, à but lucratif "
        "ou non, établies dans un pays de l'UE, de l'EEE ou associé au programme. "
        "Les particuliers ne sont pas éligibles.\n"
        "- La structure coordinatrice doit exister légalement depuis au minimum 2 ans.\n"
        "- Un consortium de partenaires européens est obligatoire.\n"
        "- Durée maximale des projets : 48 mois.\n"
        "- Budget global de l'appel : environ 60 millions d'euros par an.\n"
        "- Préfinancement : 80 % du budget alloué après signature de la convention.\n"
        "- Dépenses éligibles : salaires, sous-traitance, frais de service, soutien "
        "financier à des tiers, coûts directs liés aux activités. Coûts indirects : "
        "forfait de 7 % des coûts directs.\n"
        "- Les projets doivent favoriser la création et la diffusion d'œuvres et d'artistes "
        "en Europe, des approches nouvelles et innovantes dans les secteurs culturels.\n"
        "- Secteurs éligibles : musique, spectacle vivant, patrimoine, arts visuels, "
        "design, architecture, littérature, etc."
    ),
    "demarche_description": (
        "1. Identifier l'appel à projets pertinent sur le Funding & Tenders Portal "
        "de la Commission européenne\n"
        "2. Constituer un consortium de partenaires européens (3, 5 ou 10 pays selon "
        "l'échelle visée)\n"
        "3. S'inscrire sur le portail et obtenir un PIC (Participant Identification Code)\n"
        "4. Contacter le Relais Culture Europe à Paris pour un accompagnement gratuit\n"
        "5. Préparer et soumettre la candidature en ligne avant la date limite\n"
        "6. Attendre l'évaluation par les experts indépendants de l'EACEA"
    ),
    "documents_requis": [
        "Formulaire de candidature en ligne (Funding & Tenders Portal)",
        "Description détaillée du projet et de ses activités",
        "Budget prévisionnel détaillé",
        "Lettres de mandat des partenaires du consortium",
        "Documents légaux de l'organisation (statuts, etc.)",
        "Preuves de capacité financière et opérationnelle",
        "CV des personnes clés du projet",
    ],
    "delai_instruction": "4 à 6 mois après la date limite de soumission",
    "permanent": False,
    "date_limite": "2026-05-05",
    "url_officielle": "https://culture.ec.europa.eu/creative-europe",
    "formulaire_url": "https://ec.europa.eu/info/funding-tenders/",
    "tags": [
        "Europe Créative", "Europe", "coopération culturelle", "patrimoine",
        "médiation", "innovation", "transnational", "2021-2027",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte formelle (pas de restauration physique, plutôt valorisation)
# → on n'insère rien dans aides_protections

# Propriétaires : personnes morales publiques ou privées (pas les particuliers)
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "public_departement"},
    {"aide_id": aide_id, "proprietaire_code": "public_region"},
    {"aide_id": aide_id, "proprietaire_code": "public_etat"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
    {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
    {"aide_id": aide_id, "proprietaire_code": "mixte"},
]).execute()
print("  ✓ Propriétaires éligibles insérés")

# Travaux : plutôt valorisation et médiation que restauration physique
supabase.table("aides_travaux").insert([
    {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    {"aide_id": aide_id, "travaux_code": "restauration_generale"},
]).execute()
print("  ✓ Travaux éligibles insérés")

# Régions : aide européenne, pas de contrainte géographique en France

# Segments : collectivités et privés (personnes morales)
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "commune"},
    {"aide_id": aide_id, "segment_code": "prive"},
]).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ Europe Créative inséré avec succès (id: {aide_id})")
