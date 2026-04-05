"""
Seed: France 2030 — Culture immersive et métavers.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_france2030_culture_immersive.py
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
            "nom": "France 2030 — Appel à projets « Culture immersive et métavers »",
            "nom_court": "France 2030 Culture immersive",
            "description": "Subvention France 2030 (opérée par Bpifrance) pour des projets innovants de production et diffusion d'expériences culturelles immersives (VR, AR, métavers, vidéo mapping, son 3D).",
            "description_longue": (
                "L'appel à projets « Culture immersive et métavers », lancé dans le cadre de France 2030 "
                "et opéré par Bpifrance, vise à développer la production et la diffusion d'expériences "
                "immersives de grande qualité au service de la démocratisation culturelle. Il accompagne "
                "des projets innovants permettant un saut technologique dans les environnements immersifs : "
                "mondes virtuels persistants, réalité virtuelle, augmentée ou mixte, vidéo mapping, son 3D. "
                "Le patrimoine (musées, monuments historiques, sites archéologiques) est explicitement visé "
                "comme secteur d'application. Deux volets : aide à l'ingénierie (devis min 80 000 €) et "
                "aide à la réalisation de projet (devis min 400 000 €). Les candidatures sont déposées "
                "sur la plateforme Bpifrance."
            ),
            "categorie": "etat_drac",
            "type": "appel_a_projets",
            "organisme": "Bpifrance (opérateur France 2030) / Ministère de la Culture",
            "montant_max": None,
            "taux_max": None,
            "montant_min": 80000,
            "plancher": 80000,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": True,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Le porteur de projet doit être une entreprise des industries culturelles et créatives (ICC) ou un établissement culturel\n"
                "- L'entreprise doit être économiquement stable (pas en difficulté au sens de la réglementation européenne)\n"
                "- Secteurs éligibles : audiovisuel, cinéma, spectacle vivant, musique, musées et patrimoine, arts visuels, design, architecture, métiers d'art, jeu vidéo, livre, presse, communication, mode\n"
                "- Deux volets d'aide :\n"
                "  • Aide à l'ingénierie : devis global minimum de 80 000 € — financement des études de faisabilité, prototypage, POC\n"
                "  • Aide à la réalisation de projet : devis global minimum de 400 000 € — financement du développement et de la production\n"
                "- Les projets doivent intégrer des technologies immersives : réalité virtuelle (VR), réalité augmentée (AR), réalité mixte (MR), métavers, vidéo mapping, son spatialisé 3D\n"
                "- Le projet doit démontrer un saut technologique par rapport à l'état de l'art\n"
                "- Les projets patrimoniaux sont explicitement éligibles : numérisation 3D de monuments, visites immersives de sites historiques, reconstitutions virtuelles\n"
                "- Le projet doit contribuer à la démocratisation culturelle et à l'élargissement des publics\n"
                "- Les consortiums (entreprise + établissement culturel) sont encouragés\n"
                "- Date limite de dépôt : 25 novembre 2025 à 12h (heure de Paris)\n"
                "- Relèves intermédiaires : 2 juillet 2024, 26 novembre 2024, 25 novembre 2025\n"
                "- Le dépôt se fait exclusivement sur la plateforme en ligne Bpifrance\n"
                "- Le projet ne doit pas avoir déjà commencé avant le dépôt de la demande"
            ),
            "demarche_description": (
                "1. Vérifier l'éligibilité du projet et du porteur sur le site Bpifrance\n"
                "2. Constituer le dossier : description du projet, budget, planning, équipe, partenaires\n"
                "3. Déposer la candidature sur la plateforme en ligne Bpifrance avant la date de relève\n"
                "4. Instruction par Bpifrance et le Ministère de la Culture (comité d'experts)\n"
                "5. Audition éventuelle du porteur de projet\n"
                "6. Notification de la décision et conventionnement\n"
                "7. Versement de l'aide par tranches sur justificatifs d'avancement"
            ),
            "documents_requis": [
                "Dossier de candidature Bpifrance complété",
                "Description détaillée du projet et de l'innovation technologique",
                "Budget prévisionnel détaillé",
                "Planning de réalisation",
                "CV de l'équipe projet",
                "Lettres d'engagement des partenaires (si consortium)",
                "Business plan / modèle économique",
                "Livrables attendus et indicateurs de succès",
            ],
            "delai_instruction": "3 à 6 mois",
            "permanent": False,
            "date_limite": "2025-11-25",
            "url_officielle": "https://www.bpifrance.fr/nos-appels-a-projets-concours/appel-a-projets-culture-immersive-et-metavers",
            "formulaire_url": "https://www.bpifrance.fr/nos-appels-a-projets-concours/appel-a-projets-culture-immersive-et-metavers",
            "tags": [
                "France 2030",
                "culture immersive",
                "métavers",
                "réalité virtuelle",
                "réalité augmentée",
                "Bpifrance",
                "patrimoine numérique",
                "innovation",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (tous monuments éligibles comme sujet de projet)

# Propriétaires : entreprises et établissements culturels (pas de contrainte stricte)

# Travaux : pas de contrainte (aide à l'innovation, pas aux travaux physiques)

# Segments : tous
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
        {"aide_id": aide_id, "segment_code": "prive"},
        {"aide_id": aide_id, "segment_code": "btp"},
    ]
).execute()
print("  ✓ Segments insérés")

# Régions : aide nationale → pas de contrainte

print(f"\n✅ France 2030 Culture immersive inséré avec succès (id: {aide_id})")
