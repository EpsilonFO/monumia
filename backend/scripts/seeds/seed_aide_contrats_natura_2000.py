"""
Seed: Contrats Natura 2000 — Subventions FEADER/État pour la gestion des sites Natura 2000.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_contrats_natura_2000.py
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
            "nom": "Contrats Natura 2000 — Subventions pour la gestion des habitats et espèces en site Natura 2000",
            "nom_court": "Contrats Natura 2000",
            "description": "Subventions État/FEADER pour les actions de maintien ou restauration des habitats naturels et espèces sur les sites Natura 2000, incluant la gestion écologique des parcs, jardins et abords de monuments en zone Natura 2000.",
            "description_longue": (
                "Les contrats Natura 2000 financent les actions de préservation ou de restauration des habitats "
                "naturels et des espèces qui justifient la désignation d'un site Natura 2000. Cofinancés par "
                "l'État et le FEADER (Fonds Européen Agricole pour le Développement Rural), ils s'adressent à "
                "toute personne physique ou morale, publique ou privée, titulaire de droits sur des terrains "
                "inclus dans un site Natura 2000. Les taux de financement vont de 80 % (porteur public) à "
                "100 % (porteur privé) selon les régions. Les contrats ont une durée maximale de 5 ans. "
                "Pour le patrimoine bâti, ces contrats peuvent financer : la gestion écologique des parcs et "
                "jardins historiques situés en zone Natura 2000, l'aménagement favorable aux espèces protégées "
                "(chiroptères dans les combles, rapaces sur les clochers), la restauration de mares et zones "
                "humides dans les domaines patrimoniaux, l'entretien de haies et prairies dans les abords "
                "de monuments. Le montant minimum du projet est de 25 000 € pour bénéficier du cofinancement FEADER."
            ),
            "categorie": "europe",
            "type": "subvention",
            "organisme": "DREAL / Régions — Cofinancement FEADER (Union Européenne) et État",
            "montant_max": None,
            "taux_max": 100,
            "montant_min": None,
            "plancher": 25000,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Le projet doit être situé sur des parcelles incluses dans un site Natura 2000 désigné\n"
                "- Les actions doivent être conformes aux orientations de gestion et aux cahiers des charges "
                "définis dans le Document d'Objectifs (DOCOB) du site\n"
                "- Porteurs éligibles : toute personne physique ou morale, publique ou privée, "
                "titulaire de droits réels ou personnels conférant la jouissance des terrains "
                "inclus dans le site Natura 2000\n"
                "- Types de contrats :\n"
                "  • Contrats ni-agricoles ni-forestiers (milieux ouverts, zones humides, etc.)\n"
                "  • Contrats forestiers (gestion sylvicole favorable à la biodiversité)\n"
                "- Taux de financement (variable selon les régions) :\n"
                "  • Porteur public : jusqu'à 80 % (FEADER + État)\n"
                "  • Porteur privé : jusqu'à 100 % (FEADER + État)\n"
                "- Montant minimum de projet pour le cofinancement FEADER : 25 000 € (montant aide FEDER ≥ 20 000 €)\n"
                "- Durée du contrat : 5 ans maximum\n"
                "- Actions éligibles en lien avec le patrimoine bâti :\n"
                "  • Restauration et entretien de mares, zones humides dans les domaines patrimoniaux\n"
                "  • Gestion écologique des parcs et jardins historiques en site Natura 2000\n"
                "  • Aménagements favorables aux espèces protégées (chiroptères, rapaces, insectes)\n"
                "  • Entretien de haies, prairies, lisières en abords de monuments\n"
                "  • Lutte contre les espèces exotiques envahissantes\n"
                "- Les dépenses éligibles sont celles directement liées à la mise en œuvre du contrat\n"
                "- Non éligible : travaux de restauration du bâti sans lien avec la gestion des habitats/espèces\n"
                "- La liste des actions éligibles est annexée à chaque appel à projets régional"
            ),
            "demarche_description": (
                "1. Vérifier que le terrain ou le monument est situé en site Natura 2000 (géoportail, INPN)\n"
                "2. Consulter le DOCOB du site pour identifier les actions de gestion prioritaires\n"
                "3. Prendre contact avec l'animateur du site Natura 2000 (DREAL ou structure animatrice)\n"
                "4. Identifier les actions éligibles correspondant à votre projet\n"
                "5. Constituer le dossier de demande de contrat Natura 2000\n"
                "6. Déposer le dossier auprès de la DREAL ou de la Région (selon le programme FEADER régional)\n"
                "7. Instruction par les services instructeurs (DREAL, DDT, Région)\n"
                "8. Signature du contrat Natura 2000 (engagement sur 5 ans)\n"
                "9. Réalisation des actions et rapports de suivi\n"
                "10. Versement des aides sur présentation des justificatifs de dépenses"
            ),
            "documents_requis": [
                "Formulaire de demande de contrat Natura 2000",
                "Carte de localisation des parcelles en site Natura 2000",
                "Justificatif de droits sur les terrains (propriété, bail, convention)",
                "Description technique des actions envisagées",
                "Devis détaillés ou barèmes de coûts unitaires",
                "Plan de financement prévisionnel",
                "Avis de l'animateur du site Natura 2000",
                "Extrait du DOCOB avec les objectifs de gestion visés",
            ],
            "delai_instruction": "3 à 8 mois",
            "permanent": True,
            "url_officielle": "https://www.natura2000.fr/financements",
            "formulaire_url": None,
            "tags": [
                "Natura 2000",
                "FEADER",
                "biodiversité",
                "habitats naturels",
                "espèces protégées",
                "zones humides",
                "parcs jardins",
                "DOCOB",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (le critère est la localisation en site Natura 2000)

# Propriétaires : publics et privés
supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "public_etat"},
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
        {"aide_id": aide_id, "proprietaire_code": "mixte"},
    ]
).execute()
print("  ✓ Propriétaires insérés")

# Travaux : parcs/jardins, études
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "parcs_jardins"},
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
    ]
).execute()
print("  ✓ Travaux insérés")

# Régions : aide nationale → pas de contrainte

# Segments : tous segments
supabase.table("aides_segments").insert(
    [
        {"aide_id": aide_id, "segment_code": "commune"},
        {"aide_id": aide_id, "segment_code": "prive"},
    ]
).execute()
print("  ✓ Segments insérés")

# État de conservation : pas de contrainte

print(f"\n✅ Contrats Natura 2000 inséré avec succès (id: {aide_id})")
