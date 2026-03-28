"""
Seed: Aide régionale patrimoine — Nouvelle-Aquitaine.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_region_nouvelle_aquitaine.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Aide régionale à la restauration des Monuments historiques — Nouvelle-Aquitaine",
    "nom_court": "Aide patrimoine Nouvelle-Aquitaine",
    "description": "Subvention de la Région Nouvelle-Aquitaine pour la restauration du patrimoine protégé (classé et inscrit MH). Taux de 15 % à 30 % selon le niveau de protection, plafond de 400 000 € par tranche annuelle.",
    "description_longue": (
        "La Région Nouvelle-Aquitaine soutient la restauration des monuments historiques classés "
        "et inscrits sur son territoire à travers son règlement d'intervention « Patrimoine et Inventaire » "
        "(délibération 2017.2054.SP, mis à jour en décembre 2024). Le dispositif finance les travaux de "
        "restauration, les honoraires de maîtrise d'œuvre et les études préalables. Le taux de subvention "
        "est de 15 % pour les monuments classés et de 20 à 30 % pour les inscrits, avec un plafond de "
        "400 000 € par tranche annuelle de travaux. Les taux peuvent être modulés selon la carte des enjeux "
        "culturels du territoire. Un dispositif complémentaire « Opérations globales de valorisation de sites "
        "patrimoniaux » permet de financer jusqu'à 25 % HT (plafond 1,5 M€) les projets de valorisation "
        "incluant restauration, scénographie et aménagements d'accueil, avec bonification de +10 % pour les "
        "territoires vulnérables. La Région intervient aux côtés de l'État (DRAC) qui apporte des financements "
        "complémentaires."
    ),
    "categorie": "region",
    "type": "subvention",
    "organisme": "Région Nouvelle-Aquitaine",
    "montant_max": 400000,
    "taux_max": 30,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": False,
    "architecte_requis": True,
    "conditions_eligibilite_detail": (
        "- Patrimoine situé en Nouvelle-Aquitaine\n"
        "- Monuments classés MH : taux de subvention de 15 % du montant total des opérations, plafond 400 000 € par tranche annuelle\n"
        "- Monuments inscrits MH : taux de subvention de 20 à 30 % du montant total des opérations, plafond 400 000 € par tranche annuelle\n"
        "- Les taux sont modulés selon la carte des enjeux culturels du territoire (zones à enjeux forts, intermédiaires ou faibles)\n"
        "- Propriétaires publics éligibles : communes, EPCI, groupements de communes\n"
        "- Propriétaires privés éligibles : personnes physiques ou morales propriétaires d'un édifice classé ou inscrit MH\n"
        "- Le propriétaire privé doit financer au minimum 20 % des travaux\n"
        "- Les aides cumulées ne peuvent dépasser 80 % du coût total\n"
        "- Dépenses éligibles : travaux de restauration, honoraires de maîtrise d'œuvre, études préalables et rapports techniques\n"
        "- Dépenses non éligibles : parkings, voiries, réseaux, entretien courant, frais de fonctionnement généraux et communication\n"
        "- La restauration doit intégrer les principes d'adaptation au changement climatique (principes bioclimatiques, économies d'énergie)\n"
        "- Les SCI sont exclues du dispositif d'opérations globales de valorisation\n"
        "- Pour les opérations globales de valorisation : ouverture au public minimum 3 à 6 mois/an, équipe de gestion professionnelle, affiliation à un office de tourisme\n"
        "- Opérations globales : taux max 25 % HT en zones à enjeux forts (plafond 375 000 €), 20 % en zones intermédiaires/faibles (plafond 300 000 €)\n"
        "- Bonification +10 % pour les territoires vulnérables (opérations globales)\n"
        "- Les travaux ne doivent pas avoir commencé avant l'accord de la Région\n"
        "- Date limite habituelle de dépôt : 1er avril de chaque année (opérations globales)"
    ),
    "demarche_description": (
        "1. Contacter le Service du Patrimoine et de l'Inventaire de la Région en amont du projet (subventions.patrimoine@nouvelle-aquitaine.fr)\n"
        "2. Pour les propriétaires privés : déposer un dossier auprès de la DRAC Nouvelle-Aquitaine (CRMH)\n"
        "3. Ne pas commencer les travaux avant l'obtention de l'accord\n"
        "4. Constituer le dossier : devis, photos, rapports techniques, calendrier, délibération\n"
        "5. Pour les communes/EPCI : déposer la demande d'aide régionale via le guide des aides\n"
        "6. Instruction par les services de la Région\n"
        "7. Notification et versement sur justificatifs"
    ),
    "documents_requis": [
        "Devis des entreprises",
        "Photos du bâtiment",
        "Rapports techniques ou études préalables",
        "Calendrier de mise en œuvre du projet",
        "Délibération institutionnelle / décision du maître d'ouvrage",
        "Étude préalable de valorisation (opérations globales)",
        "Extrait KBIS ou identification SIRENE (personnes morales)",
    ],
    "delai_instruction": "3 à 6 mois",
    "permanent": True,
    "url_officielle": "https://les-aides.nouvelle-aquitaine.fr/patrimoine-et-inventaire",
    "formulaire_url": "https://les-aides.nouvelle-aquitaine.fr/fiche/restauration-des-monuments-historiques/",
    "tags": [
        "Nouvelle-Aquitaine", "région", "patrimoine", "restauration",
        "subvention régionale", "monuments historiques",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : classés et inscrits
supabase.table("aides_protections").insert([
    {"aide_id": aide_id, "protection_code": "classe"},
    {"aide_id": aide_id, "protection_code": "inscrit"},
]).execute()
print("  ✓ Protections insérées")

# Propriétaires : communes, EPCI, privés
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
    {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
]).execute()
print("  ✓ Propriétaires insérés")

# Travaux : large gamme de restauration
supabase.table("aides_travaux").insert([
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
]).execute()
print("  ✓ Travaux insérés")

# Région : Nouvelle-Aquitaine uniquement
supabase.table("aides_regions").insert([
    {"aide_id": aide_id, "region_code": "nouvelle-aquitaine"},
]).execute()
print("  ✓ Région insérée")

# Segments : communes et privés
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "commune"},
    {"aide_id": aide_id, "segment_code": "prive"},
]).execute()
print("  ✓ Segments insérés")

# Pas de contrainte sur départements, états de conservation

print(f"\n✅ Aide régionale Nouvelle-Aquitaine insérée avec succès (id: {aide_id})")
