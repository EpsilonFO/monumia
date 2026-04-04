"""
Seed: Souscription publique — Fondation du patrimoine.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_souscription_fondation_patrimoine.py
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
            "nom": "Souscription publique — Fondation du patrimoine",
            "nom_court": "Souscription Fondation du patrimoine",
            "description": "Campagne de collecte de dons défiscalisés organisée par la Fondation du patrimoine au profit d'un projet de restauration patrimoniale. Les donateurs bénéficient d'une réduction d'impôt de 66 % (IR) ou 60 % (IS).",
            "description_longue": (
                "La souscription publique est le dispositif historique de la Fondation du patrimoine. "
                "Elle permet de collecter des dons auprès de particuliers et d'entreprises pour financer "
                "la restauration d'un édifice patrimonial. Les dons sont défiscalisés : 66 % de réduction "
                "d'impôt sur le revenu pour les particuliers (dans la limite de 20 % du revenu imposable), "
                "ou 60 % de réduction d'impôt sur les sociétés pour les entreprises (dans la limite de "
                "20 000 € ou 0,5 % du CA HT). La Fondation du patrimoine héberge la collecte sur sa "
                "plateforme, assure la communication et reverse les fonds au maître d'ouvrage. "
                "La souscription peut être ouverte pour tout type de patrimoine : protégé MH, non protégé, "
                "religieux, civil, vernaculaire, etc. Le propriétaire peut être public (commune, département) "
                "ou privé (sous conditions). La Fondation peut également abonder la collecte par ses propres "
                "fonds. Ce dispositif est cumulable avec le label Fondation du patrimoine et les subventions "
                "publiques (DRAC, collectivités)."
            ),
            "categorie": "fondation",
            "type": "souscription",
            "organisme": "Fondation du patrimoine",
            "montant_max": None,
            "taux_max": None,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Tout édifice présentant un intérêt patrimonial (architectural, historique, mémoriel, paysager) peut faire l'objet d'une collecte de dons\n"
                "- Tous les niveaux de protection sont éligibles : classé MH, inscrit MH, labellisé Fondation du patrimoine, non protégé\n"
                "- Patrimoine bâti, mobilier (immeubles par destination), parcs et jardins, patrimoine naturel et biodiversité\n"
                "- Propriétaires éligibles : communes et collectivités territoriales, intercommunalités, associations (loi 1901), propriétaires privés (personnes physiques)\n"
                "- SCI éligibles uniquement si composées exclusivement de personnes physiques et dont l'objet est la gestion ou la location nue\n"
                "- Sociétés commerciales et SCI détenues par des personnes morales : EXCLUES\n"
                "- Les donateurs ne doivent avoir aucun lien de parenté (jusqu'au 4e degré) ni lien financier/capitalistique avec le propriétaire\n"
                "- La collecte représente en moyenne environ 10 % du plan de financement du projet\n"
                "- Frais de gestion : 6 % pour les propriétaires publics et associations, 5 % pour les propriétaires privés\n"
                "- Durée de la campagne : 5 ans, renouvelable. Si le projet n'aboutit pas sous 5 ans, les dons peuvent être réaffectés\n"
                "- Les travaux doivent relever de réparations et d'entretien — les destructions, constructions neuves, reconstructions et extensions ne sont PAS éligibles\n"
                "- Avantages fiscaux pour les donateurs particuliers : réduction IR de 66 % (limite 20 % du revenu imposable) ou réduction IFI de 75 % (limite 50 000 €)\n"
                "- Patrimoine religieux (depuis 15/09/2023) : réduction exceptionnelle de 75 % sur les premiers 1 000 € donnés, puis 66 % au-delà\n"
                "- Avantages fiscaux pour les entreprises mécènes : réduction IS de 60 % jusqu'à 2 M€ de dons, 40 % au-delà (limite 20 000 € ou 5 ‰ du CA HT)\n"
                "- Les fonds sont versés au porteur de projet en fin de travaux, après vérification de la conformité par l'ABF et le CAUE\n"
                "- Cumulable avec le label Fondation du patrimoine, les subventions DRAC, les aides des collectivités territoriales et le Loto du patrimoine"
            ),
            "demarche_description": (
                "1. Contacter la délégation territoriale de la Fondation du patrimoine pour présenter le projet\n"
                "2. Remplir le dossier préliminaire en ligne sur le formulaire dédié de la Fondation\n"
                "3. Fournir : photos, descriptif du bâtiment, programme de travaux, devis, preuve de propriété, plan de financement\n"
                "4. Pré-instruction par le délégué territorial (visite du site possible)\n"
                "5. Avis technique éventuel de l'UDAP (ABF), du CAUE ou de la DRAC\n"
                "6. Signature de la convention entre la Fondation et le porteur de projet → lancement de la collecte\n"
                "7. Page de projet dédiée sur fondation-patrimoine.org, supports de communication, formulaires de dons\n"
                "8. Réalisation des travaux conformément au programme validé\n"
                "9. Versement des fonds après vérification de la conformité des travaux"
            ),
            "documents_requis": [
                "Descriptif du site et de son intérêt patrimonial",
                "Programme détaillé des travaux de restauration",
                "Devis des entreprises",
                "Plan de financement prévisionnel",
                "Photos du site (avant travaux)",
                "Preuve de propriété",
                "Délibération du conseil municipal (si propriétaire public)",
                "Statuts de l'association (si association)",
            ],
            "delai_instruction": "1 à 3 mois",
            "permanent": True,
            "url_officielle": "https://www.fondation-patrimoine.org/c/soumettre-un-projet/organiser-une-collecte/233",
            "formulaire_url": "https://www.fondation-patrimoine.org/soumettre-un-projet/depot-de-dossier/formulaire-demande-collecte",
            "tags": [
                "Fondation du patrimoine",
                "souscription publique",
                "collecte de dons",
                "défiscalisation",
                "mécénat",
                "restauration",
                "patrimoine",
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
        {"aide_id": aide_id, "protection_code": "spr"},
    ]
).execute()
print("  ✓ Protections insérées")

# Propriétaires : tous types
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : tous types de restauration
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "couverture"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "vitraux"},
        {"aide_id": aide_id, "travaux_code": "peintures_murales"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
        {"aide_id": aide_id, "travaux_code": "mobilier"},
        {"aide_id": aide_id, "travaux_code": "orgues"},
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

print(
    f"\n✅ Souscription publique Fondation du patrimoine insérée avec succès (id: {aide_id})"
)
