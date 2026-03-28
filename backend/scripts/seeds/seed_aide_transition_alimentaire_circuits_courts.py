"""
Seed: Transition alimentaire et circuits courts — Programme LEADER et aides
à la diversification agricole pour les propriétaires de domaines patrimoniaux.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_transition_alimentaire_circuits_courts.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Transition alimentaire et circuits courts — Aides à la diversification et à la valorisation des domaines patrimoniaux",
    "nom_court": "Circuits courts patrimoine",
    "description": "Ensemble d'aides (LEADER, FEADER, aides régionales) pour développer des activités de circuits courts, agritourisme et transition alimentaire au sein de domaines patrimoniaux et monuments historiques ruraux.",
    "description_longue": (
        "Les propriétaires de monuments historiques et domaines patrimoniaux en zone rurale "
        "peuvent bénéficier de plusieurs dispositifs d'aide pour développer des activités "
        "liées aux circuits courts et à la transition alimentaire. Le programme LEADER, "
        "financé par le FEADER, soutient des projets de développement local incluant "
        "l'alimentation, les circuits courts et la valorisation du patrimoine. Les aides "
        "régionales à la diversification agricole permettent de financer l'installation "
        "de points de vente, de distributeurs de produits locaux, de cuisines de "
        "transformation ou d'espaces de restauration valorisant les produits du terroir. "
        "L'ANCT (Agence Nationale de la Cohésion des Territoires) finance des initiatives "
        "dans les territoires ruraux couvrant l'alimentation locale et le patrimoine. "
        "Le Fonds Incitatif et Partenarial (FIP) du Ministère de la Culture peut également "
        "contribuer au financement de projets combinant restauration de patrimoine et "
        "activité économique locale dans les communes rurales de moins de 2 000 habitants. "
        "Ces aides s'inscrivent dans la stratégie nationale pour l'alimentation, la "
        "nutrition et le climat (SNANC) et les Projets Alimentaires Territoriaux (PAT)."
    ),
    "categorie": "europe",
    "type": "subvention",
    "organisme": "FEADER / LEADER / Régions / ANCT",
    "montant_max": None,
    "taux_max": 80,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": True,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Le projet doit être situé en zone rurale ou péri-urbaine et contribuer à la "
        "transition alimentaire ou au développement de circuits courts.\n"
        "- Les projets combinant valorisation du patrimoine et activité alimentaire locale "
        "(boutique de produits du terroir dans un monument, restaurant de terroir dans un "
        "domaine historique, marché de producteurs dans un site patrimonial) sont particulièrement "
        "encouragés.\n"
        "- Pour LEADER : le projet doit s'inscrire dans la stratégie locale du Groupe d'Action "
        "Locale (GAL) et le territoire doit être couvert par un GAL actif.\n"
        "- Les bénéficiaires éligibles incluent : collectivités, associations, entreprises "
        "agricoles et artisanales, SCI, exploitants de domaines patrimoniaux.\n"
        "- Les particuliers personnes physiques ne sont généralement pas éligibles directement ; "
        "ils doivent porter le projet via une structure (entreprise, association, SCI).\n"
        "- L'acquisition d'un distributeur automatique de produits alimentaires en circuits "
        "courts est subventionnable sous réserve qu'aucune entreprise de même activité ne "
        "soit implantée dans un rayon de 5 km.\n"
        "- Dépenses éligibles : aménagement de locaux de vente ou de transformation, "
        "équipements de cuisine, signalétique, communication, études de faisabilité, "
        "formation.\n"
        "- Le projet ne doit pas avoir débuté avant le dépôt de la demande (principe de "
        "non-démarrage anticipé pour les fonds européens).\n"
        "- Pour le FIP : communes de moins de 2 000 habitants avec un monument historique.\n"
        "- Le cumul avec d'autres aides publiques est possible dans la limite de 80 % du "
        "coût total (hors aides de minimis).\n"
        "- Les Projets Alimentaires Territoriaux (PAT) reconnus par le Ministère de l'Agriculture "
        "peuvent faciliter l'accès aux financements.\n"
        "- Le porteur de projet doit disposer d'un numéro SIRET."
    ),
    "demarche_description": (
        "1. Identifier le GAL de votre territoire ou le service régional compétent\n"
        "2. Vérifier l'éligibilité du projet avec l'animateur local (GAL, chambre d'agriculture, "
        "service patrimoine de la collectivité)\n"
        "3. Monter le dossier : description du projet, plan de financement, devis, "
        "calendrier, étude de marché si nécessaire\n"
        "4. Déposer le dossier auprès du GAL (LEADER) ou de la Région/ANCT\n"
        "5. Instruction et passage en comité de sélection\n"
        "6. Notification et convention d'aide\n"
        "7. Réalisation du projet et demande de paiement sur justificatifs"
    ),
    "documents_requis": [
        "Numéro SIRET du porteur de projet",
        "Description détaillée du projet",
        "Plan de financement prévisionnel",
        "Devis ou estimations financières",
        "Étude de marché ou de faisabilité",
        "Autorisations administratives (permis, autorisation ABF si MH)",
        "Attestation de non-démarrage du projet",
        "Statuts de la structure",
        "RIB du porteur de projet",
    ],
    "delai_instruction": "2 à 6 mois",
    "permanent": False,
    "url_officielle": "https://www.reseaurural.fr/leader",
    "formulaire_url": None,
    "tags": [
        "circuits courts", "alimentation", "transition alimentaire",
        "agritourisme", "LEADER", "FEADER", "terroir", "patrimoine rural",
        "diversification", "PAT",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte (patrimoine protégé et non protégé)

# Propriétaires : large spectre
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "public_departement"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
    {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
    {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
    {"aide_id": aide_id, "proprietaire_code": "mixte"},
]).execute()
print("  ✓ Propriétaires éligibles insérés")

# Travaux : aménagement, accessibilité
supabase.table("aides_travaux").insert([
    {"aide_id": aide_id, "travaux_code": "restauration_generale"},
    {"aide_id": aide_id, "travaux_code": "accessibilite"},
    {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    {"aide_id": aide_id, "travaux_code": "menuiserie"},
    {"aide_id": aide_id, "travaux_code": "electricite"},
    {"aide_id": aide_id, "travaux_code": "plomberie"},
]).execute()
print("  ✓ Travaux éligibles insérés")

# Régions : aide nationale → pas de contrainte

# Segments : communes et privés
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "commune"},
    {"aide_id": aide_id, "segment_code": "prive"},
]).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ Transition alimentaire et circuits courts inséré avec succès (id: {aide_id})")
