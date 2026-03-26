"""
Seed: BPI France — Aide à l'innovation.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_bpi_innovation.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Bpifrance — Aide à l'innovation (Subvention Innovation)",
    "nom_court": "BPI Innovation",
    "description": "Subvention Bpifrance pour les PME et ETI innovantes : de 30 000 € à 2 M€ selon le volet, finançant 50 à 70 % des dépenses de R&D et d'innovation.",
    "description_longue": (
        "Bpifrance propose plusieurs dispositifs de subvention pour accompagner les entreprises "
        "innovantes à différents stades de maturité. La « Subvention Innovation » couvre la "
        "faisabilité (jusqu'à 30 000 €), la DeepTech (jusqu'à 90 000 €), le développement "
        "technologique (jusqu'à 50 000 €) et l'innovation de rupture (subvention + avance "
        "récupérable jusqu'à 2 M€). Le financement couvre 50 à 70 % des dépenses de R&D internes "
        "et externes. Les PME et ETI (jusqu'à 2 000 salariés) immatriculées en France sont "
        "éligibles. La demande doit être déposée avant le démarrage du projet. Dans le contexte "
        "patrimonial, ces aides peuvent financer le développement de technologies innovantes pour "
        "la restauration, la numérisation 3D, les matériaux biosourcés, ou les solutions de "
        "médiation culturelle innovantes."
    ),
    "categorie": "etat_drac",
    "type": "subvention",
    "organisme": "Bpifrance",
    "montant_max": 2000000,
    "taux_max": 70,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": True,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Entreprises éligibles : PME au sens européen et ETI jusqu'à 2 000 ETP\n"
        "- L'entreprise doit être immatriculée en France\n"
        "- La demande d'aide doit être déposée AVANT le démarrage du projet (toute dépense antérieure est exclue)\n"
        "- Plusieurs volets selon la maturité du projet :\n"
        "  • Faisabilité : subvention jusqu'à 30 000 € (50 à 70 % des dépenses)\n"
        "  • DeepTech : subvention jusqu'à 90 000 € (50 à 70 % des dépenses) pour la maturation de projets à forte composante scientifique\n"
        "  • Développement : subvention jusqu'à 50 000 € (jusqu'à 70 % des dépenses de R&D interne et externe) pour les projets à risques technologiques élevés\n"
        "  • Innovation de rupture : subvention + avance récupérable jusqu'à 2 M€\n"
        "  • Axe French Tech : subvention pour les startups French Tech\n"
        "- Les dépenses éligibles incluent : R&D interne, sous-traitance R&D, prototypage, tests, propriété intellectuelle\n"
        "- Le cofinancement est requis (fonds propres ou autres financements)\n"
        "- Le projet doit présenter un caractère innovant et un risque technologique\n"
        "- Dans le patrimoine : développement de matériaux innovants pour la restauration, technologies de numérisation 3D, solutions de diagnostic non destructif, BIM patrimonial\n"
        "- Délai de réponse : 1 à 3 mois après dépôt du dossier complet\n"
        "- L'aide est ouverte toute l'année (pas de date limite)\n"
        "- L'avance récupérable est remboursable en cas de succès commercial du projet"
    ),
    "demarche_description": (
        "1. Identifier le volet d'aide adapté au stade du projet (faisabilité, DeepTech, développement, rupture)\n"
        "2. Contacter Bpifrance ou passer par la plateforme en ligne\n"
        "3. Constituer le dossier : description du projet innovant, budget, planning, équipe\n"
        "4. Déposer la demande AVANT le démarrage du projet\n"
        "5. Instruction par Bpifrance (1 à 3 mois)\n"
        "6. Convention de financement et versement par tranches\n"
        "7. Rapports d'avancement et justificatifs de dépenses"
    ),
    "documents_requis": [
        "Dossier de demande Bpifrance",
        "Description détaillée du projet innovant",
        "Budget prévisionnel et plan de financement",
        "Planning de réalisation",
        "CV de l'équipe projet",
        "Liasses fiscales des 2 derniers exercices",
        "Kbis de l'entreprise",
        "Business plan / modèle économique",
    ],
    "delai_instruction": "1 à 3 mois",
    "permanent": True,
    "url_officielle": "https://www.bpifrance.fr/catalogue-offres/subvention-innovation",
    "formulaire_url": "https://www.bpifrance.fr/catalogue-offres/subvention-innovation",
    "tags": [
        "Bpifrance", "innovation", "subvention", "PME", "ETI",
        "R&D", "DeepTech", "French Tech", "matériaux innovants",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte

# Propriétaires : entreprises (PME, ETI)
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
    {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
]).execute()
print("  ✓ Propriétaires insérés")

# Travaux : pas de contrainte (R&D / innovation)

# Segments
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "prive"},
    {"aide_id": aide_id, "segment_code": "btp"},
]).execute()
print("  ✓ Segments insérés")

# Régions : aide nationale → pas de contrainte

print(f"\n✅ BPI Innovation inséré avec succès (id: {aide_id})")
