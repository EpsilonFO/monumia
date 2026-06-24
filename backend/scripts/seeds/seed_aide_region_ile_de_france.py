"""
Seed: Aide régionale patrimoine — Île-de-France.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_region_ile_de_france.py
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
            "nom": "Aide régionale à la restauration du patrimoine immobilier protégé — Île-de-France",
            "nom_court": "Aide patrimoine Île-de-France",
            "description": "Subvention de la Région Île-de-France pour la restauration du patrimoine protégé MH. Taux de 20 % (classé) à 30 % (inscrit), plafonné à 1 M€ de dépenses éligibles par tranche.",
            "description_longue": (
                "La Région Île-de-France soutient la restauration du patrimoine francilien protégé au titre "
                "des monuments historiques. Le taux de subvention est de 20 % pour les monuments classés et "
                "30 % pour les monuments inscrits (inversion volontaire par rapport à la DRAC qui finance "
                "davantage les classés). L'assiette éligible comprend le coût des travaux et les honoraires "
                "de maîtrise d'œuvre, plafonnée à 1 million d'euros par tranche de travaux. Les propriétaires "
                "publics (communes, EPCI, départements) et privés (personnes physiques, SCI, associations, "
                "fondations) sont éligibles, à l'exclusion de l'État. La base de calcul est HT pour les "
                "propriétaires publics et TTC pour les propriétaires privés. Le cumul des aides publiques "
                "ne peut excéder 80 % du coût total. La Région propose également un dispositif complémentaire "
                "pour le patrimoine non protégé labellisé « Patrimoine d'intérêt régional » (30 %, plafond "
                "500 000 €) et une aide spécifique pour les objets mobiliers protégés (plafond 15 000 €)."
            ),
            "categorie": "region",
            "type": "subvention",
            "organisme": "Région Île-de-France",
            "montant_max": 1000000,
            "taux_max": 30,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": True,
            "conditions_eligibilite_detail": (
                "- Patrimoine situé en Île-de-France (départements 75, 77, 78, 91, 92, 93, 94, 95)\n"
                "- Monuments classés MH : taux de subvention de 20 % des dépenses éligibles\n"
                "- Monuments inscrits MH : taux de subvention de 30 % des dépenses éligibles\n"
                "- Inversion volontaire des taux par rapport à la DRAC : la Région donne plus aux inscrits (moins aidés par la DRAC) et moins aux classés (davantage aidés par la DRAC)\n"
                "- Assiette éligible : coût des travaux + honoraires de maîtrise d'œuvre (hors études préalables)\n"
                "- Plafond de dépenses éligibles : 1 000 000 € par tranche de travaux\n"
                "- Base de calcul : HT pour les propriétaires publics, TTC pour les propriétaires privés\n"
                "- Propriétaires éligibles : communes, EPCI, départements, associations (loi 1901), fondations, personnes physiques, SCI\n"
                "- Le bien ne doit PAS appartenir à l'État\n"
                "- Le cumul des aides publiques ne peut pas excéder 80 % du coût total du projet\n"
                "- Le projet doit avoir été discuté au préalable avec la DRAC et l'ABF\n"
                "- Une demande d'autorisation de travaux doit avoir été déposée\n"
                "- Ne sont PAS éligibles : acquisitions foncières, assurances dommages, démolitions, dépollution, VRD\n"
                "- Patrimoine non protégé : éligible via le dispositif complémentaire « Patrimoine d'intérêt régional » (label régional requis, taux 30 %, plafond 500 000 €)\n"
                "- Objets mobiliers protégés MH : aide spécifique plafonnée à 15 000 € (20 % classé / 30 % inscrit)\n"
                "- Maisons et ateliers d'artistes remarquables : aide spécifique à 40 % des dépenses éligibles\n"
                "- Demandes déposées en continu sur mesdemarches.iledefrance.fr\n"
                "- Le dossier est instruit par la Direction de la culture de la Région"
            ),
            "demarche_description": (
                "1. Consulter les dispositifs patrimoine sur le site mesdemarches.iledefrance.fr\n"
                "2. Prendre contact avec la Direction de la culture de la Région Île-de-France pour vérifier l'éligibilité\n"
                "3. Constituer le dossier : descriptif du patrimoine, programme de travaux, devis, plan de financement\n"
                "4. Déposer le dossier en ligne sur la plateforme mesdemarches.iledefrance.fr\n"
                "5. Instruction par les services de la Région (avis DRAC/ABF le cas échéant)\n"
                "6. Vote en Commission permanente du Conseil régional\n"
                "7. Notification de la subvention et convention\n"
                "8. Réalisation des travaux et versement de la subvention sur justificatifs (acomptes possibles)"
            ),
            "documents_requis": [
                "Formulaire de demande de subvention régionale",
                "Descriptif du patrimoine et de son intérêt",
                "Programme détaillé des travaux",
                "Devis des entreprises (au moins 2 devis comparatifs)",
                "Plan de financement prévisionnel",
                "Photos du site avant travaux",
                "Autorisation de travaux (permis, déclaration préalable ou autorisation DRAC selon le cas)",
                "Preuve de propriété ou convention d'affectation",
                "Délibération du conseil municipal (si commune)",
                "RIB",
            ],
            "delai_instruction": "3 à 6 mois",
            "permanent": True,
            "url_officielle": "https://www.iledefrance.fr/aides-et-appels-a-projets/aide-la-restauration-du-patrimoine-immobilier-protege",
            "formulaire_url": "https://mesdemarches.iledefrance.fr",
            "tags": [
                "Île-de-France",
                "région",
                "patrimoine",
                "restauration",
                "subvention régionale",
                "monuments historiques",
                "patrimoine religieux",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : tous niveaux
supabase.table("aides_protections").insert(
    [
        {"aide_id": aide_id, "protection_code": "classe"},
        {"aide_id": aide_id, "protection_code": "inscrit"},
        {"aide_id": aide_id, "protection_code": "non_protege"},
    ]
).execute()
print("  ✓ Protections insérées")

# Propriétaires : communes, EPCI, départements, associations, fondations, privés, SCI (hors État)
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : large gamme
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "toiture"},
        {"aide_id": aide_id, "travaux_code": "charpente"},
        {"aide_id": aide_id, "travaux_code": "couverture"},
        {"aide_id": aide_id, "travaux_code": "facade"},
        {"aide_id": aide_id, "travaux_code": "maconnerie"},
        {"aide_id": aide_id, "travaux_code": "vitraux"},
        {"aide_id": aide_id, "travaux_code": "peintures_murales"},
        {"aide_id": aide_id, "travaux_code": "menuiserie"},
        {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
        {"aide_id": aide_id, "travaux_code": "mobilier"},
        {"aide_id": aide_id, "travaux_code": "orgues"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Région : Île-de-France uniquement
supabase.table("aides_regions").insert(
    [
        {"aide_id": aide_id, "region_code": "ile-de-france"},
    ]
).execute()
print("  ✓ Région insérée")

# Départements IDF
supabase.table("aides_departements").insert(
    [
        {"aide_id": aide_id, "departement_code": "75"},
        {"aide_id": aide_id, "departement_code": "77"},
        {"aide_id": aide_id, "departement_code": "78"},
        {"aide_id": aide_id, "departement_code": "91"},
        {"aide_id": aide_id, "departement_code": "92"},
        {"aide_id": aide_id, "departement_code": "93"},
        {"aide_id": aide_id, "departement_code": "94"},
        {"aide_id": aide_id, "departement_code": "95"},
    ]
).execute()
print("  ✓ Départements insérés")

# Segments : communes et privés
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
        {"aide_id": aide_id, "segment_code": "prive"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ Aide régionale Île-de-France insérée avec succès (id: {aide_id})")
