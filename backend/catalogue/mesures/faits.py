"""Jeux F1 et F2 : le typage des conditions par l'agent d'ingestion (I0, mesure M4).

Commande, depuis backend/ :

    uv run --no-sync python -m catalogue.mesures.faits tirer [--voisinage proches|recherche]

`tirer` réunit la population : les conditions des aides que l'agent d'ingestion
a écrites depuis le 2026-09-23 inclus. Une aide en est si son YAML
`backend/data/aides/<slug>.yaml` est entré dans git à cette date ou après
(`git log --diff-filter=A --no-renames` depuis HEAD, date d'auteur ; le premier
ajout à cette date ou après fait foi) et qu'il existe pour elle un journal
d'ingestion (`data/reviews/logs/ingest-<slug>.log` ou un sous-dossier
`depuis-*` du même dossier) ou une fiche `data/reviews/*-ingest-<slug>.md`.
Chaque condition est lue dans la version du commit qui a introduit l'aide, puis
comparée sur `kind`, `effect` et `fact` à HEAD et à la dernière écriture de
l'agent avant ce commit (dernier `ecrire_aide` réussi de ses journaux) : ce sont
des informations, pas des étiquettes.

Il tire, graine 20261013 :
  - F1, choix du fait : 100 conditions `kind: user_fact`. Pour chacune, le fait
    de l'agent ; s'il était neuf (absent de `facts.yaml` et de
    `facts_pending.yaml` au commit parent de celui qui a introduit l'aide) ;
    s'il figure parmi les faits que les journaux de l'aide disent avoir ajoutés
    (un fait neuf au commit parent a pu être proposé par une autre aide du même
    commit) ; les 20 voisins de la condition dans l'ontologie de ce commit
    parent, et le rang du fait de l'agent parmi eux.
  - F2, nature de la condition : 100 conditions stratifiées sur le verdict de
    l'agent (60 `user_fact` + `gate`, 20 `manual_check`, 20 `info`), avec leur
    probabilité d'inclusion et le titre de l'aide.

Voisinage par défaut (`proches`) : `ingestion.faits._proches`, la similarité
lexicale (maximum de deux `SequenceMatcher`, sur la question et sur la clé) dont
l'agent se voit opposer les faits au-dessus de 0,68 quand il en propose un.
Elle compare un fait à un fait : on l'appelle telle quelle, la condition tenant
lieu de fait (son `text` pour question, une clé vide), sans seuil et pour 20
voisins. `--voisinage recherche` prend à la place le score de
`ingestion.faits.rechercher`, l'outil `chercher_faits` avec lequel l'agent
cherche un fait (mots de la requête retrouvés dans `_texte_indexe`), le texte
de la condition servant de requête ; la boucle de score est reprise ici, la
fonction ne rendant qu'un texte sans scores. Le rappel des deux (le fait de
l'agent est-il parmi les 20 ?) est calculé sur toute la population.

Sortie dans un dossier neuf backend/data/reviews/logs/refonte/<date>-faits-<n>/ :
f1.jsonl, f2.jsonl, population.json (effectifs, rappels, comparaisons) et
consigne-etiquetage.md (définitions citées de TYPING.md et du rapport du
2026-09-23, questions F1 et F2, champs à cacher aux étiqueteurs, cf.
`CHAMPS_AGENT`). Aucun appel réseau ni de modèle ; git n'est que lu.
"""

from __future__ import annotations

import argparse
import datetime as dt
import functools
import inspect
import json
import random
import re
import subprocess
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from ingestion.faits import SEUIL_PROXIMITE, _proches, _texte_indexe, rechercher

from aides_schema import FactDef, charger_yaml
from catalogue.mesures.jeu_e import _dossier_neuf
from catalogue.veille_text import normalize

BACKEND = Path(__file__).resolve().parents[2]
REVIEWS = BACKEND / "data" / "reviews"
LOGS = REVIEWS / "logs"
TYPING = BACKEND / "data" / "TYPING.md"
RAPPORT_TRI = REVIEWS / "2026-09-23-tri-critere-demarche.md"
PREFIXE_AIDES = "backend/data/aides/"

DEBUT = "2026-09-23"
GRAINE = 20261013
TAILLE_F1 = 100
TAILLES_F2 = {"user_fact_gate": 60, "manual_check": 20, "info": 20}
N_VOISINS = 20
ABSENT = f"absent des {N_VOISINS}"

#: Ce que l'agent a écrit, ou ce qui s'en déduit : à cacher aux étiqueteurs.
#: `strate` et `p_inclusion` trahissent le `kind` de F2 ; `condition_id` est
#: nommé par l'agent, souvent d'après son verdict.
CHAMPS_AGENT = (
    "condition_id",
    "kind",
    "effect",
    "predicate",
    "applies_if",
    "levier",
    "derogation_possible",
    "fait_agent",
    "fait_neuf",
    "fait_propose_dans_journal",
    "fait_agent_definition",
    "rang_fait_agent",
    "strate",
    "p_inclusion",
    "head",
    "ecriture_agent",
    "provenance",
)

#: En-tête d'une exécution dans un journal d'ingestion, séparé par des tirets
#: cadratins (U+2014) : « <slug> \u2014 2026-09-29T00:16:10+00:00 \u2014 ingestion ds-v41 / ... ».
ENTETE_EXECUTION = re.compile(
    r"^\S+ \u2014 (\d{4}-\d{2}-\d{2}T[0-9:.]+(?:[+-]\d{2}:\d{2}|Z)?) \u2014 ingestion"
)
#: La sortie de `proposer_fait` quand le fait est écrit dans `facts_pending.yaml`.
PROPOSITION = re.compile(r"^\[sortie\] Fait « ([a-z0-9_]+) » ajouté à")
APPEL_ECRITURE = "[appel] ecrire_aide("
SORTIE_ECRITURE = "[sortie] Écrit :"


# --------------------------------------------------------------------------
# Outils
# --------------------------------------------------------------------------


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-c", "core.quotePath=false", *args],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _git_fichier(rev: str, chemin: str) -> str | None:
    """Le contenu de `chemin` (relatif à la racine du dépôt) à `rev`, ou None s'il n'y est pas."""
    r = subprocess.run(
        ["git", "show", f"{rev}:{chemin}"], cwd=BACKEND, capture_output=True, text=True
    )
    return r.stdout if r.returncode == 0 else None


def _ou(fonction: Callable[..., Any]) -> str:
    """« fichier:ligne » de la définition d'une fonction, relatif à backend/."""
    fichier = Path(inspect.getsourcefile(fonction) or "?").resolve()
    ligne = inspect.getsourcelines(fonction)[1]
    try:
        return f"{fichier.relative_to(BACKEND)}:{ligne}"
    except ValueError:
        return f"{fichier}:{ligne}"


def _kind(c: dict[str, Any]) -> str:
    return c.get("kind") or "untyped"


def _effect(c: dict[str, Any]) -> str:
    """L'`effect` tel que le schéma le lit : `gate` par défaut, `info` pour info et discretionary."""
    return c.get("effect") or ("info" if _kind(c) in ("info", "discretionary") else "gate")


def _triplet(c: dict[str, Any]) -> dict[str, Any]:
    return {"kind": _kind(c), "effect": _effect(c), "fact": c.get("fact")}


def _par_id(aide: dict[str, Any] | None, cid: Any) -> dict[str, Any] | None:
    for c in (aide or {}).get("conditions") or []:
        if isinstance(c, dict) and c.get("id") == cid:
            return c
    return None


def _horodatage(texte: str) -> dt.datetime:
    moment = dt.datetime.fromisoformat(texte)
    return moment if moment.tzinfo else moment.replace(tzinfo=dt.UTC)


# --------------------------------------------------------------------------
# Population
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Ajout:
    commit: str
    date: str
    parent: str | None

    @property
    def moment(self) -> dt.datetime:
        return _horodatage(self.date)


@dataclass
class Journaux:
    """Ce que disent les journaux d'ingestion d'une aide, toutes copies confondues."""

    fichiers: list[Path]
    executions: list[dt.datetime] = field(default_factory=list)
    #: (début de l'exécution, n° de fichier, n° de ligne, YAML écrit) par `ecrire_aide` réussi.
    ecritures: list[tuple[dt.datetime, int, int, dict[str, Any]]] = field(default_factory=list)
    #: (début de l'exécution, clé) par fait que `proposer_fait` a écrit.
    propositions: list[tuple[dt.datetime, str]] = field(default_factory=list)

    def derniere_ecriture(self, avant: dt.datetime) -> dict[str, Any] | None:
        retenues = [e for e in self.ecritures if e[0] <= avant]
        return max(retenues, key=lambda e: e[:3])[3] if retenues else None

    def proposes(self, avant: dt.datetime) -> set[str]:
        return {fait for moment, fait in self.propositions if moment <= avant}


def _lire_journaux(slug: str) -> Journaux:
    candidats = [LOGS / f"ingest-{slug}.log", *sorted(LOGS.glob(f"depuis-*/ingest-{slug}.log"))]
    journaux = Journaux([f for f in candidats if f.is_file()])
    for k, fichier in enumerate(journaux.fichiers):
        lignes = fichier.read_text(encoding="utf-8", errors="replace").splitlines()
        execution: dt.datetime | None = None
        for i, ligne in enumerate(lignes):
            entete = ENTETE_EXECUTION.match(ligne)
            if entete:
                execution = _horodatage(entete.group(1))
                journaux.executions.append(execution)
                continue
            proposition = PROPOSITION.match(ligne)
            if proposition and execution is not None:
                journaux.propositions.append((execution, proposition.group(1)))
                continue
            if (
                execution is None
                or not ligne.startswith(APPEL_ECRITURE)
                or i + 1 >= len(lignes)
                or not lignes[i + 1].startswith(SORTIE_ECRITURE)
            ):
                continue
            try:
                arguments = json.loads(ligne[len(APPEL_ECRITURE) :].removesuffix(")"))
                ecrite = charger_yaml(arguments["yaml_texte"])
            except (ValueError, KeyError, TypeError, yaml.YAMLError):
                continue
            if isinstance(ecrite, dict):
                journaux.ecritures.append((execution, k, i, ecrite))
    return journaux


@dataclass
class AideEcrite:
    slug: str
    ajout: Ajout
    #: Les ajouts du même chemin avant `DEBUT` (aide retirée puis réintroduite).
    anterieurs: list[Ajout]
    titre: str | None
    journaux: Journaux
    fiches: list[Path]
    #: Le dernier YAML que l'agent a écrit avant le commit, et les faits qu'il a proposés.
    ecriture: dict[str, Any] | None
    proposes: set[str]


@dataclass
class ConditionEcrite:
    aide: AideEcrite
    rang: int
    brute: dict[str, Any]

    @property
    def cle(self) -> tuple[str, int]:
        return (self.aide.slug, self.rang)

    @property
    def fait(self) -> str | None:
        return self.brute.get("fact")


def _ajouts() -> dict[str, list[Ajout]]:
    """Chaque fichier ajouté sous data/aides/, avec ses commits d'ajout (du plus récent au plus ancien)."""
    sortie = _git(
        "log",
        "--diff-filter=A",
        "--no-renames",
        "--format=@@%H %aI %P",
        "--name-only",
        "--",
        "data/aides/",
    )
    ajouts: dict[str, list[Ajout]] = {}
    courant: Ajout | None = None
    for ligne in sortie.splitlines():
        if ligne.startswith("@@"):
            commit, date, *parents = ligne[2:].split()
            courant = Ajout(commit, date, parents[0] if parents else None)
        elif ligne.strip() and courant is not None:
            ajouts.setdefault(ligne.strip(), []).append(courant)
    return ajouts


def _population() -> tuple[list[AideEcrite], list[ConditionEcrite], dict[str, Any]]:
    aides: list[AideEcrite] = []
    conditions: list[ConditionEcrite] = []
    sans_trace: list[str] = []
    illisibles: list[str] = []
    fichiers_ajoutes: Counter[str] = Counter()
    for chemin, liste in sorted(_ajouts().items()):
        nom = chemin.removeprefix(PREFIXE_AIDES)
        if not chemin.startswith(PREFIXE_AIDES) or "/" in nom:
            continue
        retenus = sorted((a for a in liste if a.date[:10] >= DEBUT), key=lambda a: a.date)
        if not retenus:
            continue
        if not nom.endswith(".yaml"):
            fichiers_ajoutes[".yaml.echec" if nom.endswith(".yaml.echec") else "autre"] += 1
            continue
        fichiers_ajoutes[".yaml"] += 1
        slug, ajout = nom.removesuffix(".yaml"), retenus[0]
        journaux = _lire_journaux(slug)
        fiches = sorted(REVIEWS.glob(f"*-ingest-{slug}.md"))
        if not journaux.fichiers and not fiches:
            sans_trace.append(slug)
            continue
        texte = _git_fichier(ajout.commit, chemin)
        brut = charger_yaml(texte) if texte else None
        if not isinstance(brut, dict):
            illisibles.append(slug)
            continue
        aide = AideEcrite(
            slug=slug,
            ajout=ajout,
            anterieurs=[a for a in liste if a.date[:10] < DEBUT],
            titre=brut.get("nom"),
            journaux=journaux,
            fiches=fiches,
            ecriture=journaux.derniere_ecriture(ajout.moment),
            proposes=journaux.proposes(ajout.moment),
        )
        aides.append(aide)
        for rang, condition in enumerate(brut.get("conditions") or []):
            if isinstance(condition, dict):
                conditions.append(ConditionEcrite(aide, rang, condition))
    meta = {
        "fichiers_entres_depuis_le_debut": dict(fichiers_ajoutes),
        "note_fichiers": (
            "--no-renames : un renommage compte comme une entrée, si bien que les .yaml.echec "
            "comprennent les aides plus anciennes écartées par renommage de leur .yaml"
        ),
        "exclues_sans_journal_ni_fiche": sans_trace,
        "exclues_illisibles": illisibles,
    }
    return aides, conditions, meta


# --------------------------------------------------------------------------
# Ontologie et voisinage
# --------------------------------------------------------------------------


@functools.cache
def _ontologie(rev: str | None) -> tuple[dict[str, FactDef], dict[str, FactDef]]:
    """`facts.yaml` et `facts_pending.yaml` à une révision ; vides sans révision."""

    def lire(nom: str) -> dict[str, FactDef]:
        texte = _git_fichier(rev, f"backend/data/{nom}") if rev else None
        brut = charger_yaml(texte) if texte else None
        return {cle: FactDef.model_validate(v) for cle, v in (brut or {}).items()}

    return lire("facts.yaml"), lire("facts_pending.yaml")


def _tous(rev: str | None) -> dict[str, FactDef]:
    """L'ontologie que voit l'agent : les faits en attente passent devant, comme dans `proposer`."""
    faits, attente = _ontologie(rev)
    return {**faits, **attente}


@functools.cache
def _index(rev: str | None) -> dict[str, str]:
    return {cle: _texte_indexe(cle, fait) for cle, fait in _tous(rev).items()}


def _voisins_proches(texte: str, rev: str | None) -> list[tuple[float, str]]:
    """`_proches` telle quelle : la condition tient lieu de fait, clé vide, ni seuil ni plafond de 6."""
    cible = FactDef(type="boolean", scope="projet", question=texte)
    return _proches("", cible, _tous(rev), seuil=0.0, limite=N_VOISINS)


def _voisins_recherche(texte: str, rev: str | None) -> list[tuple[float, str]]:
    """Le score de `rechercher`, le texte de la condition pour requête.

    Reprise de sa boucle (jetons normalisés, underscores aplatis, un point par
    jeton retrouvé dans `_texte_indexe`, tri par score décroissant puis par clé) :
    la fonction ne rend que le texte affiché à l'agent, sans scores.
    """
    jetons = [t for t in normalize(texte.replace("_", " ")).split() if t]
    scores = [
        (float(sum(1 for t in jetons if t in indexe)), cle) for cle, indexe in _index(rev).items()
    ]
    scores = [s for s in scores if s[0]]
    scores.sort(key=lambda s: (-s[0], s[1]))
    return scores[:N_VOISINS]


VOISINAGES: dict[str, Callable[[str, str | None], list[tuple[float, str]]]] = {
    "proches": _voisins_proches,
    "recherche": _voisins_recherche,
}


def _definition(cle: str, fait: FactDef) -> dict[str, Any]:
    return {
        "cle": cle,
        "question": " ".join(fait.question.split()),
        "type": fait.type,
        "scope": fait.scope,
        "unit": fait.unit,
        "options": [{"id": o.id, "label": o.label} for o in fait.options or []],
    }


def _neuf(c: ConditionEcrite) -> bool:
    return bool(c.fait) and c.fait not in _tous(c.aide.ajout.parent)


def _rappel(
    conditions: list[ConditionEcrite], voisins: dict[tuple[str, int], list[tuple[float, str]]]
) -> dict[str, Any]:
    dedans = [c for c in conditions if c.fait in {cle for _, cle in voisins[c.cle]}]
    existants = [c for c in conditions if not _neuf(c)]
    return {
        "conditions": len(conditions),
        "fait_agent_parmi_les_20": len(dedans),
        "part": round(len(dedans) / len(conditions), 4) if conditions else None,
        "conditions_a_fait_existant": len(existants),
        "part_parmi_faits_existants": round(len(dedans) / len(existants), 4) if existants else None,
        "au_rang_1": sum(1 for c in dedans if voisins[c.cle][0][1] == c.fait),
    }


# --------------------------------------------------------------------------
# Lignes
# --------------------------------------------------------------------------


def _fait_agent(c: ConditionEcrite) -> dict[str, Any]:
    if not c.fait:
        return {
            "fait_agent": None,
            "fait_neuf": None,
            "fait_propose_dans_journal": None,
            "fait_agent_definition": None,
        }
    neuf = _neuf(c)
    origine, ontologie = (
        ("commit_ajout", _tous(c.aide.ajout.commit))
        if neuf
        else ("commit_parent", _tous(c.aide.ajout.parent))
    )
    fait = ontologie.get(c.fait)
    return {
        "fait_agent": c.fait,
        "fait_neuf": neuf,
        "fait_propose_dans_journal": c.fait in c.aide.proposes,
        "fait_agent_definition": (
            {**_definition(c.fait, fait), "origine": origine}
            if fait
            else {"origine": "introuvable"}
        ),
    }


@functools.cache
def _aide_head(slug: str) -> dict[str, Any] | None:
    texte = _git_fichier("HEAD", f"{PREFIXE_AIDES}{slug}.yaml")
    brut = charger_yaml(texte) if texte else None
    return brut if isinstance(brut, dict) else None


def _etat_head(c: ConditionEcrite) -> dict[str, Any]:
    aide = _aide_head(c.aide.slug)
    if aide is None:
        return {"etat": "aide_absente"}
    autre = _par_id(aide, c.brute.get("id"))
    if autre is None:
        return {"etat": "condition_absente"}
    avant, apres = _triplet(c.brute), _triplet(autre)
    changements = [k for k in avant if avant[k] != apres[k]]
    return {"etat": "modifiee" if changements else "identique", "changements": changements, **apres}


def _etat_ecriture(c: ConditionEcrite) -> dict[str, Any]:
    if c.aide.ecriture is None:
        return {"etat": "sans_ecriture"}
    autre = _par_id(c.aide.ecriture, c.brute.get("id"))
    if autre is None:
        return {"etat": "absente"}
    agent, commit = _triplet(autre), _triplet(c.brute)
    changements = [k for k in agent if agent[k] != commit[k]]
    return {
        "etat": "differente" if changements else "identique",
        "changements": changements,
        **agent,
    }


def _ligne(ident: str, c: ConditionEcrite) -> dict[str, Any]:
    b = c.brute
    return {
        "id": ident,
        "slug": c.aide.slug,
        "titre_aide": c.aide.titre,
        "condition_id": b.get("id"),
        "text": b.get("text"),
        "quote": b.get("quote"),
        "kind": _kind(b),
        "effect": _effect(b),
        "predicate": b.get("predicate"),
        "applies_if": b.get("applies_if"),
        "levier": b.get("levier"),
        "derogation_possible": bool(b.get("derogation_possible", False)),
        **_fait_agent(c),
    }


def _suite(c: ConditionEcrite, p: float, etat_head: dict[str, Any]) -> dict[str, Any]:
    return {
        "p_inclusion": round(p, 6),
        "head": etat_head,
        "ecriture_agent": _etat_ecriture(c),
        "provenance": {
            "commit": c.aide.ajout.commit,
            "date": c.aide.ajout.date,
            "parent": c.aide.ajout.parent,
            "rang_dans_l_aide": c.rang,
            "ajouts_anterieurs": [a.commit for a in c.aide.anterieurs],
            "journaux": [str(f.relative_to(BACKEND)) for f in c.aide.journaux.fichiers],
            "fiches": [f.name for f in c.aide.fiches],
        },
    }


# --------------------------------------------------------------------------
# Consigne
# --------------------------------------------------------------------------


def _citer(chemin: Path, debut: str, fin: str | None) -> str:
    """De la ligne qui commence par `debut` à celle, exclue, qui commence par `fin`, mot pour mot."""
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    try:
        i = next(k for k, li in enumerate(lignes) if li.startswith(debut))
        j = (
            len(lignes)
            if fin is None
            else next(k for k in range(i + 1, len(lignes)) if lignes[k].startswith(fin))
        )
    except StopIteration as exc:
        raise ValueError(f"{chemin.name} : ancre introuvable ({debut!r} / {fin!r})") from exc
    passage = lignes[i:j]
    while passage and not passage[-1].strip():
        passage.pop()
    source = f"`{chemin.relative_to(BACKEND.parent)}`, lignes {i + 1} à {i + len(passage)}"
    corps = "\n".join(f"> {li}" if li.strip() else ">" for li in passage)
    return f"{source} :\n\n{corps}"


def _consigne(date: str, voisinage: str) -> str:
    typing_ = [
        (
            "### 1. Ce n'est pas une condition d'éligibilité",
            "**L'arbre de décision, dans cet ordre",
        ),
        ("**L'arbre de décision, dans cet ordre", "Ce quatrième cas était fermé"),
        ("### Avant de poser une question : critère ou démarche ?", "### 4. Vérifiable par"),
        ("### 4. Vérifiable par une réponse du propriétaire", "**Une énumération de bénéficiaires"),
        ("**Une énumération de bénéficiaires", "C'était l'inverse jusqu'au 2026-09-21"),
        ("- **Jamais de seuil chiffré dans la clé", "- **Une question est UNE phrase**"),
        ("**Implantation du porteur**", "**Bruit à ne pas transcrire**"),
        ("### Le quasi-doublon, et comment on s'en défend", "Aucun seuil de similarité ne sépare"),
    ]
    info, arbre, critere, user_fact, porteur, seuil, implantation, doublon = (
        _citer(TYPING, d, f) for d, f in typing_
    )
    regle = _citer(RAPPORT_TRI, "## La règle", "## Les chiffres")
    arbitrages = _citer(RAPPORT_TRI, "## Arbitrages du 2026-09-23", None)
    fonction = (
        f"`ingestion.faits._proches` ({_ou(_proches)})"
        if voisinage == "proches"
        else f"le score de `ingestion.faits.rechercher` ({_ou(rechercher)})"
    )
    cache = ", ".join(f"`{c}`" for c in CHAMPS_AGENT)
    return f"""# Consigne d'étiquetage, mesure M4 (F1 et F2)

Jeux tirés le {date} par `uv run --no-sync python -m catalogue.mesures.faits tirer`
(graine {GRAINE}) : `f1.jsonl` (choix du fait) et `f2.jsonl` (nature de la condition).
Chaque ligne est une condition d'une aide du catalogue : son texte (`text`), la citation
de la source (`quote`) et le titre de l'aide (`titre_aide`). L'étiquetage se fait à
l'aveugle : les champs qui disent ce qu'a fait l'agent d'ingestion ne se montrent pas
(liste en fin de document).

Les définitions et les règles ci-dessous sont citées mot pour mot ; la source et les
lignes précèdent chaque citation.

## F2 : critère, démarche ou promesse

Question : cette condition est-elle un critère, une démarche ou une promesse ?

### Les trois définitions (TYPING.md)

{critere}

### La règle du tri du 2026-09-23 (rapport)

{regle}

### Les arbitrages de Félix (fin du rapport)

{arbitrages}

### Ce qui n'est pas une condition d'éligibilité (TYPING.md)

Certaines conditions ne posent aucune exigence au propriétaire (paramètres financiers,
modalités, formalités). TYPING.md les décrit ainsi :

{info}

## F1 : choix du fait

Question : parmi ces faits, lequel pose la question que cette condition pose au
propriétaire, ou aucun ?

« Ces faits » sont les {N_VOISINS} faits de `voisins` (clé, question, type, portée,
unité, options), pris dans l'ontologie (`facts.yaml` et `facts_pending.yaml`) du commit
qui précède l'écriture de l'aide, et rangés par score lexical décroissant ({fonction}) :
le rang n'est pas un avis sur la pertinence.

Règles de TYPING.md sur la réutilisation d'un fait :

### L'ordre de l'arbre de décision

{arbre}

### Réutiliser un fait existant

{user_fact}

### Les bénéficiaires et le porteur

{porteur}

### L'implantation du porteur

{implantation}

### Le seuil appartient au prédicat

{seuil}

### Quand deux faits sont le même fait

{doublon}

## Champs à ne pas montrer aux étiqueteurs

{cache}.

Restent visibles : `id`, `slug`, `titre_aide`, `text`, `quote` et, pour F1, `voisins`.
"""


# --------------------------------------------------------------------------
# tirer
# --------------------------------------------------------------------------


def tirer(args: argparse.Namespace) -> int:
    aides, conditions, meta_population = _population()
    user_fact = [c for c in conditions if _kind(c.brute) == "user_fact"]
    strates = {
        "user_fact_gate": [c for c in user_fact if _effect(c.brute) == "gate"],
        "manual_check": [c for c in conditions if _kind(c.brute) == "manual_check"],
        "info": [c for c in conditions if _kind(c.brute) == "info"],
    }
    # Les voisins de toute la population user_fact, pour les deux voisinages :
    # le rappel se lit sur la population, l'échantillon n'en garde qu'un.
    voisins = {
        nom: {c.cle: fonction(c.brute.get("text") or "", c.aide.ajout.parent) for c in user_fact}
        for nom, fonction in VOISINAGES.items()
    }

    rng = random.Random(GRAINE)
    n_f1 = min(TAILLE_F1, len(user_fact))
    f1 = rng.sample(user_fact, n_f1)
    f2: list[tuple[str, ConditionEcrite, float]] = []
    for strate, membres in strates.items():
        n = min(TAILLES_F2[strate], len(membres))
        f2.extend((strate, c, n / len(membres)) for c in rng.sample(membres, n))
    rng.shuffle(f2)

    etats_head = {c.cle: _etat_head(c) for c in conditions}
    dossier = _dossier_neuf("faits")
    retenu = voisins[args.voisinage]
    with (dossier / "f1.jsonl").open("w", encoding="utf-8") as f:
        for i, c in enumerate(f1, 1):
            tous = _tous(c.aide.ajout.parent)
            liste = retenu[c.cle]
            cles = [cle for _, cle in liste]
            ligne = {
                **_ligne(f"f1-{i:03d}", c),
                "rang_fait_agent": cles.index(c.fait) + 1 if c.fait in cles else ABSENT,
                "voisins": [
                    {"rang": k, **_definition(cle, tous[cle]), "score": round(score, 4)}
                    for k, (score, cle) in enumerate(liste, 1)
                ],
                **_suite(c, n_f1 / len(user_fact), etats_head[c.cle]),
            }
            f.write(json.dumps(ligne, ensure_ascii=False, default=str) + "\n")
    with (dossier / "f2.jsonl").open("w", encoding="utf-8") as f:
        for i, (strate, c, p) in enumerate(f2, 1):
            ligne = {
                **_ligne(f"f2-{i:03d}", c),
                "strate": strate,
                **_suite(c, p, etats_head[c.cle]),
            }
            f.write(json.dumps(ligne, ensure_ascii=False, default=str) + "\n")

    neufs = [c for c in user_fact if _neuf(c)]
    commits = Counter(a.ajout.commit for a in aides)
    meta: dict[str, Any] = {
        "graine": GRAINE,
        "debut": DEBUT,
        "revision_head": _git("rev-parse", "HEAD").strip(),
        "aides": {
            "population": len(aides),
            "par_commit": {
                commit: {
                    "date": next(a.ajout.date for a in aides if a.ajout.commit == commit),
                    "parent": next(a.ajout.parent for a in aides if a.ajout.commit == commit),
                    "aides": n,
                }
                for commit, n in sorted(commits.items())
            },
            "traces": dict(
                Counter(
                    "journal_et_fiche"
                    if a.journaux.fichiers and a.fiches
                    else "journal_seul"
                    if a.journaux.fichiers
                    else "fiche_seule"
                    for a in aides
                )
            ),
            "reintroduites": [a.slug for a in aides if a.anterieurs],
            **meta_population,
        },
        "conditions": {
            "total": len(conditions),
            "par_kind_effect": dict(
                Counter(f"{_kind(c.brute)}/{_effect(c.brute)}" for c in conditions).most_common()
            ),
        },
        "f1": {
            "population": len(user_fact),
            "tirage": n_f1,
            "p_inclusion": round(n_f1 / len(user_fact), 6) if user_fact else None,
            "faits_neufs": sum(1 for c in f1 if _neuf(c)),
        },
        "f2": {
            strate: {
                "population": len(membres),
                "tirage": min(TAILLES_F2[strate], len(membres)),
                "p_inclusion": round(min(TAILLES_F2[strate], len(membres)) / len(membres), 6)
                if membres
                else None,
            }
            for strate, membres in strates.items()
        },
        "recouvrement_f1_f2": len({c.cle for c in f1} & {c.cle for _, c, _ in f2}),
        "voisinage": {
            "retenu": args.voisinage,
            "proches": {
                "fonction": f"ingestion.faits._proches ({_ou(_proches)})",
                "appel": (
                    "_proches('', FactDef(type='boolean', scope='projet', question=<text>), "
                    f"facts + facts_pending du commit parent, seuil=0.0, limite={N_VOISINS})"
                ),
                "seuil_en_production": SEUIL_PROXIMITE,
            },
            "recherche": {
                "fonction": (
                    f"score de ingestion.faits.rechercher ({_ou(rechercher)}), "
                    f"index _texte_indexe ({_ou(_texte_indexe)})"
                ),
                "appel": "requête = <text> ; un point par jeton normalisé retrouvé dans l'index",
            },
            "rappel_population": {nom: _rappel(user_fact, v) for nom, v in voisins.items()},
            "rappel_f1": {nom: _rappel(f1, v) for nom, v in voisins.items()},
        },
        "faits_neufs_population": {
            "conditions": len(neufs),
            "faits_distincts": len({c.fait for c in neufs}),
            "conditions_dont_le_journal_propose_le_fait": sum(
                1 for c in neufs if c.fait in c.aide.proposes
            ),
            "definition_introuvable_au_commit_d_ajout": sorted(
                {str(c.fait) for c in neufs if c.fait not in _tous(c.aide.ajout.commit)}
            ),
        },
        "head": {
            "etats": dict(Counter(e["etat"] for e in etats_head.values())),
            "changements": dict(
                Counter(k for e in etats_head.values() for k in e.get("changements", []))
            ),
        },
        "ecriture_agent": dict(Counter(_etat_ecriture(c)["etat"] for c in conditions)),
    }
    (dossier / "population.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    (dossier / "consigne-etiquetage.md").write_text(
        _consigne(dt.date.today().isoformat(), args.voisinage), encoding="utf-8"
    )

    print(dossier)
    resume = {
        "aides": len(aides),
        "conditions": len(conditions),
        "user_fact": len(user_fact),
        "f1": n_f1,
        "f2": {s: meta["f2"][s]["tirage"] for s in strates},
        "rappel_f1": {
            nom: f"{r['fait_agent_parmi_les_20']}/{r['conditions']}"
            for nom, r in meta["voisinage"]["rappel_f1"].items()
        },
        "rappel_population": {
            nom: f"{r['fait_agent_parmi_les_20']}/{r['conditions']}"
            for nom, r in meta["voisinage"]["rappel_population"].items()
        },
        "faits_neufs_f1": meta["f1"]["faits_neufs"],
    }
    print(json.dumps(resume, ensure_ascii=False))
    return 0


def main() -> int:
    parseur = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sous = parseur.add_subparsers(dest="commande", required=True)
    p = sous.add_parser("tirer")
    p.add_argument("--voisinage", choices=tuple(VOISINAGES), default="proches")
    p.set_defaults(fonction=tirer)
    args = parseur.parse_args()
    return args.fonction(args)


if __name__ == "__main__":
    raise SystemExit(main())
