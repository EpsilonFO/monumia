"""
Étage D : la fiche reflète-t-elle FIDÈLEMENT et COMPLÈTEMENT sa source ?

    cd backend && uv run python scripts/veille_audit.py --report-only
    cd backend && uv run python scripts/veille_audit.py --limit 10 --dry-run
    cd backend && uv run python scripts/veille_audit.py --limit 10
    cd backend && uv run python scripts/veille_audit.py <slug> [<slug>...] --force

La veille (`veille_aides.py`) détecte les CHANGEMENTS de source : si
`/ingest-aide` a raté ou déformé une condition, la source ne bouge pas, le diff
est vide, et l'erreur reste invisible pour toujours. Cet outil répond à la
question complémentaire : il compare l'intégralité des critères de la source
avec les conditions de la fiche, propose ce qui manque, signale ce qui diverge.

Pourquoi PAS d'ancrage sur le diff. `veille_apply.check_ancrage` existe
précisément pour refuser une proposition qui ne décrit pas un changement de la
source. Le mandat de l'audit est l'exact complémentaire — les divergences
fiche↔source SANS changement de source — donc l'ancrage est délibérément
absent, et `appliquer()` est appelé avec `diff=""`. Ce n'est pas un oubli.

Pourquoi un script séparé, et pas un étage de plus dans chaque run de veille.
L'audit est idempotent : si ni la fiche ni ses sources archivées n'ont bougé
depuis le dernier audit, le rejouer rend le même résultat et brûle des jetons.
La veille tourne souvent et doit rester bon marché ; l'audit tourne une fois
par aide, puis uniquement sur changement. C'est ce qui rend le parc
auto-correcteur pour un coût de croisière quasi nul après le backfill initial.

Sur quoi il travaille. Documents frais quand ils sont disponibles, baselines
ARCHIVÉES sinon. Une condition ratée à l'ingestion était déjà dans le snapshot
archivé : le contenu frais n'importe que pour les changements, déjà couverts
par la veille. Les ~800 quotes justifiées par des PDF non re-téléchargeables
entrent donc dans le périmètre au lieu d'être déclarées inauditables.

Trois circuits de sortie, et un seul écrit :
  - `absent` validé      → condition ajoutée en `kind: untyped` (à typer)
  - `divergent`          → rapport seulement. Le `text` d'une condition ne se
                           reformule JAMAIS automatiquement (règle du dépôt) :
                           l'humain tranche, correction manuelle ou
                           /ingest-aide.
  - fiche trop incomplète → escalade vers `ingest_aides_batch.py`, zéro écriture

Codes de sortie : 0 terminé ; 1 erreur fatale ; 2 au moins une escalade, un
échec de validation ou une aide inauditable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aides_schema import AIDES_DIR, DATA_DIR, Aide, load_aide

sys.path.insert(0, str(Path(__file__).resolve().parent))

from veille_aides import LOG_DIR, MANIFEST_PATH, REVIEWS_DIR, load_manifest, write_manifest
from veille_apply import (
    ChangementCondition,
    NouvelleCondition,
    VeilleLLMOutput,
    appliquer,
    check_quotes,
    parse_json_output,
)
from veille_collect import (
    DEFAULT_CONCURRENCY,
    DEFAULT_TIMEOUT,
    SOURCES_DIR,
    AideCollect,
    MonitoredUrl,
    collect,
)
from veille_journal import Journal, cellule, milliers, tokens_compacts
from veille_llm import (
    MAX_CHARS_DOCUMENT,
    MODELE_DEFAUT,
    REGISTRE,
    ModelSpec,
    call,
    json_schema,
    system_pour,
)
from veille_text import normalize, parse_front_matter
from veille_typage import TypageResult, section_typage, typer_toutes
from veille_update import MAX_AJOUTS_CONDITIONS, prompt_correction

# Origine inscrite dans la note des conditions ajoutées. Distincte de « veille » :
# dans six mois, c'est cette note qui dira si la condition vient d'un changement
# de règlement ou d'un trou d'ingestion rattrapé.
ORIGINE = "audit"

# Plafond d'appels par passage. Comme pour la veille, c'est un garde-fou de
# RELECTURE avant d'être un garde-fou de coût : le facteur limitant est le
# `git diff` relu à la main, pas la facture du fournisseur.
MAX_LLM_DEFAUT = 20

# Citations de `conforme` introuvables tolérées avant de rejeter le relevé.
# Écarter un `conforme` mal cité est normal — les tableaux HTML mal convertis
# s'aplatissent mal (voir `check_quotes_audit`). En écarter la moitié n'est plus
# un accident de mise en forme : c'est un relevé récité de mémoire, dont le
# silence sur le reste ne prouve rien. Plancher à 2 pour qu'un petit relevé ne
# se fasse pas rejeter sur une seule ligne de tableau.
TOLERANCE_CONFORMES_INVALIDES = 2
RATIO_CONFORMES_INVALIDES = 3


# Longueur en dessous de laquelle la garde anti-doublon ne teste que l'égalité.
# Une citation de dix caractères est « contenue » dans à peu près n'importe
# quelle autre : l'inclusion n'y prouve rien.
MIN_CHARS_INCLUSION = 20

Etat = Literal["a_jour", "ajouts", "divergences", "escalade", "echec", "inauditable", "non_audite"]

ETATS: tuple[Etat, ...] = (
    "escalade",
    "ajouts",
    "divergences",
    "echec",
    "inauditable",
    "non_audite",
    "a_jour",
)

SYMBOLES: dict[str, str] = {
    "a_jour": "✓",
    "ajouts": "→",
    "divergences": "~",
    "escalade": "✗",
    "echec": "!",
    "inauditable": "?",
    "non_audite": "·",
}

LEGENDES: dict[str, str] = {
    "a_jour": "la fiche couvre ce que la source dit",
    # `non_audite` n'est pas un verdict : c'est l'absence de verdict. Sans cet
    # état, un `--report-only` affichait « a_jour » pour des fiches que le
    # modèle n'avait jamais vues — le contraire exact de ce qu'il faut lire.
    "non_audite": "corpus constitué, modèle non appelé (`--report-only`)",
    "ajouts": "condition(s) manquante(s) ajoutée(s) en `untyped`",
    "divergences": "la fiche semble contredire la source — arbitrage humain",
    "escalade": "écart trop massif pour une retouche : ré-ingestion",
    "echec": "le modèle a répondu, la validation a refusé d'écrire",
    "inauditable": "aucun document lisible : rien à quoi comparer la fiche",
}


# ---------------------------------------------------------------------------
# Étape 1 — sélection : quand une aide doit-elle être (ré)auditée
# ---------------------------------------------------------------------------


def sha_fiche(chemin: Path) -> str:
    """Empreinte du YAML de l'aide. Change dès que la fiche est retouchée."""
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def sha_sources(slug: str) -> str:
    """Empreinte de TOUT le dossier `data/sources/<slug>` : noms et contenus.

    Une seule empreinte plutôt qu'une comparaison document par document, parce
    que l'ARRIVÉE d'un snapshot compte autant que la modification d'un
    existant : c'est le cas typique d'une source qui a bougé et vient d'être
    ré-archivée, et c'est précisément là que l'audit doit repasser.

    Le sha des documents FRAIS ne peut pas servir à la sélection : il faudrait
    les retélécharger pour le connaître, et la sélection doit pouvoir sauter
    une aide sans un seul appel réseau — c'est ce qui rend le régime de
    croisière quasi gratuit. La couverture reste bonne : un changement de source
    laisse une trace dans l'archive dès que la veille ou `/ingest-aide` y
    repasse, et l'un comme l'autre retouche la fiche au passage.
    """
    directory = SOURCES_DIR / slug
    if not directory.is_dir():
        return ""
    empreinte = hashlib.sha256()
    for chemin in sorted(directory.iterdir()):
        if not chemin.is_file():
            continue
        empreinte.update(chemin.name.encode("utf-8"))
        empreinte.update(hashlib.sha256(chemin.read_bytes()).digest())
    return empreinte.hexdigest()


def raison_audit(aide: Aide, manifest: dict, *, force: bool = False) -> str | None:
    """Pourquoi cette aide doit être (ré)auditée, ou None si elle peut être sautée."""
    if force:
        return "--force"
    entree = (manifest.get(aide.slug) or {}).get("audit")
    if not entree:
        return "jamais auditée"
    chemin = AIDES_DIR / f"{aide.slug}.yaml"
    if entree.get("sha_fiche") != sha_fiche(chemin):
        return "fiche modifiée depuis le dernier audit"
    if entree.get("sha_sources") != sha_sources(aide.slug):
        return "sources ré-archivées depuis le dernier audit"
    return None


def date_dernier_audit(slug: str, manifest: dict) -> date:
    """Date du dernier audit, `date.min` si jamais audité — l'ordre de passage."""
    valeur = ((manifest.get(slug) or {}).get("audit") or {}).get("date")
    if isinstance(valeur, date):
        return valeur
    if isinstance(valeur, str):
        try:
            return date.fromisoformat(valeur)
        except ValueError:
            return date.min
    return date.min


def selectionner(
    aides: dict[str, Aide], manifest: dict, *, force: bool = False, limit: int | None = None
) -> list[tuple[Aide, str]]:
    """Candidates à l'audit, des plus anciennement auditées aux plus récentes."""
    candidates = [
        (aide, raison)
        for aide in aides.values()
        if (raison := raison_audit(aide, manifest, force=force)) is not None
    ]
    candidates.sort(key=lambda t: (date_dernier_audit(t[0].slug, manifest), t[0].slug))
    return candidates[:limit] if limit is not None else candidates


def update_manifest_audit(manifest: dict, resultats: dict[str, AuditResult], today: date) -> dict:
    """Fusionne les audits du run dans le manifeste, sans toucher aux clés de veille.

    Le manifeste est partagé avec `veille_aides.py` : `checked_at`, `status`,
    `urls` et `maj` lui appartiennent et ne sont jamais réécrits ici. Un run
    partiel (`--limit`, liste de slugs) conserve l'entrée `audit` des aides
    qu'il n'a pas traitées.
    """
    merged = dict(manifest)
    for slug, res in resultats.items():
        if not res.trace_manifeste:
            continue
        entree = dict(merged.get(slug) or {})
        entree["audit"] = {
            "date": today.isoformat(),
            "sha_fiche": res.sha_fiche,
            "sha_sources": res.sha_sources,
            "docs": res.docs_manifeste,
            "portee": res.portee,
        }
        merged[slug] = entree
    return merged


# ---------------------------------------------------------------------------
# Étape 2 — corpus documentaire : frais + baselines
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DocAudit:
    """Un document soumis au modèle, et la version exacte sur laquelle il statue."""

    nom: str
    contenu: str
    kind: Literal["text", "pdf"]
    provenance: Literal["frais", "baseline"]
    sha256: str = ""
    url: str | None = None

    @property
    def tronque(self) -> bool:
        return len(self.contenu) > MAX_CHARS_DOCUMENT

    def entree_manifeste(self) -> dict[str, str]:
        cle = "url" if self.provenance == "frais" else "nom"
        valeur = self.url if self.provenance == "frais" else self.nom
        return {cle: valeur or self.nom, "sha256": self.sha256, "etat": self.provenance}


@dataclass
class Corpus:
    """Ce que l'audit a pu lire, et ce qu'il n'a PAS pu lire."""

    docs: list[DocAudit] = field(default_factory=list)
    # Documents attendus et absents : c'est ce qui dégrade la portée. Un « rien
    # à signaler » sur corpus incomplet se lit « rien à signaler SUR CE QUI A PU
    # ÊTRE LU », et le rapport doit le dire.
    manquants: list[str] = field(default_factory=list)

    @property
    def vide(self) -> bool:
        return not self.docs

    @property
    def portee(self) -> Literal["complet", "partiel"]:
        return "partiel" if self.manquants else "complet"

    def documents(self) -> list[tuple[str, str, str]]:
        """Forme consommée par `find_quote_in_any` et `check_quotes`."""
        return [(d.nom, d.contenu, d.kind) for d in self.docs]


def _sha_baseline(slug: str, nom: str) -> str:
    """Sha du snapshot : celui de son en-tête si connu, sinon celui du fichier.

    L'en-tête porte le sha du contenu TÉLÉCHARGÉ, directement comparable au sha
    d'un document frais. À défaut (les 109 PDF antérieurs au sidecar), le sha
    des octets archivés identifie tout aussi bien la version lue.
    """
    chemin = SOURCES_DIR / slug / nom
    if not chemin.is_file():
        return ""
    if chemin.suffix.lower() == ".md":
        meta = parse_front_matter(chemin.read_text(encoding="utf-8"))[0]
        if sha := meta.get("sha256"):
            return sha
    sidecar = chemin.with_name(chemin.name + ".meta.yaml")
    if sidecar.is_file():
        meta = yaml.safe_load(sidecar.read_text(encoding="utf-8")) or {}
        if sha := meta.get("sha256"):
            return str(sha)
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def _motif_absence(col: AideCollect, murl: MonitoredUrl) -> str:
    """Pourquoi cette URL n'a rien apporté au corpus, dit en clair au relecteur."""
    res = col.fetched.get(murl.url)
    if res is None:
        return "non téléchargée"
    if not res.ok:
        return res.error or f"HTTP {res.status}"
    # Téléchargée avec succès et pourtant absente du corpus : c'est un binaire
    # (PDF, .docx d'un règlement départemental) dont le texte ne s'extrait pas
    # au vol. Son snapshot archivé, lui, l'aurait fourni.
    return "contenu binaire non extractible" if res.is_binary else "contenu vide"


def construire_corpus(aide: Aide, col: AideCollect) -> Corpus:
    """Documents frais, complétés des baselines qu'aucun frais ne remplace.

    Une baseline dont la page a été re-téléchargée avec succès est ÉCARTÉE :
    soumettre les deux versions du même document ferait compter deux fois
    chaque critère et inviterait le modèle à confondre l'ancien et le nouveau
    règlement.
    """
    corpus = Corpus()
    # Quel snapshot archive quelle page : `monitored_urls` l'a déjà résolu à la
    # collecte. Le relire du système de fichiers ici ferait un second chemin
    # d'accès aux sources, donc une seconde occasion de diverger.
    remplacables = {m.url: m.baseline_path.name for m in col.urls if m.baseline_path is not None}
    remplacees: set[str] = set()

    for url, contenu, _kind in col.fresh_docs():
        res = col.fetched.get(url)
        corpus.docs.append(
            DocAudit(
                nom=url,
                contenu=contenu,
                kind="text",
                provenance="frais",
                sha256=(res.sha256 or "") if res else "",
                url=url,
            )
        )
        if nom_archive := remplacables.get(url):
            remplacees.add(nom_archive)

    for nom, contenu, kind in col.baseline_docs:
        if nom in remplacees:
            continue
        corpus.docs.append(
            DocAudit(
                nom=nom,
                contenu=contenu,
                kind="pdf" if kind == "pdf" else "text",
                provenance="baseline",
                sha256=_sha_baseline(aide.slug, nom),
            )
        )

    # --- ce qui manque au corpus, donc à la portée du verdict ---------------
    corpus.manquants.extend(f"PDF illisible : {p}" for p in col.pdf_illisibles)
    couvertes = {d.url for d in corpus.docs if d.url}
    noms_lus = {d.nom for d in corpus.docs}
    for murl in col.urls:
        # Le formulaire n'est qu'un contrôle de vivacité : son contenu n'est
        # jamais lu, son absence n'ampute donc rien.
        if murl.role == "formulaire" or murl.url in couvertes:
            continue
        # Page en erreur mais COMPENSÉE par son snapshot : rien ne manque, c'est
        # exactement le cas que la lecture des baselines est là pour couvrir.
        if murl.baseline_path is not None and murl.baseline_path.name in noms_lus:
            continue
        corpus.manquants.append(
            f"page sans contenu exploitable ({_motif_absence(col, murl)}) : {murl.url}"
        )
    if not (SOURCES_DIR / aide.slug).is_dir():
        corpus.manquants.append("aucun snapshot archivé pour cette aide")
    corpus.manquants.extend(
        f"document tronqué à {MAX_CHARS_DOCUMENT} caractères : {d.nom}"
        for d in corpus.docs
        if d.tronque
    )
    return corpus


# ---------------------------------------------------------------------------
# Étape 3 — schéma de sortie et prompt
# ---------------------------------------------------------------------------


class CritereAudit(BaseModel):
    """Un critère d'éligibilité lu dans la source, et son sort dans la fiche."""

    model_config = ConfigDict(extra="forbid")

    # Verbatim du corpus. Vérifiée par recherche littérale, comme dans la
    # veille : une citation approximative fait rejeter toute la réponse.
    quote: str
    # Condition existante qui couvre ce critère, ou None s'il n'y en a aucune.
    cond_id: str | None = None
    verdict: Literal["conforme", "absent", "divergent"]
    # verdict=absent : la proposition d'ajout.
    id: str | None = Field(default=None, pattern=r"^[a-z0-9-]+$")
    text: str | None = None
    kind: Literal["untyped", "info"] = "untyped"
    # verdict=divergent : en quoi le `text` de la fiche contredit la source.
    commentaire: str | None = None


class AuditLLMOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Contre-contrôle de confusion de fiche. Facultatif, comme dans la veille :
    # l'exiger ferait échouer gratuitement les fournisseurs qui ne savent pas
    # contraindre un schéma.
    slug: str | None = None
    # Porte de sortie volontairement facile : « l'écart me dépasse ». Rien n'est
    # appliqué, l'aide part en ré-ingestion.
    fiche_incomplete: bool = False
    raison_fiche_incomplete: str | None = None
    resume: str = ""
    criteres: list[CritereAudit] = []

    @property
    def absents(self) -> list[CritereAudit]:
        return [c for c in self.criteres if c.verdict == "absent"]

    @property
    def divergents(self) -> list[CritereAudit]:
        return [c for c in self.criteres if c.verdict == "divergent"]


SYSTEM_AUDIT = """Tu audites l'EXHAUSTIVITÉ d'une fiche d'aide au patrimoine : la fiche couvre-t-elle bien tout ce que sa source officielle exige ?

Tu ne rends QUE du JSON conforme au schéma. Aucun texte autour.

Règle absolue : chaque `quote` que tu produis doit être un extrait VERBATIM des documents fournis. Elle est vérifiée automatiquement par recherche littérale ; une citation approximative, reformulée ou reconstituée de mémoire fait rejeter toute ta réponse. Si tu ne peux pas citer, ne rapporte pas le critère.

Beaucoup de ces documents sont des pages converties en markdown, et leurs TABLEAUX y arrivent abîmés : une ligne se retrouve éclatée sur plusieurs lignes, ses cellules séparées par des `|` esseulés, ses valeurs renvoyées plus bas. Ne reconstitue JAMAIS une ligne de tableau en la remettant à plat — le résultat se lit bien mais n'existe nulle part dans le document, et la citation est rejetée. Cite un fragment COURT et CONTIGU, tel qu'il apparaît réellement : le libellé seul, ou la seule cellule qui porte ce que tu affirmes. Une citation courte et exacte vaut infiniment mieux qu'une citation complète et recomposée.

Ta tâche, dans cet ordre :

1. ÉNUMÈRE CHAQUE critère d'éligibilité que tu trouves dans les documents — y compris ceux que la fiche couvre déjà correctement. C'est un relevé exhaustif, pas une chasse aux erreurs : un critère correctement couvert doit apparaître avec `verdict: "conforme"`. Survoler les documents et ne rapporter que ce qui saute aux yeux est le principal mode d'échec de cette tâche.

2. Pour chaque critère, rattache-le à une condition existante de la fiche :
   - couvert par une condition, sans contradiction → `verdict: "conforme"`, avec son `cond_id`.
   - couvert par une condition dont le `text` CONTREDIT la source (seuil différent, périmètre différent, sens inversé) → `verdict: "divergent"`, avec son `cond_id` et un `commentaire` factuel disant en quoi les deux se contredisent.
   - aucune condition ne le couvre → `verdict: "absent"`, avec un `id` inédit en minuscules-tirets, un `text` et sa `quote`.

Ce qui n'est PAS un critère d'éligibilité : une pièce justificative, une étape de démarche, un contact, un délai d'instruction, une modalité de versement. Ne les rapporte pas comme `absent`. Si l'un d'eux mérite malgré tout de figurer dans la fiche, donne-lui `kind: "info"`.

Un critère déjà couvert sous une autre formulation est `conforme`, pas `absent`. Une reformulation, un synonyme, un découpage différent ne sont pas des manques : la question est le FOND, jamais les mots.

RÈGLE DE GRANULARITÉ — c'est le principal pourvoyeur de faux « absent », lis-la deux fois.

Une condition existante qui RÉSUME une liste couvre CHACUN de ses éléments, même si son `text` n'en nomme que quelques-uns et si sa `quote` n'en cite qu'un seul. Les fiches sont volontairement écrites ainsi : une puce de la source n'a pas à devenir une condition. Quand la source déroule une liste de critères et qu'une condition de la fiche l'énonce en bloc, chaque puce de cette liste est `conforme`, rattachée à cette condition — pas `absent`. C'est vrai en particulier des conditions `kind: "discretionary"`, qui sont par nature des synthèses de critères d'appréciation.

Avant de déclarer `absent`, pose-toi la question dans ce sens : « existe-t-il une condition, même large, même formulée autrement, sous laquelle ce critère tomberait ? » Si oui, c'est `conforme`. `absent` est réservé à ce qu'AUCUNE condition ne couvre, même partiellement.

De même, une source liste souvent ses critères par catégorie de bénéficiaire ou de projet. Les critères propres à une catégorie que la fiche ne traite pas ne sont pas des manques ; et ceux d'une catégorie qu'elle traite sont couverts dès qu'une condition énonce le critère d'appréciation en général.

Une condition ajoutée reste NON TYPÉE : donne `id`, `text`, `quote`, et `kind: "untyped"` (ou `"info"` pour une simple modalité sans incidence sur l'éligibilité). Ne propose ni `effect`, ni `fact`, ni `field`, ni prédicat : le typage est le travail d'un autre outil.

Ne propose JAMAIS de reformuler le `text` d'une condition existante. Une divergence part au rapport pour arbitrage humain, elle ne se corrige pas ici.

Si l'écart entre la fiche et la source est trop massif pour être rattrapé par quelques ajouts — fiche manifestement incomplète, dispositif différent de celui décrit, documents que tu ne reconnais pas — réponds `fiche_incomplete: true` avec la raison, et rien d'autre. C'est une porte de sortie normale, pas un échec.

Renseigne TOUJOURS `resume` : une phrase disant ce que vaut la fiche face à sa source. C'est ce que lira l'humain chargé de relire ton diff."""


def _tronquer(texte: str, limite: int) -> str:
    if len(texte) <= limite:
        return texte
    return texte[:limite] + f"\n\n[… document tronqué à {limite} caractères]"


def build_prompt_audit(aide: Aide, corpus: Corpus, *, aujourd_hui: date) -> str:
    """Prompt utilisateur : le périmètre de la fiche, ses conditions, puis le corpus.

    Contrairement à la veille, aucune restriction à un mandat de retouche : le
    rattachement d'un critère à une condition existante exige de voir TOUTES
    les conditions, sinon toute condition cachée est rapportée « absente ».

    `description` en fait partie, et ce n'est pas décoratif : c'est le SEUL
    endroit où vit le périmètre de la fiche. Mesuré au pilote du 2026-08-24 sur
    `29-projets-culturels-diffusion` — la page décrit trois volets (création,
    diffusion, animation), la fiche n'en couvre qu'un, et sans la description
    le modèle a rapporté six critères des deux autres volets comme
    « manquants ». Ils ne manquaient pas : ils n'étaient pas du sujet.
    """
    extrait = {
        "slug": aide.slug,
        "nom": aide.nom,
        "organisme": aide.organisme,
        "description": aide.description,
        # Noms seuls : le modèle n'a pas à auditer la liste des pièces, il a
        # besoin de savoir qu'elles SONT couvertes. Mesuré au pilote du
        # 2026-08-24 sur `77-association-patrimoine` : le Contrat d'Engagement
        # Républicain figure dans `documents_requis` de la fiche, mais le prompt
        # n'envoyait que les conditions — le modèle l'a donc déclaré manquant.
        # Une fiche n'est pas incomplète parce qu'elle range une exigence
        # ailleurs que dans ses conditions.
        "documents_requis": [d.nom for d in aide.documents_requis],
        "conditions": [
            {
                k: v
                for k, v in c.model_dump(mode="json").items()
                if k
                in ("id", "text", "kind", "effect", "fact", "field", "predicate", "quote", "notes")
                and v is not None
            }
            for c in aide.conditions
        ],
    }

    blocs = [
        f"Date du jour : {aujourd_hui.isoformat()}",
        "",
        "## Fiche actuelle — son périmètre et toutes ses conditions",
        "",
        "`description` délimite CE QUE COUVRE la fiche. Une source décrit souvent "
        "un dispositif plus large que ce que la fiche traite (plusieurs volets, "
        "plusieurs publics, plusieurs types de bénéficiaires) : un critère qui ne "
        "vaut que pour un périmètre exclu par la description n'est pas un manque.",
        "",
        "`documents_requis` liste les pièces que la fiche exige DÉJÀ, ailleurs que "
        "dans ses conditions. Une exigence qui s'y trouve est couverte : ne la "
        "propose pas comme condition manquante.",
        "",
        "```json",
        json.dumps(extrait, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Documents de la source officielle",
        "",
        "`frais` : page re-téléchargée aujourd'hui. `baseline` : snapshot archivé "
        "lors de l'ingestion — c'est le document sur lequel la fiche AURAIT dû être "
        "construite, et il fait pleinement foi pour juger de son exhaustivité.",
    ]
    for doc in corpus.docs:
        blocs += [
            f"\n### {doc.nom}  ({doc.provenance})",
            "```",
            _tronquer(doc.contenu, MAX_CHARS_DOCUMENT),
            "```",
        ]

    blocs += [
        "",
        f"Relève CHAQUE critère d'éligibilité des documents ci-dessus pour `{aide.slug}`, "
        "conformes compris, et dis pour chacun s'il est couvert, absent ou divergent. "
        "Une fiche complète et fidèle est le résultat NORMAL : dans ce cas tous tes "
        "critères sont `conforme`, et c'est une bonne réponse.",
    ]
    return "\n".join(blocs)


# ---------------------------------------------------------------------------
# Étape 4 — chaîne de validation
# ---------------------------------------------------------------------------


def check_referentiel_audit(out: AuditLLMOutput, aide: Aide) -> list[str]:
    """Le modèle parle-t-il de CETTE fiche, et de conditions qui existent ?"""
    erreurs: list[str] = []
    if out.slug is not None and out.slug != aide.slug:
        erreurs.append(f"slug « {out.slug} » ≠ aide auditée « {aide.slug} »")

    existants = {c.id for c in aide.conditions}
    ids_proposes: set[str] = set()
    for i, crit in enumerate(out.criteres):
        ou = f"critère #{i + 1} ({crit.verdict})"
        if crit.cond_id is not None and crit.cond_id not in existants:
            erreurs.append(f"{ou} : cond_id « {crit.cond_id} » inconnu dans la fiche")

        if crit.verdict == "absent":
            if crit.cond_id is not None:
                erreurs.append(
                    f"{ou} : contradictoire — un critère `absent` ne peut pas désigner "
                    f"la condition « {crit.cond_id} » qui le couvrirait"
                )
            if not crit.id or not (crit.text or "").strip():
                erreurs.append(f"{ou} : `absent` exige un `id` inédit ET un `text`")
                continue
            if crit.id in existants:
                erreurs.append(f"{ou} : id « {crit.id} » déjà utilisé, choisir un id inédit")
            if crit.id in ids_proposes:
                erreurs.append(f"{ou} : id « {crit.id} » proposé deux fois")
            ids_proposes.add(crit.id)
        elif crit.verdict == "divergent":
            if crit.cond_id is None:
                erreurs.append(f"{ou} : `divergent` exige le `cond_id` de la condition visée")
            if not (crit.commentaire or "").strip():
                erreurs.append(f"{ou} : `divergent` exige un `commentaire` factuel")
        elif crit.cond_id is None:
            erreurs.append(
                f"{ou} : `conforme` exige le `cond_id` de la condition qui couvre le critère "
                "— sans rattachement, utiliser `absent`"
            )
    return erreurs


def check_quotes_audit(
    out: AuditLLMOutput, documents: list[tuple[str, str, str]]
) -> tuple[list[str], list[int]]:
    """Grep normalisé de CHAQUE citation. Retourne (erreurs bloquantes, `conforme` écartés).

    Toutes les citations sont vérifiées, `conforme` comprises : elles sont la
    preuve que le modèle a LU les documents, et un relevé dont les citations
    sont reconstituées de mémoire ne prouve rien de ce qu'il déclare absent.

    Mais la SANCTION diffère selon ce que la citation porte, et c'est tout
    l'objet de cette fonction :

      - `absent` / `divergent` : une citation introuvable REJETTE la réponse.
        Ces critères-là écrivent dans le YAML ou partent au rapport comme
        constat sur la fiche ; rien n'y entre sans preuve littérale.
      - `conforme` : le critère est ÉCARTÉ, et lui seul. Il allait de toute
        façon être jeté après validation.

    Pourquoi cette asymétrie. Mesurée au pilote du 2026-08-24 sur
    `56-valorisation-restauration-patrimoine` : sur 21 critères relevés dont 19
    conformes, UNE citation issue d'un tableau HTML mal converti (ligne éclatée
    sur huit lignes, taux isolés plus bas) a fait rejeter l'audit entier — donc
    aussi deux `absent` et deux `divergent` correctement cités. Le modèle avait
    bien lu, il avait aplati la ligne du tableau ; la relance ne pouvait pas le
    corriger, et l'aide serait repassée en échec à chaque run. Détruire un
    audit pour un élément qu'on jette est disproportionné.

    Passe par le `check_quotes` de la veille via une sortie de veille factice :
    une citation acceptée à la veille ne peut pas être refusée ici pour une
    raison de tolérance différente.
    """
    if not documents:
        return ["aucun document lisible : impossible de vérifier les citations"], []
    erreurs: list[str] = []
    ecartes: list[int] = []
    for i, crit in enumerate(out.criteres):
        factice = VeilleLLMOutput(
            conditions=[
                ChangementCondition(
                    op="add",
                    id="q",
                    condition=NouvelleCondition(id="q", text="q", quote=crit.quote),
                )
            ]
        )
        for erreur in check_quotes(factice, documents):
            _, _, motif = erreur.partition(" : ")
            if crit.verdict == "conforme":
                ecartes.append(i)
            else:
                erreurs.append(
                    f"critère #{i + 1} ({crit.verdict}, cond_id={crit.cond_id}) : {motif}"
                )
            break
    return erreurs, ecartes


def check_doublons(out: AuditLLMOutput, aide: Aide) -> list[str]:
    """Un `absent` qui cite ce qu'une condition existante cite déjà est un raté.

    Le modèle n'a pas découvert un manque : il a échoué à rattacher le critère
    à la condition qui le porte. Le laisser passer ferait entrer un doublon
    dans la fiche — bien pire qu'un critère omis, puisqu'il faudra ensuite le
    typer deux fois.
    """
    erreurs: list[str] = []
    existantes = [(c.id, normalize(c.quote)) for c in aide.conditions if c.quote]
    for crit in out.absents:
        propose = normalize(crit.quote)
        if not propose:
            continue
        for cond_id, quote in existantes:
            if not quote:
                continue
            inclus = len(propose) >= MIN_CHARS_INCLUSION and propose in quote
            if propose == quote or inclus:
                erreurs.append(
                    f"critère « {crit.id} » : sa citation est déjà celle de la condition "
                    f"« {cond_id} » — c'est un rattachement manqué, pas un manque : "
                    f"répondre `conforme` avec cond_id={cond_id}"
                )
                break
    return erreurs


Etape = Literal["json", "schema", "referentiel", "quote", "doublon"]


def valider(
    texte: str, aide: Aide, corpus: Corpus
) -> tuple[AuditLLMOutput | None, list[str], Etape | None, int]:
    """Chaîne complète, dans l'ordre — l'ordre EST la sûreté.

    Retourne (sortie, erreurs, étape en échec, nombre de `conforme` écartés).
    Les `conforme` mal cités sont RETIRÉS de la sortie, pas fatals : voir
    `check_quotes_audit`. Le compte remonte jusqu'au rapport, parce qu'un
    relevé dont les citations s'effritent mérite d'être lu avec réserve.
    """
    out, erreurs, etape = parse_json_output(texte, AuditLLMOutput)
    if out is None:
        return None, erreurs, etape, 0  # type: ignore[return-value]
    # Un « ça me dépasse » est une RÉPONSE, pas une erreur : elle sort de la
    # chaîne sans être validée plus avant, puisque rien ne sera appliqué.
    if out.fiche_incomplete:
        return out, [], None, 0
    if erreurs := check_referentiel_audit(out, aide):
        return out, erreurs, "referentiel", 0

    erreurs, ecartes = check_quotes_audit(out, corpus.documents())
    if erreurs:
        return out, erreurs, "quote", len(ecartes)
    if ecartes:
        conformes = sum(1 for c in out.criteres if c.verdict == "conforme")
        plafond = max(TOLERANCE_CONFORMES_INVALIDES, conformes // RATIO_CONFORMES_INVALIDES)
        if len(ecartes) > plafond:
            return (
                out,
                [
                    f"{len(ecartes)} citation(s) de critère `conforme` introuvable(s) sur "
                    f"{conformes} (plafond {plafond}) : relevé non fiable, cite verbatim"
                ],
                "quote",
                len(ecartes),
            )
        # Retrait par index décroissant : l'inverse décalerait les suivants.
        for i in sorted(ecartes, reverse=True):
            del out.criteres[i]

    if erreurs := check_doublons(out, aide):
        return out, erreurs, "doublon", len(ecartes)
    return out, [], None, len(ecartes)


# ---------------------------------------------------------------------------
# Étape 5 — application
# ---------------------------------------------------------------------------


def sortie_ajouts(out: AuditLLMOutput, aide: Aide) -> VeilleLLMOutput:
    """Traduit les `absent` en sortie de veille, pour réutiliser son éditeur.

    Tout ce qui suit — insertion dans le style de liste local au fichier,
    assertion de différence profonde, rollback, validation `Aide` du fichier
    final — est celui de `veille_apply`, éprouvé sur les 141 fiches du dépôt.
    Le réécrire pour l'audit serait un second éditeur à maintenir, donc une
    seconde occasion d'abîmer un YAML.
    """
    return VeilleLLMOutput(
        slug=aide.slug,
        resume=out.resume,
        conditions=[
            ChangementCondition(
                op="add",
                id=crit.id or "",
                condition=NouvelleCondition(
                    id=crit.id or "",
                    text=crit.text or "",
                    kind=crit.kind,
                    quote=crit.quote,
                ),
            )
            for crit in out.absents
        ],
    )


@dataclass
class AuditResult:
    """Sort d'une aide passée à l'audit."""

    slug: str
    etat: Etat = "echec"
    modele: str = ""
    raison: str = ""
    resume: str = ""
    # Ids des conditions ajoutées au YAML.
    ajouts: list[str] = field(default_factory=list)
    # (cond_id, text actuel, quote, commentaire) — jamais écrites, arbitrage humain.
    divergences: list[tuple[str, str, str, str]] = field(default_factory=list)
    # (id, text, quote) des conditions que le modèle déclare manquantes SANS
    # qu'elles soient appliquées : au-dessus du seuil, l'aide part en escalade.
    # Sans cette matière, « 18 conditions manquantes » est un verdict que rien
    # ne permet d'instruire — or c'est exactement ce qu'il faut instruire pour
    # décider entre « fiche trouée » et « modèle qui prend des modalités pour
    # des critères ». Renseigné uniquement quand la validation a bien tourné.
    manquants_proposes: list[tuple[str, str, str]] = field(default_factory=list)
    # Critères relevés, tous verdicts confondus : la mesure de l'exhaustivité
    # du relevé, donc de la confiance à accorder à un « rien à signaler ».
    criteres_releves: int = 0
    # `conforme` retirés faute de citation littérale retrouvée. Jamais fatal en
    # petit nombre (tableaux mal convertis), mais c'est une réserve sur la
    # qualité du relevé, donc sur la confiance à accorder à son silence.
    conformes_ecartes: int = 0
    portee: Literal["complet", "partiel"] = "complet"
    manquants: list[str] = field(default_factory=list)
    docs_manifeste: list[dict[str, str]] = field(default_factory=list)
    sha_fiche: str = ""
    sha_sources: str = ""
    erreurs: list[str] = field(default_factory=list)
    etape_echec: str | None = None
    # Dernière réponse rejetée : sans elle, un rejet n'est pas rejouable au
    # débogage. Conservée uniquement en cas d'échec, et jamais dans le rapport.
    reponse_rejetee: str = ""
    tentatives: int = 0
    cout_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    latence_s: float = 0.0

    @property
    def symbole(self) -> str:
        return SYMBOLES[self.etat]

    @property
    def trace_manifeste(self) -> bool:
        """L'audit a-t-il abouti à un verdict qu'il serait vain de rejouer ?

        `echec` : non — la validation a refusé la réponse, on ne sait toujours
        rien de la fiche, et le passage suivant doit réessayer.
        `inauditable` : non plus — le jour où un snapshot arrive, l'audit part
        tout seul, c'est voulu.
        `escalade` : oui. Le verdict est acquis (la fiche est à ré-ingérer) et
        le rejouer coûterait un appel pour la même réponse. Il tombera de
        lui-même à la ré-ingestion, qui change le sha de la fiche.
        `non_audite` : non — aucun verdict n'a été demandé.
        """
        return self.etat not in ("echec", "inauditable", "non_audite")


def auditer(
    aide: Aide,
    col: AideCollect,
    spec: ModelSpec,
    *,
    aujourd_hui: date,
    dry_run: bool = False,
    chemin: Path | None = None,
    corpus: Corpus | None = None,
) -> AuditResult:
    """Un appel (au plus deux) au modèle, puis l'ajout des conditions manquantes."""
    chemin = chemin or AIDES_DIR / f"{aide.slug}.yaml"
    res = AuditResult(slug=aide.slug, modele=spec.alias)
    corpus = corpus if corpus is not None else construire_corpus(aide, col)
    res.portee = corpus.portee
    res.manquants = corpus.manquants
    res.docs_manifeste = [d.entree_manifeste() for d in corpus.docs]
    res.sha_sources = sha_sources(aide.slug)
    res.sha_fiche = sha_fiche(chemin)

    if corpus.vide:
        res.etat = "inauditable"
        res.raison = "aucun document lisible : ni page fraîche, ni snapshot exploitable"
        return res

    prompt = build_prompt_audit(aide, corpus, aujourd_hui=aujourd_hui)
    system = system_pour(spec, SYSTEM_AUDIT, AuditLLMOutput)
    schema = json_schema(AuditLLMOutput)

    out: AuditLLMOutput | None = None
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
            # Une réponse vide inexpliquée est un raté ponctuel : une relance à
            # l'identique suffit. Les vraies erreurs d'API (401, 429)
            # échoueraient pareil et ne sont pas relancées.
            if appel.reponse_vide and not relance_vide:
                relance_vide = True
                continue
            res.raison = f"appel au modèle en échec : {appel.error}"
            res.erreurs = [appel.error or "réponse vide"]
            res.etape_echec = "appel"
            return res
        reponse = appel.text
        out, erreurs, etape, ecartes = valider(reponse, aide, corpus)
        # Renseigné dès que la réponse se parse : sans ça, une aide en échec
        # s'affichait « 0 crit. » alors que le modèle en avait relevé vingt et
        # un — le compte est justement ce qui permet de juger l'échec.
        if out is not None:
            res.criteres_releves = len(out.criteres) + ecartes
            res.conformes_ecartes = ecartes
        if not erreurs or corrections:
            break
        corrections += 1
        prompt = prompt_correction(prompt, reponse, erreurs)

    if out is None or erreurs:
        res.erreurs = erreurs
        res.etape_echec = etape
        res.reponse_rejetee = reponse
        premiere = erreurs[0] if erreurs else "sans détail"
        res.raison = f"validation en échec ({etape}) : {premiere}"
        return res

    res.resume = out.resume.strip()

    # --- 5c. escalade ------------------------------------------------------
    if out.fiche_incomplete:
        # AVANT de relever quoi que ce soit : une réponse `fiche_incomplete`
        # court-circuite la validation (voir `valider`), donc ses critères n'ont
        # PAS vu le contrôle des citations. Les verser au rapport y ferait
        # entrer des divergences non vérifiées.
        res.etat = "escalade"
        res.raison = "fiche déclarée incomplète par le modèle : " + (
            out.raison_fiche_incomplete or "sans raison fournie"
        )
        return res

    res.divergences = [
        (
            crit.cond_id or "",
            next((c.text for c in aide.conditions if c.id == crit.cond_id), ""),
            crit.quote,
            crit.commentaire or "",
        )
        for crit in out.divergents
    ]
    absents = out.absents
    if len(absents) > MAX_AJOUTS_CONDITIONS:
        # Même seuil et même raison que la veille : une fiche à qui il manque
        # huit conditions a besoin d'une ré-ingestion typée et vérifiée
        # adversarialement, pas d'un empilement d'`untyped` par la petite porte.
        res.etat = "escalade"
        res.raison = (
            f"{len(absents)} conditions manquantes (seuil {MAX_AJOUTS_CONDITIONS}) : "
            "la fiche est à ré-ingérer, pas à rapiécer"
        )
        # Ces propositions ONT franchi toute la chaîne de validation (citations
        # vérifiées, doublons écartés) : seul le seuil les retient. Elles sont
        # donc de la matière fiable à porter au rapport, même si rien n'est écrit.
        res.manquants_proposes = [(crit.id or "", crit.text or "", crit.quote) for crit in absents]
        return res

    # --- 5a. les `absent` confirmés entrent en `untyped` --------------------
    if absents:
        sortie = sortie_ajouts(out, aide)
        applied = appliquer(
            json.dumps(sortie.model_dump(mode="json"), ensure_ascii=False),
            aide,
            chemin,
            corpus.documents(),
            aujourd_hui=aujourd_hui.isoformat(),
            # Pas d'ancrage : voir l'en-tête du module. L'audit cherche par
            # construction les divergences SANS changement de source.
            diff="",
            origine=ORIGINE,
        )
        if not applied.ok or applied.texte is None:
            res.erreurs = applied.erreurs
            res.etape_echec = applied.etape
            res.reponse_rejetee = reponse
            premiere = applied.erreurs[0] if applied.erreurs else "sans détail"
            res.raison = f"application en échec ({applied.etape}) : {premiere}"
            return res
        res.etat = "ajouts"
        res.ajouts = [crit.id or "" for crit in absents]
        res.raison = res.resume or f"{len(absents)} condition(s) ajoutée(s)"
        if not dry_run:
            chemin.write_text(applied.texte, encoding="utf-8")
            res.sha_fiche = sha_fiche(chemin)
        return res

    # --- 5b. divergences seules : rapport, aucune écriture ------------------
    if res.divergences:
        res.etat = "divergences"
        res.raison = res.resume or f"{len(res.divergences)} divergence(s) à arbitrer"
        return res

    res.etat = "a_jour"
    res.raison = res.resume or f"{len(out.criteres)} critère(s) relevé(s), tous couverts"
    return res


# ---------------------------------------------------------------------------
# Étape 6 — rapport
# ---------------------------------------------------------------------------


def build_report(
    resultats: dict[str, AuditResult],
    candidates: list[tuple[Aide, str]],
    *,
    total: int,
    today: date,
    duree_s: float,
    mode: str,
    typages: dict[str, TypageResult] | None = None,
) -> str:
    par_etat: dict[str, list[AuditResult]] = {e: [] for e in ETATS}
    for res in resultats.values():
        par_etat[res.etat].append(res)

    portee = {
        "report-only": "Sélection et corpus seulement : le modèle n'a pas été appelé, "
        "aucun fichier n'a été modifié.",
        "dry-run": "Audit exécuté à blanc : les ajouts ont été calculés et validés, "
        "aucun fichier n'a été écrit, le manifeste n'a PAS été mis à jour.",
        "complet": "Audit exécuté : tout ajout listé plus bas a été ÉCRIT dans "
        "`data/aides/`. Relire le `git diff` avant de committer.",
    }[mode]

    cout = sum(r.cout_usd for r in resultats.values())
    tok_in = sum(r.tokens_in for r in resultats.values())
    tok_out = sum(r.tokens_out for r in resultats.values())
    sautees = total - len(candidates)

    out: list[str] = [
        f"# Audit d'exhaustivité des fiches — {today.isoformat()}",
        "",
        f"{total} aide(s) examinée(s) en {duree_s / 60:.1f} min : {len(candidates)} "
        f"candidate(s) à l'audit, {sautees} sautée(s) (fiche et sources inchangées "
        f"depuis le dernier audit). {portee}",
        "",
        "> Cet audit répond à « la fiche reflète-t-elle sa source ? », pas à « la source "
        "a-t-elle changé ? » — cette seconde question est celle de "
        "`veille_aides.py`. Une condition ratée à l'ingestion ne produit aucun diff de "
        "source : elle n'est visible que d'ici.",
        "",
    ]
    if resultats:
        # En `--report-only` le modèle n'a pas été appelé : annoncer « N aides
        # soumises pour 0,000 $ » ferait lire un audit là où il n'y en a pas eu.
        if mode != "report-only":
            out += [
                f"{len(resultats)} aide(s) soumise(s) au modèle pour {cout:.3f} $ "
                f"({milliers(tok_in)} tokens en entrée, {milliers(tok_out)} en sortie).",
                "",
            ]
        out += [
            "| état | aides | signification |",
            "|---|---:|---|",
        ]
        for etat in ETATS:
            if par_etat[etat]:
                out.append(f"| `{etat}` | {len(par_etat[etat])} | {LEGENDES[etat]} |")
        out.append("")

    out += _section_releve(resultats, mode)
    out += _section_ajouts(par_etat["ajouts"], mode)
    out += section_typage(typages or {}, mode)
    out += _section_divergences(resultats)
    out += _section_escalades(par_etat["escalade"])
    out += _section_portees(resultats)
    out += _section_echecs(par_etat["echec"], par_etat["inauditable"])

    if mode == "report-only" and candidates:
        out += [
            "## Candidates à l'audit",
            "",
            "| aide | motif de sélection | corpus | portée |",
            "|---|---|---|---|",
        ]
        for aide, raison in candidates:
            res = resultats.get(aide.slug)
            corpus_dit = f"{len(res.docs_manifeste)} document(s)" if res else "—"
            out.append(f"| {aide.slug} | {raison} | {corpus_dit} | {res.portee if res else '—'} |")
        out.append("")
    return "\n".join(out)


def _section_releve(resultats: dict[str, AuditResult], mode: str) -> list[str]:
    """Combien de critères le modèle a relevés, aide par aide.

    C'est la seule mesure qui dise si un « rien à signaler » vaut quelque
    chose. Un relevé à 2 critères sur un règlement qui en compte vingt n'a pas
    audité la fiche : il l'a survolée, et son silence ne prouve rien. Le compte
    inclut les `conforme`, jetés ensuite — ils n'existent que pour forcer la
    lecture exhaustive, et c'est ici qu'ils servent une dernière fois.
    """
    audites = sorted(
        (r for r in resultats.values() if r.etat != "non_audite"), key=lambda r: r.slug
    )
    if mode == "report-only" or not audites:
        return []
    out = [
        "## Relevé",
        "",
        "| aide | état | critères relevés | citations écartées | portée |",
        "|---|---|---:|---:|---|",
        *(
            f"| {r.slug} | `{r.etat}` | {r.criteres_releves} | "
            f"{r.conformes_ecartes or '—'} | {r.portee} |"
            for r in audites
        ),
        "",
    ]
    if any(r.conformes_ecartes for r in audites):
        out += [
            "« Citations écartées » : critères que le modèle donnait pour couverts mais "
            "dont la citation ne se retrouve pas littéralement dans le document — le plus "
            "souvent une ligne de tableau remise à plat. Ils sont retirés du relevé sans "
            "conséquence, puisqu'un critère couvert ne produit aucune écriture. Un compte "
            "élevé reste une réserve : c'est autant de source dont la lecture n'est pas "
            "prouvée.",
            "",
        ]
    return out


def _section_ajouts(ajouts: list[AuditResult], mode: str) -> list[str]:
    if not ajouts:
        return []
    out = ["## Conditions ajoutées", ""]
    if mode == "dry-run":
        out += [
            "> **À blanc** : rien n'a été écrit. Relancer sans `--dry-run` pour "
            "appliquer, puis relire le `git diff`.",
            "",
        ]
    else:
        out += [
            "> Ces fiches sont MODIFIÉES sur disque. Les conditions entrent en "
            "`kind: untyped` et restent à typer (`/typer-aides`). Aucun modèle "
            "n'atteint zéro faux manquant : relire chaque diff avant de committer.",
            "",
        ]
    out += [
        "| aide | conditions ajoutées | portée | résumé du modèle |",
        "|---|---|---|---|",
    ]
    for res in sorted(ajouts, key=lambda r: r.slug):
        ids = ", ".join(f"`{i}`" for i in res.ajouts) or "—"
        out.append(f"| {res.slug} | {ids} | {res.portee} | {cellule(res.resume, 90)} |")
    out += ["", "```", "git diff -- data/aides", "```", ""]
    return out


def _section_divergences(resultats: dict[str, AuditResult]) -> list[str]:
    avec = sorted((r for r in resultats.values() if r.divergences), key=lambda r: r.slug)
    if not avec:
        return []
    out = [
        "## Divergences à arbitrer",
        "",
        "Le `text` d'une condition ne se reformule JAMAIS automatiquement — il vient "
        "de la source. Ces écarts partent donc à l'arbitrage humain : correction "
        "manuelle si la fiche a mal lu la source, `/ingest-aide` si elle l'a mal "
        "comprise, rien du tout si c'est le modèle qui se trompe.",
        "",
    ]
    for res in avec:
        out += [f"### {res.slug}", ""]
        for cond_id, texte, quote, commentaire in res.divergences:
            out += [
                f"- **`{cond_id}`** — {commentaire}",
                f"  - fiche : {cellule(texte, 200)}",
                f"  - source : {cellule(quote, 200)}",
            ]
        out.append("")
    return out


def _section_escalades(escalades: list[AuditResult]) -> list[str]:
    if not escalades:
        return []
    out = ["## Escalades — ré-ingestion complète", ""]
    for res in sorted(escalades, key=lambda r: r.slug):
        out.append(f"- **{res.slug}** — {res.raison}")
    out += [
        "",
        "Rien n'a été écrit. Ce que le modèle déclare manquant est listé ci-dessous "
        "pour que la décision se prenne sur pièces : une fiche réellement trouée "
        "part en ré-ingestion, un relevé qui confond critères d'éligibilité et "
        "modalités pratiques (pièces à fournir, étapes de démarche, contacts) ne "
        "prouve rien et doit faire ajuster le prompt avant le backfill.",
        "",
    ]
    for res in sorted(escalades, key=lambda r: r.slug):
        if not res.manquants_proposes:
            continue
        out += [f"### {res.slug} — {len(res.manquants_proposes)} manquant(s) déclaré(s)", ""]
        for cond_id, texte, quote in res.manquants_proposes:
            out += [
                f"- **`{cond_id}`** — {cellule(texte, 200)}",
                f"  - citation : {cellule(quote, 200)}",
            ]
        out.append("")
    slugs = " ".join(sorted(r.slug for r in escalades))
    out += [
        "",
        "Commande prête :",
        "",
        "```",
        f"uv run python scripts/ingest_aides_batch.py {slugs}",
        "```",
        "",
    ]
    return out


def _section_portees(resultats: dict[str, AuditResult]) -> list[str]:
    partielles = sorted(
        (r for r in resultats.values() if r.portee == "partiel" and r.etat != "inauditable"),
        key=lambda r: r.slug,
    )
    if not partielles:
        return []
    out = [
        "## Portées partielles",
        "",
        "Un « rien à signaler » sur ces aides se lit « rien à signaler **sur ce qui a "
        "pu être lu** ». Ce qui suit n'a PAS été soumis au modèle, et l'audit ne dit "
        "donc rien des critères que ces documents portent.",
        "",
    ]
    for res in partielles:
        out.append(f"- **{res.slug}** (`{res.etat}`)")
        out += [f"  - {m}" for m in res.manquants]
    out.append("")
    return out


def _section_echecs(echecs: list[AuditResult], inauditables: list[AuditResult]) -> list[str]:
    out: list[str] = []
    if echecs:
        out += [
            "## Échecs de validation",
            "",
            "Le modèle a répondu, la validation a refusé d'écrire. Rien n'a été modifié : "
            "c'est le comportement voulu, et l'aide reste à auditer — elle repassera "
            "d'elle-même au prochain run, aucune entrée n'ayant été écrite au manifeste. "
            "La réponse rejetée est dans le log, pas ici.",
            "",
        ]
        for res in sorted(echecs, key=lambda r: r.slug):
            out.append(f"- **{res.slug}** ({res.etape_echec}) — {res.raison}")
            out += [f"  - {e}" for e in res.erreurs[:3]]
        out.append("")
    if inauditables:
        out += [
            "## Aides inauditables",
            "",
            "Aucun document lisible : ni page fraîche, ni snapshot exploitable. Rien "
            "n'est écrit au manifeste — le jour où un snapshot arrive, l'audit repart "
            "de lui-même.",
            "",
        ]
        for res in sorted(inauditables, key=lambda r: r.slug):
            out.append(f"- **{res.slug}** — {' ; '.join(res.manquants) or res.raison}")
        out.append("")
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="veille_audit.py",
        description="Audite l'exhaustivité des fiches d'aide face à leur source officielle.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("slugs", nargs="*", help="aides à auditer (défaut : toutes)")
    p.add_argument(
        "--report-only",
        action="store_true",
        help="sélection et corpus seulement : zéro LLM, zéro écriture",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="appels et validation compris, mais sans écrire un seul fichier",
    )
    p.add_argument(
        "--max-llm",
        type=int,
        default=MAX_LLM_DEFAUT,
        help=f"plafond d'appels au modèle par passage (défaut : {MAX_LLM_DEFAUT})",
    )
    p.add_argument(
        "--model",
        default=MODELE_DEFAUT,
        choices=sorted(REGISTRE),
        help=f"modèle de l'audit (défaut : {MODELE_DEFAUT})",
    )
    p.add_argument("--limit", type=int, help="ne traiter que les N candidates les plus anciennes")
    p.add_argument(
        "--force",
        action="store_true",
        help="ré-auditer même si ni la fiche ni ses sources n'ont bougé",
    )
    p.add_argument(
        "--typer",
        action="store_true",
        help="enchaîner le typage des conditions ajoutées (elles sortent sinon "
        "l'aide du moteur déterministe) — pose des `gate`, relire le diff",
    )
    p.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    p.add_argument(
        "--proxy",
        choices=("jina",),
        help="proxy d'extraction anti-bot pour les pages fraîches",
    )
    return p.parse_args(argv)


def _charger(slugs: list[str]) -> dict[str, Aide] | None:
    if slugs:
        paths = [AIDES_DIR / f"{s}.yaml" for s in slugs]
        if manquants := [p.stem for p in paths if not p.exists()]:
            print(f"ERREUR : YAML introuvable pour : {', '.join(manquants)}", file=sys.stderr)
            return None
    else:
        paths = sorted(AIDES_DIR.glob("*.yaml"))
    try:
        return {p.stem: load_aide(p) for p in paths}
    except Exception as exc:  # noqa: BLE001 — un YAML cassé est une erreur fatale, pas un plantage
        print(f"ERREUR : YAML invalide — {exc}", file=sys.stderr)
        return None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    log = Journal()
    today = date.today()

    aides = _charger(args.slugs)
    if aides is None:
        return 1

    manifest = load_manifest()
    candidates = selectionner(aides, manifest, force=args.force, limit=args.limit)

    log(f"{'=' * 70}")
    log(f"AUDIT D'EXHAUSTIVITÉ — {today.isoformat()}")
    log(f"{'=' * 70}")
    log(
        f"{len(aides)} aide(s) examinée(s) : {len(candidates)} à auditer, "
        f"{len(aides) - len(candidates)} sautée(s) sans appel réseau ni modèle."
    )
    if not candidates:
        log("Rien à auditer : fiches et sources inchangées depuis le dernier audit.")
        return 0

    start = time.monotonic()
    collects = collect(
        [aide for aide, _ in candidates],
        concurrency=args.concurrency,
        timeout=args.timeout,
        proxy=args.proxy,
    )
    log(f"collecte terminée en {(time.monotonic() - start) / 60:.1f} min.")

    resultats = _auditer_toutes(args, candidates, collects, today, log)
    typages = _typer_ajouts(args, resultats, today, log)
    duree = time.monotonic() - start

    mode = "report-only" if args.report_only else ("dry-run" if args.dry_run else "complet")
    _recap(resultats, log, detaille=mode != "report-only")

    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REVIEWS_DIR / f"{today.isoformat()}-audit.md"
    report_path.write_text(
        build_report(
            resultats,
            candidates,
            total=len(aides),
            today=today,
            duree_s=duree,
            mode=mode,
            typages=typages,
        ),
        encoding="utf-8",
    )
    if mode == "complet" and resultats:
        write_manifest(update_manifest_audit(manifest, resultats, today))
        log("")
        log(f"manifeste : {MANIFEST_PATH.relative_to(DATA_DIR.parent)}")
    elif mode == "dry-run":
        # Sinon le vrai run suivant sauterait les aides « déjà auditées » à blanc.
        log("")
        log("manifeste : NON mis à jour (--dry-run)")
    log(f"rapport   : {report_path.relative_to(DATA_DIR.parent)}")
    log(f"durée     : {duree / 60:.1f} min")

    if appliquees := [r for r in resultats.values() if r.etat == "ajouts"]:
        log("")
        log(
            f"{len(appliquees)} fiche(s) modifiée(s)"
            + (" — à blanc, rien sur disque." if args.dry_run else " sur disque.")
        )
        if not args.dry_run:
            log("Relire avant commit : git diff -- data/aides")
    log.save(LOG_DIR / f"audit-{today.isoformat()}.log")

    compte = Counter(r.etat for r in resultats.values())
    return 2 if compte["escalade"] or compte["echec"] or compte["inauditable"] else 0


def _auditer_toutes(
    args: argparse.Namespace,
    candidates: list[tuple[Aide, str]],
    collects: dict[str, AideCollect],
    today: date,
    log: Journal,
) -> dict[str, AuditResult]:
    """Séquentiel, comme l'étage C : chaque fiche est écrite dès qu'elle est validée.

    Une interruption laisse alors un état cohérent et relisable, plutôt qu'un
    demi-lot en mémoire. Le facteur limitant est de toute façon la relecture
    humaine, pas la latence.
    """
    resultats: dict[str, AuditResult] = {}
    if args.report_only:
        log("")
        log("CORPUS (--report-only : le modèle n'est pas appelé)")
        for aide, raison in candidates:
            corpus = construire_corpus(aide, collects[aide.slug])
            res = AuditResult(slug=aide.slug, etat="non_audite", raison=raison)
            res.portee = corpus.portee
            res.manquants = corpus.manquants
            res.docs_manifeste = [d.entree_manifeste() for d in corpus.docs]
            resultats[aide.slug] = res
            frais = sum(1 for d in corpus.docs if d.provenance == "frais")
            log(
                f"  {aide.slug:<50} {len(corpus.docs):>2} doc(s) "
                f"({frais} frais) portée={corpus.portee:<8} {raison}"
            )
        return resultats

    spec = REGISTRE[args.model]
    if not spec.cle_presente:
        log("")
        log(
            f"⚠ audit ignoré : {spec.env_key} absente de backend/.env — "
            f"{len(candidates)} aide(s) restent à auditer."
        )
        return {}

    retenus = candidates[: args.max_llm]
    log("")
    log(f"{'=' * 70}")
    log(
        f"AUDIT — {len(retenus)}/{len(candidates)} aide(s), modèle {spec.alias}"
        + (" — à blanc, aucune écriture" if args.dry_run else "")
    )
    log(f"{'=' * 70}")

    for i, (aide, _raison) in enumerate(retenus, 1):
        res = auditer(
            aide,
            collects[aide.slug],
            spec,
            aujourd_hui=today,
            dry_run=args.dry_run,
        )
        resultats[aide.slug] = res
        log(
            f"  [{i}/{len(retenus)}] {res.symbole} {aide.slug:<46} "
            f"{res.cout_usd * 100:>5.2f}¢ {res.latence_s:>5.1f}s "
            f"{tokens_compacts(res.tokens_in):>6}↑{tokens_compacts(res.tokens_out):>6}↓ "
            f"{res.criteres_releves:>3} crit."
            + (f"{res.conformes_ecartes:>3}✂ " if res.conformes_ecartes else "    ")
            + cellule(res.raison, 41)
        )
        if res.reponse_rejetee:
            # Dans le log, pas dans le rapport : matière de débogage.
            log(f"      réponse rejetée : {res.reponse_rejetee.strip()}")

    if len(candidates) > len(retenus):
        log(
            f"  … {len(candidates) - len(retenus)} aide(s) laissée(s) de côté : plafond "
            f"--max-llm={args.max_llm}. Relancer après relecture pour la suite."
        )
    tok_in = sum(r.tokens_in for r in resultats.values())
    tok_out = sum(r.tokens_out for r in resultats.values())
    log(
        f"  coût de l'audit : {sum(r.cout_usd for r in resultats.values()):.3f} $"
        f"  —  {milliers(tok_in)} tokens en entrée, {milliers(tok_out)} en sortie"
    )
    return resultats


def _typer_ajouts(
    args: argparse.Namespace,
    resultats: dict[str, AuditResult],
    today: date,
    log: Journal,
) -> dict[str, TypageResult]:
    """Referme la plaie : une condition ajoutée est `untyped`, donc sort l'aide du moteur.

    N'agit que sur les aides que CE run a modifiées. Une aide portant une dette
    `untyped` antérieure se type avec `veille_typage.py` directement — l'audit
    n'a pas à élargir son mandat à ce qu'il n'a pas écrit.
    """
    if not args.typer or args.report_only:
        return {}
    slugs = [slug for slug, res in resultats.items() if res.etat == "ajouts"]
    if not slugs:
        return {}
    aides = [load_aide(AIDES_DIR / f"{slug}.yaml") for slug in slugs]
    return typer_toutes(
        aides,
        REGISTRE[args.model],
        aujourd_hui=today,
        dry_run=args.dry_run,
        max_llm=args.max_llm,
        log=log,
    )


def _recap(resultats: dict[str, AuditResult], log: Journal, *, detaille: bool = True) -> None:
    log("")
    log(f"{'=' * 70}")
    log("RÉCAP")
    log(f"{'=' * 70}")
    compte = Counter(r.etat for r in resultats.values())
    for etat in ETATS:
        if compte[etat]:
            log(f"  {SYMBOLES[etat]} {etat:<32} {compte[etat]}")
    # En `--report-only`, le bloc CORPUS ci-dessus a déjà listé chaque aide :
    # les réénumérer doublerait 141 lignes sans rien apprendre.
    for etat in ETATS if detaille else ():
        if etat == "a_jour":
            continue
        for res in sorted((r for r in resultats.values() if r.etat == etat), key=lambda r: r.slug):
            log(f"    {SYMBOLES[etat]} {res.slug:<50} {cellule(res.raison, 60)}")

    partielles = sorted(
        (r for r in resultats.values() if r.portee == "partiel" and r.etat != "inauditable"),
        key=lambda r: r.slug,
    )
    if partielles:
        log("")
        log("  portée partielle — le verdict ne porte que sur les documents lus,")
        log("  pas sur l'intégralité du règlement :")
        for res in partielles:
            log(f"    ○ {res.slug:<50} {len(res.manquants)} document(s) hors corpus")


if __name__ == "__main__":
    sys.exit(main())
