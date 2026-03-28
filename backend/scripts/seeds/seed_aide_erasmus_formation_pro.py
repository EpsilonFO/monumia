"""
Seed: Erasmus+ Formation professionnelle et Mobilités.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_erasmus_formation_pro.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Erasmus+ — Formation professionnelle et Mobilités (KA1 VET)",
    "nom_court": "Erasmus+ Formation pro",
    "description": "Programme européen finançant la mobilité d'apprentis et de professionnels de la formation professionnelle (dont les métiers du patrimoine et de l'artisanat) pour des stages, formations ou périodes d'observation en Europe.",
    "description_longue": (
        "Le programme Erasmus+ (Action clé 1 — KA1 VET) finance la mobilité internationale des "
        "apprentis, stagiaires et personnels des organismes de formation professionnelle. Dans le "
        "domaine du patrimoine, il permet aux apprentis des métiers d'art et du bâtiment ancien "
        "(tailleurs de pierre, charpentiers, restaurateurs, maçons spécialisés…) d'effectuer des "
        "stages dans des ateliers et chantiers européens, d'acquérir des compétences sur des "
        "techniques traditionnelles étrangères, et de développer leur réseau professionnel. "
        "Les organismes de formation (CFA, lycées professionnels, Compagnons du Devoir, écoles "
        "du patrimoine) peuvent obtenir une accréditation Erasmus+ ou déposer des projets de "
        "mobilité de courte durée (KA122-VET) pour envoyer jusqu'à 30 participants par projet. "
        "Les bourses couvrent les frais de voyage, de séjour et de préparation linguistique. "
        "En 2026, les barèmes ont été revus à la hausse pour mieux couvrir les frais réels des "
        "apprentis. Le complément inclusion (150 €/mois) est accessible aux apprentis en situation "
        "de handicap, résidant en ZFRR ou en QPV."
    ),
    "categorie": "europe",
    "type": "subvention",
    "organisme": "Commission européenne / Agence Erasmus+ France",
    "montant_max": None,
    "taux_max": 100,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": False,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Le porteur de projet doit être un organisme de formation professionnelle établi dans un État membre de l'UE ou un pays associé\n"
        "- Types d'organismes éligibles : CFA, lycées professionnels, Compagnons du Devoir, écoles du patrimoine, centres de formation continue\n"
        "- Les participants doivent être des apprenants en formation professionnelle initiale (iVET) ou continue (cVET), ou du personnel de formation\n"
        "- Les apprentis des métiers du patrimoine et de l'artisanat sont pleinement éligibles : tailleur de pierre, charpentier, maçon, restaurateur, couvreur, etc.\n"
        "- Deux voies d'accès :\n"
        "  • Accréditation Erasmus+ (KA121-VET) : pour les organismes souhaitant envoyer des participants régulièrement\n"
        "  • Projets de mobilité de courte durée (KA122-VET) : maximum 30 participants par projet, idéal pour les organismes débutants\n"
        "- Activités éligibles : stages en entreprise à l'étranger (2 semaines à 12 mois), observation professionnelle (job shadowing), cours de développement professionnel pour le personnel\n"
        "- Bourses calculées sur des coûts unitaires selon la destination (3 groupes de pays) :\n"
        "  • Groupe 1 (Danemark, Irlande, Islande, Liechtenstein, Luxembourg, Norvège, Suède, Finlande) : montant le plus élevé\n"
        "  • Groupe 2 (Allemagne, Autriche, Belgique, France, Italie, Espagne, etc.) : montant intermédiaire\n"
        "  • Groupe 3 (Europe de l'Est, pays associés) : montant le plus bas\n"
        "- Montant indicatif des bourses pour les apprentis en stage : 300 à 700 €/mois selon la destination + 150 €/mois de complément stage\n"
        "- Complément inclusion de 150 €/mois pour : apprentis en situation de handicap ou ALD, résidents en ZFRR ou QPV\n"
        "- Frais de voyage couverts forfaitairement selon la distance (de 23 € à 1 735 € par participant)\n"
        "- Les propriétaires de monuments ne sont pas directement bénéficiaires : ce sont les organismes de formation qui portent le projet\n"
        "- Un propriétaire de monument peut être partenaire d'accueil (chantier-école sur son monument) mais ne reçoit pas directement les fonds\n"
        "- Les dates limites de candidature sont généralement en février (KA122-VET) et en octobre (KA121-VET accréditation)\n"
        "- Le programme Erasmus+ 2021-2027 est en cours ; la prochaine programmation débutera en 2028"
    ),
    "demarche_description": (
        "1. L'organisme de formation identifie les besoins de mobilité de ses apprentis/personnels dans les métiers du patrimoine\n"
        "2. Choisir la voie d'accès : accréditation (KA121-VET) pour des mobilités régulières, ou projet de courte durée (KA122-VET) pour un premier projet\n"
        "3. Déposer la candidature sur la plateforme MonProjetErasmus+ avant la date limite (février pour KA122-VET)\n"
        "4. Identifier les partenaires d'accueil européens (ateliers, chantiers, centres de formation)\n"
        "5. Sélection des participants et préparation linguistique/culturelle\n"
        "6. Réalisation des mobilités (stages, formations, observations)\n"
        "7. Rapport final et attestation des compétences acquises (Europass Mobilité)"
    ),
    "documents_requis": [
        "Formulaire de candidature Erasmus+ (plateforme MonProjetErasmus+)",
        "Description de l'organisme et de son activité de formation",
        "Programme de mobilité détaillé (objectifs, activités, calendrier)",
        "Lettres d'engagement des partenaires d'accueil européens",
        "Budget prévisionnel basé sur les coûts unitaires Erasmus+",
        "Plan de diffusion des résultats",
    ],
    "delai_instruction": "3 à 5 mois (appel annuel, résultats en juin-juillet)",
    "permanent": False,
    "url_officielle": "https://info.erasmusplus.fr/",
    "formulaire_url": "https://monprojet.erasmusplus.fr/",
    "tags": [
        "Erasmus+", "formation professionnelle", "mobilité", "apprentissage",
        "métiers d'art", "patrimoine", "Europe", "stage", "compagnonnage",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (concerne la formation, pas le monument directement)

# Propriétaires : pas de contrainte directe (le bénéficiaire est l'organisme de formation)

# Travaux : tous types (les apprentis formés interviennent sur tous types de travaux patrimoniaux)
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
    {"aide_id": aide_id, "travaux_code": "etude_prealable"},
]).execute()
print("  ✓ Travaux insérés")

# Régions : nationale

# Segments : BTP principalement (organismes de formation du BTP patrimoine)
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "btp"},
]).execute()
print("  ✓ Segments insérés")

print(f"\n✅ Erasmus+ Formation pro inséré avec succès (id: {aide_id})")
