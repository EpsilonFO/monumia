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
        answers={"_raisons": ["restauration_travaux"]},
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
        answers={"_raisons": ["restauration_travaux"]},
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
        answers={"_raisons": ["restauration_travaux"]},
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
        answers={"_raisons": ["restauration_travaux"]},
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
        answers={"_raisons": ["valorisation_rayonnement"], "etat_travaux": "aucun"},
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
        answers={"_raisons": ["valorisation_rayonnement"], "etat_travaux": "aucun"},
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
