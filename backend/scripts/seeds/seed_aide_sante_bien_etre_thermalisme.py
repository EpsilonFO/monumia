"""
Seed: Santé, bien-être, thermalisme — Aides à la valorisation touristique et thermale du patrimoine.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_sante_bien_etre_thermalisme.py
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
    supabase.table("aides_v3")
    .insert(
        {
            "nom": "Santé, bien-être et thermalisme — Aides à la valorisation touristique du patrimoine thermal",
            "nom_court": "Thermalisme & bien-être",
            "description": "Aides régionales, Banque des Territoires et plan Destination France pour la rénovation et la valorisation de bâtiments patrimoniaux à vocation thermale, de bien-être ou de santé. Prêts bonifiés et subventions régionales variables.",
            "description_longue": (
                "Plusieurs dispositifs publics soutiennent la rénovation et la reconversion de bâtiments "
                "patrimoniaux à vocation thermale, de bien-être ou de santé. Le plan Destination France "
                "inclut un volet dédié au thermalisme et au tourisme de bien-être, avec des prêts Patrimoine "
                "& Tourisme de la Banque des Territoires pour les monuments historiques accueillant des "
                "activités de santé ou de bien-être. Les Régions (notamment Occitanie, Auvergne-Rhône-Alpes, "
                "Nouvelle-Aquitaine) proposent des aides spécifiques pour la modernisation des stations "
                "thermales et la diversification vers le bien-être. Les collectivités propriétaires "
                "d'établissements thermaux classés ou inscrits MH peuvent combiner ces aides avec les "
                "subventions DRAC pour la restauration des parties protégées. Le patrimoine thermal français "
                "(thermes historiques, casinos, parcs, buvettes) représente un patrimoine architectural "
                "exceptionnel souvent classé ou inscrit."
            ),
            "categorie": "region",
            "type": "subvention",
            "organisme": "Régions / Banque des Territoires / Plan Destination France",
            "montant_max": None,
            "taux_max": 50,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": True,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Le projet doit concerner un bâtiment patrimonial (classé, inscrit ou présentant un intérêt patrimonial reconnu) à vocation thermale, de bien-être ou de santé\n"
                "- Bénéficiaires éligibles : collectivités territoriales, établissements publics, SEM, SPL, entreprises du secteur thermal, associations gestionnaires\n"
                "- Les particuliers propriétaires peuvent être éligibles aux prêts Banque des Territoires si le projet est à vocation touristique\n"
                "- Types de projets éligibles :\n"
                "  • Rénovation et mise aux normes d'établissements thermaux historiques\n"
                "  • Création d'espaces de bien-être / spa dans un bâtiment patrimonial\n"
                "  • Reconversion d'un bâtiment patrimonial en lieu de santé ou de bien-être\n"
                "  • Aménagement d'espaces d'accueil et de soins dans un monument\n"
                "  • Restauration des éléments patrimoniaux (façades, décors, espaces thermaux historiques)\n"
                "- Prêts Banque des Territoires — Patrimoine & Tourisme :\n"
                "  • Durée : jusqu'à 40 ans\n"
                "  • Taux bonifié\n"
                "  • Pour les monuments classés/inscrits accueillant une activité touristique ou de bien-être\n"
                "  • Montant : à partir de 100 000 €\n"
                "- Aides régionales (variables selon les régions) :\n"
                "  • Occitanie : aide à la modernisation des stations thermales (jusqu'à 40 % du projet)\n"
                "  • Auvergne-Rhône-Alpes : soutien aux projets touristiques structurants (jusqu'à 30 %)\n"
                "  • Nouvelle-Aquitaine : accompagnement de la filière thermale\n"
                "- Plan Destination France :\n"
                "  • Soutien à la diversification des stations thermales vers le bien-être\n"
                "  • Accompagnement des projets structurants\n"
                "  • Ingénierie touristique pour les territoires thermaux\n"
                "- Le projet doit s'inscrire dans une logique de développement touristique durable\n"
                "- Cofinancement généralement requis (autofinancement minimum 20-30 %)\n"
                "- Les travaux sur les parties protégées MH restent éligibles aux subventions DRAC en complément\n"
                "- Le projet doit démontrer un impact économique et touristique pour le territoire\n"
                "- Conformité aux normes sanitaires et d'accessibilité ERP requise"
            ),
            "demarche_description": (
                "1. Définir le projet de valorisation thermale/bien-être du bâtiment patrimonial\n"
                "2. Contacter la Région et la Banque des Territoires pour identifier les dispositifs applicables\n"
                "3. Réaliser une étude de faisabilité technico-économique\n"
                "4. Constituer le dossier : projet architectural, business plan, plan de financement\n"
                "5. Déposer les demandes d'aides auprès des différents financeurs (Région, BdT, DRAC si MH)\n"
                "6. Obtenir les autorisations de travaux (permis, ABF si périmètre MH)\n"
                "7. Réaliser les travaux et transmettre les justificatifs\n"
                "8. Rendre compte de l'impact touristique et économique"
            ),
            "documents_requis": [
                "Étude de faisabilité technico-économique",
                "Projet architectural détaillé",
                "Business plan et prévisions d'exploitation",
                "Plan de financement prévisionnel",
                "Devis détaillés des travaux",
                "Autorisation de travaux (permis de construire ou déclaration préalable)",
                "Avis de l'ABF si périmètre MH ou SPR",
                "Statuts de la structure porteuse",
                "Délibération de la collectivité (si applicable)",
            ],
            "delai_instruction": "3 à 6 mois",
            "permanent": True,
            "url_officielle": "https://www.entreprises.gouv.fr/priorites-et-actions/proximite-et-territoires/renforcer-le-secteur-du-tourisme/le-plan-destination",
            "formulaire_url": None,
            "tags": [
                "thermalisme",
                "bien-être",
                "santé",
                "tourisme",
                "patrimoine thermal",
                "Destination France",
                "Banque des Territoires",
                "spa",
                "station thermale",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (tous types de bâtiments patrimoniaux)

# Propriétaires : collectivités, associations, SEM
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
        {"aide_id": aide_id, "proprietaire_code": "mixte"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux éligibles
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "plomberie"},
        {"aide_id": aide_id, "travaux_code": "accessibilite"},
        {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
        {"aide_id": aide_id, "travaux_code": "electricite"},
        {"aide_id": aide_id, "travaux_code": "chauffage"},
        {"aide_id": aide_id, "travaux_code": "ventilation"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale (via Destination France) + régionales → pas de contrainte

# Segments : tous
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
        {"aide_id": aide_id, "segment_code": "prive"},
    ]
).execute()
print("  ✓ Segments insérés")

print(f"\n✅ Santé, bien-être, thermalisme inséré avec succès (id: {aide_id})")
