"""
Seed: Hébergement insolite / Tourisme d'expérience.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_hebergement_insolite_tourisme.py
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
            "nom": "Aides régionales à l'hébergement insolite et au tourisme d'expérience dans le patrimoine",
            "nom_court": "Hébergement insolite patrimoine",
            "description": "Dispositifs régionaux et nationaux de soutien à la création d'hébergements insolites et de tourisme d'expérience dans des bâtiments patrimoniaux, y compris monuments protégés. Subventions de 10 % à 25 % selon les régions.",
            "description_longue": (
                "Plusieurs régions françaises proposent des aides à la création d'hébergements touristiques "
                "insolites et d'expérience, notamment dans des bâtiments patrimoniaux (châteaux, manoirs, "
                "abbayes, corps de ferme historiques). Ces dispositifs visent à diversifier l'offre touristique "
                "en valorisant le patrimoine bâti. Les formats éligibles incluent : chambres d'hôtes thématiques "
                "dans des MH, gîtes insolites (cabanes, yourtes, roulottes dans le parc d'un château), "
                "hébergements atypiques intégrés à un site patrimonial, escape games patrimoniaux avec nuitée, etc. "
                "Les taux varient de 10 % à 25 % selon les régions. La Région Grand Est finance jusqu'à 20 % "
                "(plafond 70 000 €) pour des hébergements insolites labellisés. La Région Nouvelle-Aquitaine "
                "propose jusqu'à 25 % HT (plafond 500 000 €) pour les opérations globales de valorisation "
                "de sites patrimoniaux incluant un volet hébergement. Le Prêt Tourisme BPI France (50 000 à "
                "5 M€) est également mobilisable pour ces projets. Les propriétaires de MH peuvent combiner "
                "ces aides avec les subventions DRAC, le régime fiscal MH et le label Fondation du Patrimoine."
            ),
            "categorie": "region",
            "type": "subvention",
            "organisme": "Régions françaises / BPI France / Banque des Territoires",
            "montant_max": 500000,
            "taux_max": 25,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Hébergements insolites dans des bâtiments patrimoniaux (MH classés, inscrits, ou patrimoine d'intérêt)\n"
                "- Formats éligibles : chambres d'hôtes thématiques, gîtes insolites, hébergements atypiques, tourisme expérientiel dans un site patrimonial\n"
                "- Les structures démontables (tipis, yourtes isolées) peuvent être exclues selon les régions (ex : Grand Est exclut les structures non pérennes)\n"
                "- Région Grand Est : subvention max 20 %, plafond 70 000 € (10 000 €/unité, max 7 unités), label « Insolite » requis (Gîtes de France, Clévacances ou équivalent), minimum 3 unités en création, communes et EPCI uniquement\n"
                "- Région Nouvelle-Aquitaine (opérations globales) : subvention max 25 % HT, plafond 500 000 €, ouverture au public 3-6 mois/an min., équipe professionnelle, billetterie, volet médiation obligatoire\n"
                "- Nouvelle-Aquitaine bonification +10 % pour territoires vulnérables, 15 % si cofinancement FEDER/FEADER (plafond 300 000 €)\n"
                "- Les SCI et particuliers sont exclus du dispositif Nouvelle-Aquitaine opérations globales\n"
                "- Communes, EPCI, départements, associations, entreprises éligibles selon les régions\n"
                "- Les travaux doivent être réalisés par des entreprises (auto-construction généralement exclue)\n"
                "- Le projet doit s'inscrire dans une stratégie touristique locale (partenariat avec l'OT recommandé)\n"
                "- Les hébergements doivent respecter les normes de sécurité et d'accessibilité ERP le cas échéant\n"
                "- Pour les MH : les travaux doivent être compatibles avec la protection patrimoniale (avis ABF/DRAC)\n"
                "- Prêt Tourisme BPI : 50 000 à 5 M€, TPE/PME immatriculées depuis 3 ans, cofinancement bancaire obligatoire\n"
                "- Banque des Territoires : investissement en fonds propres + prêts fonds d'épargne pour collectivités, EPCI, SEM, SPL\n"
                "- Cumulable avec DRAC MH, régime fiscal MH, Label Fondation du Patrimoine, FEADER/LEADER, ZRR/FRR"
            ),
            "demarche_description": (
                "1. Identifier le dispositif régional applicable à votre territoire\n"
                "2. Contacter le service tourisme de la Région ou l'office de tourisme local\n"
                "3. Vérifier la compatibilité du projet avec la protection patrimoniale (ABF/DRAC)\n"
                "4. Constituer le dossier : programme d'hébergement, étude de marché, devis, plan de financement\n"
                "5. Déposer le dossier auprès de la Région ou de l'organisme compétent\n"
                "6. Pour le Prêt Tourisme BPI : contacter BPI France directement\n"
                "7. Instruction et notification\n"
                "8. Réalisation des travaux et versement sur justificatifs"
            ),
            "documents_requis": [
                "Programme détaillé du projet d'hébergement",
                "Étude de marché touristique",
                "Devis des entreprises",
                "Plan de financement prévisionnel",
                "Photos du site",
                "Autorisation de travaux (permis ou déclaration préalable)",
                "Avis ABF/DRAC si monument protégé",
                "Preuve de labellisation ou demande en cours (selon régions)",
                "Business plan (pour Prêt Tourisme BPI)",
            ],
            "delai_instruction": "2 à 6 mois",
            "permanent": True,
            "url_officielle": "https://aides-territoires.beta.gouv.fr/",
            "formulaire_url": None,
            "tags": [
                "hébergement insolite",
                "tourisme d'expérience",
                "patrimoine",
                "valorisation touristique",
                "chambres d'hôtes",
                "gîte",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : tous niveaux y compris non protégé
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

# Travaux : restauration et aménagement
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "electricite"},
        {"aide_id": aide_id, "travaux_code": "plomberie"},
        {"aide_id": aide_id, "travaux_code": "chauffage"},
        {"aide_id": aide_id, "travaux_code": "accessibilite"},
        {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Pas de contrainte régionale (dispositifs multi-régions)
# Pas de contrainte département
# Tous segments
# Pas de contrainte état de conservation

print(f"\n✅ Aide hébergement insolite insérée avec succès (id: {aide_id})")
