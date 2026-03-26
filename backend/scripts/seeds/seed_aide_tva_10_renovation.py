"""
Seed: TVA réduite 10 % sur travaux de rénovation (hors énergie) — art. 279-0 bis CGI.

Run:
    cd backend && uv run python3 scripts/seed_aide_tva_10_renovation.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "TVA au taux réduit de 10 % sur les travaux de rénovation (hors amélioration énergétique)",
    "nom_court": "TVA 10 % rénovation",
    "description": "Taux de TVA intermédiaire de 10 % applicable aux travaux d'amélioration, de transformation, d'aménagement et d'entretien portant sur des locaux à usage d'habitation achevés depuis plus de 2 ans (hors travaux d'amélioration énergétique relevant du taux de 5,5 %).",
    "description_longue": (
        "L'article 279-0 bis du Code général des impôts prévoit l'application d'un taux "
        "intermédiaire de TVA à 10 % (au lieu du taux normal de 20 %) sur les travaux "
        "d'amélioration, de transformation, d'aménagement et d'entretien réalisés dans des "
        "locaux à usage d'habitation achevés depuis plus de deux ans. Ce taux s'applique "
        "à la main-d'œuvre et aux matériaux fournis par l'entreprise. Il ne couvre pas les "
        "travaux de construction ou de reconstruction, ni les gros équipements listés par "
        "décret (ascenseurs, systèmes de climatisation, installations sanitaires complètes, "
        "chaudières). Les travaux d'amélioration de la performance énergétique relèvent quant "
        "à eux du taux super-réduit de 5,5 %. Depuis le 1er mars 2025, l'attestation papier "
        "n'est plus requise : une simple mention sur le devis ou la facture certifiant le "
        "respect des conditions suffit. Ce dispositif est permanent et s'applique sur tout "
        "le territoire français."
    ),
    "categorie": "fiscalite",
    "type": "exoneration",
    "organisme": "Direction Générale des Finances Publiques (DGFiP)",
    "montant_max": None,
    "taux_max": None,
    "montant_min": None,
    "plancher": None,
    "base_ttc": True,
    "commune_max_population": None,
    "cofinancement_requis": False,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Le local doit être à usage d'habitation (résidence principale ou secondaire, logement locatif). "
        "Les locaux utilisés à des fins exclusivement professionnelles sont exclus.\n"
        "- Si le local est à usage mixte (habitation + professionnel), le taux de 10 % s'applique "
        "uniquement à la partie habitation, sauf si l'habitation représente au moins 50 % de la surface totale, "
        "auquel cas il s'applique à l'ensemble.\n"
        "- Le local doit être achevé depuis plus de 2 ans à la date du début des travaux.\n"
        "- Les travaux doivent être facturés par une entreprise (les achats de matériaux par le particulier "
        "lui-même restent au taux normal de 20 %).\n"
        "- Sont exclus du taux de 10 % :\n"
        "  • Les travaux de construction ou de reconstruction (surélévation, ajout de surface > 10 % "
        "de la surface existante, remise à l'état neuf de plus des 2/3 des éléments de second œuvre)\n"
        "  • La fourniture d'équipements ménagers ou mobiliers\n"
        "  • L'acquisition de gros équipements : systèmes de climatisation, ascenseurs et monte-charges, "
        "installations sanitaires complètes (baignoire, douche, cabine de douche, receveur, ensemble balnéo), "
        "chaudières de toute nature (y compris chaudières à condensation, sauf si elles relèvent de la TVA à 5,5 %)\n"
        "  • Depuis le 1er mars 2025 : fourniture et pose de chaudières susceptibles d'utiliser des combustibles "
        "fossiles (gaz, fioul) — taux normal de 20 % applicable\n"
        "  • Les travaux d'aménagement et d'entretien des espaces verts\n"
        "  • Les travaux de nettoyage\n"
        "- Travaux éligibles au taux de 10 % (liste non exhaustive) :\n"
        "  • Réfection de toiture et charpente\n"
        "  • Ravalement et traitement de façade\n"
        "  • Remplacement de fenêtres, volets, portes\n"
        "  • Travaux de maçonnerie, plâtrerie, peinture intérieure et extérieure\n"
        "  • Plomberie (hors installation sanitaire complète)\n"
        "  • Électricité (mise aux normes, rénovation)\n"
        "  • Carrelage, revêtements de sol et de mur\n"
        "  • Menuiseries intérieures et extérieures\n"
        "  • Travaux d'accessibilité (rampes, élargissement de portes)\n"
        "  • Restauration de vitraux, peintures murales, boiseries, stucs dans un logement\n"
        "  • Réfection de la couverture (ardoises, tuiles, zinc)\n"
        "- Pour les monuments historiques : le classement ou l'inscription ne donne pas automatiquement "
        "droit au taux réduit. Seul compte l'usage d'habitation du local. Un château classé MH "
        "mais affecté à l'habitation bénéficie du taux de 10 % pour ses travaux de rénovation.\n"
        "- Le taux de 10 % s'applique en France métropolitaine. En Corse, le taux applicable "
        "est de 10 %. Dans les DOM (Guadeloupe, Martinique, Réunion), le taux réduit est de 2,1 %.\n"
        "- Depuis le 1er mars 2025, l'attestation papier (formulaire 1300-SD / 1301-SD) n'est plus requise. "
        "Le devis ou la facture doit simplement porter la mention certifiant le respect des conditions.\n"
        "- Le preneur (client) reste responsable de la bonne application du taux réduit. En cas de "
        "non-respect des conditions, le complément de TVA est dû par le preneur."
    ),
    "demarche_description": (
        "1. Vérifier que le logement est achevé depuis plus de 2 ans\n"
        "2. S'assurer que les travaux ne constituent pas une construction/reconstruction\n"
        "3. Demander à l'entreprise d'appliquer le taux de 10 % sur le devis et la facture\n"
        "4. Depuis mars 2025 : vérifier que le devis ou la facture porte la mention certifiant "
        "le respect des conditions d'application du taux réduit\n"
        "5. Conserver les factures pendant 5 ans (délai de reprise de l'administration fiscale)"
    ),
    "documents_requis": [
        "Devis ou facture de l'entreprise portant la mention de certification du taux réduit",
        "Justificatif d'ancienneté du logement (taxe foncière, permis de construire, etc.)",
    ],
    "delai_instruction": None,
    "permanent": True,
    "url_officielle": "https://www.economie.gouv.fr/particuliers/tva-taux-reduits-travaux",
    "formulaire_url": None,
    "tags": [
        "TVA", "fiscalité", "rénovation", "travaux", "logement",
        "taux réduit", "10 %", "habitation", "entretien", "amélioration",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte (le taux réduit dépend de l'usage habitation, pas de la protection)
# → on n'insère rien dans aides_protections

# Propriétaires : tous types éligibles (particuliers, SCI, collectivités, associations)
# → on n'insère rien dans aides_proprietaires (= pas de contrainte)

# Travaux : large spectre de travaux de rénovation (hors énergie)
supabase.table("aides_travaux").insert([
    {"aide_id": aide_id, "travaux_code": "toiture"},
    {"aide_id": aide_id, "travaux_code": "charpente"},
    {"aide_id": aide_id, "travaux_code": "couverture"},
    {"aide_id": aide_id, "travaux_code": "facade"},
    {"aide_id": aide_id, "travaux_code": "maconnerie"},
    {"aide_id": aide_id, "travaux_code": "vitraux"},
    {"aide_id": aide_id, "travaux_code": "peintures_murales"},
    {"aide_id": aide_id, "travaux_code": "menuiserie"},
    {"aide_id": aide_id, "travaux_code": "electricite"},
    {"aide_id": aide_id, "travaux_code": "plomberie"},
    {"aide_id": aide_id, "travaux_code": "accessibilite"},
    {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
    {"aide_id": aide_id, "travaux_code": "restauration_generale"},
    {"aide_id": aide_id, "travaux_code": "mobilier"},
    {"aide_id": aide_id, "travaux_code": "protection_solaire"},
]).execute()
print("  ✓ Travaux éligibles insérés")

# Régions : aide nationale → pas de contrainte
# Départements : pas de contrainte
# Segments : tous segments éligibles → pas de contrainte
# État de conservation : pas de contrainte

print(f"\n✅ TVA 10 % rénovation insérée avec succès (id: {aide_id})")
