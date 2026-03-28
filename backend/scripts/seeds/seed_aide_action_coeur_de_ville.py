"""
Seed: Action Cœur de Ville (ACV).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_action_coeur_de_ville.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Programme Action Cœur de Ville — Volet patrimoine",
    "nom_court": "ACV Patrimoine",
    "description": "Programme national de revitalisation des centres-villes moyens (234 villes), piloté par l'ANCT avec 5 Md€ mobilisés. Financement privilégié pour la restauration du patrimoine en centre-ville via Banque des Territoires, ANAH, Action Logement et dotations État.",
    "description_longue": (
        "Le programme Action Cœur de Ville (ACV), lancé en décembre 2017 et prolongé en ACV 2 à partir "
        "de 2023, vise à revitaliser les centres-villes de 234 villes moyennes françaises. Doté de plus "
        "de 5 milliards d'euros sur la durée du programme, il est piloté par l'ANCT en partenariat avec "
        "la Banque des Territoires, l'ANAH, Action Logement et la DGFIP. Le volet patrimoine d'ACV "
        "permet de financer la restauration et la valorisation du patrimoine bâti en centre-ville : "
        "réhabilitation d'immeubles patrimoniaux, restauration de façades, reconversion de bâtiments "
        "historiques, mise en valeur de l'espace public patrimonial. La Banque des Territoires intervient "
        "via des prêts à taux avantageux (sur 20 à 60 ans) et des investissements en fonds propres. "
        "L'ANAH finance la rénovation de l'habitat dégradé en centre ancien. Action Logement soutient "
        "la réhabilitation de logements. Les communes ACV bénéficient d'un accès prioritaire aux "
        "dotations de l'État (DSIL, DETR, FNADT) et d'un accompagnement renforcé en ingénierie. "
        "Les monuments historiques en centre-ville ACV peuvent cumuler ces financements avec les "
        "subventions DRAC."
    ),
    "categorie": "etat_drac",
    "type": "subvention",
    "organisme": "ANCT / Banque des Territoires / ANAH / Action Logement",
    "montant_max": None,
    "taux_max": 80,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": False,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Communes labellisées Action Cœur de Ville (234 villes moyennes en France + leurs intercommunalités)\n"
        "- Les 234 villes ont été sélectionnées selon des critères de fragilité du centre-ville : vacance commerciale, dégradation de l'habitat, perte de population, éloignement des métropoles\n"
        "- Le périmètre d'intervention est le centre-ville (délimité dans la convention ACV signée avec l'État)\n"
        "- Convention ORT (Opération de Revitalisation de Territoire) obligatoire\n"
        "- ACV 1 (2018-2022) : 5 Md€ mobilisés. ACV 2 (2023-2026) : prolongation et renforcement\n"
        "- Banque des Territoires : prêts sur 20 à 60 ans à taux avantageux, investissements en fonds propres dans des opérations immobilières mixtes\n"
        "- ANAH : subventions pour la rénovation de l'habitat dégradé en centre ancien, copropriétés dégradées, lutte contre l'habitat indigne\n"
        "- Action Logement : investissement dans la réhabilitation de logements, acquisition-amélioration\n"
        "- Dotations État : DSIL, DETR, FNADT avec priorisation pour les projets ACV\n"
        "- 5 axes d'intervention : 1) Réhabilitation et restructuration de l'habitat, 2) Développement économique et commercial, 3) Accessibilité, mobilité et connexions, 4) Mise en valeur des formes urbaines, de l'espace public et du patrimoine, 5) Accès aux équipements et services publics\n"
        "- Les monuments historiques (classés ou inscrits) situés dans le périmètre ACV cumulent les financements ACV avec les subventions DRAC\n"
        "- Travaux éligibles patrimoine : restauration de façades en centre-ville, réhabilitation d'immeubles patrimoniaux, reconversion de bâtiments historiques, mise en valeur de l'espace public patrimonial, rénovation énergétique du bâti ancien\n"
        "- Les propriétaires privés peuvent bénéficier des aides ANAH et Action Logement pour la réhabilitation de logements\n"
        "- Les communes et EPCI sont les bénéficiaires principaux pour les projets d'aménagement et de patrimoine public\n"
        "- Accompagnement renforcé en ingénierie : directeur de projet ACV financé par l'État\n"
        "- Le programme couvre la période 2018-2026 (ACV 1 + ACV 2)"
    ),
    "demarche_description": (
        "1. Vérifier que la commune est labellisée ACV (liste sur le site de l'ANCT)\n"
        "2. Contacter le directeur de projet ACV de la commune\n"
        "3. Inscrire le projet patrimoine dans la convention ORT et le plan d'action ACV\n"
        "4. Solliciter les financements auprès des partenaires : Banque des Territoires (prêts), ANAH (rénovation habitat), Action Logement (logements), préfecture (DSIL/DETR)\n"
        "5. Pour les MH : solliciter la DRAC en parallèle\n"
        "6. Instruction coordonnée par le comité de projet ACV\n"
        "7. Notification et conventionnement\n"
        "8. Réalisation des travaux et versement sur justificatifs"
    ),
    "documents_requis": [
        "Convention ORT signée",
        "Plan d'action ACV de la commune",
        "Délibération du conseil municipal",
        "Programme détaillé des travaux",
        "Devis des entreprises",
        "Plan de financement prévisionnel multi-partenaires",
        "Photos du site et du centre-ville",
        "Diagnostic de centre-ville (si disponible)",
        "Autorisation de travaux (permis, déclaration préalable, autorisation DRAC si MH)",
    ],
    "delai_instruction": "3 à 12 mois",
    "permanent": False,
    "date_ouverture": "2018-01-01",
    "date_limite": "2026-12-31",
    "url_officielle": "https://agence-cohesion-territoires.gouv.fr/action-coeur-de-ville-702",
    "formulaire_url": None,
    "tags": [
        "Action Cœur de Ville", "ACV", "ANCT", "revitalisation",
        "centres-villes", "villes moyennes", "patrimoine urbain",
        "Banque des Territoires", "ANAH",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : tous niveaux y compris non protégé
supabase.table("aides_protections").insert([
    {"aide_id": aide_id, "protection_code": "classe"},
    {"aide_id": aide_id, "protection_code": "inscrit"},
    {"aide_id": aide_id, "protection_code": "non_protege"},
    {"aide_id": aide_id, "protection_code": "spr"},
]).execute()
print("  ✓ Protections insérées")

# Propriétaires : communes, privés, associations
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
    {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
]).execute()
print("  ✓ Propriétaires insérés")

# Travaux : large gamme de restauration et réhabilitation
supabase.table("aides_travaux").insert([
    {"aide_id": aide_id, "travaux_code": "restauration_generale"},
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
    {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
    {"aide_id": aide_id, "travaux_code": "etude_prealable"},
]).execute()
print("  ✓ Travaux insérés")

# Segments : communes et privés
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "commune"},
    {"aide_id": aide_id, "segment_code": "prive"},
]).execute()
print("  ✓ Segments insérés")

# Pas de contrainte régionale (programme national, 234 villes)
# Pas de contrainte département
# Pas de contrainte état de conservation

print(f"\n✅ Aide ACV insérée avec succès (id: {aide_id})")
