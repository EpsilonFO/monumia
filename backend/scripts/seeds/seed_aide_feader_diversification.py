"""
Seed: FEADER — Diversification des exploitations agricoles.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_feader_diversification.py
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
            "nom": "FEADER — Diversification des exploitations agricoles",
            "nom_court": "FEADER Diversification",
            "description": "Subvention européenne FEADER pour les agriculteurs actifs qui diversifient leur exploitation vers des activités non agricoles, notamment la conversion de bâtiments agricoles patrimoniaux en hébergements touristiques ou lieux de visite.",
            "description_longue": (
                "Le Fonds Européen Agricole pour le Développement Rural (FEADER), dans le cadre du Plan "
                "Stratégique National PAC 2023-2027, soutient les investissements de diversification des "
                "exploitations agricoles vers des activités non agricoles (article 73 du règlement UE 2021/2115). "
                "Cette mesure finance la conversion de bâtiments agricoles patrimoniaux (granges, corps de ferme, "
                "bergeries, pigeonniers) en hébergements touristiques (gîtes, chambres d'hôtes, tables d'hôtes), "
                "fermes pédagogiques, ou lieux de visite à caractère patrimonial et culturel. Le taux de base "
                "est de 40 % HT, avec des bonifications (+10 % jeune agriculteur, +10 % agriculture biologique) "
                "pouvant porter le taux à 60 %. Plafond de 200 000 € HT de dépenses éligibles par dossier "
                "individuel. Depuis 2023, le dispositif est géré par les Régions qui lancent leurs propres "
                "appels à projets."
            ),
            "categorie": "europe",
            "type": "subvention",
            "organisme": "Conseil Régional (autorité de gestion FEADER) — cofinancement Union européenne",
            "montant_max": 120000,
            "taux_max": 60,
            "montant_min": 5000,
            "plancher": 5000,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Bénéficiaires : agriculteurs actifs (exploitants affiliés MSA) — condition impérative\n"
                "- Formes juridiques éligibles : exploitant individuel, GAEC, EARL, SCEA, SARL agricole\n"
                "- Coopératives agricoles (CUMA, SCA, SICA) éligibles pour les projets collectifs "
                "(plafond 250 000 € HT)\n"
                "- L'exploitation doit être située dans la région qui gère l'appel à projets\n"
                "- Taux de base : 40 % des dépenses éligibles HT\n"
                "- Bonification jeune agriculteur (bénéficiaire DJA/AIJA) : +10 %\n"
                "- Bonification agriculture biologique (certifié ou en conversion) : +10 %\n"
                "- Taux maximum cumulé : 60 %\n"
                "- Plafond dépenses éligibles : 200 000 € HT (individuel) ou 250 000 € HT (collectif)\n"
                "- Seuil minimum de dépenses éligibles : 5 000 € HT\n"
                "- Seuil minimum par facture : 1 000 €\n"
                "- Principe de non-commencement anticipé : aucune dépense avant le dépôt de la demande\n"
                "- Maximum 3 gîtes financés par exploitation\n"
                "- Activités éligibles : hébergement touristique (gîtes, chambres d'hôtes), tables d'hôtes, "
                "fermes-auberges, fermes pédagogiques, activités patrimoniales et culturelles, écotourisme, "
                "activités équestres, transformation et vente directe\n"
                "- Dépenses éligibles : construction, rénovation, conversion de bâtiments, équipements neufs, "
                "intégration paysagère, études et honoraires (plafonnés à 10 % du total)\n"
                "- Auto-construction autorisée mais valorisée au taux horaire du SMIC\n"
                "- Obligation de maintien des actifs financés pendant 5 ans après le dernier paiement\n"
                "- Pas de cumul avec FEDER ou FSE+ sur les mêmes postes de dépenses\n"
                "- Règle de minimis applicable (200 000 € sur 3 exercices fiscaux)\n"
                "- Obligations de publicité européenne sur le projet\n"
                "- Les calendriers et critères de sélection varient selon les régions "
                "(consulter le site Europe de sa région)"
            ),
            "demarche_description": (
                "1. Identifier l'appel à projets FEADER diversification de sa région "
                "(site du Conseil Régional ou Chambre d'Agriculture)\n"
                "2. Contacter la Chambre d'Agriculture départementale pour vérifier l'éligibilité\n"
                "3. Constituer le dossier : description du projet, devis, plan de financement, business plan\n"
                "4. Déposer la demande via la plateforme numérique régionale "
                "(mesdemarches.iledefrance.fr, europac.laregion.fr, e-Synergie, etc.)\n"
                "5. Instruction par les services régionaux (2 à 6 mois)\n"
                "6. Passage en comité de sélection\n"
                "7. Convention de subvention et démarrage des travaux\n"
                "8. Demandes de paiement sur justificatifs"
            ),
            "documents_requis": [
                "Justificatif du statut d'agriculteur actif (attestation MSA)",
                "Numéro SIRET de l'exploitation",
                "Statuts de la structure (si société)",
                "Comptes financiers des 3 derniers exercices",
                "Description détaillée du projet de diversification",
                "Devis d'entreprises",
                "Plan de financement prévisionnel",
                "Business plan sur 4 ans",
                "Attestation de non-commencement des travaux",
                "Autorisations administratives (permis de construire, autorisation ABF si MH)",
                "RIB",
            ],
            "delai_instruction": "2 à 6 mois",
            "permanent": False,
            "url_officielle": "https://www.europe-en-france.gouv.fr/fr/fonds-europeens-2021-2027/fonds-europeen-agricole-pour-le-developpement-rural-FEADER",
            "formulaire_url": None,
            "tags": [
                "FEADER",
                "diversification agricole",
                "agritourisme",
                "gîte rural",
                "chambre d'hôtes",
                "ferme pédagogique",
                "patrimoine agricole",
                "conversion bâtiment",
                "Europe",
                "PAC",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (bâtiments agricoles protégés ou non)

# Propriétaires : exploitants agricoles (personnes physiques ou SCI/sociétés agricoles)
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux éligibles : rénovation et aménagement de bâtiments
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "couverture"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "electricite"},
        {"aide_id": aide_id, "travaux_code": "plomberie"},
        {"aide_id": aide_id, "travaux_code": "chauffage"},
        {"aide_id": aide_id, "travaux_code": "accessibilite"},
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale (gérée par chaque région) → pas de contrainte

# Segments : privés (exploitants agricoles)
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "prive"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ FEADER Diversification inséré avec succès (id: {aide_id})")
