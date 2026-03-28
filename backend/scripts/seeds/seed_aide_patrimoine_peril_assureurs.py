"""
Seed: Programme "Patrimoine en péril" (assureurs) — Mécénat des compagnies
d'assurance pour la restauration de monuments en péril (AXA, Allianz, Albingia).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_patrimoine_peril_assureurs.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Programme Patrimoine en péril — Mécénat des assureurs (AXA / Fondation du patrimoine)",
    "nom_court": "Patrimoine en péril (assureurs)",
    "description": "Programme de mécénat des compagnies d'assurance (AXA, Allianz, Albingia) en partenariat avec la Fondation du patrimoine pour financer la restauration de monuments historiques en péril sur l'ensemble du territoire.",
    "description_longue": (
        "Depuis 2018, plusieurs compagnies d'assurance françaises se sont engagées dans "
        "le mécénat patrimonial en partenariat avec la Fondation du patrimoine et la "
        "Mission Patrimoine (Mission Bern). Le programme le plus structuré est celui d'AXA, "
        "via le Fonds AXA pour le Progrès humain, qui verse 660 000 € par an à la "
        "Fondation du patrimoine, répartis chaque année sur 6 projets de restauration "
        "sélectionnés parmi les 100 projets prioritaires identifiés par la Mission "
        "Patrimoine. Allianz soutient la restauration d'œuvres d'art via son réseau "
        "de collaborateurs et agents généraux, avec des mécénats de 8 000 € par œuvre. "
        "Albingia, assureur spécialisé depuis 55 ans dans l'accompagnement des propriétaires "
        "de bâtiments publics et privés, contribue également à la préservation du patrimoine. "
        "La Fondation Mérimée, soutenue par des assureurs spécialisés comme Assurances de "
        "Châteaux, finance des projets de restauration de monuments historiques privés. "
        "Ces programmes de mécénat viennent compléter les financements publics (DRAC, "
        "collectivités) et les souscriptions populaires. Environ 9 000 monuments historiques "
        "sont actuellement considérés en péril en France."
    ),
    "categorie": "mecenat",
    "type": "mecenat",
    "organisme": "AXA / Allianz / Albingia / Fondation du patrimoine / Fondation Mérimée",
    "montant_max": 110000,
    "taux_max": None,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": True,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Le monument doit être en état de péril avéré ou présenter un besoin urgent de "
        "restauration.\n"
        "- Les projets sont sélectionnés par un comité comprenant des représentants de la "
        "Fondation du patrimoine, de l'assureur mécène, et du Ministère de la Culture.\n"
        "- Pour le programme AXA / Fondation du patrimoine : les projets sont choisis parmi "
        "les 100 projets prioritaires de la Mission Patrimoine (Mission Bern). Le mécénat "
        "AXA s'élève à environ 110 000 € par projet (660 000 € répartis sur 6 projets/an).\n"
        "- Pour Allianz : mécénat ciblé sur la restauration d'œuvres d'art dans les monuments, "
        "avec des dotations de 8 000 € par œuvre identifiée.\n"
        "- Les critères de sélection de la Mission Patrimoine s'appliquent : intérêt patrimonial, "
        "état de péril, maturité du projet de restauration et de valorisation, impact "
        "territorial (emploi, tourisme, revitalisation).\n"
        "- Équilibre géographique et historique recherché, avec une priorité aux zones rurales "
        "et aux petites agglomérations.\n"
        "- Le projet doit démontrer un plan de valorisation ou de réutilisation du monument "
        "après restauration, avec un impact économique attendu.\n"
        "- Les bénéficiaires peuvent être des collectivités (communes, EPCI), des associations, "
        "des fondations, des propriétaires privés (personnes physiques, SCI).\n"
        "- Un cofinancement est attendu : le mécénat vient compléter d'autres sources "
        "(subventions DRAC, aides régionales, souscription publique, autofinancement).\n"
        "- La candidature se fait via la Fondation du patrimoine ou via le signalement d'un "
        "site sur www.missionbern.fr.\n"
        "- La candidature est gratuite et doit être déposée en ligne.\n"
        "- Types de monuments éligibles : églises, châteaux, usines, ateliers, fermes, "
        "moulins, et tout autre type de bâtiment ou site patrimonial en péril.\n"
        "- Le dossier complet (attestant du respect des critères) est soumis aux comités "
        "de sélection qui se réunissent deux fois par an."
    ),
    "demarche_description": (
        "1. Signaler le monument en péril sur www.missionbern.fr ou contacter la délégation "
        "régionale de la Fondation du patrimoine\n"
        "2. Constituer le dossier de candidature en ligne (description du monument, état de "
        "péril, projet de restauration et de valorisation)\n"
        "3. Sélection par les DRAC (projets départementaux) ou le comité national (projets "
        "emblématiques)\n"
        "4. Passage en comité de sélection du mécène (AXA, Allianz, etc.)\n"
        "5. Notification de l'aide et convention de mécénat\n"
        "6. Réalisation des travaux avec suivi par la Fondation du patrimoine\n"
        "7. Communication sur le mécénat (panneau de chantier, mentions dans les supports)"
    ),
    "documents_requis": [
        "Formulaire de candidature en ligne (missionbern.fr ou fondation-patrimoine.org)",
        "Photos du monument montrant l'état de péril",
        "Descriptif du projet de restauration",
        "Plan de financement prévisionnel",
        "Projet de valorisation ou de réutilisation post-restauration",
        "Devis estimatifs des travaux",
        "Attestation de propriété",
        "Arrêté de protection MH (si applicable)",
        "Accord du propriétaire (si le porteur n'est pas le propriétaire)",
    ],
    "delai_instruction": "3 à 12 mois (selon le calendrier des comités de sélection)",
    "permanent": True,
    "url_officielle": "https://www.fondation-patrimoine.org/fondation-du-patrimoine/partenaires-et-mecenes/axa",
    "formulaire_url": "https://www.missionbern.fr/signaler-un-site",
    "tags": [
        "mécénat", "assureurs", "AXA", "Allianz", "Albingia",
        "Fondation du patrimoine", "patrimoine en péril", "Mission Bern",
        "restauration", "Fondation Mérimée",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte stricte (patrimoine protégé et non protégé éligible)

# Propriétaires : tous types
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "public_departement"},
    {"aide_id": aide_id, "proprietaire_code": "public_region"},
    {"aide_id": aide_id, "proprietaire_code": "public_etat"},
    {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
    {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
    {"aide_id": aide_id, "proprietaire_code": "mixte"},
]).execute()
print("  ✓ Propriétaires éligibles insérés")

# Travaux : restauration large spectre
supabase.table("aides_travaux").insert([
    {"aide_id": aide_id, "travaux_code": "toiture"},
    {"aide_id": aide_id, "travaux_code": "charpente"},
    {"aide_id": aide_id, "travaux_code": "couverture"},
    {"aide_id": aide_id, "travaux_code": "facade"},
    {"aide_id": aide_id, "travaux_code": "maconnerie"},
    {"aide_id": aide_id, "travaux_code": "vitraux"},
    {"aide_id": aide_id, "travaux_code": "peintures_murales"},
    {"aide_id": aide_id, "travaux_code": "menuiserie"},
    {"aide_id": aide_id, "travaux_code": "restauration_generale"},
    {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
    {"aide_id": aide_id, "travaux_code": "etude_prealable"},
]).execute()
print("  ✓ Travaux éligibles insérés")

# Régions : aide nationale → pas de contrainte

# Segments : tous
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "commune"},
    {"aide_id": aide_id, "segment_code": "prive"},
]).execute()
print("  ✓ Segments insérés")

# État de conservation : priorité aux monuments en péril, mais pas exclusif
supabase.table("aides_etats_conservation").insert([
    {"aide_id": aide_id, "etat_conservation_code": "mauvais"},
    {"aide_id": aide_id, "etat_conservation_code": "peril"},
]).execute()
print("  ✓ États de conservation insérés")

print(f"\n✅ Programme Patrimoine en péril (assureurs) inséré avec succès (id: {aide_id})")
