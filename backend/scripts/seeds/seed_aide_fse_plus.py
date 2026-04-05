"""
Seed: FSE+ (Fonds Social Européen Plus) — Formation et insertion
dans les métiers du patrimoine.

Run:
    cd backend && uv run python3 scripts/seed_aide_fse_plus.py
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
    supabase.table("aides_v2")
    .insert(
        {
            "nom": "FSE+ (Fonds Social Européen Plus) — Formation et insertion dans les métiers du patrimoine",
            "nom_court": "FSE+",
            "description": "Fonds européen finançant des actions de formation professionnelle, d'insertion et d'emploi, mobilisable pour les chantiers de restauration du patrimoine via la formation aux métiers du bâtiment ancien.",
            "description_longue": (
                "Le FSE+ est le principal instrument de l'Union européenne pour investir dans "
                "le capital humain. Doté de 99,3 milliards d'euros pour 2021-2027, il soutient "
                "l'emploi, la formation professionnelle, l'inclusion sociale et la lutte contre "
                "la pauvreté. Le FSE+ ne finance pas directement les travaux de restauration "
                "de monuments, mais il peut financer les volets emploi et formation des projets "
                "patrimoniaux : chantiers d'insertion par l'activité économique, formations aux "
                "métiers du bâtiment ancien (taille de pierre, charpente, maçonnerie traditionnelle), "
                "accompagnement des demandeurs d'emploi vers les métiers du patrimoine. "
                "En France, le FSE+ est géré par la DGEFP (Délégation Générale à l'Emploi et "
                "à la Formation Professionnelle) au niveau national et par les Conseils régionaux "
                "au niveau régional. Les porteurs de projets patrimoniaux peuvent mobiliser le FSE+ "
                "en complément d'autres aides pour financer la dimension humaine de leurs chantiers."
            ),
            "categorie": "europe",
            "type": "subvention",
            "organisme": "Commission européenne / DGEFP / Conseils régionaux (gestion partagée)",
            "montant_max": None,
            "taux_max": 60,
            "montant_min": None,
            "plancher": None,
            "base_ttc": True,
            "commune_max_population": None,
            "cofinancement_requis": True,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Le FSE+ ne finance PAS directement les travaux de restauration de monuments "
                "historiques. Il finance la dimension emploi, formation et insertion des projets.\n"
                "- Volets mobilisables pour le patrimoine :\n"
                "  • Formation professionnelle aux métiers du bâtiment ancien (taille de pierre, "
                "charpente traditionnelle, maçonnerie à la chaux, restauration de vitraux, etc.)\n"
                "  • Chantiers d'insertion par l'activité économique sur des sites patrimoniaux\n"
                "  • Accompagnement de demandeurs d'emploi vers les métiers du patrimoine\n"
                "  • Montée en compétences des artisans et entreprises du patrimoine\n"
                "- Bénéficiaires éligibles : organismes de formation, associations, collectivités, "
                "structures d'insertion, entreprises. Les particuliers ne sont pas éligibles comme "
                "porteurs de projet.\n"
                "- Taux de cofinancement UE : jusqu'à 60 % en régions en transition, 40 % en "
                "régions plus développées.\n"
                "- Les dépenses éligibles sont principalement les coûts salariaux (formateurs, "
                "encadrants, stagiaires), les frais pédagogiques et les coûts indirects forfaitaires.\n"
                "- Options de coûts simplifiés (OCS) : le FSE+ privilégie les forfaits (coûts "
                "unitaires, montants forfaitaires, taux forfaitaires) pour simplifier la gestion.\n"
                "- Le FSE+ fonctionne par appels à projets régionaux et nationaux. Les calendriers "
                "varient selon les régions et les axes prioritaires.\n"
                "- Les projets doivent s'inscrire dans les priorités du programme opérationnel "
                "national ou régional FSE+.\n"
                "- Obligations de suivi : les bénéficiaires doivent renseigner les indicateurs "
                "de réalisation et de résultat (nombre de participants, taux d'insertion, etc.).\n"
                "- Le cofinancement national peut provenir de fonds publics (État, région, "
                "département) ou de fonds privés."
            ),
            "demarche_description": (
                "1. Identifier l'appel à projets FSE+ pertinent sur le site fse.gouv.fr ou "
                "auprès du Conseil régional\n"
                "2. Vérifier l'éligibilité du projet aux priorités du programme opérationnel\n"
                "3. Préparer le dossier de demande de subvention sur la plateforme Ma Démarche FSE+\n"
                "4. Déposer le dossier en ligne avec toutes les pièces justificatives\n"
                "5. Instruction par le service gestionnaire (DGEFP ou Conseil régional)\n"
                "6. Conventionnement et démarrage des actions\n"
                "7. Bilans intermédiaires et final avec justification des dépenses"
            ),
            "documents_requis": [
                "Formulaire de demande de subvention (plateforme Ma Démarche FSE+)",
                "Descriptif détaillé de l'action de formation ou d'insertion",
                "Budget prévisionnel détaillé",
                "Plan de financement avec cofinancements identifiés",
                "Statuts de l'organisme porteur",
                "Attestation de non-assujettissement ou de récupération de TVA",
                "Programme pédagogique détaillé (si formation)",
                "Convention de partenariat le cas échéant",
            ],
            "delai_instruction": "3 à 6 mois",
            "permanent": False,
            "url_officielle": "https://www.fse.gouv.fr/",
            "formulaire_url": "https://ma-demarche.fse.gouv.fr/",
            "tags": [
                "FSE+",
                "Europe",
                "formation",
                "insertion",
                "emploi",
                "métiers du patrimoine",
                "chantier d'insertion",
                "2021-2027",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte (pas spécifique aux MH)

# Propriétaires : structures porteuses (pas les particuliers)
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "mixte"},
    ]
).execute()
print("  ✓ Propriétaires éligibles insérés")

# Travaux : formation liée à la restauration (large)
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "vitraux"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "peintures_murales"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    ]
).execute()
print("  ✓ Travaux éligibles insérés")

# Régions : pas de contrainte géographique (programme national + régional)

# Segments : tous segments (les formations bénéficient à tous)
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
        {"aide_id": aide_id, "segment_code": "prive"},
        {"aide_id": aide_id, "segment_code": "btp"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ FSE+ inséré avec succès (id: {aide_id})")
