"""
Seed: Éducation et classes de découverte — Valorisation et médiation
du patrimoine auprès du public scolaire et des jeunes.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_education_classes_decouverte.py
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
            "nom": "Subvention DRAC — Valorisation et médiation du patrimoine (éducation, classes de découverte)",
            "nom_court": "DRAC Médiation patrimoine",
            "description": "Subvention de la DRAC pour des projets de valorisation, médiation et éducation au patrimoine à destination du public scolaire et des jeunes, incluant classes de découverte, ateliers pédagogiques et visites éducatives dans les monuments historiques.",
            "description_longue": (
                "Les Directions Régionales des Affaires Culturelles (DRAC) soutiennent les projets "
                "de valorisation et de médiation du patrimoine culturel à destination des publics "
                "scolaires et des jeunes. Cette aide s'inscrit dans le cadre de l'éducation artistique "
                "et culturelle (EAC) et vise à favoriser l'accès des élèves aux monuments historiques "
                "et sites patrimoniaux. Les projets éligibles incluent les classes de découverte du "
                "patrimoine, les ateliers pédagogiques, les visites commentées, les publications "
                "éducatives, les expositions à vocation pédagogique, les chantiers de bénévoles "
                "jeunes, et les programmes de médiation associant au moins deux structures ou sites. "
                "Le dispositif national « C'est mon patrimoine ! » complète cette offre en ciblant "
                "les jeunes hors temps scolaire, notamment pendant les vacances, pour découvrir "
                "le patrimoine par la pratique artistique. Les VMF (Vieilles Maisons Françaises) "
                "proposent également le programme « Le patrimoine, toute une histoire ! » avec des "
                "kits pédagogiques gratuits pour les classes de cycle 3 (CM1-CM2-6e). La veille des "
                "Journées Européennes du Patrimoine, une journée est dédiée à l'accueil des scolaires "
                "de la maternelle au lycée."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "Ministère de la Culture — DRAC / DAC",
            "montant_max": None,
            "taux_max": 80,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Bénéficiaires éligibles : collectivités territoriales, établissements publics, "
                "associations, structures privées gestionnaires d'un monument historique ou d'un site "
                "patrimonial, ou conduisant un projet de médiation et valorisation du patrimoine.\n"
                "- Les particuliers personnes physiques ne sont pas éligibles directement ; ils doivent "
                "porter le projet via une structure (association, SCI, entreprise).\n"
                "- Le projet doit s'inscrire dans les trois piliers de l'éducation artistique et culturelle "
                "(EAC) : voir (expérience esthétique au contact du patrimoine), pratiquer (expérience "
                "artistique avec des artistes), interpréter (connaissance et réflexion critique).\n"
                "- Les actions éligibles incluent : cycles de conférences, ateliers pédagogiques, visites "
                "commentées, publications, expositions à vocation éducative, chantiers de bénévoles, "
                "et toute programmation annuelle associant au moins deux structures, sites ou monuments.\n"
                "- Les dépenses éligibles comprennent : honoraires d'intervenants extérieurs, frais de "
                "déplacement liés au projet, matériel pédagogique, supports de communication et de "
                "médiation, scénographie d'exposition.\n"
                "- Le projet doit démontrer un partenariat avec des établissements scolaires ou des "
                "structures d'accueil de jeunes (centres de loisirs, MJC, etc.).\n"
                "- Pour le dispositif « C'est mon patrimoine ! » : le projet doit cibler les jeunes "
                "hors temps scolaire (vacances scolaires), inclure une dimension de pratique artistique, "
                "et favoriser l'accès des publics éloignés de la culture (quartiers prioritaires, zones rurales).\n"
                "- Les projets en zones prioritaires (QPV, zones rurales) sont favorisés dans les critères "
                "de sélection.\n"
                "- La demande est déposée en ligne sur le portail Démarches Simplifiées auprès de la "
                "DRAC/DAC de la région concernée.\n"
                "- Chaque DRAC fixe son propre calendrier de dépôt et ses critères spécifiques.\n"
                "- Le cumul avec d'autres aides publiques est possible dans la limite de 80 % du coût "
                "total du projet.\n"
                "- Obligation de mentionner le soutien du Ministère de la Culture dans les supports "
                "de communication du projet."
            ),
            "demarche_description": (
                "1. Identifier la DRAC de votre région et vérifier le calendrier de dépôt des demandes\n"
                "2. Élaborer le projet pédagogique en lien avec des établissements scolaires ou structures jeunesse\n"
                "3. Constituer le dossier : description du projet, budget prévisionnel, partenariats, "
                "calendrier, CV des intervenants\n"
                "4. Déposer la demande en ligne sur le portail Démarches Simplifiées\n"
                "5. Instruction par la DRAC (évaluation artistique, pédagogique et territoriale)\n"
                "6. Notification de l'attribution et convention\n"
                "7. Réalisation du projet et envoi du bilan financier et qualitatif"
            ),
            "documents_requis": [
                "Description détaillée du projet pédagogique",
                "Budget prévisionnel du projet",
                "Lettres d'engagement des partenaires (établissements scolaires, structures jeunesse)",
                "CV des intervenants et artistes",
                "Calendrier prévisionnel des actions",
                "Statuts de la structure porteuse",
                "RIB de la structure",
                "Bilan du projet précédent (si renouvellement)",
            ],
            "delai_instruction": "2 à 4 mois",
            "permanent": True,
            "url_officielle": "https://www.culture.gouv.fr/catalogue-des-demarches-et-subventions/appels-a-projets-candidatures/c-est-mon-patrimoine",
            "formulaire_url": "https://demarche.numerique.gouv.fr",
            "tags": [
                "éducation",
                "classes de découverte",
                "médiation",
                "patrimoine",
                "scolaire",
                "jeunesse",
                "EAC",
                "C'est mon patrimoine",
                "VMF",
                "DRAC",
                "valorisation",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte (patrimoine protégé et non protégé)

# Propriétaires : collectivités, associations, structures privées
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "mixte"},
    ]
).execute()
print("  ✓ Propriétaires éligibles insérés")

# Travaux : valorisation, médiation (pas de travaux physiques)
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "accessibilite"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    ]
).execute()
print("  ✓ Travaux éligibles insérés")

# Régions : aide nationale → pas de contrainte

# Segments : tous segments
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
        {"aide_id": aide_id, "segment_code": "prive"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ Éducation et classes de découverte inséré avec succès (id: {aide_id})")
