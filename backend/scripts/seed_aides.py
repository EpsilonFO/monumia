"""
Seed the `aides` table in Supabase with all 16 aids.

Run:
    cd backend && python scripts/seed_aides.py

Requires SUPABASE_URL and SUPABASE_SECRET_KEY in .env (or environment).
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SECRET_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------------------------------------------------------------
# All 16 aids — columns are snake_case, criteres JSONB keeps camelCase keys
# ---------------------------------------------------------------------------

AIDES = [
    # === DRAC MH Classé ===
    {
        "id": "aide-1",
        "nom": "Subvention DRAC — Travaux sur monuments historiques classés",
        "nom_court": "DRAC MH Classé",
        "description": "Subvention de l'État pour la restauration des monuments historiques classés, versée par la Direction Régionale des Affaires Culturelles.",
        "description_longue": "La DRAC peut accorder des subventions pour les travaux d'entretien, de réparation et de restauration des monuments historiques classés n'appartenant pas à l'État. Le taux de base est d'environ 40 % du montant HT des travaux. Les travaux doivent être réalisés sous le contrôle scientifique et technique de la DRAC et ne doivent pas avoir commencé avant l'accord de subvention. Les lots techniques courants (électricité, plomberie, chauffage) sont exclus sauf s'ils relèvent de la sécurité incendie.",
        "categorie": "etat_drac",
        "type": "subvention",
        "organisme": "Direction Régionale des Affaires Culturelles (DRAC)",
        "montant_max": None,
        "taux_max": 50,
        "plancher": 3000,
        "criteres": {
            "protectionRequise": ["classe"],
            "proprietaireEligible": ["public_commune", "public_departement", "public_region", "prive_personne_physique", "prive_sci", "association"],
            "travauxEligibles": ["toiture", "charpente", "maconnerie", "vitraux", "peintures_murales", "menuiserie", "facade", "restauration_generale", "mise_en_securite", "couverture", "etude_prealable"],
            "architecteRequis": True,
        },
        "demarche_description": "1. Contacter la CRMH de votre DRAC pour un rendez-vous préalable\n2. Constituer le dossier avec le formulaire CERFA de demande de subvention\n3. Joindre le programme de travaux établi par un architecte du patrimoine\n4. Déposer le dossier auprès de la DRAC de votre région\n5. Attendre l'instruction (3 à 6 mois) et la notification de la décision",
        "documents_requis": ["Formulaire CERFA de demande de subvention", "Extrait cadastral", "Titre de propriété ou délibération du conseil municipal", "Programme détaillé des travaux", "Devis détaillé des entreprises (HT)", "Plan de financement prévisionnel", "Photos de l'état actuel", "Plan de situation", "Avis de l'ABF"],
        "delai_instruction": "3 à 6 mois",
        "permanent": True,
        "tags": ["restauration", "état", "monument classé"],
        "base_ttc": False,
    },
    # === DRAC MH Inscrit ===
    {
        "id": "aide-2",
        "nom": "Subvention DRAC — Travaux sur monuments historiques inscrits",
        "nom_court": "DRAC MH Inscrit",
        "description": "Subvention de l'État pour la restauration des monuments historiques inscrits, avec un taux de base d'environ 20 %.",
        "description_longue": "Les monuments historiques inscrits peuvent bénéficier de subventions de la DRAC pour leurs travaux de restauration. Le taux de base avoisine 20 % du montant des travaux éligibles. Comme pour les classés, les travaux ne doivent pas avoir commencé avant l'accord et doivent être réalisés sous contrôle de la DRAC. Les lots techniques courants sont exclus.",
        "categorie": "etat_drac",
        "type": "subvention",
        "organisme": "Direction Régionale des Affaires Culturelles (DRAC)",
        "taux_max": 40,
        "criteres": {
            "protectionRequise": ["inscrit"],
            "proprietaireEligible": ["public_commune", "public_departement", "public_region", "prive_personne_physique", "prive_sci", "association"],
            "travauxEligibles": ["toiture", "charpente", "maconnerie", "vitraux", "peintures_murales", "menuiserie", "facade", "restauration_generale", "mise_en_securite", "couverture", "etude_prealable"],
            "architecteRequis": True,
        },
        "demarche_description": "1. Prendre contact avec la CRMH de votre DRAC\n2. Constituer le dossier avec le formulaire CERFA\n3. Joindre les devis et le programme de travaux\n4. Déposer auprès de la DRAC\n5. Attendre l'instruction et la notification",
        "documents_requis": ["Formulaire CERFA", "Extrait cadastral", "Titre de propriété ou délibération", "Programme des travaux", "Devis détaillé", "Plan de financement", "Photos état actuel", "Avis ABF"],
        "delai_instruction": "3 à 6 mois",
        "permanent": True,
        "tags": ["restauration", "état", "monument inscrit"],
        "base_ttc": False,
    },
    # === DRAC Études ===
    {
        "id": "aide-3",
        "nom": "Subvention DRAC — Études préalables",
        "nom_court": "DRAC Études",
        "description": "Aide au financement des études préalables (diagnostics, études architecturales) sur les monuments historiques, jusqu'à 60 % du coût.",
        "description_longue": "Avant d'engager des travaux de restauration, une étude préalable est souvent indispensable. La DRAC peut financer jusqu'à 60 % du coût de ces études : diagnostic structurel, étude sanitaire, étude historique, relevé architectural. Cette aide est cruciale car elle conditionne souvent l'obtention des subventions de travaux.",
        "categorie": "etat_drac",
        "type": "subvention",
        "organisme": "Direction Régionale des Affaires Culturelles (DRAC)",
        "taux_max": 60,
        "criteres": {
            "protectionRequise": ["classe", "inscrit"],
            "proprietaireEligible": ["public_commune", "public_departement", "public_region", "prive_personne_physique", "prive_sci", "association"],
            "travauxEligibles": ["etude_prealable"],
        },
        "demarche_description": "1. Contacter la CRMH pour valider le besoin d'étude\n2. Obtenir un devis d'un architecte du patrimoine ou d'un bureau d'études\n3. Déposer la demande auprès de la DRAC\n4. L'étude ne doit pas avoir commencé avant l'accord",
        "documents_requis": ["Lettre de demande", "Devis de l'étude", "Justificatif de propriété", "Photos du monument", "Description du besoin"],
        "delai_instruction": "2 à 4 mois",
        "permanent": True,
        "tags": ["étude", "diagnostic", "état"],
        "base_ttc": False,
    },
    # === FIP ===
    {
        "id": "aide-4",
        "nom": "Fonds Incitatif et Partenarial (FIP)",
        "nom_court": "FIP",
        "description": "Aide majorée de l'État pour les communes de moins de 2 000 habitants possédant un monument historique en péril, avec contrepartie régionale obligatoire.",
        "description_longue": "Le FIP est un dispositif national géré par les DRAC, reposant sur le principe des financements croisés. Il s'adresse aux petites communes (≤ 2 000 hab.) possédant un monument classé ou inscrit en état de péril ou présentant des besoins sanitaires structurels. Le Conseil régional doit s'engager à hauteur d'au moins 15 % du coût global.",
        "categorie": "etat_drac",
        "type": "subvention",
        "organisme": "État (via DRAC) + Région",
        "taux_max": 80,
        "criteres": {
            "protectionRequise": ["classe", "inscrit"],
            "proprietaireEligible": ["public_commune"],
            "segmentEligible": ["commune"],
            "communeMaxPopulation": 2000,
            "communeDeMoins10000Hab": True,
            "cofinancementRequis": True,
            "etatConservationRequis": ["mauvais", "peril"],
            "travauxEligibles": ["toiture", "charpente", "maconnerie", "vitraux", "peintures_murales", "restauration_generale", "mise_en_securite", "facade", "couverture"],
        },
        "demarche_description": "1. Vérifier l'éligibilité auprès de la DRAC (commune ≤ 2 000 hab.)\n2. S'assurer de la contrepartie régionale (15 % minimum)\n3. Constituer le dossier FIP spécifique\n4. Déposer auprès de la DRAC avec copie à la Région",
        "documents_requis": ["Formulaire FIP", "Délibération du conseil municipal", "Justificatif de population INSEE", "Programme de travaux", "Devis détaillé HT", "Plan de financement avec engagement régional", "Photos état actuel", "Extrait cadastral"],
        "delai_instruction": "4 à 8 mois",
        "permanent": True,
        "tags": ["commune rurale", "état", "monument historique", "co-financement", "péril"],
        "base_ttc": False,
    },
    # === Label Fondation du Patrimoine ===
    {
        "id": "aide-5",
        "nom": "Label Fondation du Patrimoine",
        "nom_court": "Label FdP",
        "description": "Label fiscal permettant aux propriétaires privés de déduire de 50 à 100 % des travaux extérieurs de restauration de leur bien patrimonial non protégé.",
        "description_longue": "Le Label Fondation du Patrimoine est un outil fiscal pour les propriétaires privés de patrimoine non protégé (ou en SPR). Il permet de déduire de 50 à 100 % du montant des travaux extérieurs éligibles. Le label est accordé pour 3 ans. Conditions : le bien doit être en zone rurale (commune < 20 000 hab.) ou en SPR, être visible depuis la voie publique, et les travaux doivent concerner uniquement l'extérieur.",
        "categorie": "fondation_patrimoine",
        "type": "label",
        "organisme": "Fondation du Patrimoine",
        "criteres": {
            "protectionRequise": ["non_protege", "spr"],
            "proprietaireEligible": ["prive_personne_physique", "prive_sci"],
            "segmentEligible": ["prive"],
            "travauxEligibles": ["toiture", "charpente", "maconnerie", "facade", "menuiserie", "couverture"],
            "criteresSupplementaires": [
                {"label": "Visibilité depuis la voie publique", "description": "Le bien doit être visible depuis la voie publique ou le propriétaire doit s'engager à le rendre accessible."},
                {"label": "Zone rurale ou SPR", "description": "Le bien doit être situé en zone rurale (commune < 20 000 hab.) ou au sein d'un Site Patrimonial Remarquable (SPR)."},
                {"label": "Travaux extérieurs uniquement", "description": "Seuls les travaux extérieurs (façade, toiture, menuiseries) sont éligibles."},
            ],
        },
        "demarche_description": "1. Contacter le délégué régional de la Fondation du Patrimoine\n2. Obtenir un avis favorable de l'ABF\n3. Déposer le dossier de demande de label\n4. Présentation en commission régionale\n5. Attribution du label (durée 3 ans)",
        "documents_requis": ["Formulaire de demande de label", "Titre de propriété", "Photos extérieures du bien", "Description des travaux extérieurs envisagés", "Devis estimatif TTC", "Avis de l'ABF"],
        "delai_instruction": "2 à 3 mois",
        "permanent": True,
        "tags": ["fiscal", "privé", "fondation", "non protégé"],
        "base_ttc": True,
    },
    # === Souscription FdP ===
    {
        "id": "aide-6",
        "nom": "Souscription publique — Fondation du Patrimoine",
        "nom_court": "Souscription FdP",
        "description": "Collecte de dons publics organisée par la Fondation du Patrimoine pour financer la restauration d'un monument.",
        "description_longue": "La Fondation du Patrimoine peut organiser une souscription publique pour financer les travaux de restauration. Les dons des particuliers ouvrent droit à une réduction d'impôt de 66 % et ceux des entreprises à 60 %. La Fondation verse ensuite les fonds collectés au propriétaire.",
        "categorie": "fondation_patrimoine",
        "type": "souscription",
        "organisme": "Fondation du Patrimoine",
        "criteres": {
            "proprietaireEligible": ["public_commune", "public_departement", "prive_personne_physique", "prive_sci", "association"],
            "travauxEligibles": ["toiture", "charpente", "maconnerie", "vitraux", "peintures_murales", "facade", "restauration_generale", "couverture"],
        },
        "demarche_description": "1. Contacter la délégation régionale de la Fondation du Patrimoine\n2. Présenter le projet de restauration\n3. La Fondation évalue l'intérêt patrimonial et le potentiel de collecte\n4. Signature d'une convention de souscription\n5. Lancement de la campagne de dons",
        "documents_requis": ["Dossier de présentation du projet", "Photos du monument", "Devis des travaux", "Plan de financement", "Justificatif de propriété"],
        "delai_instruction": "1 à 2 mois",
        "permanent": True,
        "tags": ["dons", "collecte", "fondation", "fiscal"],
        "base_ttc": False,
    },
    # === Région Normandie ===
    {
        "id": "aide-7",
        "nom": "Subvention du Conseil Régional de Normandie — Patrimoine",
        "nom_court": "Région Normandie",
        "description": "Aide régionale pour la restauration du patrimoine bâti en Normandie, protégé ou non protégé.",
        "description_longue": "Le Conseil Régional de Normandie soutient la restauration du patrimoine bâti à travers un programme dédié. Les subventions peuvent couvrir jusqu'à 30 % du coût des travaux pour les monuments protégés et jusqu'à 20 % pour le patrimoine non protégé.",
        "categorie": "region",
        "type": "subvention",
        "organisme": "Conseil Régional de Normandie",
        "taux_max": 30,
        "montant_max": 100000,
        "criteres": {
            "regionEligible": ["normandie"],
            "proprietaireEligible": ["public_commune", "public_departement", "prive_personne_physique", "prive_sci", "association"],
            "travauxEligibles": ["toiture", "charpente", "maconnerie", "vitraux", "facade", "restauration_generale", "couverture", "menuiserie"],
        },
        "demarche_description": "1. Télécharger le formulaire sur le site du Conseil Régional\n2. Constituer le dossier complet\n3. Déposer en ligne ou par courrier\n4. Instruction par les services de la Région\n5. Passage en commission permanente",
        "documents_requis": ["Formulaire régional", "Délibération ou titre de propriété", "Extrait cadastral", "Programme de travaux", "Devis détaillé", "Plan de financement", "Photos état actuel", "RIB", "Attestation URSSAF"],
        "delai_instruction": "3 à 6 mois",
        "permanent": True,
        "tags": ["région", "normandie", "restauration"],
        "base_ttc": False,
    },
    # === Région AURA ===
    {
        "id": "aide-8",
        "nom": "Subvention du Conseil Régional Auvergne-Rhône-Alpes — Patrimoine",
        "nom_court": "Région AURA",
        "description": "Programme régional de soutien à la restauration du patrimoine monumental en Auvergne-Rhône-Alpes.",
        "description_longue": "La Région Auvergne-Rhône-Alpes dispose d'un fonds régional dédié à la restauration du patrimoine. Sont éligibles les monuments protégés (classés ou inscrits) et le patrimoine non protégé présentant un intérêt architectural reconnu.",
        "categorie": "region",
        "type": "subvention",
        "organisme": "Conseil Régional Auvergne-Rhône-Alpes",
        "taux_max": 25,
        "montant_max": 80000,
        "criteres": {
            "regionEligible": ["auvergne-rhone-alpes"],
            "proprietaireEligible": ["public_commune", "public_departement", "prive_personne_physique", "prive_sci", "association"],
            "travauxEligibles": ["toiture", "charpente", "maconnerie", "vitraux", "facade", "restauration_generale", "couverture"],
        },
        "demarche_description": "1. Déposer la demande en ligne sur la plateforme de la Région\n2. Joindre tous les justificatifs requis\n3. Instruction par les services patrimoine de la Région",
        "documents_requis": ["Formulaire régional", "Justificatif de propriété", "Extrait cadastral", "Devis", "Plan de financement", "Photos", "RIB"],
        "delai_instruction": "3 à 6 mois",
        "permanent": True,
        "tags": ["région", "auvergne-rhône-alpes", "restauration"],
        "base_ttc": False,
    },
    # === Région CVL ===
    {
        "id": "aide-9",
        "nom": "Subvention du Conseil Régional Centre-Val de Loire — Patrimoine",
        "nom_court": "Région CVL",
        "description": "Aide régionale pour la sauvegarde et la restauration du patrimoine en Centre-Val de Loire.",
        "description_longue": "Le Centre-Val de Loire, riche de ses châteaux de la Loire et de son patrimoine religieux, propose un programme de soutien à la restauration pour les propriétaires publics et privés.",
        "categorie": "region",
        "type": "subvention",
        "organisme": "Conseil Régional Centre-Val de Loire",
        "taux_max": 20,
        "montant_max": 60000,
        "criteres": {
            "regionEligible": ["centre-val-de-loire"],
            "proprietaireEligible": ["public_commune", "public_departement", "prive_personne_physique", "prive_sci", "association"],
            "travauxEligibles": ["toiture", "charpente", "maconnerie", "vitraux", "facade", "restauration_generale", "couverture"],
        },
        "demarche_description": "1. Contacter le service patrimoine de la Région\n2. Constituer le dossier avec les pièces requises\n3. Déposer la demande",
        "documents_requis": ["Formulaire régional", "Justificatif de propriété", "Devis", "Plan de financement", "Photos", "RIB"],
        "delai_instruction": "3 à 5 mois",
        "permanent": True,
        "tags": ["région", "centre-val-de-loire", "restauration"],
        "base_ttc": False,
    },
    # === Département Manche ===
    {
        "id": "aide-10",
        "nom": "Aide du Conseil Départemental de la Manche",
        "nom_court": "Département Manche",
        "description": "Subvention départementale pour le patrimoine dans la Manche.",
        "description_longue": "Le Conseil Départemental de la Manche propose des aides pour la restauration du patrimoine protégé et non protégé. Les dossiers sont plus simples que les dossiers régionaux.",
        "categorie": "departement",
        "type": "subvention",
        "organisme": "Conseil Départemental de la Manche",
        "taux_max": 15,
        "montant_max": 30000,
        "date_limite": "2026-03-12",
        "permanent": False,
        "criteres": {
            "departementEligible": ["50"],
            "proprietaireEligible": ["public_commune", "prive_personne_physique", "prive_sci", "association"],
            "travauxEligibles": ["toiture", "charpente", "maconnerie", "facade", "restauration_generale", "couverture", "menuiserie"],
        },
        "demarche_description": "1. Télécharger le formulaire départemental\n2. Joindre les pièces demandées\n3. Envoyer par courrier ou déposer en ligne",
        "documents_requis": ["Formulaire départemental", "Justificatif de propriété", "Devis", "Photos", "Plan de financement"],
        "delai_instruction": "1 à 2 mois",
        "tags": ["département", "manche", "normandie"],
        "base_ttc": False,
    },
    # === Département Indre-et-Loire ===
    {
        "id": "aide-11",
        "nom": "Aide du Conseil Départemental d'Indre-et-Loire",
        "nom_court": "Département 37",
        "description": "Programme départemental de soutien au patrimoine en Indre-et-Loire.",
        "description_longue": "L'Indre-et-Loire, département riche en châteaux et patrimoine religieux, propose des aides aux propriétaires pour la restauration de leurs monuments.",
        "categorie": "departement",
        "type": "subvention",
        "organisme": "Conseil Départemental d'Indre-et-Loire",
        "taux_max": 10,
        "montant_max": 20000,
        "permanent": True,
        "criteres": {
            "departementEligible": ["37"],
            "proprietaireEligible": ["public_commune", "prive_personne_physique", "prive_sci", "association"],
            "travauxEligibles": ["toiture", "charpente", "maconnerie", "facade", "restauration_generale", "couverture"],
        },
        "demarche_description": "1. Contacter le service patrimoine du Département\n2. Déposer le dossier de demande",
        "documents_requis": ["Formulaire départemental", "Justificatif de propriété", "Devis", "Photos"],
        "delai_instruction": "2 à 3 mois",
        "tags": ["département", "indre-et-loire", "centre-val-de-loire"],
        "base_ttc": False,
    },
    # === Défiscalisation MH ===
    {
        "id": "aide-12",
        "nom": "Déduction fiscale au titre des monuments historiques (Loi MH)",
        "nom_court": "Défiscalisation MH",
        "description": "Déduction de 100 % des charges de restauration et d'entretien du revenu global imposable, sans plafond.",
        "description_longue": "Le régime fiscal des Monuments Historiques permet aux propriétaires privés de monuments classés ou inscrits de déduire 100 % des charges foncières directement de leur revenu global imposable, sans aucun plafond. Ce dispositif est totalement exclu du plafonnement global des niches fiscales (10 000 €).",
        "categorie": "fiscalite",
        "type": "deduction_fiscale",
        "organisme": "Direction Générale des Finances Publiques",
        "criteres": {
            "protectionRequise": ["classe", "inscrit"],
            "segmentEligible": ["prive"],
            "proprietaireEligible": ["prive_personne_physique", "prive_sci"],
            "criteresSupplementaires": [
                {"label": "Conservation 15 ans minimum", "description": "Engagement écrit de conserver la propriété pendant au moins 15 ans à compter de l'acquisition."},
                {"label": "Détention en direct ou SCI familiale", "description": "Le bien doit être détenu en direct ou via une SCI familiale transparente (non soumise à l'IS)."},
                {"label": "Travaux validés par la DRAC", "description": "Les travaux doivent consister en une véritable restauration ou entretien, validés par les services de l'État (DRAC/UDAP)."},
            ],
        },
        "demarche_description": "1. S'assurer que le monument est classé ou inscrit MH\n2. Vérifier le mode de détention (direct ou SCI familiale non IS)\n3. Conserver tous les justificatifs de dépenses\n4. Déclarer les charges dans la déclaration de revenus (formulaire 2044 spécial)",
        "documents_requis": ["Arrêté de classement ou inscription", "Factures des travaux", "Relevé des charges foncières", "Déclaration de revenus fonciers 2044", "Attestation de détention depuis 15 ans (si revente)"],
        "delai_instruction": "Annuel (déclaration fiscale)",
        "permanent": True,
        "tags": ["fiscal", "privé", "déduction", "sans plafond"],
        "base_ttc": True,
    },
    # === Mécénat ===
    {
        "id": "aide-13",
        "nom": "Mécénat d'entreprise pour le patrimoine",
        "nom_court": "Mécénat",
        "description": "Les entreprises peuvent financer la restauration de monuments et bénéficier d'une réduction d'impôt de 60 % du montant du don.",
        "description_longue": "Le mécénat d'entreprise est un levier de financement puissant pour la restauration du patrimoine. Les dons des entreprises ouvrent droit à une réduction d'impôt sur les sociétés de 60 % dans la limite de 0,5 % du chiffre d'affaires.",
        "categorie": "mecenat",
        "type": "mecenat",
        "organisme": "Entreprises mécènes",
        "criteres": {
            "proprietaireEligible": ["public_commune", "public_departement", "prive_personne_physique", "prive_sci", "association"],
            "criteresSupplementaires": [
                {"label": "Projet d'intérêt général", "description": "Le projet doit présenter un intérêt général (patrimoine, culture, éducation)."},
            ],
        },
        "demarche_description": "1. Identifier des entreprises locales ou nationales intéressées par le patrimoine\n2. Préparer un dossier de mécénat (projet, budget, contreparties)\n3. Signer une convention de mécénat\n4. L'entreprise verse le don et reçoit un reçu fiscal",
        "documents_requis": ["Dossier de présentation du projet", "Budget prévisionnel", "Plan de contreparties", "Convention de mécénat"],
        "delai_instruction": "Variable",
        "permanent": True,
        "tags": ["entreprise", "mécénat", "RSE", "fiscal"],
        "base_ttc": False,
    },
    # === Loto du Patrimoine ===
    {
        "id": "aide-14",
        "nom": "Loto du Patrimoine — Mission Patrimoine",
        "nom_court": "Loto du Patrimoine",
        "description": "Programme national de la Fondation du Patrimoine financé par le Loto. Cible les monuments en péril avec un projet de restauration mature.",
        "description_longue": "La Mission Patrimoine portée par Stéphane Bern sélectionne chaque année environ 100 sites en péril. Les critères sont stricts : l'édifice doit être en état de péril avéré, présenter un intérêt patrimonial significatif, et disposer d'un projet opérationnel à court terme.",
        "categorie": "autre",
        "type": "subvention",
        "organisme": "Fondation du Patrimoine / Mission Patrimoine",
        "montant_max": 500000,
        "date_limite": "2026-04-30",
        "permanent": False,
        "criteres": {
            "proprietaireEligible": ["public_commune", "public_departement", "prive_personne_physique", "prive_sci", "association"],
            "etatConservationRequis": ["mauvais", "peril"],
            "criteresSupplementaires": [
                {"label": "Projet opérationnel", "description": "Le projet doit être prêt à démarrer : études techniques, autorisations, plan de financement bouclé, devis existants."},
                {"label": "Impact territorial", "description": "Potentiel de développement touristique, création de lien social, réutilisation pour de nouveaux usages."},
            ],
        },
        "demarche_description": "1. Répondre à l'appel à candidatures annuel\n2. Constituer un dossier complet avec photos et descriptif du péril\n3. Sélection par une commission nationale\n4. Annonce des lauréats lors des Journées du Patrimoine",
        "documents_requis": ["Formulaire de candidature Mission Patrimoine", "Photos montrant l'état de péril", "Descriptif historique et patrimonial", "Estimation des travaux", "Plan de financement", "Autorisations d'urbanisme"],
        "delai_instruction": "6 à 9 mois",
        "tags": ["loto", "mission patrimoine", "péril", "fondation"],
        "base_ttc": False,
    },
    # === DETR ===
    {
        "id": "aide-15",
        "nom": "Dotation d'Équipement des Territoires Ruraux (DETR)",
        "nom_court": "DETR",
        "description": "Dotation de l'État pour les communes rurales (< 20 000 hab.), pouvant couvrir des travaux sur le patrimoine communal.",
        "description_longue": "La DETR est une dotation d'investissement de l'État destinée aux communes de moins de 20 000 habitants et aux EPCI de moins de 75 000 habitants. La rénovation du patrimoine bâti communal (églises, bâtiments publics anciens) y figure parmi les priorités. Le taux varie de 20 à 50 %.",
        "categorie": "etat_drac",
        "type": "subvention",
        "organisme": "Préfecture (État)",
        "taux_max": 50,
        "plancher": 15000,
        "date_limite": "2026-03-31",
        "permanent": False,
        "criteres": {
            "segmentEligible": ["commune"],
            "proprietaireEligible": ["public_commune"],
            "communeMaxPopulation": 20000,
            "communeDeMoins10000Hab": True,
        },
        "demarche_description": "1. Déposer la demande auprès de la sous-préfecture ou préfecture\n2. La commission DETR examine les demandes\n3. Le préfet arrête la liste des subventions",
        "documents_requis": ["Formulaire DETR", "Délibération du conseil municipal", "Devis des travaux", "Plan de financement", "Fiche descriptive du projet"],
        "delai_instruction": "2 à 4 mois",
        "tags": ["commune rurale", "état", "investissement", "non protégé"],
        "base_ttc": False,
    },
    # === Aide SPR/Abords ===
    {
        "id": "aide-16",
        "nom": "Aide aux travaux en Site Patrimonial Remarquable et Abords",
        "nom_court": "Aide SPR/Abords",
        "description": "Subvention de l'État pour la restauration d'immeubles non protégés situés en SPR ou dans le périmètre des abords d'un monument historique.",
        "description_longue": "Le ministère de la Culture soutient la restauration d'immeubles non protégés au titre des MH mais situés dans un environnement urbain ou paysager protégé (SPR avec PSMV/PVAP, ou périmètre des abords d'un MH classé/inscrit). Le taux moyen est d'environ 15 %.",
        "categorie": "etat_drac",
        "type": "subvention",
        "organisme": "Ministère de la Culture (via DRAC)",
        "taux_max": 15,
        "criteres": {
            "protectionRequise": ["spr", "abords"],
            "proprietaireEligible": ["prive_personne_physique", "prive_sci", "association", "public_commune", "public_departement"],
            "travauxEligibles": ["toiture", "charpente", "maconnerie", "facade", "menuiserie", "couverture", "restauration_generale"],
        },
        "demarche_description": "1. Vérifier que l'immeuble est bien situé en SPR ou périmètre des abords\n2. Contacter la DRAC pour évaluer l'éligibilité\n3. Constituer le dossier avec programme de travaux\n4. Ne pas commencer les travaux avant réception de la demande",
        "documents_requis": ["Justificatif de situation en SPR ou abords", "Programme de travaux", "Devis détaillé", "Photos", "Plan de financement"],
        "delai_instruction": "3 à 6 mois",
        "permanent": True,
        "tags": ["SPR", "abords", "non protégé", "patrimoine urbain"],
        "base_ttc": False,
    },
]


def main():
    print(f"Seeding {len(AIDES)} aides into Supabase...")

    for aide in AIDES:
        result = (
            supabase.table("aides")
            .upsert(aide, on_conflict="id")
            .execute()
        )
        print(f"  ✓ {aide['id']} — {aide['nom_court']}")

    print(f"\nDone! {len(AIDES)} aides upserted.")


if __name__ == "__main__":
    main()
