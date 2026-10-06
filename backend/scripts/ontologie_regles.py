"""Les règles de forme d'un fait, au seul endroit où tout le monde peut les lire.

Trois chemins en ont besoin et ils ne peuvent pas s'importer l'un l'autre :

  - `ingestion/faits.py::proposer` REFUSE à l'écriture (le fait n'existe pas
    encore, l'agent peut corriger et reproposer) ;
  - `lint_aides_data.py` AVERTIT sur l'existant (25 booléens à seuil dans la
    clé et 97 questions longues sont déjà dans `facts_pending.yaml`, plus 19
    et 60 dans `facts.yaml` : les passer en erreur rendrait le lint rouge sur
    un lot qu'on n'a pas fini de corriger) ;
  - `ingestion/ontologie.py` AUDITE en fin de run.

Faire vivre ces règles dans `ingestion/faits.py` fermerait le cycle
`lint_aides_data → ingestion.faits → lint_aides_data` (le module d'ingestion
importe déjà `faits_references_dans` du lint). D'où ce module, qui ne dépend que
de `veille_text.normalize` — aucun schéma, aucun chargement de catalogue.

Les deux plafonds de longueur diffèrent volontairement : 250 caractères à
l'écriture, 300 au lint. La marge n'est pas de la mollesse, c'est ce qui
permet de durcir la porte d'entrée sans rendre rouge d'un coup le stock déjà
écrit ; elle se referme quand le stock est résorbé.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Protocol

sys.path.insert(0, str(Path(__file__).resolve().parent))

from veille_text import normalize

#: Une phrase. Le détail (les exceptions, la liste du règlement) va dans `help`,
#: que le front affiche en aide contextuelle plutôt qu'en libellé de question.
MAX_CAR_QUESTION = 250
#: Le même plafond, desserré pour l'avertissement du lint sur le stock existant.
MAX_CAR_QUESTION_LINT = 300

#: La CIBLE d'écriture d'une question, posée le 2026-10-06 (cf. l'en-tête de
#: `facts.yaml`) : une phrase d'environ 160 caractères, sans énumération. Le
#: lint avertit au-delà, sur toute l'ontologie ; `tests/test_forme_des_faits.py`
#: fige le nombre de questions de plus de 200 caractères pour qu'il ne remonte
#: pas.
MAX_CAR_QUESTION_CIBLE = 160

#: Le titre d'une carte de réponse. Au-delà, la carte devient un paragraphe :
#: les parenthèses, exemples et énumérations vont dans `description`.
MAX_CAR_LIBELLE_OPTION = 45
#: Au-delà, les cartes se rangent sous des intertitres (`groupe`).
MAX_OPTIONS_SANS_GROUPE = 8

#: Un seuil chiffré enfermé dans le libellé d'un booléen : `logement_plus_15_ans`,
#: `age_porteur_moins_62_ans`, « au moins 3 ans », « supérieur à 50 % ».
#:
#: Le seuil appartient au PRÉDICAT de l'aide, pas au fait : deux règlements qui
#: exigent 15 et 20 ans posent alors une seule question (« quel âge a le
#: bâtiment ? ») au lieu de deux booléens qu'aucun moteur ne sait rapprocher.
#:
#: Le motif est volontairement étroit — il exige un COMPARATEUR à côté du
#: nombre. « Le bâtiment date-t-il d'avant 1948 ? » ou « bénéficiez-vous de la
#: loi 1901 ? » ne portent pas de seuil comparatif et ne doivent pas être
#: refusés pour un millésime.
SEUIL_CHIFFRE_RE = re.compile(
    r"""
    (?:^|[\s_(«"'])                                   # frontière gauche
    (?:
        # « plus_15 », « moins de 62 », « au moins 3 », « supérieur à 50 »
        (?: plus | moins | mini? | maxi? | sup | inf
          | superieur\w* | inferieur\w* | minimum | maximum
          | au[\s_]moins | au[\s_]plus | a[\s_]partir[\s_]de
          | depuis | pendant | depassant | excedant )
        (?:[\s_](?:de|d|a|que|au|aux))? [\s_] \d+
      | # « 15_ans », « 30h », « 50 % », « 51pct »
        \d+ [\s_]? (?: ans? | mois | semaines? | jours? | h | heures?
                      | % | pct | pourcent | m2 | ha | ugb )
        (?: $ | [\s_.,;:?)»] )
    )
    """,
    re.VERBOSE,
)

#: Les deux seuls négateurs retenus, et c'est une décision de PRÉCISION. Y
#: ajouter « hors », « pas », « exclu » fait passer les suspects de 12 à 34 sur
#: le corpus réel, pour un seul vrai cas de plus : le français place un nom entre
#: le négateur et ce qu'il nie (« hors des catégories exclues »), et l'adjacence
#: de jetons ne sait pas le suivre. Un rapport à 90 % de bruit n'est pas lu, donc
#: ne rattrape rien.
NEGATEURS = frozenset({"non", "sans"})
#: En dessous, un préfixe commun ne prouve aucune parenté de sens.
RACINE_MIN = 5


class FaitLisible(Protocol):
    """Le strict minimum qu'une règle de forme lit d'un fait.

    Un `Protocol` plutôt qu'un import de `FactDef` : ce module doit rester
    importable par le lint sans traîner le schéma Pydantic derrière lui, et les
    tests passent des objets factices.
    """

    question: str
    type: str


def seuil_dans_la_cle(fact_id: str) -> str | None:
    """Le fragment de la CLÉ qui trahit un seuil, ou `None`.

    Renvoie le texte trouvé plutôt qu'un booléen : le message doit pouvoir citer
    ce sur quoi il bute, sinon l'agent reformule au hasard.

    La clé seule est le signal PROPRE, et c'est celui que le lint regarde : sur
    le corpus, elle désigne 25 faits proposés et 19 canoniques, tous de vrais
    seuils enfermés (`logement_plus_15_ans`, `batiment_plus_50_ans`,
    `s_engage_maintien_plantation_7_ans`).
    """
    trouve = SEUIL_CHIFFRE_RE.search(fact_id.lower())
    return trouve.group(0).strip() if trouve else None


def seuil_chiffre(fact_id: str, question: str) -> str | None:
    """Le seuil trahi par la clé OU par la question. Le filet de la porte d'entrée.

    La question est bien plus bruyante que la clé — « moins de 250 employés »
    dans la définition européenne de la PME, « 19 équipements » dans celle d'une
    commune de centralité. On l'accepte ici et nulle part ailleurs : à
    l'écriture, le refus ORIENTE (l'agent reformule, prend un integer, ou type
    la condition `manual_check` + `info`), alors qu'un avertissement de lint sur
    ce bruit ne serait plus lu.

    Une question qui déborde est refusée AVANT d'arriver ici
    (`question_trop_longue`) : les listes d'exclusions d'un règlement, qui sont
    la grande pourvoyeuse de faux positifs, ne passent donc jamais par ce test.
    """
    return seuil_dans_la_cle(fact_id) or (
        trouve.group(0).strip()
        if (trouve := SEUIL_CHIFFRE_RE.search(normalize(question)))
        else None
    )


def booleen_a_seuil(fact_id: str, fait: FaitLisible) -> str | None:
    """Le seuil enfermé dans la CLÉ d'un booléen. Un integer a le droit d'en porter un.

    C'est la forme que lit le lint : voir `seuil_chiffre` pour celle, plus
    large, qu'oppose la porte d'entrée.
    """
    if fait.type != "boolean":
        return None
    return seuil_dans_la_cle(fact_id)


def question_trop_longue(fait: FaitLisible, *, maximum: int = MAX_CAR_QUESTION) -> int | None:
    """La longueur de la question si elle dépasse, `None` sinon.

    Mesurée sur la question REPLIÉE : un scalaire YAML sur cinq lignes et la
    même phrase sur une ligne doivent compter pareil.
    """
    longueur = len(" ".join(fait.question.split()))
    return longueur if longueur > maximum else None


class OptionLisible(Protocol):
    id: str
    label: str
    groupe: str | None


def libelles_trop_longs(
    options: list[OptionLisible] | None, *, maximum: int = MAX_CAR_LIBELLE_OPTION
) -> list[str]:
    """Les ids des options dont le libellé (replié) dépasse `maximum`."""
    return [o.id for o in options or [] if len(" ".join(o.label.split())) > maximum]


def options_a_grouper(options: list[OptionLisible] | None) -> bool:
    """Plus de `MAX_OPTIONS_SANS_GROUPE` options, et aucune ne porte de groupe."""
    opts = options or []
    return len(opts) > MAX_OPTIONS_SANS_GROUPE and not any(o.groupe for o in opts)


def _nie(jetons: list[str], i: int) -> bool:
    """Le jeton `i` est-il directement précédé d'un négateur ?"""
    return i > 0 and jetons[i - 1] in NEGATEURS


def _jetons_question(question: str) -> list[str]:
    """La question en jetons nus : la ponctuation collée masquerait la racine."""
    return [j.strip("().,;:?!«»\"'") for j in normalize(question).replace("'", " ").split()]


def polarites_suspectes(pending: dict[str, FaitLisible]) -> list[str]:
    """Les faits dont la clé AFFIRME ce que la question NIE, ou l'inverse.

    `demande_eligible_france_agrimer`, dont la question demande précisément
    l'INÉLIGIBILITÉ, est le cas type — et il est plus grave qu'un doublon :
    chaque prédicat qui cite ce fait dit alors le contraire de ce que son auteur
    a lu dans la source. Un doublon coûte une question de trop ; celui-ci fausse
    un verdict d'éligibilité, et ni le lint ni le moteur ne peuvent le voir.

    On cherche une RACINE commune à la clé et à la question, puis on compare la
    polarité de ses deux occurrences : `sans cartographie` dans la clé contre
    « dispose-t-elle d'une cartographie » dans la question. Comparer les deux
    polarités globalement ne dirait rien — presque toute question de règlement
    contient une négation quelque part.
    """
    suspects = []
    for cle, fait in pending.items():
        jetons_cle = cle.split("_")
        jetons_question = _jetons_question(fait.question)
        for i, mot in enumerate(jetons_cle):
            if len(mot) < RACINE_MIN or mot in NEGATEURS:
                continue
            proche = next(
                (
                    j
                    for j, q in enumerate(jetons_question)
                    if len(q) >= RACINE_MIN and (q.startswith(mot) or mot.startswith(q))
                ),
                None,
            )
            if proche is not None and _nie(jetons_cle, i) != _nie(jetons_question, proche):
                suspects.append(cle)
                break
    return sorted(suspects)


__all__ = [
    "MAX_CAR_LIBELLE_OPTION",
    "MAX_CAR_QUESTION",
    "MAX_CAR_QUESTION_CIBLE",
    "MAX_CAR_QUESTION_LINT",
    "MAX_OPTIONS_SANS_GROUPE",
    "NEGATEURS",
    "RACINE_MIN",
    "SEUIL_CHIFFRE_RE",
    "booleen_a_seuil",
    "libelles_trop_longs",
    "options_a_grouper",
    "polarites_suspectes",
    "question_trop_longue",
    "seuil_chiffre",
    "seuil_dans_la_cle",
]
