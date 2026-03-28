"""
Seed: Loto du patrimoine / Mission Bern — Fondation du patrimoine.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_loto_patrimoine.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Loto du patrimoine — Mission Bern (Fondation du patrimoine)",
    "nom_court": "Loto du patrimoine",
    "description": "Subvention issue des recettes du Loto du patrimoine et des jeux de grattage Mission Patrimoine, redistribuée par la Fondation du patrimoine pour la restauration de sites patrimoniaux en péril sur tout le territoire.",
    "description_longue": (
        "Le Loto du patrimoine, lancé en 2018 à l'initiative de Stéphane Bern et soutenu par "
        "le ministère de la Culture, finance la restauration de sites patrimoniaux en péril grâce aux "
        "recettes de tirages spéciaux du Loto et de jeux de grattage « Mission Patrimoine ». Chaque "
        "année, une sélection de sites emblématiques (environ 100 sites départementaux + 18 sites "
        "« coup de cœur ») est retenue après un appel à candidatures. Les fonds sont redistribués "
        "par la Fondation du patrimoine, qui assure l'instruction des dossiers et le suivi des travaux. "
        "Depuis son lancement, le dispositif a permis de soutenir plus de 900 sites pour un montant "
        "total dépassant 260 millions d'euros. Les sites peuvent être classés, inscrits ou non protégés "
        "au titre des monuments historiques, à condition de présenter un intérêt patrimonial avéré et "
        "d'être en situation de péril ou de dégradation avancée."
    ),
    "categorie": "fondation",
    "type": "subvention",
    "organisme": "Fondation du patrimoine (Mission Bern / Ministère de la Culture)",
    "montant_max": 500000,
    "taux_max": 100,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": False,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Le site doit présenter un intérêt patrimonial avéré (architectural, historique, mémoriel, paysager)\n"
        "- Le site doit être en situation de péril, de dégradation avancée ou menacé de disparition\n"
        "- Tous les niveaux de protection sont éligibles : classé MH, inscrit MH, non protégé, label XXe siècle, patrimoine vernaculaire\n"
        "- Le patrimoine religieux, civil, industriel, militaire, agricole, funéraire et vernaculaire est éligible\n"
        "- Propriétaires éligibles : communes, intercommunalités, départements, régions, collectivités d'outre-mer, associations, entreprises privées, personnes physiques\n"
        "- Les propriétaires doivent démontrer leur incapacité à financer seuls la restauration\n"
        "- Deux catégories de sites sélectionnés chaque année :\n"
        "  • 18 « sites emblématiques régionaux » (un par région + outre-mer) : dotation de 200 000 à 500 000 € par site\n"
        "  • ~100 « sites départementaux » (un par département) : dotation de 30 000 à 300 000 € par site\n"
        "- Pour les sites non protégés : jusqu'à 40 % du besoin de financement couvert par la Mission Patrimoine\n"
        "- Pour les sites protégés MH : pourcentage plus faible (car déjà aidés par les subventions DRAC)\n"
        "- Pour les petits projets (~50 000 € de coût total) : jusqu'à 100 % de couverture possible\n"
        "- Les travaux doivent être de restauration patrimoniale, de sauvegarde ou de mise hors d'eau/hors d'air\n"
        "- Les travaux d'amélioration ou de rénovation simple NE SONT PAS éligibles\n"
        "- Les travaux ne doivent PAS avoir commencé avant la sélection du site\n"
        "- 4 critères de sélection : intérêt patrimonial et culturel, état de péril, maturité du projet (devis, calendrier), impact territorial et projet de valorisation\n"
        "- Le dossier doit être complet pour être soumis au comité de sélection\n"
        "- La sélection est faite par un comité présidé par Stéphane Bern, avec la Fondation du patrimoine, la FDJ et le ministère de la Culture\n"
        "- Le comité se réunit deux fois par an\n"
        "- Dates limites (édition 2026) : sites emblématiques avant le 16 novembre 2025, sites départementaux avant le 28 février 2026\n"
        "- Les sites sélectionnés peuvent également bénéficier de souscriptions publiques et de mécénat complémentaires"
    ),
    "demarche_description": (
        "1. Déposer la candidature en ligne sur https://www.missionbern.fr/signaler-un-site (seul mode de candidature accepté)\n"
        "2. Le formulaire prend environ 30 minutes à remplir (pas de sauvegarde intermédiaire possible)\n"
        "3. Fournir : descriptif du site, état des lieux, programme de travaux détaillé, devis, plan de financement, calendrier prévisionnel\n"
        "4. Instruction par les délégations départementales et régionales de la Fondation du patrimoine\n"
        "5. Sélection par le comité national présidé par Stéphane Bern\n"
        "6. Annonce publique des sites retenus (généralement en septembre lors des Journées européennes du patrimoine)\n"
        "7. Convention de financement avec la Fondation du patrimoine\n"
        "8. Réalisation des travaux et versement de la subvention par tranches sur justificatifs"
    ),
    "documents_requis": [
        "Formulaire de candidature Mission Patrimoine",
        "Descriptif détaillé du site et de son intérêt patrimonial",
        "État des lieux et diagnostic de l'état de conservation (photos, rapports)",
        "Programme de travaux détaillé",
        "Devis des entreprises",
        "Plan de financement prévisionnel",
        "Preuve de propriété",
        "Engagement du propriétaire (conservation, entretien, ouverture au public le cas échéant)",
        "Avis de la DRAC ou de l'ABF (si monument protégé)",
    ],
    "delai_instruction": "6 à 12 mois (appel annuel)",
    "permanent": False,
    "url_officielle": "https://www.missionbern.fr/",
    "formulaire_url": "https://www.missionbern.fr/signaler-un-site",
    "tags": [
        "Loto du patrimoine", "Mission Bern", "Fondation du patrimoine",
        "patrimoine en péril", "restauration", "sauvegarde", "appel à projets",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : tous niveaux éligibles
supabase.table("aides_protections").insert([
    {"aide_id": aide_id, "protection_code": "classe"},
    {"aide_id": aide_id, "protection_code": "inscrit"},
    {"aide_id": aide_id, "protection_code": "non_protege"},
]).execute()
print("  ✓ Protections insérées")

# Propriétaires : tous types
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "public_departement"},
    {"aide_id": aide_id, "proprietaire_code": "public_region"},
    {"aide_id": aide_id, "proprietaire_code": "public_etat"},
    {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
    {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
]).execute()
print("  ✓ Propriétaires insérés")

# Travaux : restauration générale et travaux de sauvegarde
supabase.table("aides_travaux").insert([
    {"aide_id": aide_id, "travaux_code": "restauration_generale"},
    {"aide_id": aide_id, "travaux_code": "toiture"},
    {"aide_id": aide_id, "travaux_code": "charpente"},
    {"aide_id": aide_id, "travaux_code": "couverture"},
    {"aide_id": aide_id, "travaux_code": "facade"},
    {"aide_id": aide_id, "travaux_code": "maconnerie"},
    {"aide_id": aide_id, "travaux_code": "vitraux"},
    {"aide_id": aide_id, "travaux_code": "peintures_murales"},
    {"aide_id": aide_id, "travaux_code": "menuiserie"},
    {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
    {"aide_id": aide_id, "travaux_code": "etude_prealable"},
]).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale → pas de contrainte

# Segments : tous segments
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "commune"},
    {"aide_id": aide_id, "segment_code": "prive"},
]).execute()
print("  ✓ Segments insérés")

# État de conservation : priorité au patrimoine en péril
supabase.table("aides_etats_conservation").insert([
    {"aide_id": aide_id, "etat_conservation_code": "mauvais"},
    {"aide_id": aide_id, "etat_conservation_code": "peril"},
]).execute()
print("  ✓ États de conservation insérés")

print(f"\n✅ Loto du patrimoine inséré avec succès (id: {aide_id})")
