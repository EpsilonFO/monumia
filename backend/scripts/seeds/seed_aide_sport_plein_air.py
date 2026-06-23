"""
Seed: Sport et activités de plein air — Aides ANS et collectivités pour l'aménagement sportif
dans le patrimoine.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_sport_plein_air.py
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
            "nom": "Sport et activités de plein air — Aides ANS et dispositifs régionaux",
            "nom_court": "Sport & plein air ANS",
            "description": "Subventions de l'Agence nationale du sport (ANS) et des Régions pour l'aménagement d'équipements sportifs et d'activités de plein air dans ou autour de sites patrimoniaux. Jusqu'à 80 % pour les équipements structurants.",
            "description_longue": (
                "L'Agence nationale du sport (ANS) finance la création, la rénovation et la mise aux normes "
                "d'équipements sportifs via le plan « 5 000 équipements — Génération 2024 » et les subventions "
                "d'équipements structurants. Les collectivités propriétaires de monuments historiques peuvent "
                "mobiliser ces aides pour aménager des espaces sportifs et de plein air dans ou autour de "
                "leurs sites patrimoniaux : parcours sportifs dans les parcs de châteaux, salles d'escalade "
                "dans des bâtiments réhabilités, bases nautiques, équipements équestres, etc. Le taux de "
                "subvention peut atteindre 80 % pour les équipements en QPV ou ZRR/FRR. Les Régions et "
                "Départements proposent également des aides complémentaires pour les projets alliant sport, "
                "nature et patrimoine. L'appel à projets DRAC/DRAJES « Pratiques culture et sport » soutient "
                "spécifiquement les projets croisant culture/patrimoine et pratique sportive."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "Agence nationale du sport (ANS) / DRAC-DRAJES / Régions",
            "montant_max": None,
            "taux_max": 80,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": True,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Bénéficiaires éligibles : collectivités territoriales et leurs groupements, associations sportives, universités publiques, établissements médico-sociaux publics\n"
                "- Les particuliers et entreprises privées ne sont PAS éligibles aux subventions ANS\n"
                "- Types de projets éligibles :\n"
                "  • Création ou rénovation d'équipements sportifs dans ou à proximité de sites patrimoniaux\n"
                "  • Aménagement de parcours sportifs et de plein air dans les parcs et jardins historiques\n"
                "  • Reconversion partielle de bâtiments patrimoniaux en espaces sportifs\n"
                "  • Équipements de sports de nature : escalade, VTT, équitation, nautisme, randonnée\n"
                "  • Équipements de proximité : city stades, terrains multisports, aires de fitness\n"
                "- Plan 5 000 équipements (2024-2026) :\n"
                "  • Doté de 300 M€ sur la période\n"
                "  • Priorité aux QPV (Quartiers Prioritaires de la Ville) et ZRR/FRR (zones rurales)\n"
                "  • Un tiers minimum des équipements financés par région doit être en QPV ou à proximité\n"
                "  • Taux de subvention : jusqu'à 80 % pour les équipements en zone prioritaire\n"
                "  • Taux standard : 30 à 50 % selon le type d'équipement\n"
                "- Équipements structurants (dispositif national ANS) :\n"
                "  • Pour les projets d'envergure régionale ou nationale\n"
                "  • Taux : jusqu'à 50 % (80 % pour les équipements parasportifs)\n"
                "  • Dossier déposé sur la plateforme Infrasport\n"
                "- Appel à projets DRAC/DRAJES « Pratiques culture et sport » :\n"
                "  • Projets croisant pratique culturelle/patrimoniale et pratique sportive\n"
                "  • Candidature annuelle (généralement T1)\n"
                "  • Aide de fonctionnement ou de projet\n"
                "- Conditions communes :\n"
                "  • Le cumul des aides publiques ne doit pas dépasser 80 % du coût total (sauf outre-mer)\n"
                "  • Le porteur doit garantir le caractère sportif pérenne de l'équipement\n"
                "  • Les travaux ne doivent pas commencer avant réception de l'accusé de dépôt via Infrasport\n"
                "  • Pour les sites MH : les travaux touchant aux parties protégées nécessitent l'avis de l'ABF\n"
                "  • Les projets en site classé ou SPR doivent respecter les prescriptions architecturales"
            ),
            "demarche_description": (
                "1. Définir le projet sportif/plein air en lien avec le site patrimonial\n"
                "2. Vérifier l'éligibilité au plan 5 000 équipements ou aux équipements structurants ANS\n"
                "3. Contacter la DRAJES et la DRAC pour le volet « Pratiques culture et sport » si applicable\n"
                "4. Constituer le dossier : programme, plans, devis, plan de financement, délibération\n"
                "5. Déposer le dossier sur la plateforme Infrasport (ANS) ou auprès de la DRAC/DRAJES\n"
                "6. Obtenir les autorisations de travaux (ABF si périmètre MH, permis de construire)\n"
                "7. Attendre la notification d'aide avant de commencer les travaux\n"
                "8. Réaliser les travaux et transmettre les justificatifs pour le versement"
            ),
            "documents_requis": [
                "Programme détaillé du projet sportif",
                "Plans architecturaux de l'équipement",
                "Devis détaillés des travaux et équipements",
                "Plan de financement prévisionnel",
                "Délibération de la collectivité approuvant le projet",
                "Avis de l'ABF (si périmètre MH ou SPR)",
                "Étude d'impact sportif et territorial",
                "Attestation de propriété ou convention d'occupation",
                "RIB de la collectivité",
            ],
            "delai_instruction": "3 à 6 mois",
            "permanent": True,
            "url_officielle": "https://www.agencedusport.fr/aides-et-subventions",
            "formulaire_url": "https://infrasport.agencedusport.fr/",
            "tags": [
                "ANS",
                "sport",
                "plein air",
                "équipements sportifs",
                "5000 équipements",
                "culture et sport",
                "DRAJES",
                "activités nature",
                "QPV",
                "ZRR",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (tous types de sites)

# Propriétaires : collectivités et associations sportives uniquement
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

# Travaux éligibles
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "accessibilite"},
        {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
        {"aide_id": aide_id, "travaux_code": "parcs_jardins"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale → pas de contrainte

# Segments : commune uniquement (les particuliers ne sont pas éligibles ANS)
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
    ]
).execute()
print("  ✓ Segments insérés")

print(f"\n✅ Sport et activités de plein air inséré avec succès (id: {aide_id})")
