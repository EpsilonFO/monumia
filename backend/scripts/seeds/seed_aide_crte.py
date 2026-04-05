"""
Seed: CRTE — Contrats de Relance et de Transition Écologique.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_crte.py
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
            "nom": "CRTE — Contrats pour la Réussite de la Transition Écologique",
            "nom_court": "CRTE",
            "description": "Contrat-cadre entre l'État et les intercommunalités permettant de mobiliser les crédits DETR, DSIL, Fonds Vert et FNADT pour des projets de transition écologique incluant la restauration du patrimoine bâti.",
            "description_longue": (
                "Les Contrats pour la Réussite de la Transition Écologique (CRTE), anciennement Contrats de "
                "Relance et de Transition Écologique, sont des contrats-cadres conclus pour 6 ans (2021-2026) "
                "entre l'État (préfets) et les intercommunalités (EPCI, PETR, Pays). Ils permettent de "
                "flécher et coordonner les crédits de droit commun de l'État (DETR, DSIL, Fonds Vert, FNADT, "
                "DGD) vers les projets structurants du territoire en matière de transition écologique. "
                "La restauration et la valorisation du patrimoine bâti communal peuvent être inscrites comme "
                "action prioritaire du CRTE, facilitant ainsi l'accès aux financements État. "
                "L'enveloppe nationale est de 1,15 milliard d'euros en 2025. "
                "Le CRTE n'est pas une aide à proprement parler mais un outil contractuel qui priorise "
                "et facilite l'accès aux dotations existantes pour les projets inscrits au contrat."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "Préfectures — ANCT (Agence Nationale de la Cohésion des Territoires)",
            "montant_max": None,
            "taux_max": 80,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": True,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Le CRTE est un contrat-cadre, pas une aide directe : il facilite l'accès aux dotations "
                "DETR, DSIL, Fonds Vert, FNADT et DGD pour les projets inscrits au contrat\n"
                "- Le territoire doit avoir signé un CRTE avec le préfet de département\n"
                "- Le projet de restauration patrimoniale doit être inscrit dans les actions prioritaires du CRTE\n"
                "- Le projet doit contribuer à la transition écologique du territoire "
                "(rénovation énergétique du patrimoine bâti, valorisation durable, etc.)\n"
                "- Porteurs éligibles : communes et EPCI membres du territoire CRTE\n"
                "- La participation minimale de la collectivité est de 20 % du montant total\n"
                "- Les projets doivent s'inscrire dans une stratégie territoriale cohérente "
                "(revitalisation centre-bourg, tourisme durable, transition énergétique)\n"
                "- Les crédits DETR et DSIL mobilisés via le CRTE suivent leurs propres règles d'éligibilité\n"
                "- Durée du contrat : 2021-2026, avec possibilité d'avenant\n"
                "- L'inscription au CRTE ne garantit pas le financement mais le facilite fortement\n"
                "- Les projets patrimoniaux combinant restauration et performance énergétique sont prioritaires\n"
                "- L'ANCT peut apporter un soutien en ingénierie pour le montage des projets"
            ),
            "demarche_description": (
                "1. Vérifier que la commune ou l'EPCI est couvert par un CRTE signé\n"
                "2. Inscrire le projet de restauration patrimoniale dans les actions du CRTE "
                "(via les comités de pilotage du contrat)\n"
                "3. Identifier les dotations mobilisables (DETR, DSIL, Fonds Vert, DGD)\n"
                "4. Constituer les dossiers de demande pour chaque dotation visée\n"
                "5. Déposer les demandes auprès de la préfecture avec mention de l'inscription au CRTE\n"
                "6. L'inscription au CRTE facilite l'instruction et la priorisation par les services de l'État\n"
                "7. Notification des subventions par dotation\n"
                "8. Réalisation des travaux et justification des dépenses"
            ),
            "documents_requis": [
                "Projet inscrit au CRTE du territoire (délibération ou compte-rendu du comité de pilotage)",
                "Fiche-action détaillée du projet patrimonial",
                "Plan de financement prévisionnel multi-dotations",
                "Devis détaillés des travaux",
                "Délibération de la collectivité approuvant le projet",
                "Note stratégique sur la contribution à la transition écologique",
                "Dossiers spécifiques à chaque dotation sollicitée (DETR, DSIL, etc.)",
            ],
            "delai_instruction": "3 à 6 mois",
            "permanent": True,
            "url_officielle": "https://anct.gouv.fr/programmes-dispositifs/contrats-pour-la-reussite-de-la-transition-ecologique",
            "formulaire_url": None,
            "tags": [
                "CRTE",
                "transition écologique",
                "contrat territorial",
                "DETR",
                "DSIL",
                "Fonds Vert",
                "intercommunalité",
                "revitalisation",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (patrimoine protégé ou non)

# Propriétaires : collectivités publiques uniquement
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : large spectre via dotations mobilisées
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

print(f"\n✅ CRTE inséré avec succès (id: {aide_id})")
