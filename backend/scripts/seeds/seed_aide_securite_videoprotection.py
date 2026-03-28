"""
Seed: Sécurité et vidéoprotection — FIPD et aides à la sécurisation des
monuments historiques et lieux de culte patrimoniaux.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_securite_videoprotection.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "FIPD — Fonds interministériel de prévention de la délinquance et de la radicalisation — Sécurisation des sites patrimoniaux",
    "nom_court": "FIPD Vidéoprotection patrimoine",
    "description": "Subvention du FIPD pour la sécurisation des monuments historiques, lieux de culte et sites patrimoniaux : vidéoprotection, alarmes anti-intrusion, contrôle d'accès, éclairage de sécurité.",
    "description_longue": (
        "Le Fonds interministériel de prévention de la délinquance et de la radicalisation "
        "(FIPD), géré par le Secrétariat général du Comité interministériel de prévention de "
        "la délinquance et de la radicalisation (SG-CIPDR), finance l'installation de systèmes "
        "de vidéoprotection et d'équipements de sécurité sur la voie publique et dans les "
        "établissements recevant du public, y compris les monuments historiques et les lieux de "
        "culte patrimoniaux. Le FIPD couvre jusqu'à 80 % du coût des équipements de "
        "vidéoprotection pour les communes (50 % en cas de renouvellement). Pour les lieux de "
        "culte, le taux peut atteindre 80 % via le volet spécifique « Sécurisation des sites "
        "sensibles ». Les équipements éligibles comprennent les caméras de vidéoprotection, "
        "les systèmes d'alarme anti-intrusion, les dispositifs de contrôle d'accès, l'éclairage "
        "de sécurité extérieur, les portiques et barrières de sécurité, ainsi que les études "
        "de sûreté et les audits de vulnérabilité. Les travaux d'installation doivent être "
        "compatibles avec le caractère patrimonial de l'édifice et respecter les prescriptions "
        "de l'ABF pour les monuments protégés. Le FIPD est doté d'environ 80 millions d'euros "
        "par an, dont une part significative est consacrée à la vidéoprotection. Les demandes "
        "sont instruites par les préfectures de département. Un volet spécifique « Protection "
        "des lieux de culte » existe depuis 2015, renforcé après les attentats, permettant de "
        "financer la sécurisation des églises, cathédrales, synagogues, mosquées et temples "
        "présentant un risque identifié."
    ),
    "categorie": "etat_drac",
    "type": "subvention",
    "organisme": "SG-CIPDR / Ministère de l'Intérieur / Préfectures",
    "montant_max": None,
    "taux_max": 80,
    "montant_min": None,
    "plancher": None,
    "base_ttc": True,
    "commune_max_population": None,
    "cofinancement_requis": True,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Le site doit être un établissement recevant du public (ERP) ou un lieu accessible "
        "au public : monument historique ouvert à la visite, lieu de culte, musée, site "
        "patrimonial.\n"
        "- Vidéoprotection voie publique (communes) : taux de subvention jusqu'à 80 % pour une "
        "première installation, 50 % pour un renouvellement ou une extension. Le projet doit "
        "être inscrit dans un schéma directeur de vidéoprotection communal ou intercommunal.\n"
        "- Sécurisation des lieux de culte : taux jusqu'à 80 % du coût des équipements. Le lieu "
        "de culte doit présenter un risque identifié (évaluation de la menace par les services "
        "de renseignement). Sont éligibles : les alarmes anti-intrusion, la vidéoprotection "
        "intérieure et extérieure, le contrôle d'accès, l'éclairage de sécurité, les travaux "
        "de mise en sûreté.\n"
        "- Pour les monuments historiques : les équipements doivent être discrets et réversibles, "
        "compatibles avec le caractère patrimonial de l'édifice. Accord de l'ABF obligatoire "
        "pour les MH classés ou inscrits et les immeubles situés en SPR.\n"
        "- Les bénéficiaires sont les communes, EPCI, associations cultuelles (loi 1905), "
        "associations diocésaines, établissements publics, et associations gestionnaires de "
        "sites patrimoniaux.\n"
        "- Les propriétaires privés de monuments historiques ne sont pas directement éligibles "
        "au FIPD mais peuvent bénéficier d'un accompagnement via la commune.\n"
        "- La demande doit être déposée auprès de la préfecture de département avant le "
        "31 mars de chaque année (campagne annuelle).\n"
        "- Le matériel de vidéoprotection doit être conforme aux normes en vigueur et le "
        "système doit être déclaré à la préfecture (autorisation préfectorale de vidéoprotection).\n"
        "- Les dépenses éligibles couvrent le matériel, l'installation, le raccordement au "
        "centre de supervision urbain (CSU) et les études de sûreté.\n"
        "- Les frais de maintenance et d'abonnement ne sont généralement pas éligibles.\n"
        "- Le cumul des aides publiques ne peut dépasser 80 % du coût total du projet."
    ),
    "demarche_description": (
        "1. Contacter la préfecture de département (référent FIPD ou bureau de la prévention de la délinquance)\n"
        "2. Réaliser un audit de sûreté ou une étude de vulnérabilité du site patrimonial\n"
        "3. Constituer le dossier FIPD (formulaire CERFA, devis, plan d'implantation des caméras)\n"
        "4. Obtenir l'accord de l'ABF si le site est protégé au titre des MH ou situé en SPR\n"
        "5. Déposer le dossier avant le 31 mars (campagne annuelle)\n"
        "6. Instruction par la préfecture et arbitrage par le préfet\n"
        "7. Notification de la subvention\n"
        "8. Réalisation des travaux et installation des équipements\n"
        "9. Demande de versement sur présentation des factures acquittées\n"
        "10. Déclaration du système de vidéoprotection à la préfecture"
    ),
    "documents_requis": [
        "Formulaire de demande FIPD (CERFA ou formulaire préfectoral)",
        "Audit de sûreté ou étude de vulnérabilité",
        "Devis détaillés des équipements et de l'installation",
        "Plan d'implantation des caméras et équipements de sécurité",
        "Délibération du conseil municipal (si commune) ou décision de l'organe dirigeant",
        "Plan de financement prévisionnel",
        "Accord de l'ABF (si site protégé MH ou SPR)",
        "Schéma directeur de vidéoprotection (si applicable)",
        "RIB de la structure demandeuse",
        "Attestation de propriété ou convention d'occupation",
    ],
    "delai_instruction": "3 à 6 mois (campagne annuelle, dépôt avant le 31 mars)",
    "permanent": True,
    "url_officielle": "https://www.cipdr.gouv.fr/fipd/",
    "formulaire_url": None,
    "tags": [
        "sécurité", "vidéoprotection", "vidéosurveillance", "FIPD",
        "alarme", "anti-intrusion", "lieux de culte", "sûreté",
        "CIPDR", "contrôle d'accès", "monument historique",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte stricte (MH et non-MH éligibles)

# Propriétaires : principalement publics et associations
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "public_departement"},
    {"aide_id": aide_id, "proprietaire_code": "public_region"},
    {"aide_id": aide_id, "proprietaire_code": "public_etat"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
]).execute()
print("  ✓ Propriétaires éligibles insérés")

# Travaux : mise en sécurité, électricité
supabase.table("aides_travaux").insert([
    {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
    {"aide_id": aide_id, "travaux_code": "electricite"},
    {"aide_id": aide_id, "travaux_code": "etude_prealable"},
]).execute()
print("  ✓ Travaux éligibles insérés")

# Régions : aide nationale → pas de contrainte

# Segments : principalement communes
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "commune"},
]).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ Sécurité et vidéoprotection (FIPD) inséré avec succès (id: {aide_id})")
