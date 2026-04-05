"""
Seed: DETR — Dotation d'Équipement des Territoires Ruraux.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_detr.py
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
            "nom": "DETR — Dotation d'Équipement des Territoires Ruraux",
            "nom_court": "DETR",
            "description": "Dotation de l'État aux communes rurales et EPCI pour financer leurs investissements d'équipement, incluant la réhabilitation du patrimoine bâti communal (mairies, églises, patrimoine non protégé).",
            "description_longue": (
                "La Dotation d'Équipement des Territoires Ruraux (DETR), régie par les articles L.2334-32 "
                "à L.2334-39 du CGCT, est une dotation annuelle de l'État destinée aux communes rurales et "
                "aux EPCI pour financer leurs projets d'investissement. Dotée d'environ 1 milliard d'euros "
                "au niveau national, elle est répartie par département et attribuée par le préfet. La DETR "
                "finance notamment la réhabilitation du patrimoine bâti communal : mairies, écoles, églises "
                "communales (loi 1905), patrimoine rural non protégé présentant un intérêt architectural, "
                "historique ou paysager, mise en sécurité et accessibilité des bâtiments publics. Le taux "
                "de subvention est compris entre 20 et 80 % HT, fixé par la commission départementale "
                "des élus. La DETR ne finance pas les travaux de restauration sur les monuments historiques "
                "classés ou inscrits (compétence DRAC), mais peut financer les travaux d'équipement et de "
                "mise aux normes sur ces bâtiments. Cumulable avec DSIL, Fonds vert, DPV et autres aides."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "État — Préfecture de département",
            "montant_max": None,
            "taux_max": 80,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": 20000,
            "cofinancement_requis": True,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Communes éligibles (métropole) : population ≤ 2 000 hab. (sans condition de potentiel "
                "financier) ou de 2 001 à 20 000 hab. si potentiel financier par habitant ≤ 1,3× la moyenne "
                "des communes de la même strate démographique\n"
                "- Communes éligibles (outre-mer) : ≤ 3 500 hab. (sans condition) ou de 3 501 à 20 000 hab. "
                "sous condition de potentiel financier\n"
                "- EPCI à fiscalité propre : éligibles sauf ceux cumulant les 3 critères : population > 75 000 "
                "hab., commune centre > 20 000 hab. ET densité ≥ 150 hab/km²\n"
                "- Syndicats de communes, syndicats mixtes et PETR également éligibles\n"
                "- Communes nouvelles : éligibles pendant 3 ans après leur création\n"
                "- Taux de subvention : minimum 20 % — maximum 80 % du montant HT des dépenses éligibles\n"
                "- Le taux effectif est fixé par la commission départementale des élus (généralement 20-40 % "
                "pour les projets patrimoine)\n"
                "- Bonus rénovation énergétique : jusqu'à 50 % si réduction de 40 % de la consommation "
                "d'énergie finale\n"
                "- Bonus bois local : jusqu'à 30 % pour charpente, menuiserie, bardage en bois local\n"
                "- Cumul des aides publiques plafonné à 80 % du coût de l'opération\n"
                "- Autofinancement minimum de 20 % par la commune\n"
                "- Projets patrimoine éligibles : réhabilitation de bâtiments communaux, églises communales "
                "(loi 1905), patrimoine rural non protégé d'intérêt architectural/historique/paysager, "
                "mise en sécurité, accessibilité\n"
                "- IMPORTANT : la DETR ne finance PAS les travaux de restauration sur les monuments historiques "
                "classés ou inscrits (compétence DRAC) — elle peut en revanche financer les travaux "
                "d'équipement et de mise aux normes (sécurité, électricité, accessibilité) sur ces bâtiments\n"
                "- Les travaux ne doivent pas avoir commencé avant la réception de l'accusé de réception "
                "de la demande\n"
                "- Projets > 100 000 € soumis à l'avis de la commission départementale\n"
                "- Dépôt uniquement en ligne via Démarches Simplifiées (Démarche Unique Nationale)"
            ),
            "demarche_description": (
                "1. Vérifier l'éligibilité de la commune sur le site de la préfecture du département\n"
                "2. Consulter les catégories d'opérations prioritaires fixées par la commission départementale\n"
                "3. Préparer le dossier : délibération du conseil municipal, devis, plan de financement\n"
                "4. Déposer le dossier en ligne sur Démarches Simplifiées (DUN) avant la date limite "
                "(généralement octobre-janvier pour l'année suivante)\n"
                "5. Instruction par la préfecture ; avis de la commission pour les projets > 100 000 €\n"
                "6. Notification de la subvention au 1er trimestre de l'année de programmation\n"
                "7. Avance de 30 % versée au démarrage des travaux\n"
                "8. Acomptes jusqu'à 80 % sur justificatifs d'avancement\n"
                "9. Solde versé à l'achèvement sur présentation du bilan"
            ),
            "documents_requis": [
                "Formulaire en ligne Démarches Simplifiées (DUN)",
                "Délibération du conseil municipal approuvant le projet et le plan de financement",
                "Devis détaillés d'entreprises ou avant-projet définitif",
                "Plan de financement prévisionnel (toutes sources)",
                "Description technique du projet",
                "Photos de l'état actuel",
                "Attestation de non-commencement des travaux",
                "Justificatif de propriété ou droits d'usage",
                "Audit énergétique (si bonus rénovation énergétique demandé)",
            ],
            "delai_instruction": "3 à 6 mois",
            "permanent": False,
            "url_officielle": "https://www.collectivites-locales.gouv.fr/finances-locales/la-dotation-dequipement-des-territoires-ruraux-detr",
            "formulaire_url": "https://www.demarches-simplifiees.fr/commencer/dotations-etat-investissement-local",
            "tags": [
                "DETR",
                "dotation",
                "commune rurale",
                "EPCI",
                "patrimoine communal",
                "église communale",
                "patrimoine non protégé",
                "préfecture",
                "investissement local",
                "réhabilitation",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : patrimoine non protégé principalement, mais aussi équipement sur MH
supabase.table("aides_protections").insert(
    [
        {"aide_id": aide_id, "protection_code": "non_protege"},
        {"aide_id": aide_id, "protection_code": "abords"},
        {"aide_id": aide_id, "protection_code": "spr"},
        {"aide_id": aide_id, "protection_code": "inscrit"},
        {"aide_id": aide_id, "protection_code": "classe"},
    ]
).execute()
print("  ✓ Protections insérées")

# Propriétaires : collectivités publiques uniquement
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux éligibles : réhabilitation, équipement, mise aux normes
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "couverture"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "electricite"},
        {"aide_id": aide_id, "travaux_code": "plomberie"},
        {"aide_id": aide_id, "travaux_code": "chauffage"},
        {"aide_id": aide_id, "travaux_code": "accessibilite"},
        {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "ventilation"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale → pas de contrainte

# Segments : communes uniquement
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ DETR inséré avec succès (id: {aide_id})")
