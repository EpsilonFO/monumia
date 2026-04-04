"""
Seed: Aides des Parcs Naturels Régionaux (PNR) à la restauration du patrimoine bâti.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_pnr.py
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
            "nom": "Aides des Parcs Naturels Régionaux à la restauration du patrimoine bâti",
            "nom_court": "Aide PNR patrimoine bâti",
            "description": "Subventions des PNR pour la restauration du petit patrimoine bâti vernaculaire (lavoirs, moulins, fontaines, façades, toitures) situé sur leur territoire.",
            "description_longue": (
                "Les Parcs Naturels Régionaux (PNR) proposent des aides financières pour la restauration "
                "du patrimoine bâti vernaculaire et remarquable situé sur leur territoire. Ces aides "
                "concernent principalement le petit patrimoine non protégé au titre des monuments "
                "historiques : lavoirs, fontaines, moulins, murs en pierre, calvaires, toitures et "
                "façades traditionnelles. Le montant maximum est généralement de 10 000 € pour les "
                "collectivités et de 5 000 € pour les particuliers, limité à un dossier par commune "
                "ou par propriétaire et par an. Les interventions sont encadrées par des conventions "
                "avec la Fondation du patrimoine et les Maisons Paysannes de France. Les PNR peuvent "
                "aussi mobiliser des fonds régionaux et départementaux en complément. Chaque PNR ayant "
                "ses propres critères, il convient de se rapprocher du Parc concerné."
            ),
            "categorie": "region",
            "type": "subvention",
            "organisme": "Parcs Naturels Régionaux (PNR)",
            "montant_max": 10000,
            "taux_max": 50,
            "montant_min": None,
            "plancher": None,
            "base_ttc": True,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Le bâtiment doit être situé sur le territoire d'un Parc Naturel Régional\n"
                "- Patrimoine éligible : petit patrimoine bâti vernaculaire non protégé au titre des MH — "
                "lavoirs, fontaines, moulins à eau, puits, petits ponts, murs en pierre, calvaires, "
                "croix, pigeonniers, fours à pain, séchoirs, granges\n"
                "- Les toitures et façades de bâtiments patrimoniaux traditionnels sont aussi éligibles\n"
                "- Montant maximum : 10 000 € pour les collectivités, 5 000 € pour les particuliers "
                "(variable selon les PNR)\n"
                "- Limité à un dossier par commune et par an, ou un dossier par propriétaire privé et par an\n"
                "- Les travaux doivent respecter les techniques et matériaux traditionnels du territoire\n"
                "- Le PNR peut exiger un conseil architectural préalable auprès du CAUE ou de l'ABF\n"
                "- Pour les biens privés : convention entre le propriétaire et le PNR stipulant :\n"
                "  • Visite en extérieur du lieu financé lors des Journées du Patrimoine pendant 5 ans\n"
                "  • Affichage de l'aide du Parc pendant et après les travaux\n"
                "- Les travaux ne doivent pas avoir commencé avant l'accord de subvention\n"
                "- Chaque PNR a ses propres critères détaillés — se rapprocher du Parc concerné\n"
                "- Certains PNR ciblent des éléments spécifiques (ex : patrimoine hydraulique, patrimoine agropastoral)\n"
                "- Les projets portés en partenariat avec la Fondation du patrimoine ou les Maisons "
                "Paysannes de France sont souvent prioritaires"
            ),
            "demarche_description": (
                "1. Vérifier que le bâtiment est situé sur le territoire d'un PNR\n"
                "2. Contacter le chargé de mission patrimoine bâti du PNR concerné\n"
                "3. Obtenir un conseil architectural (CAUE ou architecte du PNR)\n"
                "4. Constituer le dossier : photos, descriptif, devis, plan de financement\n"
                "5. Soumettre la demande au PNR avant le début des travaux\n"
                "6. Attendre l'accord de la commission d'attribution\n"
                "7. Réaliser les travaux conformément aux prescriptions\n"
                "8. Transmettre les factures pour le versement de la subvention"
            ),
            "documents_requis": [
                "Photos du bâtiment (avant travaux)",
                "Descriptif de l'élément patrimonial et de son intérêt",
                "Devis détaillés des entreprises (matériaux traditionnels)",
                "Plan de financement prévisionnel",
                "Preuve de propriété ou délibération communale",
                "Avis du CAUE ou de l'architecte du PNR (si requis)",
            ],
            "delai_instruction": "2 à 4 mois",
            "permanent": True,
            "url_officielle": "https://www.parcs-naturels-regionaux.fr/",
            "formulaire_url": None,
            "tags": [
                "PNR",
                "Parc Naturel Régional",
                "petit patrimoine",
                "patrimoine vernaculaire",
                "restauration",
                "lavoirs",
                "fontaines",
                "pierre",
                "toiture traditionnelle",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : principalement non protégé, mais peut inclure abords/SPR
supabase.table("aides_protections").insert(
    [
        {"aide_id": aide_id, "protection_code": "non_protege"},
        {"aide_id": aide_id, "protection_code": "abords"},
        {"aide_id": aide_id, "protection_code": "spr"},
    ]
).execute()
print("  ✓ Protections insérées")

# Propriétaires : collectivités et privés
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux éligibles : restauration extérieure et petit patrimoine
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "couverture"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale (tous les PNR) → pas de contrainte

# Segments : communes et privés
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
        {"aide_id": aide_id, "segment_code": "prive"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ Aide PNR patrimoine bâti insérée avec succès (id: {aide_id})")
