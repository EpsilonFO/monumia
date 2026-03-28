"""
Seed: Aides régionales à l'agritourisme.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_agritourisme.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Aides régionales à l'agritourisme — Diversification touristique des exploitations agricoles",
    "nom_court": "Agritourisme régional",
    "description": "Dispositifs régionaux (PCAE, contrats agritourisme, PASS) finançant la création d'hébergements, restauration et activités touristiques sur les exploitations agricoles, y compris la réhabilitation de bâtiments agricoles patrimoniaux.",
    "description_longue": (
        "Les Régions proposent des dispositifs d'aide à l'agritourisme finançant la diversification "
        "touristique des exploitations agricoles. Ces aides couvrent la création de gîtes ruraux, "
        "chambres d'hôtes, tables d'hôtes, fermes-auberges, fermes pédagogiques, hébergements "
        "insolites et activités de loisirs à la ferme. Elles financent notamment la réhabilitation "
        "de bâtiments agricoles patrimoniaux (granges, bergeries, pigeonniers, corps de ferme) en "
        "lieux d'accueil touristique. Les taux varient de 20 à 80 % selon les régions et dispositifs, "
        "avec des plafonds allant de 20 000 € (PASS Agritourisme) à 500 000 € (Contrat Agritourisme "
        "Occitanie). Le PCAE (Plan de Compétitivité et d'Adaptation des Exploitations) constitue "
        "le cadre national, décliné régionalement avec cofinancement FEADER. L'affiliation MSA "
        "en tant qu'exploitant agricole actif est une condition quasi universelle."
    ),
    "categorie": "region",
    "type": "subvention",
    "organisme": "Conseils Régionaux — cofinancement FEADER, État, Départements",
    "montant_max": 500000,
    "taux_max": 80,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": False,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Bénéficiaires : exploitants agricoles affiliés MSA (condition quasi universelle)\n"
        "- Formes juridiques : GAEC, EARL, SCEA, SARL agricole, exploitation individuelle\n"
        "- L'agritourisme doit être une activité complémentaire (généralement < 20 % du CA)\n"
        "- Principe de non-commencement : les travaux ne doivent pas avoir débuté avant le dépôt\n"
        "- Exemples de dispositifs régionaux :\n"
        "  • Occitanie — Contrat Agritourisme : 20-50 %, plafond 500 000 €, projets structurants, "
        "+10 % JA et écolabel\n"
        "  • Occitanie — PASS Agritourisme : 20-40 %, plafond 20 000 €, petits investissements\n"
        "  • Région Sud PACA : 80 %, plafond 20 000 €, ouverture min. 60 j/an, < 20 % CA en accueil\n"
        "  • Hauts-de-France — Pass'Agri Filières : 30 %, plafond 30 000 €/3 ans, +20 % bonus JA\n"
        "  • Pays de la Loire : 20-50 %, plafond 100 000 €, plancher 50 000 € HT projets structurants\n"
        "  • Île-de-France — Réhabilitation patrimoine bâti rural agricole : 40 % travaux (plafond "
        "90 000 €), 70 % études (plafond 5 000 €)\n"
        "  • Grand Est : 20 %, plafond 70 000 €, min. 3 unités, label requis\n"
        "  • Nouvelle-Aquitaine : 25 %, plafond 500 000 €, +10 % territoires vulnérables\n"
        "- Types de projets : gîtes ruraux, chambres d'hôtes, tables d'hôtes, fermes-auberges, "
        "fermes pédagogiques, hébergements insolites, caveaux de vente, points de vente à la ferme, "
        "activités équestres, activités nature et loisirs\n"
        "- L'adhésion à un réseau professionnel (Bienvenue à la Ferme, Accueil Paysan, Gîtes de France) "
        "est souvent requise ou fortement encouragée (délai de 4 ans pour rejoindre un réseau "
        "dans certains dispositifs)\n"
        "- Si bâtiment protégé MH : avis ABF/DRAC obligatoire, compatibilité des aménagements "
        "avec la protection patrimoniale\n"
        "- Engagement de maintien d'activité : 5 à 10 ans selon les dispositifs\n"
        "- Ouverture minimale : 60 à 90 jours/an selon les régions\n"
        "- Conformité sécurité incendie et accessibilité ERP le cas échéant\n"
        "- Cumul possible avec FEADER/LEADER, aides départementales, DJA"
    ),
    "demarche_description": (
        "1. Contacter la Chambre d'Agriculture départementale pour un diagnostic agritourisme\n"
        "2. Identifier le dispositif régional applicable (site du Conseil Régional)\n"
        "3. Vérifier l'éligibilité au GAL LEADER de son territoire (si zone rurale)\n"
        "4. Si bâtiment MH : contacter la DRAC en parallèle pour les prescriptions architecturales\n"
        "5. Constituer le dossier : description du projet, devis, plan de financement, étude de marché\n"
        "6. Déposer la demande AVANT tout commencement de travaux\n"
        "7. Instruction (2 à 6 mois)\n"
        "8. Convention et démarrage des travaux\n"
        "9. Justificatifs et versement (souvent post-travaux)"
    ),
    "documents_requis": [
        "Attestation MSA (statut exploitant agricole)",
        "Numéro SIRET",
        "Description détaillée du projet agritouristique",
        "Devis d'entreprises",
        "Plan de financement prévisionnel",
        "Étude de marché ou business plan",
        "Attestation de non-commencement des travaux",
        "Permis de construire ou déclaration préalable",
        "Autorisation ABF si bâtiment protégé",
    ],
    "delai_instruction": "2 à 6 mois",
    "permanent": False,
    "url_officielle": "https://agriculture.gouv.fr/agritourisme-tous-la-ferme",
    "formulaire_url": None,
    "tags": [
        "agritourisme", "gîte rural", "chambre d'hôtes", "ferme pédagogique",
        "ferme-auberge", "PCAE", "diversification agricole", "patrimoine rural",
        "Bienvenue à la Ferme", "hébergement insolite", "MSA",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (bâtiments protégés ou non)

# Propriétaires : exploitants agricoles privés
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
    {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
]).execute()
print("  ✓ Propriétaires insérés")

# Travaux éligibles : rénovation et aménagement
supabase.table("aides_travaux").insert([
    {"aide_id": aide_id, "travaux_code": "toiture"},
    {"aide_id": aide_id, "travaux_code": "charpente"},
    {"aide_id": aide_id, "travaux_code": "couverture"},
    {"aide_id": aide_id, "travaux_code": "facade"},
    {"aide_id": aide_id, "travaux_code": "maconnerie"},
    {"aide_id": aide_id, "travaux_code": "menuiserie"},
    {"aide_id": aide_id, "travaux_code": "electricite"},
    {"aide_id": aide_id, "travaux_code": "plomberie"},
    {"aide_id": aide_id, "travaux_code": "chauffage"},
    {"aide_id": aide_id, "travaux_code": "accessibilite"},
    {"aide_id": aide_id, "travaux_code": "restauration_generale"},
    {"aide_id": aide_id, "travaux_code": "parcs_jardins"},
]).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale (chaque région a ses dispositifs) → pas de contrainte

# Segments : privés (exploitants agricoles)
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "prive"},
]).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ Agritourisme régional inséré avec succès (id: {aide_id})")
