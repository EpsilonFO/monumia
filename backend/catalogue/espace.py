"""L'espace des conditions et des faits : rattacher chaque nouveauté à sa famille.

(« Famille » s'entend ici d'une famille de TYPAGE ou de QUESTION, rien à voir
avec les `familles` d'une aide, l'axe de cadrage d'un projet.)

Une FAMILLE de condition, c'est le typage que portent ses voisines confirmées :
les conditions d'autres aides que l'embedding rapproche (rôle `plongement`) et
que Jev juge porter sur le même critère (décision `C1-coherence` du registre).
Une famille de FAIT, c'est le fait existant qui pose déjà la même question
(décision `F3-famille-fait`). Rien ici n'écrit dans une aide : le code ne
saurait pas écrire le prédicat (les valeurs viennent de la source). Avec
`typage_famille: aligner` (registre), c'est le `lint` de l'agent qui l'oblige
à retyper une condition comme sa famille, sauf quand la famille retirerait un
gate (`garde_son_gate`) ; avec `case`, l'écart part en case pour Félix.

Quatre usages, un seul espace :

1. L'agent d'ingestion : `voisines_pour` (outil `conditions_voisines`) lui
   montre comment le catalogue type déjà le critère qu'il lit,
   `alignements` rend bloquant au `lint` l'écart qu'il doit corriger, et
   `famille_du_fait` lui oppose le fait existant qui pose sa question.
2. Après une ingestion ou une ré-extraction acceptée : `controler_aide` ouvre
   une case `coherence:<id>` par écart resté (`a_signaler`).
3. Le run de la semaine (`python -m catalogue coherence`) : l'audit du stock,
   incrémental (seules les conditions neuves se plongent, seules les paires
   neuves se jugent), et les faits en attente rattachés à leur famille.
4. L'audit ponctuel complet reste `python -m catalogue.coherence`.

L'espace se GARDE : les vecteurs dans `plongements.CACHE`, hors du dépôt ; les
jugements de Jev dans `data/catalogue/coherence/jugements.jsonl`, suivi par
git. Un jugement n'est jamais refait sur une paire inchangée, si bien qu'un
écart ne clignote pas d'une semaine à l'autre.

Les écarts déjà arbitrés vivent dans `data/catalogue/coherence/ecarts-acceptes.yaml`
(l'arbitrage du 2026-10-14 et ses suites) et dans les réponses de Félix au
journal : ni l'un ni l'autre ne revient en case tant que le typage ne bouge pas.

`MONUMIA_ESPACE=0` coupe tout l'espace côté ingestion (la suite de tests le
fait) : l'outil de l'agent répond qu'il n'est pas disponible, la recherche de
faits redevient lexicale, le contrôle d'après ingestion se tait.

Panne d'embedding ou de Jev : rien n'est signalé, rien n'est bloqué. L'outil de
l'agent dit qu'il n'a pas pu répondre, le contrôle d'après ingestion se tait,
et l'étape de la semaine le note au rapport.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import threading
from collections import Counter
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from aides_schema import Aide, Condition, FactDef, charger_yaml
from catalogue import coherence as co
from catalogue import registre as registre_mod
from catalogue.cases import Case
from catalogue.journal import empreinte
from catalogue.openrouter import choix
from catalogue.plongements import (
    CONSIGNE_FAIT_VERS_FAIT,
    Plongeur,
    avec_consigne,
    plus_proches,
    texte_fait,
)

BACKEND = Path(__file__).resolve().parents[1]
DOSSIER = BACKEND / "data" / "catalogue" / "coherence"
ACCEPTES = DOSSIER / "ecarts-acceptes.yaml"

DECISION_CONDITIONS = "C1-coherence"
DECISION_FAITS = "F3-famille-fait"
#: Cases d'écart de typage ouvertes au plus par run, les plus graves d'abord :
#: au-delà, la fiche cesse d'être lue.
MAX_CASES = 15
MAX_CASES_FAITS = 10
#: Candidats de fait soumis à Jev : les dix plus proches dans l'espace. À cinq,
#: 11 des 70 doublons de la revue du 2026-09-17 n'étaient pas montrés ; à dix,
#: 7 (`data/reviews/2026-10-14-famille-fait.md`).
CANDIDATS_FAIT = 10
AUCUN = "aucun"


def questions_fait(n: int) -> dict[str, Any]:
    """La question de `F3-famille-fait` pour `n` candidats (son empreinte en dépend)."""
    return {
        "famille": choix(
            "Un fait est une question posée au propriétaire d'un monument pour vérifier "
            "son éligibilité à des aides. Parmi les candidats, lequel demande la MÊME "
            "information que le fait proposé, au point qu'un seul des deux devrait être "
            "posé ? Les seuils et les valeurs exigées appartiennent aux aides, pas aux "
            "faits : « budget de plus de 10 000 € » et « budget estimé du projet » sont la "
            "même information.",
            {
                **{
                    f"c{k}": f"Le candidat c{k} demande la même information que le fait proposé."
                    for k in range(1, n + 1)
                },
                AUCUN: "Aucun candidat ne demande la même information : le fait proposé est neuf.",
            },
        )
    }


QUESTIONS_FAIT: dict[str, Any] = questions_fait(CANDIDATS_FAIT)
EMPREINTE_QUESTIONS_FAIT = empreinte(json.dumps(QUESTIONS_FAIT, ensure_ascii=False, sort_keys=True))


# --------------------------------------------------------------------------
# Réglages (registre)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Reglages:
    meme: float = co.SEUIL_MEME
    cosinus: float = co.SEUIL_COSINUS
    voisins: int = co.VOISINS
    min_voisines: int = co.MIN_VOISINS
    part_dominante: float = co.PART_DOMINANTE
    choix_fait: float = 0.5
    typage_famille: str = "aligner"

    @classmethod
    def depuis(cls, reg: registre_mod.Registre | None = None) -> Reglages:
        reg = reg or registre_mod.charger()
        c = reg.decisions[DECISION_CONDITIONS].seuils
        f = reg.decisions[DECISION_FAITS].seuils
        return cls(
            meme=c["meme"],
            cosinus=c["cosinus"],
            voisins=int(c["voisins"]),
            min_voisines=int(c["min_voisines"]),
            part_dominante=c["part_dominante"],
            choix_fait=f["choix"],
            typage_famille=reg.reglages.typage_famille,
        )


# --------------------------------------------------------------------------
# L'espace des conditions
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Voisine:
    ligne: co.Ligne
    cosinus: float
    #: Probabilité « même critère » selon Jev ; None si Jev n'a pas pu juger.
    meme: float | None


@dataclass
class Famille:
    """Ce que le catalogue dit d'une condition : ses voisines et le typage qui domine."""

    voisines: list[Voisine]
    dominante: co.Dominante | None
    reglages: Reglages

    @property
    def confirmees(self) -> list[Voisine]:
        return [v for v in self.voisines if v.meme is not None and v.meme >= self.reglages.meme]

    @property
    def jugee(self) -> bool:
        return all(v.meme is not None for v in self.voisines)


class Espace:
    """Le catalogue en service, plongé : conditions, vecteurs, et le juge qui les rapproche.

    Construit à la première question et gardé pour le processus : un run ou un
    agent interroge plusieurs fois le même catalogue.
    """

    def __init__(
        self,
        lignes: list[co.Ligne] | None = None,
        *,
        plongeur: Plongeur | None = None,
        juge: co.Juge | None = None,
        reglages: Reglages | None = None,
    ) -> None:
        self._lignes = lignes
        self.plongeur = plongeur or Plongeur()
        self.juge = juge or co.Juge()
        self.reglages = reglages or Reglages.depuis()
        self._vecteurs: np.ndarray | None = None
        self._verrou = threading.Lock()

    @property
    def lignes(self) -> list[co.Ligne]:
        with self._verrou:
            if self._lignes is None:
                self._lignes = co.charger()
            return self._lignes

    @property
    def vecteurs(self) -> np.ndarray:
        lignes = self.lignes
        with self._verrou:
            if self._vecteurs is None:
                self._vecteurs = self.plongeur.vecteurs([ln.texte for ln in lignes])
            return self._vecteurs

    def candidates(self, ligne: co.Ligne) -> list[tuple[co.Ligne, float]]:
        """Les conditions d'AUTRES aides les plus proches dans l'espace, au-dessus du cosinus."""
        requete = self.plongeur.vecteurs([ligne.texte])
        k = self.reglages.voisins + 30  # marge : les conditions de la même aide sont écartées
        rangs, scores = plus_proches(requete, self.vecteurs, k)
        sortie = []
        for j, s in zip(rangs[0], scores[0], strict=True):
            autre = self.lignes[int(j)]
            if autre.slug == ligne.slug or s < self.reglages.cosinus:
                continue
            sortie.append((autre, round(float(s), 4)))
            if len(sortie) == self.reglages.voisins:
                break
        return sortie

    def famille(self, ligne: co.Ligne) -> Famille:
        """Les voisines jugées par Jev, et le typage dominant des confirmées."""
        candidates = self.candidates(ligne)

        def juger(autre: co.Ligne) -> float | None:
            a, b = co.paire(ligne, autre)
            d = self.juge.juger(co._etat(a, b))
            return None if d is None else d.get(co.MEME, 0.0)

        with ThreadPoolExecutor(co.PARALLELISME_JEV) as pool:
            probas = list(pool.map(juger, [c for c, _s in candidates]))
        voisines = [Voisine(c, s, p) for (c, s), p in zip(candidates, probas, strict=True)]
        confirmees = [
            (v.ligne, float(v.meme))
            for v in voisines
            if v.meme is not None and v.meme >= self.reglages.meme
        ]
        d = co.dominante(
            ligne,
            confirmees,
            self.reglages.min_voisines,
            self.reglages.part_dominante,
        )
        return Famille(voisines, d, self.reglages)

    def fermer(self) -> None:
        self.plongeur.fermer()
        self.juge.fermer()


_INSTANCE: Espace | None = None
_VERROU_INSTANCE = threading.Lock()


def actif() -> bool:
    """L'espace sert-il côté ingestion ? `MONUMIA_ESPACE=0` le coupe (tests, panne)."""
    return os.environ.get("MONUMIA_ESPACE", "1") != "0"


def instance() -> Espace:
    """L'espace du processus, construit une fois."""
    global _INSTANCE
    with _VERROU_INSTANCE:
        if _INSTANCE is None:
            _INSTANCE = Espace()
        return _INSTANCE


# --------------------------------------------------------------------------
# 1. L'outil de l'agent
# --------------------------------------------------------------------------


def _ligne_libre(texte: str, slug: str, nom: str) -> co.Ligne:
    """Une condition en cours d'écriture, que l'espace ne connaît pas encore."""
    condition = Condition.model_validate({"id": "en-cours", "text": texte, "kind": "info"})
    return co.Ligne(slug, nom, condition, rang=10_000)


def _predicat_txt(c: Condition) -> str:
    return json.dumps(c.predicate.root, ensure_ascii=False) if c.predicate else ""


def voisines_pour(texte: str, slug: str, nom: str, esp: Espace | None = None) -> str:
    """La réponse de l'outil `conditions_voisines` : la famille du critère, et ses membres."""
    if esp is None and not actif():
        return "Espace désactivé (MONUMIA_ESPACE=0) : type la condition selon TYPING.md."
    esp = esp or instance()
    try:
        f = esp.famille(_ligne_libre(texte, slug, nom))
    except Exception as exc:  # noqa: BLE001 — l'outil répond, il ne casse pas l'agent
        return f"Espace indisponible ({type(exc).__name__}) : type la condition selon TYPING.md."
    if not f.voisines:
        return (
            "Aucune condition du catalogue ne pose ce critère (aucune voisine proche) : "
            "type-la selon TYPING.md."
        )
    lignes: list[str] = []
    if f.dominante is not None:
        d = f.dominante
        pred = (
            f", prédicat le plus fréquent `{json.dumps(d.predicat, ensure_ascii=False)}` "
            f"({d.part_predicat:.0%} des porteuses)"
            if d.predicat
            else ""
        )
        lignes += [
            f"FAMILLE : `{co.libelle(d.attendu)}` ({d.part:.0%} des voisines confirmées{pred}).",
            "Type ta condition comme sa famille : le `lint` l'imposera. Seule exception, un "
            "gate que la famille n'a pas : si ta source pose une exigence vérifiable que la "
            "famille laisse en `info`, garde ton gate.",
            "",
        ]
    elif f.confirmees:
        lignes += [
            "Pas de famille nette : les voisines confirmées sont typées de plusieurs façons. "
            "Type selon TYPING.md, en t'inspirant des voisines ci-dessous.",
            "",
        ]
    else:
        lignes += [
            "Aucune voisine n'est confirmée par Jev comme posant le même critère : type selon "
            "TYPING.md. Voisines par le vocabulaire seulement :",
            "",
        ]
    montrees = f.confirmees or f.voisines[:3]
    for v in montrees[:8]:
        c = v.ligne.condition
        juge = f"Jev {v.meme:.2f}" if v.meme is not None else "non jugée"
        lignes.append(
            f"- `{co.libelle(v.ligne.typage)}` {_predicat_txt(c)} · {v.ligne.ref} ({juge}) : "
            f"« {v.ligne.texte[:200]} »"
        )
    if not f.jugee:
        lignes.append("(Jev n'a pas pu juger toutes les voisines : réponse partielle.)")
    return "\n".join(lignes)


# --------------------------------------------------------------------------
# 2. Le contrôle d'après ingestion
# --------------------------------------------------------------------------


def _etat_ecart(ligne: co.Ligne, attendu: co.Typage) -> str:
    return empreinte(f"{ligne.ref}|{co.libelle(ligne.typage)}|{co.libelle(attendu)}")


def case_ecart(ligne: co.Ligne, f: Famille) -> Case:
    assert f.dominante is not None
    d = f.dominante
    exemples = [
        f"- voisine `{co.libelle(v.ligne.typage)}` {v.ligne.ref} : « {v.ligne.texte[:180]} »"
        for v in f.confirmees
        if v.ligne.typage == d.attendu
    ][:3]
    pred = (
        f" Prédicat le plus fréquent de la famille : `{json.dumps(d.predicat, ensure_ascii=False)}`."
        if d.predicat
        else ""
    )
    return Case(
        f"coherence:{ligne.condition.id}",
        f"a:{ligne.slug}",
        f"`{co.libelle(ligne.typage)}`, sa famille dit `{co.libelle(d.attendu)}`",
        _etat_ecart(ligne, d.attendu),
        {
            "garder": "écart voulu, ne plus le signaler",
            "vu": "je retype la condition à la main",
        },
        (
            f"Condition `{ligne.condition.id}` : « {ligne.texte[:300]} »",
            f"{len(f.confirmees)} voisine(s) confirmée(s) par Jev, {d.part:.0%} typées "
            f"`{co.libelle(d.attendu)}`.{pred}",
            *exemples,
        ),
    )


def ecart(ligne: co.Ligne, f: Famille) -> bool:
    return f.dominante is not None and not co.concorde(ligne, f.dominante.attendu)


def garde_son_gate(ligne: co.Ligne, attendu: co.Typage) -> bool:
    """La famille retirerait un gate que la condition pose : la condition garde le sien.

    Mesuré le 2026-10-14 sur les désaccords que Félix a arbitrés
    (`data/reviews/2026-10-14-heritage-typage.md`) : quand la famille AJOUTE un
    gate, elle avait raison 48 fois contre 5 ; quand elle en RETIRE un, l'agent
    avait raison 17 fois contre 4. Une famille en `info` dit souvent que les
    autres aides ont oublié l'exigence, pas qu'elle n'existe pas.
    """
    return co.pese(ligne.typage) and not co.pese(attendu)


def a_aligner(ligne: co.Ligne, f: Famille) -> bool:
    """L'écart que le `lint` de l'agent refuse (réglage `typage_famille: aligner`)."""
    return (
        ecart(ligne, f)
        and f.dominante is not None
        and not garde_son_gate(ligne, f.dominante.attendu)
    )


def a_signaler(ligne: co.Ligne, f: Famille) -> bool:
    """L'écart qui devient une case : tous en mode `case`, les seuls à aligner sinon."""
    if f.reglages.typage_famille == "case":
        return ecart(ligne, f)
    return a_aligner(ligne, f)


def message_alignement(ligne: co.Ligne, f: Famille) -> str:
    """L'erreur de `lint` qui oblige l'agent à retyper la condition comme sa famille."""
    assert f.dominante is not None
    d = f.dominante
    porteuses = [v for v in f.confirmees if v.ligne.typage == d.attendu]
    pred = (
        f" Prédicat le plus fréquent chez elles : `{json.dumps(d.predicat, ensure_ascii=False)}`"
        " (les valeurs viennent de TA source : seuil, liste, territoire)."
        if d.predicat
        else ""
    )
    lignes = [
        f"  ✗ {ligne.condition.id} : typée `{co.libelle(ligne.typage)}`, mais "
        f"{len(f.confirmees)} conditions d'autres aides qui posent le même critère sont "
        f"typées `{co.libelle(d.attendu)}` ({d.part:.0%}). Retype-la en "
        f"`{co.libelle(d.attendu)}`.{pred}",
    ]
    for v in porteuses[:2]:
        lignes.append(
            f"      ex. {v.ligne.ref} {_predicat_txt(v.ligne.condition)} : « {v.ligne.texte[:160]} »"
        )
    return "\n".join(lignes)


def alignements(
    slug: str, texte_yaml: str, *, esp: Espace | None = None
) -> tuple[list[str], str | None]:
    """Les erreurs de typage que le `lint` de l'agent rend bloquantes, et une note de panne.

    Vide en mode `typage_famille: case` : l'écart part alors en case après
    l'ingestion. Une panne n'impose rien : l'agent finit, et le contrôle
    d'après ingestion rattrape ce qu'il peut.
    """
    if esp is None and not actif():
        return [], None
    try:
        aide = Aide.model_validate(charger_yaml(texte_yaml))
        esp = esp or instance()
        if esp.reglages.typage_famille != "aligner":
            return [], None
        erreurs = []
        for ligne in co.lignes_de(slug, aide):
            f = esp.famille(ligne)
            if a_aligner(ligne, f):
                erreurs.append(message_alignement(ligne, f))
        return erreurs, None
    except Exception as exc:  # noqa: BLE001 (le contrôle en panne ne bloque pas l'agent)
        return [], f"(contrôle de famille indisponible : {type(exc).__name__}, rien n'est imposé)"


def controler_aide(
    slug: str,
    texte_yaml: str,
    *,
    seulement: Iterable[str] | None = None,
    esp: Espace | None = None,
) -> tuple[list[Case], str | None]:
    """Les cases d'écart d'une aide qui vient d'être écrite, et une note en cas de panne.

    `seulement` borne le contrôle aux conditions neuves d'une ré-extraction :
    celles qu'elle garde à l'octet ont déjà été contrôlées.
    """
    if esp is None and not actif():
        return [], None
    try:
        aide = Aide.model_validate(charger_yaml(texte_yaml))
        esp = esp or instance()
        visees = set(seulement) if seulement is not None else None
        cases = []
        for ligne in co.lignes_de(slug, aide):
            if visees is not None and ligne.condition.id not in visees:
                continue
            f = esp.famille(ligne)
            if a_signaler(ligne, f):
                cases.append(case_ecart(ligne, f))
        return cases, None
    except Exception as exc:  # noqa: BLE001 — un contrôle en panne ne refuse pas l'aide
        return [], f"contrôle de cohérence en panne pour `{slug}` ({type(exc).__name__})"


def ligne_mesures(mesures: Iterable[dict[str, int]]) -> str | None:
    """La ligne du rapport qui dit ce que les agents ont fait des signaux de l'espace.

    Elle transforme en chiffres ce que les mesures du 2026-10-14 n'ont pas pu
    observer : l'agent réutilise-t-il le fait que Jev lui désigne, et corrige-t-il
    le typage que le lint lui refuse ?
    """
    total: Counter[str] = Counter()
    for m in mesures:
        total.update(m)
    if not total:
        return None
    return (
        f"- Espace : {total['conditions']} condition(s), `conditions_voisines` appelé "
        f"{total['appels_conditions_voisines']} fois ; {total['alignements_leves']} écart(s) "
        f"de typage levé(s) au lint, {total['alignements_restants']} resté(s) ; "
        f"{total['polarites_levees']} prédicat(s) refusé(s) au lint, "
        f"{total['polarites_restantes']} resté(s) ; "
        f"{total['alertes_faits']} alerte(s) de fait : {total['alertes_reutilisees']} "
        f"réutilisée(s), {total['alertes_maintenues']} fait(s) maintenu(s), "
        f"{total['alertes_abandonnees']} abandonnée(s) ; {total['faits_neufs']} fait(s) neuf(s)."
    )


# --------------------------------------------------------------------------
# 3. La famille d'un fait
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FamilleFait:
    cle: str
    proba: float
    candidats: list[str]


def _decrire_fait(cle: str, fait: FactDef) -> dict[str, Any]:
    sortie: dict[str, Any] = {"cle": cle, "question": " ".join(fait.question.split())}
    if fait.help:
        sortie["aide"] = " ".join(fait.help.split())[:400]
    if fait.options:
        sortie["reponses"] = [o.label for o in fait.options]
    return sortie


def famille_du_fait(
    cle: str,
    fait: FactDef,
    ontologie: dict[str, FactDef],
    *,
    plongeur: Plongeur | None = None,
    juge: co.Juge | None = None,
    reglages: Reglages | None = None,
) -> FamilleFait | None:
    """Le fait existant qui pose déjà la même question, s'il y en a un selon Jev.

    Les candidats sont les plus proches dans l'espace (consigne fait vers
    fait) ; Jev choisit parmi eux ou répond « aucun ». Lève sur une panne
    d'embedding ; une panne de Jev rend None.
    """
    plongeur = plongeur or instance().plongeur
    juge = juge or instance().juge
    reglages = reglages or Reglages.depuis()
    autres = [k for k in ontologie if k != cle]
    if not autres:
        return None
    corpus = plongeur.vecteurs([texte_fait(k, ontologie[k]) for k in autres])
    requete = plongeur.vecteurs([avec_consigne(CONSIGNE_FAIT_VERS_FAIT, texte_fait(cle, fait))])
    rangs, _ = plus_proches(requete, corpus, CANDIDATS_FAIT)
    candidats = [autres[int(j)] for j in rangs[0]]
    etat = {
        "fait_propose": _decrire_fait(cle, fait),
        "candidats": {f"c{n}": _decrire_fait(k, ontologie[k]) for n, k in enumerate(candidats, 1)},
    }
    d = juge.juger(etat, QUESTIONS_FAIT, "famille")
    if d is None:
        return None
    choisi, p = max(d.items(), key=lambda kv: kv[1])
    if choisi == AUCUN or p < reglages.choix_fait or not choisi.startswith("c"):
        return None
    rang = int(choisi[1:]) - 1
    if rang >= len(candidats):
        return None
    return FamilleFait(candidats[rang], round(p, 3), candidats)


# --------------------------------------------------------------------------
# 4. L'étape de la semaine
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Accepte:
    ref: str
    actuel: str
    attendu: str


def lire_acceptes(chemin: Path = ACCEPTES) -> set[Accepte]:
    if not chemin.exists():
        return set()
    brut = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    return {Accepte(e["ref"], e["actuel"], e["attendu"]) for e in brut.get("acceptes") or []}


@dataclass
class Bilan:
    cases: list[Case] = field(default_factory=list)
    lignes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def stock(
    esp: Espace,
    acceptes: set[Accepte],
    repondu: Any,
    *,
    max_cases: int = MAX_CASES,
) -> Bilan:
    """Les écarts de tout le catalogue, hors écarts acceptés et déjà répondus."""
    b = Bilan()
    lignes = esp.lignes
    paires = co.paires_candidates(lignes, esp.plongeur, esp.reglages.cosinus, esp.reglages.voisins)
    avant = esp.juge.appels
    jugements = co.juger_paires(lignes, paires, esp.juge)
    voisins = co.voisinage(len(lignes), jugements, esp.reglages.meme)
    signalements = co.signaler(
        lignes, voisins, esp.reglages.min_voisines, esp.reglages.part_dominante
    )
    ouverts = []
    for s in signalements:
        ligne = lignes[s.indice]
        if Accepte(ligne.ref, co.libelle(ligne.typage), co.libelle(s.attendu)) in acceptes:
            continue
        if esp.reglages.typage_famille == "aligner" and garde_son_gate(ligne, s.attendu):
            continue
        sorte, objet = f"coherence:{ligne.condition.id}", f"a:{ligne.slug}"
        if repondu(sorte, objet, _etat_ecart(ligne, s.attendu)):
            continue
        ouverts.append((s, ligne))
    ouverts.sort(
        key=lambda x: (
            co.ORDRE_IMPACT.index(co.impact(Counter([x[1].typage, x[0].attendu]))),
            x[1].ref,
        )
    )
    for s, ligne in ouverts[:max_cases]:
        autour = voisins[s.indice]
        f = Famille(
            [
                Voisine(lignes[j], paires.get((min(s.indice, j), max(s.indice, j)), 0.0), p)
                for j, p in sorted(autour.items(), key=lambda x: -x[1])
            ],
            co.Dominante(s.attendu, s.part, [], s.predicat, s.part_predicat),
            esp.reglages,
        )
        b.cases.append(case_ecart(ligne, f))
    b.lignes += [
        f"{len(lignes)} conditions, {len(paires)} paires candidates, "
        f"{esp.juge.appels - avant} paire(s) jugée(s) cette semaine.",
        f"{len(signalements)} écart(s) au voisinage, {len(ouverts)} hors écarts acceptés et "
        f"réponses ; {min(len(ouverts), max_cases)} en case.",
    ]
    if len(ouverts) > max_cases:
        b.notes.append(f"- {len(ouverts) - max_cases} écart(s) de typage attendent le run suivant.")
    if esp.juge.pannes:
        b.notes.append(f"- Jev en panne sur certaines paires : {dict(esp.juge.pannes)}.")
    return b


def faits_en_attente(
    pending: dict[str, FactDef],
    facts: dict[str, FactDef],
    repondu: Any,
    esp: Espace,
    *,
    max_cases: int = MAX_CASES_FAITS,
) -> Bilan:
    """Les faits proposés que Jev rattache à un fait existant : une case par rapprochement.

    En `faits_neufs: auto`, aucune case : l'agent a déjà relu le fait que Jev
    désignait avant de proposer le sien, et Jev seul rattache à tort plus d'un
    fait sur deux qu'il désigne (`data/reviews/2026-10-14-famille-fait.md`).
    Le rapport garde le compte.
    """
    from catalogue.registre import faits_neufs_en_case

    en_case = faits_neufs_en_case()
    b = Bilan()
    ontologie = {**facts, **pending}
    trouves = 0
    for cle, fait in sorted(pending.items()):
        f = famille_du_fait(
            cle, fait, ontologie, plongeur=esp.plongeur, juge=esp.juge, reglages=esp.reglages
        )
        if f is None:
            continue
        trouves += 1
        sorte, objet, etat = "famille-fait", f"f:{cle}", empreinte(f"{cle}|{f.cle}")
        if not en_case or repondu(sorte, objet, etat) or len(b.cases) >= max_cases:
            continue
        autre = ontologie[f.cle]
        b.cases.append(
            Case(
                sorte,
                objet,
                f"`{cle}` pose la même question que `{f.cle}`",
                etat,
                {
                    "fusionner": f"fusionner dans `{f.cle}` (à la main, `fusionner_faits.py`)",
                    "garder": "deux questions différentes, garder les deux",
                },
                (
                    f"`{cle}` : « {' '.join(fait.question.split())} »",
                    f"`{f.cle}` : « {' '.join(autre.question.split())} »",
                    f"Jev : {f.proba:.2f} (candidats : {', '.join(f.candidats)}).",
                ),
            )
        )
    b.lignes.append(f"{len(pending)} fait(s) en attente, {trouves} rattaché(s) à un fait existant.")
    return b


def commande(journal: Path, parties: Path | None, *, plafond: float | None = None) -> int:
    """`python -m catalogue coherence` : l'étape de la semaine."""
    import secrets

    from aides_schema import load_facts, load_pending_facts
    from catalogue import cases as cases_mod
    from catalogue.journal import Journal, Vue
    from catalogue.rapport import Rapport, Section, parties_json

    reg = registre_mod.charger()
    if reg.decisions[DECISION_CONDITIONS].statut != "en_service":
        print(f"{DECISION_CONDITIONS} n'est pas en service au registre : rien à faire.")
        return 0
    jour = dt.date.today()
    run = f"{jour.isoformat()}-coherence-{secrets.token_hex(2)}"
    j = Journal(journal)
    vue = Vue(list(j.lire()))
    reponses, _ = cases_mod.relire((BACKEND / "data" / "reviews").glob("*-semaine*.md"), vue, run)
    if reponses:
        j.ajouter_lot(reponses)
    for e in reponses:
        vue.prendre(e)

    def repondu(sorte: str, objet: str, etat: str) -> bool:
        return cases_mod.reponse(vue, sorte, objet, etat) is not None

    esp = Espace(reglages=Reglages.depuis(reg))
    bilans: list[Bilan] = []
    try:
        bilans.append(stock(esp, lire_acceptes(), repondu))
        if plafond is None or esp.juge.cout_usd + esp.plongeur.cout_usd < plafond:
            bilans.append(faits_en_attente(load_pending_facts(), load_facts(), repondu, esp))
    finally:
        esp.fermer()
    depense = esp.juge.cout_usd + esp.plongeur.cout_usd
    cases = [c for b in bilans for c in b.cases]
    lignes = [ln for b in bilans for ln in b.lignes] + [n for b in bilans for n in b.notes]
    entete = [f"- Cohérence du typage : {len(cases)} case(s), {depense:.4f} $."]
    sections = [Section("Cohérence du typage", lignes)]
    if parties is not None:
        parties.write_text(parties_json(entete, cases, sections, depense=depense), encoding="utf-8")
    else:
        r = Rapport(jour, run)
        r.entete, r.cases, r.sections = entete, cases, sections
        print(f"rapport : {r.ecrire(BACKEND / 'data' / 'reviews')}")
    return 0
