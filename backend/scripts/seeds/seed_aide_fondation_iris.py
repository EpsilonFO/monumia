"""
Seed: Fondation Iris — Appel à projets zones humides.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_fondation_iris.py
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
            "nom": "Fondation Iris — Appel à projets pour la préservation des zones humides",
            "nom_court": "Fondation Iris",
            "description": "Subvention de la Fondation Iris (sous égide Fondation de France) pour des projets de préservation et de restauration de zones humides en France métropolitaine et outre-mer.",
            "description_longue": (
                "La Fondation Iris, fondation privée sous l'égide de la Fondation de France créée en 2012, "
                "soutient des projets de préservation de sites naturels et d'espèces menacées. Son appel "
                "à projets annuel est exclusivement dédié à la protection et à la mise en valeur des zones "
                "humides : marais, mares, tourbières, mangroves, lagunes, deltas, embouchures, ripisylves. "
                "Les financements sont attribués au cas par cas, sans montant minimum ni maximum. Sont "
                "éligibles les associations, fonds de dotation, fondations, universités et établissements "
                "publics enregistrés en France menant des projets d'intérêt général. Une attention "
                "particulière est portée aux projets favorisant les synergies entre acteurs d'un territoire "
                "et s'inscrivant dans les politiques publiques en faveur des zones humides."
            ),
            "categorie": "fondation",
            "type": "appel_a_projets",
            "organisme": "Fondation Iris (sous égide Fondation de France)",
            "montant_max": None,
            "taux_max": None,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Structures éligibles : associations loi 1901, fonds de dotation, fondations, "
                "universités, établissements publics enregistrés en France\n"
                "- Les entreprises et les particuliers ne sont pas éligibles\n"
                "- Les collectivités territoriales ne sont pas directement éligibles, mais peuvent "
                "être partenaires d'un porteur associatif\n"
                "- Le projet doit concerner la préservation ou la restauration de zones humides :\n"
                "  • Marais, mares, tourbières, bourbiers, marécages\n"
                "  • Mangroves, lagunes, deltas, embouchures\n"
                "  • Ripisylves (forêts riveraines)\n"
                "- Deux modes d'action privilégiés :\n"
                "  • Préservation : actions concrètes de terrain (acquisition foncière, gardiennage, "
                "aménagement, plaidoyer)\n"
                "  • Recherche et exploration : expéditions scientifiques et études\n"
                "- Les projets de sensibilisation et d'éducation à la nature seuls ne sont plus retenus "
                "depuis 2026\n"
                "- Pas de montant minimum ni maximum — évaluation au cas par cas\n"
                "- Pas de taux de cofinancement imposé\n"
                "- Attention particulière aux projets qui :\n"
                "  • Favorisent les synergies entre différents acteurs d'un même territoire\n"
                "  • S'inscrivent dans les politiques publiques en faveur des zones humides\n"
                "  • Permettent de maintenir la pérennité de zones humides existantes\n"
                "- Le projet peut concerner la France métropolitaine et l'outre-mer\n"
                "- Le lien avec le patrimoine bâti est pertinent lorsque des monuments historiques "
                "sont situés en zone humide ou comprennent des éléments hydrauliques patrimoniaux "
                "(douves, canaux, bassins, systèmes d'irrigation historiques)"
            ),
            "demarche_description": (
                "1. Consulter le thème de l'appel à projets en cours sur le site de la Fondation Iris\n"
                "2. Vérifier l'éligibilité de la structure porteuse (association, fondation, établissement public)\n"
                "3. Soumettre le dossier de candidature en ligne avant la date limite de l'appel à projets\n"
                "4. La Fondation évalue les projets et sélectionne les lauréats\n"
                "5. Convention de financement signée avec la Fondation\n"
                "6. Mise en œuvre du projet avec reporting régulier"
            ),
            "documents_requis": [
                "Dossier de candidature en ligne (formulaire Fondation Iris)",
                "Description détaillée du projet et de la zone humide concernée",
                "Budget prévisionnel détaillé",
                "Plan de financement (autres cofinancements éventuels)",
                "Statuts de la structure porteuse",
                "Rapport d'activité de la structure",
            ],
            "delai_instruction": "3 à 6 mois",
            "permanent": False,
            "url_officielle": "https://www.fondationiris.org/soumettre-un-projet/",
            "formulaire_url": "https://www.fondationiris.org/soumettre-un-projet/",
            "tags": [
                "Fondation Iris",
                "zones humides",
                "biodiversité",
                "patrimoine naturel",
                "marais",
                "tourbières",
                "mangroves",
                "Fondation de France",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (sites naturels, pas de lien MH direct)

# Propriétaires : associations et établissements publics
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "association"},
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : parcs et jardins (zones humides = patrimoine paysager/naturel)
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "parcs_jardins"},
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale → pas de contrainte

# Segments : commune (collectivités partenaires) — pas de contrainte stricte

# État de conservation : pas de contrainte

print(f"\n✅ Fondation Iris insérée avec succès (id: {aide_id})")
