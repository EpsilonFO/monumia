"""
Seed: Fondation du patrimoine — Mécénat d'entreprise dirigé.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_mecenat_entreprise_dirige.py
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
            "nom": "Fondation du patrimoine — Mécénat d'entreprise dirigé",
            "nom_court": "Mécénat entreprise dirigé (FdP)",
            "description": "Dispositif permettant à une entreprise de flécher son don via la Fondation du patrimoine vers un monument ou projet patrimonial spécifique, avec réduction d'impôt de 60 %.",
            "description_longue": (
                "La Fondation du patrimoine propose aux entreprises un mécanisme de mécénat dirigé "
                "(ou fléché) : l'entreprise choisit un projet de restauration patrimoniale précis et "
                "effectue son don via la Fondation, qui joue le rôle de tiers de confiance et délivre "
                "le reçu fiscal. Ce dispositif s'appuie sur le cadre fiscal de la loi Aillagon (art. 238 bis "
                "du CGI) et offre une réduction d'impôt de 60 % sur les dons ≤ 2 M€ (40 % au-delà). "
                "L'entreprise peut ainsi soutenir un monument de son territoire, renforcer son ancrage "
                "local et son image tout en bénéficiant d'un avantage fiscal significatif. La Fondation "
                "organise des clubs de mécènes régionaux où les entreprises locales se regroupent pour "
                "financer collectivement des projets patrimoniaux sélectionnés par vote."
            ),
            "categorie": "mecenat",
            "type": "mecenat",
            "organisme": "Fondation du patrimoine",
            "montant_max": None,
            "taux_max": 60,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Mécène : toute entreprise assujettie à l'IR (BIC, BNC, BA) ou à l'IS\n"
                "- Réduction d'impôt : 60 % du montant du don pour la fraction ≤ 2 M€ par exercice\n"
                "- Au-delà de 2 M€ de dons : taux réduit à 40 %\n"
                "- Plafond : 20 000 € ou 0,5 % du chiffre d'affaires HT, le plus élevé des deux\n"
                "- Report de l'excédent sur les 5 exercices suivants\n"
                "- Spécificité du mécénat dirigé : l'entreprise choisit le projet patrimonial bénéficiaire\n"
                "- Le don transite obligatoirement par la Fondation du patrimoine qui délivre le reçu fiscal\n"
                "- Le monument bénéficiaire peut être classé, inscrit ou non protégé\n"
                "- Pour les MH privés protégés : le monument doit être conservé par son propriétaire "
                "et ouvert au public pendant au moins 10 ans (art. 238 bis 1° e du CGI)\n"
                "- Formes de mécénat acceptées :\n"
                "  • Financier (versement en numéraire)\n"
                "  • En nature (don de matériaux, produits, services)\n"
                "  • De compétences (mise à disposition de salariés)\n"
                "- Contreparties limitées : la valeur des contreparties ne doit pas excéder 25 % du don\n"
                "- L'organisme bénéficiaire doit remplir les critères d'intérêt général :\n"
                "  • Gestion désintéressée\n"
                "  • Ne pas fonctionner au profit d'un cercle restreint\n"
                "  • Activité non lucrative\n"
                "- Clubs de mécènes : les entreprises locales peuvent se regrouper au sein de clubs "
                "organisés par la Fondation pour co-financer des projets sélectionnés collectivement\n"
                "- L'entreprise peut valoriser son engagement (logo, communication) dans le respect "
                "de la disproportion marquée entre contreparties et don"
            ),
            "demarche_description": (
                "1. Identifier un projet patrimonial à soutenir (monument, église, patrimoine rural, etc.)\n"
                "2. Contacter la délégation régionale de la Fondation du patrimoine\n"
                "3. Formaliser le don par une convention de mécénat tripartite (entreprise, Fondation, porteur de projet)\n"
                "4. Effectuer le versement auprès de la Fondation du patrimoine\n"
                "5. La Fondation délivre un reçu fiscal (cerfa n° 11580)\n"
                "6. L'entreprise impute la réduction d'impôt sur sa déclaration fiscale (IS ou IR)\n"
                "7. Alternative : rejoindre un club de mécènes local pour co-financer des projets"
            ),
            "documents_requis": [
                "Convention de mécénat (tripartite si mécénat dirigé)",
                "Reçu fiscal (cerfa n° 11580) délivré par la Fondation du patrimoine",
                "Justificatif du versement",
                "Description du projet patrimonial bénéficiaire",
            ],
            "delai_instruction": "Variable selon le projet (convention en quelques semaines)",
            "permanent": True,
            "url_officielle": "https://www.fondation-patrimoine.org/c/s-engager/nous-donner/devenir-mecene/333",
            "formulaire_url": None,
            "tags": [
                "mécénat",
                "entreprise",
                "mécénat dirigé",
                "mécénat fléché",
                "Fondation du patrimoine",
                "réduction d'impôt",
                "238 bis",
                "club de mécènes",
                "patrimoine local",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (le mécénat dirigé peut cibler tout patrimoine)

# Propriétaires : pas de contrainte (tous types de porteurs de projets)

# Travaux : pas de contrainte (tous travaux de restauration/conservation)

# Régions : aide nationale → pas de contrainte

# Segments : tous segments

# État de conservation : pas de contrainte

print(
    f"\n✅ Fondation du patrimoine — Mécénat d'entreprise dirigé inséré avec succès (id: {aide_id})"
)
