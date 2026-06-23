"""
Seed: Forêts et domaines boisés — Fondation France Bois Forêt pour notre Patrimoine.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_forets_domaines_boises.py
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
            "nom": "Fondation France Bois Forêt pour notre Patrimoine",
            "nom_court": "France Bois Forêt Patrimoine",
            "description": "Appel à projets de la Fondation France Bois Forêt finançant la restauration de patrimoine bâti en valorisant le matériau bois issu de forêts françaises gérées durablement.",
            "description_longue": (
                "La Fondation France Bois Forêt pour notre Patrimoine, abritée par la Fondation de France, "
                "lance chaque année un appel à projets destiné à financer la restauration de patrimoine "
                "bâti public et de monuments historiques privés accessibles au public, en mettant en avant "
                "l'utilisation du matériau bois issu de forêts françaises certifiées gestion durable. Le "
                "dispositif soutient la restauration de charpentes, toitures, menuiseries et tout élément "
                "architectural en bois. Chaque édition sélectionne environ 7 lauréats pour une dotation "
                "pouvant atteindre 10 000 € par projet. Depuis sa création, la Fondation a accompagné "
                "plus de 28 projets pour un montant total dépassant 280 000 €. Le patrimoine éligible est "
                "très large : urbain, rural, agricole, artistique, religieux, paysager, militaire, maritime "
                "ou industriel, à condition que les travaux utilisent significativement du bois français "
                "tracé et certifié."
            ),
            "categorie": "fondation",
            "type": "appel_a_projets",
            "organisme": "Fondation France Bois Forêt (sous égide de la Fondation de France)",
            "montant_max": 10000,
            "taux_max": None,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Les travaux doivent utiliser une part très significative de matériau bois issu de forêts françaises gérées durablement\n"
                "- La traçabilité du bois doit être certifiée (certification PEFC ou FSC de préférence)\n"
                "- Le bâtiment doit être ouvert au public (obligatoire)\n"
                "- Patrimoine éligible : urbain, rural, agricole, artistique, religieux, paysager, militaire, maritime, industriel\n"
                "- Bénéficiaires : personnes morales (communes, associations, fondations, entreprises) ET personnes physiques\n"
                "- Les monuments historiques classés ou inscrits privés sont éligibles s'ils sont accessibles au public\n"
                "- Le patrimoine public bâti présentant un intérêt historique, artistique ou architectural est éligible\n"
                "- Environ 7 lauréats sélectionnés par édition, pour une dotation de jusqu'à 10 000 € par projet\n"
                "- L'appel à projets est annuel avec des dates de dépôt précises (généralement février à octobre)\n"
                "- Le dossier est examiné par un jury qui sélectionne les lauréats\n"
                "- Les travaux doivent valoriser le savoir-faire des métiers du bois et de la forêt française\n"
                "- Critères de sélection : qualité patrimoniale du bâtiment, pertinence de l'utilisation du bois, engagement en gestion durable, impact territorial"
            ),
            "demarche_description": (
                "1. Consulter l'appel à projets en cours sur le site de France Bois Forêt\n"
                "2. Constituer le dossier de candidature décrivant le projet de restauration\n"
                "3. Détailler l'utilisation prévue de bois français certifié gestion durable\n"
                "4. Envoyer le dossier complet à fondation@franceboisforet.fr avant la date limite\n"
                "5. Examen du dossier par le jury de sélection (novembre généralement)\n"
                "6. Notification des lauréats (décembre)\n"
                "7. Versement de la dotation et suivi du projet"
            ),
            "documents_requis": [
                "Formulaire de candidature de l'appel à projets",
                "Description détaillée du projet de restauration",
                "Devis des travaux mentionnant l'origine et la certification du bois utilisé",
                "Photos de l'état actuel du bâtiment",
                "Justificatif de propriété ou d'autorisation du propriétaire",
                "Plan de financement prévisionnel",
                "Attestation d'ouverture au public",
            ],
            "delai_instruction": "2 à 4 mois (appel à projets annuel)",
            "permanent": False,
            "url_officielle": "https://franceboisforet.fr/lappel-a-projets-deposez-vos-projets/",
            "formulaire_url": "https://franceboisforet.fr/lappel-a-projets-deposez-vos-projets/",
            "tags": [
                "forêt",
                "bois",
                "France Bois Forêt",
                "charpente",
                "gestion durable",
                "patrimoine bâti",
                "appel à projets",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : tous niveaux éligibles
supabase.table("aides_protections").insert(
    [
        {"aide_id": aide_id, "protection_code": "classe"},
        {"aide_id": aide_id, "protection_code": "inscrit"},
        {"aide_id": aide_id, "protection_code": "non_protege"},
    ]
).execute()
print("  ✓ Protections insérées")

# Propriétaires : tous types (public et privé)
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : principalement charpente, menuiserie, toiture (travaux bois)
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "couverture"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale → pas de contrainte

# Segments : tous segments
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
        {"aide_id": aide_id, "segment_code": "prive"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ Fondation France Bois Forêt Patrimoine insérée avec succès (id: {aide_id})")
