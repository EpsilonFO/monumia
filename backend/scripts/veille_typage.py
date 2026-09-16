"""
Typage automatique des conditions `untyped` laissées par l'audit.

    cd backend && uv run python scripts/veille_typage.py <slug> [<slug>...] --dry-run
    cd backend && uv run python scripts/veille_typage.py <slug>
    cd backend && uv run python scripts/veille_audit.py <slug> --force --typer

Pourquoi cet étage existe. Une condition `untyped` n'est PAS inerte : le moteur
déterministe ne traite que les aides à zéro `untyped` (`aides_engine_ready` dans
`eligibility_engine.py`). Une condition ajoutée par l'audit sort donc l'aide
entière du diagnostic — le parc était à 140/141 engine-ready, et la première
écriture réelle de l'audit en a fait tomber une. Améliorer la fidélité d'une
fiche en la retirant du moteur est un mauvais échange : ce module referme la
plaie dans la foulée.

Ce qu'il fait. Un appel structuré par aide : le modèle voit les conditions
`untyped`, un index compact de l'ontologie, et l'arbre de décision de
`data/TYPING.md`. Il rend un typage par condition, et propose au besoin des
faits nouveaux. Un appel, jamais de boucle agentique, comme partout ailleurs
dans la veille.

Ce qu'il ne fait JAMAIS :
  - écrire dans `data/facts.yaml` — un fait nouveau se propose dans
    `facts_pending.yaml`, l'humain le promeut, et le commit vaut validation
    (règle du dépôt, cf. CLAUDE.md et TYPING.md) ;
  - toucher au `text` ni à la `quote` d'une condition — le typage porte sur la
    forme, jamais sur le fond ;
  - produire un `manual_check` + `effect: gate` — le pire typage possible :
    le moteur rend None sans poser de question, et l'aide ne peut alors
    STRUCTURELLEMENT jamais sortir « éligible » (TYPING.md, objectif zéro).

Ce qu'il PEUT faire, sur décision explicite du propriétaire du dépôt : poser un
`gate`, y compris sur un fait qu'il vient de proposer. C'est le point sensible
du dispositif — un gate mal posé élimine silencieusement des monuments d'une
aide à laquelle ils ont droit, et l'audit qui produit ces conditions n'est pas
déterministe. Deux garde-fous, et pas un de plus : le prédicat est validé par
les MÊMES fonctions que `lint_aides_data.py` (opérateurs autorisés par type,
valeurs dans les options), et le `git diff` est relu avant commit.

Codes de sortie : 0 terminé ; 1 erreur fatale ; 2 au moins un échec de typage.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aides_schema import (
    AIDES_DIR,
    FACTS_PENDING_FILE,
    FIELD_REGISTRY,
    Aide,
    FactDef,
    Predicate,
    load_aide,
    load_facts,
    load_pending_facts,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lint_aides_data import check_fact_predicate, check_field_predicate
from pipeline.verrou import ajouter_sous_verrou
from veille_apply import (
    CHAMPS_TYPAGE,
    ChangementCondition,
    VeilleLLMOutput,
    appliquer,
    parse_json_output,
)
from veille_journal import Journal, cellule, milliers, tokens_compacts
from veille_llm import MODELE_DEFAUT, ModelSpec, call, json_schema, resoudre_modele, system_pour
from veille_update import prompt_correction

MAX_LLM_DEFAUT = 20

Etat = Literal["type", "rien_a_faire", "echec"]

SYMBOLES: dict[str, str] = {"type": "→", "rien_a_faire": "=", "echec": "!"}


# ---------------------------------------------------------------------------
# Schéma de sortie
# ---------------------------------------------------------------------------


class OptionFait(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    label: str
    # « Pas encore décidé » est une vraie réponse : le moteur traite alors le
    # fait comme inconnu, ce qui produit une incertitude au lieu d'éliminer.
    unknown: bool = False


class NouveauFait(BaseModel):
    """Fait proposé pour `facts_pending.yaml`. JAMAIS écrit dans `facts.yaml`."""

    model_config = ConfigDict(extra="forbid")

    cle: str = Field(pattern=r"^[a-z0-9_]+$")
    type: Literal["boolean", "integer", "number", "enum", "multi_enum"]
    scope: Literal["monument", "projet", "proprietaire"]
    question: str
    options: list[OptionFait] | None = None
    unit: str | None = None
    help: str | None = None

    def to_factdef(self) -> dict[str, Any]:
        brut: dict[str, Any] = {
            "type": self.type,
            "scope": self.scope,
            "question": self.question,
        }
        if self.options:
            brut["options"] = [o.model_dump(exclude_defaults=True) for o in self.options]
        if self.unit:
            brut["unit"] = self.unit
        if self.help:
            brut["help"] = self.help
        return brut


class TypageCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["info", "auto", "discretionary", "user_fact", "manual_check"]
    effect: Literal["gate", "info", "modulateur"]
    fact: str | None = None
    field: str | None = None
    predicate: dict[str, Any] | None = None
    # Justification du typage. Obligatoire sur `manual_check` (TYPING.md), et
    # c'est là que se pose le « ⚠ À TRANCHER » d'une hésitation réelle.
    notes: str | None = None


class TypageLLMOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str | None = None
    resume: str = ""
    conditions: list[TypageCondition] = []
    nouveaux_faits: list[NouveauFait] = []


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_TYPAGE = """Tu types des conditions d'éligibilité d'aides au patrimoine, pour qu'un moteur déterministe puisse les évaluer.

Tu ne rends QUE du JSON conforme au schéma. Aucun texte autour.

Tu ne touches NI au `text` NI à la `quote` d'une condition : ils viennent de la source et ne se reformulent jamais. Ton travail porte sur la forme — `kind`, `effect`, `fact`/`field`, `predicate` — pas sur le fond.

APPLIQUE CET ARBRE DANS L'ORDRE. Le premier cas qui s'applique gagne.

1. Ce n'est pas une condition d'éligibilité → `kind: "info"`, `effect: "info"`.
   Modalités de dépôt et de versement, pièces du dossier, avis et échanges préalables, obligations légales générales du droit français (autorisation d'urbanisme, accord ABF, normes ERP, régularité fiscale et sociale), formalités, non-récurrences, non-cumuls, redondances avec le périmètre de l'aide, engagements à la main du porteur (communication, accessibilité, restitution), labels à obtenir APRÈS travaux, bénéficiaires très larges déjà couverts par le périmètre.

2. Décidable sur les données structurées → `kind: "auto"`, `field` du registre fourni + `predicate`.

3. Appréciation du financeur → `kind: "discretionary"`, `effect: "info"` (ou `"modulateur"` si ça joue sur le taux).
   « intérêt patrimonial », « qualité du projet », « pertinence », « au cas par cas », « à titre exceptionnel », jurys et comités.

4. Vérifiable par une réponse du propriétaire → `kind: "user_fact"`, `fact` + `predicate`.
   CHERCHE D'ABORD UN FAIT EXISTANT dans l'index fourni : la valeur de l'ontologie est la déduplication. Reformule la condition en question — si une question existante y répond, c'est le bon fait. Ne propose un fait nouveau que si AUCUN existant ne convient.
   Le prédicat encode le seuil de CETTE aide, pas une généralité.
   Engagement futur (« s'engager à… ») → fait de volonté `s_engage_*`, une intention déclarée suffit.
   Gate de scope sur un enum : sois STRICT sur l'option dédiée, jamais large. Un prédicat trop large valide à tort des profils hors-scope, ce qui est pire que d'éliminer un cas limite.

5. Vraie condition, mais invérifiable proprement → `kind: "manual_check"`, `effect: "info"`, `notes` OBLIGATOIRE disant pourquoi c'est irréductible.
   Matrices par catégorie, périmètres contractuels ou cartographiques, accords de tiers, ratios comptables du porteur, conditions jamais strictement dirimantes.

RÈGLE ABSOLUE : jamais `kind: "manual_check"` avec `effect: "gate"`. C'est le pire typage possible — le moteur rend « inconnu » sans poser aucune question, et l'aide ne peut alors JAMAIS sortir « éligible ». Avant d'y songer, épuise dans l'ordre : fait existant, fait nouveau, `discretionary`, `info`, puis `manual_check` + `info`.

`effect` :
- `gate` : condition non satisfaite ⇒ aide refusée. Réservé à `auto`, `user_fact`, et jamais à `manual_check`.
- `modulateur` : joue sur le taux ou le montant, jamais sur l'éligibilité.
- `info` : aucune incidence. OBLIGATOIRE avec `kind: "info"`, et le seul choix raisonnable avec `discretionary` hors modulateur.

Un `gate` élimine des monuments d'une aide. N'en pose un que si la condition est réellement dirimante et que ton prédicat traduit exactement le seuil cité. Dans le doute, `effect: "info"`.

Faits nouveaux (`nouveaux_faits`) :
- Préfère MESURABLE à binaire quand les seuils varient d'une aide à l'autre : `jours_ouverture_public_par_an` en integer répond à tous les seuils, `ouvert_au_public` en boolean à un seul.
- `scope` juste : `monument` (durable), `projet` (ce chantier), `proprietaire` (la personne).
- Question compréhensible par un non-expert. Options d'enum exhaustives et mutuellement exclusives, avec une option `unknown: true` quand « pas encore décidé » est une vraie réponse.
- Conventions : `s_engage_*` (volonté), `*_pct`, `*_ans`, `*_par_an` (unités).

Renseigne `notes` dès que le typage n'est pas évident, en une phrase. Si tu hésites réellement entre deux typages, fais quand même la meilleure proposition et préfixe la note par « ⚠ À TRANCHER : » suivi de la question.

Renseigne TOUJOURS `resume` : une phrase sur ce que tu as typé et les points à relire. C'est ce que lira l'humain chargé de relire ton diff.

Types TOUTES les conditions qu'on te donne, sans exception : une seule laissée de côté garde l'aide entière hors du moteur."""


def index_faits(facts: dict[str, FactDef]) -> str:
    """Index compact de l'ontologie : de quoi NOMMER le bon fait, pas plus.

    `facts.yaml` pèse 92 Ko (~25k tokens) : l'envoyer entier à chaque appel
    serait du gaspillage, et l'essentiel de son volume (`levier`, `help`,
    commentaires) ne sert pas au rattachement. Le prédicat proposé contre le
    fait retenu est de toute façon revalidé EN LOCAL contre la vraie
    définition, par les fonctions du linter — une option inventée est donc
    attrapée sans que le modèle ait eu à lire les options.
    """
    lignes: list[str] = []
    for cle, f in sorted(facts.items()):
        bout = f"{cle} ({f.type}, {f.scope})"
        if f.unit:
            bout += f" [{f.unit}]"
        bout += f" — {f.question}"
        if f.options:
            bout += "  options: " + ", ".join(o.id for o in f.options)
        lignes.append(bout)
    return "\n".join(lignes)


def index_champs() -> str:
    lignes: list[str] = []
    for nom, spec in sorted(FIELD_REGISTRY.items()):
        bout = f"{nom} ({spec['type']})"
        if valeurs := spec.get("values"):
            bout += "  valeurs: " + ", ".join(sorted(valeurs))
        lignes.append(bout)
    return "\n".join(lignes)


def build_prompt_typage(
    aide: Aide, conditions: list[Any], facts: dict[str, FactDef], *, aujourd_hui: date
) -> str:
    a_typer = [
        {
            k: v
            for k, v in c.model_dump(mode="json").items()
            if k in ("id", "text", "quote", "notes") and v is not None
        }
        for c in conditions
    ]
    # Les conditions DÉJÀ typées de la même fiche servent de gabarit : elles
    # montrent les faits que cette aide mobilise déjà et le grain de typage
    # retenu par les humains qui l'ont écrite.
    deja = [
        {
            k: v
            for k, v in c.model_dump(mode="json").items()
            if k in ("id", "text", "kind", "effect", "fact", "field", "predicate") and v is not None
        }
        for c in aide.conditions
        if c.kind != "untyped"
    ]

    return "\n".join(
        [
            f"Date du jour : {aujourd_hui.isoformat()}",
            "",
            f"## Aide `{aide.slug}` — {aide.nom} ({aide.organisme})",
            "",
            aide.description,
            "",
            "## Conditions À TYPER",
            "```json",
            json.dumps(a_typer, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Conditions déjà typées de la même fiche (gabarit)",
            "",
            "Elles montrent les faits que cette aide mobilise déjà et le grain de "
            "typage retenu. Réutilise les mêmes faits quand la condition à typer "
            "porte sur la même chose.",
            "```json",
            json.dumps(deja, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Ontologie des faits existants (`kind: user_fact`)",
            "",
            "Cherche ici AVANT de proposer un fait nouveau.",
            "```",
            index_faits(facts),
            "```",
            "",
            "## Champs structurés disponibles (`kind: auto`)",
            "```",
            index_champs(),
            "```",
            "",
            f"Type les {len(a_typer)} condition(s) ci-dessus pour `{aide.slug}`. "
            "Rends une entrée par condition, aucune de moins.",
        ]
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

Etape = Literal["json", "schema", "referentiel", "predicat", "fait"]


def check_referentiel_typage(
    out: TypageLLMOutput, aide: Aide, attendus: set[str], facts: dict[str, FactDef]
) -> list[str]:
    """Cohérence kind/effect/fact/field, et exhaustivité du typage."""
    erreurs: list[str] = []
    if out.slug is not None and out.slug != aide.slug:
        erreurs.append(f"slug « {out.slug} » ≠ aide traitée « {aide.slug} »")

    vus: set[str] = set()
    connus = set(facts) | {f.cle for f in out.nouveaux_faits}
    for t in out.conditions:
        ou = f"condition « {t.id} »"
        if t.id not in attendus:
            erreurs.append(f"{ou} : n'est pas une condition `untyped` de cette fiche")
            continue
        if t.id in vus:
            erreurs.append(f"{ou} : typée deux fois")
        vus.add(t.id)

        # La règle non négociable, et la seule que le schéma `Aide` ne couvre
        # pas : un manual_check gate rend None sans poser de question, donc
        # l'aide ne peut jamais sortir « éligible ».
        if t.kind == "manual_check" and t.effect == "gate":
            erreurs.append(
                f"{ou} : `manual_check` + `gate` est INTERDIT — l'aide ne pourrait "
                "jamais sortir éligible. Épuiser : fait existant, fait nouveau, "
                "discretionary, info, puis manual_check + info."
            )
        if t.kind == "manual_check" and not (t.notes or "").strip():
            erreurs.append(
                f"{ou} : `manual_check` exige des `notes` disant pourquoi c'est irréductible"
            )
        if t.kind in ("info", "discretionary") and t.effect == "gate":
            erreurs.append(f"{ou} : une condition {t.kind} n'a aucune incidence — `gate` interdit")

        if t.kind == "user_fact":
            if not t.fact or t.predicate is None:
                erreurs.append(f"{ou} : `user_fact` exige `fact` ET `predicate`")
            elif t.fact not in connus:
                erreurs.append(
                    f"{ou} : fait « {t.fact} » inconnu — le choisir dans l'ontologie "
                    "fournie, ou le proposer dans `nouveaux_faits`"
                )
            if t.field:
                erreurs.append(f"{ou} : `field` est réservé à kind=auto")
        elif t.kind == "auto":
            if not t.field or t.predicate is None:
                erreurs.append(f"{ou} : `auto` exige `field` ET `predicate`")
            elif t.field not in FIELD_REGISTRY:
                erreurs.append(f"{ou} : champ « {t.field} » absent du registre fourni")
            if t.fact:
                erreurs.append(f"{ou} : `fact` est réservé à kind=user_fact")
        elif t.fact or t.field or t.predicate is not None:
            erreurs.append(f"{ou} : kind={t.kind} n'admet ni fact, ni field, ni predicate")

    # Exhaustivité : une seule condition laissée `untyped` garde l'aide ENTIÈRE
    # hors du moteur, donc un typage partiel ne sert à rien.
    if manquantes := sorted(attendus - vus):
        erreurs.append(
            f"condition(s) non typée(s) : {manquantes} — une seule `untyped` "
            "restante garde toute l'aide hors du moteur déterministe"
        )
    return erreurs


def check_predicats(out: TypageLLMOutput, facts: dict[str, FactDef]) -> list[str]:
    """Prédicats validés par les MÊMES fonctions que `lint_aides_data.py`.

    C'est le garde-fou qui rend le gate automatique tenable : un opérateur
    interdit pour le type du fait, ou une valeur hors de ses options, est
    attrapé ici, en local, avant toute écriture. Un prédicat que le typage
    accepterait et que le lint refuserait laisserait le dépôt cassé après coup.
    """
    proposes = {}
    for nf in out.nouveaux_faits:
        try:
            proposes[nf.cle] = FactDef.model_validate(nf.to_factdef())
        except ValidationError:
            continue  # signalé par `check_nouveaux_faits`
    tous = {**facts, **proposes}

    erreurs: list[str] = []
    for t in out.conditions:
        if t.predicate is None:
            continue
        ou = f"condition « {t.id} »"
        try:
            predicate = Predicate.model_validate(t.predicate)
        except ValidationError as exc:
            erreurs.append(f"{ou} : prédicat invalide — {exc.errors()[0]['msg']}")
            continue
        if t.kind == "user_fact":
            erreurs.extend(check_fact_predicate(ou, t.fact, predicate, tous))
        elif t.kind == "auto":
            erreurs.extend(check_field_predicate(ou, t.field, predicate))
    return erreurs


def check_nouveaux_faits(
    out: TypageLLMOutput, facts: dict[str, FactDef], pending: dict[str, FactDef]
) -> list[str]:
    erreurs: list[str] = []
    vus: set[str] = set()
    for nf in out.nouveaux_faits:
        ou = f"fait proposé « {nf.cle} »"
        if nf.cle in facts:
            erreurs.append(f"{ou} : existe DÉJÀ dans facts.yaml — le référencer, pas le recréer")
        if nf.cle in vus:
            erreurs.append(f"{ou} : proposé deux fois")
        vus.add(nf.cle)
        if nf.cle in pending:
            # Déjà en attente : on ne le réécrit pas, mais le référencer est bon.
            continue
        try:
            FactDef.model_validate(nf.to_factdef())
        except ValidationError as exc:
            detail = exc.errors()[0]
            erreurs.append(f"{ou} : {'.'.join(str(p) for p in detail['loc'])} — {detail['msg']}")
    # Un fait proposé que personne n'utilise est du bruit dans facts_pending.
    references = {t.fact for t in out.conditions if t.fact}
    if orphelins := sorted({nf.cle for nf in out.nouveaux_faits} - references):
        erreurs.append(f"fait(s) proposé(s) mais référencé(s) par aucune condition : {orphelins}")
    return erreurs


def valider(
    texte: str,
    aide: Aide,
    attendus: set[str],
    facts: dict[str, FactDef],
    pending: dict[str, FactDef],
) -> tuple[TypageLLMOutput | None, list[str], Etape | None]:
    """Chaîne complète, dans l'ordre — l'ordre EST la sûreté."""
    out, erreurs, etape = parse_json_output(texte, TypageLLMOutput)
    if out is None:
        return None, erreurs, etape  # type: ignore[return-value]
    if erreurs := check_referentiel_typage(out, aide, attendus, facts):
        return out, erreurs, "referentiel"
    if erreurs := check_nouveaux_faits(out, facts, pending):
        return out, erreurs, "fait"
    if erreurs := check_predicats(out, facts):
        return out, erreurs, "predicat"
    return out, [], None


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


def sortie_typage(out: TypageLLMOutput, aide: Aide, aujourd_hui: date) -> VeilleLLMOutput:
    """Traduit le typage en sortie de veille, pour réutiliser son éditeur.

    L'insertion chirurgicale, l'assertion de différence profonde avec rollback
    et la validation `Aide` du fichier final viennent de `veille_apply` — le
    même éditeur éprouvé sur les 141 fiches du dépôt. `text` et `quote` ne sont
    jamais transmis : ils ne sont pas dans `CHAMPS_TYPAGE`.
    """
    trace = f"typée par audit du {aujourd_hui.isoformat()}"
    existantes = {c.id: c for c in aide.conditions}
    changements: list[ChangementCondition] = []
    for t in out.conditions:
        champs: dict[str, Any] = {"kind": t.kind, "effect": t.effect}
        if t.fact:
            champs["fact"] = t.fact
        if t.field:
            champs["field"] = t.field
        if t.predicate is not None:
            champs["predicate"] = t.predicate
        # La note de l'audit (« ajoutée par audit du …, à typer ») est REMPLACÉE :
        # la condition n'est plus à typer, et la garder ferait rechercher
        # indéfiniment un travail déjà fait par `/typer-aides`.
        ancienne = (existantes[t.id].notes or "") if t.id in existantes else ""
        ancienne = ancienne.split(" — ajoutée par audit du ")[0].strip()
        if ancienne.startswith("ajoutée par audit du "):
            ancienne = ""
        morceaux = [m for m in (ancienne, (t.notes or "").strip(), trace) if m]
        champs["notes"] = " — ".join(morceaux)
        changements.append(ChangementCondition(op="update", id=t.id, champs=champs))
    return VeilleLLMOutput(slug=aide.slug, resume=out.resume, conditions=changements)


def ecrire_faits_pending(nouveaux: list[NouveauFait]) -> list[str]:
    """Ajoute les faits proposés à `facts_pending.yaml`. JAMAIS `facts.yaml`.

    Le fichier est committé et relu à la main : on n'y réécrit pas les entrées
    existantes, on ajoute à la fin, et le diff git ne montre donc que la
    nouveauté. C'est ce diff que l'humain arbitre avant de promouvoir le fait
    vers `facts.yaml` — le commit vaut validation (TYPING.md).

    L'ajout passe par `ajouter_sous_verrou` : `facts_pending.yaml` est partagé
    avec `ingerer.py`, qui peut tourner en même temps, et un `write_text` direct
    l'a déjà détruit une fois (2026-09-04, quatre faits perdus).
    """
    if not nouveaux:
        return []
    existants = load_pending_facts()
    a_ecrire = [nf for nf in nouveaux if nf.cle not in existants]
    if not a_ecrire:
        return []
    bloc = "".join(
        yaml.safe_dump(
            {nf.cle: nf.to_factdef()},
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=10**6,
        )
        + "\n"
        for nf in a_ecrire
    )
    entete = (
        f"\n# --- veille_typage.py ({date.today().isoformat()}) ---\n#\n"
        "# Faits proposés par le typage automatique, en attente de validation humaine.\n"
        "# Approuver = déplacer l'entrée vers `facts.yaml` (cf. data/TYPING.md).\n"
    )
    ajouter_sous_verrou(FACTS_PENDING_FILE, entete + bloc, valider=_valider_pending)
    load_pending_facts.cache_clear()
    return [nf.cle for nf in a_ecrire]


def _valider_pending(texte: str) -> None:
    """Refuse d'écrire un `facts_pending.yaml` que le lint ne pourrait pas lire."""
    brut = yaml.safe_load(texte) or {}
    if not isinstance(brut, dict):
        raise ValueError("facts_pending.yaml doit être un dictionnaire de faits")
    for cle, valeur in brut.items():
        try:
            FactDef.model_validate(valeur)
        except Exception as exc:
            raise ValueError(f"fait invalide « {cle} » : {exc}") from exc


@dataclass
class TypageResult:
    slug: str
    etat: Etat = "echec"
    modele: str = ""
    raison: str = ""
    resume: str = ""
    # (id, kind, effect) de chaque condition typée — la matière du RÉCAP.
    typees: list[tuple[str, str, str]] = field(default_factory=list)
    faits_proposes: list[str] = field(default_factory=list)
    gates_poses: int = 0
    erreurs: list[str] = field(default_factory=list)
    etape_echec: str | None = None
    reponse_rejetee: str = ""
    tentatives: int = 0
    cout_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    latence_s: float = 0.0

    @property
    def symbole(self) -> str:
        return SYMBOLES[self.etat]


def typer(
    aide: Aide,
    spec: ModelSpec,
    *,
    aujourd_hui: date,
    dry_run: bool = False,
    chemin: Path | None = None,
) -> TypageResult:
    """Un appel (au plus deux) au modèle, puis l'écriture si tout passe."""
    chemin = chemin or AIDES_DIR / f"{aide.slug}.yaml"
    res = TypageResult(slug=aide.slug, modele=spec.alias)

    a_typer = [c for c in aide.conditions if c.kind == "untyped"]
    if not a_typer:
        res.etat = "rien_a_faire"
        res.raison = "aucune condition `untyped` : l'aide est déjà engine-ready"
        return res

    facts = load_facts()
    pending = load_pending_facts()
    attendus = {c.id for c in a_typer}
    prompt = build_prompt_typage(aide, a_typer, {**facts, **pending}, aujourd_hui=aujourd_hui)
    system = system_pour(spec, SYSTEM_TYPAGE, TypageLLMOutput)
    schema = json_schema(TypageLLMOutput)

    out: TypageLLMOutput | None = None
    erreurs: list[str] = []
    etape: Etape | None = None
    reponse = ""
    relance_vide, corrections = False, 0
    while True:
        appel = call(spec, system, prompt, schema=schema)
        res.tentatives += 1
        res.cout_usd += appel.cost_usd or 0.0
        res.tokens_in += appel.input_tokens
        res.tokens_out += appel.output_tokens
        res.latence_s += appel.latency_s
        if not appel.ok:
            if appel.reponse_vide and not relance_vide:
                relance_vide = True
                continue
            res.raison = f"appel au modèle en échec : {appel.error}"
            res.erreurs = [appel.error or "réponse vide"]
            res.etape_echec = "appel"
            return res
        reponse = appel.text
        out, erreurs, etape = valider(reponse, aide, attendus, {**facts, **pending}, pending)
        if not erreurs or corrections:
            break
        corrections += 1
        prompt = prompt_correction(prompt, reponse, erreurs)

    if out is None or erreurs:
        res.erreurs = erreurs
        res.etape_echec = etape
        res.reponse_rejetee = reponse
        res.raison = f"validation en échec ({etape}) : {erreurs[0] if erreurs else 'sans détail'}"
        return res

    res.resume = out.resume.strip()
    res.typees = [(t.id, t.kind, t.effect) for t in out.conditions]
    res.gates_poses = sum(1 for t in out.conditions if t.effect == "gate")

    sortie = sortie_typage(out, aide, aujourd_hui)
    # Les faits proposés dans CETTE réponse ne sont pas encore sur disque : sans
    # eux, l'éditeur refuserait tout prédicat posé dessus. `facts_pending.yaml`
    # n'est écrit qu'APRÈS l'édition, pour ne pas y laisser de fait orphelin si
    # celle-ci échoue.
    proposes = {}
    for nf in out.nouveaux_faits:
        try:
            proposes[nf.cle] = FactDef.model_validate(nf.to_factdef())
        except ValidationError:  # pragma: no cover — déjà refusé par `valider`
            continue
    applied = appliquer(
        json.dumps(sortie.model_dump(mode="json"), ensure_ascii=False),
        aide,
        chemin,
        # Aucune quote n'est produite par le typage : le contrôle de citations
        # n'a rien à vérifier, et un document factice non vide lui suffit.
        [("typage", "", "text")],
        aujourd_hui=aujourd_hui.isoformat(),
        diff="",
        champs_condition=CHAMPS_TYPAGE,
        facts_extra=proposes,
    )
    if not applied.ok or applied.texte is None:
        res.erreurs = applied.erreurs
        res.etape_echec = applied.etape
        res.reponse_rejetee = reponse
        premiere = applied.erreurs[0] if applied.erreurs else "sans détail"
        res.raison = f"application en échec ({applied.etape}) : {premiere}"
        return res

    res.etat = "type"
    res.raison = res.resume or f"{len(res.typees)} condition(s) typée(s)"
    if not dry_run:
        chemin.write_text(applied.texte, encoding="utf-8")
        res.faits_proposes = ecrire_faits_pending(out.nouveaux_faits)
    else:
        res.faits_proposes = [
            nf.cle for nf in out.nouveaux_faits if nf.cle not in load_pending_facts()
        ]
    return res


# ---------------------------------------------------------------------------
# Rapport (section, réutilisée par le rapport d'audit)
# ---------------------------------------------------------------------------


def section_typage(resultats: dict[str, TypageResult], mode: str) -> list[str]:
    """Section markdown du typage. Le rapport d'audit la porte telle quelle."""
    faits = sorted({c for r in resultats.values() for c in r.faits_proposes})
    typees = [r for r in resultats.values() if r.etat == "type"]
    echecs = [r for r in resultats.values() if r.etat == "echec"]
    if not typees and not echecs:
        return []

    out = ["## Typage des conditions ajoutées", ""]
    if mode == "dry-run":
        out += ["> **À blanc** : aucun typage n'a été écrit.", ""]
    else:
        out += [
            "> Une condition `untyped` sort l'aide ENTIÈRE du moteur déterministe : "
            "ce typage l'y ramène. Il pose des `gate`, qui éliminent — relire chaque "
            "prédicat avant de committer.",
            "",
        ]
    if typees:
        out += ["| aide | condition | kind | effect |", "|---|---|---|---|"]
        for r in sorted(typees, key=lambda r: r.slug):
            for cond_id, kind, effect in r.typees:
                marque = " ⚠" if effect == "gate" else ""
                out.append(f"| {r.slug} | `{cond_id}` | `{kind}` | `{effect}`{marque} |")
        out += [
            "",
            "Les `gate` marqués ⚠ éliminent une aide quand ils ne sont pas "
            "satisfaits : ce sont eux qu'il faut relire en premier.",
            "",
        ]
    if faits:
        out += [
            "### Faits proposés",
            "",
            "Ajoutés à `data/facts_pending.yaml`, **jamais** à `facts.yaml`. Les "
            "approuver, c'est déplacer leur entrée vers `facts.yaml` — le commit "
            "vaut validation.",
            "",
            *(f"- `{c}`" for c in faits),
            "",
        ]
    if echecs:
        out += ["### Typages en échec", ""]
        for r in sorted(echecs, key=lambda r: r.slug):
            out.append(f"- **{r.slug}** ({r.etape_echec}) — {r.raison}")
            out += [f"  - {e}" for e in r.erreurs[:3]]
        out += [
            "",
            "Ces aides gardent leurs conditions `untyped`, donc restent hors du "
            "moteur déterministe jusqu'à un typage réussi ou manuel.",
            "",
        ]
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def typer_toutes(
    aides: list[Aide],
    spec: ModelSpec,
    *,
    aujourd_hui: date,
    dry_run: bool,
    max_llm: int,
    log: Journal,
) -> dict[str, TypageResult]:
    candidats = [a for a in aides if any(c.kind == "untyped" for c in a.conditions)]
    if not candidats:
        return {}
    if not spec.cle_presente:
        log("")
        log(
            f"⚠ typage ignoré : {spec.env_key} absente de backend/.env — "
            f"{len(candidats)} aide(s) restent hors du moteur."
        )
        return {}

    retenus = candidats[:max_llm]
    log("")
    log(f"{'=' * 70}")
    log(
        f"TYPAGE — {len(retenus)}/{len(candidats)} aide(s), modèle {spec.alias}"
        + (" — à blanc, aucune écriture" if dry_run else "")
    )
    log(f"{'=' * 70}")

    resultats: dict[str, TypageResult] = {}
    for i, aide in enumerate(retenus, 1):
        # Relecture depuis le disque : en enchaînement après l'audit, l'objet
        # en mémoire précède l'écriture des conditions à typer.
        chemin = AIDES_DIR / f"{aide.slug}.yaml"
        frais = load_aide(chemin) if chemin.exists() else aide
        res = typer(frais, spec, aujourd_hui=aujourd_hui, dry_run=dry_run, chemin=chemin)
        resultats[aide.slug] = res
        log(
            f"  [{i}/{len(retenus)}] {res.symbole} {aide.slug:<46} "
            f"{res.cout_usd * 100:>5.2f}¢ {res.latence_s:>5.1f}s "
            f"{tokens_compacts(res.tokens_in):>6}↑{tokens_compacts(res.tokens_out):>6}↓ "
            f"{len(res.typees):>2} typée(s)"
            + (f" {res.gates_poses}⚠gate" if res.gates_poses else "       ")
            + f"  {cellule(res.raison, 38)}"
        )
        if res.reponse_rejetee:
            log(f"      réponse rejetée : {res.reponse_rejetee.strip()}")
    if len(candidats) > len(retenus):
        log(
            f"  … {len(candidats) - len(retenus)} aide(s) laissée(s) : plafond --max-llm={max_llm}."
        )
    tok_in = sum(r.tokens_in for r in resultats.values())
    tok_out = sum(r.tokens_out for r in resultats.values())
    log(
        f"  coût du typage : {sum(r.cout_usd for r in resultats.values()):.3f} $"
        f"  —  {milliers(tok_in)} tokens en entrée, {milliers(tok_out)} en sortie"
    )
    return resultats


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="veille_typage.py",
        description="Type les conditions `untyped` pour ramener les aides dans le moteur.",
    )
    p.add_argument("slugs", nargs="*", help="aides à typer (défaut : toutes celles qui en ont)")
    p.add_argument("--dry-run", action="store_true", help="sans écrire un seul fichier")
    p.add_argument("--max-llm", type=int, default=MAX_LLM_DEFAUT)
    p.add_argument(
        "--model",
        default=MODELE_DEFAUT,
        help=f"alias du registre ou `fournisseur:identifiant` (défaut : {MODELE_DEFAUT})",
    )
    p.add_argument("--limit", type=int)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    log = Journal()
    today = date.today()

    # Un VEILLE_MODEL mal saisi doit dire lequel et proposer les valeurs
    # valides, pas dérouler une KeyError au milieu d'un passage.
    try:
        resoudre_modele(args.model)
    except KeyError as exc:
        print(f"ERREUR : {exc.args[0]}", file=sys.stderr)
        return 1

    if args.slugs:
        paths = [AIDES_DIR / f"{s}.yaml" for s in args.slugs]
        if manquants := [p.stem for p in paths if not p.exists()]:
            print(f"ERREUR : YAML introuvable pour : {', '.join(manquants)}", file=sys.stderr)
            return 1
    else:
        paths = sorted(AIDES_DIR.glob("*.yaml"))
    try:
        aides = [load_aide(p) for p in paths]
    except Exception as exc:  # noqa: BLE001 — un YAML cassé est fatal, pas un plantage
        print(f"ERREUR : YAML invalide — {exc}", file=sys.stderr)
        return 1

    a_faire = [a for a in aides if any(c.kind == "untyped" for c in a.conditions)]
    log(f"{'=' * 70}")
    log(f"TYPAGE DES CONDITIONS — {today.isoformat()}")
    log(f"{'=' * 70}")
    log(f"{len(aides)} aide(s) examinée(s), {len(a_faire)} avec des conditions `untyped`.")
    if not a_faire:
        log("Rien à typer : toutes les aides du périmètre sont engine-ready.")
        return 0
    if args.limit:
        a_faire = a_faire[: args.limit]

    debut = time.monotonic()
    resultats = typer_toutes(
        a_faire,
        resoudre_modele(args.model),
        aujourd_hui=today,
        dry_run=args.dry_run,
        max_llm=args.max_llm,
        log=log,
    )

    log("")
    log(f"{'=' * 70}")
    log("RÉCAP")
    log(f"{'=' * 70}")
    compte = Counter(r.etat for r in resultats.values())
    for etat, n in compte.most_common():
        log(f"  {SYMBOLES[etat]} {etat:<20} {n}")
    if gates := sum(r.gates_poses for r in resultats.values()):
        log(f"  ⚠ {gates} `gate` posé(s) — ils ÉLIMINENT : relire chaque prédicat.")
    if faits := sorted({c for r in resultats.values() for c in r.faits_proposes}):
        log(f"  {len(faits)} fait(s) proposé(s) dans facts_pending.yaml : {', '.join(faits)}")
    log(f"durée : {(time.monotonic() - debut) / 60:.1f} min")
    if not args.dry_run and any(r.etat == "type" for r in resultats.values()):
        log("Relire avant commit : git diff -- data/aides data/facts_pending.yaml")

    return 2 if compte["echec"] else 0


if __name__ == "__main__":
    sys.exit(main())
