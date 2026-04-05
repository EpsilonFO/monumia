"""
Seed: Éco-PTZ (Éco-Prêt à Taux Zéro).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_eco_ptz.py
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
            "nom": "Éco-PTZ — Éco-Prêt à Taux Zéro pour la rénovation énergétique",
            "nom_court": "Éco-PTZ",
            "description": "Prêt sans intérêts jusqu'à 50 000 € pour financer des travaux de rénovation énergétique. Remboursable sur 15 à 20 ans. Sans condition de ressources.",
            "description_longue": (
                "L'éco-prêt à taux zéro (éco-PTZ) est un prêt sans intérêts accordé par les banques "
                "partenaires pour financer des travaux de rénovation énergétique dans les logements. "
                "Le montant varie de 7 000 € (parois vitrées seules) à 50 000 € (performance énergétique "
                "globale). Le remboursement s'étale sur 15 ans maximum (20 ans pour les rénovations "
                "performantes avec gain ≥ 35 %). Aucune condition de ressources n'est requise. Le logement "
                "doit être achevé depuis au moins 2 ans et constituer une résidence principale. Les travaux "
                "doivent être réalisés par un professionnel RGE et générer un gain d'au moins 2 classes "
                "au DPE. L'éco-PTZ est cumulable avec MaPrimeRénov', les CEE et la TVA à 5,5 %. "
                "Applicable aux monuments historiques à usage d'habitation sous réserve de compatibilité "
                "des travaux avec les contraintes patrimoniales."
            ),
            "categorie": "etat_drac",
            "type": "pret",
            "organisme": "Banques partenaires — Ministère de la Transition Écologique / Ministère de l'Économie",
            "montant_max": 50000,
            "taux_max": None,
            "montant_min": 7000,
            "plancher": None,
            "base_ttc": True,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Prêt à taux zéro (0 % d'intérêts), les intérêts sont pris en charge par l'État\n"
                "- Aucune condition de ressources pour le demandeur\n"
                "- Le demandeur doit être propriétaire occupant ou bailleur du logement\n"
                "- Le logement doit constituer une résidence principale (occupée au moins 8 mois/an)\n"
                "- Le logement doit être achevé depuis au moins 2 ans à la date de début des travaux\n"
                "- Gain minimum de 2 classes énergétiques au DPE requis\n"
                "- Montants maximums selon le type de travaux :\n"
                "  • 7 000 € pour le remplacement de parois vitrées uniquement\n"
                "  • 15 000 € pour un seul type de travaux (hors vitrages)\n"
                "  • 25 000 € pour un bouquet de 2 travaux combinés\n"
                "  • 30 000 € pour 3 travaux ou plus (rénovation globale)\n"
                "  • 50 000 € pour une performance énergétique globale minimale (gain ≥ 35 %)\n"
                "  • 10 000 € pour la réhabilitation d'un assainissement non collectif\n"
                "- Durée de remboursement : 15 ans maximum (20 ans pour performance globale ≥ 35 %)\n"
                "- Travaux éligibles (7 catégories) :\n"
                "  • Isolation thermique de la toiture\n"
                "  • Isolation thermique des murs donnant sur l'extérieur\n"
                "  • Isolation thermique des parois vitrées (fenêtres, portes-fenêtres)\n"
                "  • Isolation thermique des planchers bas\n"
                "  • Installation ou remplacement d'un système de chauffage ou de production d'eau chaude sanitaire\n"
                "  • Installation d'équipements de chauffage utilisant des énergies renouvelables\n"
                "  • Installation d'équipements de production d'eau chaude sanitaire utilisant des énergies renouvelables\n"
                "- Les travaux doivent être réalisés par un professionnel RGE (Reconnu Garant de l'Environnement)\n"
                "- ATTENTION monuments historiques :\n"
                "  • Le logement MH doit avoir un usage d'habitation (résidence principale)\n"
                "  • L'isolation par l'extérieur est souvent incompatible avec les façades protégées\n"
                "  • Le remplacement de fenêtres nécessite l'accord de l'ABF\n"
                "  • Les travaux doivent respecter les prescriptions de l'architecte des bâtiments de France\n"
                "  • Certains travaux éligibles à l'éco-PTZ peuvent être refusés par l'ABF pour des raisons patrimoniales\n"
                "- Un seul éco-PTZ par logement (sauf éco-PTZ complémentaire sous conditions)\n"
                "- Cumul possible avec : MaPrimeRénov', CEE, TVA 5,5 %, aides des collectivités\n"
                "- Le prêt est accordé par les banques ayant signé une convention avec l'État\n"
                "- Le professionnel RGE doit fournir un audit énergétique ou un DPE attestant du gain de classes"
            ),
            "demarche_description": (
                "1. Faire réaliser un audit énergétique ou un DPE pour évaluer les gains attendus\n"
                "2. Obtenir des devis de professionnels RGE pour les travaux envisagés\n"
                "3. Si monument historique : obtenir l'accord de l'ABF ou du CRMH sur les travaux\n"
                "4. Remplir le formulaire « emprunteur » et le formulaire « entreprise » de l'éco-PTZ\n"
                "5. Déposer le dossier auprès d'une banque partenaire ayant signé la convention avec l'État\n"
                "6. Après acceptation, faire réaliser les travaux dans un délai de 3 ans\n"
                "7. Transmettre les factures à la banque pour justifier de la réalisation des travaux"
            ),
            "documents_requis": [
                "Formulaire emprunteur éco-PTZ",
                "Formulaire entreprise éco-PTZ (rempli par le professionnel RGE)",
                "Devis détaillés des travaux",
                "Justificatif de qualification RGE du professionnel",
                "Audit énergétique ou DPE avant travaux",
                "Avis d'imposition",
                "Justificatif de propriété",
                "Attestation de résidence principale",
            ],
            "delai_instruction": "2 à 4 semaines (instruction bancaire)",
            "permanent": True,
            "url_officielle": "https://www.economie.gouv.fr/particuliers/gerer-mon-argent/emprunter-et-sassurer/leco-pret-taux-zero-eco-ptz-pouvez-vous-en-beneficier",
            "formulaire_url": None,
            "tags": [
                "éco-PTZ",
                "prêt taux zéro",
                "rénovation énergétique",
                "isolation",
                "chauffage",
                "banque",
                "RGE",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte (tous bâtiments d'habitation éligibles)

# Propriétaires : privés principalement (prêt bancaire)
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : rénovation énergétique
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "chauffage"},
        {"aide_id": aide_id, "travaux_code": "plomberie"},
        {"aide_id": aide_id, "travaux_code": "ventilation"},
        {"aide_id": aide_id, "travaux_code": "protection_solaire"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Segments : privé uniquement (prêt bancaire)
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "prive"},
    ]
).execute()
print("  ✓ Segments insérés")

# Régions : national → pas de contrainte
# État de conservation : pas de contrainte

print(f"\n✅ Éco-PTZ inséré avec succès (id: {aide_id})")
