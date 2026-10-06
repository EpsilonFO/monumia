"""
Référentiels de libellés humains pour les codes utilisés en DB.

Mappings code → libellé pour : protection MH, type de propriétaire, type de
travaux, état de conservation, type d'édifice, région (kebab-case) et
département (INSEE).
Les codes doivent rester alignés avec les valeurs stockées dans les tables
`aides_v3` et `communes`, et avec les YAML de `data/aides/`.
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
    "public_epci": "Intercommunalité (EPCI)",
    "public_departement": "Département",
    "public_region": "Région",
    "public_etat": "État",
    "syndicat_mixte": "Syndicat mixte / Parc naturel régional",
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
    "etude_prealable": "Étude préalable",
    "mobilier": "Mobilier",
    "archives": "Archives et documents (photographies, fonds papier, audiovisuel)",
    "orgues": "Orgues",
    "parcs_jardins": "Parcs et jardins",
    "protection_solaire": "Protection solaire",
    "ventilation": "Ventilation",
    # Le DOMAINE autour du bâti, ajouté le 2026-09-17. Un monument, ce n'est pas
    # qu'un bâtiment : des terres, un bois, un étang, une activité installée. Ces
    # quatre codes existent pour que les aides qui ne financent QUE cela puissent
    # se cadrer — sans eux, elles n'ont aucun moyen de dire « je ne finance pas
    # votre toiture » et posent leurs questions à tout le monde (mesuré sur le
    # lot Grand Est : 88 aides dans le tronc commun d'une commune des Vosges).
    "exploitation_agricole": "Exploitation agricole (plantations, vergers, haies)",
    "foret": "Forêt et desserte forestière",
    "eau_milieux_aquatiques": "Eau et milieux aquatiques (cours d'eau, étang, captage)",
    "equipement_professionnel": "Équipement professionnel (matériel, véhicule)",
    # Ajouté le 2026-09-23 : le numérique était une question posée à tous
    # (`projet_composante_numerique`) alors que c'est l'OBJET du projet. Les
    # aides qui ne financent que cela se cadrent par `hard_filters.travaux`.
    "equipement_numerique": "Équipement numérique (informatique, outils de médiation, affichage, réseau)",
}

# ── Familles thématiques d'une aide ────────────────────────────────────────────
#
# L'axe de cadrage d'un projet « faire vivre le lieu », ce que `raison` ne sait
# pas dire : ses quatre valeurs mettent dans le même sac un festival, un gîte et
# un outil de médiation. Liste FERMÉE, portée par l'aide (`Aide.familles`), et
# non par un fait : la famille est décidée par un humain à la prospection, une
# fois pour toutes, là où un fait demanderait une réponse à chaque utilisateur.
#
# Les clés et leurs descriptions viennent de `scripts/prospection/tri.py`
# (branche `feat/pipeline-prospection-ingestion`), où elles sont déjà calculées
# pour chaque dispositif candidat : c'est ce travail que l'ingestion perdait.
# `adjacente` et `hors_perimetre` restent des valeurs de TRI, pas des familles —
# elles disent de garder ou d'écarter un candidat, pas ce que l'aide finance.
#
# Scission du 2026-09-22 : `tourisme_hebergement` mettait dans le même sac un
# gîte et un sentier de randonnée. Un testeur qui cochait la tuile s'entendait
# demander « créez-vous un hébergement touristique ? » juste après l'avoir dit —
# la famille ne pouvait pas répondre à sa place, puisqu'elle couvrait aussi les
# sites de visite. Les deux codes qui la remplacent le peuvent (cf.
# `FAITS_DEDUITS_VRAI_DES_FAMILLES`). L'ancien code survit en ALIAS
# (`FAMILLES_HERITEES`), pour les projets déjà enregistrés.
#
# Deux usages, deux textes : `FAMILLES_LABELS` est le libellé produit (tuile du
# wizard, puce d'une fiche d'aide), `FAMILLES_DESCRIPTION` la définition qui
# part dans les prompts d'ingestion et sert de règle au relecteur.
FAMILLES_LABELS = {
    "restauration_bati": "Restauration du bâti",
    "energie_climat": "Énergie et climat",
    "eau_nature_domaine": "Eau, nature et domaine",
    "securite_risques": "Sécurité et risques",
    "parcs_jardins_paysages": "Parcs, jardins et paysages",
    "hebergement_touristique": "Hébergement touristique",
    "tourisme_visite": "Site de visite et tourisme",
    "activite_economique_lieu": "Activité économique dans le lieu",
    "spectacles_manifestations": "Spectacles et manifestations",
    "vie_locale_associative": "Vie locale et associative",
    "mediation_numerique_expositions": "Médiation, expositions, musée, numérique",
    "accessibilite_publics": "Accessibilité et accueil des publics",
    "etudes_ingenierie": "Études et ingénierie",
    "labels_passerelles": "Labels et passerelles",
}

FAMILLES_DESCRIPTION = {
    "restauration_bati": (
        "travaux sur le bâti, protégé ou non, y compris le mobilier attaché "
        "(orgues, cloches, vitraux)"
    ),
    "energie_climat": (
        "rénovation énergétique, chauffage et énergies renouvelables (géothermie, bois, "
        "réseaux de chaleur, solaire), adaptation au changement climatique, matériaux "
        "biosourcés, AMO énergie"
    ),
    "eau_nature_domaine": (
        "eau et sécheresse, cours d'eau et plans d'eau (moulins, douves, étangs), "
        "biodiversité, Natura 2000, forêt, vergers, haies, agriculture ou viticulture "
        "du domaine"
    ),
    "securite_risques": (
        "catastrophes naturelles, inondations, incendie, foudre, sûreté, mise en sécurité"
    ),
    "parcs_jardins_paysages": "parcs et jardins, arbres, paysages, abords",
    "hebergement_touristique": (
        "hébergements touristiques : gîtes, chambres d'hôtes, meublés, hôtels, hostels, "
        "hébergement collectif, hôtellerie de plein air, insolite"
    ),
    "tourisme_visite": (
        "sites de visite, itinérance et randonnée, événementiel touristique, promotion et "
        "stratégie touristique d'un territoire"
    ),
    "activite_economique_lieu": (
        "reconversion et nouvel usage, tiers-lieux, commerce, artisanat ou ESS installés "
        "dans le lieu, création ou reprise d'activité, prêts, garanties et chèques "
        "mobilisables par l'exploitant du monument"
    ),
    "spectacles_manifestations": (
        "festivals, saisons, résidences, manifestations accueillies dans le monument"
    ),
    "vie_locale_associative": (
        "vie associative, fêtes et initiatives locales, mémoire, langues et cultures "
        "régionales, coopération, dont une association d'amis du monument peut bénéficier"
    ),
    "mediation_numerique_expositions": (
        "signalétique, scénographie, numérique, expositions, musées, publications, inventaire"
    ),
    "accessibilite_publics": "accessibilité, accueil des publics, handicap",
    "etudes_ingenierie": "études préalables, diagnostics, ingénierie, AMO",
    "labels_passerelles": "labels et dispositifs qui ouvrent l'accès à d'autres aides",
}

# Codes de famille RETIRÉS du référentiel → ce qu'ils valent aujourd'hui.
#
# Un projet enregistré porte ses familles dans `projets.questionnaire._familles`,
# et rien ne les réécrit. Sans cette table, un projet coché « Tourisme et
# hébergement » avant la scission déclarerait une famille que plus aucune aide ne
# porte : `hors_famille` (déclaré non vide, intersection vide) écarterait TOUTES
# les aides taguées — l'inverse exact de ce que l'utilisateur a demandé.
#
# Un héritage ÉLARGIT donc toujours (l'ancien code vaut ses deux successeurs) ;
# il ne peut rien retirer. Lu par le moteur (`familles_heritees`, appliqué avant
# `hors_famille` comme avant les déductions) et par le front (`readFamilles`,
# qui recoche les deux tuiles à la reprise du wizard). Les `tri.jsonl` de
# prospection ne sont PAS réécrits pour la même raison : ce sont des décisions
# humaines datées, et l'alias suffit à les lire.
FAMILLES_HERITEES: dict[str, frozenset[str]] = {
    "tourisme_hebergement": frozenset({"hebergement_touristique", "tourisme_visite"}),
}

ETAT_LABELS = {
    "bon": "Bon état",
    "moyen": "État moyen",
    "mauvais": "Mauvais état",
    "peril": "En péril",
}

# ── Type d'édifice (colonne `monuments.type_edifice`) ──────────────────────────
#
# Ajouté le 2026-09-30. Le questionnaire demandait à un propriétaire de lavoir
# « votre édifice est-il une église ? », à celui d'une église « le bien est-il
# représentatif de l'histoire et de la culture juives ? » : une quinzaine de
# faits constatifs de `facts.yaml` décrivent la NATURE du bien, et chacun se
# posait à part. Le type, saisi une fois sur la fiche, y répond d'avance par
# `auto_source` (table `eligibility_engine.DEDUCTIONS_TYPE_EDIFICE`).
#
# CHOIX MULTIPLE (même jour, migration 20260930082523) : un domaine réunit un
# château, sa chapelle, son pigeonnier. Un fait n'est alors déduit qu'à
# l'unanimité des types cochés.
#
# Liste FERMÉE en quatre endroits, qui doivent rester d'accord : ce dict, le
# CHECK de la migration qui pose la colonne, `TYPES_EDIFICE` côté front
# (`frontend/src/constants/monument-options.ts`) et ses regroupements
# (`GROUPES_TYPE_EDIFICE`, `lib/fiche-monument.ts`). `tests/test_type_edifice.py`
# le vérifie. Les codes sont figés : les tables de déduction les citent.
#
# L'ordre est celui des regroupements du menu (religieux, demeures, civils,
# rural, ouvrages et mémoire). Il n'y a pas de « je ne sais pas » : laisser le
# champ vide le dit, et `autre` ne déduit rien non plus (fail-closed).
TYPE_EDIFICE_LABELS = {
    "eglise": "Église, cathédrale, basilique",
    "chapelle": "Chapelle",
    "abbaye_couvent": "Abbaye, prieuré, couvent",
    "temple": "Temple protestant",
    "synagogue": "Synagogue",
    "croix_calvaire": "Croix, calvaire",
    "autre_religieux": "Autre édifice religieux",
    "chateau": "Château, château fort",
    "manoir_demeure": "Manoir, demeure",
    "hotel_particulier": "Hôtel particulier",
    "maison": "Maison",
    "edifice_public": "Édifice public",
    "hopital": "Hôpital, hospice, Hôtel-Dieu",
    "halle": "Halle, marché couvert",
    "patrimoine_industriel": "Patrimoine industriel",
    "ferme": "Ferme, grange, bâtiment agricole",
    "moulin": "Moulin",
    "lavoir_fontaine": "Lavoir, fontaine",
    "pigeonnier": "Pigeonnier, colombier",
    "petit_patrimoine": "Four, puits, petit patrimoine",
    "fortification": "Fortification, rempart, porte de ville",
    "pont": "Pont, aqueduc, ouvrage d'art",
    "jardin": "Parc, jardin",
    "site_archeologique": "Site archéologique, mégalithe",
    "monument_aux_morts": "Monument aux morts",
    "monument_commemoratif": "Statue, monument commémoratif",
    "autre": "Autre",
}

# Les deux PRÉCISIONS de la fiche. Chacune répond à un fait existant :
# `edifice_toujours_affecte_culte` et `edifice_architecture_romane`.
#
# L'affectation au culte suit le type d'édifice : elle est proposée dès qu'AU
# MOINS un type coché l'admet ; quand plus aucun ne l'admet, elle n'est ni
# proposée (front), ni conservée (router), ni lue (`build_context`) : une
# réponse « affecté au culte » restée d'un premier choix « église » ne doit pas
# suivre la fiche devenue « château ». Elle ne nourrit que son propre fait :
# château + chapelle « affectée au culte » ne font pas un édifice cultuel.
TYPES_AVEC_AFFECTATION_CULTE = frozenset(
    {"eglise", "chapelle", "abbaye_couvent", "temple", "synagogue", "autre_religieux"}
)

# L'architecture romane suit le DOMAINE Mérimée du bien (2026-10-06), pas le
# type coché : la précision n'est proposée qu'aux édifices que Mérimée range en
# « architecture religieuse », seule ou combinée (« architecture
# religieuse;architecture militaire »). Les autres biens, et ceux saisis à la
# main, n'ont pas de champ : le fait reste inconnu, et le questionnaire pose la
# question si une aide la cite. Aucun « non » n'est déduit d'office, puisque le
# programme roman vise « toutes les catégories » d'édifices. Miroir exact :
# `architectureRomaneApplicable` (frontend/src/lib/fiche-monument.ts).
DOMAINE_ARCHITECTURE_RELIGIEUSE = "architecture religieuse"


def architecture_romane_applicable(domaine: object) -> bool:
    """Le domaine Mérimée contient-il « architecture religieuse » ?

    Découpé sur `;`, chaque terme sans espaces autour ni majuscules. Absent,
    vide ou d'un autre type : non.
    """
    if not isinstance(domaine, str):
        return False
    termes = (t.strip().lower() for t in domaine.split(";"))
    return DOMAINE_ARCHITECTURE_RELIGIEUSE in termes


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

# Rattachement d'un département à sa région (découpage de 2016, DOM compris).
# Le catalogue ne porte PAS cette information : une aide départementale ne
# déclare que ses `hard_filters.departements`, et c'est cette table qui permet
# de la compter dans sa région — sans elle, une région dont toutes les aides
# sont départementales apparaîtrait vide. La partition est exhaustive et
# disjointe sur DEPARTEMENT_LABELS, ce que `test_labels_geo` vérifie : un
# département oublié ici disparaîtrait silencieusement des statistiques.
REGION_DEPARTEMENTS = {
    "auvergne-rhone-alpes": [
        "01",
        "03",
        "07",
        "15",
        "26",
        "38",
        "42",
        "43",
        "63",
        "69",
        "73",
        "74",
    ],
    "bourgogne-franche-comte": ["21", "25", "39", "58", "70", "71", "89", "90"],
    "bretagne": ["22", "29", "35", "56"],
    "centre-val-de-loire": ["18", "28", "36", "37", "41", "45"],
    "corse": ["2A", "2B"],
    "grand-est": ["08", "10", "51", "52", "54", "55", "57", "67", "68", "88"],
    "hauts-de-france": ["02", "59", "60", "62", "80"],
    "ile-de-france": ["75", "77", "78", "91", "92", "93", "94", "95"],
    "normandie": ["14", "27", "50", "61", "76"],
    "nouvelle-aquitaine": ["16", "17", "19", "23", "24", "33", "40", "47", "64", "79", "86", "87"],
    "occitanie": ["09", "11", "12", "30", "31", "32", "34", "46", "48", "65", "66", "81", "82"],
    "pays-de-la-loire": ["44", "49", "53", "72", "85"],
    "provence-alpes-cote-d-azur": ["04", "05", "06", "13", "83", "84"],
    "guadeloupe": ["971"],
    "martinique": ["972"],
    "guyane": ["973"],
    "la-reunion": ["974"],
    "mayotte": ["976"],
}

#: L'inverse : code INSEE du département → code de sa région.
DEPARTEMENT_REGION = {
    departement: region
    for region, departements in REGION_DEPARTEMENTS.items()
    for departement in departements
}
