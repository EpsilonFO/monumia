"""
Seed: World Monuments Fund (WMF) — World Monuments Watch.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_world_monuments_fund.py
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
            "nom": "World Monuments Fund (WMF) — World Monuments Watch",
            "nom_court": "WMF",
            "description": "Organisation internationale finançant la conservation et la restauration de monuments et sites patrimoniaux exceptionnels dans le monde, dont la France, via le programme World Monuments Watch et des subventions directes.",
            "description_longue": (
                "Le World Monuments Fund (WMF) est une organisation non gouvernementale internationale "
                "créée en 1965, dédiée à la préservation de monuments et sites patrimoniaux exceptionnels "
                "à travers le monde. Présent en France depuis 1989 via sa branche WMF France (réouverte "
                "en 2023 sous la direction de Mathilde Augé), le WMF a conduit plus de 30 projets sur "
                "21 sites français et investi 19 millions de dollars dans le patrimoine français. "
                "Le programme phare est le World Monuments Watch, une liste biennale de 25 sites "
                "patrimoniaux menacés dans le monde. L'inscription sur cette liste ouvre l'accès à des "
                "financements, une expertise technique et une visibilité internationale. En 2026, le WMF "
                "a annoncé un engagement de plus de 7 millions de dollars pour 21 nouveaux projets dans "
                "le monde. Parmi les projets récents en France : la Chapelle de la Sorbonne, l'église "
                "Saint-Eustache à Paris, le Potager du Roi à Versailles, la Chancellerie d'Orléans."
            ),
            "categorie": "fondation",
            "type": "subvention",
            "organisme": "World Monuments Fund (WMF)",
            "montant_max": None,
            "taux_max": None,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": True,
            "architecte_requis": True,
            "conditions_eligibilite_detail": (
                "- Le site doit présenter une signification culturelle exceptionnelle (architecturale, historique, artistique)\n"
                "- Le site doit faire face à un besoin urgent de conservation (dégradation, menace climatique, conflit, pression urbaine)\n"
                "- La faisabilité de l'approche de conservation proposée est un critère clé de sélection\n"
                "- Le WMF privilégie les sites moins connus et ceux associés à des communautés dont les moyens d'existence seraient directement impactés par la préservation\n"
                "- Tous les niveaux de protection sont éligibles : classé MH, inscrit MH, patrimoine remarquable non protégé\n"
                "- Propriétaires éligibles : collectivités, État, associations, fondations, établissements publics\n"
                "- Les propriétaires privés peuvent être éligibles si le site présente une signification culturelle majeure et une dimension publique\n"
                "- Programme World Monuments Watch : liste biennale de 25 sites mondiaux ; les nominations sont ouvertes tous les 2 ans (prochaine échéance : mars 2026 pour Watch 2027)\n"
                "- Le WMF peut aussi financer des projets hors Watch via des partenariats directs\n"
                "- Un cofinancement est généralement requis : le WMF agit en co-financeur avec d'autres partenaires (État, mécènes, collectivités)\n"
                "- Le WMF apporte également une expertise technique (plans de conservation, études de diagnostic, formation)\n"
                "- Les projets doivent inclure un volet de sensibilisation du public et de développement des capacités locales\n"
                "- La candidature au Watch se fait via un formulaire en ligne sur wmf.org\n"
                "- Le WMF évalue : signification culturelle du site, urgence de l'action, faisabilité, impact sur la communauté locale"
            ),
            "demarche_description": (
                "1. Nominer le site via le formulaire en ligne sur wmf.org/watch-nominate (nominations ouvertes tous les 2 ans)\n"
                "2. Fournir un dossier complet : signification culturelle, état de conservation, menaces, approche proposée, partenaires locaux\n"
                "3. Évaluation par un panel international d'experts du WMF\n"
                "4. Sélection des 25 sites du World Monuments Watch\n"
                "5. Co-conception d'un plan d'action et d'une stratégie de financement avec l'équipe WMF\n"
                "6. Mise en œuvre du projet de conservation avec suivi technique du WMF\n"
                "7. Pour les projets hors Watch : contacter directement WMF France (wmf.org/affiliate/france)"
            ),
            "documents_requis": [
                "Formulaire de nomination World Monuments Watch",
                "Description de la signification culturelle du site",
                "État de conservation et diagnostic des menaces",
                "Programme de conservation proposé",
                "Plan de financement et partenaires identifiés",
                "Photos et documentation visuelle",
                "Lettres de soutien des partenaires locaux et institutionnels",
            ],
            "delai_instruction": "12 à 18 mois (cycle biennal du Watch)",
            "permanent": False,
            "url_officielle": "https://www.wmf.org/",
            "formulaire_url": "https://www.wmf.org/watch-nominate",
            "tags": [
                "World Monuments Fund",
                "WMF",
                "Watch",
                "patrimoine mondial",
                "conservation",
                "international",
                "restauration",
                "sites menacés",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : tous niveaux (signification culturelle prime)
supabase.table("aides_protections").insert(
    [
        {"aide_id": aide_id, "protection_code": "classe"},
        {"aide_id": aide_id, "protection_code": "inscrit"},
        {"aide_id": aide_id, "protection_code": "non_protege"},
    ]
).execute()
print("  ✓ Protections insérées")

# Propriétaires : principalement publics et associations
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : restauration, conservation, études
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "vitraux"},
        {"aide_id": aide_id, "travaux_code": "peintures_murales"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
        {"aide_id": aide_id, "travaux_code": "parcs_jardins"},
        {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : nationale (pas de contrainte)

# Segments : tous segments
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
        {"aide_id": aide_id, "segment_code": "prive"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : priorité aux sites en péril ou dégradés
supabase.table("aides_etats_conservation").insert(
    [
        {"aide_id": aide_id, "etat_conservation_code": "moyen"},
        {"aide_id": aide_id, "etat_conservation_code": "mauvais"},
        {"aide_id": aide_id, "etat_conservation_code": "peril"},
    ]
).execute()
print("  ✓ États de conservation insérés")

print(f"\n✅ World Monuments Fund inséré avec succès (id: {aide_id})")
