"""
Seed: Fonds Friches — Recyclage foncier (Fonds Vert, Axe 3).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_fonds_friches.py
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
            "nom": "Fonds Friches — Recyclage foncier (Fonds Vert, Axe 3)",
            "nom_court": "Fonds Friches",
            "description": "Subvention pour les opérations de recyclage de friches (études, acquisitions foncières, démolition, dépollution, réhabilitation) dont le bilan économique est déficitaire. Intégré au Fonds Vert depuis 2023.",
            "description_longue": (
                "Le Fonds Friches, désormais intégré à l'axe 3 « Recyclage foncier » du Fonds Vert, "
                "soutient les opérations d'aménagement portant sur des fonciers artificialisés dont le bilan "
                "économique est déficitaire. Il finance les études (y compris diagnostics de pollution), "
                "les acquisitions foncières, les travaux de démolition ou déconstruction, de dépollution, "
                "de réhabilitation de bâtiments, de restauration écologique des sols et d'aménagement. "
                "Le fonds est ouvert aux maîtres d'ouvrage publics (collectivités, établissements publics, "
                "EPL, SEM, bailleurs sociaux) et, sous conditions, aux entreprises privées et associations. "
                "L'enveloppe nationale du Fonds Vert est de 1,15 milliard d'euros en 2025. "
                "Les dépenses financées doivent être soldées en 2027. "
                "Ce dispositif peut être mobilisé pour la reconversion de friches patrimoniales "
                "(anciens bâtiments industriels, religieux ou patrimoniaux en déshérence) "
                "en projets de revitalisation incluant la restauration du patrimoine bâti."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "Ministère de la Transition Écologique — Préfectures (DREAL/DDT)",
            "montant_max": None,
            "taux_max": 80,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": True,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Le projet doit porter sur un foncier déjà artificialisé qualifié de friche "
                "(terrain laissé à l'abandon, bâti désaffecté, ancienne zone d'activité, etc.)\n"
                "- Le bilan économique de l'opération doit être déficitaire après prise en compte de "
                "toutes les autres subventions publiques et optimisation des leviers d'équilibre "
                "(densité, mixité programmatique)\n"
                "- La participation minimale de la collectivité maître d'ouvrage est de 20 % "
                "du montant total des financements publics\n"
                "- Le projet doit être suffisamment mature : maîtrise d'ouvrage identifiée, "
                "conditions de maîtrise foncière connues, programmation urbaine définie, "
                "bilan économique de l'opération établi\n"
                "- Porteurs éligibles : collectivités locales, EPCI, établissements publics d'État, "
                "EPL, SEM, bailleurs sociaux, et sous conditions entreprises privées et associations\n"
                "- Dépenses éligibles : études (y compris SSP), acquisitions foncières, "
                "travaux de démolition/déconstruction, dépollution, réhabilitation de bâtiments, "
                "restauration écologique des sols, aménagement\n"
                "- Les dépenses financées doivent être soldées au plus tard en 2027\n"
                "- Les projets de renaturation sont également éligibles\n"
                "- Non éligible : opérations dont le bilan est à l'équilibre ou excédentaire\n"
                "- Le cumul des aides publiques ne peut dépasser 80 % du coût total du projet\n"
                "- Instruction par les préfets de département avec appui des DREAL"
            ),
            "demarche_description": (
                "1. Vérifier que le terrain est qualifiable de friche (foncier artificialisé en déshérence)\n"
                "2. Établir le bilan économique de l'opération démontrant le déficit\n"
                "3. Constituer le dossier de candidature (études préalables, programmation, plan de financement)\n"
                "4. Déposer le dossier auprès de la préfecture de département (DDT/DDTM) ou via la plateforme démarches-simplifiées\n"
                "5. Instruction par les services de l'État (DREAL, DDT)\n"
                "6. Notification de la subvention\n"
                "7. Réaliser les travaux et transmettre les justificatifs de dépenses\n"
                "8. Versement sur présentation des factures acquittées (solde avant fin 2027)"
            ),
            "documents_requis": [
                "Dossier de candidature Fonds Vert - Recyclage foncier",
                "Bilan économique prévisionnel de l'opération (démontrant le déficit)",
                "Études préalables (diagnostic environnemental, étude de pollution SSP si concerné)",
                "Programme d'aménagement ou de revitalisation",
                "Plan de financement détaillé avec cofinancements identifiés",
                "Justificatif de maîtrise foncière ou convention d'acquisition",
                "Devis détaillés des travaux",
                "Délibération de la collectivité approuvant l'opération",
            ],
            "delai_instruction": "3 à 6 mois",
            "permanent": True,
            "url_officielle": "https://www.ecologie.gouv.fr/fonds-vert",
            "formulaire_url": None,
            "tags": [
                "Fonds Friches",
                "Fonds Vert",
                "recyclage foncier",
                "friche",
                "dépollution",
                "réhabilitation",
                "reconversion",
                "aménagement",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (friches protégées ou non)

# Propriétaires : principalement publics mais aussi privés sous conditions
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
print("  ✓ Propriétaires insérés")

# Travaux : démolition, dépollution, réhabilitation, études
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
        {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale → pas de contrainte

# Segments : principalement communes et BTP
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
        {"aide_id": aide_id, "segment_code": "prive"},
        {"aide_id": aide_id, "segment_code": "btp"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ Fonds Friches inséré avec succès (id: {aide_id})")
