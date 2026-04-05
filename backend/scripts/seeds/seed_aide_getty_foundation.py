"""
Seed: Getty Foundation — Conservation du patrimoine architectural.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_getty_foundation.py
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
    supabase.table("aides_v2")
    .insert(
        {
            "nom": "Getty Foundation — Programmes de conservation du patrimoine architectural",
            "nom_court": "Getty Foundation",
            "description": "Fondation américaine finançant des programmes de conservation du patrimoine architectural à l'international, notamment via des bourses de recherche, des résidences et des subventions pour plans de conservation.",
            "description_longue": (
                "La Getty Foundation, basée à Los Angeles, est l'une des plus importantes fondations "
                "mondiales dédiées au patrimoine et aux arts visuels. Elle finance des programmes de "
                "conservation du patrimoine architectural à l'international. Son programme phare "
                "« Keeping It Modern » (2014-2020) a soutenu 90 projets de conservation de bâtiments "
                "remarquables du XXe siècle dans le monde, finançant des plans de gestion de conservation, "
                "des études de diagnostic et des analyses de matériaux modernes. Bien que Keeping It Modern "
                "soit désormais clôturé, la Getty Foundation continue de proposer des programmes de "
                "subventions pour la conservation du patrimoine : bourses de recherche (Conservation Guest "
                "Scholars), programmes de formation professionnelle, et initiatives ponctuelles comme "
                "« Conserving Black Modernism ». Les subventions vont de 21 500 $ (résidence 3 mois) "
                "à plusieurs centaines de milliers de dollars pour les projets de conservation. Les "
                "candidatures sont ouvertes aux institutions et professionnels du monde entier, y compris "
                "en France."
            ),
            "categorie": "fondation",
            "type": "subvention",
            "organisme": "Getty Foundation (J. Paul Getty Trust)",
            "montant_max": None,
            "taux_max": None,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": True,
            "conditions_eligibilite_detail": (
                "- La Getty Foundation finance principalement des institutions (musées, universités, collectivités), pas des particuliers\n"
                "- Les bâtiments privés ne sont généralement PAS éligibles aux programmes de conservation architecturale\n"
                "- Le programme « Keeping It Modern » est clôturé depuis 2020 (90 projets financés au total)\n"
                "- Programmes encore actifs en 2026 :\n"
                "  • Conservation Guest Scholars : résidence de 3 à 6 mois au Getty Conservation Institute (21 500 $ à 43 000 $) ; ouvert aux professionnels avec au moins 7 ans d'expérience en conservation\n"
                "  • Subventions ponctuelles pour la conservation du patrimoine architectural (montants variables, sur appel à projets)\n"
                "- Les projets doivent contribuer à l'avancement des pratiques de conservation (dimension recherche/innovation)\n"
                "- Les candidats doivent démontrer un bilan de publications ou de contributions au domaine de la conservation\n"
                "- Les projets de recherche doctorale ou post-doctorale NE SONT PAS éligibles\n"
                "- Les candidatures sont ouvertes à toutes les nationalités\n"
                "- Le patrimoine éligible est principalement l'architecture du XXe siècle (pour les anciens programmes) ou le patrimoine bâti en général\n"
                "- Les projets financés doivent inclure : plans de gestion de conservation, études de diagnostic, analyse de matériaux, formation\n"
                "- La Getty Foundation publie des appels à projets spécifiques sur getty.edu/funding/opportunities\n"
                "- Les monuments historiques français classés ou inscrits peuvent être éligibles si le projet s'inscrit dans un programme Getty actif"
            ),
            "demarche_description": (
                "1. Consulter les programmes ouverts sur getty.edu/funding/opportunities\n"
                "2. Vérifier les critères d'éligibilité du programme visé\n"
                "3. Préparer le dossier de candidature selon les instructions du programme\n"
                "4. Soumettre la candidature en ligne avant la date limite du cycle\n"
                "5. Évaluation par un comité d'experts internationaux\n"
                "6. Notification des résultats (généralement 3 à 6 mois après la date limite)\n"
                "7. Convention de financement et mise en œuvre du projet"
            ),
            "documents_requis": [
                "Formulaire de candidature du programme Getty visé",
                "CV et publications du candidat / de l'équipe",
                "Description détaillée du projet de conservation",
                "Budget prévisionnel",
                "Documentation du site (photos, plans, rapports de diagnostic)",
                "Lettres de soutien des partenaires institutionnels",
            ],
            "delai_instruction": "3 à 6 mois",
            "permanent": False,
            "url_officielle": "https://www.getty.edu/foundation/",
            "formulaire_url": "https://www.getty.edu/funding/opportunities/",
            "tags": [
                "Getty Foundation",
                "Keeping It Modern",
                "conservation",
                "architecture XXe",
                "recherche",
                "international",
                "patrimoine bâti",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : classé et inscrit principalement (sites remarquables)
supabase.table("aides_protections").insert(
    [
        {"aide_id": aide_id, "protection_code": "classe"},
        {"aide_id": aide_id, "protection_code": "inscrit"},
    ]
).execute()
print("  ✓ Protections insérées")

# Propriétaires : principalement publics et associations/institutions
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : études, restauration, conservation
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : nationale (pas de contrainte — programme international)

# Segments : communes principalement
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte stricte

print(f"\n✅ Getty Foundation insérée avec succès (id: {aide_id})")
