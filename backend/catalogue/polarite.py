"""Le sens des prédicats : ce que le texte d'une condition admet, contre ce que son prédicat admet.

Un prédicat inversé (`eq: true` au lieu de `eq: false`, une option oubliée dans
un `in`) écarte à tort tous les propriétaires qui répondent juste, sans un
bruit : ni le lint, ni le moteur, ni un test ne le voient, puisque le prédicat
est bien formé. C'est l'erreur la plus chère du catalogue.

Pour chaque gate `user_fact` sur un fait à réponses (booléen, choix, choix
multiple), Jev reçoit le texte de la condition, sa citation et la question du
fait, et une question fermée PAR RÉPONSE : « un demandeur qui répond X
remplit-il cette condition ? ». Le moteur dit, lui, ce que le prédicat fait de
cette réponse (`_normalize_answer` puis `evaluate_predicate`, comme au
diagnostic). Un désaccord a deux sens :

  - `ecarte_a_tort` : le prédicat écarte une réponse que le texte admet. Une
    aide perdue pour ces propriétaires ;
  - `laisse_passer` : le prédicat admet une réponse que le texte exclut. Une
    aide proposée à tort, que le dossier refusera.

Les réponses qui ne tranchent pas (valeur nulle, « je ne sais pas ») ne sont
pas jugées : le moteur n'en écarte personne.

Les jugements sont gardés comme ceux de la cohérence (empreinte des
questions, du modèle et de l'état), dans un fichier à part : un même état
n'est jamais rejugé.
"""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aides_schema import OPTIONS_BOOLEEN_IMPLICITES, Condition, FactDef, evaluate_predicate
from catalogue import coherence as co
from catalogue.journal import cle as cle_decision
from catalogue.journal import empreinte
from catalogue.openrouter import Panne, noul
from eligibility_engine import _normalize_answer

BACKEND = Path(__file__).resolve().parents[1]
JUGEMENTS = BACKEND / "data" / "catalogue" / "coherence" / "polarite.jsonl"
TAILLE_CITATION = 600
TAILLE_AIDE_FAIT = 300
PARALLELISME = 8

CONSIGNE = (
    "Le texte est une condition d'éligibilité d'une aide au patrimoine, et la question "
    "est celle que le questionnaire pose au demandeur pour la vérifier. D'après le seul "
    "texte de la condition (et sa citation), un demandeur qui donne la réponse « {label} » "
    "remplit-il cette condition ?"
)
VRAI = "Oui : avec cette réponse, la condition est remplie (le texte l'admet)."
FAUX = (
    "Non : avec cette réponse, la condition n'est pas remplie (le texte l'exclut, ou "
    "exige autre chose)."
)
#: Les règles de lecture d'un instructeur, jointes à chaque état. Ajoutées le
#: 2026-10-15 après le diagnostic de la relecture (`data/reviews/2026-10-14-polarite.md`) :
#: les erreurs de Jev tenaient au vocabulaire juridique des bénéficiaires et de
#: l'antériorité, jamais à une aide en particulier. Règles générales seulement :
#: une règle écrite pour un cas vu serait du surapprentissage.
REGLES = (
    "Règles de lecture, celles d'un instructeur du dossier. "
    "Une liste de bénéficiaires est limitative, sauf si le texte la dit indicative "
    "(« notamment », « principalement »). "
    "Les collectivités territoriales sont les communes, les départements et les régions ; "
    "« collectivités » ou « collectivités locales » les couvre toutes les trois. "
    "Une intercommunalité (EPCI), une métropole ou un syndicat mixte est un établissement "
    "public qui groupe des collectivités, pas une collectivité : il n'est admis que si le "
    "texte nomme les groupements, les EPCI, les intercommunalités, les structures "
    "intercommunales ou les établissements publics. "
    "Une commune, un département ou une région n'est pas un établissement public. L'État "
    "n'est ni une collectivité territoriale, ni un établissement public. "
    "Une SCI est une société civile : une personne morale de droit privé et une société, "
    "pas un particulier. "
    "Avancement des travaux : un projet sans travaux remplit une condition qui interdit "
    "seulement d'avoir commencé avant le dépôt. Des devis signés sans chantier commencé "
    "remplissent une condition qui interdit le commencement ou le démarrage des travaux, "
    "mais pas une condition qui interdit leur engagement, la signature de devis ou de "
    "marchés, ou le commencement d'exécution de l'opération."
)
#: L'empreinte de la forme des questions et des règles (le libellé de chaque réponse varie).
EMPREINTE_QUESTIONS = empreinte(
    json.dumps(
        {"consigne": CONSIGNE, "vrai": VRAI, "faux": FAUX, "regles": REGLES},
        ensure_ascii=False,
    )
)


@dataclass(frozen=True)
class Reponse:
    id: str
    label: str
    #: Ce que le prédicat fait de cette réponse : admise, écartée.
    admise: bool


@dataclass(frozen=True)
class Gate:
    slug: str
    nom: str
    condition: Condition
    fait: FactDef
    reponses: tuple[Reponse, ...]

    @property
    def ref(self) -> str:
        return f"{self.slug}#{self.condition.id}"


def options(fait: FactDef) -> list[Any]:
    if fait.type == "boolean":
        return list(fait.options or OPTIONS_BOOLEEN_IMPLICITES)
    return list(fait.options or [])


def gate_de(slug: str, nom: str, c: Condition, faits: dict[str, FactDef]) -> Gate | None:
    """La gate à juger, ou None : pas un gate `user_fact`, fait sans réponses, prédicat absent."""
    if c.kind != "user_fact" or c.effect != "gate" or not c.fact or c.predicate is None:
        return None
    fait = faits.get(c.fact)
    if fait is None or fait.type not in ("boolean", "enum", "multi_enum"):
        return None
    reponses = []
    for o in options(fait):
        valeur = _normalize_answer(fait, [o.id] if fait.type == "multi_enum" else o.id)
        if valeur is None:
            continue
        admise = evaluate_predicate(c.predicate.root, valeur)
        if admise is None:
            continue
        reponses.append(Reponse(o.id, o.label, bool(admise)))
    if len(reponses) < 2:
        return None
    return Gate(slug, nom, c, fait, tuple(reponses))


def etat(g: Gate) -> dict[str, Any]:
    sortie: dict[str, Any] = {
        "regles_de_lecture": REGLES,
        "aide": g.nom,
        "condition": " ".join(g.condition.text.split()),
        "question": " ".join(g.fait.question.split()),
    }
    if g.condition.quote:
        sortie["citation"] = " ".join(g.condition.quote.split())[:TAILLE_CITATION]
    if g.fait.help:
        sortie["aide_a_la_question"] = " ".join(g.fait.help.split())[:TAILLE_AIDE_FAIT]
    return sortie


def questions(g: Gate) -> dict[str, Any]:
    return {
        f"r{k}": noul(CONSIGNE.format(label=r.label), VRAI, FAUX) for k, r in enumerate(g.reponses)
    }


class Juge:
    """Jev sur une gate, toutes ses réponses en un appel, chaque jugement gardé une fois pour toutes."""

    def __init__(self, fichier: Path = JUGEMENTS, client: Any = None) -> None:
        self._base = co.Juge(fichier, client=client)
        self._verrou = threading.Lock()

    @property
    def cout_usd(self) -> float:
        return self._base.cout_usd

    @property
    def appels(self) -> int:
        return self._base.appels

    def juger(self, g: Gate) -> dict[str, float] | None:
        """La probabilité, réponse par réponse (id), que la condition soit remplie ; None en panne."""
        e, q = etat(g), questions(g)
        cle = cle_decision(EMPREINTE_QUESTIONS, self._base.modele.nom, {"etat": e, "q": q})
        if cle in self._base.connus:
            p = self._base.connus[cle]
        else:
            if self._base._client is None:
                with self._verrou:
                    if self._base._client is None:
                        from catalogue.openrouter import Client

                        self._base._client = Client()
            try:
                d = self._base._client.decider(
                    self._base.modele.nom,
                    e,
                    q,
                    acceptes=self._base.modele.acceptes,
                    delai_s=self._base.modele.delai_s,
                    role="polarite",
                )
            except Panne as exc:
                with self._verrou:
                    self._base.pannes[exc.classe] += 1
                return None
            p = {nom: round(avis.proba("true"), 4) for nom, avis in d.avis.items()}
            with self._verrou:
                self._base.appels += 1
                self._base.cout_usd += d.cout_usd or 0.0
                self._base.connus[cle] = p
                self._base._ajouter({"k": cle, "p": p})
        return {r.id: p[f"r{k}"] for k, r in enumerate(g.reponses) if f"r{k}" in p}

    def fermer(self) -> None:
        self._base.fermer()


@dataclass(frozen=True)
class Desaccord:
    reponse: Reponse
    p_remplie: float

    @property
    def sens(self) -> str:
        return "laisse_passer" if self.reponse.admise else "ecarte_a_tort"


def desaccords(g: Gate, probas: dict[str, float], haut: float, bas: float) -> list[Desaccord]:
    """Les réponses où le prédicat et Jev divergent nettement.

    Écartée par le prédicat, admise par Jev à `haut` ou plus ; admise par le
    prédicat, admise par Jev à `bas` ou moins.
    """
    sortie = []
    for r in g.reponses:
        p = probas.get(r.id)
        if p is None:
            continue
        if (not r.admise and p >= haut) or (r.admise and p <= bas):
            sortie.append(Desaccord(r, p))
    return sortie


# --------------------------------------------------------------------------
# Le contrôle de l'agent d'ingestion
# --------------------------------------------------------------------------

DECISION = "P1-polarite"
_JUGE: Juge | None = None


def _juge() -> Juge:
    global _JUGE
    if _JUGE is None:
        _JUGE = Juge()
    return _JUGE


def _seuils() -> tuple[float, float]:
    from catalogue import registre as registre_mod

    s = registre_mod.charger().decisions[DECISION].seuils
    return s["haut"], s["bas"]


def verifier(
    slug: str,
    texte_yaml: str,
    faits: dict[str, FactDef],
    *,
    juge: Juge | None = None,
    seuils: tuple[float, float] | None = None,
) -> tuple[list[str], list[str], str | None]:
    """(erreurs bloquantes, indications, note de panne) pour le `lint` de l'agent.

    Bloquant : le prédicat ÉCARTE une réponse que le texte admet selon Jev.
    Mesuré le 2026-10-14 (`data/reviews/2026-10-14-polarite.md`) : le prédicat
    avait tort 34 fois sur 40. Quand c'est Jev qui se trompe, l'agent élargit
    un prédicat juste, et l'erreur devient une aide proposée de trop : le sens
    bénin. Indication seulement : le prédicat ADMET une réponse que le texte
    exclut, juste une fois sur deux. Une panne n'impose rien.
    """
    from aides_schema import Aide, charger_yaml
    from catalogue import espace

    if juge is None and not espace.actif():
        return [], [], None
    try:
        aide = Aide.model_validate(charger_yaml(texte_yaml))
        juge = juge or _juge()
        haut, bas = seuils or _seuils()
        bloquants: list[str] = []
        indications: list[str] = []
        gates = [
            (c, g) for c in aide.conditions if (g := gate_de(slug, aide.nom, c, faits)) is not None
        ]
        # Un appel de Jev par gate, en parallèle : l'agent attend ce lint.
        with ThreadPoolExecutor(PARALLELISME) as pool:
            jugees = list(pool.map(juge.juger, [g for _c, g in gates]))
        for (c, g), probas in zip(gates, jugees, strict=True):
            if probas is None:
                continue
            for d in desaccords(g, probas, haut, bas):
                if d.sens == "ecarte_a_tort":
                    bloquants.append(
                        f"  ✗ {c.id} : ton prédicat `{json.dumps(c.predicate.root if c.predicate else None, ensure_ascii=False)}` "
                        f"écarte la réponse « {d.reponse.label} » (`{d.reponse.id}`), que le texte "
                        f"de la condition admet selon Jev ({d.p_remplie:.0%}). Relis la source : "
                        "ajoute cette réponse au prédicat, ou corrige le texte s'il ne dit pas "
                        "ce que dit la source."
                    )
                else:
                    indications.append(
                        f"  · {c.id} : ton prédicat admet « {d.reponse.label} » (`{d.reponse.id}`), "
                        f"que le texte semble exclure selon Jev ({1 - d.p_remplie:.0%}). À vérifier."
                    )
        return bloquants, indications, None
    except Exception as exc:  # noqa: BLE001 (le contrôle en panne ne bloque pas l'agent)
        return [], [], f"(contrôle du sens des prédicats indisponible : {type(exc).__name__})"
