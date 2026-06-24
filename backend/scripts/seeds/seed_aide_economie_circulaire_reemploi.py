"""
Seed: Économie circulaire et réemploi de matériaux — Aides ADEME et éco-organismes.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_economie_circulaire_reemploi.py
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
            "nom": "Économie circulaire et réemploi de matériaux — Aides ADEME / Éco-organismes",
            "nom_court": "Réemploi matériaux ADEME",
            "description": "Subventions ADEME et éco-organismes (Ecomaison, Ecominéro) pour les projets intégrant le réemploi et la valorisation de matériaux de construction dans les chantiers de restauration. Jusqu'à 60 % des dépenses éligibles.",
            "description_longue": (
                "L'ADEME et les éco-organismes du bâtiment (Ecomaison, Ecominéro) proposent des aides "
                "financières pour soutenir le réemploi, la réutilisation et la valorisation des matériaux "
                "de construction. Ces dispositifs peuvent s'appliquer aux chantiers de restauration de "
                "monuments et bâtiments patrimoniaux qui intègrent une démarche d'économie circulaire : "
                "réemploi de pierres, tuiles, bois, ferronneries, etc. L'ADEME finance des études de "
                "faisabilité, des diagnostics ressources et des investissements dans des équipements de "
                "réemploi à hauteur de 60 % maximum. Les éco-organismes lancent régulièrement des appels "
                "à projets pour le réemploi dans le BTP. La conservation de la substance du monument "
                "historique favorise naturellement le réemploi des matériaux existants, en cohérence "
                "avec les principes de la Charte de Venise."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "ADEME / Ecomaison / Ecominéro",
            "montant_max": None,
            "taux_max": 60,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Bénéficiaires éligibles : collectivités territoriales, entreprises (y compris artisans du BTP), structures de l'ESS, associations, chambres de commerce et de métiers\n"
                "- Les particuliers ne sont PAS directement éligibles — ils bénéficient indirectement via les entreprises de travaux\n"
                "- Types d'aides disponibles :\n"
                "  • Aide à l'étude de faisabilité / diagnostic ressources : jusqu'à 70 % du coût\n"
                "  • Aide aux investissements pour le réemploi : jusqu'à 60 % des dépenses éligibles\n"
                "  • Appels à projets thématiques (Ecomaison / Ecominéro) : enveloppes variables\n"
                "- Dépenses éligibles :\n"
                "  • Diagnostic PEMD (Produits, Équipements, Matériaux, Déchets) avant démolition/rénovation\n"
                "  • Dépose soignée de matériaux en vue du réemploi\n"
                "  • Stockage, reconditionnement et caractérisation des matériaux de réemploi\n"
                "  • Équipements nécessaires au tri, nettoyage et préparation des matériaux\n"
                "  • Plateformes de réemploi de matériaux\n"
                "- Conditions spécifiques patrimoine :\n"
                "  • Le réemploi de matériaux anciens (pierres de taille, tuiles, ardoises, bois de charpente) est particulièrement pertinent pour les chantiers MH\n"
                "  • Le diagnostic PEMD est obligatoire depuis le 1er juillet 2023 pour les démolitions/rénovations significatives (surface > 1 000 m²)\n"
                "  • Les chantiers patrimoniaux favorisant le réemploi in situ sont éligibles\n"
                "- Étude de faisabilité requise avant toute demande d'aide aux investissements\n"
                "- Les projets doivent démontrer un bénéfice environnemental quantifiable (tonnes de déchets évitées)\n"
                "- Appel à projets Ecomaison/Ecominéro : sessions annuelles, candidatures ouvertes généralement au T1\n"
                "- Non cumulable avec d'autres aides ADEME sur le même poste de dépense\n"
                "- L'aide ADEME est attribuée sur décision du directeur régional après instruction"
            ),
            "demarche_description": (
                "1. Identifier le volet économie circulaire du projet de restauration (matériaux à réemployer, flux à valoriser)\n"
                "2. Contacter la direction régionale de l'ADEME pour un accompagnement en amont\n"
                "3. Réaliser une étude de faisabilité ou un diagnostic PEMD (finançable par l'ADEME)\n"
                "4. Constituer le dossier : description du projet, quantification des matériaux, bénéfice environnemental, devis\n"
                "5. Déposer la demande sur la plateforme Agir pour la transition (ADEME) ou répondre à l'appel à projets éco-organisme\n"
                "6. Attendre la notification d'aide avant de commencer les investissements\n"
                "7. Réaliser les opérations et transmettre les justificatifs\n"
                "8. Obtenir le versement sur présentation du bilan final"
            ),
            "documents_requis": [
                "Description détaillée du projet de réemploi",
                "Diagnostic PEMD ou étude de faisabilité",
                "Quantification des matériaux à réemployer (en tonnes)",
                "Devis des prestataires et fournisseurs",
                "Plan de financement prévisionnel",
                "Bilan environnemental attendu (tonnes CO₂ évitées, déchets évités)",
                "Statuts de la structure porteuse",
                "RIB",
            ],
            "delai_instruction": "2 à 4 mois",
            "permanent": True,
            "url_officielle": "https://agirpourlatransition.ademe.fr/entreprises/aides-financieres",
            "formulaire_url": "https://agirpourlatransition.ademe.fr/entreprises/aides-financieres/catalogue",
            "tags": [
                "ADEME",
                "économie circulaire",
                "réemploi",
                "matériaux",
                "BTP",
                "diagnostic PEMD",
                "valorisation",
                "éco-organisme",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (tous types de bâtiments)

# Propriétaires : collectivités, associations, entreprises (pas les particuliers directement)
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux éligibles : large spectre (le réemploi touche tous types de matériaux)
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "couverture"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale → pas de contrainte

# Segments : commune et BTP
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
        {"aide_id": aide_id, "segment_code": "btp"},
    ]
).execute()
print("  ✓ Segments insérés")

print(f"\n✅ Économie circulaire et réemploi inséré avec succès (id: {aide_id})")
