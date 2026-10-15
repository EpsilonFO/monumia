"""Les reformulations de question proposées par l'agent d'ingestion (décision `R1-reformulation`).

Face à un fait presque bon (même information, question trop étroite ou ambiguë
pour le cas de sa source), l'agent peut proposer une nouvelle tournure de la
`question` et du `help` d'un fait de `facts.yaml`, après avoir vu toutes les
conditions qui le citent (`scripts/ingestion/reformulation.py`, qui porte les
refus). Ce module prend le relais une fois l'aide acceptée :

1. **Remontée** : la proposition entre dans le fichier partagé
   `data/catalogue/reformulations.yaml` (premier arrivé gardé, une par fait)
   et ouvre une case `R-reformulation` dans le rapport de la semaine.
2. **Application** au run suivant, sur la réponse de Félix : `appliquer`
   réécrit le bloc du fait dans `facts.yaml`, à condition que la question et
   l'aide en place soient encore celles que la proposition a vues ; `refuser`,
   ou des témoins qui ne correspondent plus, retirent l'entrée sans rien écrire.

La réécriture de `facts.yaml` est TEXTUELLE : seules les lignes de `question`
et de `help` du fait changent, les commentaires du fichier restent. Le
validateur relit le fichier complet et refuse toute écriture où autre chose
que ces deux champs de ce fait aurait bougé.
"""

from __future__ import annotations

import copy
import json
import re
import textwrap
from pathlib import Path
from typing import Any

import yaml
from pipeline.verrou import reecrire_sous_verrou

from aides_schema import DATA_DIR, FACTS_FILE, FactDef, charger_yaml
from catalogue.cases import Case
from catalogue.journal import Vue, empreinte

REFORMULATIONS = DATA_DIR / "catalogue" / "reformulations.yaml"
SORTE = "R-reformulation"
ENTETE = (
    "# Reformulations de question proposées par l'agent d'ingestion (R1-reformulation).\n"
    "# Une entrée par fait, en attente de la case `R-reformulation` du rapport de la\n"
    "# semaine. Écrit par `catalogue/reformulations.py` : ne pas éditer à la main.\n"
)
#: Au-delà, la case devient un mur que personne ne lit.
MAX_LIGNES_CITATIONS = 12
LARGEUR = 100


def _plat(texte: Any) -> str:
    """Le texte tel qu'on le compare : un scalaire replié et le même sur une ligne sont égaux."""
    return " ".join(str(texte or "").split())


def objet(cle: str) -> str:
    return f"f:{cle}"


def etat(entree: dict[str, Any]) -> str:
    """L'empreinte de ce que Félix voit : la tournure d'origine et la tournure proposée."""
    return empreinte(
        json.dumps(
            {
                k: _plat(entree.get(k))
                for k in ("fact", "question_origine", "help_origine", "question", "help")
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


# ------------------------------------------------------------------ le fichier d'attente


def lire(chemin: Path | None = None) -> dict[str, dict[str, Any]]:
    """Les entrées en attente, clé du fait -> entrée. Fichier absent : aucune."""
    chemin = chemin or REFORMULATIONS
    if not chemin.exists():
        return {}
    brut = charger_yaml(chemin.read_text(encoding="utf-8")) or {}
    if not isinstance(brut, dict):
        raise ValueError(f"{chemin} : un dictionnaire de reformulations est attendu")
    return {str(k): dict(v) for k, v in brut.items() if isinstance(v, dict)}


def _dump(entrees: dict[str, dict[str, Any]]) -> str:
    if not entrees:
        return ENTETE
    return (
        ENTETE + "\n" + yaml.safe_dump(entrees, allow_unicode=True, sort_keys=True, width=LARGEUR)
    )


def _valider_fichier(texte: str) -> None:
    brut = charger_yaml(texte) or {}
    if not isinstance(brut, dict):
        raise ValueError("reformulations.yaml doit être un dictionnaire")
    for cle, entree in brut.items():
        if not isinstance(entree, dict) or entree.get("fact") != cle:
            raise ValueError(f"entrée « {cle} » mal formée")


def deposer(entree: dict[str, Any], chemin: Path | None = None, *, remplacer: bool) -> bool:
    """Écrit l'entrée sous verrou. Vrai si c'est elle qui est désormais en attente pour ce fait.

    `remplacer` : la même ingestion qui repropose (le fichier de l'atelier).
    Sinon, premier arrivé gardé : une entrée d'une AUTRE aide sur le même fait
    reste, et celle-ci n'entre pas ; celle de la même aide est remplacée.
    """
    chemin = chemin or REFORMULATIONS
    cle = entree["fact"]
    gardee = True

    def transformer(texte: str) -> str:
        nonlocal gardee
        entrees = (charger_yaml(texte) or {}) if texte.strip() else {}
        deja = entrees.get(cle)
        if deja is not None and not remplacer and deja.get("slug") != entree.get("slug"):
            gardee = False
            return texte
        entrees[cle] = entree
        return _dump(entrees)

    reecrire_sous_verrou(chemin, transformer, valider=_valider_fichier)
    return gardee


def retirer(cle: str, chemin: Path | None = None) -> None:
    chemin = chemin or REFORMULATIONS

    def transformer(texte: str) -> str:
        entrees = (charger_yaml(texte) or {}) if texte.strip() else {}
        entrees.pop(cle, None)
        return _dump(entrees)

    if chemin.exists():
        reecrire_sous_verrou(chemin, transformer, valider=_valider_fichier)


# ------------------------------------------------------------------ remontée en case


def case(entree: dict[str, Any]) -> Case:
    cle = entree["fact"]
    lignes = [
        f"Proposée par l'ingestion de `{entree.get('slug')}` ({entree.get('jour')}). "
        f"Le fait est cité {entree.get('citations', 0)} fois dans le catalogue.",
        "",
        f"- question actuelle : « {_plat(entree.get('question_origine'))} »",
        f"- question proposée : « {_plat(entree.get('question'))} »",
    ]
    if _plat(entree.get("help")) != _plat(entree.get("help_origine")):
        lignes += [
            f"- aide actuelle : « {_plat(entree.get('help_origine')) or '(aucune)'} »",
            f"- aide proposée : « {_plat(entree.get('help'))} »",
        ]
    lignes += ["", f"Justification de l'agent : {_plat(entree.get('justification'))}"]
    p1 = entree.get("p1") or {}
    lignes.append(
        f"Contrôle du sens (P1) : {p1.get('gates', 0)} gate(s) rejugée(s) avec les deux "
        f"questions, plus forte dérive {float(p1.get('derive', 0.0)):.2f}, aucun désaccord nouveau."
    )
    extrait = list(entree.get("extrait_citations") or [])
    if extrait:
        lignes += ["", "Conditions qui citent le fait :"]
        lignes += [f"- {li}" for li in extrait[:MAX_LIGNES_CITATIONS]]
        if entree.get("citations", 0) > len(extrait[:MAX_LIGNES_CITATIONS]):
            lignes.append(
                f"- … et {entree['citations'] - len(extrait[:MAX_LIGNES_CITATIONS])} autre(s)"
            )
    lignes += [
        "",
        "Une surcharge de ce fait dans `/admin` (`faits_surcharges`), s'il y en a une, masque "
        "la question de `facts.yaml` en production : la réécriture n'y changera rien tant "
        "qu'elle n'est pas rétablie.",
    ]
    return Case(
        SORTE,
        objet(cle),
        f"reformuler la question de `{cle}`",
        etat(entree),
        {
            "appliquer": "réécrire `question` (et `help`) dans `facts.yaml` au prochain run",
            "refuser": "garder la question actuelle",
        },
        tuple(lignes),
    )


def _cite(texte_aide: str, cle: str) -> bool:
    return re.search(rf"^\s*fact:\s*{re.escape(cle)}\s*$", texte_aide, re.MULTILINE) is not None


def remonter(
    slug: str,
    proposees: list[dict[str, Any]],
    texte_aide: str,
    *,
    ecrire: bool,
    chemin: Path | None = None,
) -> tuple[list[Case], list[str]]:
    """(cases, notes) pour les reformulations d'une aide acceptée.

    Une reformulation n'entre que si l'aide écrite cite encore le fait, et si
    le registre garde le réglage `reformulation_fait: case`. À blanc, la case
    se montre sans que rien n'entre au fichier d'attente.
    """
    chemin = chemin or REFORMULATIONS
    from catalogue.registre import reformulation_fait_active

    if not proposees or not reformulation_fait_active():
        return [], []
    cases: list[Case] = []
    notes: list[str] = []
    for entree in proposees:
        cle = entree.get("fact")
        if not cle or entree.get("slug") != slug:
            continue
        if not _cite(texte_aide, cle):
            notes.append(f"reformulation de `{cle}` ignorée : l'aide écrite ne cite plus le fait")
            continue
        if ecrire and not deposer(entree, chemin, remplacer=False):
            notes.append(
                f"reformulation de `{cle}` ignorée : une autre proposition sur ce fait attend Félix"
            )
            continue
        cases.append(case(entree))
    return cases, notes


# ------------------------------------------------------------------ application


def _ligne_cle(ligne: str, champ: str, indent: str) -> bool:
    return re.match(rf"^{re.escape(indent)}{re.escape(champ)}\s*:", ligne) is not None


def _etendue(lignes: list[str], debut: int, fin: int, indent: str, champ: str) -> tuple[int, int]:
    """(début, fin) des lignes du champ `champ` dans le corps [debut, fin) d'un fait, ou (-1, -1)."""
    for i in range(debut, fin):
        if _ligne_cle(lignes[i], champ, indent):
            j = i + 1
            while j < fin and (
                not lignes[j].strip() or len(lignes[j]) - len(lignes[j].lstrip(" ")) > len(indent)
            ):
                j += 1
            while j > i + 1 and not lignes[j - 1].strip():
                j -= 1
            return i, j
    return -1, -1


def _rendre(champ: str, valeur: str, indent: str) -> list[str]:
    """Les lignes d'un scalaire : sur une ligne s'il tient, replié (`>-`) sinon."""
    valeur = _plat(valeur)
    une = yaml.safe_dump({champ: valeur}, allow_unicode=True, width=10**9).rstrip("\n")
    if "\n" not in une and len(indent) + len(une) <= LARGEUR:
        return [f"{indent}{une}\n"]
    corps = textwrap.wrap(
        valeur,
        width=LARGEUR - len(indent) - 2,
        break_long_words=False,
        break_on_hyphens=False,
    )
    return [f"{indent}{champ}: >-\n", *(f"{indent}  {li}\n" for li in corps)]


def reecrire_fait(texte: str, cle: str, question: str, aide: str | None) -> str:
    """`facts.yaml` avec la question (et l'aide, si donnée) du fait `cle` remplacées, texte compris.

    Découpage textuel comme `ingestion.faits._decouper_bloc` : le corps du fait
    est la suite de lignes indentées (ou vides) qui suit sa clé.
    """
    lignes = texte.splitlines(keepends=True)
    entete = re.compile(rf"^{re.escape(cle)}\s*:")
    depart = next((i for i, li in enumerate(lignes) if entete.match(li)), None)
    if depart is None:
        raise ValueError(f"« {cle} » introuvable en tête de ligne dans facts.yaml")
    fin = depart + 1
    while fin < len(lignes) and (lignes[fin][:1] in (" ", "\t") or not lignes[fin].strip()):
        fin += 1
    corps = [li for li in lignes[depart + 1 : fin] if li.strip()]
    if not corps:
        raise ValueError(f"« {cle} » n'a pas de corps")
    indent = corps[0][: len(corps[0]) - len(corps[0].lstrip(" "))]
    q0, q1 = _etendue(lignes, depart + 1, fin, indent, "question")
    if q0 < 0:
        raise ValueError(f"« {cle} » sans `question`")
    nouvelles = _rendre("question", question, indent)
    lignes[q0:q1] = nouvelles
    fin += len(nouvelles) - (q1 - q0)
    if aide is not None:
        h0, h1 = _etendue(lignes, depart + 1, fin, indent, "help")
        rendu = _rendre("help", aide, indent)
        if h0 < 0:
            apres_question = q0 + len(nouvelles)
            lignes[apres_question:apres_question] = rendu
        else:
            lignes[h0:h1] = rendu
    return "".join(lignes)


def _aplatir(faits: dict[str, Any], cle: str) -> dict[str, Any]:
    """Copie où la question et l'aide de `cle` sont mises sur une ligne : le repli ne compte pas."""
    sortie = copy.deepcopy(faits)
    if isinstance(sortie.get(cle), dict):
        for champ in ("question", "help"):
            if champ in sortie[cle]:
                sortie[cle][champ] = _plat(sortie[cle][champ])
    return sortie


def _validateur(cle: str, avant: dict[str, Any], question: str, aide: str | None):
    """Refuse toute écriture où autre chose que `question` / `help` de `cle` aurait bougé."""

    def valider(texte: str) -> None:
        apres = charger_yaml(texte) or {}
        attendu = _aplatir(avant, cle)
        attendu[cle]["question"] = _plat(question)
        if aide is not None:
            attendu[cle]["help"] = _plat(aide)
        obtenu = _aplatir(apres, cle)
        if obtenu != attendu:
            bouges = sorted(
                k for k in set(attendu) | set(obtenu) if attendu.get(k) != obtenu.get(k)
            )
            raise ValueError(f"la réécriture toucherait autre chose que la question : {bouges}")
        FactDef.model_validate(apres[cle])

    return valider


def appliquer_une(
    entree: dict[str, Any], facts_path: Path | None = None, *, ecrire: bool = True
) -> str:
    """`appliquee` ou `perimee` ; n'écrit que si les témoins correspondent encore (et `ecrire`)."""
    facts_path = facts_path or FACTS_FILE
    cle = entree["fact"]
    issue = "perimee"

    def transformer(texte: str) -> str:
        nonlocal issue
        brut = charger_yaml(texte) or {}
        fait = brut.get(cle)
        if (
            not isinstance(fait, dict)
            or _plat(fait.get("question")) != _plat(entree.get("question_origine"))
            or _plat(fait.get("help")) != _plat(entree.get("help_origine"))
        ):
            return texte
        issue = "appliquee"
        if not ecrire:
            return texte
        nouveau = reecrire_fait(texte, cle, entree["question"], entree.get("help"))
        _validateur(cle, brut, entree["question"], entree.get("help"))(nouveau)
        return nouveau

    reecrire_sous_verrou(facts_path, transformer, valider=lambda _texte: None)
    if issue == "appliquee" and ecrire:
        from aides_schema import load_facts

        load_facts.cache_clear()
    return issue


def appliquer(
    vue: Vue,
    *,
    a_blanc: bool = False,
    chemin: Path | None = None,
    facts_path: Path | None = None,
) -> list[str]:
    """Les réponses de Félix aux cases `R-reformulation`, appliquées ; rend les notes du rapport."""
    facts_path = facts_path or FACTS_FILE
    chemin = chemin or REFORMULATIONS
    notes: list[str] = []
    for cle, entree in lire(chemin).items():
        e = vue.felix.get((objet(cle), SORTE))
        if e is None or e.donnees.get("etat") != etat(entree):
            continue
        if e.issue == "refuser":
            notes.append(f"- reformulation de `{cle}` refusée par Félix : la question reste")
        elif e.issue == "appliquer":
            issue = appliquer_une(entree, facts_path, ecrire=not a_blanc)
            notes.append(
                f"- question de `{cle}` réécrite dans `facts.yaml` sur réponse de Félix"
                if issue == "appliquee"
                else f"- reformulation de `{cle}` périmée : la question en place a changé depuis, "
                "rien n'est écrit"
            )
        else:
            continue
        if not a_blanc:
            retirer(cle, chemin)
    return notes


# ------------------------------------------------------------------ lint


def avertissements(facts: dict[str, FactDef], chemin: Path | None = None) -> list[str]:
    """Les entrées en attente dont le fait a disparu ou dont la question a changé depuis."""
    chemin = chemin or REFORMULATIONS
    try:
        entrees = lire(chemin)
    except Exception as exc:  # noqa: BLE001 — un fichier illisible se signale, ne casse pas le lint
        return [f"{chemin.name} illisible : {exc}"]
    sortie = []
    for cle, entree in sorted(entrees.items()):
        fait = facts.get(cle)
        if fait is None:
            sortie.append(
                f"{chemin.name}: `{cle}` n'existe plus dans facts.yaml, l'entrée est à retirer"
            )
        elif _plat(fait.question) != _plat(entree.get("question_origine")) or _plat(
            fait.help
        ) != _plat(entree.get("help_origine")):
            sortie.append(
                f"{chemin.name}: la question de `{cle}` a changé depuis la proposition de "
                f"`{entree.get('slug')}` : entrée périmée, la case ne pourra rien appliquer"
            )
    return sortie


__all__ = [
    "REFORMULATIONS",
    "SORTE",
    "appliquer",
    "appliquer_une",
    "avertissements",
    "case",
    "deposer",
    "etat",
    "lire",
    "objet",
    "reecrire_fait",
    "remonter",
    "retirer",
]
