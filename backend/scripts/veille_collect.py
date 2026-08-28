"""
Étage A de la veille : quelles URL surveiller, et qu'ont-elles rendu aujourd'hui.

Zéro LLM, zéro décision — cet étage ne fait que RAPPORTER. Il charge les
baselines archivées, télécharge les pages, et laisse `veille_analyze` conclure.
Séparer les deux permet de rejouer le triage sans retélécharger, et de tester
l'analyse sans réseau.

Deux comparaisons, dans cet ordre :
  1. sha256 du texte BRUT contre celui de l'en-tête du snapshot. Identique ⇒ la
     page n'a pas bougé d'un octet, rien d'autre à calculer. Mesuré sur
     sauvegardeartfrancais.fr : ce chemin rapide fonctionne réellement, le sha
     est stable d'une requête à l'autre.
  2. sinon, diff normalisé du markdown (`veille_analyze`). Beaucoup de CMS
     glissent un horodatage ou un jeton dans le HTML, ce qui fait varier le sha
     à chaque requête sans que le contenu change.
"""

from __future__ import annotations

import asyncio
import hashlib
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aides_schema import DATA_DIR, Aide

sys.path.insert(0, str(Path(__file__).resolve().parent))

from snapshot_source import HEADERS_NAVIGATEUR, UA, resoudre_shield, to_markdown
from veille_text import flatten_markdown_links, parse_front_matter

SOURCES_DIR = DATA_DIR / "sources"

# En-dessous de ce nombre de caractères extraits, un PDF de règlement est réputé
# ILLISIBLE : c'est un scan dont `pdftotext` ne tire que les en-têtes. Mesuré :
# 6 PDF du dépôt sur 109, dont 3 rendent zéro caractère, portant 74 quotes.
# Les compter comme baseline imputerait à la « dette » des quotes qui n'ont
# jamais été vérifiables.
PDF_MIN_TEXT = 1000

# Codes que l'on retente une fois : surcharge, limitation de débit, pare-feu
# applicatif qui laisse parfois passer au second essai.
HTTP_REESSAYABLE = frozenset({408, 425, 429, 500, 502, 503, 504})

DEFAULT_CONCURRENCY = 8
DEFAULT_TIMEOUT = 30.0
RETRY_BACKOFF_S = 2.0

# Proxy d'extraction anti-bot, opt-in (`--proxy jina`). Rend directement du
# markdown : son contenu sert au contrôle des quotes, JAMAIS au diff de triage,
# puisqu'il ne passe pas par la même chaîne de conversion que la baseline.
JINA_PREFIX = "https://r.jina.ai/"

UrlRole = Literal["officielle", "snapshot", "formulaire"]

# Seuls ces types sont diffés comme du texte. Tout le reste — PDF, .docx des
# règlements départementaux, tableurs, archives — est comparé par sha d'octets :
# les passer à html2text produit du binaire décodé en « prose », qui diverge
# intégralement à chaque téléchargement.
TYPES_TEXTUELS = ("text/html", "text/plain", "application/xhtml", "text/markdown")
SUFFIXES_BINAIRES = (
    ".pdf",
    ".doc",
    ".docx",
    ".odt",
    ".xls",
    ".xlsx",
    ".ods",
    ".ppt",
    ".pptx",
    ".zip",
)


def _est_textuel(content_type: str, url: str) -> bool:
    if url.lower().split("?")[0].endswith(SUFFIXES_BINAIRES):
        return False
    ctype = content_type.split(";")[0].strip().lower()
    # Type absent : on se fie à l'extension, déjà contrôlée ci-dessus.
    return not ctype or ctype.startswith(TYPES_TEXTUELS)


# ---------------------------------------------------------------------------
# Baselines archivées (pur système de fichiers, aucune requête)
# ---------------------------------------------------------------------------


@cache
def pdf_to_text(path: Path) -> str | None:
    """Texte d'un PDF via `pdftotext`. None si l'outil ou l'extraction manque.

    Mode par défaut (pas `-layout`) : l'ordre de lecture rend mieux la prose
    continue des règlements, et l'effondrement des blancs de `normalize()` rend
    de toute façon l'indentation physique non signifiante.
    """
    try:
        out = subprocess.run(
            ["pdftotext", str(path), "-"], capture_output=True, timeout=60, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        # `OSError` et pas seulement `FileNotFoundError` : sous WSL, un PATH qui
        # traverse les dossiers Windows rend un `pdftotext` non exécutable, et le
        # `PermissionError` qui en sort faisait planter le run entier au lieu de
        # dégrader le PDF en « illisible ». L'outil absent est un cas prévu, pas
        # une panne.
        return None
    return out.stdout.decode("utf-8", errors="replace") if out.returncode == 0 else None


def load_baselines(slug: str) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Documents archivés d'une aide, et la liste de ses PDF illisibles.

    Retourne [(nom, contenu, type)] consommable par `find_quote_in_any`. TOUS
    les snapshots du dossier sont chargés, pas seulement `source.snapshot` : une
    aide a souvent une page d'appel à projets, un règlement PDF et un
    formulaire, et une quote n'est justifiée que par l'un d'eux.
    """
    directory = SOURCES_DIR / slug
    if not directory.is_dir():
        return [], []
    docs: list[tuple[str, str, str]] = []
    illisibles: list[str] = []
    for path in sorted(directory.iterdir()):
        suffix = path.suffix.lower()
        if suffix == ".md":
            # Liens aplatis : les quotes ont été saisies depuis le rendu visuel
            # de la page, où l'URL d'une ancre en milieu de phrase n'apparaît pas.
            body = parse_front_matter(path.read_text(encoding="utf-8"))[1]
            docs.append((path.name, flatten_markdown_links(body), "text"))
        elif suffix == ".pdf":
            text = pdf_to_text(path)
            if text is None:
                illisibles.append(f"{path.name} (pdftotext indisponible ou en échec)")
            elif len(text.strip()) < PDF_MIN_TEXT:
                illisibles.append(f"{path.name} ({len(text.strip())} car. extraits)")
            else:
                docs.append((path.name, text, "pdf"))
    return docs, illisibles


@dataclass(frozen=True)
class MonitoredUrl:
    """Une URL à re-visiter, et la preuve archivée à laquelle la comparer."""

    url: str
    role: UrlRole
    label: str | None = None
    baseline_path: Path | None = None
    baseline_sha: str | None = None
    # Corps markdown du snapshot : le terme de gauche du diff.
    baseline_body: str | None = None
    is_binary: bool = False

    @property
    def has_baseline(self) -> bool:
        return self.baseline_sha is not None

    @property
    def host(self) -> str:
        return urlsplit(self.url).netloc.lower()


def _snapshot_baselines(slug: str) -> dict[str, MonitoredUrl]:
    """Baseline la plus récente pour chaque URL déjà snapshotée de l'aide.

    La provenance vient de l'en-tête des `.md` et des sidecars `.pdf.meta.yaml`
    — c'est la seule façon de savoir QUELLE page un snapshot archive. Les 109
    PDF antérieurs au sidecar n'ont pas de provenance : ils restent utilisables
    comme baseline de quotes, mais leur page n'est pas surveillable.
    """
    directory = SOURCES_DIR / slug
    if not directory.is_dir():
        return {}
    # Tri par nom = tri par date (les noms commencent par l'horodatage ISO) :
    # la dernière écriture pour une URL donnée gagne.
    baselines: dict[str, MonitoredUrl] = {}
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() == ".md":
            meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
            url, sha = meta.get("url"), meta.get("sha256")
            if url and url.startswith(("http://", "https://")):
                baselines[url] = MonitoredUrl(
                    url=url,
                    role="snapshot",
                    label=_label_of(path.stem),
                    baseline_path=path,
                    baseline_sha=sha,
                    baseline_body=body,
                )
        elif path.name.endswith(".pdf.meta.yaml"):
            meta = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if (url := meta.get("url")) and url.startswith(("http://", "https://")):
                baselines[url] = MonitoredUrl(
                    url=url,
                    role="snapshot",
                    label=_label_of(path.name.removesuffix(".pdf.meta.yaml")),
                    baseline_path=path.with_name(path.name.removesuffix(".meta.yaml")),
                    baseline_sha=meta.get("sha256"),
                    is_binary=True,
                )
    return baselines


def _label_of(stem: str) -> str | None:
    """« 2026-08-05-reglement » → « reglement » ; « 2026-08-05 » → None."""
    rest = stem[len("0000-00-00") :].lstrip("-")
    return rest or None


def monitored_urls(aide: Aide) -> list[MonitoredUrl]:
    """URL surveillées pour une aide, dédupliquées, dans un ordre stable.

    `url_officielle` d'abord (c'est la page principale, dont la mort déclenche
    une escalade), puis les pages déjà snapshotées, puis `formulaire_url` — ce
    dernier n'est qu'un contrôle de vivacité : son contenu n'est ni diffé ni
    cité, seul son code HTTP compte.
    """
    baselines = _snapshot_baselines(aide.slug)
    urls: list[MonitoredUrl] = []
    seen: set[str] = set()

    if officielle := aide.source.url_officielle:
        base = baselines.get(officielle)
        urls.append(
            MonitoredUrl(
                url=officielle,
                role="officielle",
                label=base.label if base else None,
                baseline_path=base.baseline_path if base else None,
                baseline_sha=base.baseline_sha if base else None,
                baseline_body=base.baseline_body if base else None,
                is_binary=base.is_binary if base else not _est_textuel("", officielle),
            )
        )
        seen.add(officielle)

    for url in sorted(baselines):
        if url not in seen:
            urls.append(baselines[url])
            seen.add(url)

    if (formulaire := aide.source.formulaire_url) and formulaire not in seen:
        urls.append(MonitoredUrl(url=formulaire, role="formulaire"))
    return urls


# ---------------------------------------------------------------------------
# Téléchargement
# ---------------------------------------------------------------------------


@dataclass
class FetchResult:
    url: str
    status: int | None = None
    error: str | None = None
    # Texte brut tel que reçu — c'est lui qui porte le sha comparé à l'en-tête.
    raw_text: str | None = None
    # Markdown : terme de droite du diff, et support du contrôle des quotes.
    body_md: str | None = None
    sha256: str | None = None
    # Contenu non textuel (PDF, .docx, tableur) : comparé par sha uniquement.
    is_binary: bool = False
    via_proxy: bool = False
    # Page obtenue seulement après repli sous identité de navigateur (403 au
    # premier essai). Le contenu reste diffable : il passe par `to_markdown`
    # comme la baseline, contrairement au proxy.
    via_navigateur: bool = False
    # Page obtenue après résolution d'un défi JavaScript (« shield »).
    via_shield: bool = False
    elapsed_s: float = 0.0
    retried: bool = False

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 300 and self.error is None

    @property
    def reessayable(self) -> bool:
        """Panne probablement transitoire : à retenter, jamais à escalader."""
        if self.error is not None:
            # Timeout, coupure, refus de connexion : la source n'est pas en
            # cause, le réseau ou l'anti-bot l'est.
            return True
        return self.status in HTTP_REESSAYABLE or self.status == 403

    @property
    def morte(self) -> bool:
        """La page n'existe plus — c'est une décision éditoriale, pas une panne."""
        return self.status in (404, 410)


async def _fetch_one(
    client: httpx.AsyncClient,
    murl: MonitoredUrl,
    *,
    semaphore: asyncio.Semaphore,
    host_locks: dict[str, asyncio.Lock],
    proxy: str | None,
) -> FetchResult:
    target = f"{JINA_PREFIX}{murl.url}" if proxy == "jina" else murl.url
    result = FetchResult(url=murl.url, via_proxy=proxy == "jina")
    start = time.monotonic()
    # None = identité par défaut du client (UA Monumia). Renseigné au second
    # essai si le premier s'est heurté à un WAF.
    headers: dict[str, str] | None = None
    # Verrou d'hôte AVANT le sémaphore : l'inverse laisserait plusieurs tâches
    # d'un même hôte occuper toutes les places disponibles pour s'attendre.
    async with host_locks[murl.host]:
        for attempt in (1, 2):
            async with semaphore:
                try:
                    resp = await client.get(target, headers=headers)
                    if (defi := resoudre_shield(resp.content)) is not None:
                        # Ce n'est pas la page mais un script qui pose un cookie
                        # calculé avant de rediriger. Rejouer le calcul coûte une
                        # multiplication ; sans ça la page revient vide de
                        # substance et l'aide sort en ERREUR_HTTP. Le cookie est
                        # posé sur le client partagé : les autres URL du même
                        # hôte en profitent sans repayer l'aller-retour.
                        nom, valeur = defi
                        client.cookies.set(nom, valeur, domain=murl.host)
                        result.via_shield = True
                        resp = await client.get(target, headers=headers)
                    result.status = resp.status_code
                    result.error = None
                    if resp.is_success:
                        ctype = resp.headers.get("content-type", "")
                        result.is_binary = not _est_textuel(ctype, murl.url)
                        if result.is_binary:
                            # Un binaire ne se diffe pas en texte : seul le sha
                            # de ses octets dit s'il a bougé. Sans ce test, un
                            # .docx passait par html2text, qui rendait 111 000
                            # caractères de ZIP illisible — donc « 100 % des
                            # lignes changées » et une escalade à chaque
                            # passage, sur sept aides de Seine-et-Marne.
                            result.sha256 = hashlib.sha256(resp.content).hexdigest()
                        else:
                            result.raw_text = resp.text
                            result.sha256 = hashlib.sha256(resp.text.encode()).hexdigest()
                            # Le proxy rend déjà du markdown : le reconvertir
                            # l'abîmerait.
                            result.body_md = (
                                resp.text if result.via_proxy else to_markdown(resp.text)
                            )
                except httpx.HTTPError as exc:
                    result.status = None
                    result.error = f"{type(exc).__name__}: {exc}"
            if attempt == 1 and not result.ok and result.reessayable:
                result.retried = True
                if result.status == 403:
                    # Un 403 est un refus déterministe : réémettre la même
                    # requête après une pause ne change rien. On change
                    # d'identité, et on n'attend pas.
                    headers = HEADERS_NAVIGATEUR
                else:
                    await asyncio.sleep(RETRY_BACKOFF_S)
                continue
            break
    # Après la boucle seulement : le repli n'est constaté que s'il a abouti.
    result.via_navigateur = headers is not None and result.ok
    result.elapsed_s = time.monotonic() - start
    return result


async def _fetch_all_async(
    urls: list[MonitoredUrl], *, concurrency: int, timeout: float, proxy: str | None
) -> dict[str, FetchResult]:
    semaphore = asyncio.Semaphore(concurrency)
    host_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
    async with httpx.AsyncClient(
        headers={"User-Agent": UA}, follow_redirects=True, timeout=timeout
    ) as client:
        results = await asyncio.gather(
            *(
                _fetch_one(client, m, semaphore=semaphore, host_locks=host_locks, proxy=proxy)
                for m in urls
            )
        )
    return {r.url: r for r in results}


@dataclass
class AideCollect:
    """Tout ce que l'étage A sait d'une aide, avant toute interprétation."""

    slug: str
    urls: list[MonitoredUrl] = field(default_factory=list)
    fetched: dict[str, FetchResult] = field(default_factory=dict)
    baseline_docs: list[tuple[str, str, str]] = field(default_factory=list)
    pdf_illisibles: list[str] = field(default_factory=list)

    @property
    def page_principale(self) -> MonitoredUrl | None:
        return next((u for u in self.urls if u.role == "officielle"), None)

    def fresh_docs(self) -> list[tuple[str, str, str]]:
        """Contenus frais fouillables, pour le contrôle des quotes."""
        docs = []
        for murl in self.urls:
            if murl.role == "formulaire":
                continue
            res = self.fetched.get(murl.url)
            if res and res.ok and res.body_md:
                docs.append((murl.url, flatten_markdown_links(res.body_md), "text"))
        return docs


def collect(
    aides: list[Aide],
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout: float = DEFAULT_TIMEOUT,
    proxy: str | None = None,
    offline: bool = False,
) -> dict[str, AideCollect]:
    """Charge les baselines de chaque aide puis télécharge toutes ses URL.

    Le téléchargement est mutualisé sur l'ensemble des aides : sérialiser par
    hôte n'a de sens que globalement, plusieurs aides d'une même région
    partageant le même serveur (guide-aides.hautsdefrance.fr sert cinq aides).

    `offline=True` saute le réseau — sert aux tests et à l'inspection du
    périmètre de surveillance sans toucher aux sources.
    """
    collects: dict[str, AideCollect] = {}
    for aide in aides:
        docs, illisibles = load_baselines(aide.slug)
        collects[aide.slug] = AideCollect(
            slug=aide.slug,
            urls=monitored_urls(aide),
            baseline_docs=docs,
            pdf_illisibles=illisibles,
        )

    if offline:
        return collects

    # Dédupliqué : deux aides peuvent surveiller la même page (les aides
    # Hauts-de-France partagent leur guide), on ne la télécharge qu'une fois.
    par_url: dict[str, MonitoredUrl] = {}
    for col in collects.values():
        for murl in col.urls:
            par_url.setdefault(murl.url, murl)

    fetched = asyncio.run(
        _fetch_all_async(
            sorted(par_url.values(), key=lambda m: m.url),
            concurrency=concurrency,
            timeout=timeout,
            proxy=proxy,
        )
    )
    for col in collects.values():
        col.fetched = {m.url: fetched[m.url] for m in col.urls if m.url in fetched}
    return collects
