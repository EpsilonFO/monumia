"""Profils de mesure du questionnaire, partagés par le banc et le test de CI.

À la racine du paquet, et pas sous `scripts/` : pyright n'analyse que `*.py`
racine et `services` (cf. pyproject), et le test doit pouvoir l'importer en
mode `prepend` sans bricoler `sys.path`.

Ce que ce module chiffre, c'est le TRONC COMMUN : les questions partagées par
au moins deux aides encore candidates. Elles seules sont posées dans le
questionnaire général ; celles qui ne servent qu'une aide se posent sur la
carte de cette aide. C'est ce nombre-là qu'on veut voir rester petit quand le
catalogue grossit — le total, lui, croît linéairement avec les aides et ne dit
rien d'utile.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aides_schema import Aide, FactDef
from eligibility_engine import run_deterministic_diagnostic

# Faits de PÉRIMÈTRE répondus « non » par les trois profils historiques, pour
# simuler un propriétaire dont le projet est une pure restauration. Figé ici
# tel quel : ces profils servent de point de comparaison avec les mesures
# publiées (69, 56 et 55 questions), et y toucher les rendrait incomparables.
# Le cadrage moderne passe par `_raisons`, que portent les profils suivants.
PERIMETRES_HISTORIQUES = (
    "projet_hebergement_touristique",
    "projet_developpement_touristique",
    "projet_equipement_culturel",
    "projet_lieu_diffusion_culturelle",
    "porteur_compagnie_artistique",
    "porteur_ecole_art",
    "projet_valorisation_historique",
)

_NON_HISTORIQUE: dict[str, object] = dict.fromkeys(PERIMETRES_HISTORIQUES, False)


@dataclass(frozen=True)
class Profil:
    """Un propriétaire type, tel que le moteur le voit."""

    monument: dict
    population: int
    #: Réponses déjà connues, clés réservées comprises (`_raisons`).
    answers: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class Mesure:
    """Ce qu'un profil rend au banc et au ratchet."""

    retenues: int
    eligibles: int
    #: Conditions `manual_check` restées en incertitude sur les aides retenues.
    manual_check: int
    questions: list[dict]
    tronc: list[dict]
    propres: list[dict]
    slugs_eligibles: set[str]


PROFILS: dict[str, Profil] = {
    # ── Les trois profils historiques du banc (mesures publiées : 69/56/55) ──
    "privé, inscrit, Pays de la Loire": Profil(
        monument=dict(
            protection="inscrit",
            proprietaire="prive_personne_physique",
            region="pays-de-la-loire",
            departement_num="44",
            etat_conservation="mauvais",
            travaux_envisages=["toiture", "facade"],
        ),
        population=3000,
        answers=dict(_NON_HISTORIQUE),
    ),
    "commune, non protégé, Nouvelle-Aquitaine": Profil(
        monument=dict(
            protection="non_protege",
            proprietaire="public_commune",
            region="nouvelle-aquitaine",
            departement_num="33",
            etat_conservation="moyen",
            travaux_envisages=["toiture"],
        ),
        population=3000,
        answers=dict(_NON_HISTORIQUE),
    ),
    "association, inscrit, Centre-Val de Loire": Profil(
        monument=dict(
            protection="inscrit",
            proprietaire="association",
            region="centre-val-de-loire",
            departement_num="37",
            etat_conservation="moyen",
            travaux_envisages=["maconnerie"],
        ),
        population=3000,
        answers=dict(_NON_HISTORIQUE),
    ),
    # ── Les profils du diagnostic du 2026-09-16 : église classée d'une commune
    # de 1 200 habitants, cadrée par la finalité comme le fait le wizard. ──
    #
    # `statut_juridique_porteur` fait partie du cadrage depuis le 2026-09-17 :
    # c'est la 2e question du QCM, tout le monde y répond, et sans sa réponse le
    # ratchet compte les ~90 questions d'entreprise que le gate bénéficiaires
    # écarte. Les trois profils historiques ci-dessus restent figés — leurs
    # mesures publiées (69/56/55) doivent rester comparables.
    "commune, classé, Grand Est (88), restauration": Profil(
        monument=dict(
            protection="classe",
            proprietaire="public_commune",
            region="grand-est",
            departement_num="88",
            etat_conservation="mauvais",
            travaux_envisages=["toiture", "charpente", "maconnerie"],
        ),
        population=1200,
        answers={
            "_raisons": ["restauration_travaux"],
            "statut_juridique_porteur": ["public_commune"],
        },
    ),
    "commune, classé, BFC (71), restauration": Profil(
        monument=dict(
            protection="classe",
            proprietaire="public_commune",
            region="bourgogne-franche-comte",
            departement_num="71",
            etat_conservation="mauvais",
            travaux_envisages=["toiture", "charpente", "maconnerie"],
        ),
        population=1200,
        answers={
            "_raisons": ["restauration_travaux"],
            "statut_juridique_porteur": ["public_commune"],
        },
    ),
    "personne physique, classé, BFC (71), restauration": Profil(
        monument=dict(
            protection="classe",
            proprietaire="prive_personne_physique",
            region="bourgogne-franche-comte",
            departement_num="71",
            etat_conservation="mauvais",
            travaux_envisages=["toiture", "charpente", "maconnerie"],
        ),
        population=1200,
        answers={
            "_raisons": ["restauration_travaux"],
            "statut_juridique_porteur": ["prive_personne_physique"],
        },
    ),
    "commune, classé, Île-de-France (77), restauration": Profil(
        monument=dict(
            protection="classe",
            proprietaire="public_commune",
            region="ile-de-france",
            departement_num="77",
            etat_conservation="mauvais",
            travaux_envisages=["toiture", "charpente", "maconnerie"],
        ),
        population=1200,
        answers={
            "_raisons": ["restauration_travaux"],
            "statut_juridique_porteur": ["public_commune"],
        },
    ),
    # Le périmètre qui s'élargit : « faire vivre le lieu », sans chantier. C'est
    # le profil que l'ouverture du catalogue (spectacles, jardins, hébergement,
    # médiation) fait gonfler en premier — d'où sa place dans le ratchet.
    #
    # `etat_travaux: aucun` EST le cadrage de ces deux profils (refonte
    # 2026-09-16) : la question se pose en tête du QCM, et c'est sa réponse qui
    # écarte les programmes de chantier et déduit un budget de travaux nul. Sans
    # elle, on mesurerait un projet d'animation dont on ne sait pas s'il comporte
    # des travaux — l'état d'avant, précisément celui que le testeur a subi.
    "commune, classé, BFC (71), faire vivre": Profil(
        monument=dict(
            protection="classe",
            proprietaire="public_commune",
            region="bourgogne-franche-comte",
            departement_num="71",
            etat_conservation="bon",
            travaux_envisages=[],
        ),
        population=1200,
        answers={
            "_raisons": ["valorisation_rayonnement"],
            "etat_travaux": "aucun",
            "statut_juridique_porteur": ["public_commune"],
        },
    ),
    # Le profil du testeur du 2026-09-16 (retours
    # `docs/retours-questionnaire-faire-vivre-le-lieu-2026-09-16.md`) : c'est
    # lui qui a vu trois questions de travaux dans un projet d'animation. Il
    # entre au ratchet pour que ce symptôme ne revienne pas par une ingestion.
    "privé, inscrit, Nièvre (58), faire vivre": Profil(
        monument=dict(
            protection="inscrit",
            proprietaire="prive_personne_physique",
            region="bourgogne-franche-comte",
            departement_num="58",
            etat_conservation="bon",
            travaux_envisages=[],
        ),
        population=1200,
        answers={
            "_raisons": ["valorisation_rayonnement"],
            "etat_travaux": "aucun",
            "statut_juridique_porteur": ["prive_personne_physique"],
        },
    ),
    # Les deux profils du testeur du 2026-09-22 : même monument, même intention,
    # deux FAMILLES différentes. Ils entrent au ratchet ensemble parce que c'est
    # leur ÉCART qui dit si le cadrage fonctionne — un projet d'hébergement ne
    # doit pas voir les questions d'un festival, et réciproquement.
    #
    # Le Grand Est est le territoire le plus dense du catalogue, et c'est là que
    # le bug s'est vu : 106 aides candidates, 80 questions générées, 31 dans le
    # tronc commun, contre 10 pour le même profil en Bourgogne-Franche-Comté.
    # Trois causes, toutes corrigées le 2026-09-22 — 17 aides « faire vivre »
    # sans famille (backfill + lint bloquant), la famille tourisme trop large
    # (scindée en deux), et « le fioul après les travaux » posé sans travaux
    # (`pertinent_si` sur `etat_travaux`).
    "association, inscrit, Grand Est (88), hébergement": Profil(
        monument=dict(
            protection="inscrit",
            proprietaire="association",
            region="grand-est",
            departement_num="88",
            etat_conservation="bon",
            travaux_envisages=[],
        ),
        population=1200,
        answers={
            "_raisons": ["valorisation_rayonnement"],
            "_familles": ["hebergement_touristique"],
            "etat_travaux": "aucun",
            "statut_juridique_porteur": ["association"],
        },
    ),
    "association, inscrit, Grand Est (88), spectacles": Profil(
        monument=dict(
            protection="inscrit",
            proprietaire="association",
            region="grand-est",
            departement_num="88",
            etat_conservation="bon",
            travaux_envisages=[],
        ),
        population=1200,
        answers={
            "_raisons": ["valorisation_rayonnement"],
            "_familles": ["spectacles_manifestations"],
            "etat_travaux": "aucun",
            "statut_juridique_porteur": ["association"],
        },
    ),
}


def partition_tronc(questions: list[dict]) -> tuple[list[dict], list[dict]]:
    """Sépare le tronc commun des questions propres à une seule aide.

    Miroir de `partitionnerQuestions` ([frontend/src/lib/qcm.ts]) sur des
    réponses vides : une question entre au tronc dès qu'elle porte sur au moins
    deux aides, et LA PORTEUSE SUIT SA DÉPENDANTE — une question branchée par
    `dependsOn` n'a de sens que si la porteuse est posée, qui reste donc au
    tronc même mono-aide. Jamais l'inverse.
    """
    tronc = {q["id"] for q in questions if len(q.get("aideIds") or []) >= 2}
    par_id = {q["id"]: q for q in questions}
    change = True
    while change:
        change = False
        for q in questions:
            dep = q.get("dependsOn")
            if not dep or q["id"] not in tronc:
                continue
            porteuse = dep.get("questionId")
            if porteuse in par_id and porteuse not in tronc:
                tronc.add(porteuse)
                change = True
    return (
        [q for q in questions if q["id"] in tronc],
        [q for q in questions if q["id"] not in tronc],
    )


def mesurer(aides: dict[str, Aide], facts: dict[str, FactDef], profil: Profil) -> Mesure:
    res = run_deterministic_diagnostic(
        aides, facts, profil.monument, profil.population, dict(profil.answers)
    )
    lignes = [
        *res["aidesEligibles"],
        *res["aidesPotentiellementEligibles"],
        *res["aidesAtteignables"],
        *res["aidesNonEligibles"],
    ]
    retenues = [r for r in lignes if r["statut"] != "non_eligible"]
    mc = sum(
        1
        for r in retenues
        for e in r["llmEvaluation"]["evaluations"]
        if e.get("nature") == "manual_check" and e.get("verdict") == "incertitude"
    )
    questions = res["qcmQuestions"]
    tronc, propres = partition_tronc(questions)
    return Mesure(
        retenues=len(retenues),
        eligibles=sum(1 for r in retenues if r["statut"] == "eligible"),
        manual_check=mc,
        questions=questions,
        tronc=tronc,
        propres=propres,
        slugs_eligibles={r["aide"]["id"] for r in retenues if r["statut"] == "eligible"},
    )


# ---------------------------------------------------------------------------
# Miroir Python de l'élimination front (frontend/src/lib/qcm.ts)
# ---------------------------------------------------------------------------
#
# `partition_tronc` compte les questions que le questionnaire POURRAIT poser,
# réponses vides. Ce n'est pas ce que vit l'utilisateur : il répond, et chaque
# réponse écarte des aides, donc des questions. Sur le profil « commune, classé,
# Grand Est (88), restauration », l'écart était de 68 questions calculées contre
# 18 réellement posées — et c'est le second chiffre qui décide si le tunnel est
# supportable.
#
# Les deux miroirs (celui-ci et `qcm.ts`) ne peuvent plus diverger en silence :
# `tests/fixtures/qcm_elimination.json` est rejouée des deux côtés.

#: Réponse « je ne sais pas » : elle n'écarte rien, par construction.
ID_SKIP = "skip"


def _ids_choisis(question: dict, reponse: object) -> list[str]:
    """Les ids réellement retenus, sans les réponses « je ne sais pas »."""
    bruts = reponse if isinstance(reponse, list) else [reponse]
    inconnues = {o["id"] for o in question.get("options") or [] if o.get("unknown")}
    return [i for i in bruts if isinstance(i, str) and i and i != ID_SKIP and i not in inconnues]


def aides_eliminees(answers: dict[str, object], questions: list[dict]) -> set[str]:
    """Miroir de `computeEliminatedAideIds` ([frontend/src/lib/qcm.ts]).

    Question à choix multiple : une aide n'est écartée que si CHAQUE case cochée
    l'écarte — cocher une case de plus ne peut que libérer des aides (sémantique
    existentielle du moteur, cf. `MultiValue`). D'où l'INTERSECTION, et non
    l'union, des éliminations par option. Sauf `eliminationsStrictesParOption`
    (exclusions `none_in`), où une seule case cochée suffit : union.

    Repli sur `eliminatingOptionIds` quand la carte fine ne rend rien, dans le
    même ordre que le front : une carte fine vide ne doit pas court-circuiter la
    forme grossière, sans quoi des aides resteraient vivantes ici et mortes à
    l'écran.
    """
    eliminees: set[str] = set()
    for question in questions:
        choisis = _ids_choisis(question, answers.get(question["id"]))
        if not choisis:
            continue
        par_option = question.get("eliminationsParOption") or {}
        commun: set[str] | None = None
        for identifiant in choisis:
            portee = set(par_option.get(identifiant) or [])
            commun = portee if commun is None else (commun & portee)
            if not commun:
                break
        # Exclusions strictes (`none_in`) : une seule case suffit, d'où l'UNION.
        strictes = question.get("eliminationsStrictesParOption") or {}
        for identifiant in choisis:
            eliminees |= set(strictes.get(identifiant) or [])
        if commun:
            eliminees |= commun
            continue
        grossier = set(question.get("eliminatingOptionIds") or [])
        if grossier and all(i in grossier for i in choisis):
            eliminees |= set(question.get("aideIds") or [])
    return eliminees


def est_visible(question: dict, answers: dict[str, object]) -> bool:
    """Miroir de `isVisible` : une question branchée attend sa porteuse.

    Fail-closed comme le front : tant que la porteuse n'est pas répondue, on
    pose quand même — une question de trop plutôt qu'une aide écartée en
    silence.
    """
    dep = question.get("dependsOn")
    if not dep:
        return True
    reponse = answers.get(dep["questionId"])
    donnes = [
        i
        for i in (reponse if isinstance(reponse, list) else [reponse])
        if isinstance(i, str) and i != ID_SKIP
    ]
    if not donnes:
        return True
    return any(i in dep["showForOptionIds"] for i in donnes)


def sert_une_aide_vivante(question: dict, eliminees: set[str]) -> bool:
    """Miroir de `isQuestionServingLiveAide`. Fail-open sans `aideIds`."""
    ids = question.get("aideIds")
    if not ids:
        return True
    return any(i not in eliminees for i in ids)


def _option_la_plus_eliminante(question: dict, eliminees: set[str]) -> str | None:
    """L'option qui écarte le plus d'aides encore vivantes.

    La règle est écrite noir sur blanc parce qu'elle décide de la mesure : elle
    donne le parcours le plus COURT, donc le chiffre le plus favorable au
    catalogue. C'est assumé — un ratchet ne se compare qu'à lui-même, et il lui
    faut surtout une règle stable. Un parcours mesuré sur la réponse la moins
    éliminante dirait autre chose (le pire cas), ce qui est une autre mesure, pas
    une correction de celle-ci.
    """
    par_option = question.get("eliminationsParOption") or {}
    grossier = set(question.get("eliminatingOptionIds") or [])
    toutes = set(question.get("aideIds") or [])
    inconnues = {o["id"] for o in question.get("options") or [] if o.get("unknown")}
    meilleur: tuple[int, str] | None = None
    for option in question.get("options") or []:
        identifiant = option["id"]
        if identifiant == ID_SKIP or identifiant in inconnues:
            continue
        portee = set(par_option.get(identifiant) or ())
        if not portee and identifiant in grossier:
            portee = toutes
        gain = len(portee - eliminees)
        # L'id départage à gain égal : le parcours doit être le MÊME d'un
        # passage à l'autre, sinon le ratchet mesure du bruit.
        if meilleur is None or (gain, identifiant) > (meilleur[0], meilleur[1]):
            meilleur = (gain, identifiant)
    return meilleur[1] if meilleur else None


def parcours_simule(aides: dict[str, Aide], facts: dict[str, FactDef], profil: Profil) -> list[str]:
    """Les questions du tronc RÉELLEMENT posées, dans l'ordre, jusqu'à épuisement.

    À chaque tour : la première question du tronc encore visible
    (`dependsOn` respecté) et encore servante (au moins une aide vivante), à
    laquelle on répond par l'option la plus éliminante. Le tour suivant repart
    des aides restantes — c'est ce que fait le front, question après question.
    """
    mesure = mesurer(aides, facts, profil)
    tronc = mesure.tronc
    answers: dict[str, object] = {}
    posees: list[str] = []
    # Borne de sûreté : une question par tour, jamais deux fois la même.
    for _ in range(len(tronc)):
        eliminees = aides_eliminees(answers, tronc)
        suivante = next(
            (
                q
                for q in tronc
                if q["id"] not in answers
                and est_visible(q, answers)
                and sert_une_aide_vivante(q, eliminees)
            ),
            None,
        )
        if suivante is None:
            break
        choix = _option_la_plus_eliminante(suivante, eliminees)
        if choix is None:
            break
        answers[suivante["id"]] = choix
        posees.append(suivante["id"])
    return posees


def delta_tronc(
    aides_avant: dict[str, Aide],
    aides_apres: dict[str, Aide],
    facts: dict[str, FactDef],
) -> dict[str, tuple[int, int, list[str]]]:
    """Par profil : (tronc avant, tronc après, ids des questions ENTRANTES).

    Sert à chiffrer ce qu'une aide coûte au questionnaire de tout le monde —
    la seule grandeur qu'une fiche de review ne peut pas deviner depuis la
    fiche de l'aide seule.
    """
    sortie: dict[str, tuple[int, int, list[str]]] = {}
    for nom, profil in PROFILS.items():
        avant = mesurer(aides_avant, facts, profil)
        apres = mesurer(aides_apres, facts, profil)
        ids_avant = {q["id"] for q in avant.tronc}
        entrantes = sorted(q["id"] for q in apres.tronc if q["id"] not in ids_avant)
        sortie[nom] = (len(avant.tronc), len(apres.tronc), entrantes)
    return sortie
