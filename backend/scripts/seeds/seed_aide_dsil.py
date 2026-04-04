"""
Seed: DSIL — Dotation de Soutien à l'Investissement Local.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_dsil.py
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
            "nom": "Dotation de Soutien à l'Investissement Local (DSIL)",
            "nom_court": "DSIL",
            "description": "Dotation de l'État destinée aux communes et intercommunalités pour soutenir leurs projets d'investissement structurants, incluant la rénovation du patrimoine public.",
            "description_longue": (
                "La Dotation de Soutien à l'Investissement Local (DSIL), créée par la loi de finances "
                "pour 2016 et pérennisée en 2018, est une dotation d'investissement versée par l'État aux "
                "communes et aux EPCI à fiscalité propre. Elle finance des projets d'investissement "
                "s'inscrivant dans les grandes priorités nationales : rénovation thermique, mise aux normes "
                "des équipements publics, développement du tourisme, revitalisation des centres-bourgs, etc. "
                "Les projets de restauration de patrimoine historique communal peuvent être éligibles "
                "lorsqu'ils s'inscrivent dans une démarche de mise en valeur du patrimoine, de "
                "développement touristique ou dans le cadre de programmes nationaux (Petites Villes de "
                "Demain, Action Cœur de Ville, Villages d'Avenir). L'enveloppe nationale est d'environ "
                "570 à 600 M€ par an, répartie entre les préfectures de région. Les crédits sont attribués "
                "par le préfet de région après instruction par les services préfectoraux."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "Préfecture de région (DGCL — Ministère de l'Intérieur)",
            "montant_max": None,
            "taux_max": 80,
            "montant_min": 20000,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Bénéficiaires : communes, EPCI à fiscalité propre, pôles d'équilibre territoriaux et ruraux (PETR)\n"
                "- Les propriétaires privés ne sont PAS éligibles\n"
                "- Le projet doit s'inscrire dans l'une des priorités légales (art. L. 2334-42 CGCT) :\n"
                "  • Rénovation thermique et transition énergétique\n"
                "  • Mise aux normes et sécurisation des équipements publics\n"
                "  • Développement des infrastructures de mobilité ou construction de logements\n"
                "  • Développement du numérique et de la téléphonie mobile\n"
                "  • Création, transformation et rénovation des bâtiments scolaires\n"
                "  • Réalisation d'hébergements et d'équipements publics pour le tourisme\n"
                "  • Projets relevant des grandes priorités nationales (Action Cœur de Ville, Petites Villes de Demain, Villages d'Avenir)\n"
                "- Pour le patrimoine historique : le projet doit être présenté sous l'angle « mise en valeur du patrimoine », « équipement public » ou « développement touristique »\n"
                "- Taux de subvention en pratique : 20 % à 80 % du montant HT selon les projets\n"
                "- Le cumul avec d'autres aides publiques (DETR, FEDER, Région, Département) est possible mais le taux global ne doit généralement pas dépasser 80 % du coût HT\n"
                "- Pas de critère strict de population (contrairement à la DETR), mais priorité aux petites et moyennes communes\n"
                "- Les travaux ne doivent pas avoir commencé avant la notification de la subvention (sauf dérogation)\n"
                "- Chaque préfecture de région fixe son propre calendrier et ses propres critères de priorisation\n"
                "- La commission DETR-DSIL départementale est consultée pour avis"
            ),
            "demarche_description": (
                "1. Prendre contact avec la préfecture de département ou sous-préfecture pour vérifier l'éligibilité du projet\n"
                "2. Constituer le dossier de demande de subvention\n"
                "3. Déposer le dossier auprès de la préfecture (souvent via demarches-simplifiees.fr)\n"
                "4. Instruction par les services préfectoraux\n"
                "5. Consultation de la commission DETR-DSIL départementale\n"
                "6. Décision d'attribution par le préfet de région\n"
                "7. Notification de la subvention et convention\n"
                "8. Versement par tranches sur justificatifs d'avancement des travaux"
            ),
            "documents_requis": [
                "Délibération de la collectivité approuvant l'opération et le plan de financement",
                "Note descriptive du projet (objectifs, calendrier, impacts attendus)",
                "Devis détaillés ou résultats d'appel d'offres",
                "Plan de financement prévisionnel",
                "Documents d'urbanisme et autorisations (permis de construire, avis ABF si MH)",
                "RIB de la collectivité",
                "Pour les MH : autorisation de travaux DRAC et avis de l'ABF",
            ],
            "delai_instruction": "3 à 6 mois",
            "permanent": True,
            "url_officielle": "https://www.collectivites-locales.gouv.fr/finances-locales/dotation-de-soutien-linvestissement-local-dsil",
            "formulaire_url": None,
            "tags": [
                "DSIL",
                "dotation",
                "investissement local",
                "communes",
                "intercommunalités",
                "patrimoine public",
                "tourisme",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : classé et inscrit (patrimoine public protégé)
supabase.table("aides_protections").insert(
    [
        {"aide_id": aide_id, "protection_code": "classe"},
        {"aide_id": aide_id, "protection_code": "inscrit"},
        {"aide_id": aide_id, "protection_code": "non_protege"},
    ]
).execute()
print("  ✓ Protections insérées")

# Propriétaires : collectivités publiques uniquement
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : large spectre pour les équipements publics
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "couverture"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "electricite"},
        {"aide_id": aide_id, "travaux_code": "plomberie"},
        {"aide_id": aide_id, "travaux_code": "chauffage"},
        {"aide_id": aide_id, "travaux_code": "accessibilite"},
        {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale → pas de contrainte

# Segments : communes uniquement
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ DSIL insérée avec succès (id: {aide_id})")
