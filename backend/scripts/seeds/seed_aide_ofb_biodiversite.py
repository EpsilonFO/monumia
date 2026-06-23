"""
Seed: OFB — Aides biodiversité (Atlas de la biodiversité communale, Territoire Engagé pour la Nature).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_ofb_biodiversite.py
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
            "nom": "OFB — Aides à la biodiversité (Atlas de la biodiversité communale & Territoire Engagé pour la Nature)",
            "nom_court": "OFB Biodiversité",
            "description": "Subventions de l'Office Français de la Biodiversité pour les collectivités engagées dans la connaissance et la préservation de la biodiversité, y compris sur les sites patrimoniaux (parcs, jardins historiques, abords de monuments).",
            "description_longue": (
                "L'Office Français de la Biodiversité (OFB) finance les collectivités territoriales pour des "
                "projets de connaissance et de préservation de la biodiversité à travers plusieurs dispositifs : "
                "les Atlas de la Biodiversité Communale (ABC), le programme Territoire Engagé pour la Nature (TEN), "
                "et divers appels à projets thématiques. L'enveloppe 2025 pour les ABC est de 8 millions d'euros, "
                "avec un plafond de 250 000 € par collectivité. Ces aides peuvent être mobilisées pour des projets "
                "intégrant patrimoine bâti et biodiversité : inventaires de la faune et flore dans les parcs et "
                "jardins historiques, aménagements favorables à la biodiversité sur les sites patrimoniaux "
                "(nichoirs, gîtes à chauves-souris dans les combles de monuments, corridors écologiques), "
                "plans de gestion écologique des espaces verts patrimoniaux. Les projets combinant valorisation "
                "du patrimoine culturel et préservation de la biodiversité sont particulièrement encouragés."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "Office Français de la Biodiversité (OFB)",
            "montant_max": 250000,
            "taux_max": 80,
            "montant_min": 5000,
            "plancher": None,
            "base_ttc": True,
            "commune_max_population": None,
            "cofinancement_requis": True,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Atlas de la Biodiversité Communale (ABC) :\n"
                "  • Enveloppe 2025 : 8 M€\n"
                "  • Plafond : 250 000 € par commune ou intercommunalité\n"
                "  • Minimum : 5 000 € de subvention\n"
                "  • Durée du projet : 36 à 48 mois\n"
                "  • Porteurs éligibles : communes et EPCI ayant la compétence urbanisme\n"
                "  • Le projet doit inclure un volet inventaire naturaliste et un volet sensibilisation/mobilisation\n"
                "  • Calendrier 2025 : relève le 21 avril et le 15 juin\n"
                "- Territoire Engagé pour la Nature (TEN) :\n"
                "  • Programme de reconnaissance et d'accompagnement (3 ans renouvelable)\n"
                "  • Porteurs : communes et intercommunalités\n"
                "  • Engagement à mettre en œuvre un plan d'actions pour la biodiversité\n"
                "  • Accès facilité aux financements OFB et partenaires\n"
                "- Appels à projets thématiques (liens intergénérationnels, plans de paysage, etc.) :\n"
                "  • Montants : 5 000 à 60 000 € selon le dispositif\n"
                "  • Projets situés en métropole et dans les DOM (Guadeloupe, Guyane, Martinique, Mayotte, La Réunion)\n"
                "- Le projet peut porter sur des sites patrimoniaux : parcs et jardins historiques, "
                "abords de monuments, espaces verts communaux à valeur patrimoniale\n"
                "- Non éligible : projets sans volet biodiversité, travaux de construction pure\n"
                "- La collectivité doit assurer un cofinancement (part variable selon le dispositif)"
            ),
            "demarche_description": (
                "1. Identifier le dispositif OFB adapté au projet (ABC, TEN, appel à projets thématique)\n"
                "2. Consulter le calendrier des appels à projets sur ofb.gouv.fr\n"
                "3. Prendre contact avec l'Agence Régionale de la Biodiversité (ARB) de votre région\n"
                "4. Constituer le dossier de candidature (description du projet, budget, planning)\n"
                "5. Déposer le dossier sur la plateforme démarches-simplifiées ou aides-territoires\n"
                "6. Instruction par les services de l'OFB\n"
                "7. Notification de la subvention et convention\n"
                "8. Réalisation du projet et rapports d'avancement\n"
                "9. Justification des dépenses et versement du solde"
            ),
            "documents_requis": [
                "Formulaire de candidature OFB",
                "Description détaillée du projet (objectifs, méthodologie, calendrier)",
                "Budget prévisionnel et plan de financement",
                "Délibération de la collectivité approuvant le projet",
                "Cartographie du territoire concerné",
                "Partenariats envisagés (associations naturalistes, CPIE, etc.)",
                "CV des intervenants ou prestataires naturalistes",
                "Lettres de soutien des partenaires",
            ],
            "delai_instruction": "3 à 6 mois",
            "permanent": True,
            "url_officielle": "https://ofb.gouv.fr/financements",
            "formulaire_url": None,
            "tags": [
                "OFB",
                "biodiversité",
                "atlas biodiversité communale",
                "ABC",
                "territoire engagé nature",
                "faune",
                "flore",
                "parcs jardins",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte

# Propriétaires : collectivités publiques
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : parcs/jardins, études
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "parcs_jardins"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale → pas de contrainte

# Segments : communes
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ OFB Biodiversité inséré avec succès (id: {aide_id})")
