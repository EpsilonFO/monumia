"""
Seed: Agences de l'eau — Aides aux collectivités (12e programme 2025-2030).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_agences_eau.py
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
            "nom": "Agences de l'eau — Aides à la gestion de l'eau et des milieux aquatiques (12e programme 2025-2030)",
            "nom_court": "Agences de l'eau",
            "description": "Subventions des agences de l'eau pour les travaux liés à la gestion des eaux pluviales, la restauration de zones humides, l'assainissement et la sobriété hydrique sur le patrimoine bâti des collectivités.",
            "description_longue": (
                "Les six agences de l'eau (Adour-Garonne, Artois-Picardie, Loire-Bretagne, Rhin-Meuse, "
                "Rhône-Méditerranée-Corse, Seine-Normandie) disposent de programmes d'intervention pluriannuels "
                "pour soutenir les projets liés à la gestion de l'eau. Le 12e programme (2025-2030) mobilise "
                "plus de 2 milliards d'euros par an. Les collectivités propriétaires de patrimoine bâti peuvent "
                "bénéficier d'aides pour : la gestion intégrée des eaux pluviales (déconnexion, infiltration, "
                "récupération), la restauration de zones humides à proximité de monuments ou parcs historiques, "
                "l'assainissement et la mise aux normes des réseaux, la sobriété hydrique des bâtiments publics. "
                "Les taux de subvention varient de 30 à 80 % selon l'agence, le type de projet et les priorités "
                "du bassin. Les Solutions Fondées sur la Nature (SFN) sont particulièrement encouragées."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "Agences de l'eau (Adour-Garonne, Artois-Picardie, Loire-Bretagne, Rhin-Meuse, RMC, Seine-Normandie)",
            "montant_max": None,
            "taux_max": 80,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- L'aide est attribuée par l'agence de l'eau du bassin hydrographique où se situe le projet\n"
                "- Six agences couvrent le territoire : Adour-Garonne, Artois-Picardie, Loire-Bretagne, "
                "Rhin-Meuse, Rhône-Méditerranée-Corse, Seine-Normandie\n"
                "- Chaque agence a ses propres critères et taux, définis dans son programme d'intervention\n"
                "- Porteurs éligibles : communes, EPCI, syndicats d'eau, établissements publics, associations\n"
                "- Types de projets éligibles en lien avec le patrimoine bâti :\n"
                "  • Gestion intégrée des eaux pluviales (déconnexion des réseaux, noues, bassins d'infiltration)\n"
                "  • Récupération et réutilisation des eaux de pluie sur bâtiments publics\n"
                "  • Restauration de zones humides (y compris dans les parcs et jardins historiques)\n"
                "  • Assainissement non collectif ou collectif (mise aux normes)\n"
                "  • Sobriété hydrique des bâtiments publics patrimoniaux\n"
                "- Taux de subvention : de 30 % à 80 % selon l'agence et la nature du projet\n"
                "- Les Solutions Fondées sur la Nature (SFN) bénéficient de taux majorés\n"
                "- Les projets situés en zone de captage prioritaire ou en territoire vulnérable sont priorisés\n"
                "- Les « contrats eau et climat » signés avec l'agence facilitent l'accès aux aides\n"
                "- Non éligible : travaux sans lien avec la gestion de l'eau ou des milieux aquatiques\n"
                "- Le projet doit respecter la réglementation en vigueur (code de l'environnement)"
            ),
            "demarche_description": (
                "1. Identifier l'agence de l'eau compétente pour votre bassin hydrographique\n"
                "2. Consulter le programme d'intervention de l'agence et les appels à projets en cours\n"
                "3. Prendre contact avec la délégation territoriale de l'agence pour présenter le projet\n"
                "4. Constituer le dossier de demande de subvention (formulaire de l'agence)\n"
                "5. Joindre les études techniques, devis et plan de financement\n"
                "6. Déposer le dossier auprès de l'agence de l'eau (plateforme en ligne ou courrier)\n"
                "7. Instruction par les services de l'agence\n"
                "8. Notification et convention de financement\n"
                "9. Réalisation des travaux et justification des dépenses"
            ),
            "documents_requis": [
                "Formulaire de demande de subvention de l'agence de l'eau concernée",
                "Études techniques ou diagnostic préalable",
                "Devis détaillés des travaux",
                "Plan de financement prévisionnel",
                "Délibération de la collectivité approuvant le projet",
                "Plan de situation et cartographie du projet",
                "Autorisations administratives (loi sur l'eau si nécessaire)",
                "RIB de la collectivité",
            ],
            "delai_instruction": "2 à 6 mois",
            "permanent": True,
            "url_officielle": "https://www.lesagencesdeleau.fr",
            "formulaire_url": None,
            "tags": [
                "agences de l'eau",
                "eau",
                "milieux aquatiques",
                "zones humides",
                "eaux pluviales",
                "assainissement",
                "sobriété hydrique",
                "SFN",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte

# Propriétaires : principalement publics
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : liés à la gestion de l'eau sur le patrimoine bâti
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "plomberie"},
        {"aide_id": aide_id, "travaux_code": "parcs_jardins"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "couverture"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale → pas de contrainte (6 agences couvrent tout le territoire)

# Segments : communes
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ Agences de l'eau inséré avec succès (id: {aide_id})")
