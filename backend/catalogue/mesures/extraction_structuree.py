"""Prototype d'extraction structurée pour le banc X : un appel JSON, le YAML émis par le code (I0, M3).

Commande, depuis backend/ (un processus par configuration et par passe : la
redirection des sources est globale au processus) :

    uv run python -m catalogue.mesures.extraction_structuree <dossier du banc> \\
        --config b|c --passe 1|2 [--seulement <slug> ...]

Pour chaque aide du banc, dans `<banc>/structuree-<config>/p<passe>/<slug>/` :

1. les instantanés archivés de l'aide sont copiés dans le dossier de sortie,
   comme pour l'agent ; le modèle reçoit la version la plus récente de chaque
   document, sous son nom de fichier, telle que la lit la recherche de
   citations (`veille_collect.load_baselines`) ;
2. un appel `z-ai/glm-5.3-flash` (effort medium, json_schema strict) reçoit la
   même doctrine que l'agent (`ingestion.contexte.prompt_systeme` : skill,
   extraits du README et de TYPING, schéma condensé, index des faits), la seule
   différence étant le bloc d'adaptation au harnais, et la même aide-exemple
   (`choisir_aide_reference`) ;
3. le code émet le YAML (ordre des clés du catalogue, `yaml.safe_dump`), écrit
   les faits proposés au format de `facts_pending.yaml` (`faits._bloc`), puis
   contrôle : chargement, lint mono-slug avec citations et contrôles d'écriture
   (`lint_aides_data.lint`, comme l'ingestion), `familles` non vide, trois faits
   neufs au plus, forme de chaque fait neuf (`faits._refus_de_forme`), voisins
   d'un fait neuf montrés au modèle avant qu'il le maintienne (`faits._proches`,
   comme la garde de l'agent) ;
4. deux tours de correction au plus sur les erreurs du code ;
5. configuration b seulement : le vérificateur de l'agent (`ingestion.verification
   .verifier`, `or-ds41`), puis un tour de correction sur ses objections et, au
   besoin, un dernier tour sur les erreurs du code.

Une aide qui ne passe pas les contrôles finit en `<slug>.yaml.echec`. Une panne
(réseau, crédits, réponse vide ou JSON invalide après deux essais) est une
issue `panne`, jamais un refus. Chaque appel est tracé avec son coût facturé
dans `appels.jsonl` ; `resume.json` résume l'aide.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import time
from pathlib import Path
from typing import Any

import yaml
from ingestion import contexte, faits
from ingestion.atelier import Atelier, atelier_redirige
from ingestion.verification import verifier
from lint_aides_data import lint
from pipeline import llm

from aides_schema import (
    CATEGORIES,
    FIELD_REGISTRY,
    RAISONS,
    TYPES,
    FactDef,
    load_aide,
    load_facts,
    load_pending_facts,
)
from catalogue.mesures.lanceur_agent import indexer, relever
from catalogue.openrouter import Client, Panne
from catalogue.registre import charger as charger_registre
from catalogue.veille_collect import load_baselines
from catalogue.veille_text import find_quote_in_any
from labels import (
    DEPARTEMENT_LABELS,
    ETAT_LABELS,
    FAMILLES_LABELS,
    OWNERSHIP_LABELS,
    PROTECTION_LABELS,
    REGION_LABELS,
    TRAVAUX_LABELS,
)
from pieces_schema import load_pieces

BACKEND = Path(__file__).resolve().parents[2]
SOURCES = BACKEND / "data" / "sources"
AIDES = BACKEND / "data" / "aides"
# Trois tours : le banc X du 2026-10-10 a refusé deux aides pour des citations
# recollées, et le troisième tour vise précisément ces citations.
TOURS_CORRECTION = 3
# Les fournisseurs les plus rapides d'abord : un fournisseur de GLM répondait en
# 286 s en médiane au banc X, et un de ses appels a tourné 16 minutes à vide.
FOURNISSEURS = {"sort": "throughput"}
ORDRE_AIDE = (
    "slug",
    "nom",
    "nom_court",
    "organisme",
    "categorie",
    "type",
    "raison",
    "familles",
    "description",
    "description_longue",
    "source",
    "financement",
    "cumul",
    "calendrier",
    "hard_filters",
    "applies_if",
    "conditions",
    "demarche",
    "documents_requis",
    "tags",
)
CATEGORIES_ECART = (
    "metier_agricole",
    "entreprise_generale",
    "organisateur_artiste",
    "pratique_amateur",
    "aide_personne",
    "non_dispositif",
    "objet_hors_lieu",
)

ADAPTATIONS = """\
## Adaptations au harnais (à lire APRÈS le skill)

Tu ne tournes pas dans Claude Code et tu n'as aucun outil : tu rends UNE réponse,
un objet JSON conforme au schéma imposé, et le code en tire le fichier YAML.
Chaque étape du skill s'y traduit ainsi :

| Étape du skill | Ce que tu fais ici |
|---|---|
| 0 — Contexte | RIEN À FAIRE : README, TYPING, schéma et index des faits sont ci-dessous. |
| 1 — Sources et snapshots | Les instantanés archivés sont dans le message, chacun sous son nom de fichier : ce sont tes seules sources. Si la source montre que l'aide ne relève pas du catalogue (test du destinataire), remplis `hors_perimetre` et laisse `conditions` vide. |
| 2 — Extraction | Remplis le JSON. Chaque `quote` est une copie EXACTE d'un passage d'un instantané, et `document` nomme ce fichier. |
| 3 — Lint | Le code lance le lint sur le YAML qu'il émet et te renvoie ses erreurs ; tu rends alors le JSON COMPLET corrigé. |
| 4 — Vérification adversariale | Le code la lance et te renvoie les objections ; tu rends le JSON COMPLET corrigé. |
| 5 — Fiche de review | `qualite_source` et `a_trancher` en tiennent lieu. |

Règles du harnais :

- **Un fait nouveau n'existe que dans `faits_proposes`**, trois au plus. Un
  `fact` qui n'est ni dans l'index ci-dessous ni proposé dans la même réponse
  est une erreur. Avant d'en proposer un, cherche dans l'index une question
  équivalente : le prédicat porte le seuil, pas le fait.
- **Prédicats** : `{op, valeurs, branches}`. `valeurs` porte UNE valeur pour
  eq, neq, gt, gte, lt, lte et contains, une liste pour in, not_in et none_in ;
  any_of et all_of portent leurs `branches` et une liste `valeurs` vide.
- **Ce que la source ne dit pas reste null** (ou une liste vide), jamais une
  valeur devinée.
"""


# --------------------------------------------------------------------------
# Schéma de la réponse
# --------------------------------------------------------------------------


def _chaine(*nul: bool) -> dict[str, Any]:
    return {"type": ["string", "null"]} if nul else {"type": "string"}


def _enum(valeurs: Any) -> dict[str, Any]:
    return {"type": "string", "enum": sorted(valeurs)}


def _objet(proprietes: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(proprietes),
        "properties": proprietes,
    }


def _nul(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def schema_aide() -> dict[str, Any]:
    """Le json_schema strict de la réponse, ses énumérations tirées du code."""
    champs = sorted(k for k in FIELD_REGISTRY if k != "monument.nom")
    porteurs = [o.id for o in (load_facts()["statut_juridique_porteur"].options or [])]
    defs: dict[str, Any] = {
        "Valeur": {"anyOf": [{"type": "string"}, {"type": "number"}, {"type": "boolean"}]},
        "Feuille": _objet(
            {
                "op": _enum(
                    ["eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in", "none_in", "contains"]
                ),
                "valeurs": {"type": "array", "items": {"$ref": "#/$defs/Valeur"}},
            }
        ),
        "Predicat": _objet(
            {
                "op": _enum(
                    [
                        "eq",
                        "neq",
                        "gt",
                        "gte",
                        "lt",
                        "lte",
                        "in",
                        "not_in",
                        "none_in",
                        "contains",
                        "any_of",
                        "all_of",
                    ]
                ),
                "valeurs": {"type": "array", "items": {"$ref": "#/$defs/Valeur"}},
                "branches": _nul({"type": "array", "items": {"$ref": "#/$defs/Feuille"}}),
            }
        ),
        "AppliesIf": _objet(
            {
                "fact": _chaine(True),
                "field": _nul(_enum(champs)),
                "predicate": {"$ref": "#/$defs/Predicat"},
            }
        ),
        "Condition": _objet(
            {
                "id": _chaine(),
                "text": _chaine(),
                "quote": _chaine(True),
                "document": _chaine(True),
                "kind": _enum(["auto", "user_fact", "discretionary", "info", "manual_check"]),
                "effect": _enum(["gate", "modulateur", "info"]),
                "fact": _chaine(True),
                "field": _nul(_enum(champs)),
                "predicate": _nul({"$ref": "#/$defs/Predicat"}),
                "applies_if": _nul({"$ref": "#/$defs/AppliesIf"}),
                "derogation_possible": {"type": "boolean"},
                "levier": _chaine(True),
                "notes": _chaine(True),
            }
        ),
        "Document": _objet(
            {
                "nom": _chaine(),
                "url": _chaine(True),
                "obligatoire": {"type": "boolean"},
                "note": _chaine(True),
                "piece_id": _nul(_enum(load_pieces())),
            }
        ),
        "OptionFait": _objet(
            {
                "id": _chaine(),
                "label": _chaine(),
                "description": _chaine(True),
                "unknown": {"type": "boolean"},
                "valeur": {"type": ["boolean", "null"]},
            }
        ),
        "FaitPropose": _objet(
            {
                "id": _chaine(),
                "type": _enum(["boolean", "integer", "number", "enum", "multi_enum"]),
                "scope": _enum(["monument", "projet", "proprietaire"]),
                "question": _chaine(),
                "help": _chaine(True),
                "unit": _chaine(True),
                "options": _nul({"type": "array", "items": {"$ref": "#/$defs/OptionFait"}}),
                "porteurs_concernes": _nul({"type": "array", "items": _enum(porteurs)}),
                "justification": _chaine(),
                "voisins_ecartes": {"type": "array", "items": {"type": "string"}},
            }
        ),
    }
    nombre = {"type": ["number", "null"]}
    racine = _objet(
        {
            "hors_perimetre": _nul(
                _objet(
                    {
                        "categorie": _enum(CATEGORIES_ECART),
                        "motif": _chaine(),
                        "citation": _chaine(),
                    }
                )
            ),
            "nom": _chaine(),
            "nom_court": _chaine(),
            "organisme": _chaine(),
            "categorie": _enum(CATEGORIES),
            "type": _enum(TYPES),
            "raison": {"type": "array", "items": _enum(RAISONS)},
            "familles": {"type": "array", "items": _enum(FAMILLES_LABELS)},
            "description": _chaine(),
            "description_longue": _chaine(True),
            "formulaire_url": _chaine(True),
            "financement": _objet(
                {
                    "montant_min": nombre,
                    "montant_max": nombre,
                    "taux_min": nombre,
                    "taux_max": nombre,
                    "plancher": nombre,
                    "base_ttc": {"type": "boolean"},
                    "assiette": _chaine(True),
                }
            ),
            "cumul": _objet(
                {
                    "plafond_public_pct": nombre,
                    "cumulable": {"type": "boolean"},
                    "exclusions": {"type": "array", "items": {"type": "string"}},
                }
            ),
            "calendrier": _objet(
                {
                    "permanent": {"type": "boolean"},
                    "date_ouverture": _chaine(True),
                    "date_limite": _chaine(True),
                    "delai_instruction": _chaine(True),
                }
            ),
            "hard_filters": _objet(
                {
                    "protections": {"type": "array", "items": _enum(PROTECTION_LABELS)},
                    "proprietaires": {"type": "array", "items": _enum(OWNERSHIP_LABELS)},
                    "travaux": {"type": "array", "items": _enum(TRAVAUX_LABELS)},
                    "regions": {"type": "array", "items": _enum(REGION_LABELS)},
                    "departements": {"type": "array", "items": _enum(DEPARTEMENT_LABELS)},
                    "etats_conservation": {"type": "array", "items": _enum(ETAT_LABELS)},
                    "commune_max_population": {"type": ["integer", "null"]},
                }
            ),
            "perimetre": _nul(
                _objet({"fact": _chaine(), "predicate": {"$ref": "#/$defs/Predicat"}})
            ),
            "conditions": {"type": "array", "items": {"$ref": "#/$defs/Condition"}},
            "demarche": _chaine(True),
            "documents_requis": {"type": "array", "items": {"$ref": "#/$defs/Document"}},
            "tags": {"type": "array", "items": {"type": "string"}},
            "faits_proposes": {"type": "array", "items": {"$ref": "#/$defs/FaitPropose"}},
            "qualite_source": _enum(["reglement", "page_officielle", "vulgarisation"]),
            "a_trancher": {"type": "array", "items": {"type": "string"}},
        }
    )
    racine["$defs"] = defs
    return racine


# --------------------------------------------------------------------------
# Du JSON au YAML
# --------------------------------------------------------------------------


def _blancs(texte: str | None) -> str | None:
    return " ".join(texte.split()) if texte else texte


def predicat(p: dict[str, Any]) -> dict[str, Any]:
    """`{op, valeurs, branches}` vers la forme du catalogue (`{op: valeur}`)."""
    op, valeurs = p["op"], p.get("valeurs") or []
    if op in ("any_of", "all_of"):
        return {op: [predicat(b) for b in (p.get("branches") or [])]}
    if op in ("in", "not_in", "none_in"):
        return {op: list(valeurs)}
    if len(valeurs) != 1:
        raise ValueError(f"l'opérateur {op} attend une seule valeur, reçu {valeurs!r}")
    return {op: valeurs[0]}


def _date(valeur: str | None) -> dt.date | None:
    return dt.date.fromisoformat(valeur) if valeur else None


def _sans_vides(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None and v != [] and v != ""}


def emettre(
    donnees: dict[str, Any], slug: str, url: str | None, snapshot: str | None
) -> dict[str, Any]:
    """Le dict de l'aide, dans l'ordre des clés du catalogue, sans null."""
    aide: dict[str, Any] = {k: donnees.get(k) for k in ORDRE_AIDE if k in donnees}
    aide["slug"] = slug
    aide["source"] = _sans_vides(
        {
            "url_officielle": url,
            "formulaire_url": donnees.get("formulaire_url"),
            "verified_at": dt.date.today(),
            "snapshot": snapshot,
        }
    )
    f = donnees["financement"]
    aide["financement"] = {k: v for k, v in f.items() if v is not None}
    c = donnees["cumul"]
    aide["cumul"] = _sans_vides(
        {
            "plafond_public_pct": c.get("plafond_public_pct"),
            "cumulable": c.get("cumulable"),
            "exclusions": c.get("exclusions"),
        }
    )
    cal = donnees["calendrier"]
    aide["calendrier"] = _sans_vides(
        {
            "permanent": cal.get("permanent"),
            "date_ouverture": _date(cal.get("date_ouverture")),
            "date_limite": _date(cal.get("date_limite")),
            "delai_instruction": cal.get("delai_instruction"),
        }
    )
    hf = _sans_vides(dict(donnees["hard_filters"]))
    if hf:
        aide["hard_filters"] = hf
    else:
        aide.pop("hard_filters", None)
    if donnees.get("perimetre"):
        aide["applies_if"] = {
            "fact": donnees["perimetre"]["fact"],
            "predicate": predicat(donnees["perimetre"]["predicate"]),
        }
    conditions = []
    vus: dict[str, int] = {}
    for c in donnees["conditions"]:
        ident = c["id"]
        vus[ident] = vus.get(ident, 0) + 1
        if vus[ident] > 1:
            ident = f"{ident}-{vus[ident]}"
        cond: dict[str, Any] = {
            "id": ident,
            "text": _blancs(c["text"]),
            "kind": c["kind"],
            "effect": c["effect"],
        }
        if c.get("fact"):
            cond["fact"] = c["fact"]
        if c.get("field"):
            cond["field"] = c["field"]
        if c.get("predicate"):
            cond["predicate"] = predicat(c["predicate"])
        if c.get("applies_if"):
            a = c["applies_if"]
            cond["applies_if"] = _sans_vides(
                {
                    "fact": a.get("fact"),
                    "field": a.get("field"),
                    "predicate": predicat(a["predicate"]),
                }
            )
        if c.get("derogation_possible"):
            cond["derogation_possible"] = True
        if c.get("levier"):
            cond["levier"] = c["levier"]
        if c.get("quote"):
            cond["quote"] = _blancs(c["quote"])
        if c.get("notes"):
            cond["notes"] = _blancs(c["notes"])
        conditions.append(cond)
    aide["conditions"] = conditions
    aide["documents_requis"] = [
        _sans_vides(
            {
                "nom": d["nom"],
                "url": d.get("url"),
                "obligatoire": None if d.get("obligatoire", True) else False,
                "note": d.get("note"),
                "piece_id": d.get("piece_id"),
            }
        )
        for d in donnees.get("documents_requis") or []
    ]
    # L'ordre des clés du catalogue, quel que soit l'ordre d'insertion ci-dessus.
    return {k: aide[k] for k in ORDRE_AIDE if k in aide and aide[k] is not None and aide[k] != []}


def definition_fait(f: dict[str, Any]) -> dict[str, Any]:
    options = None
    if f.get("options"):
        options = [
            _sans_vides(
                {
                    "id": o["id"],
                    "label": o["label"],
                    "description": o.get("description"),
                    "unknown": True if o.get("unknown") else None,
                    "valeur": o.get("valeur"),
                }
            )
            for o in f["options"]
        ]
    return _sans_vides(
        {
            "type": f["type"],
            "scope": f["scope"],
            "question": f["question"],
            "options": options,
            "unit": f.get("unit"),
            "help": f.get("help"),
            "porteurs_concernes": f.get("porteurs_concernes"),
        }
    )


# --------------------------------------------------------------------------
# Contrôles
# --------------------------------------------------------------------------


def coherence(donnees: dict[str, Any]) -> list[str]:
    """Les contraintes du schéma des aides que le json_schema ne peut pas dire, en clair.

    Le message de validation de pydantic, renvoyé tel quel, laissait au banc X une
    condition `user_fact` sans fait après deux corrections.
    """
    messages = []
    for c in donnees.get("conditions") or []:
        ident, kind, effect = c["id"], c["kind"], c["effect"]
        if kind == "user_fact" and not (c.get("fact") and c.get("predicate")):
            messages.append(
                f"condition {ident} : kind user_fact exige `fact` et `predicate`. Si aucun fait ne "
                "pose la question, propose-en un dans `faits_proposes`, ou type la condition en "
                "manual_check, effect info, avec des notes."
            )
        if kind == "auto" and not (c.get("field") and c.get("predicate")):
            messages.append(f"condition {ident} : kind auto exige `field` et `predicate`.")
        if kind not in ("user_fact", "auto") and (
            c.get("fact") or c.get("field") or c.get("predicate")
        ):
            messages.append(
                f"condition {ident} : kind {kind} ne porte ni fact, ni field, ni predicate "
                "(seuls user_fact et auto en portent)."
            )
        if kind == "info" and effect != "info":
            messages.append(f"condition {ident} : kind info exige effect info.")
        if kind == "discretionary" and effect == "gate":
            messages.append(
                f"condition {ident} : discretionary n'est jamais un gate (info ou modulateur)."
            )
        if kind == "manual_check" and effect == "gate":
            messages.append(
                f"condition {ident} : manual_check en gate est interdit (info ou modulateur)."
            )
        if c.get("levier") and kind != "manual_check":
            messages.append(f"condition {ident} : `levier` n'existe que sur un manual_check.")
        if c.get("derogation_possible") and not (
            kind in ("auto", "user_fact") and effect == "gate"
        ):
            messages.append(
                f"condition {ident} : derogation_possible n'existe que sur un gate auto ou user_fact."
            )
    return messages


def citations_introuvables(atelier: Atelier, donnees: dict[str, Any]) -> list[str]:
    """Une consigne par citation que la recherche du lint ne retrouve pas."""
    documents, _, _ = load_baselines(atelier.slug)
    messages = []
    for c in donnees.get("conditions") or []:
        q = c.get("quote")
        if q and not find_quote_in_any(q, documents)[1].found:
            messages.append(
                f"citation de la condition {c['id']} introuvable mot pour mot dans les instantanés : "
                f"« {q[:300]} ». Copie UN SEUL passage continu d'un instantané, sans points de "
                "suspension ni puces mises bout à bout ; si l'exigence s'étend sur plusieurs "
                "passages, garde le passage principal ou scinde la condition."
            )
    return messages


def ecrire_et_controler(
    atelier: Atelier,
    donnees: dict[str, Any],
    url: str | None,
    snapshot: str | None,
    pending_origine: str,
    voisins_montres: set[str],
) -> tuple[list[str], list[str], list[str]]:
    """Écrit le YAML et les faits proposés, puis rend (erreurs, faits du run, voisins à montrer)."""
    erreurs: list[str] = []
    a_montrer: list[str] = []
    facts = dict(load_facts())
    proposes = donnees.get("faits_proposes") or []
    if len(proposes) > faits.MAX_FAITS_PAR_AIDE:
        erreurs.append(f"{len(proposes)} faits proposés : trois au plus.")
    blocs = []
    ids_proposes: list[str] = []
    load_pending_facts.cache_clear()
    pending = dict(load_pending_facts(atelier.pending_path))
    for f in proposes[: faits.MAX_FAITS_PAR_AIDE]:
        ident = f["id"]
        try:
            fait = FactDef.model_validate(definition_fait(f))
        except Exception as exc:  # noqa: BLE001 : l'erreur repart au modèle
            erreurs.append(f"fait proposé {ident} invalide : {str(exc)[:400]}")
            continue
        if len((f.get("justification") or "").strip()) < 80:
            erreurs.append(f"fait proposé {ident} : justification de moins de 80 caractères.")
        forme = faits._refus_de_forme(ident, fait)
        if forme:
            erreurs.append(f"fait proposé {ident} : {forme}")
            continue
        if ident in facts or (ident in pending and ident not in pending_origine):
            erreurs.append(
                f"fait proposé {ident} : la clé existe déjà dans l'ontologie, réutilise-la."
            )
            continue
        proches = [c for _s, c in faits._proches(ident, fait, {**facts, **pending}) if c != ident]
        nouveaux = [c for c in proches if c not in voisins_montres]
        if nouveaux:
            a_montrer.extend(nouveaux)
            erreurs.append(
                f"fait proposé {ident} : des faits proches existent ({', '.join(nouveaux)}) ; "
                "leur définition est ci-dessous. Réutilise l'un d'eux, ou garde ta proposition "
                "en disant dans sa justification pourquoi aucun ne convient."
            )
        definition = fait.model_dump(exclude_none=True, exclude_defaults=True)
        blocs.append(
            faits._bloc(atelier.slug, ident, definition, f.get("justification") or "", atelier.jour)
        )
        ids_proposes.append(ident)
    atelier.pending_path.write_text(pending_origine + "".join(blocs), encoding="utf-8")
    load_pending_facts.cache_clear()

    incoherences = coherence(donnees)
    if incoherences:
        return [*erreurs, *incoherences], ids_proposes, a_montrer
    try:
        aide = emettre(donnees, atelier.slug, url, snapshot)
    except (ValueError, KeyError) as exc:
        return [*erreurs, f"prédicat ou champ invalide : {exc}"], ids_proposes, a_montrer
    atelier.aides_dir.mkdir(parents=True, exist_ok=True)
    atelier.yaml_path.write_text(
        yaml.safe_dump(aide, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8"
    )
    try:
        load_aide(atelier.yaml_path)
    except Exception as exc:  # noqa: BLE001
        return [*erreurs, f"le YAML ne se charge pas : {str(exc)[:800]}"], ids_proposes, a_montrer
    if not aide.get("familles"):
        erreurs.append("`familles` est vide : au moins une famille est exigée.")
    rapport = lint(
        [atelier.slug],
        quotes=True,
        ecriture=True,
        aides_dir=atelier.aides_dir,
        pending_path=atelier.pending_path,
        faits_du_run=tuple(ids_proposes),
    )
    if not rapport.ok:
        erreurs.append("lint :\n" + rapport.texte()[:6000])
        erreurs.extend(citations_introuvables(atelier, donnees))
    return erreurs, ids_proposes, a_montrer


# --------------------------------------------------------------------------
# Une aide
# --------------------------------------------------------------------------


def _documents(atelier: Atelier) -> tuple[str, str | None]:
    """Les instantanés tels que les lit la recherche de citations, le plus récent par URL."""
    index = indexer(atelier.dossier_sources)
    gardes = {a.chemin.name: a.url for a in index.values()}
    documents, _illisibles, _ = load_baselines(atelier.slug)
    blocs = []
    for nom, contenu, _type in documents:
        if nom in gardes:
            blocs.append(f"### {nom} ({gardes[nom]})\n\n{contenu.strip()}")
    principal = max(gardes, key=lambda n: len(n)) if gardes else None
    return "\n\n".join(blocs), principal


def extraire(
    slug: str,
    sortie: Path,
    client: Client,
    *,
    avec_verificateur: bool,
) -> dict[str, Any]:
    debut = time.monotonic()
    atelier = atelier_redirige(slug, sortie)
    shutil.copytree(SOURCES / slug, atelier.dossier_sources, dirs_exist_ok=True)
    pending_origine = atelier.pending_path.read_text(encoding="utf-8")
    catalogue = yaml.safe_load((AIDES / f"{slug}.yaml").read_text(encoding="utf-8"))
    url = (catalogue.get("source") or {}).get("url_officielle")
    sources, _principal = _documents(atelier)
    snapshot_principal = next(
        (
            f"data/sources/{slug}/{a.chemin.name}"
            for a in indexer(atelier.dossier_sources).values()
            if url and a.url.rstrip("/") == url.rstrip("/")
        ),
        None,
    )
    gabarit = contexte.choisir_aide_reference(slug, AIDES)
    systeme = contexte.prompt_systeme(
        dict(load_facts()), dict(load_pending_facts(atelier.pending_path))
    )
    systeme = systeme.replace(contexte.ADAPTATIONS.rstrip(), ADAPTATIONS.rstrip())
    consigne = "\n\n".join(
        [
            f"Aide à extraire : `{slug}`. URL officielle : {url}",
            (
                f"## Aide-exemple : `{gabarit[0]}` (sa forme, pas son contenu)\n\n```yaml\n{gabarit[1].rstrip()}\n```"
                if gabarit
                else ""
            ),
            "## Sources archivées\n\n" + sources,
            "Rends le JSON de l'aide.",
        ]
    )
    messages = [{"role": "system", "content": systeme}, {"role": "user", "content": consigne}]
    schema = schema_aide()
    resume: dict[str, Any] = {"slug": slug, "tours": 0, "verification": None, "erreurs": []}
    voisins_montres: set[str] = set()

    modele = charger_registre().modele("extraction")

    def appeler(role: str) -> dict[str, Any]:
        reponse = client.completer(
            modele.nom,
            messages,
            schema=schema,
            nom_schema="aide",
            effort=modele.effort,
            fournisseurs=FOURNISSEURS,
            acceptes=modele.acceptes,
            delai_s=modele.delai_s,
            role=role,
        )
        resume["tours"] += 1
        messages.append({"role": "assistant", "content": reponse.texte})
        return reponse.donnees

    def corriger(erreurs: list[str], a_montrer: list[str], cause: str) -> None:
        detail = ""
        if a_montrer:
            facts = dict(load_facts())
            pending = dict(load_pending_facts(atelier.pending_path))
            detail = "\n\n## Définitions des faits proches\n\n" + "\n\n".join(
                faits.detail(facts, pending, c) for c in dict.fromkeys(a_montrer)
            )
            voisins_montres.update(a_montrer)
        messages.append(
            {
                "role": "user",
                "content": f"{cause}\n\n"
                + "\n\n".join(f"- {e}" for e in erreurs)
                + detail
                + "\n\nCorrige et rends le JSON COMPLET de l'aide.",
            }
        )

    try:
        donnees = appeler("extraction")
        if donnees.get("hors_perimetre"):
            (sortie / f"{slug}.hors-perimetre.json").write_text(
                json.dumps(donnees["hors_perimetre"], ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
            resume.update(issue="hors_perimetre", duree_s=round(time.monotonic() - debut, 1))
            return resume
        erreurs, proposes, a_montrer = ecrire_et_controler(
            atelier, donnees, url, snapshot_principal, pending_origine, voisins_montres
        )
        for _ in range(TOURS_CORRECTION):
            if not erreurs:
                break
            corriger(erreurs, a_montrer, "Le code a refusé le JSON :")
            donnees = appeler("correction")
            erreurs, proposes, a_montrer = ecrire_et_controler(
                atelier, donnees, url, snapshot_principal, pending_origine, voisins_montres
            )
        if avec_verificateur and not erreurs:
            rapport, rendu = verifier(
                atelier,
                llm.client_pour(
                    "verification", charger_registre().modele("verification").alias_providall
                ),
                aide=load_aide(atelier.yaml_path),
            )
            bloquants = [p for p in rapport.problemes if p.severite == "bloquant"]
            resume["verification"] = {
                "problemes": len(rapport.problemes),
                "bloquants": len(bloquants),
                "indisponible": rapport.commentaire == "vérificateur indisponible",
            }
            if bloquants:
                messages.append(
                    {
                        "role": "user",
                        "content": "Le vérificateur adversarial a relu le YAML contre les sources :\n\n"
                        + rendu
                        + "\n\nCorrige les problèmes bloquants que la source confirme ; en désaccord, "
                        "garde ta version. Rends le JSON COMPLET de l'aide.",
                    }
                )
                donnees = appeler("correction_verification")
                erreurs, proposes, a_montrer = ecrire_et_controler(
                    atelier, donnees, url, snapshot_principal, pending_origine, voisins_montres
                )
                if erreurs:
                    corriger(erreurs, a_montrer, "Le code a refusé le JSON :")
                    donnees = appeler("correction")
                    erreurs, proposes, a_montrer = ecrire_et_controler(
                        atelier, donnees, url, snapshot_principal, pending_origine, voisins_montres
                    )
    except Panne as exc:
        resume.update(issue="panne", panne=exc.classe, message=str(exc)[:300])
        resume["duree_s"] = round(time.monotonic() - debut, 1)
        return resume

    if erreurs and atelier.yaml_path.exists():
        atelier.yaml_path.rename(atelier.yaml_echec_path)
    resume.update(
        issue="refusee" if erreurs else "acceptee",
        erreurs=erreurs,
        faits_proposes=proposes,
        conditions=len(donnees.get("conditions") or []),
        qualite_source=donnees.get("qualite_source"),
        a_trancher=donnees.get("a_trancher"),
        duree_s=round(time.monotonic() - debut, 1),
    )
    return resume


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("banc")
    parseur.add_argument("--config", choices=("b", "c"), required=True)
    parseur.add_argument("--passe", type=int, required=True)
    parseur.add_argument("--seulement", nargs="*", default=[])
    args = parseur.parse_args()
    banc = Path(args.banc).resolve()
    racine = banc / f"structuree-{args.config}" / f"p{args.passe}"
    llm.charger_env()
    slugs = [
        a["slug"] for a in json.loads((banc / "aides.json").read_text(encoding="utf-8"))["aides"]
    ]
    for slug in slugs:
        if args.seulement and slug not in args.seulement:
            continue
        sortie = racine / slug
        if (sortie / "resume.json").exists():
            continue
        if sortie.exists():
            shutil.rmtree(sortie)
        sortie.mkdir(parents=True)
        appels = sortie / "appels.jsonl"
        relever(appels)
        pannes_precedentes: list[str] = []
        # Une panne n'est pas un échec : la production rejouerait l'aide. Une
        # seconde tentative, dans un dossier neuf ; la dépense de la première
        # reste comptée.
        for _ in range(2):
            client = Client(journal=appels)
            try:
                resume = extraire(slug, sortie, client, avec_verificateur=args.config == "b")
            finally:
                client.fermer()
            if resume["issue"] != "panne":
                break
            pannes_precedentes.append(f"{resume.get('panne')} : {resume.get('message', '')[:200]}")
            for sous in ("aides", "reviews"):
                shutil.rmtree(sortie / sous, ignore_errors=True)
        resume["pannes_rejouees"] = pannes_precedentes
        couts = [json.loads(x) for x in appels.read_text(encoding="utf-8").splitlines() if x]
        resume.update(
            config=args.config,
            passe=args.passe,
            cout_facture_usd=round(sum(c.get("cout_usd") or 0.0 for c in couts), 6),
            appels=len(couts),
            appels_sans_cout=sum(1 for c in couts if c.get("cout_usd") is None),
            modeles_servis=sorted({c.get("modele_servi") or "?" for c in couts}),
        )
        (sortie / "resume.json").write_text(
            json.dumps(resume, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(
            f"{args.config} p{args.passe} {slug} : {resume['issue']}, {resume['tours']} tours, "
            f"{resume['cout_facture_usd']:.4f} $, {resume.get('duree_s')} s",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
