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

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.verrou import ajouter_sous_verrou, reecrire_sous_verrou
from veille_text import normalize

from aides_schema import FAIT_PORTEUR, FactDef, load_pending_facts

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
    for _score, cle in resultats[:limite]:
        fait = tous[cle]
        marque = " ⏳ (proposé, non approuvé)" if cle in pending else ""
        options = ""
        if fait.options:
            options = "  [" + ", ".join(o.id for o in fait.options) + "]"
        lignes.append(
            f"  {cle}  {fait.type}  {fait.scope}  "
            f"« {' '.join(fait.question.split())} »{options}{marque}"
        )
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
        avertissement += (
            f"\n⚠ RÉSERVÉ AUX PORTEURS : {', '.join(fait.porteurs_concernes)}. Si tu gates sur "
            f"ce fait, l'aide DOIT aussi gater `{FAIT_PORTEUR}` (gate `in` traduisant la puce "
            "« Bénéficiaires » de la source) — le lint le refuse sinon. Sans ce gate, l'aide "
            "pose sa question d'entreprise à toutes les communes (TYPING § bénéficiaires).\n"
        )
    return f"{entete}\n{corps}{avertissement}"


# ---------------------------------------------------------------------------
# Proposition
# ---------------------------------------------------------------------------


def _bloc(slug: str, fact_id: str, definition: dict, justification: str, jour: date) -> str:
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
        f"{justif}\n"
        f"{corps}"
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


def _message_proximite(proches: list[tuple[float, str]], tous: dict[str, FactDef]) -> str:
    """L'erreur qui ORIENTE : les faits proches, leur question, et quoi en faire."""
    lignes = [
        f"ERREUR : {len(proches)} fait(s) de l'ontologie ressemblent à celui que tu proposes. "
        "Relis-les, puis soit tu en réutilises un (le prédicat porte le seuil, pas le fait), "
        "soit tu reproposes en CITANT chaque clé ci-dessous dans ta justification et en "
        "disant ce qui la disqualifie :",
    ]
    for score, cle in proches:
        fait = tous[cle]
        options = "  [" + ", ".join(o.id for o in fait.options) + "]" if fait.options else ""
        lignes.append(
            f"  {cle}  ({score:.0%})  {fait.type}  {fait.scope}  "
            f"« {' '.join(fait.question.split())} »{options}"
        )
    lignes.append(
        "`detail_fait <clé>` pour la définition complète. Un fait légitimement voisin "
        "n'est PAS refusé : il suffit de le nommer et d'expliquer l'écart."
    )
    return "\n".join(lignes)


def _validateur(fact_id: str, facts: dict[str, FactDef]):
    """Refuse d'écrire un `facts_pending.yaml` que le lint ne pourrait pas lire.

    La validation porte sur le fichier COMPLET tel qu'il serait écrit : c'est
    la seule façon de voir une collision avec une entrée qu'un autre worker
    vient d'ajouter sous le même verrou.
    """

    def valider(texte: str) -> None:
        brut = yaml.safe_load(texte) or {}
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


def proposer(
    atelier: Atelier,
    facts: dict[str, FactDef],
    fact_id: str,
    definition_yaml: str,
    justification: str,
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

    try:
        brut = yaml.safe_load(definition_yaml)
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

    proches = _proches(fact_id, fait, {**facts, **pending})
    non_cites = [(s, c) for s, c in proches if c not in justification]
    if non_cites:
        return _message_proximite(proches, {**facts, **pending})

    definition = fait.model_dump(exclude_none=True, exclude_defaults=True)
    bloc = _bloc(atelier.slug, fact_id, definition, justification, atelier.jour)
    try:
        ajouter_sous_verrou(atelier.pending_path, bloc, valider=_validateur(fact_id, facts))
    except Exception as exc:
        return f"ERREUR : écriture refusée dans facts_pending.yaml — {exc}"
    # Le lint que l'agent lancera juste après doit voir le fait : sans purge,
    # il se ferait refuser sa propre proposition (`fait inconnu`).
    load_pending_facts.cache_clear()
    return (
        f"Fait « {fact_id} » ajouté à {atelier.relatif(atelier.pending_path)} "
        "(en attente d'approbation humaine). Tu peux le référencer dès maintenant "
        "dans une condition `kind: user_fact`, et le signaler dans la review."
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
        brut = yaml.safe_load(texte) or {}
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
