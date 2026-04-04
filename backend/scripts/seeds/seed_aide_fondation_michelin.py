"""
Seed: Fondation d'entreprise Michelin — Le Plus Grand Musée de France.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_fondation_michelin.py
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
            "nom": "Fondation d'entreprise Michelin — Le Plus Grand Musée de France",
            "nom_court": "Fondation Michelin",
            "description": "Financement de la restauration d'œuvres d'art et d'éléments patrimoniaux dans les communes proches des sites industriels Michelin, via le programme « Le Plus Grand Musée de France » en partenariat avec la Sauvegarde de l'Art Français.",
            "description_longue": (
                "La Fondation d'entreprise Michelin soutient la restauration du patrimoine local à travers "
                "le programme « Le Plus Grand Musée de France », lancé en 2017 en partenariat avec "
                "la Sauvegarde de l'Art Français. Les collaborateurs Michelin identifient des œuvres d'art "
                "et éléments patrimoniaux (tableaux, sculptures, vitraux, mobilier, objets d'art sacré…) "
                "situés dans les communes proches de leurs sites industriels, puis votent pour sélectionner "
                "ceux qui bénéficieront d'un financement de restauration. Depuis 2017, plus de 47 œuvres "
                "ont été restaurées grâce à ce dispositif. La Fondation finance également des projets "
                "patrimoniaux majeurs (ex : Galerie des Carrosses du château de Versailles). Le montant "
                "par œuvre est généralement de 8 000 à 10 000 €."
            ),
            "categorie": "fondation",
            "type": "mecenat",
            "organisme": "Fondation d'entreprise Michelin / Sauvegarde de l'Art Français",
            "montant_max": 10000,
            "taux_max": 100,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- L'œuvre ou l'élément patrimonial doit être situé dans une commune proche d'un site industriel Michelin en France\n"
                "- Le bien doit être accessible au public (église, place publique, mairie, musée municipal…)\n"
                "- L'œuvre doit nécessiter une restauration avérée (dégradation visible, risque de perte)\n"
                "- Types de biens éligibles : tableaux, sculptures, vitraux, mobilier, objets d'art sacré, patrimoine industriel, éléments architecturaux\n"
                "- Les biens peuvent être classés MH, inscrits MH ou non protégés, à condition de présenter un intérêt patrimonial\n"
                "- Propriétaires éligibles : communes, associations, établissements publics\n"
                "- Les propriétaires privés (personnes physiques, SCI) ne sont généralement PAS éligibles\n"
                "- La sélection est faite par les collaborateurs Michelin du site concerné (vote interne)\n"
                "- Le programme fonctionne par campagne annuelle : les collaborateurs identifient les œuvres, un comité valide, puis un vote a lieu\n"
                "- Montant habituel : 8 000 € par œuvre (jusqu'à 10 000 € selon les sites)\n"
                "- La Fondation peut financer des projets plus importants hors programme PGMF (montants variables, sur dossier)\n"
                "- Les travaux de restauration doivent être confiés à un restaurateur professionnel qualifié\n"
                "- L'œuvre restaurée doit rester accessible au public après restauration\n"
                "- La candidature ne se fait pas directement par le propriétaire : c'est un collaborateur Michelin qui identifie et propose l'œuvre"
            ),
            "demarche_description": (
                "1. Un collaborateur Michelin identifie une œuvre patrimoniale à restaurer près de son site de travail\n"
                "2. L'œuvre est proposée au programme « Le Plus Grand Musée de France »\n"
                "3. Vote des collaborateurs du site pour sélectionner l'œuvre lauréate\n"
                "4. Validation par la Fondation d'entreprise Michelin et la Sauvegarde de l'Art Français\n"
                "5. Financement de la restauration (8 000 à 10 000 €)\n"
                "6. Restauration par un professionnel qualifié\n"
                "7. Inauguration de l'œuvre restaurée avec les collaborateurs et la commune"
            ),
            "documents_requis": [
                "Identification de l'œuvre (photos, localisation, historique)",
                "Diagnostic de l'état de conservation",
                "Devis de restauration par un professionnel qualifié",
                "Accord du propriétaire (commune ou association)",
            ],
            "delai_instruction": "6 à 12 mois (campagne annuelle)",
            "permanent": False,
            "url_officielle": "https://fondation.michelin.com/",
            "formulaire_url": None,
            "tags": [
                "Fondation Michelin",
                "Le Plus Grand Musée de France",
                "Sauvegarde de l'Art Français",
                "mécénat",
                "restauration",
                "œuvres d'art",
                "patrimoine local",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : tous niveaux (l'intérêt patrimonial prime)
supabase.table("aides_protections").insert(
    [
        {"aide_id": aide_id, "protection_code": "classe"},
        {"aide_id": aide_id, "protection_code": "inscrit"},
        {"aide_id": aide_id, "protection_code": "non_protege"},
    ]
).execute()
print("  ✓ Protections insérées")

# Propriétaires : collectivités et associations uniquement
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : restauration d'œuvres et d'éléments patrimoniaux
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
        {"aide_id": aide_id, "travaux_code": "vitraux"},
        {"aide_id": aide_id, "travaux_code": "peintures_murales"},
        {"aide_id": aide_id, "travaux_code": "mobilier"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : nationale (pas de contrainte régionale, dépend des sites Michelin)

# Segments : communes principalement
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte stricte

print(f"\n✅ Fondation Michelin insérée avec succès (id: {aide_id})")
