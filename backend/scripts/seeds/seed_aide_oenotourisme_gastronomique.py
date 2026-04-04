"""
Seed: Œnotourisme et tourisme gastronomique.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_oenotourisme_gastronomique.py
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
            "nom": "Aides à l'œnotourisme et au tourisme gastronomique dans le patrimoine",
            "nom_court": "Œnotourisme & gastronomie patrimoine",
            "description": "Dispositifs nationaux et régionaux de soutien aux projets œnotouristiques et gastronomiques dans des sites patrimoniaux. Subventions de 10 % à 50 % selon les dispositifs, prêts BPI et Banque des Territoires.",
            "description_longue": (
                "La France est la première destination œnotouristique européenne avec 12 millions de visiteurs "
                "en 2024. Plusieurs dispositifs publics soutiennent les projets alliant patrimoine protégé et "
                "œnotourisme ou tourisme gastronomique. Le label « Vignobles & Découvertes » (Atout France) "
                "fédère les destinations œnotouristiques et permet d'accéder à des aides régionales spécifiques. "
                "La Région Bourgogne-Franche-Comté finance jusqu'à 20 % (plafond 20 000 €) les projets "
                "œnotouristiques labellisés. La Région Auvergne-Rhône-Alpes propose 20 % (plafond 50 000 €) "
                "pour les projets individuels et 20 % (plafond 150 000 €) pour les projets collectifs. "
                "FranceAgriMer finance jusqu'à 35 % les investissements vitivinicoles (caveaux de vente) via "
                "l'OCM. Le programme « Territoires d'Histoire(s) » de la Banque des Territoires cible "
                "spécifiquement les sites MH avec prêts à 25 ans. Le Prêt Tourisme BPI est mobilisable pour "
                "les structures d'exploitation touristique dans des MH. La Fondation du Patrimoine / Airbnb "
                "(programme Patrimoine et Tourisme Local) finance la restauration de bâtiments patrimoniaux "
                "à vocation touristique (5,6 M€ sur 200 projets)."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "Atout France / Régions / FranceAgriMer / Banque des Territoires",
            "montant_max": 200000,
            "taux_max": 50,
            "montant_min": None,
            "plancher": 10000,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Projets alliant patrimoine bâti (MH classés, inscrits, ou patrimoine d'intérêt) et activité œnotouristique ou gastronomique\n"
                "- Label Vignobles & Découvertes (Atout France) : prérequis pour les aides régionales œnotourisme, durée 3 ans renouvelable, candidature avant le 31 décembre\n"
                "- Région Bourgogne-Franche-Comté : subvention max 20 %, plafond 20 000 €, plancher 10 000 € de dépenses, labellisation V&D requise ou en cours, minimum 3 offres œnotouristiques à créer, bonification écoconditions et label Tourisme & Handicaps. Période : 1er mai 2024 – 31 décembre 2028\n"
                "- Région Auvergne-Rhône-Alpes : projets individuels 20 % (plafond 50 000 €, plancher 10 000 €), projets collectifs investissement 20 % (plafond 150 000 €, plancher 50 000 €), études collectives 50 % (plafond 20 000 €, plancher 5 000 €). Entités viticoles uniquement, projets allant au-delà de la dégustation/vente. Acquisition immobilière, boutiques, aménagements extérieurs et parkings non éligibles\n"
                "- Région Nouvelle-Aquitaine (Découverte économique) : taux max 10 %, plancher 20 000 € HT, plafond 500 000 € HT, ouverture au public min. 90 jours/an, maintien activité 5 ans, partenariat OT local. SCI, grandes entreprises, ETI et collectivités non éligibles\n"
                "- FranceAgriMer OCM vitivinicole : 30-35 % des dépenses éligibles (PME), bonus environnemental +5 %, enveloppe 150 M€, seuls les caveaux de vente sont couverts (pas l'accueil touristique pur). Appel annuel, dépôt janvier-mars\n"
                "- Programme Patrimoine et Tourisme Local (Fondation du Patrimoine / Airbnb) : restauration de bâtiments patrimoniaux à vocation touristique, enveloppe 5,6 M€ sur 200 projets, candidature avant le 13 février\n"
                "- AMI Tourisme et Gastronomie (Atout France / DGE) : jusqu'à 200 000 € pour projets événementiels innovants valorisant la gastronomie. Personnes morales publiques ou privées\n"
                "- Banque des Territoires « Territoires d'Histoire(s) » : prêts jusqu'à 25 ans à 3 % (Livret A + 1,3 %), sites MH et SPR, enveloppe 250 M€ fonds propres + 1 Md€ mobilisés\n"
                "- Cumulable avec : DRAC MH, régime fiscal MH, Label Fondation du Patrimoine, FEADER/LEADER, ZRR/FRR\n"
                "- Les travaux sur MH doivent respecter les prescriptions de l'ABF/DRAC"
            ),
            "demarche_description": (
                "1. Vérifier si votre territoire est labellisé Vignobles & Découvertes (ou candidater)\n"
                "2. Identifier les dispositifs régionaux applicables à votre région\n"
                "3. Contacter le service tourisme de la Région ou la DRAC pour les MH\n"
                "4. Constituer le dossier : programme du projet, devis, plan de financement, étude de marché\n"
                "5. Pour FranceAgriMer : déposer la demande lors de l'appel annuel (janvier-mars)\n"
                "6. Pour la Fondation du Patrimoine : candidater en ligne avant le 13 février\n"
                "7. Instruction et notification\n"
                "8. Réalisation du projet et versement sur justificatifs"
            ),
            "documents_requis": [
                "Programme détaillé du projet œnotouristique/gastronomique",
                "Devis des entreprises",
                "Plan de financement prévisionnel",
                "Étude de marché ou de fréquentation",
                "Justificatif de labellisation Vignobles & Découvertes (si applicable)",
                "Photos du site patrimonial",
                "Autorisation de travaux si nécessaire",
                "Avis ABF/DRAC si monument protégé",
                "Business plan (pour prêts BPI/BdT)",
            ],
            "delai_instruction": "2 à 6 mois",
            "permanent": True,
            "url_officielle": "https://www.atout-france.fr/fr/informations/label-vignobles-decouvertes",
            "formulaire_url": None,
            "tags": [
                "œnotourisme",
                "tourisme gastronomique",
                "Vignobles & Découvertes",
                "patrimoine",
                "valorisation touristique",
                "vin",
                "gastronomie",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : tous niveaux
supabase.table("aides_protections").insert(
    [
        {"aide_id": aide_id, "protection_code": "classe"},
        {"aide_id": aide_id, "protection_code": "inscrit"},
        {"aide_id": aide_id, "protection_code": "non_protege"},
    ]
).execute()
print("  ✓ Protections insérées")

# Propriétaires : large gamme
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : restauration et aménagement touristique
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "electricite"},
        {"aide_id": aide_id, "travaux_code": "plomberie"},
        {"aide_id": aide_id, "travaux_code": "accessibilite"},
        {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Pas de contrainte régionale (dispositifs multi-régions)
# Tous segments
# Pas de contrainte état de conservation

print(f"\n✅ Aide œnotourisme & gastronomie insérée avec succès (id: {aide_id})")
