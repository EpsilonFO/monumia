"""
Seed: Fondation de France — Programme Patrimoine.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_fondation_de_france_patrimoine.py
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
            "nom": "Fondation de France — Programme Patrimoine",
            "nom_court": "Fondation de France (Patrimoine)",
            "description": "Soutien financier de la Fondation de France pour des projets de restauration et valorisation du patrimoine bâti, paysager et artistique portés par des structures d'intérêt général.",
            "description_longue": (
                "La Fondation de France consacre un programme dédié au patrimoine, finançant des projets "
                "de restauration, préservation et valorisation du patrimoine architectural, paysager, "
                "industriel et artistique. Les aides sont attribuées exclusivement à des structures "
                "d'intérêt général (associations, fondations, collectivités) via des appels à projets "
                "ou des fondations abritées thématiques. La Fondation de France intervient là où les "
                "financements publics sont insuffisants et privilégie les projets combinant restauration "
                "patrimoniale avec des dimensions sociales, éducatives ou écologiques. Elle abrite "
                "également des fondations thématiques dédiées au patrimoine (patrimoine juif, éco-restauration, "
                "patrimoine maritime, etc.) qui lancent leurs propres appels à projets."
            ),
            "categorie": "fondation",
            "type": "subvention",
            "organisme": "Fondation de France",
            "montant_max": None,
            "taux_max": None,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": True,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Porteurs de projets éligibles : structures d'intérêt général uniquement\n"
                "  • Associations loi 1901\n"
                "  • Fondations reconnues d'utilité publique (FRUP)\n"
                "  • Fondations abritées par la Fondation de France\n"
                "  • Collectivités territoriales et établissements publics\n"
                "  • Organismes professionnels à but non lucratif\n"
                "- Les structures lucratives (entreprises, SCI, personnes physiques) ne sont PAS éligibles\n"
                "- Les propriétaires privés personnes physiques ne peuvent pas candidater directement ; "
                "ils doivent passer par une association ou fondation porteuse\n"
                "- Types de patrimoine soutenus :\n"
                "  • Patrimoine architectural (bâti historique, monuments, édifices religieux)\n"
                "  • Patrimoine paysager (parcs, jardins, sites naturels patrimoniaux)\n"
                "  • Patrimoine industriel, agricole, maritime\n"
                "  • Patrimoine artistique (œuvres d'art, mobilier)\n"
                "- Critères de sélection privilégiés :\n"
                "  • Qualité patrimoniale et intérêt historique du projet\n"
                "  • Dimension sociale ou éducative (insertion, formation, sensibilisation)\n"
                "  • Dimension écologique (éco-restauration, matériaux biosourcés, biodiversité)\n"
                "  • Ancrage territorial et impact local\n"
                "  • Plan de financement solide avec cofinancements\n"
                "- Fonctionnement par appels à projets thématiques (calendrier variable)\n"
                "- Les fondations abritées (patrimoine juif, patrimoine maritime, etc.) ont leurs propres "
                "critères et calendriers\n"
                "- Le projet doit être d'intérêt général et bénéficier au plus grand nombre\n"
                "- Les travaux de mise en conformité ou d'accessibilité seuls ne sont généralement pas financés\n"
                "- Les opérations purement événementielles sont exclues"
            ),
            "demarche_description": (
                "1. Consulter les appels à projets en cours sur le site de la Fondation de France\n"
                "2. Vérifier l'éligibilité de la structure porteuse (intérêt général, non lucratif)\n"
                "3. Constituer le dossier de candidature selon les critères de l'appel à projets\n"
                "4. Déposer le dossier en ligne sur la plateforme de la Fondation de France\n"
                "5. Instruction par un comité d'experts (délai variable selon le programme)\n"
                "6. Notification de la décision et convention de financement\n"
                "7. Versement de l'aide selon l'avancement des travaux"
            ),
            "documents_requis": [
                "Dossier de candidature selon le formulaire de l'appel à projets",
                "Statuts de la structure porteuse",
                "Budget prévisionnel détaillé et plan de financement",
                "Description du projet et de son intérêt patrimonial",
                "Devis des travaux envisagés",
                "Justificatifs des cofinancements obtenus ou sollicités",
                "Photographies du patrimoine concerné",
            ],
            "delai_instruction": "3 à 6 mois (selon l'appel à projets)",
            "permanent": False,
            "url_officielle": "https://www.fondationdefrance.org/fr/patrimoine",
            "formulaire_url": None,
            "tags": [
                "Fondation de France",
                "fondation",
                "patrimoine",
                "appel à projets",
                "association",
                "collectivité",
                "éco-restauration",
                "intérêt général",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (protégé et non protégé)

# Propriétaires : uniquement structures d'intérêt général (public + asso)
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()

# Travaux : pas de contrainte (restauration générale, tous types)

# Régions : aide nationale → pas de contrainte

# Segments : commune et associations (pas les privés directement)
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
    ]
).execute()

# État de conservation : pas de contrainte

print(f"\n✅ Fondation de France — Programme Patrimoine inséré avec succès (id: {aide_id})")
