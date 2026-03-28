"""
Seed: Interreg — Coopération territoriale européenne pour le patrimoine culturel.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_interreg.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Interreg — Coopération territoriale européenne (volet patrimoine culturel)",
    "nom_court": "Interreg Patrimoine",
    "description": "Financement européen pour des projets transfrontaliers ou transnationaux de valorisation et restauration du patrimoine culturel, dans le cadre des programmes Interreg 2021-2027.",
    "description_longue": (
        "Interreg est le volet de coopération territoriale européenne financé par le FEDER. "
        "La France participe à 22 programmes de coopération territoriale (transfrontaliers, "
        "transnationaux et interrégionaux) dotés de 3 milliards d'euros au total. "
        "Le patrimoine culturel est l'une des thématiques les plus populaires : environ "
        "4,7 milliards d'euros du FEDER sont alloués à la création d'emplois sur sites "
        "patrimoniaux et à l'attractivité touristique. Les programmes concernant la France "
        "incluent : Interreg France-Suisse, France-Italie (ALCOTRA), Grande Région, "
        "Rhin supérieur, France-Wallonie-Vlaanderen, France-Angleterre, Espace Alpin, "
        "Espace Atlantique, Sudoe, Méditerranée, Europe du Nord-Ouest, et Interreg Europe. "
        "Chaque programme a ses propres objectifs, critères et calendriers d'appels à projets. "
        "Le taux de cofinancement FEDER est généralement de 60 % à 80 %. Le projet doit "
        "impérativement associer des partenaires d'au moins deux pays participants."
    ),
    "categorie": "europe",
    "type": "subvention",
    "organisme": "Commission européenne / Autorités de gestion Interreg (Régions, États membres)",
    "montant_max": 2000000,
    "taux_max": 80,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": True,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Le projet doit obligatoirement associer des partenaires d'au moins 2 pays "
        "participant au programme Interreg concerné (dimension transfrontalière ou transnationale).\n"
        "- Le porteur de projet (chef de file) doit être situé dans la zone éligible du programme.\n"
        "- Bénéficiaires éligibles : collectivités territoriales, établissements publics, "
        "universités, centres de recherche, associations, fondations. Les entreprises privées "
        "et particuliers ne sont généralement pas éligibles comme chef de file.\n"
        "- Types de projets patrimoniaux éligibles : restauration et mise en valeur "
        "transfrontalière du patrimoine bâti, itinéraires culturels transfrontaliers, "
        "numérisation et partage de ressources patrimoniales, formation aux métiers du "
        "patrimoine, tourisme culturel durable, échanges de bonnes pratiques.\n"
        "- Le projet doit démontrer une plus-value de la coopération transfrontalière "
        "ou transnationale (le projet ne pourrait pas être réalisé par un seul partenaire).\n"
        "- Taux de cofinancement FEDER : généralement 60 % à 80 % selon le programme. "
        "Les régions ultrapériphériques (outre-mer) peuvent bénéficier de taux majorés.\n"
        "- Le budget moyen d'un projet Interreg se situe entre 500 000 € et 2 000 000 €, "
        "variable selon les programmes.\n"
        "- Durée des projets : généralement 24 à 36 mois.\n"
        "- Les dépenses éligibles incluent : personnel, frais de déplacement, équipements, "
        "travaux, expertise externe, frais administratifs.\n"
        "- Le cumul avec d'autres fonds européens (FEADER, FSE+) est interdit sur la même dépense.\n"
        "- Obligation de communication sur le soutien de l'UE.\n"
        "- Programmation 2021-2027, avec des appels à projets réguliers jusqu'en 2027."
    ),
    "demarche_description": (
        "1. Identifier le programme Interreg correspondant à votre zone géographique "
        "(transfrontalier, transnational ou interrégional)\n"
        "2. Trouver des partenaires dans le(s) pays voisin(s) participant au programme\n"
        "3. Vérifier la cohérence du projet avec les objectifs spécifiques du programme\n"
        "4. Contacter le secrétariat technique conjoint (STC) du programme pour un avis préalable\n"
        "5. Monter le dossier de candidature avec le partenariat transfrontalier "
        "(description, budget, répartition des tâches, calendrier)\n"
        "6. Déposer le dossier lors d'un appel à projets ouvert\n"
        "7. Évaluation par le comité de sélection et notification"
    ),
    "documents_requis": [
        "Formulaire de candidature du programme Interreg",
        "Accord de partenariat signé par tous les partenaires",
        "Budget détaillé par partenaire et par poste de dépense",
        "Description technique du projet et résultats attendus",
        "Statuts des structures partenaires",
        "Lettres d'engagement des partenaires",
        "Calendrier prévisionnel",
        "Autorisations administratives si travaux (permis, ABF)",
    ],
    "delai_instruction": "4 à 9 mois (selon le programme et le calendrier d'appels à projets)",
    "permanent": False,
    "url_officielle": "https://www.europe-en-france.gouv.fr/fr/programmes-europeens/cooperation-territoriale-europeenne",
    "formulaire_url": None,
    "tags": [
        "Interreg", "Europe", "FEDER", "coopération territoriale",
        "transfrontalier", "patrimoine culturel", "tourisme culturel",
        "2021-2027",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte formelle

# Propriétaires : collectivités, établissements publics, associations
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "public_departement"},
    {"aide_id": aide_id, "proprietaire_code": "public_region"},
    {"aide_id": aide_id, "proprietaire_code": "public_etat"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
    {"aide_id": aide_id, "proprietaire_code": "mixte"},
]).execute()
print("  ✓ Propriétaires éligibles insérés")

# Travaux : restauration, valorisation, études
supabase.table("aides_travaux").insert([
    {"aide_id": aide_id, "travaux_code": "toiture"},
    {"aide_id": aide_id, "travaux_code": "facade"},
    {"aide_id": aide_id, "travaux_code": "maconnerie"},
    {"aide_id": aide_id, "travaux_code": "restauration_generale"},
    {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    {"aide_id": aide_id, "travaux_code": "accessibilite"},
    {"aide_id": aide_id, "travaux_code": "parcs_jardins"},
]).execute()
print("  ✓ Travaux éligibles insérés")

# Régions : toutes les régions frontalières et d'outre-mer → pas de contrainte
# (chaque programme a sa zone, mais presque toute la France est couverte)

# Segments : principalement communes
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "commune"},
]).execute()
print("  ✓ Segments insérés")

print(f"\n✅ Interreg Patrimoine inséré avec succès (id: {aide_id})")
