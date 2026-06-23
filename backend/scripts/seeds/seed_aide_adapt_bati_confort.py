"""
Seed: Programme Adapt Bâti Confort (CEE) — Rafraîchissement durable des bâtiments.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_adapt_bati_confort.py
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
    supabase.table("aides_v3")
    .insert(
        {
            "nom": "Programme Adapt Bâti Confort — Certificats d'Économie d'Énergie (CEE)",
            "nom_court": "Adapt Bâti Confort",
            "description": "Programme CEE finançant l'adaptation des bâtiments existants aux fortes chaleurs par des solutions passives et sobres en énergie, avec accompagnement technique et financier.",
            "description_longue": (
                "Le programme Adapt Bâti Confort (référence PRO-INFO-58) est un programme financé "
                "par les Certificats d'Économie d'Énergie (CEE), créé par arrêté du 5 août 2025. "
                "Doté de 9 millions d'euros (1,13 TWhcumac) sur 4 ans (2025-2029), il vise à "
                "développer des solutions de rafraîchissement passif et sobre en énergie pour "
                "adapter les bâtiments existants (résidentiels et tertiaires) aux vagues de chaleur. "
                "Le programme est piloté par l'ADEME, le CEREMA et le CSTB. Il sélectionne "
                "50 opérations pilotes à travers la France via un Appel à Manifestation d'Intérêt (AMI), "
                "avec une assistance à maîtrise d'ouvrage (AMO) et un financement des travaux. "
                "Les régions prioritaires sont Provence-Alpes-Côte d'Azur, Occitanie, "
                "Auvergne-Rhône-Alpes et Nouvelle-Aquitaine. Le programme inclut un volet "
                "de formation (500 collectivités, 3 000 professionnels, 300 prescripteurs)."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "ADEME / CEREMA / CSTB (opérateurs de l'État)",
            "montant_max": None,
            "taux_max": None,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Le programme cible les bâtiments existants résidentiels et tertiaires situés "
                "dans les régions les plus exposées au risque de fortes chaleurs.\n"
                "- Régions pilotes prioritaires : Provence-Alpes-Côte d'Azur, Occitanie, "
                "Auvergne-Rhône-Alpes, Nouvelle-Aquitaine. D'autres régions peuvent être "
                "éligibles selon les vagues d'appels.\n"
                "- Le bâtiment doit être un bâtiment existant (pas de construction neuve).\n"
                "- Les solutions financées doivent être passives ou sobres en énergie : "
                "protection solaire (brise-soleil, volets, stores extérieurs), ventilation "
                "naturelle ou mécanique optimisée, isolation thermique, végétalisation, "
                "toitures réfléchissantes, puits climatiques. Les systèmes de climatisation "
                "classiques ne sont pas l'objet principal du programme.\n"
                "- La sélection se fait par Appel à Manifestation d'Intérêt (AMI) sur la "
                "plateforme ADEME. 50 opérations pilotes sont prévues.\n"
                "- Les maîtres d'ouvrage sélectionnés bénéficient d'une AMO (assistance à "
                "maîtrise d'ouvrage) gratuite et d'un financement complémentaire.\n"
                "- Suivi et évaluation multicritères obligatoires (confort thermique, "
                "économies d'énergie, réduction carbone, coût).\n"
                "- Les bâtiments patrimoniaux (monuments historiques) peuvent être éligibles "
                "dès lors qu'ils nécessitent une adaptation au confort d'été, sous réserve "
                "de compatibilité des solutions avec les contraintes patrimoniales.\n"
                "- Programme valable du 8 août 2025 au 31 décembre 2029.\n"
                "- Bénéficiaires : collectivités territoriales, bailleurs sociaux, "
                "copropriétés, gestionnaires de bâtiments tertiaires, propriétaires privés."
            ),
            "demarche_description": (
                "1. Consulter l'Appel à Manifestation d'Intérêt (AMI) sur la plateforme ADEME\n"
                "2. Vérifier l'éligibilité du bâtiment (existant, zone exposée aux fortes chaleurs)\n"
                "3. Préparer le dossier de candidature (description du bâtiment, diagnostic thermique, "
                "solutions envisagées)\n"
                "4. Déposer le dossier sur la plateforme ADEME dans les délais de l'AMI\n"
                "5. Sélection par le comité de pilotage (ADEME/CEREMA/CSTB)\n"
                "6. Mise en place de l'AMO et réalisation des travaux\n"
                "7. Suivi et évaluation sur la durée du programme"
            ),
            "documents_requis": [
                "Diagnostic thermique du bâtiment",
                "Description des solutions de rafraîchissement envisagées",
                "Plan de financement prévisionnel",
                "Autorisations administratives si monument protégé (ABF)",
                "Engagement de participation au suivi et à l'évaluation",
            ],
            "delai_instruction": "3 à 6 mois (selon les vagues d'AMI)",
            "permanent": False,
            "url_officielle": "https://www.ecologie.gouv.fr/presse/lancement-du-programme-adapt-bati-confort-finance-certificats-deconomie-denergie-cee",
            "formulaire_url": None,
            "tags": [
                "CEE",
                "certificats économie énergie",
                "rafraîchissement",
                "confort d'été",
                "adaptation climatique",
                "ADEME",
                "CEREMA",
                "rénovation énergétique",
                "bâtiment existant",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte (MH éligibles aussi)

# Propriétaires : large spectre
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
        {"aide_id": aide_id, "proprietaire_code": "mixte"},
    ]
).execute()
print("  ✓ Propriétaires éligibles insérés")

# Travaux : spécifiques au rafraîchissement et confort thermique
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "protection_solaire"},
        {"aide_id": aide_id, "travaux_code": "ventilation"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    ]
).execute()
print("  ✓ Travaux éligibles insérés")

# Régions : priorité aux 4 régions pilotes mais pas d'exclusion formelle
# On n'insère pas de contrainte régionale pour ne pas exclure d'autres régions

# Segments : tous
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
        {"aide_id": aide_id, "segment_code": "prive"},
    ]
).execute()
print("  ✓ Segments insérés")

print(f"\n✅ Adapt Bâti Confort inséré avec succès (id: {aide_id})")
