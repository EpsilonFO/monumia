"""
Seed: Numérique inclusif et FabLabs — Aides pour la numérisation du patrimoine,
la création de FabLabs dans des lieux patrimoniaux et la médiation numérique.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_numerique_inclusif_fablabs.py
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
            "nom": "Numérique inclusif et FabLabs — Aides à la médiation et valorisation numérique du patrimoine",
            "nom_court": "Numérique inclusif / FabLabs patrimoine",
            "description": "Dispositifs de financement pour la numérisation du patrimoine, la création de FabLabs dans des lieux patrimoniaux, la médiation numérique et l'inclusion numérique : France Num, Programme Nouveaux Lieux Nouveaux Liens, appels à projets régionaux.",
            "description_longue": (
                "Plusieurs dispositifs publics permettent de financer des projets mêlant numérique "
                "et patrimoine. Le programme France Num, porté par la Direction Générale des Entreprises "
                "(DGE), accompagne la transformation numérique des TPE/PME et peut financer la "
                "numérisation d'activités liées au patrimoine (visites virtuelles, billetterie en ligne, "
                "modélisation 3D). Le programme Nouveaux Lieux Nouveaux Liens (NLLNL) du Ministère de "
                "la Culture soutient les tiers-lieux culturels, dont les FabLabs implantés dans des "
                "bâtiments patrimoniaux, avec des subventions de fonctionnement et d'investissement. "
                "La Banque des Territoires propose des prêts et des investissements pour les tiers-lieux "
                "en zone rurale ou périurbaine. Les DRAC financent des projets de médiation numérique "
                "du patrimoine (réalité augmentée, applications de visite, numérisation 3D d'édifices). "
                "Le programme France 2030 — Culture immersive soutient les projets innovants de "
                "valorisation numérique du patrimoine (réalité virtuelle, expériences immersives). "
                "Les Fabriques de territoire (programme de l'ANCT) financent la création ou le "
                "développement de tiers-lieux numériques inclusifs, pouvant s'implanter dans des "
                "bâtiments patrimoniaux. Enfin, les conseils régionaux proposent souvent des aides "
                "spécifiques à la valorisation numérique du patrimoine et à la création de FabLabs."
            ),
            "categorie": "etat_drac",
            "type": "subvention",
            "organisme": "Ministère de la Culture / DGE / ANCT / Banque des Territoires / DRAC",
            "montant_max": 150000,
            "taux_max": 80,
            "montant_min": None,
            "plancher": None,
            "base_ttc": True,
            "commune_max_population": None,
            "cofinancement_requis": True,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Programme Nouveaux Lieux Nouveaux Liens (Ministère de la Culture) : subventions "
                "jusqu'à 75 000 € pour les tiers-lieux culturels (dont FabLabs patrimoine). Le lieu "
                "doit proposer une programmation culturelle ouverte au public et un modèle économique "
                "viable. Priorité aux zones rurales et quartiers prioritaires.\n"
                "- Fabriques de territoire (ANCT) : subventions de 50 000 à 150 000 € pour la création "
                "ou le développement de tiers-lieux numériques. Le projet doit répondre à un besoin "
                "territorial identifié (inclusion numérique, formation, création). Appels à projets "
                "réguliers.\n"
                "- France Num : accompagnement et diagnostic numérique gratuit pour les TPE/PME du "
                "patrimoine. Chèques numériques de 500 à 5 000 € selon les dispositifs régionaux.\n"
                "- DRAC — Médiation numérique : subventions pour les projets de numérisation et de "
                "médiation numérique du patrimoine (applications, réalité augmentée, modélisation 3D). "
                "Taux variable selon les DRAC, généralement 30 à 50 % du coût du projet.\n"
                "- France 2030 — Culture immersive : subventions et avances remboursables pour les "
                "projets innovants de valorisation numérique du patrimoine. Montants de 50 000 à "
                "500 000 €. Appels à projets du CNC.\n"
                "- Banque des Territoires : prêts à taux bonifiés et investissements en fonds propres "
                "pour les tiers-lieux en milieu rural. Montants de 50 000 à 300 000 €.\n"
                "- Le FabLab doit être ouvert au public et proposer des activités d'inclusion numérique "
                "(ateliers, formations, accès libre aux équipements).\n"
                "- Les projets de numérisation du patrimoine doivent respecter les normes de "
                "documentation patrimoniale (inventaire, base Mérimée/Palissy).\n"
                "- Cofinancement requis : le porteur doit apporter au minimum 20 % du budget total.\n"
                "- Les bénéficiaires peuvent être des collectivités, associations, entreprises de l'ESS, "
                "établissements publics, ou porteurs privés.\n"
                "- L'implantation dans un bâtiment patrimonial (MH, SPR, label Architecture "
                "Contemporaine Remarquable) est un critère valorisé mais non obligatoire."
            ),
            "demarche_description": (
                "1. Identifier le dispositif adapté au projet (NLLNL, Fabriques de territoire, DRAC, France 2030)\n"
                "2. Contacter la DRAC ou la préfecture de région pour un premier échange\n"
                "3. Constituer le dossier de candidature (description du projet, plan de financement, "
                "étude de faisabilité)\n"
                "4. Déposer la candidature lors de l'appel à projets (calendrier variable selon dispositif)\n"
                "5. Instruction par le comité de sélection\n"
                "6. Notification et convention de financement\n"
                "7. Réalisation du projet avec reporting intermédiaire\n"
                "8. Bilan final et demande de solde"
            ),
            "documents_requis": [
                "Formulaire de candidature spécifique au dispositif",
                "Description détaillée du projet (objectifs, publics visés, programmation)",
                "Plan de financement prévisionnel",
                "Étude de faisabilité ou note d'opportunité",
                "Devis des équipements numériques et des travaux d'aménagement",
                "Statuts de la structure porteuse",
                "Attestation de propriété ou convention d'occupation du bâtiment",
                "Lettres de soutien des partenaires locaux",
                "CV des porteurs de projet",
            ],
            "delai_instruction": "3 à 9 mois (selon le dispositif et le calendrier des AAP)",
            "permanent": False,
            "url_officielle": "https://www.culture.gouv.fr/aides-demarches/dispositifs-specifiques/nouveaux-lieux-nouveaux-liens",
            "formulaire_url": None,
            "tags": [
                "numérique",
                "FabLab",
                "tiers-lieu",
                "médiation numérique",
                "numérisation",
                "inclusion numérique",
                "France Num",
                "réalité augmentée",
                "3D",
                "culture immersive",
                "ANCT",
                "Fabriques de territoire",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte (patrimoine protégé et non protégé)

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
        {"aide_id": aide_id, "proprietaire_code": "mixte"},
    ]
).execute()
print("  ✓ Propriétaires éligibles insérés")

# Travaux : aménagement, équipement numérique, études
supabase.table("aides_travaux").insert(
    [
        {"aide_id": aide_id, "travaux_code": "etude_prealable"},
        {"aide_id": aide_id, "travaux_code": "electricite"},
        {"aide_id": aide_id, "travaux_code": "accessibilite"},
        {"aide_id": aide_id, "travaux_code": "restauration_generale"},
    ]
).execute()
print("  ✓ Travaux éligibles insérés")

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

print(f"\n✅ Numérique inclusif et FabLabs inséré avec succès (id: {aide_id})")
