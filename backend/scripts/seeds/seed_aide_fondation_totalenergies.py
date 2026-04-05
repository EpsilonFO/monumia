"""
Seed: Fondation TotalEnergies — Chantiers patrimoine et insertion.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_fondation_totalenergies.py
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
            "nom": "Fondation TotalEnergies — Chantiers patrimoine et insertion professionnelle",
            "nom_court": "Fondation TotalEnergies",
            "description": "Soutien financier de la Fondation TotalEnergies (en partenariat avec la Fondation du patrimoine) pour des chantiers de restauration intégrant des clauses d'insertion professionnelle pour les jeunes.",
            "description_longue": (
                "Depuis 2006, la Fondation TotalEnergies et la Fondation du patrimoine collaborent pour "
                "financer des chantiers de restauration du patrimoine bâti à travers toute la France. "
                "Ce partenariat a déjà permis de soutenir plus de 330 projets. La spécificité de ce "
                "programme est l'intégration obligatoire de clauses d'insertion professionnelle : chaque "
                "chantier doit servir de vecteur de formation et de retour à l'emploi pour des jeunes "
                "éloignés du marché du travail, des bénéficiaires du RSA ou des personnes en situation "
                "de handicap. Les métiers du patrimoine (maçonnerie, taille de pierre, charpente, "
                "ferronnerie, vitrail) sont ainsi transmis à travers des chantiers concrets. En 2025, "
                "18 projets ont été soutenus, représentant plus de 20 000 heures d'insertion."
            ),
            "categorie": "fondation",
            "type": "subvention",
            "organisme": "Fondation TotalEnergies (en partenariat avec la Fondation du patrimoine)",
            "montant_max": None,
            "taux_max": None,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": True,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Porteurs de projets éligibles :\n"
                "  • Associations et structures d'insertion par l'activité économique (SIAE)\n"
                "  • Collectivités territoriales\n"
                "  • Fondations et établissements publics\n"
                "  • Entreprises d'insertion\n"
                "- Les propriétaires privés personnes physiques ne peuvent pas candidater directement\n"
                "- Conditions de la structure porteuse :\n"
                "  • Budget annuel ≥ 400 000 € (dernier exercice clos, hors valorisation du bénévolat)\n"
                "  • Au moins 2 salariés en CDI (équivalent temps plein)\n"
                "- Clause d'insertion professionnelle obligatoire :\n"
                "  • Le chantier de restauration doit intégrer des heures d'insertion pour des publics "
                "éloignés de l'emploi (jeunes sans qualification, bénéficiaires du RSA, travailleurs "
                "handicapés)\n"
                "  • Contrats éligibles : professionnalisation, apprentissage, CDI d'insertion, "
                "collaboration avec des entreprises d'insertion\n"
                "- Critères de sélection :\n"
                "  • Fort ancrage territorial du projet\n"
                "  • Impact social mesurable (nombre de bénéficiaires, heures d'insertion)\n"
                "  • Qualité patrimoniale du bâtiment restauré\n"
                "  • Transmission de savoir-faire artisanaux (maçonnerie, taille de pierre, charpente, "
                "ferronnerie, vitrail)\n"
                "  • Développement économique local\n"
                "- Fonctionnement par appel à projets annuel (candidatures en début d'année)\n"
                "- Calendrier 2026 : candidatures du 5 février au 5 mars 2026 en 2 phases :\n"
                "  • Phase 1 : éligibilité de la structure et du projet (réponse sous 24h)\n"
                "  • Phase 2 : présentation détaillée du projet si éligible\n"
                "- Les projets purement privés sans dimension d'insertion ne sont pas éligibles\n"
                "- Couverture : France métropolitaine et outre-mer"
            ),
            "demarche_description": (
                "1. Consulter l'appel à projets annuel sur le site de la Fondation TotalEnergies\n"
                "2. Vérifier l'éligibilité de la structure (budget ≥ 400 000 €, ≥ 2 CDI)\n"
                "3. Déposer la candidature en ligne (Phase 1 : éligibilité structure et projet)\n"
                "4. Si éligible (réponse sous 24h), présenter le projet détaillé (Phase 2)\n"
                "5. Sélection par un comité conjoint Fondation TotalEnergies / Fondation du patrimoine\n"
                "6. Convention de financement et lancement du chantier\n"
                "7. Suivi des indicateurs d'insertion (heures, contrats, retour à l'emploi)"
            ),
            "documents_requis": [
                "Formulaire de candidature en ligne",
                "Statuts et bilans financiers de la structure porteuse (2 derniers exercices)",
                "Description du projet patrimonial et du programme de travaux",
                "Plan d'insertion détaillé (publics visés, heures, contrats, partenaires insertion)",
                "Budget prévisionnel et plan de financement",
                "Photographies du patrimoine concerné",
                "Attestation du nombre de salariés en CDI",
            ],
            "delai_instruction": "2 à 4 mois (appel à projets annuel)",
            "date_ouverture": None,
            "date_limite": None,
            "permanent": False,
            "url_officielle": "https://fondation.totalenergies.com/fr/nos-actions/nos-actions-dialogue-des-cultures-et-patrimoine",
            "formulaire_url": "https://fondation.totalenergies.com/fr/appel-a-projets-2026",
            "tags": [
                "Fondation TotalEnergies",
                "Fondation du patrimoine",
                "insertion",
                "emploi",
                "jeunes",
                "chantier",
                "formation",
                "métiers du patrimoine",
                "taille de pierre",
                "maçonnerie",
                "restauration",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (protégé et non protégé)

# Propriétaires : structures d'intérêt général (publics + asso)
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()

# Travaux : principalement les métiers du bâti ancien
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "couverture"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "vitraux"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
    ]
).execute()

# Régions : aide nationale → pas de contrainte

# Segments : commune (porteurs publics et asso, pas les privés)
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
    ]
).execute()

# État de conservation : pas de contrainte

print(f"\n✅ Fondation TotalEnergies inséré avec succès (id: {aide_id})")
