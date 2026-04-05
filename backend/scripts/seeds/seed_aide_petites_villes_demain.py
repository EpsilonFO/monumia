"""
Seed: Petites Villes de Demain (PVD).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_petites_villes_demain.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = (
    supabase.table("aides_v2")
    .insert(
        {
            "nom": "Programme Petites Villes de Demain — Volet patrimoine",
            "nom_court": "PVD Patrimoine",
            "description": "Programme national de revitalisation des petites centralités (< 20 000 hab.), piloté par l'ANCT, avec financement d'ingénierie et accès prioritaire aux dotations de l'État (DSIL, DETR, Fonds Friches) pour la restauration du patrimoine communal.",
            "description_longue": (
                "Le programme Petites Villes de Demain (PVD), lancé en octobre 2020 pour la période 2020-2026, "
                "est piloté par l'Agence Nationale de la Cohésion des Territoires (ANCT). Il concerne environ "
                "1 600 communes de moins de 20 000 habitants exerçant des fonctions de centralité. Le programme "
                "n'apporte pas directement de subvention travaux mais offre un cadre privilégié d'accès aux "
                "financements existants : DSIL (Dotation de Soutien à l'Investissement Local), DETR (Dotation "
                "d'Équipement des Territoires Ruraux), Fonds Friches, prêts Banque des Territoires. Les communes "
                "PVD bénéficient d'un financement d'ingénierie (chef de projet à 75 % pris en charge par l'État, "
                "environ 45 000 €/an) et d'une priorisation dans l'attribution des dotations. Le volet patrimoine "
                "couvre la restauration de bâtiments communaux patrimoniaux, la rénovation de centres-bourgs "
                "historiques, la mise en valeur du patrimoine (éclairage, signalétique, parcours), les travaux de "
                "mise en sécurité et d'accessibilité, et la rénovation énergétique de bâtiments anciens. Les "
                "communes PVD peuvent cumuler ces aides avec les subventions DRAC pour les monuments historiques."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "ANCT / Banque des Territoires / Préfectures",
            "montant_max": None,
            "taux_max": 80,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": 20000,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Communes labellisées Petites Villes de Demain (environ 1 600 communes en France)\n"
                "- Population inférieure à 20 000 habitants, exerçant des fonctions de centralité (pôle de services, bassin de vie)\n"
                "- La commune doit avoir signé une convention ORT (Opération de Revitalisation de Territoire) ou un plan d'action PVD\n"
                "- Les communes ont été désignées par les préfets et présidents d'intercommunalité au lancement du programme (pas d'appel à candidatures ouvert)\n"
                "- Financement d'ingénierie : chef de projet PVD pris en charge à 75 % par l'État (environ 45 000 €/an)\n"
                "- DSIL : taux variable, généralement 20 à 80 % du coût du projet, avec bonus prioritaire pour les communes PVD\n"
                "- DETR : plafond variable par département, taux jusqu'à 80 % pour les petites communes\n"
                "- Fonds Friches : réhabilitation de friches patrimoniales\n"
                "- Banque des Territoires : prêts à taux avantageux (prêts « Gaïa » sur 20-40 ans à taux préférentiel)\n"
                "- Les monuments historiques (classés ou inscrits) dans les communes PVD cumulent les aides PVD avec les subventions DRAC\n"
                "- Les travaux sur MH doivent être réalisés sous contrôle de l'ABF (inscrits) ou de l'ACMH (classés)\n"
                "- Travaux éligibles : restauration bâtiments communaux patrimoniaux, rénovation centres-bourgs historiques, mise en valeur (éclairage, signalétique, parcours), mise en sécurité, accessibilité, rénovation énergétique compatible\n"
                "- Partenaires financeurs : ANCT, Banque des Territoires, ANAH (habitat/rénovation énergétique), DRAC, Action Logement, CEREMA, Régions, Départements\n"
                "- Le programme couvre la période 2020-2026 (prolongation possible)\n"
                "- Seules les communes publiques sont éligibles (pas les propriétaires privés directement)"
            ),
            "demarche_description": (
                "1. Vérifier que la commune est labellisée PVD sur petitevillesdedemain.anct.gouv.fr\n"
                "2. Contacter le chef de projet PVD de la commune ou de l'intercommunalité\n"
                "3. Inscrire le projet patrimoine dans la convention ORT ou le plan d'action PVD\n"
                "4. Solliciter les dotations de l'État (DSIL, DETR) via la préfecture\n"
                "5. Contacter la Banque des Territoires pour les prêts avantageux\n"
                "6. Pour les MH : solliciter également la DRAC (subvention complémentaire)\n"
                "7. Instruction par les services de l'État\n"
                "8. Notification et versement sur justificatifs"
            ),
            "documents_requis": [
                "Convention ORT ou plan d'action PVD signé",
                "Délibération du conseil municipal",
                "Programme détaillé des travaux",
                "Devis des entreprises",
                "Plan de financement prévisionnel",
                "Photos du site avant travaux",
                "Autorisation de travaux (permis, déclaration préalable, autorisation DRAC)",
                "Diagnostic patrimonial (si disponible)",
            ],
            "delai_instruction": "3 à 9 mois",
            "permanent": False,
            "date_ouverture": "2020-10-01",
            "date_limite": "2026-12-31",
            "url_officielle": "https://petitevillesdedemain.anct.gouv.fr",
            "formulaire_url": None,
            "tags": [
                "Petites Villes de Demain",
                "PVD",
                "ANCT",
                "revitalisation",
                "centres-bourgs",
                "patrimoine communal",
                "DSIL",
                "DETR",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : tous niveaux y compris non protégé (patrimoine communal)
supabase.table("aides_protections").insert(
    [
        {"aide_id": aide_id, "protection_code": "classe"},
        {"aide_id": aide_id, "protection_code": "inscrit"},
        {"aide_id": aide_id, "protection_code": "non_protege"},
    ]
).execute()
print("  ✓ Protections insérées")

# Propriétaires : communes uniquement
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : large gamme
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "couverture"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "vitraux"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "electricite"},
        {"aide_id": aide_id, "travaux_code": "plomberie"},
        {"aide_id": aide_id, "travaux_code": "chauffage"},
        {"aide_id": aide_id, "travaux_code": "accessibilite"},
        {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Segments : communes uniquement
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
    ]
).execute()
print("  ✓ Segments insérés")

# Pas de contrainte régionale (programme national)
# Pas de contrainte département
# Pas de contrainte état de conservation

print(f"\n✅ Aide PVD insérée avec succès (id: {aide_id})")
