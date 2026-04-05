"""
Seed: FIPHFP — Fonds pour l'Insertion des Personnes Handicapées dans la Fonction Publique.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_fiphfp.py
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
            "nom": "FIPHFP — Aides à l'accessibilité des locaux professionnels publics",
            "nom_court": "FIPHFP Accessibilité",
            "description": "Financement par le FIPHFP des travaux d'accessibilité et d'adaptation des locaux professionnels des employeurs publics, y compris les bâtiments patrimoniaux (mairies, musées, bibliothèques, préfectures).",
            "description_longue": (
                "Le Fonds pour l'Insertion des Personnes Handicapées dans la Fonction Publique (FIPHFP), "
                "créé par la loi du 11 février 2005, finance les actions favorisant l'insertion professionnelle "
                "et le maintien dans l'emploi des personnes en situation de handicap dans les trois fonctions "
                "publiques (État, territoriale, hospitalière). Il prend en charge les travaux d'accessibilité "
                "et d'adaptation des locaux professionnels, y compris les bâtiments patrimoniaux appartenant "
                "à des employeurs publics (mairies classées MH, musées, bibliothèques, préfectures, palais "
                "de justice, hôpitaux historiques). Le taux de prise en charge atteint 100 % pour les locaux "
                "exclusivement professionnels, et 50 à 75 % pour les locaux mixtes (agents + public). "
                "L'enveloppe cumulée peut atteindre 2 M€ pour les plus gros employeurs publics. "
                "Cette aide est complémentaire des subventions DRAC pour la restauration patrimoniale."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "FIPHFP — Caisse des Dépôts et Consignations",
            "montant_max": 2000000,
            "taux_max": 100,
            "montant_min": 200,
            "plancher": None,
            "base_ttc": True,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Réservé aux employeurs publics des trois fonctions publiques : État, territoriale, hospitalière\n"
                "- Les collectivités territoriales (communes, départements, régions), EPCI, syndicats mixtes, "
                "CCAS, établissements publics locaux sont éligibles\n"
                "- Employeurs de 20 agents et plus : doivent être à jour de leurs contributions FIPHFP\n"
                "- Employeurs de moins de 20 agents : éligibles sans obligation de contribution\n"
                "- Locaux exclusivement professionnels (réservés aux agents) : prise en charge jusqu'à 100 %\n"
                "- Locaux mixtes (agents + accueil du public, ex : mairie, musée) :\n"
                "  • Employeurs < 50 agents : jusqu'à 75 %\n"
                "  • Employeurs ≥ 50 agents : jusqu'à 50 %\n"
                "- Plafonds cumulés par taille d'employeur (enveloppe accessibilité) :\n"
                "  • ≤ 19 agents : 50 000 €\n"
                "  • 20-49 agents : 100 000 €\n"
                "  • 50-199 agents : 150 000 €\n"
                "  • 200-999 agents : 200 000 €\n"
                "  • 1 000-4 999 agents : 400 000 €\n"
                "  • 5 000-9 999 agents : 750 000 €\n"
                "  • 10 000-49 999 agents : 1 200 000 €\n"
                "  • 50 000-99 999 agents : 1 500 000 €\n"
                "  • ≥ 100 000 agents : 2 000 000 €\n"
                "- Seuil minimum : 200 € TTC par bénéficiaire\n"
                "- Travaux éligibles : tous travaux d'accessibilité pour tous types de handicap "
                "(rampes, ascenseurs, signalétique, revêtements, bandes podotactiles, éclairage, "
                "systèmes d'alerte, refuges PMR, etc.)\n"
                "- Études de faisabilité et diagnostics accessibilité éligibles\n"
                "- Exclusions : établissements scolaires, lieux de culte, équipements socioculturels, "
                "constructions neuves\n"
                "- Les travaux doivent être compatibles avec les prescriptions de l'ABF si bâtiment protégé MH\n"
                "- Cumul possible avec les subventions DRAC (DRAC pour la restauration, FIPHFP pour l'accessibilité)\n"
                "- Deux modalités : aides ponctuelles (demande unique) ou convention pluriannuelle"
            ),
            "demarche_description": (
                "1. Se connecter à la plateforme PeP'S (portail en ligne du FIPHFP)\n"
                "2. Naviguer vers : Accès aux services > FIPHFP - Demande FIPHFP > Demande d'aide\n"
                "3. Renseigner la description détaillée des travaux d'accessibilité\n"
                "4. Joindre les devis, le diagnostic accessibilité et les justificatifs\n"
                "5. Le FIPHFP instruit le dossier (accord de principe sous ~15 jours si complet)\n"
                "6. Délai total de traitement : environ 90 jours\n"
                "7. Pour les projets importants : possibilité de conventionnement pluriannuel"
            ),
            "documents_requis": [
                "Description détaillée des travaux d'accessibilité prévus",
                "Devis d'entreprises",
                "Diagnostic accessibilité ou étude de faisabilité",
                "Prescription du médecin de prévention (si adaptation de poste individuelle)",
                "Justificatif de mise à jour des contributions FIPHFP",
            ],
            "delai_instruction": "15 jours (accord de principe) à 90 jours (paiement)",
            "permanent": True,
            "url_officielle": "https://www.fiphfp.fr/",
            "formulaire_url": "https://www.fiphfp.fr/employeurs/nos-services/les-aides-financieres-ponctuelles",
            "tags": [
                "FIPHFP",
                "accessibilité",
                "handicap",
                "fonction publique",
                "locaux professionnels",
                "adaptation",
                "PMR",
                "rampe",
                "ascenseur",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (tous bâtiments publics, protégés ou non)

# Propriétaires : employeurs publics uniquement
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : accessibilité et mise en sécurité uniquement
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "accessibilite"},
        {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
        {"aide_id": aide_id, "travaux_code": "electricite"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale → pas de contrainte

# Segments : communes uniquement (les privés ne sont pas employeurs publics)
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ FIPHFP inséré avec succès (id: {aide_id})")
