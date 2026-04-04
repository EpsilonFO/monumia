"""
Seed: Label « Jardin remarquable » et aides associées.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_label_jardin_remarquable.py
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
            "nom": "Label « Jardin remarquable » et aides associées",
            "nom_court": "Label Jardin remarquable",
            "description": "Label d'État valorisant les parcs et jardins ouverts au public présentant un intérêt culturel, historique, botanique ou esthétique. Ouvre l'accès à des aides régionales et au mécénat.",
            "description_longue": (
                "Le label « Jardin remarquable » est un label d'État créé en 2004 par le ministère "
                "de la Culture. Il est attribué pour 7 ans (renouvelable) par le préfet de région, "
                "sur avis d'une commission présidée par le directeur régional des affaires culturelles "
                "(DRAC). Le label distingue les parcs et jardins ouverts au public qui présentent un "
                "intérêt remarquable du point de vue de l'histoire, de la composition, de la botanique "
                "ou de l'esthétique. Il ne constitue pas une aide financière directe, mais ouvre l'accès "
                "à des dispositifs de soutien : aides régionales spécifiques aux jardins labellisés, "
                "accompagnement pour la recherche de mécénat, visibilité dans les Rendez-vous aux jardins, "
                "et priorité dans certains appels à projets patrimoniaux. Certaines régions (Centre-Val "
                "de Loire, Île-de-France…) proposent des subventions dédiées aux jardins labellisés."
            ),
            "categorie": "etat_drac",
            "type": "label",
            "organisme": "Ministère de la Culture — DRAC",
            "montant_max": None,
            "taux_max": None,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Le jardin doit être ouvert au public au minimum 50 jours par an entre le 1er janvier "
                "et le 31 décembre, dont 30 jours comprenant au moins 5 dimanches entre le 1er avril "
                "et le 30 septembre\n"
                "- Critères d'attribution évalués par la commission régionale DRAC :\n"
                "  • Composition : organisation des espaces, tracé, perspectives\n"
                "  • Intégration dans le site et qualité des abords\n"
                "  • Éléments remarquables : présence d'eau, fabriques, architectures végétales, statues\n"
                "  • Intérêt botanique : diversité, rareté, collections\n"
                "  • Intérêt historique : ancienneté, lien avec un monument, évolution documentée\n"
                "  • Qualité de l'entretien et existence d'un plan de gestion\n"
                "  • Communication et documentation à destination du public\n"
                "- Le jardin peut être protégé MH (classé ou inscrit) ou non protégé\n"
                "- Propriétaires éligibles : collectivités, personnes physiques, associations, SCI\n"
                "- Le label engage le propriétaire à :\n"
                "  • Maintenir la qualité d'entretien du jardin\n"
                "  • Assurer l'ouverture au public selon les conditions minimales\n"
                "  • Participer aux Rendez-vous aux jardins (événement national annuel)\n"
                "- Label attribué pour 7 ans (depuis circulaire du 15 décembre 2023), renouvelable\n"
                "- Le label est révocable si les conditions ne sont plus respectées\n"
                "- Le label n'est pas une aide financière directe mais ouvre l'accès à :\n"
                "  • Des subventions régionales dédiées (ex : ACRPJP en Centre-Val de Loire)\n"
                "  • Un accompagnement pour la recherche de mécénat\n"
                "  • Une visibilité accrue (site du ministère, Rendez-vous aux jardins)\n"
                "  • Une priorité dans certains appels à projets patrimoniaux\n"
                "- Les jardins protégés MH peuvent aussi bénéficier des aides DRAC classiques "
                "en plus du label"
            ),
            "demarche_description": (
                "1. Vérifier que le jardin remplit les critères de qualité et d'ouverture au public\n"
                "2. Constituer le dossier de candidature (pas de date limite, candidatures en continu)\n"
                "3. Soumettre le dossier à la DRAC de la région concernée\n"
                "4. Visite sur site par la commission régionale présidée par le DRAC\n"
                "5. Avis de la commission dans un délai de 4 mois\n"
                "6. Décision du préfet de région\n"
                "7. Si labellisé : s'engager à maintenir l'entretien et l'ouverture au public\n"
                "8. Solliciter les aides régionales et le mécénat ouverts par le label"
            ),
            "documents_requis": [
                "Dossier de candidature avec historique du jardin",
                "Plan du jardin et de ses espaces",
                "Photos du jardin (vues d'ensemble et détails remarquables)",
                "Plan de gestion et d'entretien",
                "Calendrier d'ouverture au public",
                "Documentation mise à disposition des visiteurs",
                "Inventaire botanique (si pertinent)",
            ],
            "delai_instruction": "4 à 6 mois",
            "permanent": True,
            "url_officielle": "https://www.culture.gouv.fr/aides-demarches/protections-labels-et-appellations/label-jardin-remarquable",
            "formulaire_url": None,
            "tags": [
                "Jardin remarquable",
                "label",
                "parcs et jardins",
                "DRAC",
                "ministère de la Culture",
                "botanique",
                "patrimoine végétal",
                "ouverture au public",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (jardins protégés ou non)

# Propriétaires : tous types
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : parcs et jardins principalement
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "parcs_jardins"},
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale → pas de contrainte

# Segments : tous
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
        {"aide_id": aide_id, "segment_code": "prive"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ Label Jardin remarquable inséré avec succès (id: {aide_id})")
