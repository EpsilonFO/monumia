"""
Seed: CIR (Crédit d'Impôt Recherche).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_cir.py
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
            "nom": "Crédit d'Impôt Recherche (CIR)",
            "nom_court": "CIR",
            "description": "Crédit d'impôt de 30 % sur les dépenses de recherche et développement (R&D) des entreprises, jusqu'à 100 M€ de dépenses (5 % au-delà).",
            "description_longue": (
                "Le Crédit d'Impôt Recherche (CIR) est un dispositif fiscal majeur destiné à encourager "
                "les efforts de recherche et développement (R&D) des entreprises françaises. Il permet de "
                "déduire 30 % des dépenses de R&D éligibles (5 % au-delà de 100 M€). Le taux est majoré "
                "à 50 % pour les dépenses en outre-mer. Le CIR est accessible à toute entreprise soumise "
                "à un régime réel d'imposition (IS ou IR), quelle que soit sa taille ou son secteur. "
                "Dans le contexte patrimonial, le CIR peut financer des travaux de recherche sur les "
                "matériaux anciens, les techniques de restauration innovantes, les méthodes de diagnostic "
                "non destructif, ou les technologies numériques appliquées au patrimoine (BIM patrimonial, "
                "photogrammétrie, datation). Réforme 2025 : suppression du régime jeune docteur, des frais "
                "de brevets et de veille technologique ; réduction du taux de fonctionnement de 43 % à 40 %."
            ),
            "categorie": "fiscalite",
            "type": "deduction_fiscale",
            "organisme": "Ministère de l'Économie — Direction Générale des Finances Publiques (DGFiP)",
            "montant_max": None,
            "taux_max": 30,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Toute entreprise industrielle, commerciale ou agricole soumise à un régime réel d'IS ou d'IR est éligible\n"
                "- Aucune condition de taille : TPE, PME, ETI, grandes entreprises\n"
                "- Taux de crédit d'impôt : 30 % des dépenses de R&D jusqu'à 100 M€, 5 % au-delà\n"
                "- Taux majoré en outre-mer : 50 % jusqu'à 100 M€, 5 % au-delà\n"
                "- Les dépenses de R&D doivent correspondre à des opérations de recherche fondamentale, recherche appliquée ou développement expérimental\n"
                "- Dépenses éligibles : salaires et charges des chercheurs et techniciens de recherche, amortissement des équipements de R&D, sous-traitance R&D (organismes agréés), frais de fonctionnement (40 % des salaires depuis 2025)\n"
                "- Dépenses NON éligibles depuis 2025 : frais de brevets et COV, dépenses de veille technologique, régime jeune docteur supprimé\n"
                "- Le crédit d'impôt est imputable sur l'IS/IR des 3 années suivantes ; le solde non imputé est remboursé\n"
                "- Remboursement immédiat pour : PME, jeunes entreprises innovantes (JEI), entreprises en difficulté, entreprises nouvelles\n"
                "- Les travaux de recherche sur la restauration du patrimoine peuvent être éligibles : recherche sur matériaux anciens, techniques de conservation innovantes, diagnostic non destructif, photogrammétrie, BIM patrimonial\n"
                "- Déclaration sur formulaire n° 2069-A-SD à joindre à la déclaration de résultats\n"
                "- Date limite : 15 du 4e mois suivant la clôture de l'exercice\n"
                "- Le rescrit fiscal CIR permet de sécuriser l'éligibilité en amont (réponse sous 3 mois)\n"
                "- En cas de contrôle, l'entreprise doit justifier la nature scientifique et technique des travaux"
            ),
            "demarche_description": (
                "1. Identifier les projets de R&D éligibles au CIR\n"
                "2. Documenter les travaux : état de l'art, verrous technologiques, travaux réalisés, résultats\n"
                "3. Calculer les dépenses éligibles (salaires, amortissements, sous-traitance, fonctionnement)\n"
                "4. Remplir le formulaire n° 2069-A-SD\n"
                "5. Joindre à la déclaration de résultats de l'entreprise\n"
                "6. Optionnel : demander un rescrit fiscal CIR pour sécuriser l'éligibilité\n"
                "7. Conserver les justificatifs pendant 3 ans (période de contrôle)"
            ),
            "documents_requis": [
                "Formulaire n° 2069-A-SD",
                "Dossier technique justifiant la nature R&D des travaux",
                "État de l'art scientifique et technique",
                "Fiches de temps des chercheurs et techniciens",
                "Factures de sous-traitance (organismes agréés CIR)",
                "Amortissements des équipements de R&D",
                "Déclaration de résultats de l'entreprise",
            ],
            "delai_instruction": "Immédiat (déclaratif) — rescrit : 3 mois",
            "permanent": True,
            "url_officielle": "https://entreprendre.service-public.fr/vosdroits/F23533",
            "formulaire_url": None,
            "tags": [
                "CIR",
                "crédit d'impôt",
                "recherche",
                "R&D",
                "innovation",
                "fiscal",
                "matériaux patrimoniaux",
                "restauration innovante",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte

# Propriétaires : entreprises uniquement (SCI, associations éventuellement)
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : pas de contrainte (R&D, pas travaux physiques directement)

# Segments
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "prive"},
        {"aide_id": aide_id, "segment_code": "btp"},
    ]
).execute()
print("  ✓ Segments insérés")

# Régions : aide nationale → pas de contrainte

print(f"\n✅ CIR inséré avec succès (id: {aide_id})")
