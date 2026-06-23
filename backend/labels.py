"""
Référentiels de libellés humains pour les codes utilisés en DB.

Mappings code → libellé pour : protection MH, type de propriétaire, type de
travaux, état de conservation, région (kebab-case) et département (INSEE).
Les codes doivent rester alignés avec les valeurs stockées dans les tables
`aides_*` et `communes` (cf. matching_engine.prefiltrer_aides).
"""

PROTECTION_LABELS = {
    "classe": "Classé Monument Historique",
    "inscrit": "Inscrit Monument Historique",
    "abords": "En périmètre d'un MH (abords)",
    "spr": "Site Patrimonial Remarquable (SPR)",
    "non_protege": "Non protégé",
}

OWNERSHIP_LABELS = {
    "public_commune": "Commune",
    "public_departement": "Département",
    "public_region": "Région",
    "public_etat": "État",
    "prive_personne_physique": "Propriétaire privé (personne physique)",
    "prive_sci": "SCI",
    "association": "Association",
    "mixte": "Propriété mixte",
}

TRAVAUX_LABELS = {
    "toiture": "Toiture",
    "charpente": "Charpente",
    "couverture": "Couverture",
    "facade": "Façade",
    "maconnerie": "Maçonnerie",
    "vitraux": "Vitraux",
    "peintures_murales": "Peintures murales",
    "menuiserie": "Menuiserie",
    "electricite": "Électricité",
    "plomberie": "Plomberie",
    "chauffage": "Chauffage",
    "accessibilite": "Accessibilité",
    "mise_en_securite": "Mise en sécurité",
    "restauration_generale": "Restauration générale",
    "etude_prealable": "Étude préalable",
    "mobilier": "Mobilier",
    "orgues": "Orgues",
    "parcs_jardins": "Parcs et jardins",
    "protection_solaire": "Protection solaire",
    "ventilation": "Ventilation",
}

ETAT_LABELS = {
    "bon": "Bon état",
    "moyen": "État moyen",
    "mauvais": "Mauvais état",
    "peril": "En péril",
}

REGION_LABELS = {
    "auvergne-rhone-alpes": "Auvergne-Rhône-Alpes",
    "bourgogne-franche-comte": "Bourgogne-Franche-Comté",
    "bretagne": "Bretagne",
    "centre-val-de-loire": "Centre-Val de Loire",
    "corse": "Corse",
    "grand-est": "Grand Est",
    "hauts-de-france": "Hauts-de-France",
    "ile-de-france": "Île-de-France",
    "normandie": "Normandie",
    "nouvelle-aquitaine": "Nouvelle-Aquitaine",
    "occitanie": "Occitanie",
    "pays-de-la-loire": "Pays de la Loire",
    "provence-alpes-cote-d-azur": "Provence-Alpes-Côte d'Azur",
    "guadeloupe": "Guadeloupe",
    "martinique": "Martinique",
    "guyane": "Guyane",
    "la-reunion": "La Réunion",
    "mayotte": "Mayotte",
}

# INSEE department codes → libellé. Used to humanise filter labels;
# `aides_v3.departements` and `communes.departement_num` both store the
# code form (e.g. "75", "2A", "971").
DEPARTEMENT_LABELS = {
    "01": "Ain",
    "02": "Aisne",
    "03": "Allier",
    "04": "Alpes-de-Haute-Provence",
    "05": "Hautes-Alpes",
    "06": "Alpes-Maritimes",
    "07": "Ardèche",
    "08": "Ardennes",
    "09": "Ariège",
    "10": "Aube",
    "11": "Aude",
    "12": "Aveyron",
    "13": "Bouches-du-Rhône",
    "14": "Calvados",
    "15": "Cantal",
    "16": "Charente",
    "17": "Charente-Maritime",
    "18": "Cher",
    "19": "Corrèze",
    "2A": "Corse-du-Sud",
    "2B": "Haute-Corse",
    "21": "Côte-d'Or",
    "22": "Côtes-d'Armor",
    "23": "Creuse",
    "24": "Dordogne",
    "25": "Doubs",
    "26": "Drôme",
    "27": "Eure",
    "28": "Eure-et-Loir",
    "29": "Finistère",
    "30": "Gard",
    "31": "Haute-Garonne",
    "32": "Gers",
    "33": "Gironde",
    "34": "Hérault",
    "35": "Ille-et-Vilaine",
    "36": "Indre",
    "37": "Indre-et-Loire",
    "38": "Isère",
    "39": "Jura",
    "40": "Landes",
    "41": "Loir-et-Cher",
    "42": "Loire",
    "43": "Haute-Loire",
    "44": "Loire-Atlantique",
    "45": "Loiret",
    "46": "Lot",
    "47": "Lot-et-Garonne",
    "48": "Lozère",
    "49": "Maine-et-Loire",
    "50": "Manche",
    "51": "Marne",
    "52": "Haute-Marne",
    "53": "Mayenne",
    "54": "Meurthe-et-Moselle",
    "55": "Meuse",
    "56": "Morbihan",
    "57": "Moselle",
    "58": "Nièvre",
    "59": "Nord",
    "60": "Oise",
    "61": "Orne",
    "62": "Pas-de-Calais",
    "63": "Puy-de-Dôme",
    "64": "Pyrénées-Atlantiques",
    "65": "Hautes-Pyrénées",
    "66": "Pyrénées-Orientales",
    "67": "Bas-Rhin",
    "68": "Haut-Rhin",
    "69": "Rhône",
    "70": "Haute-Saône",
    "71": "Saône-et-Loire",
    "72": "Sarthe",
    "73": "Savoie",
    "74": "Haute-Savoie",
    "75": "Paris",
    "76": "Seine-Maritime",
    "77": "Seine-et-Marne",
    "78": "Yvelines",
    "79": "Deux-Sèvres",
    "80": "Somme",
    "81": "Tarn",
    "82": "Tarn-et-Garonne",
    "83": "Var",
    "84": "Vaucluse",
    "85": "Vendée",
    "86": "Vienne",
    "87": "Haute-Vienne",
    "88": "Vosges",
    "89": "Yonne",
    "90": "Territoire de Belfort",
    "91": "Essonne",
    "92": "Hauts-de-Seine",
    "93": "Seine-Saint-Denis",
    "94": "Val-de-Marne",
    "95": "Val-d'Oise",
    "971": "Guadeloupe",
    "972": "Martinique",
    "973": "Guyane",
    "974": "La Réunion",
    "976": "Mayotte",
}


# Closed set of allowed incertitude categories. MUST match the identifiers
# listed in prompts/eligibility.j2 — any drift causes the LLM-emitted category
# to be coerced to "autre", which in turn breaks the QCM ↔ incertitude matching
# (the frontend marks an incertitude as clarified by exact category equality).
ALLOWED_INCERTITUDE_CATEGORIES = {
    # Procédure et antériorité
    "non_commencement_travaux",
    "accord_abf_prealable",
    "convention_drac",
    "demande_autorisation_urbanisme",
    "delai_realisation_post_accord",
    # Intervenants et qualifications
    "architecte_mh_acmh",
    "artisan_rge",
    "qualification_specifique",
    # Diagnostics et études
    "diagnostic_prealable",
    "dpe_audit_energetique",
    "gain_energetique_minimum",
    "etude_impact_patrimonial",
    # Ouverture, usage et destination
    "ouverture_public",
    "usage_batiment",
    "residence_principale",
    "usage_non_lucratif",
    "anciennete_batiment",
    # Engagements et durée
    "engagement_conservation",
    "engagement_location",
    "engagement_ouverture_public",
    "maintien_activite",
    # Conditions financières
    "revenus_plafond",
    "montant_minimum_projet",
    "cumul_aides_plafond",
    "cofinancement_requis",
    "regime_fiscal",
    # Garanties et assurances
    "assurance_garantie",
    # Critères sociaux et territoriaux
    "emploi_insertion",
    "formation_apprentissage",
    "accessibilite_pmr_erp",
    "territoire_specifique",
    "impact_territorial",
    # Innovation et partenariats
    "innovation_saut_techno",
    "partenariat_consortium",
    # Autres
    "label_certification_prealable",
    "autre",
}
