"""
Seed: Programme LIFE — Projets environnement, climat et énergie propre
appliqués au patrimoine bâti.

Run:
    cd backend && uv run python3 scripts/seed_aide_life.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Programme LIFE — Projets environnement et climat appliqués au patrimoine bâti",
    "nom_court": "Programme LIFE",
    "description": "Programme européen finançant des projets innovants en environnement et climat, pouvant inclure la rénovation énergétique et l'adaptation climatique de bâtiments patrimoniaux.",
    "description_longue": (
        "Le programme LIFE est l'instrument financier de l'Union européenne dédié "
        "à l'environnement et à l'action pour le climat, doté de 5,4 milliards d'euros "
        "pour 2021-2027. Il comporte quatre sous-programmes : Nature et biodiversité, "
        "Économie circulaire et qualité de vie, Atténuation et adaptation au changement "
        "climatique, et Transition vers une énergie propre. Bien que LIFE ne soit pas un "
        "programme patrimonial, il peut financer des projets portant sur la rénovation "
        "énergétique de bâtiments historiques, l'adaptation climatique du patrimoine bâti, "
        "ou des approches innovantes d'économie circulaire appliquées à la restauration. "
        "Le programme fonctionne par appels à projets annuels publiés sur le portail "
        "Funding & Tenders de la Commission européenne. Les projets doivent être innovants, "
        "reproductibles et apporter une valeur ajoutée européenne."
    ),
    "categorie": "europe",
    "type": "subvention",
    "organisme": "Commission européenne — CINEA (Agence exécutive européenne pour le climat, les infrastructures et l'environnement)",
    "montant_max": None,
    "taux_max": 75,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": True,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Le programme LIFE ne finance pas directement la restauration patrimoniale. "
        "Il finance des projets innovants en environnement et climat qui PEUVENT concerner "
        "le patrimoine bâti (rénovation énergétique, adaptation climatique, économie circulaire "
        "appliquée à la restauration).\n"
        "- Fonctionne par appels à projets annuels (pas de guichet permanent). Les appels "
        "sont publiés chaque année entre mars et mai.\n"
        "- Quatre sous-programmes avec des taux de cofinancement différents :\n"
        "  • Nature et biodiversité : jusqu'à 75 % (espèces/habitats prioritaires) ou 67 % "
        "(mixte prioritaire/non prioritaire), budget 2,14 Md€\n"
        "  • Économie circulaire et qualité de vie : jusqu'à 60 %, budget 1,35 Md€\n"
        "  • Atténuation et adaptation au changement climatique : jusqu'à 60 %\n"
        "  • Transition vers une énergie propre : jusqu'à 95 % (actions de coordination "
        "et de soutien)\n"
        "- Bénéficiaires éligibles : toute entité juridique publique ou privée enregistrée "
        "dans l'UE ou dans un pays associé au programme. Les particuliers ne sont pas "
        "éligibles directement.\n"
        "- Les projets doivent démontrer un caractère innovant, reproductible et une valeur "
        "ajoutée européenne.\n"
        "- LIFE ne cofinance ni les projets de recherche fondamentale, ni les projets "
        "d'infrastructures classiques.\n"
        "- Types de projets pertinents pour le patrimoine :\n"
        "  • Projets pilotes de rénovation énergétique de bâtiments historiques\n"
        "  • Adaptation au changement climatique du patrimoine bâti\n"
        "  • Réemploi de matériaux et économie circulaire dans la restauration\n"
        "  • Gestion durable de sites naturels patrimoniaux (parcs, jardins historiques)\n"
        "- Durée typique des projets : 3 à 5 ans.\n"
        "- Le cofinancement (part non-UE) peut provenir de fonds publics nationaux, "
        "régionaux ou de fonds propres."
    ),
    "demarche_description": (
        "1. Identifier l'appel à projets pertinent sur le portail Funding & Tenders "
        "de la Commission européenne\n"
        "2. Constituer un consortium de partenaires si nécessaire (pas toujours obligatoire "
        "pour LIFE, contrairement à d'autres programmes)\n"
        "3. S'inscrire sur le portail et obtenir un PIC (Participant Identification Code)\n"
        "4. Contacter le Point de Contact National LIFE en France (Ministère de la "
        "Transition écologique) pour un accompagnement\n"
        "5. Préparer et soumettre la candidature en ligne (concept note puis candidature "
        "complète en deux étapes pour certains appels)\n"
        "6. Attendre l'évaluation par les experts de la CINEA (6 à 9 mois)"
    ),
    "documents_requis": [
        "Formulaire de candidature en ligne (Funding & Tenders Portal)",
        "Description technique détaillée du projet",
        "Budget prévisionnel détaillé",
        "Analyse d'impact environnemental attendu",
        "Plan de réplication et de transférabilité",
        "Documents légaux de l'organisation (statuts, etc.)",
        "Preuves de capacité financière et opérationnelle",
        "Lettres de soutien des partenaires le cas échéant",
    ],
    "delai_instruction": "6 à 9 mois après la date limite de soumission",
    "permanent": False,
    "url_officielle": "https://cinea.ec.europa.eu/programmes/life_en",
    "formulaire_url": "https://ec.europa.eu/info/funding-tenders/",
    "tags": [
        "LIFE", "Europe", "environnement", "climat", "énergie",
        "rénovation énergétique", "économie circulaire", "biodiversité",
        "2021-2027",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte (le programme n'est pas spécifique aux MH)
# → on n'insère rien dans aides_protections

# Propriétaires : entités juridiques publiques ou privées (pas les particuliers)
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

# Travaux : rénovation énergétique, parcs/jardins, études
supabase.table("aides_travaux").insert([
    {"aide_id": aide_id, "travaux_code": "chauffage"},
    {"aide_id": aide_id, "travaux_code": "electricite"},
    {"aide_id": aide_id, "travaux_code": "ventilation"},
    {"aide_id": aide_id, "travaux_code": "protection_solaire"},
    {"aide_id": aide_id, "travaux_code": "parcs_jardins"},
    {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    {"aide_id": aide_id, "travaux_code": "toiture"},
    {"aide_id": aide_id, "travaux_code": "facade"},
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

print(f"\n✅ Programme LIFE inséré avec succès (id: {aide_id})")
