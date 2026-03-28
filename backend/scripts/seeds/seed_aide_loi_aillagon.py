"""
Seed: Loi Aillagon — Mécénat d'entreprise pour le patrimoine.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_loi_aillagon.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Loi Aillagon — Mécénat d'entreprise pour le patrimoine",
    "nom_court": "Mécénat entreprise (Aillagon)",
    "description": "Réduction d'impôt de 60 % (jusqu'à 90 % pour les trésors nationaux) pour les entreprises qui effectuent des dons en faveur de la restauration du patrimoine monumental.",
    "description_longue": (
        "La loi Aillagon (loi n° 2003-709 du 1er août 2003) constitue le cadre fiscal du "
        "mécénat en France. Elle permet aux entreprises assujetties à l'impôt sur le revenu "
        "ou à l'impôt sur les sociétés de bénéficier d'une réduction d'impôt de 60 % du montant "
        "des dons effectués en faveur d'organismes d'intérêt général à caractère culturel ou "
        "patrimonial, dans la limite de 20 000 € ou 0,5 % du chiffre d'affaires HT (le plus "
        "élevé des deux). Au-delà de 2 M€ de dons annuels, le taux passe à 40 %. Pour les dons "
        "en faveur de l'acquisition de trésors nationaux, le taux monte à 90 %. Les excédents "
        "sont reportables sur les 5 exercices suivants. Ce dispositif est un levier majeur pour "
        "financer la restauration de monuments historiques via des fondations reconnues d'utilité "
        "publique ou des associations agréées."
    ),
    "categorie": "mecenat",
    "type": "mecenat",
    "organisme": "Direction générale des Finances publiques (DGFiP)",
    "montant_max": None,
    "taux_max": 60,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": False,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Entreprises éligibles : toute entreprise assujettie à l'IR (BIC, BNC, BA) ou à l'IS, "
        "quel que soit son régime d'imposition\n"
        "- Réduction d'impôt : 60 % du montant des dons pour la fraction ≤ 2 M€ par exercice\n"
        "- Au-delà de 2 M€ de dons annuels : taux réduit à 40 % (sauf dons aux organismes "
        "d'aide aux personnes en difficulté qui restent à 60 %)\n"
        "- Plafond global : 20 000 € ou 0,5 % du chiffre d'affaires HT, le plus élevé des deux\n"
        "- Report possible de l'excédent sur les 5 exercices suivants\n"
        "- Taux majoré à 90 % pour les dons en faveur de l'achat de trésors nationaux\n"
        "- Organismes bénéficiaires éligibles :\n"
        "  • Fondations reconnues d'utilité publique (FRUP)\n"
        "  • Associations reconnues d'utilité publique (ARUP)\n"
        "  • Organismes d'intérêt général à caractère culturel, éducatif, scientifique "
        "ou concourant à la mise en valeur du patrimoine artistique\n"
        "  • Fondation du patrimoine et ses fondations abritées\n"
        "  • Communes et collectivités (pour travaux sur le patrimoine public)\n"
        "- Conditions de l'organisme bénéficiaire :\n"
        "  • Activité non lucrative\n"
        "  • Gestion désintéressée\n"
        "  • Ne pas fonctionner au profit d'un cercle restreint de personnes\n"
        "- Le don peut prendre la forme : versement en numéraire, don en nature, mécénat "
        "de compétences (mise à disposition de salariés)\n"
        "- Contreparties autorisées dans la limite de 25 % du montant du don "
        "(ex : visibilité du logo, invitations)\n"
        "- L'entreprise doit obtenir un reçu fiscal de l'organisme bénéficiaire\n"
        "- Application directe aux travaux de conservation, restauration ou accessibilité "
        "de monuments historiques classés ou inscrits (art. 238 bis 1° e du CGI)\n"
        "- Les dons à des fondations ou associations agréées subventionnant des travaux MH "
        "ouvrent droit à la réduction dans les mêmes conditions\n"
        "- Les propriétaires de MH peuvent solliciter du mécénat via une fondation ou "
        "association habilitée pour financer leurs travaux de restauration"
    ),
    "demarche_description": (
        "1. Identifier un organisme éligible (fondation RUP, association agréée, Fondation du patrimoine)\n"
        "2. Formaliser le don par une convention de mécénat entre l'entreprise et l'organisme\n"
        "3. L'organisme bénéficiaire délivre un reçu fiscal (cerfa n° 11580)\n"
        "4. L'entreprise impute la réduction d'impôt sur sa déclaration fiscale\n"
        "5. Pour l'IR : reporter sur la déclaration n° 2042 (case 7US)\n"
        "6. Pour l'IS : imputer sur le relevé de solde d'IS\n"
        "7. Conserver le reçu fiscal et la convention de mécénat"
    ),
    "documents_requis": [
        "Convention de mécénat entre l'entreprise et l'organisme bénéficiaire",
        "Reçu fiscal (cerfa n° 11580) délivré par l'organisme",
        "Justificatif du versement (virement, chèque)",
        "Statuts de l'organisme bénéficiaire (pour vérification éligibilité)",
    ],
    "delai_instruction": "Immédiat (déclaration fiscale annuelle)",
    "permanent": True,
    "url_officielle": "https://www.culture.gouv.fr/thematiques/mecenat/qu-est-ce-que-le-mecenat/la-loi-aillagon-inciter-l-engagement-des-particuliers-et-des-entreprises",
    "formulaire_url": None,
    "tags": [
        "mécénat", "loi Aillagon", "entreprise", "réduction d'impôt", "238 bis",
        "fondation", "patrimoine", "restauration", "défiscalisation",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (le mécénat peut financer tous types de biens)
# mais les MH classés/inscrits sont spécifiquement visés par l'art. 238 bis 1° e

# Propriétaires : tous types (le mécénat peut être dirigé vers tout porteur)
# Pas de contrainte → on n'insère rien

# Travaux : pas de contrainte (tous travaux de conservation/restauration)

# Régions : aide nationale → pas de contrainte

# Segments : tous (le mécénat peut bénéficier à tous les segments)

# État de conservation : pas de contrainte

print(f"\n✅ Loi Aillagon — Mécénat d'entreprise inséré avec succès (id: {aide_id})")
