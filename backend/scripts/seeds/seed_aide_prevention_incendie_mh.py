"""
Seed: Prévention incendie sur les Monuments Historiques — Subvention DRAC
pour la mise en sécurité incendie des MH.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_prevention_incendie_mh.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Subvention DRAC — Mise en sécurité incendie des monuments historiques",
    "nom_court": "DRAC Sécurité incendie MH",
    "description": "Subvention de l'État (DRAC) pour les travaux de mise en sécurité incendie des monuments historiques classés ou inscrits : détection, extinction, mise aux normes électriques, plans de sauvegarde.",
    "description_longue": (
        "Suite à l'incendie de Notre-Dame de Paris en 2019, le Ministère de la Culture "
        "a renforcé sa politique de prévention incendie pour l'ensemble des monuments "
        "historiques. Les travaux de mise en sécurité strictement nécessaires à la "
        "conservation de l'immeuble sont éligibles aux subventions DRAC, au même titre "
        "que les travaux de restauration. Cela inclut l'installation de systèmes de "
        "détection incendie (détecteurs de fumée, caméras thermiques), de systèmes "
        "d'extinction (sprinklers adaptés au patrimoine, brouillard d'eau), la mise "
        "aux normes des installations électriques, la suppression ou neutralisation "
        "de réseaux ou installations techniques présentant des risques, et l'élaboration "
        "de plans de sauvegarde des biens culturels. Le plan « Sécurité cathédrales » "
        "lancé en 2019 et renforcé en 2023 a déployé 11 actions spécifiques pour les "
        "87 cathédrales propriétés de l'État, incluant des caméras thermiques, des "
        "audits de sécurité-sûreté et le retrait des installations à risques. Ces "
        "subventions s'appliquent à tous les monuments historiques, publics ou privés, "
        "classés ou inscrits. Les conseillers sécurité incendie de la MISSA (Mission "
        "Sécurité Sûreté) du Ministère évaluent le niveau de sécurité et émettent des "
        "avis techniques sur les projets."
    ),
    "categorie": "etat_drac",
    "type": "subvention",
    "organisme": "Ministère de la Culture — DRAC / DAC / MISSA",
    "montant_max": None,
    "taux_max": 40,
    "montant_min": 1000,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": False,
    "architecte_requis": True,
    "conditions_eligibilite_detail": (
        "- L'immeuble doit être protégé au titre des monuments historiques (classé ou inscrit).\n"
        "- Taux de subvention : jusqu'à 40 % du montant des travaux pour un immeuble classé, "
        "jusqu'à 15-20 % pour un immeuble inscrit (plafonné à 40 % de la dépense réelle).\n"
        "- Subvention plancher : 1 000 €.\n"
        "- Les travaux éligibles sont ceux strictement nécessaires à la conservation et à la "
        "sécurité de l'immeuble : dispositifs de détection et d'extinction incendie, mise aux "
        "normes électriques, suppression ou neutralisation de réseaux et installations techniques "
        "présentant des risques de sécurité.\n"
        "- Les travaux ne doivent pas commencer avant l'obtention de l'accord de la DRAC. "
        "Le préfet de région dispose de 6 mois à compter du dossier complet pour délivrer "
        "l'arrêté de subvention.\n"
        "- Les travaux doivent être réalisés par des entreprises spécialisées et validés par "
        "l'Architecte des Bâtiments de France (ABF) pour les inscrits, ou sous la maîtrise "
        "d'œuvre de l'architecte en chef des monuments historiques (ACMH) pour les classés.\n"
        "- Les propriétaires publics et privés sont éligibles.\n"
        "- Le cumul des aides publiques ne peut dépasser 80 % de la dépense subventionnée ; "
        "le porteur doit financer au minimum 20 %.\n"
        "- Les monuments en état de péril ou présentant un risque incendie élevé "
        "(installations électriques vétustes, combles en bois sans détection, absence de "
        "compartimentage) sont prioritaires.\n"
        "- Un diagnostic sécurité incendie préalable par les conseillers MISSA peut être "
        "demandé ou recommandé.\n"
        "- L'élaboration d'un plan de sauvegarde des biens culturels (PSBC) est éligible "
        "au financement.\n"
        "- Pour les cathédrales (propriété de l'État) : programme spécifique « Sécurité "
        "cathédrales » avec financement intégral par l'État."
    ),
    "demarche_description": (
        "1. Contacter la Conservation Régionale des Monuments Historiques (CRMH) de la DRAC\n"
        "2. Faire réaliser un diagnostic sécurité incendie (par un bureau d'études spécialisé "
        "ou les conseillers MISSA)\n"
        "3. Constituer le dossier de demande de subvention avec l'ABF ou l'ACMH\n"
        "4. Déposer le dossier sur le portail Démarches Simplifiées\n"
        "5. Instruction par la DRAC et arbitrage budgétaire\n"
        "6. Arrêté de subvention par le préfet de région\n"
        "7. Réalisation des travaux (ne pas commencer avant l'arrêté)\n"
        "8. Demande de versement sur présentation des factures acquittées"
    ),
    "documents_requis": [
        "Formulaire de demande de subvention (Démarches Simplifiées)",
        "Diagnostic sécurité incendie",
        "Devis détaillés des entreprises",
        "Programme des travaux validé par l'ABF ou l'ACMH",
        "Plan de financement prévisionnel",
        "Attestation de propriété ou bail",
        "Arrêté de classement ou d'inscription au titre des MH",
        "Photos de l'état actuel",
        "RIB du propriétaire ou maître d'ouvrage",
    ],
    "delai_instruction": "3 à 6 mois",
    "permanent": True,
    "url_officielle": "https://www.culture.gouv.fr/thematiques/securite-surete/securite-et-surete-des-biens/securite-et-surete-des-monuments-historiques",
    "formulaire_url": "https://demarche.numerique.gouv.fr/commencer/mh_subvention-etudes-travaux",
    "tags": [
        "incendie", "sécurité", "prévention", "détection",
        "DRAC", "MISSA", "monument historique", "mise en sécurité",
        "plan cathédrales", "PSBC", "électricité",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : MH classés et inscrits uniquement
supabase.table("aides_protections").insert([
    {"aide_id": aide_id, "protection_code": "classe"},
    {"aide_id": aide_id, "protection_code": "inscrit"},
]).execute()
print("  ✓ Protections insérées")

# Propriétaires : tous types
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "public_departement"},
    {"aide_id": aide_id, "proprietaire_code": "public_region"},
    {"aide_id": aide_id, "proprietaire_code": "public_etat"},
    {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
    {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
    {"aide_id": aide_id, "proprietaire_code": "mixte"},
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

# Segments : tous
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "commune"},
    {"aide_id": aide_id, "segment_code": "prive"},
]).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte formelle, mais priorité au péril
# On n'insère pas de contrainte pour ne pas exclure des MH en bon état qui veulent prévenir

print(f"\n✅ Prévention incendie MH inséré avec succès (id: {aide_id})")
