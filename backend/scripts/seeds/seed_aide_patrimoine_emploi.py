"""
Seed: Programme Patrimoine Emploi (Fondation du patrimoine).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_patrimoine_emploi.py
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
            "nom": "Programme Patrimoine Emploi — Fondation du patrimoine",
            "nom_court": "Patrimoine Emploi",
            "description": "Programme de la Fondation du patrimoine qui finance des chantiers de restauration patrimoniale en y intégrant des parcours d'insertion professionnelle pour des personnes éloignées de l'emploi.",
            "description_longue": (
                "Le programme Patrimoine Emploi, porté par la Fondation du patrimoine, vise à concilier "
                "la sauvegarde du patrimoine bâti avec l'insertion professionnelle. Il finance des chantiers "
                "de restauration sur des édifices patrimoniaux (protégés ou non) en intégrant des parcours "
                "de formation et d'insertion pour des personnes éloignées de l'emploi (demandeurs d'emploi "
                "de longue durée, bénéficiaires du RSA, jeunes sans qualification, etc.). Les chantiers "
                "sont encadrés par des professionnels qualifiés du bâtiment et des accompagnateurs "
                "socioprofessionnels. Le programme est mis en œuvre en partenariat avec des structures "
                "d'insertion par l'activité économique (SIAE), des organismes de formation, France Travail "
                "et les collectivités territoriales. La Fondation du patrimoine apporte un financement "
                "complémentaire aux aides à l'insertion (État, FSE, collectivités) pour couvrir le surcoût "
                "lié à la dimension patrimoniale des chantiers (matériaux traditionnels, techniques anciennes)."
            ),
            "categorie": "fondation",
            "type": "subvention",
            "organisme": "Fondation du patrimoine",
            "montant_max": None,
            "taux_max": None,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": True,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Programme combinant restauration patrimoniale et insertion professionnelle\n"
                "- Le chantier doit porter sur un édifice présentant un intérêt patrimonial "
                "(classé, inscrit MH, ou patrimoine non protégé d'intérêt local)\n"
                "- Le projet doit intégrer un volet insertion : accueil de personnes éloignées de l'emploi "
                "en parcours de formation aux métiers du patrimoine\n"
                "- Publics visés pour l'insertion : demandeurs d'emploi de longue durée, bénéficiaires "
                "du RSA, jeunes sans qualification (16-25 ans), travailleurs handicapés, réfugiés\n"
                "- Le chantier doit être porté ou accompagné par une structure d'insertion par l'activité "
                "économique (SIAE) agréée : ACI, entreprise d'insertion (EI), association intermédiaire (AI)\n"
                "- Encadrement technique obligatoire par un professionnel qualifié du bâtiment "
                "(maçon, charpentier, couvreur, tailleur de pierre, etc.)\n"
                "- Accompagnement socioprofessionnel obligatoire des salariés en insertion\n"
                "- Le financement de la Fondation du patrimoine couvre le surcoût patrimonial "
                "(matériaux traditionnels, techniques anciennes, formation spécifique)\n"
                "- Cofinancement requis : les aides à l'insertion (aide au poste État/FSE, "
                "financements collectivités) doivent être mobilisées en parallèle\n"
                "- Priorité aux projets en milieu rural ou dans des communes défavorisées\n"
                "- Priorité aux techniques traditionnelles : maçonnerie de pierre, charpente bois, "
                "couverture ardoise/tuile, enduits à la chaux, taille de pierre\n"
                "- Le projet doit prévoir des certifications ou qualifications pour les personnes en insertion "
                "(CQP, titres professionnels, habilitations)\n"
                "- Propriétaires éligibles : collectivités, associations, propriétaires privés "
                "(pour ces derniers, le volet insertion doit être porté par une structure agréée)\n"
                "- Tous types de travaux de restauration compatibles avec un chantier d'insertion : "
                "gros œuvre, maçonnerie, couverture, charpente, menuiserie, enduits, peinture"
            ),
            "demarche_description": (
                "1. Contacter la délégation régionale de la Fondation du patrimoine\n"
                "2. Présenter le projet patrimonial et le volet insertion envisagé\n"
                "3. Identifier une structure d'insertion (SIAE) partenaire pour le chantier\n"
                "4. Constituer le dossier : description du monument, programme de travaux, "
                "plan de formation, budget prévisionnel\n"
                "5. Obtenir les cofinancements insertion (aide au poste, FSE, collectivités)\n"
                "6. Validation par la Fondation du patrimoine et convention de financement\n"
                "7. Réalisation du chantier avec suivi technique et socioprofessionnel\n"
                "8. Bilan final : rapport d'activité, justificatifs de dépenses, bilan d'insertion"
            ),
            "documents_requis": [
                "Description du monument et de son intérêt patrimonial",
                "Programme détaillé des travaux de restauration",
                "Plan de formation et d'insertion professionnelle",
                "Convention avec la structure d'insertion (SIAE) partenaire",
                "Budget prévisionnel détaillé et plan de financement",
                "Justificatifs des cofinancements obtenus ou sollicités",
                "Agrément de la SIAE (délivré par la DDETS)",
                "Photographies du monument avant travaux",
            ],
            "delai_instruction": "2 à 4 mois",
            "permanent": True,
            "url_officielle": "https://www.fondation-patrimoine.org",
            "formulaire_url": None,
            "tags": [
                "Fondation du patrimoine",
                "insertion professionnelle",
                "emploi",
                "formation",
                "SIAE",
                "chantier d'insertion",
                "métiers du patrimoine",
                "patrimoine emploi",
                "inclusion sociale",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (protégé et non protégé)

# Propriétaires : tous types
# (pas d'insertion = pas de contrainte)

# Travaux : travaux compatibles avec un chantier d'insertion
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

# Segments : tous segments

# État de conservation : pas de contrainte

print(f"\n✅ Programme Patrimoine Emploi inséré avec succès (id: {aide_id})")
