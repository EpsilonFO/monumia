"""
Seed: Apprentissage dans les métiers du patrimoine.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_apprentissage_patrimoine.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Apprentissage dans les métiers du patrimoine — Aide à l'embauche d'apprentis",
    "nom_court": "Apprentissage patrimoine",
    "description": "Aide exceptionnelle de l'État aux employeurs qui recrutent des apprentis dans les métiers du patrimoine (tailleur de pierre MH, charpentier, couvreur, maçon du bâti ancien, restaurateur…), couvrant une partie du coût salarial la première année.",
    "description_longue": (
        "L'apprentissage est une voie privilégiée pour former la main-d'œuvre qualifiée "
        "indispensable à la restauration des monuments historiques. Les employeurs (entreprises "
        "du BTP patrimoine, artisans, ateliers de restauration) qui recrutent un apprenti "
        "bénéficient d'une aide exceptionnelle de l'État. En 2026, cette aide est de 5 000 € "
        "pour les entreprises de moins de 250 salariés et de 2 000 € pour les entreprises de "
        "250 salariés et plus (6 000 € pour un apprenti en situation de handicap, quelle que "
        "soit la taille). L'aide est versée la première année du contrat. Les formations "
        "concernées couvrent du CAP au bac+5 (niveau 7 RNCP) : CAP Tailleur de pierre, "
        "BP Tailleur de pierre spécialité MH, CAP Charpentier, CAP Couvreur, BP Maçon, "
        "Bac pro Interventions sur le patrimoine bâti, BTS Bâtiment, Master conservation-"
        "restauration, etc. Les CFA spécialisés incluent les Compagnons du Devoir, les CFA "
        "du BTP, l'École d'Avignon, l'INP. L'apprenti alterne entre le CFA et l'entreprise "
        "d'accueil, intervenant directement sur des chantiers de restauration."
    ),
    "categorie": "etat_drac",
    "type": "subvention",
    "organisme": "Ministère du Travail / ASP (Agence de Services et de Paiement)",
    "montant_max": 6000,
    "taux_max": None,
    "montant_min": 2000,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": False,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- L'aide concerne les contrats d'apprentissage conclus entre le 8 mars 2026 et le 31 décembre 2026\n"
        "  • Les contrats conclus entre le 1er janvier et le 7 mars 2026 NE SONT PAS éligibles (période de suspension)\n"
        "- Montants de l'aide (première année uniquement) :\n"
        "  • 5 000 € pour les entreprises de moins de 250 salariés\n"
        "  • 2 000 € pour les entreprises de 250 salariés et plus (sous condition d'atteindre un seuil d'alternants)\n"
        "  • 6 000 € pour un apprenti en situation de handicap (RQTH), quelle que soit la taille de l'entreprise\n"
        "- L'apprenti doit préparer un diplôme ou titre professionnel de niveau CAP à bac+5 (niveau 3 à 7 RNCP)\n"
        "- Formations patrimoine éligibles (non exhaustif) :\n"
        "  • CAP Tailleur de pierre, CAP Charpentier bois, CAP Couvreur, CAP Maçon, CAP Menuisier\n"
        "  • BP Tailleur de pierre des monuments historiques (remplacé par BP Tailleur de pierre / appareilleur MH à partir de 2025)\n"
        "  • Bac pro Interventions sur le patrimoine bâti (options maçonnerie, charpente, couverture)\n"
        "  • BMA (Brevet des Métiers d'Art) : ébéniste, ferronnerie d'art, vitrail\n"
        "  • BTS Bâtiment, BTMS (Brevet Technique des Métiers Supérieur)\n"
        "  • Licence pro et Master en conservation-restauration du patrimoine\n"
        "- L'employeur peut être une entreprise du BTP patrimoine, un artisan, un atelier de restauration, une collectivité (pour les apprentis en mairie)\n"
        "- Le contrat d'apprentissage est conclu pour une durée de 1 à 3 ans selon la formation\n"
        "- L'apprenti doit avoir entre 16 et 29 ans révolus (pas de limite d'âge pour les travailleurs handicapés)\n"
        "- L'aide est versée mensuellement par l'ASP la première année du contrat\n"
        "- Pour un propriétaire de monument : l'intérêt est indirect — faciliter le recrutement d'apprentis par les entreprises intervenant sur son chantier\n"
        "- Les entreprises de 250+ salariés doivent s'engager à atteindre un taux d'alternants de 5 % de leur effectif au 31/12/2026\n"
        "- L'OPCO de l'entreprise prend en charge les coûts de formation en CFA (en plus de l'aide à l'embauche)"
    ),
    "demarche_description": (
        "1. L'entreprise du patrimoine identifie un besoin en apprenti (tailleur de pierre, charpentier, etc.)\n"
        "2. Trouver un CFA proposant la formation souhaitée (Compagnons du Devoir, CFA BTP, École d'Avignon…)\n"
        "3. Recruter l'apprenti et signer le contrat d'apprentissage (formulaire CERFA FA 13)\n"
        "4. Transmettre le contrat à l'OPCO de l'entreprise dans les 5 jours ouvrables\n"
        "5. L'OPCO transmet à l'ASP pour le versement de l'aide\n"
        "6. L'aide est versée automatiquement chaque mois la première année\n"
        "7. L'apprenti alterne entre le CFA et l'entreprise sur les chantiers de restauration"
    ),
    "documents_requis": [
        "Contrat d'apprentissage (CERFA FA 13)",
        "Convention de formation avec le CFA",
        "Pièce d'identité de l'apprenti",
        "Attestation de l'employeur (taille de l'entreprise)",
        "RQTH de l'apprenti (le cas échéant, pour le montant majoré)",
    ],
    "delai_instruction": "Immédiat (versement automatique après dépôt du contrat à l'OPCO)",
    "permanent": False,
    "url_officielle": "https://travail-emploi.gouv.fr/aides-aux-employeurs-dapprentis",
    "formulaire_url": None,
    "tags": [
        "apprentissage", "métiers du patrimoine", "tailleur de pierre",
        "charpentier", "restauration", "formation", "BTP", "Compagnons du Devoir",
        "aide à l'embauche", "CFA",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : tous niveaux (l'apprenti peut travailler sur tout type de monument)
supabase.table("aides_protections").insert([
    {"aide_id": aide_id, "protection_code": "classe"},
    {"aide_id": aide_id, "protection_code": "inscrit"},
    {"aide_id": aide_id, "protection_code": "non_protege"},
]).execute()
print("  ✓ Protections insérées")

# Propriétaires : pas de contrainte directe (c'est l'entreprise qui embauche l'apprenti)

# Travaux : tous types de travaux patrimoniaux
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
    {"aide_id": aide_id, "travaux_code": "mobilier"},
]).execute()
print("  ✓ Travaux insérés")

# Régions : nationale

# Segments : BTP (entreprises du patrimoine)
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "btp"},
]).execute()
print("  ✓ Segments insérés")

print(f"\n✅ Apprentissage patrimoine inséré avec succès (id: {aide_id})")
