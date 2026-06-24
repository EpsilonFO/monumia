"""
Seed: MaPrimeRénov' — Aide à la rénovation énergétique des logements,
applicable aux monuments historiques sous conditions.

Run:
    cd backend && uv run python3 scripts/seed_aide_maprimerenov.py
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
    supabase.table("aides_v3")
    .insert(
        {
            "nom": "MaPrimeRénov' — Aide à la rénovation énergétique",
            "nom_court": "MaPrimeRénov'",
            "description": "Aide de l'État pour la rénovation énergétique des logements, ouverte aux propriétaires de monuments historiques sous réserve d'autorisation DRAC et d'intervention par un artisan RGE.",
            "description_longue": (
                "MaPrimeRénov' est la principale aide de l'État français pour la rénovation "
                "énergétique des logements, gérée par l'ANAH (Agence Nationale de l'Habitat). "
                "Elle est ouverte à tous les propriétaires occupants et bailleurs, y compris "
                "les propriétaires de monuments historiques classés ou inscrits, à condition "
                "d'obtenir l'autorisation préalable de la DRAC pour les travaux impactant "
                "l'aspect du bâtiment protégé. Le dispositif se décline en deux parcours : "
                "le parcours « par geste » (travaux isolés : chauffage, isolation, ventilation) "
                "et le parcours « rénovation d'ampleur » (rénovation globale avec gain minimum "
                "de 2 classes DPE). Les montants varient selon les revenus du ménage (4 catégories : "
                "très modestes, modestes, intermédiaires, supérieurs) et le type de travaux. "
                "Budget 2026 : 3,6 milliards d'euros. Le logement doit être une résidence "
                "principale ou mis en location comme tel, construit depuis au moins 15 ans "
                "(2 ans en outre-mer pour le parcours par geste)."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "ANAH (Agence Nationale de l'Habitat)",
            "montant_max": 40000,
            "taux_max": 80,
            "montant_min": None,
            "plancher": None,
            "base_ttc": True,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Propriétaires éligibles : propriétaires occupants et bailleurs (personnes "
                "physiques uniquement). Les copropriétés peuvent bénéficier de MaPrimeRénov' "
                "Copropriété.\n"
                "- Le logement doit être une résidence principale (occupé au moins 8 mois/an) "
                "ou mis en location comme résidence principale du locataire.\n"
                "- Ancienneté du logement : construit depuis au moins 15 ans (2 ans en outre-mer "
                "pour le parcours par geste).\n"
                "- Monuments historiques : les propriétaires de MH classés ou inscrits SONT "
                "éligibles, mais doivent obtenir l'autorisation préalable de la DRAC avant "
                "tout travaux modifiant l'aspect du bâtiment protégé. Les travaux doivent être "
                "compatibles avec la conservation du monument.\n"
                "- Artisan RGE (Reconnu Garant de l'Environnement) obligatoire pour la plupart "
                "des travaux.\n"
                "- Parcours « par geste » (travaux isolés) :\n"
                "  • Chauffage : pompe à chaleur air/eau (3 000-5 000 €), géothermique "
                "(6 000-11 000 €), chauffe-eau solaire (2 000-4 000 €)\n"
                "  • Isolation : fenêtres (40-100 €/fenêtre), toiture, murs\n"
                "  • Ventilation : VMC double flux (2 500-3 000 €)\n"
                "  • Audit énergétique : 300-500 €\n"
                "  • Plafond cumulé : 20 000 € sur 5 ans glissants\n"
                "  • ⚠️ En 2026 : l'isolation des murs seule et les chaudières biomasse ne sont "
                "plus éligibles en parcours par geste\n"
                "- Parcours « rénovation d'ampleur » :\n"
                "  • Gain minimum de 2 classes DPE requis\n"
                "  • Accompagnement obligatoire par Mon Accompagnateur Rénov'\n"
                "  • Minimum 2 gestes d'isolation parmi : murs, toiture, fenêtres, planchers\n"
                "  • Plafond : 30 000 € (gain 2 classes) à 40 000 € (gain ≥3 classes)\n"
                "  • Taux de prise en charge :\n"
                "    – Très modestes : 80 %\n"
                "    – Modestes : 60 %\n"
                "    – Intermédiaires : 45 %\n"
                "    – Supérieurs : 10 % (uniquement rénovation d'ampleur)\n"
                "- Barème de revenus (Revenu Fiscal de Référence N-1, personne seule) :\n"
                "  • Très modestes (Bleu) : ≤ 17 363 € (province) / ≤ 24 031 € (Île-de-France)\n"
                "  • Modestes (Jaune) : ≤ 22 259 € (province) / ≤ 29 253 € (Île-de-France)\n"
                "  • Intermédiaires (Violet) : ≤ 31 185 € (province) / ≤ 40 851 € (Île-de-France)\n"
                "  • Supérieurs (Rose) : au-dessus des seuils intermédiaires\n"
                "- Les travaux ne doivent PAS avoir commencé avant le dépôt du dossier.\n"
                "- Délai de réalisation : les travaux doivent être achevés dans les 2 ans "
                "(par geste) ou 3 ans (rénovation d'ampleur) suivant la décision d'attribution.\n"
                "- Cumulable avec : CEE, éco-PTZ, TVA 5,5 %, aides locales. Non cumulable avec "
                "la loi Monuments Historiques pour les mêmes dépenses."
            ),
            "demarche_description": (
                "1. Créer un compte sur maprimerenov.gouv.fr\n"
                "2. Pour les MH : obtenir l'autorisation préalable de la DRAC\n"
                "3. Réaliser un audit énergétique (obligatoire pour la rénovation d'ampleur)\n"
                "4. Faire établir des devis par des artisans RGE\n"
                "5. Déposer le dossier en ligne AVANT le début des travaux\n"
                "6. Attendre la notification d'accord de l'ANAH\n"
                "7. Réaliser les travaux\n"
                "8. Transmettre les factures pour obtenir le versement de la prime"
            ),
            "documents_requis": [
                "Pièce d'identité du propriétaire",
                "Dernier avis d'imposition (revenus N-1)",
                "Devis détaillé(s) de l'artisan RGE",
                "Justificatif de propriété (taxe foncière)",
                "Attestation d'occupation du logement",
                "Audit énergétique (parcours rénovation d'ampleur)",
                "Autorisation DRAC (si monument historique classé ou inscrit)",
                "Certificat RGE de l'artisan",
            ],
            "delai_instruction": "1 à 3 mois",
            "permanent": True,
            "url_officielle": "https://www.maprimerenov.gouv.fr/",
            "formulaire_url": "https://www.maprimerenov.gouv.fr/",
            "tags": [
                "MaPrimeRénov'",
                "ANAH",
                "rénovation énergétique",
                "isolation",
                "chauffage",
                "DPE",
                "pompe à chaleur",
                "RGE",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : tous types (MaPrimeRénov' est ouverte à tous, y compris MH)
# → on n'insère rien = pas de contrainte sur la protection

# Propriétaires : personnes physiques uniquement (occupants et bailleurs)
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
    ]
).execute()
print("  ✓ Propriétaires éligibles insérés")

# Travaux : rénovation énergétique
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "chauffage"},
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "ventilation"},
        {"aide_id": aide_id, "travaux_code": "electricite"},
        {"aide_id": aide_id, "travaux_code": "protection_solaire"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
    ]
).execute()
print("  ✓ Travaux éligibles insérés")

# Régions : aide nationale, pas de contrainte géographique

# Segments : propriétaires privés uniquement
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "prive"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ MaPrimeRénov' inséré avec succès (id: {aide_id})")
