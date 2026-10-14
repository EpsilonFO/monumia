"""Recherche, détail et proposition d'un fait de l'ontologie.

L'ontologie est le bien le plus précieux du catalogue : c'est elle qui fait
qu'une même question n'est posée qu'une fois au propriétaire, quel que soit le
nombre d'aides qui en dépendent. Un fait proposé en doublon d'un fait existant
coûte donc une question de plus dans le questionnaire de tout le monde — d'où
l'ordre imposé par le skill : chercher, lire le détail, et seulement en dernier
recours proposer.

Un fait proposé va TOUJOURS dans `facts_pending.yaml`, jamais dans
`facts.yaml` : l'approbation (type, scope, formulation canonique de la
question) est une décision humaine. L'écriture passe par `ajouter_sous_verrou`
— deux ingestions parallèles ont déjà détruit ce fichier une fois.
"""

from __future__ import annotations

import re
import sys
import textwrap
from collections.abc import Sequence
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ontologie_regles import (
    MAX_CAR_QUESTION,
    booleen_a_seuil,
    polarites_suspectes,
    question_trop_longue,
    seuil_chiffre,
)
from pipeline.verrou import ajouter_sous_verrou, reecrire_sous_verrou
from veille_text import normalize

from aides_schema import FAIT_PORTEUR, FactDef, charger_yaml, load_pending_facts

from .atelier import Atelier

LIMITE_DEFAUT = 15

# Au-dessus de ce score, la proposition doit citer nommément le fait proche.
#
# Aucun seuil ne SÉPARE les deux populations : mesurées sur le corpus réel, les
# vrais doublons vont de 0,09 à 1,00 en similarité de question et les faits
# légitimement voisins de 0,27 à 0,89 — `porteur_siege_grand_est` et
# `porteur_siege_centre_val_de_loire` sont deux faits distincts à 0,89. D'où un
# détecteur qui ALERTE et force la lecture, et ne refuse jamais.
#
# La valeur, elle, est calée sur deux mesures des 765 faits du corpus :
#   - les cinq familles de doublons connues tombent entre 0,71 et 0,94 (le
#     `max` avec la similarité de CLÉ y est décisif : la reformulation complète
#     `exploitation_atelier_animal` / `exploitation_sau_atelier_animal` vaut
#     0,09 sur la question et 0,93 sur la clé) ;
#   - à 0,55, la proposition médiane se voit opposer SIX voisins et 95 % des
#     propositions déclenchent l'alerte — une liste que le modèle recopierait
#     sans la lire, donc un garde-fou qui ne garde rien. À 0,68, elle se tait
#     sur 60 % des propositions, et ce qu'elle dit porte.
SEUIL_PROXIMITE = 0.68
# Au-delà, la liste cesse d'orienter et devient un mur de texte que le modèle
# recopiera sans lire.
MAX_PROCHES = 6

# Faits NEUFS qu'une seule aide peut faire naître. Mesuré : 563 faits proposés
# pour 643 aides, dont 431 (77 %) cités par une seule aide — et l'ontologie a
# doublé en une nuit. Une aide légitime réutilise l'existant et apporte un ou
# deux faits ; au-delà, ce ne sont plus des faits mais les puces d'un règlement.
#
# Le plafond n'est pas un couperet arbitraire : il a trois issues, toutes
# ouvertes par la doctrine, et le message les nomme. C'est ce qui le distingue
# d'une limite qui pousserait le modèle à tricher sur les libellés.
MAX_FAITS_PAR_AIDE = 3


def _texte_indexe(cle: str, fait: FactDef) -> str:
    """Tout ce sur quoi une recherche doit mordre, normalisé une fois."""
    morceaux = [cle.replace("_", " "), fait.question, fait.help or ""]
    for option in fait.options or []:
        morceaux += [option.id.replace("_", " "), option.label]
    if fait.levier:
        morceaux.append(fait.levier.resume)
    return normalize(" ".join(morceaux))


def rechercher(
    facts: dict[str, FactDef],
    pending: dict[str, FactDef],
    mots: str,
    *,
    scope: str | None = None,
    limite: int = LIMITE_DEFAUT,
) -> str:
    """Faits dont l'id, la question, l'aide ou les options portent ces mots.

    Classement par nombre de mots retrouvés : une requête de trois mots dont un
    seul mord ne doit pas passer devant celle où les trois mordent. À égalité,
    ordre alphabétique — un classement stable est plus facile à relire pour
    l'agent comme pour l'humain qui débogue.
    """
    # Les underscores sont aplatis des DEUX côtés : l'index que lit l'agent
    # affiche les ids tels quels (`en_cours`), il les recopiera donc dans sa
    # requête — et « en_cours » ne doit pas manquer « en cours ».
    tokens = [t for t in normalize(mots.replace("_", " ")).split() if t]
    if not tokens:
        return "Aucun mot-clé fourni."
    tous = {**facts, **pending}
    resultats: list[tuple[int, str]] = []
    for cle, fait in tous.items():
        if scope and fait.scope != scope:
            continue
        indexe = _texte_indexe(cle, fait)
        score = sum(1 for t in tokens if t in indexe)
        if score:
            resultats.append((score, cle))
    if not resultats:
        cadre = f" (scope {scope})" if scope else ""
        return (
            f"Aucun fait ne porte « {mots} »{cadre}. Élargis les mots-clés, ou "
            "propose un fait nouveau avec `proposer_fait` si aucun ne convient."
        )
    resultats.sort(key=lambda r: (-r[0], r[1]))
    lignes = [f"{len(resultats)} fait(s) trouvé(s), les {min(limite, len(resultats))} meilleurs :"]
    lignes += [_ligne_fait(cle, tous[cle], pending) for _score, cle in resultats[:limite]]
    return "\n".join(lignes)


def _ligne_fait(cle: str, fait: FactDef, pending: dict[str, FactDef]) -> str:
    marque = " ⏳ (proposé, non approuvé)" if cle in pending else ""
    options = "  [" + ", ".join(o.id for o in fait.options) + "]" if fait.options else ""
    return (
        f"  {cle}  {fait.type}  {fait.scope}  "
        f"« {' '.join(fait.question.split())} »{options}{marque}"
    )


def rechercher_plongement(
    facts: dict[str, FactDef],
    pending: dict[str, FactDef],
    mots: str,
    *,
    scope: str | None = None,
    limite: int = LIMITE_DEFAUT,
) -> str:
    """Les faits les plus proches de ces mots PAR LE SENS (espace d'embedding).

    Mesuré le 2026-10-14 : avec le texte d'une condition pour requête, le bon
    fait est parmi les 20 premiers 94 fois sur 100, contre 72 pour le comptage
    de mots (`data/reviews/2026-10-14-rappel-faits-plongement.md`). Les faits
    dont l'id ou le texte portent TOUS les mots sont ajoutés en fin de liste :
    une recherche par clé exacte doit toujours retrouver sa clé. Lève si
    l'espace est indisponible ; l'appelant retombe sur `rechercher`.
    """
    from catalogue.espace import instance
    from catalogue.plongements import (
        CONSIGNE_MOTS_VERS_FAIT,
        avec_consigne,
        plus_proches,
        texte_fait,
    )

    if not mots.strip():
        return "Aucun mot-clé fourni."
    tous = {k: f for k, f in {**facts, **pending}.items() if not scope or f.scope == scope}
    if not tous:
        return f"Aucun fait de scope {scope}."
    cles = list(tous)
    plongeur = instance().plongeur
    corpus = plongeur.vecteurs([texte_fait(k, tous[k]) for k in cles])
    requete = plongeur.vecteurs([avec_consigne(CONSIGNE_MOTS_VERS_FAIT, mots)])
    rangs, _ = plus_proches(requete, corpus, limite)
    trouves = [cles[int(j)] for j in rangs[0]]
    jetons = [t for t in normalize(mots.replace("_", " ")).split() if t]
    exacts = [
        cle
        for cle in sorted(tous)
        if cle not in trouves and jetons and all(t in _texte_indexe(cle, tous[cle]) for t in jetons)
    ][:5]
    lignes = [
        f"Les {len(trouves)} faits les plus proches de « {mots} », du plus proche au plus lointain :"
    ]
    lignes += [_ligne_fait(cle, tous[cle], pending) for cle in trouves]
    if exacts:
        lignes.append("Faits qui portent aussi tous ces mots :")
        lignes += [_ligne_fait(cle, tous[cle], pending) for cle in exacts]
    return "\n".join(lignes)


def detail(facts: dict[str, FactDef], pending: dict[str, FactDef], fact_id: str) -> str:
    """La définition complète d'un fait, telle qu'elle est écrite en YAML."""
    fait = pending.get(fact_id) or facts.get(fact_id)
    if fait is None:
        return (
            f"Fait inconnu : « {fact_id} ». Il n'est ni dans facts.yaml ni dans "
            "facts_pending.yaml. Utilise `chercher_faits` pour le retrouver, ou "
            "`proposer_fait` si aucun fait existant ne convient."
        )
    entete = f"# {fact_id}" + (" — PROPOSÉ, non encore approuvé" if fact_id in pending else "")
    corps = yaml.safe_dump(
        {fact_id: fait.model_dump(exclude_none=True, exclude_defaults=True)},
        allow_unicode=True,
        sort_keys=False,
    )
    avertissement = ""
    if fait.hors_gate:
        avertissement = (
            "\n⚠ HORS GATE : aucune condition ne doit gater sur ce fait, le lint le refuse. "
            "La condition se type `manual_check` + `effect: info`, sans `fact` ni `predicate`, "
            "en gardant `text` et `quote` (TYPING, « manual_check + effect: info »).\n"
        )
    if fait.porteurs_concernes:
        # Le message disait encore « l'aide DOIT aussi gater le porteur, le lint le
        # refuse sinon », règle abandonnée le 2026-09-21 : il produisait les gates
        # porteur devinés (EPCI et syndicats mixtes oubliés) retirés à la main
        # sur 61 aides la semaine suivante.
        avertissement += (
            f"\n⚠ RÉSERVÉ AUX PORTEURS : {', '.join(fait.porteurs_concernes)}. Le moteur ferme "
            "déjà ce fait aux autres porteurs. Gate `in` sur "
            f"`{FAIT_PORTEUR}` SEULEMENT si la source nomme ses bénéficiaires, en traduisant "
            "sa liste telle quelle ; sinon aucun gate porteur (SKILL, « Bénéficiaires »).\n"
        )
    return f"{entete}\n{corps}{avertissement}"


# ---------------------------------------------------------------------------
# Proposition
# ---------------------------------------------------------------------------


def _bloc(
    slug: str,
    fact_id: str,
    definition: dict,
    justification: str,
    jour: date,
    famille: str | None = None,
) -> str:
    """Le bloc à ajouter, dans la forme qu'a prise le fichier à la main.

    Un commentaire de provenance et une justification repliée avant chaque
    entrée : c'est ce qui permet à la relecture humaine de trancher sans
    rouvrir la source de l'aide.
    """
    justif = textwrap.fill(
        " ".join(justification.split()),
        width=76,
        initial_indent="# ",
        subsequent_indent="# ",
    )
    corps = yaml.safe_dump({fact_id: definition}, allow_unicode=True, sort_keys=False)
    return (
        f"\n# --- {slug} ---\n"
        f"#\n"
        f"# Proposé par ingerer.py {slug} ({jour.isoformat()}).\n"
        f"{justif}\n" + (f"# {famille}\n" if famille else "") + f"{corps}"
    )


def _proches(
    fact_id: str,
    fait: FactDef,
    tous: dict[str, FactDef],
    *,
    seuil: float = SEUIL_PROXIMITE,
    limite: int = MAX_PROCHES,
) -> list[tuple[float, str]]:
    """Les faits de l'ontologie les plus proches de celui qu'on propose.

    Deux similarités, retenues au MAXIMUM et non moyennées : une reformulation
    complète garde la clé (`exploitation_atelier_animal` /
    `exploitation_sau_atelier_animal`), un renommage garde la question. Prendre
    la moyenne noierait chacun des deux cas dans l'autre moitié.

    Les candidats sont ceux que `chercher_faits` sait retrouver, et la question
    affichée est celle qu'il affiche : l'agent doit pouvoir vérifier par la
    recherche exactement ce qu'on lui oppose.
    """
    cible_question = normalize(fait.question)
    cible_cle = fact_id.replace("_", " ")
    scores: list[tuple[float, str]] = []
    for cle, autre in tous.items():
        if cle == fact_id:
            continue
        score = max(
            SequenceMatcher(None, cible_question, normalize(autre.question)).ratio(),
            SequenceMatcher(None, cible_cle, cle.replace("_", " ")).ratio(),
        )
        if score >= seuil:
            scores.append((score, cle))
    scores.sort(key=lambda s: (-s[0], s[1]))
    return scores[:limite]


def _message_proximite(
    proches: list[tuple[float, str]],
    tous: dict[str, FactDef],
    *,
    non_lus: Sequence[str] = (),
) -> str:
    """L'erreur qui ORIENTE : les faits proches, leur question, et quoi en faire."""
    lignes = [
        f"ERREUR : {len(proches)} fait(s) de l'ontologie ressemblent à celui que tu proposes. "
        "Relis-les avec `detail_fait`, puis soit tu en réutilises un (le prédicat porte le "
        "seuil, pas le fait), soit tu reproposes en disant ce qui les disqualifie :",
    ]
    for score, cle in proches:
        fait = tous[cle]
        options = "  [" + ", ".join(o.id for o in fait.options) + "]" if fait.options else ""
        marque = "  ← pas encore lu" if cle in non_lus else ""
        lignes.append(
            f"  {cle}  ({score:.0%})  {fait.type}  {fait.scope}  "
            f"« {' '.join(fait.question.split())} »{options}{marque}"
        )
    if non_lus:
        lignes.append(
            "Appelle `detail_fait` sur chacun des faits marqués « pas encore lu » avant de "
            "reproposer : recopier une clé dans la justification ne dit pas que tu l'as lue, "
            "et c'est exactement comme ça que 27 paires de quasi-doublons sont entrées."
        )
    lignes.append(
        "Un fait légitimement voisin n'est PAS refusé : il suffit de l'avoir lu et "
        "d'expliquer l'écart dans la justification."
    )
    return "\n".join(lignes)


def _famille(fact_id: str, fait: FactDef, tous: dict[str, FactDef]) -> tuple[Any, bool]:
    """(la famille du fait selon Jev ou None, l'espace est-il en panne).

    En panne (espace coupé, embedding ou Jev indisponible), l'appelant reprend
    le garde lexical : un fait neuf ne passe jamais sans garde.
    """
    try:
        from catalogue.espace import actif, famille_du_fait

        if not actif():
            return None, True
        f = famille_du_fait(fact_id, fait, tous)
    except Exception:  # noqa: BLE001 — l'espace en panne ne bloque pas la proposition
        return None, True
    return f, False


def _message_famille(famille: Any, tous: dict[str, FactDef]) -> str:
    """L'erreur qui ORIENTE vers le fait existant que Jev rattache à la proposition."""
    autre = tous[famille.cle]
    options = "  [" + ", ".join(o.id for o in autre.options) + "]" if autre.options else ""
    voisins = [c for c in famille.candidats if c != famille.cle]
    return "\n".join(
        [
            f"ERREUR : le fait existant `{famille.cle}` pose déjà cette question selon Jev "
            f"({famille.proba:.0%}) :",
            f"  {famille.cle}  {autre.type}  {autre.scope}  "
            f"« {' '.join(autre.question.split())} »{options}",
            "Relis-le avec `detail_fait`, puis réutilise-le : le seuil appartient au prédicat "
            "de l'aide, pas au fait. S'il ne convient vraiment pas, repropose en disant dans "
            "la justification ce qui l'en distingue : la proposition passera, et le "
            "rapprochement sera soumis à Félix.",
            f"Autres faits proches : {', '.join(voisins)}." if voisins else "",
        ]
    ).rstrip()


#: Une question que tout demandeur accepte : « acceptez-vous de… »,
#: « vous engagez-vous à… ». Elle ne trie personne et entre au questionnaire de
#: tous les propriétaires.
_PROMESSE_RE = re.compile(
    r"^\W*(acceptez|vous\s+(vous\s+)?engag|vous-engag|vous\s+engager|"
    r"(le\s+porteur|la\s+structure|le\s+b[ée]n[ée]ficiaire)\s+s['’]\s*engag)",
    re.IGNORECASE,
)


def promesse(fact_id: str, fait: FactDef) -> bool:
    """Vrai si le fait proposé est une promesse : clé `s_engage_*` ou question d'engagement.

    La famille entière (43 faits, 143 conditions) a été retypée le 2026-09-22 ;
    la consigne du SKILL n'avait pas suffi à l'empêcher de naître. Le refus
    vit ici, au seul endroit où le fait n'existe pas encore.
    """
    return fact_id.startswith("s_engage") or bool(_PROMESSE_RE.search(fait.question))


def _refus_de_forme(fact_id: str, fait: FactDef) -> str | None:
    """Les refus de FORME, ou `None`. Chacun oriente vers ce qu'il faut écrire.

    Ils se posent à l'ÉCRITURE et pas au lint, parce qu'ici le fait n'existe pas
    encore : l'agent peut corriger et reproposer, sans qu'aucun prédicat ne cite
    déjà la clé. Le lint, lui, ne peut qu'avertir sur un stock déjà écrit.
    """
    if promesse(fact_id, fait):
        return (
            f"ERREUR : « {fact_id} » est une PROMESSE (« acceptez-vous… », « vous "
            "engagez-vous à… ») : tout demandeur répond oui, la question ne trie personne et "
            "elle entrerait au questionnaire de TOUS les propriétaires.\n"
            "Type la condition `kind: info` + `effect: info`, avec le `text` et la `quote` de "
            "la source : l'exigence reste affichée sur la fiche, sans devenir une question. "
            "Si la promesse cache un critère réel (déposer avant le démarrage d'un "
            "CHANTIER, par exemple), gate sur le fait qui porte ce critère (`etat_travaux`) : "
            "le moteur ne le pose qu'aux aides qui le gatent (TYPING.md, « Antériorité du "
            "dépôt »)."
        )
    seuil = booleen_a_seuil(fact_id, fait) or (
        seuil_chiffre(fact_id, fait.question) if fait.type == "boolean" else None
    )
    if seuil:
        return (
            f"ERREUR : « {fact_id} » est un booléen qui enferme un seuil chiffré "
            f"(« {seuil} »). Le seuil appartient au PRÉDICAT de l'aide, pas au fait : deux "
            "règlements qui exigent 15 et 20 ans doivent poser UNE question (« quel âge a "
            "le bâtiment ? ») et non deux booléens qu'aucun moteur ne sait rapprocher.\n"
            "Propose plutôt un `integer` ou un `number` — clé sans chiffre, `unit` renseignée, "
            "question ouverte — et gate dessus avec `{gte: 15}`. Si la valeur ne se demande "
            "pas raisonnablement au propriétaire, type la condition `manual_check` + "
            "`effect: info` et ne propose aucun fait."
        )
    longueur = question_trop_longue(fait)
    if longueur:
        return (
            f"ERREUR : la question fait {longueur} caractères ({MAX_CAR_QUESTION} au maximum). "
            "Une question est UNE phrase, lisible par un propriétaire qui n'a pas le "
            "règlement sous les yeux ; le détail va dans `help`, que le front affiche en "
            "aide contextuelle.\n"
            "Si ce que tu écris est la liste d'exclusions d'un règlement, ce n'est pas un "
            "fait : c'est `hard_filters.travaux` ou un `applies_if` quand elle borne l'objet, "
            "et `manual_check` + `effect: info` sinon."
        )
    if polarites_suspectes({fact_id: fait}):
        return (
            f"ERREUR : la clé « {fact_id} » et la question semblent de polarité OPPOSÉE — "
            "l'une affirme ce que l'autre nie. Chaque prédicat qui citerait ce fait dirait "
            "alors le contraire de ce que tu as lu dans la source, et ni le lint ni le moteur "
            "ne peuvent le voir.\n"
            "Accorde les deux : soit la clé dit ce que la question demande "
            "(`chauffage_sans_fioul` ↔ « le chauffage sera-t-il sans fioul ? »), soit tu "
            "inverses la question."
        )
    return None


def _validateur(fact_id: str, facts: dict[str, FactDef]):
    """Refuse d'écrire un `facts_pending.yaml` que le lint ne pourrait pas lire.

    La validation porte sur le fichier COMPLET tel qu'il serait écrit : c'est
    la seule façon de voir une collision avec une entrée qu'un autre worker
    vient d'ajouter sous le même verrou.
    """

    def valider(texte: str) -> None:
        brut = charger_yaml(texte) or {}
        if not isinstance(brut, dict):
            raise ValueError("facts_pending.yaml doit être un dictionnaire de faits")
        for cle, valeur in brut.items():
            try:
                FactDef.model_validate(valeur)
            except Exception as exc:
                raise ValueError(f"fait invalide « {cle} » : {exc}") from exc
        if fact_id not in brut:
            raise ValueError(f"« {fact_id} » absent du fichier après ajout — YAML mal formé ?")
        collisions = sorted(set(brut) & set(facts))
        if collisions:
            raise ValueError(f"clé(s) déjà présentes dans facts.yaml : {collisions}")

    return valider


def _message_plafond(deja: Sequence[str]) -> str:
    """Le refus qui ORIENTE : trois issues nommées, aucune n'est « débrouille-toi »."""
    return (
        f"ERREUR : plafond atteint — cette ingestion a déjà proposé {len(deja)} fait(s) neuf(s) "
        f"({', '.join(deja)}), c'est le maximum. Une aide qui en demande un quatrième décrit "
        "les puces de son règlement, pas des questions que d'autres financeurs poseraient.\n"
        "Trois issues, toutes conformes à la doctrine :\n"
        "  - une exigence PROPRE à cette aide, qu'aucun fait partageable ne porte, se type "
        "`kind: manual_check` + `effect: info` : la condition garde son `text` et sa `quote`, "
        "et s'affiche « à confirmer avec l'organisme » ;\n"
        "  - un ENGAGEMENT du demandeur (« s'engage à… », charte, balisage) se type "
        "`kind: info` + `effect: info` : il se vérifie au dossier, pas au questionnaire ;\n"
        "  - si l'un des faits déjà proposés est moins partageable que celui-ci, "
        "`retirer_fait` le retire, et tu reproposes."
    )


def proposer(
    atelier: Atelier,
    facts: dict[str, FactDef],
    fact_id: str,
    definition_yaml: str,
    justification: str,
    *,
    deja_proposes: Sequence[str] = (),
    detailles: Sequence[str] = (),
) -> str:
    """Ajoute un fait à `facts_pending.yaml`. Renvoie le message rendu à l'agent.

    Les faits en attente sont RELUS DEPUIS LE DISQUE et non pris dans le
    contexte du run : un worker parallèle a pu en ajouter un depuis, et
    proposer deux fois la même clé casserait le fichier.
    """
    if not fact_id or not fact_id.replace("_", "").isalnum() or not fact_id.islower():
        return (
            f"ERREUR : identifiant de fait invalide « {fact_id} » — "
            "en minuscules, chiffres et underscores seulement (ex. jardin_remarquable)."
        )
    if not justification or len(justification.strip()) < 80:
        return (
            "ERREUR : justification trop courte. Explique en quelques phrases POURQUOI "
            "aucun fait existant ne convient (cite les faits proches que tu as écartés "
            "et ce qui les disqualifie) — c'est ce texte qui sert à la relecture humaine."
        )
    if len(deja_proposes) >= MAX_FAITS_PAR_AIDE:
        return _message_plafond(deja_proposes)

    try:
        brut = charger_yaml(definition_yaml)
    except yaml.YAMLError as exc:
        return f"ERREUR : YAML invalide — {exc}"
    # Le modèle envoie tantôt la définition nue, tantôt `{id: définition}` :
    # les deux sont acceptées, la seconde est dépliée.
    if isinstance(brut, dict) and set(brut) == {fact_id} and isinstance(brut[fact_id], dict):
        brut = brut[fact_id]
    if not isinstance(brut, dict):
        return "ERREUR : la définition doit être un objet YAML (type, scope, question…)."

    try:
        fait = FactDef.model_validate(brut)
    except Exception as exc:
        return f"ERREUR : définition de fait invalide — {exc}"

    forme = _refus_de_forme(fact_id, fait)
    if forme:
        return forme

    if fact_id in facts:
        return (
            f"ERREUR : « {fact_id} » existe déjà dans facts.yaml — réutilise-le "
            "(le prédicat porte le seuil, pas le fait). `detail_fait` pour le relire."
        )
    load_pending_facts.cache_clear()
    pending = load_pending_facts(atelier.pending_path)
    if fact_id in pending:
        return (
            f"ERREUR : « {fact_id} » est déjà proposé dans facts_pending.yaml — "
            "utilise-le tel quel, il est valide pour le typage."
        )

    tous = {**facts, **pending}
    mention: str | None = None
    famille, en_panne = _famille(fact_id, fait, tous)
    if en_panne:
        proches = _proches(fact_id, fait, tous)
        # « Cite le fait voisin » doit vouloir dire « va le LIRE ». Le garde
        # cherchait la clé du voisin comme SOUS-CHAÎNE de la justification :
        # recopier `porteur_siege_grand_est` dans une phrase suffisait à lever
        # l'alerte, sans avoir jamais ouvert sa définition. On demande
        # maintenant un `detail_fait`.
        non_lus = [(s, c) for s, c in proches if c not in detailles]
        if non_lus:
            return _message_proximite(proches, tous, non_lus=[c for _s, c in non_lus])
    elif famille is not None:
        if famille.cle not in detailles:
            return _message_famille(famille, tous)
        mention = (
            f"Famille selon Jev : {famille.cle} ({famille.proba:.2f}), lue et écartée par l'agent."
        )

    definition = fait.model_dump(exclude_none=True, exclude_defaults=True)
    bloc = _bloc(atelier.slug, fact_id, definition, justification, atelier.jour, mention)
    try:
        ajouter_sous_verrou(atelier.pending_path, bloc, valider=_validateur(fact_id, facts))
    except Exception as exc:
        return f"ERREUR : écriture refusée dans facts_pending.yaml — {exc}"
    # Le lint que l'agent lancera juste après doit voir le fait : sans purge,
    # il se ferait refuser sa propre proposition (`fait inconnu`).
    load_pending_facts.cache_clear()
    suite = (
        f" Jev désignait `{famille.cle}` : le rattachement est noté dans le bloc."
        if mention and famille is not None
        else ""
    )
    return (
        f"Fait « {fact_id} » ajouté à {atelier.relatif(atelier.pending_path)} "
        "(en attente d'approbation humaine). Tu peux le référencer dès maintenant "
        "dans une condition `kind: user_fact`, et le signaler dans la review." + suite
    )


# ---------------------------------------------------------------------------
# Retrait
# ---------------------------------------------------------------------------


def _references(aides_dir: Path, fact_id: str) -> list[str]:
    """Les aides dont une condition cible ce fait — `fact:` et `applies_if.fact`.

    Recherche TEXTUELLE et non chargement des 396 fichiers : les deux formes
    s'écrivent `fact: <id>` en YAML, le motif est donc exact, et un retrait
    n'a pas à payer le prix d'un lint complet.
    """
    motif = re.compile(rf"^\s*fact:\s*{re.escape(fact_id)}\s*$", re.MULTILINE)
    if not aides_dir.is_dir():
        return []
    return sorted(
        chemin.stem
        for chemin in aides_dir.glob("*.yaml")
        if motif.search(chemin.read_text(encoding="utf-8", errors="replace"))
    )


def _decouper_bloc(texte: str, fact_id: str) -> tuple[int, int] | None:
    """(début, fin) des lignes du bloc de `fact_id`, commentaire de tête compris.

    Découpage TEXTUEL, jamais `safe_load` puis `safe_dump` : le dump détruirait
    les justifications commentées de tout le fichier, qui sont précisément ce
    que la relecture humaine arbitre.

    En tête, on remonte les commentaires attenants et on s'arrête à la ligne
    vide qui les précède — donc jamais au-delà d'une autre clé de premier
    niveau, deux blocs historiques du fichier portant plusieurs faits sous un
    seul en-tête de provenance. En queue, on descend le corps indenté (lignes
    vides d'un scalaire replié comprises) puis on absorbe les lignes vides qui
    suivent, qui sont le séparateur du bloc retiré.
    """
    lignes = texte.splitlines(keepends=True)
    entete = re.compile(rf"^{re.escape(fact_id)}\s*:")
    depart = next((i for i, li in enumerate(lignes) if entete.match(li)), None)
    if depart is None:
        return None
    debut = depart
    while debut > 0 and lignes[debut - 1].startswith("#"):
        debut -= 1
    dernier_corps = depart
    curseur = depart + 1
    while curseur < len(lignes) and (
        lignes[curseur][:1] in (" ", "\t") or not lignes[curseur].strip()
    ):
        if lignes[curseur].strip():
            dernier_corps = curseur
        curseur += 1
    fin = dernier_corps + 1
    while fin < len(lignes) and not lignes[fin].strip():
        fin += 1
    return debut, fin


def _validateur_retrait(fact_id: str, avant: set[str]):
    """Refuse toute réécriture qui ne retire pas exactement ce fait-là.

    L'invariant se lit sur le fichier COMPLET relu sous le verrou : un
    découpage textuel qui mordrait sur le voisin se verrait ici, et le fichier
    ne serait pas touché.
    """

    def valider(texte: str) -> None:
        brut = charger_yaml(texte) or {}
        if not isinstance(brut, dict):
            raise ValueError("facts_pending.yaml doit être un dictionnaire de faits")
        attendu = avant - {fact_id}
        if set(brut) != attendu:
            perdus = sorted(attendu - set(brut))
            surnumeraires = sorted(set(brut) - attendu)
            raise ValueError(
                "le retrait aurait emporté d'autres faits "
                f"(perdus : {perdus or 'aucun'}, en trop : {surnumeraires or 'aucun'})"
            )
        for cle, valeur in brut.items():
            try:
                FactDef.model_validate(valeur)
            except Exception as exc:
                raise ValueError(f"fait invalide « {cle} » : {exc}") from exc

    return valider


def retirer(atelier: Atelier, fact_id: str, *, proposes: Sequence[str] = ()) -> str:
    """Retire un fait de `facts_pending.yaml`. Renvoie le message rendu à l'agent.

    Deux gardes, sans quoi un worker effacerait le fait d'un autre : le fait
    doit avoir été proposé par le RUN COURANT (`proposes`), et n'être référencé
    par aucune aide. Un fait approuvé (`facts.yaml`) ne se retire jamais par ici
    — c'est une décision humaine, pas un geste d'agent.
    """
    load_pending_facts.cache_clear()
    pending = load_pending_facts(atelier.pending_path)
    if fact_id not in pending:
        return (
            f"ERREUR : « {fact_id} » n'est pas dans facts_pending.yaml — rien à retirer. "
            "Seuls les faits que tu viens de proposer s'y retirent."
        )
    if fact_id not in proposes:
        return (
            f"ERREUR : « {fact_id} » n'a pas été proposé par cette ingestion — "
            "il vient d'une autre aide, et le retirer casserait son typage. "
            "Signale-le dans la fiche de review si tu le crois en doublon."
        )
    references = _references(atelier.aides_dir, fact_id)
    if references:
        return (
            f"ERREUR : « {fact_id} » est encore référencé par {', '.join(references)}. "
            "Retype d'abord la ou les conditions qui le citent (`ecrire_aide`), "
            "puis relance `retirer_fait`."
        )

    avant = set(pending)

    def transformer(texte: str) -> str:
        bornes = _decouper_bloc(texte, fact_id)
        if bornes is None:
            raise ValueError(f"« {fact_id} » introuvable en tête de ligne dans le fichier")
        debut, fin = bornes
        lignes = texte.splitlines(keepends=True)
        reste = "".join(lignes[:debut] + lignes[fin:])
        return (reste.rstrip("\n") + "\n") if reste.strip() else ""

    try:
        reecrire_sous_verrou(
            atelier.pending_path, transformer, valider=_validateur_retrait(fact_id, avant)
        )
    except Exception as exc:
        return f"ERREUR : retrait refusé dans facts_pending.yaml — {exc}"
    load_pending_facts.cache_clear()
    return (
        f"Fait « {fact_id} » retiré de {atelier.relatif(atelier.pending_path)}. "
        "Plus aucune condition ne doit le citer : relance `lint` pour t'en assurer."
    )


__all__ = [
    "LIMITE_DEFAUT",
    "MAX_PROCHES",
    "SEUIL_PROXIMITE",
    "detail",
    "proposer",
    "rechercher",
    "retirer",
]
