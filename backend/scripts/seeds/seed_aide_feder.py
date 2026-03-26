"""
Seed: FEDER (Fonds Européen de Développement Régional) — Patrimoine culturel.

Run:
    cd backend && uv run python3 scripts/seed_aide_feder.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "FEDER — Fonds Européen de Développement Régional (volet patrimoine culturel)",
    "nom_court": "FEDER Patrimoine",
    "description": "Cofinancement européen pour des projets de restauration, réhabilitation et valorisation du patrimoine culturel, dans le cadre des programmes opérationnels régionaux 2021-2027.",
    "description_longue": (
        "Le FEDER est l'un des principaux fonds structurels de l'Union européenne. "
        "Pour la période 2021-2027, la France dispose de 9,07 milliards d'euros répartis "
        "sur 19 programmes régionaux. Le volet patrimoine culturel relève principalement "
        "de l'Objectif Stratégique 5 (OS5) : développement territorial intégré. "
        "Le FEDER cofinance des projets de restauration, réhabilitation et mise en valeur "
        "du patrimoine culturel ayant un impact mesurable sur le développement territorial "
        "(attractivité touristique, emploi, cohésion sociale). Chaque région définit ses "
        "propres critères et calendriers dans son Programme Opérationnel et son Document "
        "de Mise en Œuvre (DOMO). Le taux de cofinancement FEDER varie de 40 % à 85 % "
        "selon la catégorie de la région. Le cumul avec d'autres aides publiques (DRAC, "
        "région, département) est possible sous condition d'éviter le double financement "
        "d'une même dépense."
    ),
    "categorie": "europe",
    "type": "subvention",
    "organisme": "Commission européenne / Conseils régionaux (autorités de gestion)",
    "montant_max": 3000000,
    "taux_max": 85,
    "montant_min": None,
    "plancher": 1000000,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": True,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Le FEDER est géré région par région : chaque région définit ses propres critères "
        "dans son Programme Opérationnel et son Document de Mise en Œuvre (DOMO). Il est "
        "impératif de consulter le DOMO de sa région.\n"
        "- Le projet doit s'inscrire dans l'Objectif Stratégique 5 (OS5) : développement "
        "territorial intégré (zones urbaines OS 5.1, zones rurales OS 5.2).\n"
        "- Le projet doit avoir un impact mesurable sur le développement territorial : "
        "création d'emplois, retombées touristiques, inclusion sociale, attractivité.\n"
        "- Taux de cofinancement FEDER selon la catégorie de région :\n"
        "  • Régions les plus développées (majorité de la métropole) : 40 % à 50 %\n"
        "  • Régions en transition : 60 % à 70 %\n"
        "  • Régions moins développées (outre-mer) : jusqu'à 85 %\n"
        "- Seuil minimum de projet souvent fixé à 1 million d'euros HT (ex : Hauts-de-France), "
        "mais variable selon les régions.\n"
        "- Plafond FEDER par opération généralement de 3 millions d'euros, variable selon les régions.\n"
        "- Le FEDER ne finance jamais 100 % du projet : un cofinancement est obligatoire "
        "(région, département, DRAC, autofinancement, etc.).\n"
        "- Le cumul avec d'autres aides est possible (DRAC, aides régionales, ADEME, BPI, "
        "France 2030) à condition d'éviter le double financement sur une même dépense.\n"
        "- Le FEDER ne conditionne pas formellement l'aide à un type de protection MH "
        "spécifique, mais les projets classés ou inscrits MH sont souvent mieux notés.\n"
        "- Le patrimoine non protégé peut aussi être éligible si le projet s'inscrit dans "
        "une stratégie de développement territorial.\n"
        "- Ouverture au public souvent exigée ou fortement valorisée dans les critères "
        "de sélection.\n"
        "- Priorité aux projets intégrant la transition écologique et numérique.\n"
        "- Obligation de publicité : afficher le soutien de l'UE sur le site et dans "
        "les communications du projet.\n"
        "- Additionnalité : le FEDER ne doit pas se substituer à des financements nationaux existants.\n"
        "- Les dépenses doivent être réalisées et justifiées (remboursement sur justificatifs).\n"
        "- Programmation actuelle : 2021-2027, avec possibilité de déposer de nouveaux "
        "projets jusqu'en 2027. Les derniers paiements sont prévus fin 2029.\n"
        "- Les propriétaires privés ne sont pas systématiquement éligibles : à vérifier "
        "région par région. Les collectivités territoriales, EPCI, établissements publics "
        "et associations sont généralement éligibles."
    ),
    "demarche_description": (
        "1. Identifier la mesure applicable dans le programme FEDER de votre région "
        "(appel à projets ponctuel ou aide permanente « au fil de l'eau »)\n"
        "2. Vérifier l'éligibilité technique, financière et territoriale du projet "
        "en consultant le DOMO régional\n"
        "3. Monter un dossier comprenant description détaillée, plan financier, "
        "calendrier, preuves de l'impact territorial du projet\n"
        "4. Préparer les documents obligatoires (statuts, bilans, devis, autorisations)\n"
        "5. Déposer le dossier sur la plateforme e-Synergie (plateforme nationale de "
        "dépôt des fonds européens) ou sur le portail régional dédié\n"
        "6. Répondre aux demandes complémentaires pendant la phase d'instruction"
    ),
    "documents_requis": [
        "Statuts de la structure porteuse",
        "Bilans financiers des dernières années",
        "Plan de financement détaillé du projet",
        "Devis et estimations des travaux",
        "Autorisations administratives (permis de construire, autorisation ABF si MH)",
        "Description technique détaillée du projet",
        "Calendrier prévisionnel des travaux",
        "Étude d'impact / analyse des retombées territoriales attendues",
        "Dossier de candidature spécifique (si appel à projets ponctuel)",
    ],
    "delai_instruction": "3 à 9 mois (variable selon les régions)",
    "permanent": False,
    "url_officielle": "https://www.europe-en-france.gouv.fr",
    "formulaire_url": None,
    "tags": [
        "FEDER", "Europe", "fonds européens", "patrimoine culturel",
        "développement territorial", "restauration", "valorisation",
        "cofinancement", "2021-2027",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte formelle (patrimoine non protégé aussi éligible)
# → on n'insère rien dans aides_protections

# Propriétaires : principalement collectivités, établissements publics, associations
# Les privés ne sont pas systématiquement éligibles mais possible selon les régions
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "public_departement"},
    {"aide_id": aide_id, "proprietaire_code": "public_region"},
    {"aide_id": aide_id, "proprietaire_code": "public_etat"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
    {"aide_id": aide_id, "proprietaire_code": "mixte"},
]).execute()
print("  ✓ Propriétaires éligibles insérés")

# Travaux : large spectre
supabase.table("aides_travaux").insert([
    {"aide_id": aide_id, "travaux_code": "toiture"},
    {"aide_id": aide_id, "travaux_code": "charpente"},
    {"aide_id": aide_id, "travaux_code": "couverture"},
    {"aide_id": aide_id, "travaux_code": "facade"},
    {"aide_id": aide_id, "travaux_code": "maconnerie"},
    {"aide_id": aide_id, "travaux_code": "vitraux"},
    {"aide_id": aide_id, "travaux_code": "peintures_murales"},
    {"aide_id": aide_id, "travaux_code": "menuiserie"},
    {"aide_id": aide_id, "travaux_code": "electricite"},
    {"aide_id": aide_id, "travaux_code": "plomberie"},
    {"aide_id": aide_id, "travaux_code": "chauffage"},
    {"aide_id": aide_id, "travaux_code": "accessibilite"},
    {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
    {"aide_id": aide_id, "travaux_code": "restauration_generale"},
    {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    {"aide_id": aide_id, "travaux_code": "parcs_jardins"},
]).execute()
print("  ✓ Travaux éligibles insérés")

# Régions : aide nationale (toutes régions éligibles) → pas de contrainte

# Segments : principalement collectivités
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "commune"},
]).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ FEDER Patrimoine inséré avec succès (id: {aide_id})")
