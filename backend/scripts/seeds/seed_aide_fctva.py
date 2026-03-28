"""
Seed: FCTVA — Fonds de Compensation pour la Taxe sur la Valeur Ajoutée.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_fctva.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Fonds de Compensation pour la Taxe sur la Valeur Ajoutée (FCTVA)",
    "nom_court": "FCTVA",
    "description": "Compensation forfaitaire de la TVA acquittée par les collectivités territoriales sur leurs dépenses réelles d'investissement, y compris les travaux de restauration de monuments historiques publics.",
    "description_longue": (
        "Le Fonds de Compensation pour la Taxe sur la Valeur Ajoutée (FCTVA) est un prélèvement "
        "sur les recettes de l'État qui compense de manière forfaitaire la TVA acquittée par les "
        "collectivités territoriales et leurs groupements sur leurs dépenses réelles d'investissement. "
        "Le taux de compensation est de 16,404 % du montant TTC des dépenses éligibles. Pour les "
        "travaux de restauration de monuments historiques appartenant aux collectivités, le FCTVA "
        "constitue un levier financier automatique important, cumulable avec les subventions DRAC, "
        "DGD, DETR ou DSIL. Depuis la réforme de 2021, le traitement est largement automatisé "
        "via les comptes de gestion. Le versement intervient selon trois régimes : année N (contemporain), "
        "N+1 (accéléré) ou N+2 (droit commun) selon le type de collectivité."
    ),
    "categorie": "etat_drac",
    "type": "subvention",
    "organisme": "Direction Générale des Finances Publiques (DGFiP)",
    "montant_max": None,
    "taux_max": 16,
    "montant_min": None,
    "plancher": None,
    "base_ttc": True,
    "commune_max_population": None,
    "cofinancement_requis": False,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Bénéficiaires : communes, EPCI, départements, régions, syndicats mixtes, SDIS, CCAS/CIAS, établissements publics locaux\n"
        "- Les propriétaires privés ne sont PAS éligibles au FCTVA\n"
        "- Taux de compensation forfaitaire : 16,404 % du montant TTC des dépenses éligibles\n"
        "- Dépenses éligibles : dépenses réelles d'investissement inscrites en section d'investissement du budget\n"
        "  • Travaux de construction, rénovation, restauration de bâtiments publics\n"
        "  • Travaux sur monuments historiques appartenant à la collectivité\n"
        "  • Équipements, voirie, réseaux\n"
        "  • Immobilisations corporelles\n"
        "- Dépenses NON éligibles :\n"
        "  • Biens cédés ou mis à disposition de tiers non éligibles\n"
        "  • Immobilisations incorporelles (sauf logiciels)\n"
        "  • Dépenses réalisées pour des activités assujetties à la TVA (pas de double compensation)\n"
        "- Trois régimes de versement :\n"
        "  • Contemporain (année N) : traitement automatisé depuis 2021 pour certaines collectivités\n"
        "  • Accéléré (N+1) : communautés de communes, communautés d'agglomération ayant signé un CRTE, etc.\n"
        "  • Droit commun (N+2) : autres collectivités\n"
        "- Le FCTVA est cumulable avec les autres subventions (DRAC, DGD, DETR, DSIL, FEDER, etc.)\n"
        "- Le traitement est largement automatisé depuis la réforme de 2021 via l'exploitation des comptes de gestion\n"
        "- Les travaux doivent être inscrits en section d'investissement du budget de la collectivité"
    ),
    "demarche_description": (
        "1. Inscrire les dépenses de travaux en section d'investissement du budget de la collectivité\n"
        "2. Réaliser les travaux et comptabiliser les dépenses\n"
        "3. Le FCTVA est calculé automatiquement par la DGFiP à partir des comptes de gestion (depuis 2021)\n"
        "4. Vérification par les services préfectoraux\n"
        "5. Versement automatique selon le régime applicable (N, N+1 ou N+2)\n"
        "6. Pour les collectivités non encore automatisées : état déclaratif annuel à transmettre à la préfecture"
    ),
    "documents_requis": [
        "Comptes de gestion de la collectivité (transmis automatiquement par le comptable public)",
        "État déclaratif des dépenses d'investissement éligibles (si non automatisé)",
        "Délibérations budgétaires inscrivant les travaux en section d'investissement",
    ],
    "delai_instruction": "Automatique (versement en N, N+1 ou N+2 selon régime)",
    "permanent": True,
    "url_officielle": "https://www.collectivites-locales.gouv.fr/finances-locales/fonds-de-compensation-pour-la-taxe-sur-la-valeur-ajoutee-fctva",
    "formulaire_url": None,
    "tags": [
        "FCTVA", "TVA", "compensation", "investissement",
        "collectivités", "automatique",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : tous niveaux (toute dépense d'investissement sur bâtiment public)
supabase.table("aides_protections").insert([
    {"aide_id": aide_id, "protection_code": "classe"},
    {"aide_id": aide_id, "protection_code": "inscrit"},
    {"aide_id": aide_id, "protection_code": "non_protege"},
]).execute()
print("  ✓ Protections insérées")

# Propriétaires : collectivités publiques uniquement
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "public_departement"},
    {"aide_id": aide_id, "proprietaire_code": "public_region"},
    {"aide_id": aide_id, "proprietaire_code": "public_etat"},
]).execute()
print("  ✓ Propriétaires insérés")

# Travaux : tous types (c'est une compensation sur dépenses d'investissement)
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
    {"aide_id": aide_id, "travaux_code": "electricite"},
    {"aide_id": aide_id, "travaux_code": "plomberie"},
    {"aide_id": aide_id, "travaux_code": "chauffage"},
    {"aide_id": aide_id, "travaux_code": "accessibilite"},
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

print(f"\n✅ FCTVA inséré avec succès (id: {aide_id})")
