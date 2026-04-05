"""
Seed: FNADT — Fonds National d'Aménagement et de Développement du Territoire.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_fnadt.py
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
            "nom": "Fonds National d'Aménagement et de Développement du Territoire (FNADT)",
            "nom_court": "FNADT",
            "description": "Fonds de l'État finançant des projets structurants d'aménagement du territoire, incluant la valorisation du patrimoine dans le cadre de démarches contractuelles (CPER, Petites Villes de Demain, etc.).",
            "description_longue": (
                "Le Fonds National d'Aménagement et de Développement du Territoire (FNADT), créé par la "
                "loi du 4 février 1995 (loi Pasqua), est un instrument financier de l'État destiné à soutenir "
                "les projets d'aménagement du territoire. Il se compose de deux sections : une section "
                "générale décidée au niveau national et une section locale contractualisée dans le cadre "
                "des Contrats de Plan État-Région (CPER). Le FNADT peut financer des projets de "
                "valorisation du patrimoine historique lorsqu'ils s'inscrivent dans une démarche territoriale "
                "globale : revitalisation de centres-bourgs, développement touristique, programmes Petites "
                "Villes de Demain ou Action Cœur de Ville. Les crédits de la section locale sont déconcentrés "
                "auprès des préfets de région (SGAR). Le taux de subvention varie généralement de 20 % "
                "à 50 % du coût éligible."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "ANCT / Préfecture de région (SGAR)",
            "montant_max": None,
            "taux_max": 50,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": True,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Bénéficiaires : collectivités territoriales, EPCI, associations, établissements publics\n"
                "- Les propriétaires privés (personnes physiques, SCI) ne sont PAS éligibles directement\n"
                "- Le projet doit s'inscrire dans une démarche contractuelle ou un programme national :\n"
                "  • Contrat de Plan État-Région (CPER) — section locale\n"
                "  • Programme Petites Villes de Demain\n"
                "  • Programme Action Cœur de Ville\n"
                "  • Contrat de Relance et de Transition Écologique (CRTE)\n"
                "  • Contrats de ruralité\n"
                "- Deux sections distinctes :\n"
                "  • Section générale : projets d'envergure nationale ou interrégionale, décidée par le Premier ministre\n"
                "  • Section locale (CPER) : projets régionaux, crédits délégués aux préfets de région\n"
                "- Pour le patrimoine : le projet doit avoir une dimension d'aménagement du territoire (revitalisation, attractivité, tourisme)\n"
                "- Taux de subvention en pratique : 20 % à 50 % du coût éligible du projet\n"
                "- Le cofinancement est requis : le FNADT ne peut pas être la seule source de financement\n"
                "- Cumul possible avec DETR, DSIL, FEDER, aides régionales dans la limite des règles d'aides publiques\n"
                "- Les études préalables (ingénierie, diagnostic) sont également éligibles\n"
                "- Le calendrier et les priorités varient selon la programmation CPER en cours et les orientations régionales\n"
                "- La section locale dépend des enveloppes inscrites dans le CPER de chaque région"
            ),
            "demarche_description": (
                "1. Prendre contact avec la préfecture de région (SGAR) ou la sous-préfecture pour vérifier l'éligibilité\n"
                "2. Vérifier que le projet s'inscrit dans le cadre du CPER ou d'un programme national éligible\n"
                "3. Constituer le dossier de demande de subvention\n"
                "4. Déposer le dossier auprès du SGAR (section locale) ou de l'ANCT (section générale)\n"
                "5. Instruction par les services de l'État\n"
                "6. Décision du préfet de région (section locale) ou du Premier ministre (section générale)\n"
                "7. Notification de la subvention et convention\n"
                "8. Versement par tranches sur justificatifs"
            ),
            "documents_requis": [
                "Délibération de la collectivité ou décision de l'organe compétent",
                "Description détaillée du projet et note de présentation",
                "Plan de financement prévisionnel",
                "Devis ou estimations des travaux",
                "Calendrier prévisionnel de réalisation",
                "Justificatifs de la maîtrise foncière",
                "Rattachement au CPER ou à un programme national (le cas échéant)",
            ],
            "delai_instruction": "3 à 9 mois",
            "permanent": True,
            "url_officielle": "https://anct.gouv.fr",
            "formulaire_url": None,
            "tags": [
                "FNADT",
                "aménagement du territoire",
                "CPER",
                "ANCT",
                "revitalisation",
                "centres-bourgs",
                "patrimoine territorial",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : tous niveaux (le patrimoine non protégé peut être éligible dans le cadre FNADT)
supabase.table("aides_protections").insert(
    [
        {"aide_id": aide_id, "protection_code": "classe"},
        {"aide_id": aide_id, "protection_code": "inscrit"},
        {"aide_id": aide_id, "protection_code": "non_protege"},
    ]
).execute()
print("  ✓ Protections insérées")

# Propriétaires : collectivités et associations
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : restauration et valorisation
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "couverture"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "accessibilite"},
        {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale → pas de contrainte

# Segments : communes et associations
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ FNADT inséré avec succès (id: {aide_id})")
