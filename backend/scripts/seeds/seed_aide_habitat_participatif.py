"""
Seed: Habitat participatif et coopératives d'habitants — Aides pour la
transformation de bâtiments patrimoniaux en habitat participatif (loi ALUR,
ANAH, Banque des Territoires).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_habitat_participatif.py
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
            "nom": "Habitat participatif et coopératives d'habitants — Aides à la réhabilitation patrimoniale",
            "nom_court": "Habitat participatif patrimoine",
            "description": "Dispositifs d'aide pour la transformation de bâtiments patrimoniaux en habitat participatif ou coopératives d'habitants : prêts bonifiés (PLS/PLAI), aides ANAH, ingénierie AMO et Bail Réel Solidaire.",
            "description_longue": (
                "La loi ALUR de 2014 (articles L.200-1 à L.200-13 du Code de la Construction et de "
                "l'Habitation) a créé un cadre juridique pour l'habitat participatif en reconnaissant "
                "deux formes : les coopératives d'habitants (propriété collective, parts sociales, "
                "anti-spéculation) et les sociétés d'autopromotion (propriété individuelle dans un "
                "cadre collectif). Ces montages permettent de réhabiliter des bâtiments patrimoniaux "
                "anciens (corps de ferme, anciennes usines, bâtiments conventuels, immeubles historiques) "
                "en logements participatifs mêlant espaces privatifs et espaces communs partagés. "
                "Plusieurs sources de financement sont mobilisables : les prêts locatifs sociaux "
                "(PLS/PLAI) de la Banque des Territoires à taux bonifiés, les aides de l'ANAH pour la "
                "réhabilitation de logements dégradés (MaPrimeRénov' Copropriétés), la TVA réduite à "
                "5,5 % pour les travaux de rénovation énergétique, et les subventions d'Assistance à "
                "Maîtrise d'Ouvrage (AMO) des collectivités locales. Les Organismes de Foncier Solidaire "
                "(OFS) peuvent proposer un Bail Réel Solidaire (BRS) permettant de dissocier le foncier "
                "du bâti et de réduire significativement le coût d'acquisition. Plusieurs régions "
                "(Auvergne-Rhône-Alpes, Bretagne, Nouvelle-Aquitaine, Île-de-France) proposent des "
                "appels à projets ou des aides spécifiques pour l'habitat participatif. Le réseau "
                "Coordin'action Nationale de l'Habitat Participatif accompagne les porteurs de projets."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "ANAH / Banque des Territoires / Collectivités territoriales / OFS",
            "montant_max": None,
            "taux_max": None,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": True,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Le projet doit s'inscrire dans le cadre juridique de la loi ALUR (coopérative "
                "d'habitants ou société d'autopromotion).\n"
                "- Le bâtiment doit être destiné à un usage principal d'habitation après réhabilitation.\n"
                "- Pour les prêts PLS/PLAI (Banque des Territoires) : le projet doit être porté par un "
                "organisme HLM, une coopérative d'habitants agréée ou une SCI coopérative (SCCC). "
                "Taux bonifiés indexés sur le Livret A.\n"
                "- Pour les aides ANAH (MaPrimeRénov' Copropriétés) : le bâtiment doit avoir plus de "
                "15 ans, les travaux doivent viser la rénovation énergétique, réalisés par des artisans RGE. "
                "Montant jusqu'à 25 000 € par logement pour les ménages très modestes.\n"
                "- TVA réduite à 5,5 % : applicable aux travaux de rénovation énergétique sur logements "
                "de plus de 2 ans.\n"
                "- Bail Réel Solidaire (BRS) : le projet doit être situé dans le périmètre d'un OFS agréé. "
                "Dissociation foncier/bâti, obligation d'occupation comme résidence principale, "
                "plafonds de ressources et de prix de cession.\n"
                "- Les bâtiments patrimoniaux (MH, SPR, ZPPAUP) sont éligibles sous réserve de "
                "compatibilité des travaux avec les prescriptions de l'ABF.\n"
                "- AMO subventionnée : les collectivités (communes, EPCI, régions) peuvent prendre en "
                "charge tout ou partie de l'assistance à maîtrise d'ouvrage nécessaire au montage du "
                "projet participatif.\n"
                "- Les projets en zone de revitalisation rurale (ZRR) ou dans le cadre de programmes "
                "Action Cœur de Ville / Petites Villes de Demain bénéficient de bonifications.\n"
                "- Le groupe d'habitants doit être constitué et engagé dans une démarche collective "
                "documentée (charte, statuts, règlement).\n"
                "- Cumul possible avec les dispositifs fiscaux patrimoniaux (Malraux, MH) sous conditions."
            ),
            "demarche_description": (
                "1. Constituer le groupe d'habitants et définir le projet collectif (charte, gouvernance)\n"
                "2. Identifier le bâtiment patrimonial et évaluer sa faisabilité technique et juridique\n"
                "3. Se rapprocher de la Coordin'action Nationale de l'Habitat Participatif pour l'accompagnement\n"
                "4. Constituer la structure juridique (coopérative d'habitants, SCCC, société d'autopromotion)\n"
                "5. Solliciter une AMO auprès de la collectivité locale\n"
                "6. Déposer les demandes de financement (ANAH, Banque des Territoires, aides régionales)\n"
                "7. Obtenir les autorisations d'urbanisme (permis de construire, accord ABF si MH/SPR)\n"
                "8. Réaliser les travaux de réhabilitation\n"
                "9. Installation des habitants et mise en place de la gestion collective"
            ),
            "documents_requis": [
                "Statuts de la coopérative d'habitants ou société d'autopromotion",
                "Charte du groupe d'habitants",
                "Étude de faisabilité technique et financière",
                "Plan de financement prévisionnel",
                "Devis détaillés des travaux de réhabilitation",
                "Attestation de propriété ou promesse de vente du bâtiment",
                "Dossier de demande d'aide ANAH (si applicable)",
                "Demande de prêt PLS/PLAI (si applicable)",
                "Autorisation d'urbanisme ou permis de construire",
                "Accord ABF (si monument historique ou SPR)",
            ],
            "delai_instruction": "6 à 18 mois (montage global du projet)",
            "permanent": True,
            "url_officielle": "https://www.habitatparticipatif.eu",
            "formulaire_url": None,
            "tags": [
                "habitat participatif",
                "coopérative d'habitants",
                "loi ALUR",
                "réhabilitation",
                "patrimoine",
                "ANAH",
                "Banque des Territoires",
                "BRS",
                "OFS",
                "logement social",
                "AMO",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte stricte (tous types de bâtiments patrimoniaux)

# Propriétaires : associations, communes, SCI, personnes physiques
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
        {"aide_id": aide_id, "proprietaire_code": "mixte"},
    ]
).execute()
print("  ✓ Propriétaires éligibles insérés")

# Travaux : réhabilitation large
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "electricite"},
        {"aide_id": aide_id, "travaux_code": "plomberie"},
        {"aide_id": aide_id, "travaux_code": "chauffage"},
        {"aide_id": aide_id, "travaux_code": "accessibilite"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    ]
).execute()
print("  ✓ Travaux éligibles insérés")

# Régions : aide nationale → pas de contrainte

# Segments : privé et communes
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
        {"aide_id": aide_id, "segment_code": "prive"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : priorité aux bâtiments dégradés mais pas exclusif
supabase.table("aides_etats_conservation").insert(
    [
        {"aide_id": aide_id, "etat_conservation_code": "moyen"},
        {"aide_id": aide_id, "etat_conservation_code": "mauvais"},
        {"aide_id": aide_id, "etat_conservation_code": "peril"},
    ]
).execute()
print("  ✓ États de conservation insérés")

print(f"\n✅ Habitat participatif inséré avec succès (id: {aide_id})")
