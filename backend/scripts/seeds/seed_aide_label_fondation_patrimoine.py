"""
Seed: Dispositif fiscal — Label de la Fondation du patrimoine.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_label_fondation_patrimoine.py
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
            "nom": "Dispositif fiscal — Label de la Fondation du patrimoine",
            "nom_court": "Label Fondation du patrimoine",
            "description": "Déduction fiscale pour les propriétaires privés d'immeubles non protégés au titre des MH, labellisés par la Fondation du patrimoine. Déduction de 50 % à 100 % des travaux extérieurs sur le revenu global.",
            "description_longue": (
                "Le label de la Fondation du patrimoine est un dispositif fiscal permettant aux "
                "propriétaires privés d'immeubles non protégés au titre des monuments historiques — mais "
                "présentant un intérêt patrimonial — de déduire de leur revenu imposable une partie du coût "
                "des travaux de restauration extérieurs. Le bâtiment doit être situé en commune de moins de "
                "20 000 habitants, ou en site classé/protégé. La déduction est de 50 % du montant TTC des "
                "travaux si l'immeuble ne produit aucun revenu, et de 100 % si au moins 20 % du financement "
                "provient de subventions publiques ou de la Fondation du patrimoine. Pour les immeubles "
                "productifs de revenus fonciers, les travaux sont déductibles des revenus fonciers au régime "
                "réel. La Fondation accorde également une aide financière d'au moins 2 % du programme de travaux."
            ),
            "categorie": "fiscalite",
            "type": "deduction_fiscale",
            "organisme": "Fondation du patrimoine",
            "montant_max": None,
            "taux_max": 100,
            "montant_min": None,
            "plancher": None,
            "base_ttc": True,
            "commune_max_population": 20000,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Immeuble NON protégé au titre des monuments historiques (ni classé, ni inscrit)\n"
                "- L'immeuble doit présenter un intérêt patrimonial suffisant, apprécié par la Fondation du patrimoine en lien avec les UDAP (ABF)\n"
                "- Localisation : commune de moins de 20 000 habitants, OU site classé au titre du code de l'environnement, OU site patrimonial remarquable (SPR)\n"
                "- Exception géographique : en site classé ou SPR, la limite de 20 000 habitants ne s'applique pas\n"
                "- Le bâtiment doit être visible de la voie publique (condition de visibilité)\n"
                "- Travaux éligibles : exclusivement travaux extérieurs — façades, toitures, couvertures, menuiseries extérieures, parcs et jardins\n"
                "- Les travaux intérieurs NE SONT PAS éligibles au label\n"
                "- Les travaux doivent être réalisés dans les règles de l'art pour préserver ou restituer l'authenticité du bâtiment\n"
                "- Déduction fiscale pour immeubles non productifs de revenus :\n"
                "  • 50 % du montant TTC des travaux déductibles du revenu global\n"
                "  • 100 % du montant TTC si au moins 20 % du financement provient de subventions publiques ou de la Fondation du patrimoine\n"
                "- Déduction fiscale pour immeubles productifs de revenus fonciers :\n"
                "  • Travaux déductibles des revenus fonciers au régime réel (déduction classique des charges foncières)\n"
                "- Le propriétaire doit conserver le bien pendant au moins 15 ans après l'acquisition\n"
                "- Le label est attribué pour une durée de 3 ans (pour un programme de travaux donné)\n"
                "- La Fondation du patrimoine accorde en plus une aide financière d'au moins 2 % du programme de travaux\n"
                "- Le label doit être obtenu AVANT le début des travaux\n"
                "- Le propriétaire doit être une personne physique (les SCI à l'IS sont exclues)\n"
                "- Les immeubles déjà protégés MH (classés ou inscrits) ne sont pas éligibles au label — ils relèvent du régime fiscal MH\n"
                "- Cumul possible avec les souscriptions publiques de la Fondation du patrimoine\n"
                "- Non cumulable avec le régime fiscal des monuments historiques (art. 156 bis du CGI)"
            ),
            "demarche_description": (
                "1. Vérifier l'éligibilité du bâtiment auprès du délégué régional de la Fondation du patrimoine\n"
                "2. Constituer le dossier : photos, descriptif du bâtiment, programme de travaux envisagés, devis\n"
                "3. Soumettre la demande de label à la Fondation du patrimoine\n"
                "4. La Fondation instruit le dossier en lien avec l'ABF (UDAP)\n"
                "5. Obtenir le label AVANT de commencer les travaux\n"
                "6. Réaliser les travaux conformément au programme validé\n"
                "7. Déduire les travaux de la déclaration de revenus (case 6QW ou revenus fonciers selon le cas)\n"
                "8. Conserver les justificatifs pendant la durée du label + 3 ans"
            ),
            "documents_requis": [
                "Photos du bâtiment (avant travaux)",
                "Descriptif du patrimoine et de son intérêt architectural",
                "Programme détaillé des travaux extérieurs envisagés",
                "Devis des entreprises",
                "Preuve de propriété (acte notarié ou relevé de propriété)",
                "Attestation de non-protection MH",
                "Plan de financement prévisionnel",
            ],
            "delai_instruction": "2 à 4 mois",
            "permanent": True,
            "url_officielle": "https://www.fondation-patrimoine.org/c/soumettre-un-projet/defiscaliser-travaux/232",
            "formulaire_url": None,
            "tags": [
                "Fondation du patrimoine",
                "label",
                "déduction fiscale",
                "travaux extérieurs",
                "patrimoine non protégé",
                "défiscalisation",
                "façade",
                "toiture",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : uniquement non protégé (le label est pour les bâtiments hors MH)
supabase.table("aides_protections").insert(
    [
        {"aide_id": aide_id, "protection_code": "non_protege"},
    ]
).execute()
print("  ✓ Protections insérées")

# Propriétaires : personnes physiques uniquement
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux éligibles : extérieurs uniquement
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "couverture"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "parcs_jardins"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale → pas de contrainte

# Segments : privé uniquement
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "prive"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ Label Fondation du patrimoine inséré avec succès (id: {aide_id})")
