"""
Seed: TVA réduite 5,5 % sur travaux de rénovation énergétique.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_tva_5_5_renovation_energetique.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "TVA réduite à 5,5 % sur les travaux de rénovation énergétique",
    "nom_court": "TVA 5,5 % réno. énergétique",
    "description": "Taux réduit de TVA à 5,5 % (au lieu de 20 %) applicable aux travaux d'amélioration de la performance énergétique des logements achevés depuis plus de 2 ans.",
    "description_longue": (
        "Les travaux de rénovation énergétique réalisés dans des logements achevés depuis plus "
        "de 2 ans bénéficient d'un taux de TVA réduit à 5,5 % au lieu de 20 %. Ce taux s'applique "
        "sur la fourniture et la pose de matériaux et équipements d'économie d'énergie : isolation "
        "thermique (toiture, murs, planchers, vitrages), systèmes de chauffage performants, "
        "équipements utilisant des énergies renouvelables, ventilation. Le taux réduit s'applique "
        "aussi aux travaux indissociablement liés (travaux annexes réalisés dans la même pièce ou "
        "le même bâti). Le logement peut être une résidence principale ou secondaire. Tous les "
        "propriétaires, locataires et occupants sont éligibles, sans condition de ressources. "
        "Applicable aux monuments historiques à usage d'habitation."
    ),
    "categorie": "fiscalite",
    "type": "exoneration",
    "organisme": "Direction Générale des Finances Publiques (DGFiP) — Ministère de l'Économie",
    "montant_max": None,
    "taux_max": None,
    "montant_min": None,
    "plancher": None,
    "base_ttc": True,
    "commune_max_population": None,
    "cofinancement_requis": False,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Taux de TVA réduit à 5,5 % (au lieu de 20 %) sur les travaux de rénovation énergétique\n"
        "- Le logement doit être achevé depuis plus de 2 ans à la date de début des travaux\n"
        "- Le logement doit être affecté à l'habitation (résidence principale OU secondaire)\n"
        "- Aucune condition de ressources\n"
        "- Bénéficiaires : propriétaires occupants, bailleurs, locataires, occupants à titre gratuit, SCI, syndicats de copropriété\n"
        "- Travaux éligibles au taux de 5,5 % :\n"
        "  • Isolation thermique des parois opaques (murs, toitures, planchers)\n"
        "  • Isolation thermique des parois vitrées (fenêtres, portes-fenêtres, volets isolants)\n"
        "  • Installation de chaudières à haute performance énergétique\n"
        "  • Installation de pompes à chaleur (air/eau, eau/eau, sol/eau)\n"
        "  • Installation d'appareils de chauffage au bois ou biomasse\n"
        "  • Installation de chauffe-eau solaires ou thermodynamiques\n"
        "  • Installation de systèmes de ventilation mécanique (VMC simple ou double flux)\n"
        "  • Équipements de régulation et programmation du chauffage\n"
        "  • Travaux indissociablement liés aux travaux d'amélioration énergétique\n"
        "- Travaux NON éligibles au 5,5 % :\n"
        "  • Travaux de remise en état ou d'entretien courant (taux de 10 %)\n"
        "  • Surélévation, extension, construction neuve (taux de 20 %)\n"
        "  • Aménagements intérieurs sans lien avec la performance énergétique\n"
        "  • Installation de climatisation seule\n"
        "- Le taux de 5,5 % s'applique à la fois à la fourniture des matériaux et à la main-d'œuvre\n"
        "- Les travaux doivent être facturés par une entreprise (pas d'auto-réalisation)\n"
        "- Depuis le 1er janvier 2025, l'attestation Cerfa n'est plus obligatoire pour le taux de 5,5 %\n"
        "- L'entreprise doit mentionner sur le devis et la facture le respect des conditions d'éligibilité\n"
        "- ATTENTION monuments historiques :\n"
        "  • Le taux de 5,5 % s'applique aux MH à usage d'habitation pour les travaux de rénovation énergétique\n"
        "  • Les travaux de restauration patrimoniale pure (non énergétique) relèvent du taux de 10 % (travaux d'amélioration)\n"
        "  • Si un MH n'est pas à usage d'habitation, le taux de 5,5 % ne s'applique pas\n"
        "- Cumul possible avec toutes les autres aides : MaPrimeRénov', CEE, éco-PTZ, aides régionales\n"
        "- Le taux de 5,5 % est un dispositif fiscal permanent (pas de date de fin)"
    ),
    "demarche_description": (
        "1. Vérifier que le logement est achevé depuis plus de 2 ans\n"
        "2. Faire établir un devis par une entreprise mentionnant le taux de TVA à 5,5 %\n"
        "3. L'entreprise applique directement le taux réduit sur la facture\n"
        "4. Conserver la facture comme justificatif en cas de contrôle fiscal"
    ),
    "documents_requis": [
        "Devis mentionnant le taux de TVA à 5,5 %",
        "Facture détaillée de l'entreprise",
    ],
    "delai_instruction": "Immédiat (application directe sur la facture)",
    "permanent": True,
    "url_officielle": "https://www.economie.gouv.fr/cedef/les-fiches-pratiques/comment-sapplique-le-taux-reduit-de-tva-sur-les-travaux-realises-dans-les-logements",
    "formulaire_url": None,
    "tags": [
        "TVA", "5,5 %", "rénovation énergétique", "isolation",
        "chauffage", "fiscalité", "taux réduit",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte (tous logements éligibles, y compris MH)

# Propriétaires : tous types (y compris locataires via l'entreprise)
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "public_departement"},
    {"aide_id": aide_id, "proprietaire_code": "public_region"},
    {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
    {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
    {"aide_id": aide_id, "proprietaire_code": "mixte"},
]).execute()
print("  ✓ Propriétaires insérés")

# Travaux : rénovation énergétique
supabase.table("aides_travaux").insert([
    {"aide_id": aide_id, "travaux_code": "toiture"},
    {"aide_id": aide_id, "travaux_code": "facade"},
    {"aide_id": aide_id, "travaux_code": "menuiserie"},
    {"aide_id": aide_id, "travaux_code": "chauffage"},
    {"aide_id": aide_id, "travaux_code": "plomberie"},
    {"aide_id": aide_id, "travaux_code": "ventilation"},
    {"aide_id": aide_id, "travaux_code": "protection_solaire"},
]).execute()
print("  ✓ Travaux insérés")

# Régions : national → pas de contrainte
# Segments : tous → pas de contrainte
# État de conservation : pas de contrainte

print(f"\n✅ TVA 5,5 % rénovation énergétique inséré avec succès (id: {aide_id})")
