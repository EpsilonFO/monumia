"""
Seed: OPCO et formation professionnelle — Métiers du patrimoine.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_opco_formation.py
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
            "nom": "OPCO et formation professionnelle — Métiers du patrimoine bâti",
            "nom_court": "OPCO Formation patrimoine",
            "description": "Financement par les OPCO (Constructys, AFDAS, etc.) de formations professionnelles aux métiers du patrimoine bâti : taille de pierre, charpente, couverture, maçonnerie ancienne, enduits à la chaux.",
            "description_longue": (
                "Les Opérateurs de Compétences (OPCO) financent la formation professionnelle des salariés "
                "et des alternants dans les métiers du patrimoine bâti. Constructys (OPCO de la construction) "
                "est le principal financeur pour les entreprises du bâtiment intervenant sur le patrimoine. "
                "L'AFDAS couvre les métiers de la culture et des industries créatives. Les OPCO prennent en "
                "charge les coûts pédagogiques, les salaires pendant la formation et les frais annexes "
                "(déplacement, hébergement) pour plusieurs dispositifs : plan de développement des compétences, "
                "contrat de professionnalisation, contrat d'apprentissage, Pro-A (reconversion ou promotion "
                "par alternance), CPF de transition professionnelle. Les formations éligibles couvrent "
                "les métiers traditionnels du patrimoine : taille de pierre, charpente bois, couverture "
                "(ardoise, tuile, lauze, chaume), maçonnerie de pierre, enduits à la chaux, ferronnerie d'art, "
                "vitrail, restauration de peintures murales, etc. Les entreprises de moins de 50 salariés "
                "bénéficient d'une prise en charge renforcée. Ce dispositif permet aux entreprises du BTP "
                "spécialisées patrimoine de former leurs salariés aux techniques traditionnelles et de recruter "
                "des alternants qualifiés."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "OPCO Constructys / AFDAS / autres OPCO",
            "montant_max": None,
            "taux_max": 100,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Dispositif destiné aux entreprises et artisans du BTP intervenant sur le patrimoine bâti\n"
                "- OPCO principal : Constructys (OPCO de la construction, BTP et négoce de matériaux)\n"
                "- Autres OPCO concernés : AFDAS (culture, industries créatives), OPCO EP (entreprises de proximité/artisans)\n"
                "- Dispositifs de financement disponibles :\n"
                "  • Plan de développement des compétences : prise en charge des formations courtes "
                "et longues pour les salariés (100 % pour les entreprises < 50 salariés)\n"
                "  • Contrat de professionnalisation : alternance (16-25 ans ou demandeurs d'emploi 26+), "
                "prise en charge des coûts de formation + aide à l'embauche\n"
                "  • Contrat d'apprentissage : alternance (16-29 ans), financement selon le niveau de prise "
                "en charge (NPEC) défini par France Compétences\n"
                "  • Pro-A (reconversion ou promotion par alternance) : pour les salariés en CDI, "
                "niveau de qualification < licence, prise en charge des coûts de formation\n"
                "  • CPF de transition professionnelle (ex-CIF) : pour les salariés souhaitant une reconversion, "
                "financé par Transitions Pro\n"
                "- Formations patrimoine éligibles :\n"
                "  • CAP/BP/BMA Tailleur de pierre\n"
                "  • CAP/BP Charpentier bois\n"
                "  • CAP/BP Couvreur\n"
                "  • CAP/BP Maçon (option patrimoine bâti ancien)\n"
                "  • CAP Staffeur ornemaniste\n"
                "  • BMA Ferronnerie d'art\n"
                "  • CAP/BMA Vitrailliste\n"
                "  • CQP Ouvrier professionnel en restauration du patrimoine\n"
                "  • Titre professionnel Maçon du bâti ancien\n"
                "  • Formations courtes : enduits à la chaux, techniques de pierre sèche, "
                "charpente traditionnelle, couverture en lauze/ardoise\n"
                "- Conditions d'éligibilité entreprise :\n"
                "  • Être à jour de ses cotisations formation professionnelle\n"
                "  • Être rattachée à un OPCO (automatique selon le code NAF/APE)\n"
                "  • Les entreprises < 50 salariés bénéficient d'une prise en charge renforcée\n"
                "  • Les entreprises < 11 salariés (TPE) ont un accès prioritaire\n"
                "- Montants de prise en charge (Constructys, indicatifs) :\n"
                "  • Plan de formation : jusqu'à 40 €/h (coûts pédagogiques), plafonné selon la taille de l'entreprise\n"
                "  • Apprentissage : selon le NPEC (6 000 à 12 000 €/an selon le diplôme)\n"
                "  • Contrat de professionnalisation : 15 à 25 €/h selon le diplôme visé\n"
                "- Aide exceptionnelle à l'embauche d'un alternant : 6 000 € la première année "
                "(dispositif reconduit sous conditions)\n"
                "- Ce dispositif ne finance pas directement des travaux mais la formation des professionnels "
                "qui réaliseront les travaux sur le patrimoine"
            ),
            "demarche_description": (
                "1. Identifier l'OPCO de rattachement de l'entreprise (Constructys pour le BTP)\n"
                "2. Consulter le catalogue de formations éligibles sur le site de l'OPCO\n"
                "3. Choisir le dispositif adapté (plan de formation, alternance, Pro-A, CPF transition)\n"
                "4. Sélectionner un organisme de formation certifié Qualiopi\n"
                "5. Déposer la demande de prise en charge sur l'espace employeur de l'OPCO\n"
                "6. Obtenir l'accord de financement de l'OPCO\n"
                "7. Inscrire le salarié/alternant à la formation\n"
                "8. Transmettre les justificatifs (attestation de présence, facture) pour le remboursement"
            ),
            "documents_requis": [
                "Demande de prise en charge (formulaire OPCO)",
                "Devis ou convention de formation de l'organisme certifié Qualiopi",
                "Programme détaillé de la formation",
                "Contrat de travail du salarié ou contrat d'alternance",
                "Attestation de présence en formation",
                "Facture de l'organisme de formation",
            ],
            "delai_instruction": "2 à 4 semaines (accord de prise en charge)",
            "permanent": True,
            "url_officielle": "https://www.constructys.fr",
            "formulaire_url": None,
            "tags": [
                "OPCO",
                "Constructys",
                "AFDAS",
                "formation professionnelle",
                "apprentissage",
                "alternance",
                "métiers du patrimoine",
                "taille de pierre",
                "charpente",
                "couverture",
                "maçonnerie",
                "BTP",
                "CQP",
                "Pro-A",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (les formations s'appliquent à tout type de patrimoine)

# Propriétaires : pas de contrainte (ce sont les entreprises du BTP qui en bénéficient)

# Travaux : métiers du patrimoine bâti
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "couverture"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "vitraux"},
        {"aide_id": aide_id, "travaux_code": "peintures_murales"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
    ]
).execute()

# Régions : aide nationale → pas de contrainte

# Segments : principalement BTP
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "btp"},
    ]
).execute()

# État de conservation : pas de contrainte

print(f"\n✅ OPCO et formation professionnelle inséré avec succès (id: {aide_id})")
