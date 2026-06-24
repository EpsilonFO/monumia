"""
Seed: Fondation Crédit Agricole — Pays de France.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_fondation_credit_agricole.py
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
            "nom": "Fondation Crédit Agricole — Pays de France",
            "nom_court": "Fondation CA Pays de France",
            "description": "Mécénat de la Fondation Crédit Agricole Pays de France pour la préservation et la valorisation du patrimoine culturel et naturel porté par des acteurs locaux d'intérêt général.",
            "description_longue": (
                "Depuis 1979, la Fondation Crédit Agricole Pays de France soutient des projets de "
                "préservation et de valorisation du patrimoine culturel portés par des acteurs locaux, "
                "associatifs et publics. Pionnière du mécénat d'entreprise en France, elle a soutenu "
                "plus de 1 400 projets aux côtés du Groupe Crédit Agricole. La Fondation finance le "
                "patrimoine bâti (monuments, édifices religieux, bâtiments historiques), le patrimoine "
                "artistique (œuvres d'art, mobilier), les musées et écomusées, le patrimoine industriel, "
                "agricole et maritime, ainsi que le patrimoine naturel et la biodiversité. Les projets "
                "sont sélectionnés sur leur intérêt patrimonial, leur impact territorial et l'engagement "
                "d'une communauté locale. Les candidatures transitent par la plateforme CA-Engages et "
                "les Caisses régionales du Crédit Agricole."
            ),
            "categorie": "fondation",
            "type": "mecenat",
            "organisme": "Fondation Crédit Agricole — Pays de France",
            "montant_max": None,
            "taux_max": None,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": True,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Porteurs de projets éligibles : structures d'intérêt général éligibles au mécénat\n"
                "  • Associations loi 1901\n"
                "  • Collectivités territoriales (communes, EPCI, départements, régions)\n"
                "  • Établissements publics\n"
                "  • Fondations reconnues d'utilité publique\n"
                "- Les structures à but lucratif (entreprises, SCI, personnes physiques) ne sont PAS éligibles\n"
                "- La structure doit disposer d'un rescrit fiscal ou être éligible au mécénat\n"
                "- Types de patrimoine soutenus :\n"
                "  • Patrimoine bâti (monuments, édifices religieux, bâtiments historiques)\n"
                "  • Patrimoine artistique (œuvres d'art, mobilier, objets d'art)\n"
                "  • Musées et écomusées\n"
                "  • Patrimoine industriel, agricole et maritime\n"
                "  • Patrimoine naturel et biodiversité\n"
                "  • Animation locale liée au patrimoine\n"
                "- Critères de sélection :\n"
                "  • Intérêt patrimonial du projet (indépendamment de la protection MH)\n"
                "  • Impact en matière d'attractivité et de développement du territoire\n"
                "  • Engagement d'une communauté locale autour du projet\n"
                "  • Solidité du plan de financement et cofinancements\n"
                "  • Ouverture au public ou visibilité depuis la voie publique\n"
                "- Projets exclus :\n"
                "  • Travaux d'accessibilité ou de mise en conformité seuls\n"
                "  • Opérations ponctuelles ou événementielles\n"
                "  • Projets de recherche, production d'ouvrages, films et podcasts\n"
                "- Le parrainage d'une Caisse régionale du Crédit Agricole est un atout significatif\n"
                "- Les sites ou œuvres doivent être ouverts à la visite ou visibles du grand public\n"
                "- Couverture : France métropolitaine et outre-mer"
            ),
            "demarche_description": (
                "1. Prendre contact avec la Caisse régionale du Crédit Agricole de votre territoire\n"
                "2. Déposer le dossier de candidature sur la plateforme CA-Engages (www.ca-engages.fr)\n"
                "3. La Caisse régionale peut parrainer le projet et le présenter à la Fondation\n"
                "4. Instruction par le comité de sélection de la Fondation Pays de France\n"
                "5. Notification de la décision et convention de mécénat\n"
                "6. Versement de l'aide selon l'avancement du projet\n"
                "7. Bilan et communication sur le projet achevé"
            ),
            "documents_requis": [
                "Dossier de candidature via la plateforme CA-Engages",
                "Statuts de la structure porteuse",
                "Rescrit fiscal ou justificatif d'éligibilité au mécénat",
                "Budget prévisionnel et plan de financement",
                "Description du projet patrimonial et de son intérêt",
                "Photographies et documentation sur le patrimoine concerné",
                "Lettre de parrainage de la Caisse régionale (recommandé)",
            ],
            "delai_instruction": "3 à 6 mois",
            "permanent": True,
            "url_officielle": "https://fondation-ca-paysdefrance.org/",
            "formulaire_url": "https://www.ca-engages.fr",
            "tags": [
                "Fondation Crédit Agricole",
                "Pays de France",
                "mécénat",
                "fondation",
                "patrimoine culturel",
                "patrimoine naturel",
                "biodiversité",
                "association",
                "collectivité",
                "territoire",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (l'intérêt patrimonial est évalué indépendamment de la protection MH)

# Propriétaires : structures d'intérêt général uniquement
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()

# Travaux : pas de contrainte (tous types de restauration patrimoniale)

# Régions : aide nationale → pas de contrainte

# Segments : commune (publics + asso, pas les privés)
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
    ]
).execute()

# État de conservation : pas de contrainte

print(f"\n✅ Fondation Crédit Agricole — Pays de France inséré avec succès (id: {aide_id})")
