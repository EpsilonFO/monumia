"""
Seed: AGEFIPH — Aide à l'adaptation des situations de travail et accessibilité.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_agefiph.py
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
            "nom": "AGEFIPH — Aide à l'adaptation des situations de travail et accessibilité",
            "nom_court": "AGEFIPH",
            "description": "Aides financières de l'AGEFIPH pour l'aménagement des postes de travail et l'accessibilité des locaux professionnels accueillant des travailleurs handicapés, applicables aux monuments historiques abritant une activité économique.",
            "description_longue": (
                "L'Association de Gestion du Fonds pour l'Insertion Professionnelle des Personnes "
                "Handicapées (AGEFIPH) propose plusieurs aides financières pour les employeurs du "
                "secteur privé qui emploient ou souhaitent employer des personnes en situation de "
                "handicap. Dans le contexte du patrimoine, ces aides sont pertinentes pour les "
                "propriétaires de monuments historiques qui y exercent une activité économique "
                "(hébergement touristique, restaurant, commerce, atelier d'artisan) et doivent "
                "adapter leurs locaux ou postes de travail. L'aide principale est l'Aide à "
                "l'Adaptation des Situations de Travail (AST), qui couvre jusqu'à 100 % des "
                "coûts d'aménagement du poste de travail. L'AGEFIPH propose également l'Aide "
                "à la Lourdeur du Handicap (RLH) pour compenser durablement les surcoûts liés "
                "au handicap d'un salarié, allant de 6 534 € à 13 009 €/an. Ces aides sont "
                "cumulables avec le FTA et le crédit d'impôt accessibilité."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "AGEFIPH (Association de Gestion du Fonds pour l'Insertion Professionnelle des Personnes Handicapées)",
            "montant_max": None,
            "taux_max": 100,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- L'AGEFIPH s'adresse exclusivement aux employeurs du SECTEUR PRIVÉ et aux travailleurs non-salariés handicapés\n"
                "- Les employeurs publics relèvent du FIPHFP (Fonds pour l'Insertion des Personnes Handicapées dans la Fonction Publique)\n"
                "- Aide à l'Adaptation des Situations de Travail (AST) :\n"
                "  • Couvre les frais d'aménagement du poste de travail ou de télétravail pour un salarié handicapé\n"
                "  • Depuis le 1er janvier 2025 : prise en charge possible à 100 % des coûts de compensation du handicap\n"
                "  • Montant déterminé au cas par cas selon les besoins spécifiques identifiés par le médecin du travail\n"
                "  • Dépenses éligibles : équipements spécifiques, logiciels adaptés, tutorat, interprétariat LSF, transcription braille, aménagement du poste\n"
                "  • La préconisation du médecin du travail est OBLIGATOIRE\n"
                "- Aide à la Lourdeur du Handicap (RLH) :\n"
                "  • Compense durablement les surcoûts liés au handicap d'un salarié dans l'exercice de son activité professionnelle\n"
                "  • Montant 2025 : de 6 534 € à 13 008,60 € par an selon le niveau de lourdeur évalué\n"
                "  • Renouvelable tous les 3 ans\n"
                "- Conditions pour le salarié : disposer d'une RQTH (Reconnaissance de la Qualité de Travailleur Handicapé)\n"
                "- Dans le contexte du patrimoine, ces aides peuvent financer :\n"
                "  • L'aménagement d'un poste d'accueil touristique dans un monument pour un salarié handicapé\n"
                "  • L'adaptation d'un atelier d'artisan dans un bâtiment ancien\n"
                "  • L'accessibilité d'un espace de travail dans un monument historique exploité commercialement\n"
                "- L'aide est cumulable avec le FTA, le crédit d'impôt accessibilité PME et les aides régionales\n"
                "- Le demandeur doit être employeur privé ou travailleur indépendant handicapé\n"
                "- Les collectivités territoriales ne sont PAS éligibles à l'AGEFIPH (elles relèvent du FIPHFP)"
            ),
            "demarche_description": (
                "1. Le salarié handicapé doit disposer d'une RQTH en cours de validité\n"
                "2. Consultation du médecin du travail qui établit les préconisations d'aménagement\n"
                "3. Contacter le conseiller AGEFIPH ou Cap emploi pour étudier les solutions\n"
                "4. Constituer le dossier de demande d'aide (AST ou RLH) auprès de l'AGEFIPH\n"
                "5. Instruction par l'AGEFIPH (évaluation des besoins et des coûts)\n"
                "6. Notification de l'aide et réalisation des aménagements\n"
                "7. Envoi des justificatifs pour versement de l'aide"
            ),
            "documents_requis": [
                "Formulaire de demande AGEFIPH (AST ou RLH)",
                "RQTH du salarié en cours de validité",
                "Préconisations du médecin du travail",
                "Devis des équipements ou aménagements",
                "Fiche de poste du salarié",
                "Contrat de travail",
            ],
            "delai_instruction": "1 à 3 mois",
            "permanent": True,
            "url_officielle": "https://www.agefiph.fr/aides-financieres",
            "formulaire_url": "https://www.agefiph.fr/aides-financieres/aide-ladaptation-des-situations-de-travail",
            "tags": [
                "AGEFIPH",
                "handicap",
                "accessibilité",
                "aménagement poste",
                "RQTH",
                "travailleur handicapé",
                "inclusion",
                "adaptation",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : tous niveaux
supabase.table("aides_protections").insert(
    [
        {"aide_id": aide_id, "protection_code": "classe"},
        {"aide_id": aide_id, "protection_code": "inscrit"},
        {"aide_id": aide_id, "protection_code": "non_protege"},
    ]
).execute()
print("  ✓ Protections insérées")

# Propriétaires : secteur privé uniquement
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : accessibilité et aménagement
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "accessibilite"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : nationale

# Segments : privé
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "prive"},
    ]
).execute()
print("  ✓ Segments insérés")

print(f"\n✅ AGEFIPH inséré avec succès (id: {aide_id})")
