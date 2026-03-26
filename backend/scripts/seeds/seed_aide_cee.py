"""
Seed: Certificats d'Économies d'Énergie (CEE).

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_cee.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Certificats d'Économies d'Énergie (CEE)",
    "nom_court": "CEE",
    "description": "Primes versées par les fournisseurs d'énergie (« obligés ») pour financer des travaux d'économies d'énergie dans les bâtiments. Applicable aux monuments historiques sous conditions.",
    "description_longue": (
        "Le dispositif des Certificats d'Économies d'Énergie (CEE) oblige les fournisseurs "
        "d'énergie à promouvoir l'efficacité énergétique. En pratique, ils financent des primes "
        "aux particuliers, collectivités et entreprises réalisant des travaux d'économie d'énergie. "
        "Les travaux éligibles sont définis par des fiches d'opérations standardisées (BAR-EN pour "
        "l'isolation, BAR-TH pour le chauffage/ventilation). Le montant de la prime dépend du "
        "volume de kWh cumac économisés. La 6ᵉ période (2026-2030) fixe un objectif de 5 250 TWh "
        "cumac. Les monuments historiques sont éligibles au dispositif pour les travaux d'efficacité "
        "énergétique, mais les contraintes patrimoniales (ABF, ACMH) peuvent limiter les solutions "
        "techniques applicables. Aucune condition de ressources n'est requise. Cumulable avec "
        "MaPrimeRénov', l'éco-PTZ et la TVA à 5,5 %."
    ),
    "categorie": "etat_drac",
    "type": "subvention",
    "organisme": "Fournisseurs d'énergie (obligés) — Ministère de la Transition Écologique",
    "montant_max": None,
    "taux_max": None,
    "montant_min": None,
    "plancher": None,
    "base_ttc": True,
    "commune_max_population": None,
    "cofinancement_requis": False,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Tout propriétaire (occupant, bailleur), locataire, collectivité, copropriété ou SCI peut bénéficier des CEE\n"
        "- Aucune condition de ressources\n"
        "- Le logement (ou bâtiment) doit être achevé depuis plus de 2 ans\n"
        "- Les travaux doivent correspondre à une fiche d'opération standardisée du catalogue officiel\n"
        "- Principales fiches résidentielles applicables au patrimoine :\n"
        "  • BAR-EN-101 : Isolation de combles ou de toitures\n"
        "  • BAR-EN-102 : Isolation des murs\n"
        "  • BAR-EN-103 : Isolation d'un plancher\n"
        "  • BAR-EN-104 : Fenêtre ou porte-fenêtre avec vitrage isolant\n"
        "  • BAR-EN-105 : Isolation de toitures terrasses\n"
        "  • BAR-TH-112 : Appareil de chauffage au bois\n"
        "  • BAR-TH-113 : Chaudière biomasse individuelle\n"
        "  • BAR-TH-127 : VMC simple flux hygroréglable\n"
        "  • BAR-TH-125 : VMC double flux haute performance\n"
        "  • BAR-TH-171 : Pompe à chaleur air/eau\n"
        "  • BAR-TH-172 : Pompe à chaleur eau/eau ou sol/eau\n"
        "  • BAR-TH-148 : Chauffe-eau thermodynamique\n"
        "  • BAR-TH-101 : Chauffe-eau solaire individuel\n"
        "- ATTENTION monuments historiques : les travaux doivent respecter les contraintes patrimoniales\n"
        "  • Isolation par l'extérieur souvent impossible sur façades protégées (accord ABF requis)\n"
        "  • Remplacement de fenêtres soumis à validation de l'architecte des bâtiments de France\n"
        "  • Les solutions d'isolation par l'intérieur ou de chauffage peuvent être plus adaptées\n"
        "- Le contrat avec l'obligé (fournisseur d'énergie) doit être signé AVANT le début des travaux\n"
        "- Les travaux doivent être réalisés par un professionnel RGE (Reconnu Garant de l'Environnement)\n"
        "- Le montant de la prime dépend du volume de kWh cumac économisés, variable selon :\n"
        "  • La zone climatique (H1, H2, H3)\n"
        "  • La surface traitée\n"
        "  • Les performances techniques de l'équipement installé\n"
        "- Bonifications « Coup de Pouce » pour certaines opérations (remplacement chaudière fioul/gaz, rénovation performante)\n"
        "- 6ᵉ période du dispositif : 2026-2030 (objectif : 5 250 TWh cumac)\n"
        "- Cumul possible avec : MaPrimeRénov', éco-PTZ, TVA 5,5 %, aides régionales\n"
        "- Cumul interdit : pas de double comptage CEE sur une même opération\n"
        "- Contrôle possible après travaux par organisme d'inspection accrédité"
    ),
    "demarche_description": (
        "1. Identifier les travaux éligibles et la fiche CEE correspondante\n"
        "2. Choisir un obligé (fournisseur d'énergie) ou un délégataire et signer le contrat CEE AVANT le début des travaux\n"
        "3. Faire réaliser les travaux par un artisan RGE\n"
        "4. Transmettre les justificatifs (facture, attestation sur l'honneur, preuve de qualification RGE)\n"
        "5. Recevoir la prime CEE (virement, chèque, bon d'achat ou déduction sur facture selon l'obligé)"
    ),
    "documents_requis": [
        "Attestation sur l'honneur signée par le bénéficiaire et le professionnel",
        "Facture détaillée des travaux (matériaux, performances, surfaces)",
        "Preuve de qualification RGE du professionnel",
        "Cadre de contribution CEE signé avant travaux",
        "Preuve d'ancienneté du logement (+ de 2 ans)",
    ],
    "delai_instruction": "2 à 8 semaines après réception des justificatifs",
    "permanent": True,
    "url_officielle": "https://www.ecologie.gouv.fr/politiques-publiques/dispositif-certificats-deconomies-denergie",
    "formulaire_url": None,
    "tags": [
        "CEE", "certificats économies énergie", "rénovation énergétique",
        "isolation", "chauffage", "prime énergie", "obligés",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte (tous bâtiments éligibles, y compris MH)

# Propriétaires : tous types
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "public_departement"},
    {"aide_id": aide_id, "proprietaire_code": "public_region"},
    {"aide_id": aide_id, "proprietaire_code": "public_etat"},
    {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
    {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
    {"aide_id": aide_id, "proprietaire_code": "mixte"},
]).execute()
print("  ✓ Propriétaires insérés")

# Travaux : isolation, chauffage, ventilation
supabase.table("aides_travaux").insert([
    {"aide_id": aide_id, "travaux_code": "toiture"},
    {"aide_id": aide_id, "travaux_code": "facade"},
    {"aide_id": aide_id, "travaux_code": "menuiserie"},
    {"aide_id": aide_id, "travaux_code": "chauffage"},
    {"aide_id": aide_id, "travaux_code": "ventilation"},
    {"aide_id": aide_id, "travaux_code": "electricite"},
    {"aide_id": aide_id, "travaux_code": "protection_solaire"},
]).execute()
print("  ✓ Travaux insérés")

# Régions : national → pas de contrainte
# Segments : tous → pas de contrainte
# État de conservation : pas de contrainte

print(f"\n✅ CEE inséré avec succès (id: {aide_id})")
