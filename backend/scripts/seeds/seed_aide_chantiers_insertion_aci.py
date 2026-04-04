"""
Seed: Chantiers d'insertion (Ateliers et Chantiers d'Insertion — ACI).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_chantiers_insertion_aci.py
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
            "nom": "Ateliers et Chantiers d'Insertion (ACI) — Patrimoine",
            "nom_court": "Chantiers d'insertion (ACI)",
            "description": "Dispositif d'insertion par l'activité économique permettant de réaliser des travaux de restauration patrimoniale avec des salariés en parcours d'insertion, financé par l'aide au poste de l'État et le FSE.",
            "description_longue": (
                "Les Ateliers et Chantiers d'Insertion (ACI) sont des structures d'insertion par l'activité "
                "économique (SIAE) conventionnées par l'État qui emploient des personnes très éloignées de "
                "l'emploi dans le cadre de contrats à durée déterminée d'insertion (CDDI). Appliqués au "
                "patrimoine, les ACI réalisent des travaux de restauration sur des monuments et édifices "
                "historiques tout en offrant un parcours d'insertion professionnelle. L'État verse une aide "
                "au poste d'environ 22 536 € par an et par ETP (montant socle 2024, revalorisé chaque année), "
                "cofinancée par le Fonds Social Européen (FSE+). Les ACI patrimoine sont portés par des "
                "associations ou des collectivités et encadrés techniquement par des professionnels qualifiés "
                "du bâtiment ancien. Les salariés en insertion bénéficient d'un accompagnement socioprofessionnel "
                "et peuvent obtenir des certifications (CQP, titres professionnels). Ce dispositif permet de "
                "réduire significativement le coût des travaux de restauration tout en contribuant à la "
                "formation et l'emploi dans les métiers du patrimoine."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "État (DDETS/DREETS) — Fonds Social Européen (FSE+)",
            "montant_max": None,
            "taux_max": None,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Cadre juridique : Code du travail, articles L. 5132-1 à L. 5132-17 (insertion par l'activité économique)\n"
                "- L'ACI doit être une structure conventionnée par l'État (convention pluriannuelle avec la DDETS)\n"
                "- Porteurs éligibles : associations loi 1901, CCAS/CIAS, collectivités territoriales, "
                "établissements publics de coopération intercommunale\n"
                "- Les entreprises privées et personnes physiques ne peuvent PAS porter un ACI\n"
                "- Un propriétaire privé peut bénéficier d'un ACI sur son monument à condition qu'une "
                "structure porteuse agréée (association, collectivité) organise le chantier\n"
                "- Aide au poste socle : environ 22 536 €/an/ETP (montant 2024, revalorisé annuellement)\n"
                "- Aide au poste modulée : part modulée de 0 à 10 % supplémentaire selon les résultats d'insertion\n"
                "- Cofinancement FSE+ : le FSE cofinance l'aide au poste (pas de démarche supplémentaire pour le porteur)\n"
                "- Les salariés en insertion sont embauchés en CDDI (contrat à durée déterminée d'insertion) :\n"
                "  • Durée minimale : 4 mois\n"
                "  • Durée maximale : 24 mois (renouvellements compris)\n"
                "  • Dérogation possible jusqu'à 36 mois pour les 50 ans et plus ou travailleurs handicapés\n"
                "  • Durée hebdomadaire : 20 à 35 heures\n"
                "- Publics éligibles pour l'insertion : personnes agréées par France Travail (ex-Pôle emploi) :\n"
                "  • Demandeurs d'emploi de longue durée (DELD)\n"
                "  • Bénéficiaires du RSA\n"
                "  • Jeunes de moins de 26 ans sans qualification\n"
                "  • Travailleurs handicapés (RQTH)\n"
                "  • Personnes sous main de justice\n"
                "  • Réfugiés et bénéficiaires de la protection subsidiaire\n"
                "- Encadrement technique obligatoire : au moins un encadrant technique par chantier, "
                "qualifié dans les métiers du bâtiment ancien\n"
                "- Accompagnement socioprofessionnel obligatoire : un accompagnateur pour 12 à 15 salariés en insertion\n"
                "- L'ACI ne doit pas faire de concurrence au secteur marchand (principe de non-concurrence)\n"
                "- Les travaux réalisables en ACI patrimoine :\n"
                "  • Maçonnerie traditionnelle (pierre sèche, pierre de taille, mortier de chaux)\n"
                "  • Charpente bois\n"
                "  • Couverture (ardoise, tuile, lauze)\n"
                "  • Enduits à la chaux et badigeons\n"
                "  • Menuiserie bois\n"
                "  • Taille de pierre\n"
                "  • Débroussaillage et entretien des abords\n"
                "  • Travaux préparatoires (échafaudage, nettoyage)\n"
                "- Le monument peut être classé, inscrit MH ou patrimoine non protégé\n"
                "- Pour les MH classés : les travaux doivent être supervisés par un architecte des Bâtiments de France\n"
                "- Le conventionnement de l'ACI est délivré par la DDETS (Direction départementale de l'emploi, "
                "du travail et des solidarités) pour une durée de 3 ans renouvelable"
            ),
            "demarche_description": (
                "1. Identifier ou contacter un ACI existant spécialisé patrimoine dans votre département "
                "(via la DDETS ou le réseau des SIAE)\n"
                "2. Si création d'un ACI : déposer un dossier de conventionnement à la DDETS\n"
                "3. Obtenir l'agrément IAE pour les salariés en insertion (via France Travail)\n"
                "4. Constituer le dossier technique du chantier patrimonial\n"
                "5. Recruter l'encadrant technique et l'accompagnateur socioprofessionnel\n"
                "6. Signer la convention avec la DDETS (aide au poste)\n"
                "7. Lancer le chantier avec les salariés en insertion\n"
                "8. Assurer le suivi socioprofessionnel et les bilans trimestriels\n"
                "9. Transmettre les bilans annuels à la DDETS et au FSE+"
            ),
            "documents_requis": [
                "Convention de l'ACI avec la DDETS",
                "Agrément IAE des salariés en insertion (délivré par France Travail)",
                "Description du projet patrimonial et programme des travaux",
                "Budget prévisionnel du chantier",
                "CV et qualifications de l'encadrant technique",
                "Plan d'accompagnement socioprofessionnel",
                "Autorisation de travaux si monument classé ou inscrit (ABF/DRAC)",
            ],
            "delai_instruction": "2 à 6 mois (conventionnement ACI)",
            "permanent": True,
            "url_officielle": "https://travail-emploi.gouv.fr/emploi-et-insertion/insertion-activite-economique/",
            "formulaire_url": None,
            "tags": [
                "ACI",
                "chantier d'insertion",
                "insertion professionnelle",
                "SIAE",
                "aide au poste",
                "FSE",
                "DDETS",
                "CDDI",
                "métiers du patrimoine",
                "formation",
                "inclusion sociale",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (classé, inscrit, non protégé)

# Propriétaires : porteur = asso ou collectivité, mais bénéficiaire = tous
# On filtre les porteurs d'ACI (pas les propriétaires du monument)
# → pas de contrainte sur les propriétaires (le proprio privé peut bénéficier d'un ACI via une asso)

# Travaux : travaux compatibles avec un ACI
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "couverture"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "parcs_jardins"},
    ]
).execute()

# Régions : aide nationale → pas de contrainte

# Segments : tous segments (commune, privé, BTP)

# État de conservation : pas de contrainte

print(f"\n✅ Chantiers d'insertion (ACI) inséré avec succès (id: {aide_id})")
