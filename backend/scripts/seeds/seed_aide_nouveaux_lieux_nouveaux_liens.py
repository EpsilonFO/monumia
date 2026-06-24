"""
Seed: Programme Nouveaux Lieux, Nouveaux Liens (ANCT) — Tiers-lieux et patrimoine.

Run:
    cd backend && uv run python3 scripts/seed_aide_nouveaux_lieux_nouveaux_liens.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = (
    supabase.table("aides_v3")
    .insert(
        {
            "nom": "Programme Nouveaux Lieux, Nouveaux Liens — Fabriques de Territoire (ANCT)",
            "nom_court": "Nouveaux Lieux, Nouveaux Liens",
            "description": "Programme national de l'ANCT soutenant la création et la consolidation de tiers-lieux (Fabriques de Territoire, Manufactures de Proximité) sur les territoires fragiles, incluant la réhabilitation de bâtiments patrimoniaux en espaces partagés.",
            "description_longue": (
                "Le programme « Nouveaux Lieux, Nouveaux Liens » est piloté par l'ANCT (Agence "
                "nationale de la cohésion des territoires) depuis 2020. Il vise à créer une "
                "dynamique nationale en renforçant le maillage des territoires avec un réseau "
                "dense de tiers-lieux. Le programme a labellisé 407 Fabriques de Territoire "
                "et 100 Manufactures de Proximité depuis son lancement, avec un investissement "
                "total de plus de 90 millions d'euros. Les Fabriques de Territoire sont des "
                "tiers-lieux implantés dans des territoires fragiles (zones rurales, quartiers "
                "politique de la ville, petites villes) qui proposent des services de proximité : "
                "coworking, fablabs, cafés associatifs, jardins partagés, micro-folies. "
                "Le programme peut financer la réhabilitation de bâtiments patrimoniaux pour "
                "les transformer en tiers-lieux, ce qui en fait une opportunité pour les "
                "propriétaires de patrimoine souhaitant donner un usage collectif à leur bien. "
                "Les lauréats reçoivent une subvention forfaitaire de 50 000 € pour un an, "
                "renouvelable par re-conventionnement."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "ANCT — Agence Nationale de la Cohésion des Territoires",
            "montant_max": 50000,
            "taux_max": None,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Le programme fonctionne par vagues de sélection (appels à manifestation "
                "d'intérêt / AMI) et re-conventionnements annuels. Ce n'est pas un guichet "
                "permanent.\n"
                "- Les lauréats « Fabriques de Territoire » reçoivent une subvention forfaitaire "
                "de 50 000 € pour un an, renouvelable par re-conventionnement.\n"
                "- Bénéficiaires éligibles : associations, collectivités (communes, intercommunalités, "
                "EPCI, métropoles), entreprises de l'ESS, coopératives (SCIC, SCOP), porteurs de "
                "projets de tiers-lieux.\n"
                "- Priorité géographique : territoires fragiles — zones rurales, quartiers politique "
                "de la ville (QPV), petites villes, territoires Action Cœur de Ville et Petites "
                "Villes de Demain.\n"
                "- 34 % des tiers-lieux labellisés sont en milieu rural, 28 % dans des villes moyennes.\n"
                "- Le projet doit correspondre à la définition d'un tiers-lieu : espace hybride "
                "et flexible favorisant la rencontre, le partage et l'initiative collective.\n"
                "- Types de tiers-lieux éligibles : coworking, fablabs, ateliers partagés, cafés "
                "associatifs, jardins partagés, micro-folies, manufactures de proximité.\n"
                "- La réhabilitation de bâtiments patrimoniaux en tiers-lieux est éligible, "
                "mais le projet doit avoir un usage collectif et de proximité.\n"
                "- Le volet DEFFINOV (185 projets, 50 M€) soutient des consortiums entre "
                "tiers-lieux, organismes de formation et acteurs de compétence.\n"
                "- Le volet Manufactures de Proximité (100 labellisées, 30 M€) cible les "
                "ateliers de fabrication partagés.\n"
                "- Les particuliers (personnes physiques) ne sont généralement pas éligibles "
                "directement : il faut porter le projet via une structure (association, "
                "coopérative, collectivité).\n"
                "- 15 réseaux régionaux de tiers-lieux sont actifs et peuvent accompagner "
                "les porteurs de projets."
            ),
            "demarche_description": (
                "1. Vérifier si un appel à manifestation d'intérêt (AMI) ou une vague de "
                "re-conventionnement est en cours sur le site de l'ANCT\n"
                "2. Contacter le réseau régional de tiers-lieux de votre territoire pour "
                "un accompagnement\n"
                "3. Préparer un dossier décrivant le projet de tiers-lieu, son ancrage "
                "territorial et ses usages\n"
                "4. Déposer la candidature sur la plateforme indiquée par l'ANCT lors de "
                "l'appel en cours\n"
                "5. Attendre la sélection par le comité national"
            ),
            "documents_requis": [
                "Dossier de candidature (formulaire ANCT)",
                "Statuts de la structure porteuse",
                "Description du projet de tiers-lieu et de ses usages",
                "Plan de financement et modèle économique",
                "Ancrage territorial : diagnostic du territoire et des besoins",
                "Partenariats locaux identifiés",
            ],
            "delai_instruction": "3 à 6 mois (selon les vagues de sélection)",
            "permanent": False,
            "url_officielle": "https://anct.gouv.fr/programmes-dispositifs/tiers-lieux",
            "formulaire_url": None,
            "tags": [
                "ANCT",
                "tiers-lieux",
                "Fabriques de Territoire",
                "Manufactures de Proximité",
                "Nouveaux Lieux Nouveaux Liens",
                "cohésion territoriale",
                "ESS",
                "zones rurales",
                "QPV",
                "réhabilitation",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte (patrimoine protégé ou non)
# → on n'insère rien dans aides_protections

# Propriétaires : collectivités, associations, structures ESS
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
        {"aide_id": aide_id, "proprietaire_code": "mixte"},
    ]
).execute()
print("  ✓ Propriétaires éligibles insérés")

# Travaux : réhabilitation, aménagement intérieur
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "electricite"},
        {"aide_id": aide_id, "travaux_code": "plomberie"},
        {"aide_id": aide_id, "travaux_code": "chauffage"},
        {"aide_id": aide_id, "travaux_code": "accessibilite"},
        {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
    ]
).execute()
print("  ✓ Travaux éligibles insérés")

# Régions : aide nationale → pas de contrainte

# Segments : principalement communes et structures ESS
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
        {"aide_id": aide_id, "segment_code": "prive"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ Nouveaux Lieux, Nouveaux Liens inséré avec succès (id: {aide_id})")
