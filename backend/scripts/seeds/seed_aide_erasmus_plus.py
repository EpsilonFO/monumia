"""
Seed: Erasmus+ — Formation professionnelle et mobilités dans les métiers
du patrimoine.

Run:
    cd backend && uv run python3 scripts/seed_aide_erasmus_plus.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = (
    supabase.table("aides_v2")
    .insert(
        {
            "nom": "Erasmus+ — Formation professionnelle et mobilités dans les métiers du patrimoine",
            "nom_court": "Erasmus+",
            "description": "Programme européen finançant la mobilité et la formation professionnelle, mobilisable pour les échanges de savoir-faire et la formation aux métiers de la restauration du patrimoine.",
            "description_longue": (
                "Erasmus+ est le programme de l'Union européenne pour l'éducation, la formation, "
                "la jeunesse et le sport, doté de 26,2 milliards d'euros pour 2021-2027. "
                "Dans le contexte du patrimoine, Erasmus+ peut financer : la mobilité des "
                "apprentis et professionnels des métiers du patrimoine (compagnons, tailleurs "
                "de pierre, charpentiers, restaurateurs) pour des stages en Europe ; des "
                "partenariats de coopération entre organismes de formation aux métiers du "
                "bâtiment ancien ; des projets d'alliance pour les compétences sectorielles "
                "dans la filière patrimoine/restauration. Le programme est géré en France par "
                "l'Agence Erasmus+ France / Éducation Formation (Bordeaux) pour le volet "
                "éducation/formation et par l'Agence Erasmus+ France / Jeunesse & Sport (Paris) "
                "pour le volet jeunesse. Erasmus+ ne finance pas directement les travaux de "
                "restauration mais les volets formation et échange de compétences."
            ),
            "categorie": "europe",
            "type": "subvention",
            "organisme": "Commission européenne / Agence Erasmus+ France Éducation Formation",
            "montant_max": 400000,
            "taux_max": 80,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Erasmus+ ne finance PAS directement les travaux de restauration. Il finance "
                "la formation, la mobilité et les échanges de savoir-faire liés aux métiers "
                "du patrimoine.\n"
                "- Actions clés mobilisables pour le patrimoine :\n"
                "  • Action clé 1 — Mobilité : stages professionnels en Europe pour apprentis "
                "et salariés des métiers du patrimoine (taille de pierre, charpente, maçonnerie "
                "traditionnelle, restauration). Durée : 2 semaines à 12 mois.\n"
                "  • Action clé 2 — Partenariats de coopération : projets transnationaux entre "
                "organismes de formation pour développer des méthodes pédagogiques innovantes, "
                "des référentiels de compétences, des outils numériques pour les métiers du "
                "patrimoine. Budget max : 120 000 € à 400 000 € selon l'échelle.\n"
                "  • Action clé 2 — Partenariats simplifiés (small-scale) : projets plus courts "
                "et à budget réduit (30 000 € ou 60 000 €) pour des organisations moins "
                "expérimentées.\n"
                "- Bénéficiaires éligibles : organismes de formation, lycées professionnels, "
                "CFA, universités, associations, entreprises, chambres des métiers, collectivités. "
                "Les particuliers ne candidatent pas directement mais participent via leur "
                "organisme d'envoi.\n"
                "- Partenariat transnational : minimum 3 organisations de 3 pays différents "
                "(pour l'action clé 2 standard).\n"
                "- Taux de financement : forfaits couvrant les frais de voyage, séjour, "
                "organisation, gestion de projet. Taux effectif souvent 80-100 % des coûts.\n"
                "- Les appels à projets sont publiés annuellement (généralement en automne pour "
                "l'année suivante) avec des dates limites au printemps.\n"
                "- Les projets doivent contribuer aux priorités Erasmus+ : inclusion, transition "
                "numérique, développement durable, participation citoyenne.\n"
                "- Exemples concrets pour le patrimoine : mobilité d'apprentis tailleurs de pierre "
                "en Italie, partenariat franco-allemand sur la restauration de colombages, "
                "formation numérique à la modélisation 3D de monuments."
            ),
            "demarche_description": (
                "1. Identifier l'action Erasmus+ pertinente (mobilité ou partenariat) sur le "
                "site de l'Agence Erasmus+ France\n"
                "2. Constituer un consortium de partenaires européens si nécessaire\n"
                "3. Préparer le dossier de candidature sur la plateforme en ligne de la "
                "Commission européenne\n"
                "4. Soumettre avant la date limite de l'appel (généralement février-mars "
                "pour la mobilité, mars-avril pour les partenariats)\n"
                "5. Évaluation par l'Agence nationale Erasmus+ France\n"
                "6. Conventionnement et démarrage des activités"
            ),
            "documents_requis": [
                "Formulaire de candidature en ligne (plateforme Erasmus+)",
                "Description du projet et des activités prévues",
                "Programme de mobilité ou plan de travail du partenariat",
                "Lettres de mandat des partenaires européens",
                "Budget prévisionnel (basé sur les forfaits Erasmus+)",
                "Documents légaux de l'organisme candidat",
                "Accréditation Erasmus+ (si applicable, pour la mobilité récurrente)",
            ],
            "delai_instruction": "3 à 5 mois après la date limite de soumission",
            "permanent": False,
            "url_officielle": "https://agence.erasmusplus.fr/",
            "formulaire_url": "https://webgate.ec.europa.eu/erasmus-esc/",
            "tags": [
                "Erasmus+",
                "Europe",
                "formation",
                "mobilité",
                "apprentissage",
                "métiers du patrimoine",
                "compétences",
                "2021-2027",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte

# Propriétaires : structures de formation, collectivités, associations, entreprises
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "mixte"},
    ]
).execute()
print("  ✓ Propriétaires éligibles insérés")

# Travaux : formation liée à tous types de restauration
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "vitraux"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "peintures_murales"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    ]
).execute()
print("  ✓ Travaux éligibles insérés")

# Régions : pas de contrainte géographique

# Segments : tous segments
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
        {"aide_id": aide_id, "segment_code": "prive"},
        {"aide_id": aide_id, "segment_code": "btp"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ Erasmus+ inséré avec succès (id: {aide_id})")
