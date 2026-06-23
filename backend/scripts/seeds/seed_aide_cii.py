"""
Seed: CII (Crédit d'Impôt Innovation).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_cii.py
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
            "nom": "Crédit d'Impôt Innovation (CII)",
            "nom_court": "CII",
            "description": "Crédit d'impôt de 20 % (30 % en Corse) sur les dépenses d'innovation des PME, plafonné à 400 000 € de dépenses éligibles par an.",
            "description_longue": (
                "Le Crédit d'Impôt Innovation (CII) est un dispositif fiscal réservé aux PME qui conçoivent "
                "des prototypes ou installations pilotes de produits nouveaux. Depuis la loi de finances 2025, "
                "le taux est de 20 % (contre 30 % précédemment), avec un plafond de 400 000 € de dépenses "
                "éligibles par an, soit un crédit d'impôt maximum de 80 000 €. En Corse, le taux est majoré : "
                "35 % pour les moyennes entreprises et 40 % pour les petites entreprises. Le dispositif est "
                "prorogé jusqu'au 31 décembre 2027. Dans le contexte patrimonial, le CII peut financer le "
                "développement de prototypes innovants pour la restauration (enduits spéciaux, matériaux "
                "biosourcés, outils de diagnostic), la numérisation du patrimoine, ou les solutions de "
                "médiation culturelle innovantes."
            ),
            "categorie": "fiscalite",
            "type": "deduction_fiscale",
            "organisme": "Ministère de l'Économie — Direction Générale des Finances Publiques (DGFiP)",
            "montant_max": 80000,
            "taux_max": 20,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Réservé aux PME au sens communautaire : effectif < 250 salariés, CA annuel ≤ 50 M€ ou total bilan ≤ 43 M€\n"
                "- L'entreprise doit être soumise à un régime réel d'IS ou d'IR (normal ou simplifié)\n"
                "- Taux du crédit d'impôt : 20 % des dépenses éligibles (depuis le 16 février 2025)\n"
                "- Taux majorés en Corse : 35 % pour les moyennes entreprises, 40 % pour les petites entreprises\n"
                "- Plafond de dépenses éligibles : 400 000 € par an, soit un crédit d'impôt maximum de 80 000 €\n"
                "- Le projet doit porter sur la conception d'un prototype ou d'une installation pilote d'un produit nouveau\n"
                "- Un « produit nouveau » doit se distinguer des produits existants par des performances supérieures sur le plan technique, de l'éco-conception, de l'ergonomie ou des fonctionnalités\n"
                "- Les dépenses de production du prototype ne sont PAS éligibles (seule la phase de conception)\n"
                "- Dépenses éligibles : salaires et charges du personnel affecté à l'innovation, amortissement des équipements neufs, sous-traitance (prestataires agréés), frais de propriété intellectuelle (brevets, dessins, modèles)\n"
                "- Dispositif prorogé jusqu'au 31 décembre 2027\n"
                "- Déclaration sur formulaire n° 2069-A-SD à joindre à la déclaration de résultats\n"
                "- Date limite : 15 du 4e mois suivant la clôture de l'exercice\n"
                "- Remboursement immédiat pour les PME (pas d'attente de 3 ans)\n"
                "- Dans le patrimoine : prototypes de matériaux innovants pour la restauration, outils de diagnostic patrimonial, solutions numériques de médiation culturelle\n"
                "- Le CII est cumulable avec le CIR mais les mêmes dépenses ne peuvent pas être déclarées aux deux dispositifs"
            ),
            "demarche_description": (
                "1. Identifier les projets d'innovation éligibles (prototypes, installations pilotes)\n"
                "2. Vérifier le statut PME de l'entreprise\n"
                "3. Documenter le caractère nouveau du produit par rapport à l'état du marché\n"
                "4. Calculer les dépenses éligibles (plafond 400 000 €)\n"
                "5. Remplir le formulaire n° 2069-A-SD\n"
                "6. Joindre à la déclaration de résultats de l'entreprise\n"
                "7. Conserver les justificatifs pendant 3 ans"
            ),
            "documents_requis": [
                "Formulaire n° 2069-A-SD",
                "Dossier technique justifiant le caractère nouveau du produit",
                "État du marché et comparaison avec les produits existants",
                "Fiches de temps du personnel affecté à l'innovation",
                "Factures de sous-traitance (prestataires agréés)",
                "Amortissements des équipements neufs",
                "Déclaration de résultats de l'entreprise",
            ],
            "delai_instruction": "Immédiat (déclaratif) — remboursement PME sous 6 mois",
            "permanent": True,
            "url_officielle": "https://entreprendre.service-public.gouv.fr/vosdroits/F35494",
            "formulaire_url": None,
            "tags": [
                "CII",
                "crédit d'impôt",
                "innovation",
                "PME",
                "prototype",
                "fiscal",
                "produit nouveau",
                "matériaux innovants",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte

# Propriétaires : PME uniquement
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : pas de contrainte

# Segments
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "prive"},
        {"aide_id": aide_id, "segment_code": "btp"},
    ]
).execute()
print("  ✓ Segments insérés")

# Régions : aide nationale → pas de contrainte

print(f"\n✅ CII inséré avec succès (id: {aide_id})")
