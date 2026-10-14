"""Reformuler la question d'un fait existant : le geste exceptionnel de l'agent (`R1-reformulation`).

Face à un fait presque bon (même information, question trop étroite ou ambiguë
pour le cas de sa source), l'agent avait trois sorties : forcer le sens,
proposer un fait voisin, ou se replier sur `manual_check`. Celle-ci en ajoute
une quatrième : proposer une tournure plus juste de `question` et de `help`,
jamais du sens. Elle devient une case pour Félix, et rien n'est réécrit avant
sa réponse (`catalogue.reformulations`).

**L'aide doit être juste avec la question ACTUELLE.** La reformulation améliore
ce que lit le propriétaire, elle ne conditionne jamais le typage : un refus,
du code ou de Félix, est sans conséquence sur l'aide. D'où des messages de
refus qui renvoient tous vers « garde la question actuelle ».

Les refus, dans l'ordre :

1. fait absent de `facts.yaml` (un fait en attente se retire et se repropose) ;
2. `detail_fait` ou `conditions_du_fait` non appelés sur ce fait ;
3. type hors `boolean` / `enum` / `multi_enum`, les seuls que P1 sait juger ;
4. fait cité plus de `citations_max` fois : trop partagé pour une ingestion ;
5. forme : celle d'un fait neuf (`faits._refus_de_forme`), sur la nouvelle
   question ;
6. tournure trop éloignée de l'actuelle (`similarite_min`) ;
7. une reformulation d'une autre aide attend déjà sur ce fait ;
8. le sens : chaque gate qui cite le fait est rejugée par P1 avec l'ancienne
   puis la nouvelle question (même consigne, même empreinte, donc mêmes
   seuils). Refus si une gate gagne un désaccord, ou si une probabilité bouge
   de plus de `derive_max`. Jev ou l'espace en panne : refus.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from veille_text import normalize

from aides_schema import Aide, FactDef

from .atelier import Atelier
from .faits import Citation, _refus_de_forme

TYPES_JUGES = ("boolean", "enum", "multi_enum")
MIN_CAR_JUSTIFICATION = 60
#: Les lignes de citations recopiées dans la proposition, pour la case.
MAX_EXTRAIT = 12
GARDE = (
    "Garde la question actuelle : ton aide doit être juste avec elle, et ce refus ne "
    "change rien à son typage."
)


def _plat(texte: str | None) -> str:
    return " ".join((texte or "").split())


def _refus(message: str) -> tuple[str, None]:
    return f"ERREUR : {message}\n{GARDE}", None


def _rejuger(
    fact_id: str,
    nouveau: FactDef,
    facts: Mapping[str, FactDef],
    aides: Mapping[str, Aide],
    *,
    derive_max: float,
    juge: Any = None,
    seuils_p1: tuple[float, float] | None = None,
) -> tuple[str | None, dict[str, Any]]:
    """(motif de refus ou None, résumé) du rejugement P1 de chaque gate qui cite le fait."""
    from catalogue import espace
    from catalogue import polarite as pol

    if juge is None and not espace.actif():
        return "le contrôle du sens (Jev) est coupé dans ce run : rien ne peut le garantir.", {}
    avec = {**facts, fact_id: nouveau}
    paires = []
    for slug in sorted(aides):
        aide = aides[slug]
        for c in aide.conditions:
            if c.fact != fact_id:
                continue
            avant = pol.gate_de(slug, aide.nom, c, dict(facts))
            apres = pol.gate_de(slug, aide.nom, c, avec)
            if avant is not None and apres is not None:
                paires.append((avant, apres))
    if not paires:
        return None, {"gates": 0, "derive": 0.0}
    try:
        juge = juge or pol._juge()
        haut, bas = seuils_p1 or pol._seuils()
        with ThreadPoolExecutor(pol.PARALLELISME) as pool:
            jugees = list(pool.map(juge.juger, [g for paire in paires for g in paire]))
    except Exception as exc:  # noqa: BLE001 — Jev en panne : refus, jamais d'acceptation
        return f"le contrôle du sens est en panne ({type(exc).__name__}).", {}
    if any(p is None for p in jugees):
        return "Jev n'a pas pu rejuger toutes les conditions qui citent le fait.", {}
    nouveaux: list[str] = []
    derive, ou = 0.0, ""
    for k, (avant, apres) in enumerate(paires):
        p0, p1 = jugees[2 * k] or {}, jugees[2 * k + 1] or {}
        deja = {(d.reponse.id, d.sens) for d in pol.desaccords(avant, p0, haut, bas)}
        for d in pol.desaccords(apres, p1, haut, bas):
            if (d.reponse.id, d.sens) not in deja:
                verbe = "écarterait à tort" if d.sens == "ecarte_a_tort" else "laisserait passer"
                nouveaux.append(f"{apres.ref} {verbe} « {d.reponse.label} » ({d.p_remplie:.0%})")
        for r in avant.reponses:
            if r.id in p0 and r.id in p1 and abs(p1[r.id] - p0[r.id]) > derive:
                derive = abs(p1[r.id] - p0[r.id])
                ou = f"{avant.ref}, réponse « {r.label} » : {p0[r.id]:.0%} → {p1[r.id]:.0%}"
    resume = {"gates": len(paires), "derive": round(derive, 4)}
    if nouveaux:
        return (
            "avec ta question, le prédicat d'une condition existante ne dirait plus ce que dit "
            "son texte (rejugement P1) :\n  " + "\n  ".join(nouveaux[:5]),
            resume,
        )
    if derive > derive_max:
        return (
            f"ta question change la façon dont une condition existante se lit (dérive "
            f"{derive:.2f}, {derive_max:.2f} au plus) : {ou}. Une reformulation change la "
            "tournure, pas ce que la réponse veut dire.",
            resume,
        )
    return None, resume


def proposer(
    atelier: Atelier,
    facts: Mapping[str, FactDef],
    fact_id: str,
    question: str,
    aide_contextuelle: str,
    justification: str,
    *,
    citations: list[Citation],
    aides: Mapping[str, Aide],
    detailles: set[str],
    inspectes: set[str],
    deja: Mapping[str, dict[str, Any]],
    seuils: Mapping[str, float],
    juge: Any = None,
    seuils_p1: tuple[float, float] | None = None,
    partage: Path | None = None,
) -> tuple[str, dict[str, Any] | None]:
    """(message rendu à l'agent, entrée écrite ou None). `aide_contextuelle` vide : `help` inchangé."""
    from catalogue import reformulations as rf

    fait = facts.get(fact_id)
    if fait is None:
        return _refus(
            f"« {fact_id} » n'est pas un fait de facts.yaml. Seul un fait approuvé se "
            "reformule ; un fait en attente que tu as proposé se retire (`retirer_fait`) et "
            "se repropose."
        )
    manquants = [
        nom
        for nom, faits_lus in (("detail_fait", detailles), ("conditions_du_fait", inspectes))
        if fact_id not in faits_lus
    ]
    if manquants:
        return _refus(
            f"appelle d'abord {' et '.join(f'`{n}`' for n in manquants)} sur `{fact_id}` : "
            "une reformulation se décide après avoir lu le fait ET chaque condition qui le cite."
        )
    if deja and fact_id not in deja:
        autre = next(iter(deja))
        return _refus(
            f"une seule reformulation par aide, et tu as déjà proposé celle de `{autre}`. "
            "Rappelle l'outil sur ce même fait pour la remplacer."
        )
    if fait.type not in TYPES_JUGES:
        return _refus(
            f"`{fact_id}` est de type {fait.type} : seules les questions à réponses "
            f"({', '.join(TYPES_JUGES)}) se reformulent, parce que leur sens se contrôle."
        )
    citations_max = int(seuils["citations_max"])
    if len(citations) > citations_max:
        return _refus(
            f"`{fact_id}` est cité {len(citations)} fois ({citations_max} au plus) : trop "
            "partagé pour qu'une ingestion en change la question. Si elle te semble fausse, "
            "dis-le dans la fiche de review : c'est à Félix."
        )
    question = _plat(question)
    aide = _plat(aide_contextuelle) or None
    if len(_plat(justification)) < MIN_CAR_JUSTIFICATION:
        return _refus(
            "justification trop courte : dis quel propriétaire, dans le cas de ta source, "
            "hésiterait ou répondrait mal avec la question actuelle, et pourquoi."
        )
    if question == _plat(fait.question) and (aide is None or aide == _plat(fait.help)):
        return _refus("ta proposition est identique à la question actuelle.")
    nouveau = fait.model_copy(update={"question": question, **({"help": aide} if aide else {})})
    if forme := _refus_de_forme(fact_id, nouveau):
        return _refus("la nouvelle question ne passe pas la forme d'un fait.\n" + forme)
    similarite = SequenceMatcher(None, normalize(fait.question), normalize(question)).ratio()
    if similarite < seuils["similarite_min"]:
        return _refus(
            f"ta question s'éloigne trop de l'actuelle (ressemblance {similarite:.2f}, "
            f"{seuils['similarite_min']:.2f} au moins). Une reformulation retouche la "
            "tournure ; une autre question est un autre fait."
        )
    try:
        en_attente = rf.lire(partage or rf.REFORMULATIONS).get(fact_id)
    except Exception:  # noqa: BLE001 — fichier partagé illisible : refus prudent
        return _refus("le fichier des reformulations en attente est illisible.")
    if en_attente is not None and en_attente.get("slug") != atelier.slug:
        return _refus(
            f"une reformulation de `{fact_id}` proposée par `{en_attente.get('slug')}` attend "
            "déjà Félix."
        )
    motif, p1 = _rejuger(
        fact_id,
        nouveau,
        facts,
        aides,
        derive_max=seuils["derive_max"],
        juge=juge,
        seuils_p1=seuils_p1,
    )
    if motif:
        return _refus(motif)
    entree: dict[str, Any] = {
        "fact": fact_id,
        "slug": atelier.slug,
        "jour": atelier.jour.isoformat(),
        "question_origine": _plat(fait.question),
        "help_origine": _plat(fait.help) or None,
        "question": question,
        "help": aide if aide is not None else (_plat(fait.help) or None),
        "justification": _plat(justification),
        "citations": len(citations),
        "extrait_citations": [c.ligne() for c in citations[:MAX_EXTRAIT]],
        "p1": p1,
    }
    try:
        rf.deposer(entree, atelier.reformulations_path, remplacer=True)
    except Exception as exc:  # noqa: BLE001 — l'écriture ratée est un refus, pas une panne du run
        return _refus(f"écriture de la proposition impossible ({exc}).")
    remplace = " Elle remplace ta proposition précédente." if fact_id in deja else ""
    return (
        f"Reformulation de `{fact_id}` proposée : elle deviendra une case pour Félix si ton "
        f"aide est acceptée ({p1.get('gates', 0)} gate(s) rejugée(s), dérive "
        f"{p1.get('derive', 0.0):.2f}).{remplace} Rien n'est réécrit avant sa réponse : ton "
        "aide reste typée sur la question actuelle. Mentionne-la dans la fiche de review.",
        entree,
    )


__all__ = ["proposer"]
