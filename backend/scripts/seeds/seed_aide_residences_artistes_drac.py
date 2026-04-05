"""
Seed: Résidences d'artistes en territoire (DRAC).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_residences_artistes_drac.py
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
            "nom": "Résidences d'artistes en territoire (DRAC)",
            "nom_court": "Résidences artistes DRAC",
            "description": "Subvention DRAC pour accueillir des résidences d'artistes en territoire, notamment en milieu rural. Soutien à la création artistique et à la médiation culturelle.",
            "description_longue": (
                "Les Directions Régionales des Affaires Culturelles (DRAC) soutiennent l'implantation "
                "de résidences d'artistes sur les territoires, en particulier en milieu rural et dans les "
                "quartiers prioritaires de la politique de la ville. Le dispositif vise à favoriser la "
                "présence artistique de longue durée, la rencontre entre artistes et habitants, et la "
                "médiation culturelle. Les résidences peuvent être de création, de diffusion ou de "
                "médiation. Le porteur de projet (collectivité, association, établissement culturel) "
                "accueille un ou plusieurs artistes pour une durée de 2 à 3 mois minimum. La subvention "
                "DRAC ne peut excéder 50 % du coût total du projet, avec un plafond variable selon les "
                "régions (généralement 10 000 à 15 000 €). Le dispositif s'inscrit dans la politique "
                "de démocratisation culturelle et d'aménagement du territoire du Ministère de la Culture."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "Ministère de la Culture — Direction Régionale des Affaires Culturelles (DRAC)",
            "montant_max": 15000,
            "taux_max": 50,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": True,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Le porteur de projet doit être une collectivité territoriale, un EPCI, une association culturelle, un établissement public culturel ou un lieu patrimonial\n"
                "- La résidence doit se dérouler sur une durée minimale de 2 à 3 mois (dont au moins 1 mois continu de présence de l'artiste)\n"
                "- Priorité aux territoires ruraux, zones peu dotées en équipements culturels, et quartiers prioritaires de la politique de la ville (QPV)\n"
                "- Tous les champs artistiques sont éligibles : spectacle vivant, arts visuels, musique, cinéma, littérature, arts numériques, etc.\n"
                "- Le projet doit inclure un volet médiation / rencontre avec les habitants (ateliers, restitutions publiques, échanges)\n"
                "- La subvention DRAC ne peut excéder 50 % du coût total du projet\n"
                "- Plafond de subvention généralement compris entre 10 000 € et 15 000 € (variable selon la DRAC régionale)\n"
                "- Le cofinancement est requis : collectivités locales, mécénat, autofinancement\n"
                "- Le dossier doit être déposé sur la plateforme Démarches simplifiées avant la date limite fixée par chaque DRAC (généralement entre juin et septembre)\n"
                "- La candidature doit préciser : le projet artistique, le lieu d'accueil, les conditions d'hébergement et de travail de l'artiste, le programme de médiation, le budget prévisionnel\n"
                "- Les monuments historiques (classés ou inscrits) peuvent servir de lieu d'accueil pour la résidence, renforçant l'éligibilité\n"
                "- L'artiste doit être rémunéré selon les standards en vigueur (respect des conventions collectives)\n"
                "- Partenariat avec des établissements scolaires, structures sociales ou associations locales fortement encouragé\n"
                "- Le projet ne doit pas avoir déjà commencé au moment du dépôt de la demande"
            ),
            "demarche_description": (
                "1. Contacter la DRAC de sa région pour connaître les modalités et le calendrier de l'appel à projets\n"
                "2. Constituer le dossier : projet artistique, CV de l'artiste, programme de médiation, budget prévisionnel, lettres de partenariat\n"
                "3. Déposer le dossier sur la plateforme Démarches simplifiées avant la date limite\n"
                "4. Instruction par la DRAC (2 à 4 mois)\n"
                "5. Notification de la décision et conventionnement\n"
                "6. Réalisation de la résidence et transmission du bilan"
            ),
            "documents_requis": [
                "Projet artistique détaillé",
                "CV et portfolio de l'artiste accueilli",
                "Programme de médiation et d'actions culturelles",
                "Budget prévisionnel détaillé",
                "Plan de financement avec cofinancements",
                "Lettres d'engagement des partenaires locaux",
                "Description du lieu d'accueil et des conditions d'hébergement",
                "Statuts de la structure porteuse (si association)",
            ],
            "delai_instruction": "2 à 4 mois",
            "permanent": False,
            "url_officielle": "https://www.culture.gouv.fr/catalogue-des-demarches-et-subventions/appels-a-projets-candidatures/residences-d-artistes-en-territoire",
            "formulaire_url": None,
            "tags": [
                "DRAC",
                "résidence artiste",
                "médiation culturelle",
                "ruralité",
                "création artistique",
                "territoire",
                "QPV",
                "patrimoine vivant",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (tous monuments éligibles comme lieu d'accueil)

# Propriétaires : collectivités et associations principalement
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : pas directement lié aux travaux (aide culturelle)
# Pas de contrainte → aucune insertion

# Segments
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
    ]
).execute()
print("  ✓ Segments insérés")

# Régions : aide nationale → pas de contrainte

# État de conservation : pas de contrainte

print(f"\n✅ Résidences d'artistes DRAC inséré avec succès (id: {aide_id})")
