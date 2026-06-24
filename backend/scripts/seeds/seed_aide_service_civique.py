"""
Seed: Service Civique — Patrimoine.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_service_civique.py
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
            "nom": "Service Civique — Missions patrimoine",
            "nom_court": "Service Civique",
            "description": "Accueil de volontaires en Service Civique pour des missions de valorisation, médiation et préservation du patrimoine, avec une indemnité prise en charge par l'État.",
            "description_longue": (
                "Le Service Civique, créé par la loi du 10 mars 2010, permet à des jeunes de 16 à 25 ans "
                "(30 ans pour les personnes en situation de handicap) de s'engager pour une durée de 6 à 12 "
                "mois dans une mission d'intérêt général. Le domaine 'Culture et loisirs' couvre les missions "
                "liées au patrimoine : médiation culturelle, sensibilisation du public, inventaire du patrimoine, "
                "animation d'un site historique, participation à des chantiers participatifs de restauration, "
                "valorisation numérique, organisation d'événements patrimoniaux (Journées du Patrimoine, etc.). "
                "L'État verse directement au volontaire une indemnité mensuelle de 620,14 € (montant 2024). "
                "La structure d'accueil verse un complément de 115,45 €/mois (en nature ou en espèces). "
                "Le coût réel pour la structure est donc très limité (environ 115 €/mois), ce qui en fait "
                "un levier intéressant pour les propriétaires de monuments souhaitant développer la "
                "valorisation et l'ouverture au public de leur site. Les structures d'accueil éligibles "
                "sont les associations, fondations, collectivités et établissements publics agréés par "
                "l'Agence du Service Civique."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "Agence du Service Civique (État)",
            "montant_max": None,
            "taux_max": None,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Cadre juridique : loi n° 2010-241 du 10 mars 2010 relative au Service Civique\n"
                "- Volontaires éligibles : jeunes de 16 à 25 ans (30 ans pour les personnes handicapées), "
                "de nationalité française, européenne ou résidant en France depuis plus d'un an\n"
                "- Durée de la mission : 6 à 12 mois, 24 à 35 heures par semaine\n"
                "- Indemnité versée par l'État au volontaire : 620,14 €/mois (montant 2024)\n"
                "- Majoration sur critères sociaux : +115,45 €/mois pour les boursiers ou RSA\n"
                "- Complément versé par la structure d'accueil : 115,45 €/mois (en nature ou espèces)\n"
                "- Coût total pour la structure : environ 115 €/mois + frais d'encadrement\n"
                "- Structures d'accueil éligibles :\n"
                "  • Associations loi 1901 agréées par l'Agence du Service Civique\n"
                "  • Fondations reconnues d'utilité publique\n"
                "  • Collectivités territoriales (communes, départements, régions)\n"
                "  • Établissements publics (musées, CAUE, parcs naturels)\n"
                "  • Organismes HLM\n"
                "- Les entreprises privées, SCI et personnes physiques ne peuvent PAS accueillir directement "
                "de volontaires en Service Civique\n"
                "- Un propriétaire privé peut bénéficier du dispositif si une association porteuse agréée "
                "accueille le volontaire et l'affecte à une mission sur son monument\n"
                "- La mission doit être d'intérêt général et ne pas se substituer à un emploi salarié\n"
                "- Missions patrimoine possibles :\n"
                "  • Médiation culturelle et accueil du public sur un site historique\n"
                "  • Sensibilisation au patrimoine auprès des scolaires et du grand public\n"
                "  • Inventaire et documentation du patrimoine local\n"
                "  • Valorisation numérique (site web, réseaux sociaux, visites virtuelles)\n"
                "  • Participation à des chantiers participatifs de restauration\n"
                "  • Organisation d'événements (JEP, concerts, expositions)\n"
                "  • Animation d'un lieu patrimonial\n"
                "- Le volontaire ne doit PAS réaliser de travaux techniques de restauration "
                "(réservés aux professionnels qualifiés)\n"
                "- La structure doit obtenir un agrément de l'Agence du Service Civique "
                "(agrément collectif ou individuel)\n"
                "- Formation civique et citoyenne obligatoire (2 jours minimum)\n"
                "- Un tuteur doit être désigné au sein de la structure d'accueil\n"
                "- Le Service Civique n'est pas compatible avec un emploi salarié à temps plein"
            ),
            "demarche_description": (
                "1. Vérifier l'éligibilité de la structure (association, collectivité, fondation)\n"
                "2. Demander l'agrément Service Civique auprès de l'Agence du Service Civique "
                "(via la plateforme en ligne)\n"
                "3. Rédiger la fiche de mission patrimoine et la publier sur service-civique.gouv.fr\n"
                "4. Sélectionner le volontaire parmi les candidatures reçues\n"
                "5. Signer le contrat d'engagement de Service Civique\n"
                "6. Désigner un tuteur et organiser la formation civique et citoyenne\n"
                "7. Accompagner le volontaire pendant toute la durée de sa mission\n"
                "8. Établir le bilan de mission en fin d'engagement"
            ),
            "documents_requis": [
                "Demande d'agrément Service Civique (formulaire en ligne)",
                "Statuts de la structure d'accueil",
                "Fiche de mission détaillée (objectifs, activités, encadrement)",
                "Contrat d'engagement de Service Civique",
                "Attestation de formation civique et citoyenne",
            ],
            "delai_instruction": "1 à 3 mois (agrément) puis recrutement continu",
            "permanent": True,
            "url_officielle": "https://www.service-civique.gouv.fr",
            "formulaire_url": "https://www.service-civique.gouv.fr/organisme/accueillir-un-volontaire",
            "tags": [
                "Service Civique",
                "volontariat",
                "jeunes",
                "médiation culturelle",
                "valorisation",
                "patrimoine",
                "mission d'intérêt général",
                "ouverture au public",
                "animation",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (le Service Civique s'applique à tout type de patrimoine)

# Propriétaires : structures d'accueil agréées (asso, collectivités, fondations)
# Mais un proprio privé peut bénéficier via une asso porteuse → pas de contrainte stricte
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()

# Travaux : pas de travaux techniques — missions de valorisation uniquement
# → pas de contrainte sur les travaux (le Service Civique est complémentaire)

# Régions : aide nationale → pas de contrainte

# Segments : commune et associations principalement
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
    ]
).execute()

# État de conservation : pas de contrainte

print(f"\n✅ Service Civique — Missions patrimoine inséré avec succès (id: {aide_id})")
