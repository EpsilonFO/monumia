"""
Seed: Mécénat de compétences — Patrimoine.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_mecenat_competences.py
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
            "nom": "Mécénat de compétences pour le patrimoine",
            "nom_court": "Mécénat de compétences",
            "description": "Dispositif permettant à une entreprise de mettre gratuitement à disposition ses salariés (artisans, ingénieurs, experts) pour contribuer à la restauration d'un monument historique, avec un avantage fiscal de 60 % du coût salarial.",
            "description_longue": (
                "Le mécénat de compétences est une forme de mécénat en nature définie par la loi "
                "n° 2003-709 du 1er août 2003 (dite loi Aillagon). Il consiste pour une entreprise à "
                "mettre gratuitement à disposition un ou plusieurs de ses salariés, sur leur temps de "
                "travail, au profit d'un organisme d'intérêt général ou d'un propriétaire de monument "
                "historique. Dans le domaine du patrimoine, cela permet à des artisans qualifiés, "
                "ingénieurs, architectes, experts en diagnostic ou en gestion de projet de contribuer "
                "bénévolement à la restauration, l'entretien ou la valorisation d'un monument protégé. "
                "L'entreprise mécène bénéficie d'une réduction d'impôt sur les sociétés égale à 60 % "
                "du coût de revient de la mise à disposition (salaire + charges sociales), dans la limite "
                "de 0,5 % du chiffre d'affaires HT (ou 20 000 € pour les entreprises dont le CA < 4 M€). "
                "La Demeure Historique, agréée par le ministère du Budget depuis 2008, est habilitée à "
                "signer des conventions de mécénat entre entreprises et propriétaires de monuments privés. "
                "Plusieurs grandes entreprises (VINCI, Accenture, Deloitte, etc.) développent des "
                "programmes de mécénat de compétences patrimoine."
            ),
            "categorie": "mecenat",
            "type": "mecenat",
            "organisme": "Entreprises mécènes (via La Demeure Historique, Fondation du patrimoine, ou en direct)",
            "montant_max": None,
            "taux_max": None,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Le mécénat de compétences est un don en nature : l'entreprise met gratuitement à disposition ses salariés sur leur temps de travail\n"
                "- Le monument bénéficiaire doit remplir l'une des conditions suivantes :\n"
                "  • Être classé ou inscrit au titre des Monuments Historiques\n"
                "  • Appartenir à un organisme d'intérêt général (association, fondation, collectivité)\n"
                "  • Être labellisé par la Fondation du patrimoine\n"
                "- Pour les monuments privés protégés MH : le propriétaire doit s'engager à conserver le monument et à l'ouvrir au public pendant au moins 10 ans\n"
                "- L'entreprise mécène bénéficie d'une réduction d'impôt de 60 % du coût de revient (salaire + charges sociales du salarié mis à disposition)\n"
                "- Plafond de la réduction : 0,5 % du CA HT de l'entreprise, ou 20 000 € si le CA est inférieur à 4 M€\n"
                "- Pour les dons supérieurs à 2 M€ par an, le taux de réduction est ramené à 40 % au-delà de ce seuil\n"
                "- L'excédent éventuel de réduction est reportable sur les 5 exercices suivants\n"
                "- Une convention de mécénat doit être signée entre l'entreprise et le bénéficiaire\n"
                "- Un reçu fiscal (cerfa n° 11580) doit être établi par le bénéficiaire\n"
                "- La Demeure Historique peut servir d'intermédiaire agréé pour les conventions de mécénat avec les propriétaires privés de MH\n"
                "- Les compétences mises à disposition peuvent être : artisanat du bâtiment, ingénierie, architecture, diagnostic, gestion de projet, communication, numérique, juridique\n"
                "- Le salarié mis à disposition reste sous contrat avec son entreprise (pas de lien de subordination avec le bénéficiaire)\n"
                "- La durée de mise à disposition est définie par la convention (quelques jours à plusieurs mois)\n"
                "- Le mécénat de compétences est compatible avec d'autres formes de mécénat (financier, en nature) pour le même monument"
            ),
            "demarche_description": (
                "1. Identifier une entreprise disposant de compétences utiles à la restauration du monument\n"
                "2. Contacter l'entreprise ou passer par un intermédiaire (La Demeure Historique, Fondation du patrimoine, plateformes de mécénat)\n"
                "3. Définir ensemble le périmètre de la mission de mécénat de compétences (compétences, durée, objectifs)\n"
                "4. Rédiger et signer une convention de mécénat entre l'entreprise et le bénéficiaire\n"
                "5. Mise à disposition du ou des salariés sur le chantier ou le projet\n"
                "6. Délivrer un reçu fiscal (cerfa n° 11580) à l'entreprise mécène\n"
                "7. L'entreprise déclare le don sur sa déclaration d'IS pour bénéficier de la réduction de 60 %"
            ),
            "documents_requis": [
                "Convention de mécénat de compétences signée",
                "Reçu fiscal (cerfa n° 11580*04)",
                "Description de la mission et des compétences mises à disposition",
                "Justificatif du statut de monument historique (arrêté de classement ou inscription)",
                "Engagement d'ouverture au public pendant 10 ans (si monument privé)",
                "Valorisation du don (coût de revient salarial + charges)",
            ],
            "delai_instruction": "Variable (négociation directe)",
            "permanent": True,
            "url_officielle": "https://www.culture.gouv.fr/thematiques/monuments-sites/acteurs-metiers-formations/les-partenaires/les-mecenes-et-fondations/le-mecenat-sur-les-monuments-historiques",
            "formulaire_url": None,
            "tags": [
                "mécénat de compétences",
                "mécénat en nature",
                "loi Aillagon",
                "réduction d'impôt",
                "entreprise",
                "restauration",
                "artisanat",
                "Demeure Historique",
                "monuments historiques",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : classé et inscrit (MH requis pour les privés, ou label Fondation du patrimoine)
supabase.table("aides_protections").insert(
    [
        {"aide_id": aide_id, "protection_code": "classe"},
        {"aide_id": aide_id, "protection_code": "inscrit"},
    ]
).execute()
print("  ✓ Protections insérées")

# Propriétaires : tous types (conditions différentes selon public/privé)
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : tous types de restauration et entretien
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "couverture"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "vitraux"},
        {"aide_id": aide_id, "travaux_code": "peintures_murales"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "electricite"},
        {"aide_id": aide_id, "travaux_code": "plomberie"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
        {"aide_id": aide_id, "travaux_code": "mobilier"},
        {"aide_id": aide_id, "travaux_code": "parcs_jardins"},
        {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
        {"aide_id": aide_id, "travaux_code": "accessibilite"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : nationale (pas de contrainte)

# Segments : tous segments
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
        {"aide_id": aide_id, "segment_code": "prive"},
        {"aide_id": aide_id, "segment_code": "btp"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ Mécénat de compétences inséré avec succès (id: {aide_id})")
