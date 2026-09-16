"""Audit de l'ontologie en fin de run : ce que les gardes à l'écriture ratent.

Trois causes ont produit 90 quasi-doublons et 48 orphelins dans
`facts_pending.yaml`. Deux se corrigent à l'écriture — `retirer_fait` rend
l'ontologie réparable, l'avertissement de proximité force à motiver. La
troisième ne s'attrape qu'après coup : `chercher_faits` ne croise pas les
synonymes, et deux runs qui ne partagent pas de vocabulaire proposeront le même
fait sous deux noms sans jamais se rencontrer.

D'où un audit en fin de run, à DEUX ÉTAGES, et l'hybridation n'est pas un
confort :

  - un pré-filtre déterministe, sans réseau, qui apparie sur la clé et sur la
    question. Il est aveugle à la reformulation complète — la mesure du corpus
    donne 0,09 de similarité de question entre deux faits identiques ;
  - un appel de modèle, UN seul, qui juge les paires retenues. Lui voit le sens.

Le rapport ne modifie RIEN : il propose des fusions, il ne fusionne pas. Une
fusion automatique se tromperait sur les paires à polarité inversée
(`chauffage_fioul_apres_travaux` contre `chauffage_sans_fioul_apres_travaux`),
où l'erreur inverse un critère d'éligibilité en silence et sans laisser de
trace dans un diff.
"""

from __future__ import annotations

import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import providall
from lint_aides_data import faits_references_dans
from pipeline.llm import Compteur
from veille_text import normalize

from aides_schema import FactDef

from .atelier import Atelier
from .faits import SEUIL_PROXIMITE

# Le pré-filtre ratisse PLUS LARGE que le garde à l'écriture : il n'a personne à
# interrompre, et ce qu'il laisse passer ici, plus rien ne le verra. Le coût
# d'une paire de trop est une ligne dans un prompt ; celui d'une paire manquée
# est une question de plus dans le questionnaire de tous les propriétaires.
SEUIL_AUDIT = SEUIL_PROXIMITE - 0.08
# Au-delà, le prompt cesse d'être lisible par le modèle comme par l'humain qui
# relira le rapport. Les paires sont triées par score : on garde les pires.
MAX_PAIRES = 60

# Les deux seuls négateurs retenus, et c'est une décision de PRÉCISION. Y
# ajouter « hors », « pas », « exclu » fait passer les suspects de 12 à 34 sur
# le corpus réel, pour un seul vrai cas de plus : le français place un nom entre
# le négateur et ce qu'il nie (« hors des catégories exclues »), et l'adjacence
# de jetons ne sait pas le suivre. Un rapport à 90 % de bruit n'est pas lu, donc
# ne rattrape rien.
_NEGATEURS = frozenset({"non", "sans"})
# En dessous, un préfixe commun ne prouve aucune parenté de sens.
_RACINE_MIN = 5


class Fusion(BaseModel):
    """Un verdict du modèle sur une paire de faits."""

    garder: str = Field(description="Clé du fait à CONSERVER")
    retirer: str = Field(description="Clé du fait à retirer au profit du précédent")
    verdict: Literal["doublon", "polarite_inversee", "distincts"] = Field(
        description="doublon = même question posée deux fois ; polarite_inversee = même "
        "critère mais l'un nie ce que l'autre affirme, fusionner impose d'inverser le "
        "prédicat des aides du camp retiré ; distincts = ne pas fusionner"
    )
    motif: str = Field(description="Ce qui fonde le verdict, en une ou deux phrases")
    prudence: str = Field(
        default="",
        description="Ce qu'il faut vérifier avant de fusionner : scopes différents, "
        "types différents, options à réconcilier, prédicats à inverser",
    )


class RapportOntologie(BaseModel):
    """Ce que l'audit a trouvé. Aucun de ces champs n'est appliqué automatiquement."""

    fusions: list[Fusion] = []
    commentaire: str = ""
    # Calculés, jamais demandés au modèle : il n'a pas à recompter ce qu'un
    # `set` sait, et lui laisser la main sur ces listes les rendrait fausses.
    orphelins: list[str] = []
    polarites_suspectes: list[str] = []
    degrade: str = ""

    @property
    def a_fusionner(self) -> list[Fusion]:
        return [f for f in self.fusions if f.verdict != "distincts"]


# ---------------------------------------------------------------------------
# Étage 1 : le pré-filtre déterministe
# ---------------------------------------------------------------------------


def paires_suspectes(
    facts: dict[str, FactDef],
    pending: dict[str, FactDef],
    *,
    seuil: float = SEUIL_AUDIT,
    limite: int = MAX_PAIRES,
) -> list[tuple[float, str, str]]:
    """Les paires (score, clé A, clé B) assez proches pour mériter un jugement.

    Seuls les faits PROPOSÉS sont candidats au retrait : un fait approuvé a été
    arbitré par un humain, et l'audit d'un run n'a pas à le remettre en cause.
    Chaque proposé est donc comparé à toute l'ontologie, approuvés compris — un
    doublon d'un fait de `facts.yaml` est le cas le plus rentable à trouver.

    Deux similarités prises au MAXIMUM, jamais moyennées : une reformulation
    complète garde la clé, un renommage garde la question, et la moyenne noierait
    chacun des deux cas dans l'autre moitié.
    """
    tous = {**facts, **pending}
    vus: set[tuple[str, str]] = set()
    scores: list[tuple[float, str, str]] = []
    for cle, fait in pending.items():
        question = normalize(fait.question)
        mots_cle = cle.replace("_", " ")
        for autre, fait_autre in tous.items():
            if autre == cle:
                continue
            paire = (cle, autre) if cle < autre else (autre, cle)
            if paire in vus:
                continue
            score = max(
                SequenceMatcher(None, question, normalize(fait_autre.question)).ratio(),
                SequenceMatcher(None, mots_cle, autre.replace("_", " ")).ratio(),
            )
            if score >= seuil:
                vus.add(paire)
                scores.append((score, cle, autre))
    scores.sort(key=lambda s: (-s[0], s[1], s[2]))
    return scores[:limite]


def orphelins(pending: dict[str, FactDef], aides_dir: Path) -> list[str]:
    """Les faits proposés qu'aucune aide ne référence — des brouillons.

    Même comptage que le lint, sur le catalogue ENTIER : un fait proposé par une
    autre aide du même run ne doit pas passer pour abandonné.
    """
    return sorted(set(pending) - faits_references_dans(aides_dir))


def _nie(jetons: list[str], i: int) -> bool:
    """Le jeton `i` est-il directement précédé d'un négateur ?"""
    return i > 0 and jetons[i - 1] in _NEGATEURS


def _jetons_question(question: str) -> list[str]:
    """La question en jetons nus : la ponctuation collée masquerait la racine."""
    return [j.strip("().,;:?!«»\"'") for j in normalize(question).replace("'", " ").split()]


def polarites_suspectes(pending: dict[str, FactDef]) -> list[str]:
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
            if len(mot) < _RACINE_MIN or mot in _NEGATEURS:
                continue
            proche = next(
                (
                    j
                    for j, q in enumerate(jetons_question)
                    if len(q) >= _RACINE_MIN and (q.startswith(mot) or mot.startswith(q))
                ),
                None,
            )
            if proche is not None and _nie(jetons_cle, i) != _nie(jetons_question, proche):
                suspects.append(cle)
                break
    return sorted(suspects)


# ---------------------------------------------------------------------------
# Étage 2 : le jugement
# ---------------------------------------------------------------------------

CONSIGNE = """\
Tu audites l'ontologie des faits d'un catalogue d'aides au financement du
patrimoine. Un « fait » est une question posée une seule fois au propriétaire,
et dont plusieurs aides lisent la réponse. Deux faits qui posent la MÊME
question, c'est une question de plus dans le questionnaire de tout le monde.

On te donne des paires de faits qu'un appariement textuel a jugées proches. Le
textuel se trompe dans les deux sens : `porteur_siege_grand_est` et
`porteur_siege_centre_val_de_loire` se ressemblent à 89 % et sont deux faits
DISTINCTS (deux régions), tandis que `exploitation_atelier_animal` et
`exploitation_sau_atelier_animal` se ressemblent à 9 % sur la question et sont
le MÊME fait. C'est pour ça qu'on te les soumet.

Pour chaque paire, tranche :
  - `doublon` : les deux posent la même question au même interlocuteur. Dis
    lequel GARDER — celui dont la question est la plus claire et la portée la
    plus générale, et à égalité celui de facts.yaml (marqué « approuvé »).
  - `polarite_inversee` : même critère, mais l'un affirme ce que l'autre nie
    (« chauffage au fioul maintenu » / « chauffage sans fioul »). Fusionner
    impose d'INVERSER le prédicat des aides du fait retiré : dis-le en prudence.
  - `distincts` : ne pas fusionner. Deux territoires, deux seuils, deux portées.

Trois pièges à ne pas manquer, à signaler dans `prudence` :
  - des `scope` différents (monument / projet / proprietaire) ne se fusionnent
    pas sans décision de modèle : le scope dit à QUOI la question se rattache ;
  - un `enum` qui absorbe des booléens fait passer les prédicats de `eq: true` à
    `in: [...]`, ce qui demande de relire ce que chaque aide exige vraiment ;
  - des `options` qui ne se recouvrent pas.

Ne propose une fusion que si tu la défendrais devant la personne qui devra
l'appliquer à la main dans les fichiers d'aides. Dans le doute, `distincts`.
"""


def _ligne_fait(cle: str, fait: FactDef, *, approuve: bool) -> str:
    options = "  options=[" + ", ".join(o.id for o in fait.options) + "]" if fait.options else ""
    unite = f" ({fait.unit})" if fait.unit else ""
    marque = "approuvé" if approuve else "proposé"
    aide = f"\n      aide : {' '.join(fait.help.split())}" if fait.help else ""
    return (
        f"  {cle}  [{marque}]  {fait.type}{unite}  scope={fait.scope}{options}\n"
        f"      « {' '.join(fait.question.split())} »{aide}"
    )


def construire_prompt(
    paires: list[tuple[float, str, str]],
    facts: dict[str, FactDef],
    pending: dict[str, FactDef],
) -> str:
    tous = {**facts, **pending}
    blocs = []
    for score, a, b in paires:
        blocs.append(
            f"### Paire {a} / {b} — proximité textuelle {score:.0%}\n"
            + _ligne_fait(a, tous[a], approuve=a in facts)
            + "\n"
            + _ligne_fait(b, tous[b], approuve=b in facts)
        )
    return "\n\n".join(
        [
            CONSIGNE,
            "Tu n'as ni outil ni accès au système de fichiers : tout ce qu'il te faut est "
            "ci-dessous. Réponds UNIQUEMENT par le JSON demandé, une entrée par paire.",
            f"## {len(paires)} paire(s) à juger\n\n" + "\n\n".join(blocs),
        ]
    )


def auditer(
    atelier: Atelier,
    facts: dict[str, FactDef],
    pending: dict[str, FactDef],
    client: providall.Client | None = None,
    *,
    compteur: Compteur | None = None,
    seuil: float = SEUIL_AUDIT,
    limite: int = MAX_PAIRES,
) -> RapportOntologie:
    """Audite l'ontologie. Ne lève JAMAIS : une panne devient un rapport dégradé.

    Le run est terminé quand cet audit tourne — les fichiers sont écrits, les
    fiches de review aussi. Faire échouer le run sur un audit qui ne modifie
    rien coûterait une ingestion entière pour une information de confort.
    """
    rapport = RapportOntologie(
        orphelins=orphelins(pending, atelier.aides_dir),
        polarites_suspectes=polarites_suspectes(pending),
    )
    paires = paires_suspectes(facts, pending, seuil=seuil, limite=limite)
    if not paires:
        rapport.commentaire = "Aucune paire de faits assez proche pour mériter un jugement."
        return rapport
    if client is None:
        rapport.degrade = f"{len(paires)} paire(s) proches non jugées (audit désactivé)."
        return rapport

    essai = client.try_complete_json(RapportOntologie, construire_prompt(paires, facts, pending))
    if compteur is not None:
        compteur.ajouter(essai.response, "audit_ontologie")
    if essai.data is None:
        rapport.degrade = (
            f"Auditeur indisponible ({essai.response.error}) — "
            f"{len(paires)} paire(s) proches restent à trancher à la main : "
            + ", ".join(f"{a}/{b}" for _s, a, b in paires[:10])
            + (" …" if len(paires) > 10 else "")
        )
        return rapport
    # Les listes calculées ne viennent pas du modèle : il aurait pu les inventer,
    # et elles sont exactes par construction.
    rapport.fusions = essai.data.fusions
    rapport.commentaire = essai.data.commentaire
    return rapport


# ---------------------------------------------------------------------------
# Rendu
# ---------------------------------------------------------------------------


def rendre(rapport: RapportOntologie) -> str:
    """Le rapport tel qu'il s'imprime en fin de run, sous le tableau des aides."""
    lignes: list[str] = ["", "AUDIT DE L'ONTOLOGIE (aucun fichier n'a été modifié) :"]
    if rapport.degrade:
        lignes.append(f"  ⚠ {rapport.degrade}")
    a_fusionner = rapport.a_fusionner
    if a_fusionner:
        lignes.append(f"  {len(a_fusionner)} fusion(s) proposée(s) :")
        for f in a_fusionner:
            marque = " ⚠ POLARITÉ INVERSÉE" if f.verdict == "polarite_inversee" else ""
            lignes.append(f"    {f.retirer} → {f.garder}{marque}")
            lignes.append(f"      {' '.join(f.motif.split())}")
            if f.prudence:
                lignes.append(f"      prudence : {' '.join(f.prudence.split())}")
    elif not rapport.degrade:
        lignes.append("  Aucune fusion à proposer.")
    if rapport.orphelins:
        lignes.append(
            f"  {len(rapport.orphelins)} fait(s) proposé(s) qu'aucune aide ne référence : "
            + ", ".join(rapport.orphelins)
        )
    if rapport.polarites_suspectes:
        lignes.append(
            f"  {len(rapport.polarites_suspectes)} fait(s) dont la clé et la question "
            "semblent de polarité opposée (un prédicat les citant dirait l'inverse de ce "
            "qu'on a lu) : " + ", ".join(rapport.polarites_suspectes)
        )
    if rapport.commentaire:
        lignes.append(f"  {' '.join(rapport.commentaire.split())}")
    lignes.append(
        "  Rien n'est appliqué : une fusion se fait à la main, dans facts_pending.yaml ET "
        "dans les aides qui citent le fait retiré."
    )
    return "\n".join(lignes)


__all__ = [
    "CONSIGNE",
    "MAX_PAIRES",
    "SEUIL_AUDIT",
    "Fusion",
    "RapportOntologie",
    "auditer",
    "construire_prompt",
    "orphelins",
    "paires_suspectes",
    "polarites_suspectes",
    "rendre",
]
