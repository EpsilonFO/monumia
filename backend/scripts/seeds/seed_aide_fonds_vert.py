"""
Seed: Fonds vert — Rénovation énergétique et transition écologique des bâtiments publics locaux.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_fonds_vert.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Fonds vert — Rénovation énergétique des bâtiments publics locaux",
    "nom_court": "Fonds vert",
    "description": "Subvention de l'État aux collectivités pour la rénovation énergétique de leur patrimoine bâti et la transition écologique, incluant le patrimoine cultuel dont elles sont propriétaires.",
    "description_longue": (
        "Le Fonds d'accélération de la transition écologique dans les territoires (Fonds vert) "
        "est un dispositif de l'État doté d'environ 840 M€ en 2026, destiné à soutenir les "
        "collectivités territoriales dans leurs investissements de transition écologique. "
        "L'axe 1 « Performance environnementale » finance notamment la rénovation énergétique "
        "des bâtiments publics locaux (mairies, écoles, équipements sportifs, églises communales…). "
        "Le patrimoine cultuel dont les collectivités sont propriétaires constitue une cible "
        "transversale prioritaire. Le taux de subvention est déterminé par le préfet de département "
        "au cas par cas, généralement entre 20 % et 80 % selon la capacité financière de la "
        "collectivité et l'ambition écologique du projet. Un minimum de 20 % d'autofinancement "
        "est requis. Le cumul avec DETR, DSIL, DSID et DPV est possible."
    ),
    "categorie": "etat_drac",
    "type": "subvention",
    "organisme": "Ministère de la Transition écologique — Préfectures de département",
    "montant_max": None,
    "taux_max": 80,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": True,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Porteurs éligibles : communes, EPCI à fiscalité propre, pôles d'équilibre territorial, "
        "syndicats d'énergie, départements, régions\n"
        "- Les associations, fondations, établissements publics locaux et bailleurs sociaux "
        "peuvent être éligibles pour certaines mesures spécifiques\n"
        "- Bâtiments éligibles : bâtiments publics existants (tertiaire ou résidentiel) dont la "
        "collectivité est propriétaire ou titulaire d'un bail emphytéotique\n"
        "- Le patrimoine cultuel (églises, chapelles) dont les communes sont propriétaires est "
        "une cible transversale prioritaire\n"
        "- Pour la rénovation énergétique (Axe 1) : objectif de réduction de 40 % de la "
        "consommation d'énergie finale, ou atteinte du niveau BBC rénovation / classe C du DPE\n"
        "- Une étude thermique préalable est requise pour démontrer l'atteinte de l'objectif\n"
        "- Le début d'exécution des travaux ne peut intervenir avant le dépôt de la demande "
        "sur Démarches Simplifiées (sauf urgence avérée)\n"
        "- Autofinancement minimum de 20 % par le porteur de projet\n"
        "- Taux de subvention déterminé par le préfet au cas par cas (généralement 20-80 %) "
        "en fonction du gain écologique, de la capacité financière et de la situation socio-économique\n"
        "- Cumul possible avec DETR, DSIL, DSID, DPV et autres aides publiques\n"
        "- Les projets doivent s'inscrire dans l'un des trois axes : performance environnementale, "
        "adaptation au changement climatique, ou amélioration du cadre de vie\n"
        "- Priorité donnée aux projets en territoires ruraux, petites villes et quartiers prioritaires\n"
        "- Les travaux de mise en sécurité du patrimoine cultuel sont éligibles même sans "
        "composante énergétique forte"
    ),
    "demarche_description": (
        "1. Identifier la mesure du Fonds vert correspondant au projet (Axe 1, 2 ou 3)\n"
        "2. Vérifier l'éligibilité auprès de la préfecture de département ou de la DDT\n"
        "3. Réaliser l'étude thermique préalable (pour la rénovation énergétique)\n"
        "4. Déposer le dossier sur la plateforme Démarches Simplifiées avant la date limite\n"
        "5. Le préfet instruit et sélectionne les projets, détermine le montant de la subvention\n"
        "6. Convention de subvention signée ; une avance est versée au démarrage\n"
        "7. Versements complémentaires sur justificatifs d'avancement (plafonnés à 80 % de la subvention)\n"
        "8. Solde versé à l'achèvement des travaux sur présentation du bilan"
    ),
    "documents_requis": [
        "Délibération de la collectivité approuvant le projet et le plan de financement",
        "Étude thermique préalable (rénovation énergétique)",
        "Devis ou estimations détaillées des travaux",
        "Plan de financement prévisionnel",
        "Note descriptive du projet et de ses objectifs écologiques",
        "Attestation de propriété ou bail emphytéotique du bâtiment",
    ],
    "delai_instruction": "2 à 6 mois",
    "permanent": False,
    "url_officielle": "https://www.ecologie.gouv.fr/fonds-vert",
    "formulaire_url": None,
    "tags": [
        "Fonds vert", "rénovation énergétique", "bâtiment public", "transition écologique",
        "patrimoine cultuel", "collectivités", "préfecture", "subvention État",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (tous bâtiments publics, protégés ou non)

# Propriétaires : collectivités publiques uniquement
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "public_departement"},
    {"aide_id": aide_id, "proprietaire_code": "public_region"},
    {"aide_id": aide_id, "proprietaire_code": "public_etat"},
]).execute()
print("  ✓ Propriétaires insérés")

# Travaux éligibles : rénovation énergétique au sens large
supabase.table("aides_travaux").insert([
    {"aide_id": aide_id, "travaux_code": "toiture"},
    {"aide_id": aide_id, "travaux_code": "charpente"},
    {"aide_id": aide_id, "travaux_code": "couverture"},
    {"aide_id": aide_id, "travaux_code": "facade"},
    {"aide_id": aide_id, "travaux_code": "maconnerie"},
    {"aide_id": aide_id, "travaux_code": "menuiserie"},
    {"aide_id": aide_id, "travaux_code": "electricite"},
    {"aide_id": aide_id, "travaux_code": "chauffage"},
    {"aide_id": aide_id, "travaux_code": "ventilation"},
    {"aide_id": aide_id, "travaux_code": "protection_solaire"},
    {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
    {"aide_id": aide_id, "travaux_code": "accessibilite"},
    {"aide_id": aide_id, "travaux_code": "restauration_generale"},
]).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale → pas de contrainte

# Segments : communes et collectivités
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "commune"},
]).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ Fonds vert inséré avec succès (id: {aide_id})")
