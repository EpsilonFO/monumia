"""
Seed: DGD Patrimoine — Dotation Générale de Décentralisation (volet Patrimoine).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_dgd_patrimoine.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Dotation Générale de Décentralisation — Patrimoine (DGD)",
    "nom_court": "DGD Patrimoine",
    "description": "Dotation de l'État compensant le transfert de compétences patrimoine aux collectivités, finançant la restauration des monuments historiques classés et inscrits dont elles sont propriétaires.",
    "description_longue": (
        "La Dotation Générale de Décentralisation — volet Patrimoine (DGD Patrimoine) est issue "
        "de la loi du 13 août 2004 relative aux libertés et responsabilités locales, qui a transféré "
        "aux collectivités territoriales la compétence de gestion des monuments historiques leur "
        "appartenant. Cette dotation compense financièrement ce transfert en permettant aux "
        "collectivités de financer les travaux de restauration, de conservation et d'entretien de "
        "leurs monuments historiques classés ou inscrits. Les crédits sont programmés par le préfet "
        "de région sur proposition du directeur régional des affaires culturelles (DRAC). Le taux "
        "maximum est de 50 % pour les monuments classés et de 40 % pour les monuments inscrits, "
        "sur la base du montant HT des travaux. L'instruction des dossiers est assurée par la "
        "Conservation Régionale des Monuments Historiques (CRMH) au sein de la DRAC."
    ),
    "categorie": "etat_drac",
    "type": "subvention",
    "organisme": "DRAC — Direction Régionale des Affaires Culturelles (Ministère de la Culture)",
    "montant_max": None,
    "taux_max": 50,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": False,
    "architecte_requis": True,
    "conditions_eligibilite_detail": (
        "- Bénéficiaires : communes, EPCI, départements, régions et autres collectivités territoriales propriétaires ou affectataires de monuments historiques\n"
        "- Les propriétaires privés ne sont PAS éligibles à la DGD Patrimoine\n"
        "- L'État (propriétaire direct) n'est PAS éligible\n"
        "- Monuments éligibles : monuments historiques classés ou inscrits uniquement (pas de patrimoine non protégé)\n"
        "- Taux maximum de subvention :\n"
        "  • Monument classé : jusqu'à 50 % du montant HT des travaux\n"
        "  • Monument inscrit : jusqu'à 40 % du montant HT des travaux\n"
        "- Le taux effectif dépend de l'enveloppe régionale disponible et des priorités de la DRAC\n"
        "- Travaux éligibles : restauration, conservation, entretien des parties protégées, études préalables, diagnostics sanitaires, travaux d'urgence (mise hors d'eau, consolidation)\n"
        "- Les travaux sur objets mobiliers classés ou inscrits appartenant aux collectivités sont également éligibles\n"
        "- Cumul possible avec d'autres subventions (Région, Département, Fondation du Patrimoine) dans la limite de 80 % du coût total généralement\n"
        "- Les travaux ne doivent PAS avoir commencé avant la notification de la subvention (sauf autorisation de démarrage anticipé)\n"
        "- Pour les monuments classés : maîtrise d'œuvre obligatoire par un architecte en chef des monuments historiques (ACMH) ou architecte du patrimoine\n"
        "- Pour les monuments inscrits : maîtrise d'œuvre par un architecte qualifié, avec avis de l'ABF\n"
        "- Le dossier doit être déposé avant le 31 décembre N-1 pour une programmation en année N (variable selon les DRAC)\n"
        "- L'avis de la Commission Régionale du Patrimoine et de l'Architecture (CRPA) peut être requis"
    ),
    "demarche_description": (
        "1. Prendre contact avec la Conservation Régionale des Monuments Historiques (CRMH) de la DRAC ou l'UDAP du département\n"
        "2. Constituer le dossier de demande de subvention DGD\n"
        "3. Déposer le dossier auprès de la DRAC de la région (avant le 31 décembre N-1 en général)\n"
        "4. Instruction du dossier par la CRMH\n"
        "5. Avis de la Commission Régionale du Patrimoine et de l'Architecture si nécessaire\n"
        "6. Programmation par le préfet de région sur proposition du DRAC\n"
        "7. Notification de l'arrêté de subvention\n"
        "8. Versement d'acomptes sur justificatifs d'avancement, puis solde sur présentation du décompte final"
    ),
    "documents_requis": [
        "Délibération de la collectivité approuvant l'opération et le plan de financement",
        "Programme détaillé des travaux",
        "Devis estimatifs ou résultats d'appel d'offres",
        "Étude préalable ou diagnostic sanitaire (pour les opérations importantes)",
        "Plan de financement prévisionnel",
        "Attestation de propriété ou titre d'affectataire",
        "Autorisation de travaux sur monument historique (classé) ou déclaration préalable (inscrit)",
        "Avis de l'Architecte des Bâtiments de France",
    ],
    "delai_instruction": "3 à 6 mois",
    "permanent": True,
    "url_officielle": "https://www.culture.gouv.fr/Aides-demarches/Protections-labels-et-appellations/Protection-au-titre-des-monuments-historiques",
    "formulaire_url": None,
    "tags": [
        "DGD", "dotation générale de décentralisation", "patrimoine",
        "DRAC", "monuments historiques", "collectivités",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : classé et inscrit uniquement
supabase.table("aides_protections").insert([
    {"aide_id": aide_id, "protection_code": "classe"},
    {"aide_id": aide_id, "protection_code": "inscrit"},
]).execute()
print("  ✓ Protections insérées")

# Propriétaires : collectivités publiques uniquement
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "public_departement"},
    {"aide_id": aide_id, "proprietaire_code": "public_region"},
]).execute()
print("  ✓ Propriétaires insérés")

# Travaux : restauration, conservation, entretien
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

# Régions : aide nationale → pas de contrainte

# Segments : communes uniquement (collectivités)
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "commune"},
]).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ DGD Patrimoine insérée avec succès (id: {aide_id})")
