"""Le prompt système de l'agent d'ingestion, et son premier message.

Principe directeur : **le skill est la doctrine, ce module n'est que le
harnais**. `.claude/skills/ingest-aide/SKILL.md` est chargé TEL QUEL, sans une
ligne réécrite. Ce qu'on ajoute autour tient en six blocs, dont un seul
(« Adaptations au harnais ») est de la prose neuve — et il ne dit rien de ce
qu'il faut extraire, seulement par quel outil passer.

Deux blocs sont GÉNÉRÉS depuis le code plutôt que rédigés :

  - le condensé de schéma vient des modèles Pydantic d'`aides_schema`. Un champ
    ajouté au schéma apparaît dans le prompt le jour même, et un champ retiré
    en disparaît — une table recopiée à la main aurait dérivé au premier
    refactor, et le modèle aurait écrit du YAML que le lint refuse.
  - l'index des faits remplace les ~50 000 jetons de `facts.yaml` par une ligne
    par fait (~12 500 pour 247 faits). L'agent cherche dans l'index, puis
    demande le détail du seul fait qui l'intéresse. Les questions n'y sont PAS
    tronquées : c'est leur formulation exacte qui permet de reconnaître qu'un
    fait existant répond déjà au besoin, et donc de ne pas en proposer un
    treizième doublon.

Le tout pèse ~23 500 jetons.

L'ordre est stable et le contenu ne dépend pas du slug : le préfixe se met en
cache chez le fournisseur, et 60 tours sur la même aide ne le repayent qu'une
fois.
"""

from __future__ import annotations

import re
import sys
import textwrap
from pathlib import Path
from typing import Any, Literal, Union, get_args, get_origin

import yaml
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from aides_schema import (
    CATEGORIES,
    FAIT_PORTEUR,
    OPS_BY_FACT_TYPE,
    OPS_BY_FIELD_TYPE,
    RAISONS,
    TYPES,
    Aide,
    AppliesIf,
    Calendrier,
    Condition,
    Cumul,
    Document,
    FactDef,
    FactOption,
    Financement,
    Flags,
    HardFilters,
    Levier,
    Source,
    charger_yaml,
    load_all_aides,
)
from aides_schema import FIELD_REGISTRY as _FIELD_REGISTRY
from labels import (
    DEPARTEMENT_LABELS,
    ETAT_LABELS,
    OWNERSHIP_LABELS,
    PROTECTION_LABELS,
    REGION_LABELS,
    TRAVAUX_LABELS,
)
from pieces_schema import load_pieces

from .atelier import BACKEND_DIR, Atelier

RACINE = BACKEND_DIR.parent
SKILL_PATH = RACINE / ".claude" / "skills" / "ingest-aide" / "SKILL.md"
README_PATH = BACKEND_DIR / "data" / "README.md"
TYPING_PATH = BACKEND_DIR / "data" / "TYPING.md"

# L'aide de référence servie à l'agent quand aucune aide du même préfixe n'est
# disponible : 34 conditions typées, un `applies_if` de périmètre, un
# calendrier daté, des `documents_requis` avec liens. Un exemple complet vaut
# mieux qu'un paragraphe de consignes sur le format attendu.
AIDE_REFERENCE_DEFAUT = "hdf-jardins-en-scene"

# Bonus de richesse accordé à une aide du même financeur : elle partage les
# conventions locales (nom court, tournures du règlement, structure des
# documents), ce qui vaut quelques mécanismes de schéma — mais pas tous, et
# délibérément MOINS que la prime d'un `applies_if` : le périmètre d'une aide
# est plus coûteux à rater qu'un nom court mal tourné.
PRIME_MEME_PREFIXE = 3

# Au-delà, un gabarit coûte plus de contexte qu'il n'apprend de format.
TAILLE_MAX_GABARIT = 40_000

# Les deux endroits où un YAML se coupe sans se casser : le début d'une clé de
# premier niveau, et le début d'un élément de liste (à n'importe quel niveau).
FRONTIERE_YAML = re.compile(r"^(?:[A-Za-z_][\w.-]*:|\s*-\s)")


# ---------------------------------------------------------------------------
# Découpe de markdown
# ---------------------------------------------------------------------------

_TITRE_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.M)


def _normaliser_titre(titre: str) -> str:
    """Compare des titres sans se soucier des accents de balisage.

    « ## `effect` » et « ## effect » doivent désigner la même section : le
    backtick est de la mise en forme, pas de l'identité.
    """
    return re.sub(r"[`*_]", "", titre).strip().lower()


def section(md: str, titre: str) -> str:
    """Une section markdown, de son titre jusqu'au prochain de niveau ≤.

    Le titre se donne en préfixe : « Jurisprudence » retrouve « ###
    Jurisprudence des retypages (chantier 2026-08, 449 gates → 1) », dont on ne
    veut surtout pas recopier le compteur dans le code.
    """
    cible = _normaliser_titre(titre)
    for m in _TITRE_RE.finditer(md):
        if not _normaliser_titre(m.group(2)).startswith(cible):
            continue
        niveau = len(m.group(1))
        for suivant in _TITRE_RE.finditer(md, m.end()):
            if len(suivant.group(1)) <= niveau:
                return md[m.start() : suivant.start()].rstrip() + "\n"
        return md[m.start() :].rstrip() + "\n"
    raise KeyError(f"section introuvable : {titre!r}")


def sans_front_matter(md: str) -> str:
    """Retire l'en-tête YAML d'un fichier de skill.

    L'en-tête (`name`, `description`) sert au dispatcher de Claude Code, pas au
    modèle : le laisser lui apprendrait qu'il est un skill invocable, ce qu'il
    n'est pas ici.
    """
    if md.startswith("---"):
        fin = md.find("\n---", 3)
        if fin != -1:
            return md[fin + 4 :].lstrip("\n")
    return md


def titres(md: str) -> list[str]:
    """Tous les titres d'un markdown — sert aux tests de non-dérive."""
    return [m.group(2).strip() for m in _TITRE_RE.finditer(md)]


# ---------------------------------------------------------------------------
# Condensé du schéma, généré depuis les modèles Pydantic
# ---------------------------------------------------------------------------

MODELES: tuple[type[BaseModel], ...] = (
    Aide,
    Condition,
    AppliesIf,
    Source,
    Financement,
    Cumul,
    Calendrier,
    HardFilters,
    Document,
    Flags,
    FactDef,
    FactOption,
    Levier,
)


def _nom_type(annotation: Any) -> str:
    """Rend une annotation en une chaîne courte et lisible par un modèle."""
    if annotation is type(None):
        return "null"
    origine = get_origin(annotation)
    if origine is Literal:
        return " | ".join(repr(v) for v in get_args(annotation))
    if origine in (Union, type(int | str)):
        parties = [_nom_type(a) for a in get_args(annotation) if a is not type(None)]
        rendu = " | ".join(parties)
        return f"{rendu} | null" if type(None) in get_args(annotation) else rendu
    if origine in (list, tuple, set, frozenset):
        args = get_args(annotation)
        interieur = ", ".join(_nom_type(a) for a in args) if args else ""
        return f"{getattr(origine, '__name__', 'list')}[{interieur}]"
    if origine is dict:
        return "dict"
    nom = getattr(annotation, "__name__", None)
    return nom or str(annotation).replace("typing.", "")


def _defaut(champ: Any) -> str:
    if champ.is_required():
        return "OBLIGATOIRE"
    valeur = champ.get_default(call_default_factory=True)
    if isinstance(valeur, BaseModel):
        return f"{type(valeur).__name__}()"
    return repr(valeur)


def _modele_en_lignes(modele: type[BaseModel]) -> list[str]:
    lignes = [f"{modele.__name__} :"]
    for nom, champ in modele.model_fields.items():
        ligne = f"  {nom}: {_nom_type(champ.annotation)} = {_defaut(champ)}"
        if champ.description:
            ligne += f"   # {' '.join(champ.description.split())}"
        lignes.append(ligne)
    return lignes


def _codes(nom: str, mapping: dict[str, str], limite: int | None = None) -> str:
    cles = list(mapping)
    if limite is not None and len(cles) > limite:
        cles = cles[:limite] + [f"… ({len(mapping)} codes au total)"]
    return f"{nom} : {', '.join(cles)}"


def _lignes_codes(codes: list[str], largeur: int = 88) -> list[str]:
    """Une liste de codes repliée, pour ne pas rendre une ligne de 900 caractères."""
    lignes: list[str] = []
    courante = "  "
    for code in codes:
        if len(courante) + len(code) + 2 > largeur:
            lignes.append(courante.rstrip().rstrip(","))
            courante = "  "
        courante += f"{code}, "
    if courante.strip():
        lignes.append(courante.rstrip().rstrip(","))
    return lignes


def condense_schema() -> str:
    """Le schéma exact, en ~3 000 jetons, toujours synchrone avec le code."""
    blocs: list[str] = [
        "## Schéma exact (généré depuis backend/aides_schema.py)",
        "",
        "Un champ absent de cette table N'EXISTE PAS : `model_config` interdit",
        "les clés supplémentaires, et le lint refusera le fichier.",
        "",
        "```",
    ]
    for modele in MODELES:
        blocs.extend(_modele_en_lignes(modele))
        blocs.append("")
    blocs.append("```")
    blocs.extend(
        [
            "",
            "### Vocabulaires fermés",
            "",
            "```",
            f"categorie      : {', '.join(CATEGORIES)}",
            f"type           : {', '.join(TYPES)}",
            f"raison         : {', '.join(RAISONS)}",
            "kind           : untyped, auto, user_fact, discretionary, info, manual_check",
            "effect         : gate, modulateur, info",
            "",
            "Opérateurs de prédicat autorisés par type de FAIT :",
            *(f"  {t:<12} {', '.join(sorted(ops))}" for t, ops in sorted(OPS_BY_FACT_TYPE.items())),
            "",
            "Opérateurs autorisés par type de CHAMP (kind: auto) :",
            *(
                f"  {t:<12} {', '.join(sorted(ops))}"
                for t, ops in sorted(OPS_BY_FIELD_TYPE.items())
            ),
            "Combinateurs : any_of, all_of (liste de prédicats)",
            "",
            "Chemins autorisés pour `field` (FIELD_REGISTRY) :",
            *(f"  {chemin:<34} {spec['type']}" for chemin, spec in sorted(_FIELD_REGISTRY.items())),
            "",
            "Identifiants autorisés pour `documents_requis[].piece_id` (référentiel",
            "data/pieces.yaml). TOUTE AUTRE VALEUR EST REFUSÉE par le schéma, et le",
            "champ est FACULTATIF : omettre `piece_id` vaut infiniment mieux que d'en",
            "inventer un — la plupart des pièces sont propres à une seule aide et n'ont",
            "rien à réutiliser.",
            *_lignes_codes(sorted(load_pieces())),
            "",
            "Codes des hard_filters :",
            f"  {_codes('protections', PROTECTION_LABELS)}",
            f"  {_codes('proprietaires', OWNERSHIP_LABELS)}",
            f"  {_codes('travaux', TRAVAUX_LABELS)}",
            f"  {_codes('etats_conservation', ETAT_LABELS)}",
            f"  {_codes('regions', REGION_LABELS)}",
            f"  {_codes('departements', DEPARTEMENT_LABELS, limite=12)}",
            "```",
        ]
    )
    return "\n".join(blocs)


# ---------------------------------------------------------------------------
# Index des faits
# ---------------------------------------------------------------------------


def index_faits(facts: dict[str, FactDef], pending: dict[str, FactDef]) -> str:
    """Une ligne par fait — l'ontologie sans ses 50 000 jetons.

    Le détail complet (help, levier, libellés des options) se demande fait par
    fait avec `detail_fait`. Charger `facts.yaml` en entier coûterait la moitié
    d'une fenêtre de contexte pour trois faits réellement utilisés.
    """
    lignes = [
        "## Faits de l'ontologie (data/facts.yaml)",
        "",
        "Une ligne par fait : `id  type  scope  « question »  [options]`. Les faits",
        "marqués ⏳ sont PROPOSÉS (facts_pending.yaml) et non encore approuvés — ils",
        "sont utilisables tels quels. Pour le détail d'un fait (aide, levier, libellés",
        "des options), appeler `detail_fait`. Pour en trouver un, `chercher_faits`.",
        "",
        "```",
    ]
    for cle in sorted({**facts, **pending}):
        fait = pending.get(cle) or facts[cle]
        marque = "⏳ " if cle in pending else "   "
        options = ""
        if fait.options:
            ids = [o.id + ("*" if o.unknown else "") for o in fait.options]
            options = "  [" + ", ".join(ids) + "]"
        unite = f" ({fait.unit})" if fait.unit else ""
        # Deux marques distinctes : le SKILL interdit de gater un fait à levier,
        # SAUF quand le levier garde la question. Une marque unique faisait
        # renoncer l'agent à gater `ouverture_public` et les autres critères
        # maintenus le 2026-09-23.
        levier = ""
        if fait.levier:
            levier = (
                "  ⚡levier, question maintenue (gate permis)"
                if fait.levier.question_maintenue
                else "  ⚡levier (jamais de gate)"
            )
        lignes.append(
            f"{marque}{cle}  {fait.type}{unite}  {fait.scope}  "
            f"« {' '.join(fait.question.split())} »{options}{levier}"
        )
    lignes.append("```")
    lignes.append("")
    lignes.append("`*` sur une option = réponse « je ne sais pas » (le moteur la traite")
    lignes.append("comme un fait inconnu, jamais comme un « non »).")
    lignes.append("")
    lignes.append("Un fait `boolean` peut lui aussi porter des options : la question offre")
    lignes.append("alors plus de deux réponses, chacune envoyant true, false ou « rien »")
    lignes.append("aux prédicats. Cela NE CHANGE RIEN au typage d'une condition — un gate")
    lignes.append("sur un booléen se pose toujours `{eq: true}` ou `{eq: false}`.")
    return "\n".join(lignes)


# ---------------------------------------------------------------------------
# Adaptations au harnais
# ---------------------------------------------------------------------------

ADAPTATIONS = """\
## Adaptations au harnais (à lire APRÈS le skill)

Tu ne tournes pas dans Claude Code : tu n'as ni shell, ni Read, ni Agent, ni
WebSearch. Tu as les outils ci-dessous, et rien d'autre. Chaque étape du skill
s'y traduit ainsi :

| Étape du skill | Ce que tu fais ici |
|---|---|
| 0 — Contexte | RIEN À FAIRE : README, TYPING, schéma et index des faits sont déjà ci-dessous. N'essaie pas de lire des fichiers. |
| 1 — Sources et snapshots | `snapshotter` chaque URL, puis `lire_snapshot` pour lire l'archive. `lister_snapshots` te dit ce qui est déjà là. |
| 2 — Extraction | `ecrire_aide` avec le YAML COMPLET du fichier. Il valide, écrit, et te rend un audit de tes citations. |
| 3 — Lint | `lint` (mono-slug, citations comprises). Il doit sortir vert. |
| 4 — Vérification adversariale | `verification_adversariale`, UNE fois, après un lint vert. |
| 5 — Fiche de review | `ecrire_review`, puis un dernier message SANS appel d'outil pour clore. |

Règles du harnais :

- **Un seul slug.** Tous les outils sont bornés à l'aide en cours. Tu ne peux
  écrire aucun autre fichier, et aucun chemin ne sort de son dossier.
- **`explorer_url` n'est JAMAIS citable.** Sa sortie porte le bandeau
  « NON CITABLE » : elle sert à repérer une page ou à suivre un lien, elle est
  tronquée et n'est archivée nulle part. Une `quote` ne peut venir que d'un
  `lire_snapshot`. Citer depuis `explorer_url`, c'est produire une citation que
  le lint déclarera introuvable.
- **`proposer_fait` est la seule voie vers un fait nouveau.** N'écris jamais un
  `fact:` qui n'est ni dans l'index ci-dessous ni proposé par toi dans ce run.
- **`conditions_du_fait` liste tout ce qui cite un fait** (gates, `applies_if`,
  `pertinent_si`), avec effet, prédicat et texte.
- **`proposer_reformulation` est une exception**, quand l'outil est dans ta
  liste : une nouvelle tournure de la question d'un fait que tu réutilises,
  jamais un autre sens. Ton aide reste typée sur la question actuelle.
- **`ecrire_aide` réécrit tout le fichier** à chaque appel : envoie toujours le
  YAML entier, jamais un fragment. Tu peux l'appeler autant de fois que tu veux.
- **Ton budget est compté.** Tu as un nombre de tours limité. Lis les snapshots
  par tranches utiles plutôt que page par page, et n'appelle pas deux fois le
  même outil avec les mêmes arguments. Si tu reçois « BUDGET ÉPUISÉ », arrête
  l'extraction, lance `lint`, écris la review avec l'état atteint et dis-y ce
  qui manque.
- **Tu ne commites rien et tu ne charges rien en base.** Ta réponse finale est
  la fiche de review, écrite avec `ecrire_review`.
"""


# ---------------------------------------------------------------------------
# Assemblage
# ---------------------------------------------------------------------------


def prompt_systeme(
    facts: dict[str, FactDef],
    pending: dict[str, FactDef],
    *,
    skill_path: Path = SKILL_PATH,
    readme_path: Path = README_PATH,
    typing_path: Path = TYPING_PATH,
) -> str:
    """Les six blocs, dans un ordre qui ne change pas d'un run à l'autre."""
    skill = sans_front_matter(skill_path.read_text(encoding="utf-8"))
    readme = readme_path.read_text(encoding="utf-8")
    typage = typing_path.read_text(encoding="utf-8")

    sections_typing = [
        "L'arbre de décision",
        "`effect`",
        "`applies_if`",
        "`applies_if` au niveau de l'AIDE",
        # Le SKILL renvoie à ces trois sections et l'agent n'a pas le droit de
        # lire un fichier : sans elles, `raison`, `familles` et
        # `hard_filters.travaux` se remplissaient au jugé (18 `raison` de
        # valorisation incohérentes, 409 aides sur 475 sans cadrage des travaux).
        "`raison`",
        "`familles`",
        "Les critères structurés",
        "Puces composites",
        "Proposer un nouveau fait",
        "`levier`",
        "Conventions de `notes`",
        "Format de la fiche de review",
    ]
    return "\n\n---\n\n".join(
        [
            skill.rstrip(),
            ADAPTATIONS.rstrip(),
            "# Extraits de backend/data/README.md\n\n"
            + section(readme, "Workflow").rstrip()
            + "\n\n"
            + section(readme, "Typologie des conditions").rstrip(),
            "# Extraits de backend/data/TYPING.md\n\n"
            + "\n\n".join(section(typage, t).rstrip() for t in sections_typing),
            condense_schema(),
            index_faits(facts, pending),
        ]
    )


def prompt_initial(
    *,
    slug: str,
    url: str,
    atelier: Atelier,
    urls_pdf: tuple[str, ...] = (),
    territoire: str | None = None,
    famille: str | None = None,
    beneficiaires: str | None = None,
    note: str | None = None,
    departements: tuple[str, ...] = (),
    doublon_probable: str | None = None,
    source_unique_vulgarisation: bool = False,
    faits_du_run: tuple[str, ...] = (),
    existante: str | None = None,
    aide_reference: str | None = None,
) -> str:
    """Le premier message utilisateur : la commande de travail.

    `existante` (le YAML actuel) n'est fourni QUE pour une ré-extraction. Le
    donner sur une aide neuve inviterait le modèle à le recopier ; l'omettre
    sur une ré-extraction lui ferait perdre les conditions que la source ne
    porte plus mais que la review doit signaler.

    `faits_du_run` est ici et NON dans le prompt système, et c'est délibéré :
    le système pèse ~23 000 jetons, il est identique pour toutes les aides, et
    c'est ce qui fait tenir le cache de préfixe du fournisseur — le premier
    poste de dépense du pipeline. Y mettre une liste qui change à chaque aide
    invaliderait le cache à chaque appel.
    """
    morceaux = [
        f"Ingère l'aide `{slug}`.",
        "",
        f"- Source principale : {url}",
    ]
    for pdf in urls_pdf:
        morceaux.append(f"- Document à snapshoter aussi : {pdf}")
    if territoire:
        morceaux.append(f"- Territoire : {territoire}")
    if famille:
        morceaux.append(f"- Famille pressentie à la prospection : {famille}")
    if beneficiaires:
        morceaux.append(
            "- Bénéficiaires lus à la prospection (à vérifier sur la source, à typer en gate "
            f"`{FAIT_PORTEUR}`) : {beneficiaires}"
        )
    if departements:
        morceaux.append(
            f"- Départements couverts par ce guichet : {', '.join(departements)} — écris-les "
            f"tous dans `hard_filters.departements: {list(departements)}`. Un seul fichier "
            "pour le dispositif, pas un par département."
        )
    if note:
        morceaux.append(f"- Note de prospection (indicative, à vérifier sur la source) : {note}")
        morceaux.append(
            "  Cette note dit À QUELLE CONDITION un propriétaire de monument est concerné. "
            "Sauf si l'aide relève de `restauration_bati`, TRADUIS-LA en `applies_if` de "
            "périmètre — une condition, branchée en premier, qui écarte l'aide quand le "
            "projet n'est pas de ce type. C'est ce qui garde le questionnaire court malgré "
            "la largeur thématique du catalogue."
        )
    if doublon_probable:
        morceaux.append(
            f"- ⚠ Doublon probable de `{doublon_probable}`. Si la source décrit bien le MÊME "
            "dispositif, ne crée pas un second fichier : dis-le en tête de la fiche de "
            "review sous « ⚠ À trancher », et arrête-toi là."
        )
    if source_unique_vulgarisation:
        morceaux.append(
            "- ⚠ Page de VULGARISATION : elle présente le dispositif sans en porter le "
            "règlement. Cherche le règlement d'intervention ou le cadre d'intervention "
            "(lien « règlement », « cadre d'intervention », « délibération ») et snapshote-le "
            "AVANT d'extraire. Une condition tirée d'une page de présentation n'est pas "
            "citable."
        )
    morceaux.append(f"- Fichier à écrire : {atelier.relatif(atelier.yaml_path)}")

    if faits_du_run:
        morceaux += [
            "",
            "Faits proposés depuis le début de ce run (⏳ non approuvés, mais utilisables",
            "TELS QUELS dans une condition `user_fact` — ne les repropose pas sous un autre",
            "nom, c'est exactement comme ça que les doublons `_v2` sont nés) :",
            *(f"  - {cle}" for cle in faits_du_run),
        ]

    deja = atelier.snapshots()
    if deja:
        morceaux += [
            "",
            "Snapshots déjà archivés pour cette aide (lisibles avec `lire_snapshot`) :",
            *(f"  - {p.name}" for p in deja),
        ]

    if existante:
        morceaux += [
            "",
            "C'est une RÉ-EXTRACTION. Version actuelle du fichier — à comparer à la",
            "source, pas à recopier ; toute condition que la source ne porte plus doit",
            "être signalée dans la review (cf. étape 5 du skill) :",
            "",
            "```yaml",
            existante.rstrip(),
            "```",
        ]

    if aide_reference:
        morceaux += [
            "",
            "Exemple d'une aide récente correctement ingérée — pour le FORMAT (structure,",
            "granularité des conditions, style des `text`, usage des champs), jamais pour",
            "son contenu :",
            "",
            "```yaml",
            aide_reference.rstrip(),
            "```",
        ]

    morceaux += [
        "",
        f"Commence par `snapshotter` la source principale ({url}), puis lis l'archive",
        "avec `lire_snapshot`. Termine par `ecrire_review`.",
    ]
    return "\n".join(morceaux)


def richesse_doctrinale(aide: Aide) -> int:
    """Combien de mécanismes du schéma cette aide DÉMONTRE.

    Un gabarit n'apprend au modèle que ce qu'il contient. Mesuré en vrai
    (or-glm sur hdf-jardins-en-scene, 2026-09-06) : le gabarit servi était une
    aide sans `applies_if` et sans un seul `modulateur` — le modèle n'a produit
    ni l'un ni l'autre, et on lui a reproché deux absences qu'il n'avait aucun
    moyen de deviner. Un exemple sert à montrer les mécanismes, pas à être
    récent : c'est donc la COUVERTURE qu'on maximise, jamais la date.
    """
    points = 0
    if aide.applies_if:
        points += 4  # le mécanisme le plus coûteux à rater, et le plus rare
    if aide.financement.assiette:
        points += 2
    if aide.cumul.plafond_public_pct is not None or aide.cumul.exclusions:
        points += 1
    if aide.demarche:
        points += 1
    if any(d.url or d.piece_id or not d.obligatoire for d in aide.documents_requis):
        points += 1
    if any(c.derogation_possible for c in aide.conditions):
        points += 2
    if any(c.applies_if for c in aide.conditions):
        points += 2
    # Un point par couple (kind, effect) distinct : c'est la mesure directe de
    # ce que le gabarit sait montrer de la typologie. `manual_check` en est
    # exclu — le compter récompensait l'anti-patron (cf. le malus ci-dessous).
    points += len({(c.kind, c.effect) for c in aide.conditions if c.kind != "manual_check"})

    # Des modulateurs ATOMIQUES sont le mécanisme que les runs réels ratent le
    # plus : mesuré deux fois sur hdf-jardins-en-scene, les 11 critères de
    # sélection de la source ont été repliés en 2 conditions composites typées
    # `info`, donc sans effet sur le diagnostic. Un gabarit qui en montre
    # plusieurs est le seul endroit où le modèle apprend la scission.
    points += min(sum(1 for c in aide.conditions if c.effect == "modulateur"), 5)

    # Le `manual_check` est ce que la doctrine cherche à ÉLIMINER (objectif
    # zéro, cf. CLAUDE.md). Un gabarit qui en porte treize enseigne exactement
    # ce qu'on veut résorber : il COÛTE des points. Sans ce malus, la richesse
    # servait `hdf-prac-projets-rayonnement-culturel` (13 manual_check, 39
    # `info`, 1 seul modulateur) — mieux que le précédent sur `applies_if`,
    # pire sur le typage, et la sortie du modèle a suivi les deux fois.
    points -= min(sum(1 for c in aide.conditions if c.kind == "manual_check"), 6)
    return points


def tronquer_gabarit(texte: str) -> str:
    """Le gabarit raccourci, mais toujours un document YAML valide.

    Une coupe à l'octet tombait au milieu d'un scalaire cité (vu le
    2026-09-18 sur `cvl-filieres-locales`, 55 k : le gabarit servi ne se
    parsait plus). Un gabarit qui ne se charge pas enseigne une syntaxe
    cassée — c'est exactement ce qu'il est là pour éviter.

    On coupe donc à une FRONTIÈRE : le début d'une clé de premier niveau ou
    d'un élément de liste, la plus tardive qui tienne sous la limite et dont
    le document tronqué se parse encore. Couper sur un élément de liste plutôt
    que sur la seule clé de premier niveau importe : `conditions` est le
    dernier champ et le plus long d'une fiche, et s'arrêter avant lui servirait
    un gabarit sans une seule condition — soit tout ce qu'il a à montrer.
    """
    if len(texte) < TAILLE_MAX_GABARIT:
        return texte
    frontieres: list[int] = []
    position = 0
    for ligne in texte.splitlines(keepends=True):
        if position > TAILLE_MAX_GABARIT:
            break
        if position and FRONTIERE_YAML.match(ligne):
            frontieres.append(position)
        position += len(ligne)
    for coupe in reversed(frontieres):
        morceau = texte[:coupe]
        try:
            charger_yaml(morceau)
        except yaml.YAMLError:
            continue
        return morceau
    return texte[:TAILLE_MAX_GABARIT]


def sans_bloc_fiche(texte: str) -> str:
    """Le YAML d'une aide sans son bloc `fiche:` ni l'en-tête commenté qui le précède.

    La fiche est rédigée APRÈS l'ingestion, par `rediger_fiches.py` et le skill
    `rediger-fiche`. Servie dans le gabarit (12 000 caractères sur 31 000 au
    2026-09-28), elle apprenait à l'agent à en improviser une, sans le skill
    d'écriture, et `rediger_fiches` refuse ensuite de réécrire une fiche qui
    n'est pas le dernier bloc du fichier.
    """
    lignes = texte.splitlines(keepends=True)
    debut = next((i for i, li in enumerate(lignes) if li.startswith("fiche:")), None)
    if debut is None:
        return texte
    fin = next(
        (j for j in range(debut + 1, len(lignes)) if re.match(r"[A-Za-z_]", lignes[j])),
        len(lignes),
    )
    while debut > 0 and lignes[debut - 1].startswith("#"):
        debut -= 1
    return "".join(lignes[:debut] + lignes[fin:]).rstrip() + "\n"


# Ce qui, dans le choix d'un gabarit, ne dépend pas de l'aide en cours : les
# mécanismes que chaque aide démontre et sa richesse doctrinale. Seule la prime
# de préfixe en dépend. Le recalculer à chaque appel coûtait 596 × 596
# évaluations de `richesse_doctrinale` pour un passage sur tout le catalogue
# (7 s pour chacun des tests de gabarit). Mis de côté par dossier, avec le
# catalogue dont il vient : si `load_all_aides` rend un autre objet (cache
# vidé), on recalcule.
_CLASSEMENTS: dict[Path, tuple[dict[str, Aide], list[tuple[tuple[int, ...], int, str]]]] = {}


def _classement(aides_dir: Path) -> list[tuple[tuple[int, ...], int, str]]:
    """[(mécanismes démontrés, richesse, slug)] pour chaque aide du catalogue."""
    # `load_all_aides` est mis en cache par `aides_schema` : sans lui, chaque
    # appel reparsait les 215 fichiers du catalogue, soit 21 500 lectures pour
    # un lot de cent aides (et 4 minutes pour un seul test).
    catalogue = load_all_aides(aides_dir)
    connu = _CLASSEMENTS.get(aides_dir)
    if connu is not None and connu[0] is catalogue:
        return connu[1]
    lignes = [
        (
            (
                1 if aide.applies_if else 0,
                1 if aide.hard_filters.travaux else 0,
                1 if aide.familles else 0,
                1
                if any(c.fact == FAIT_PORTEUR and c.effect == "gate" for c in aide.conditions)
                else 0,
                1 if any(c.effect == "modulateur" for c in aide.conditions) else 0,
                1 if any(c.levier for c in aide.conditions) else 0,
            ),
            richesse_doctrinale(aide),
            autre,
        )
        for autre, aide in catalogue.items()
    ]
    _CLASSEMENTS[aides_dir] = (catalogue, lignes)
    return lignes


def choisir_aide_reference(slug: str, aides_dir: Path) -> tuple[str, str] | None:
    """(slug, YAML) du meilleur gabarit disponible pour ce slug.

    Le classement est LEXICOGRAPHIQUE : `applies_if`, puis
    `hard_filters.travaux`, puis `familles`. Un gabarit qui porte un périmètre
    bat tout gabarit qui n'en porte pas, quelle que soit sa richesse par
    ailleurs ; à périmètre égal celui qui montre un CADRAGE des travaux
    l'emporte ; à cadrage égal, celui qui montre une FAMILLE. C'est le mécanisme le plus coûteux à rater (sans
    lui, les conditions d'une aide d'un autre métier polluent le questionnaire
    de tout le monde) et le seul que le modèle ne peut pas deviner. Le laisser
    en simple bonus pondéré ne suffisait pas : le bonus « modulateurs » de
    `richesse_doctrinale` le dépassait, et 19 slugs sur 215 retombaient sur un
    gabarit sans périmètre.

    `hard_filters.travaux` est venu en second le 2026-09-17, pour la même raison
    et après le même constat : AUCUN des 405 gabarits servis n'en portait, et le
    champ n'était rempli que sur 42 aides du catalogue. Le lot Grand Est y a
    laissé 88 aides sans cadrage dans le tronc commun d'une commune des Vosges —
    une aide qui ne finance qu'une plantation ou une desserte forestière n'avait
    aucun moyen de dire qu'elle ne finance pas une toiture. Troisième fois que le
    même défaut se paie (`applies_if`, `modulateur`, puis celui-ci) : ce que le
    gabarit ne montre pas, le modèle ne le produit pas.

    `familles` est venu en troisième, le même jour et pour la même raison : 21 %
    du catalogue seulement, alors que le champ est explicitement demandé à
    l'extraction (SKILL.md, étape 2). C'est la leçon la plus dure de ces trois
    passages — `applies_if`, que l'étape 2 ne demande NULLE PART, est le mieux
    rempli des trois (44 %) parce qu'il est le seul que le gabarit garantissait.
    Le gabarit ne fait pas que compléter la consigne : il l'emporte sur elle.

    Le GATE BÉNÉFICIAIRES est venu en quatrième, le 2026-09-17, pour la
    quatrième fois la même raison : 37 aides du lot Grand Est gataient un fait
    d'entreprise sans dire qui pouvait déposer, et posaient donc leurs questions
    de PME à toutes les communes. Un gabarit qui montre la traduction de la puce
    « Bénéficiaires » en gate `in` sur `statut_juridique_porteur` est la seule
    manière de la rendre évidente au modèle — le lint la refuse désormais, mais
    un refus arrive après coup, un gabarit avant.

    Le MODULATEUR est venu en cinquième, le 2026-09-22, et c'est la cinquième
    fois la même leçon. Il n'était qu'un bonus pondéré dans
    `richesse_doctrinale` — exactement le montage qui avait échoué pour
    `applies_if` — et la prime de préfixe territorial le dépassait : une fois le
    catalogue réduit de 1079 à 547 aides, les treize slugs du Bas-Rhin ont tous
    reçu le même gabarit sans un seul `modulateur`, parce qu'il était le plus
    riche des 67 restants. Un gabarit sans modulateur n'enseigne pas la scission
    d'un critère composite, et le modèle replie alors onze critères de sélection
    en deux conditions `info` sans effet sur le diagnostic.

    Le LEVIER est venu en sixième, le 2026-09-28 : la repasse critère /
    démarche du 2026-09-23 a retypé à la main 340 conditions posées en question
    sur une démarche faisable avant le dépôt. Un gabarit qui montre un
    `manual_check` + `info` citant son `levier` est la forme à imiter.

    À famille égale, la RICHESSE DOCTRINALE départage, parce qu'un gabarit
    pauvre enseigne la pauvreté (cf. `richesse_doctrinale`), avec une prime au
    même préfixe territorial (une aide du même financeur partage ses
    conventions — nom court, tournures du règlement, structure des documents).

    Le catalogue ENTIER concourt : un gabarit local pauvre perd contre un
    gabarit riche d'ailleurs. Sans cette mise en concurrence, ingérer une aide
    HDF servait un gabarit sans `applies_if` — parce que la seule aide HDF qui
    en porte un est justement celle qu'on est en train d'ingérer.

    Le fichier de l'aide en cours est évidemment exclu.
    """
    prefixe = slug.split("-")[0]
    meilleur: tuple[tuple[int | str, ...], str] | None = None
    for criteres, richesse, autre in _classement(aides_dir):
        if autre == slug:
            continue
        note = richesse + (PRIME_MEME_PREFIXE if autre.startswith(f"{prefixe}-") else 0)
        # Le slug termine la clé : à note égale, le choix doit être le MÊME
        # d'un passage à l'autre, sinon le préfixe de cache ne mord plus.
        cle = (*criteres, note, autre)
        if meilleur is None or cle > meilleur[0]:
            meilleur = (cle, autre)
    if meilleur is None:
        return None
    chemin = aides_dir / f"{meilleur[1]}.yaml"
    texte = sans_bloc_fiche(chemin.read_text(encoding="utf-8"))
    # Un gabarit énorme mangerait la fenêtre de contexte pour rien ; à ce
    # stade il n'en reste qu'un à mesurer, la troncature est donc gratuite.
    return meilleur[1], tronquer_gabarit(texte)


def estimer_jetons(texte: str) -> int:
    """Ordre de grandeur pour `--dry-run` : ~3,6 caractères par jeton en français."""
    return round(len(texte) / 3.6)


def apercu(texte: str, largeur: int = 100) -> str:
    return textwrap.shorten(" ".join(texte.split()), width=largeur, placeholder="…")


__all__ = [
    "ADAPTATIONS",
    "AIDE_REFERENCE_DEFAUT",
    "MODELES",
    "README_PATH",
    "SKILL_PATH",
    "TYPING_PATH",
    "apercu",
    "choisir_aide_reference",
    "condense_schema",
    "estimer_jetons",
    "index_faits",
    "prompt_initial",
    "prompt_systeme",
    "sans_front_matter",
    "section",
    "titres",
    "tronquer_gabarit",
]
