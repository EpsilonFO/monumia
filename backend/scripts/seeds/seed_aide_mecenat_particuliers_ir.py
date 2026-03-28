"""
Seed: Mécénat des particuliers (IR) — Réduction d'impôt sur le revenu pour dons au patrimoine.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_mecenat_particuliers_ir.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Mécénat des particuliers — Réduction d'impôt sur le revenu (article 200 du CGI)",
    "nom_court": "Dons particuliers (IR)",
    "description": "Réduction d'impôt sur le revenu de 66 % (ou 75 % pour le patrimoine religieux) pour les particuliers effectuant des dons en faveur de la restauration du patrimoine.",
    "description_longue": (
        "L'article 200 du Code général des impôts permet aux particuliers de bénéficier d'une "
        "réduction d'impôt sur le revenu lorsqu'ils effectuent des dons au profit d'organismes "
        "d'intérêt général œuvrant pour la conservation du patrimoine. Le taux standard est de "
        "66 % du montant des dons, dans la limite de 20 % du revenu imposable. Un taux majoré "
        "de 75 % s'applique aux dons destinés à la restauration du patrimoine religieux via la "
        "Fondation du patrimoine (dans la limite de 1 000 € par an). L'excédent est reportable "
        "sur les 5 années suivantes. Ce dispositif permet aux propriétaires de monuments de "
        "solliciter des dons de particuliers via des fondations habilitées (Fondation du patrimoine, "
        "La Demeure Historique) et de bénéficier indirectement de ce levier de financement."
    ),
    "categorie": "fiscalite",
    "type": "deduction_fiscale",
    "organisme": "Direction générale des Finances publiques (DGFiP)",
    "montant_max": None,
    "taux_max": 66,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": False,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Bénéficiaires : tout particulier fiscalement domicilié en France et assujetti à l'IR\n"
        "- Taux standard : réduction d'impôt de 66 % du montant des dons\n"
        "- Plafond : 20 % du revenu imposable du foyer fiscal\n"
        "- Report de l'excédent : possible sur les 5 années suivantes (consommation par ordre d'ancienneté)\n"
        "- Taux majoré à 75 % pour les dons au patrimoine religieux :\n"
        "  • Dons à la Fondation du patrimoine pour la conservation du patrimoine immobilier religieux\n"
        "  • Communes ≤ 10 000 habitants (métropole) ou ≤ 20 000 habitants (outre-mer)\n"
        "  • Plafond spécifique de 1 000 € par an au taux de 75 % ; au-delà, taux de 66 %\n"
        "- Taux majoré à 75 % pour les dons Chambord (2026) : dans la limite de 1 000 € par an\n"
        "- Organismes bénéficiaires éligibles :\n"
        "  • Fondations reconnues d'utilité publique (FRUP)\n"
        "  • Associations reconnues d'utilité publique (ARUP)\n"
        "  • Organismes d'intérêt général à caractère culturel ou patrimonial\n"
        "  • Fondation du patrimoine (habilitée à collecter pour les MH privés)\n"
        "  • La Demeure Historique (habilitée à collecter pour les MH privés)\n"
        "- Conditions de l'organisme bénéficiaire :\n"
        "  • Activité non lucrative et gestion désintéressée\n"
        "  • Ne pas fonctionner au profit d'un cercle restreint\n"
        "- Restriction pour les dons dirigés vers un MH privé (via Fondation du patrimoine) :\n"
        "  • Le donateur ne doit pas être propriétaire du monument\n"
        "  • Le donateur ne doit pas être ascendant, descendant ou conjoint du propriétaire\n"
        "- Le donateur doit obtenir un reçu fiscal de l'organisme bénéficiaire\n"
        "- Périmètre géographique : France, UE, Islande, Norvège, Liechtenstein\n"
        "- Ce dispositif profite indirectement aux propriétaires de MH qui lancent des campagnes "
        "de souscription publique via la Fondation du patrimoine ou La Demeure Historique"
    ),
    "demarche_description": (
        "1. Le propriétaire du monument sollicite une fondation habilitée (Fondation du patrimoine, La Demeure Historique) pour ouvrir une campagne de souscription\n"
        "2. Les particuliers effectuent leurs dons auprès de la fondation (en ligne, chèque, virement)\n"
        "3. La fondation délivre un reçu fiscal (cerfa n° 11580*04) au donateur\n"
        "4. Le donateur reporte le montant du don dans sa déclaration de revenus (formulaire 2042 RICI, cases 7UF/7UG)\n"
        "5. La réduction d'impôt est appliquée automatiquement par l'administration fiscale\n"
        "6. En janvier : versement d'un acompte de 60 % basé sur les dons de l'année précédente"
    ),
    "documents_requis": [
        "Reçu fiscal (cerfa n° 11580*04) délivré par l'organisme bénéficiaire",
        "Déclaration de revenus n° 2042 RICI",
        "Justificatif du versement (relevé bancaire, reçu en ligne)",
    ],
    "delai_instruction": "Immédiat (déclaration fiscale annuelle, réduction appliquée à N+1)",
    "permanent": True,
    "url_officielle": "https://www.service-public.gouv.fr/particuliers/vosdroits/F426",
    "formulaire_url": None,
    "tags": [
        "mécénat", "particuliers", "IR", "réduction d'impôt", "article 200",
        "dons", "patrimoine", "défiscalisation", "souscription publique",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (les dons peuvent financer tout type de patrimoine)

# Propriétaires : pas de contrainte (bénéficie indirectement à tous via souscription)

# Travaux : pas de contrainte (tous travaux de conservation/restauration)

# Régions : aide nationale → pas de contrainte

# Segments : principalement prive mais aussi commune (via souscription publique)
# Pas de contrainte stricte → on n'insère rien

# État de conservation : pas de contrainte

print(f"\n✅ Mécénat des particuliers (IR) inséré avec succès (id: {aide_id})")
