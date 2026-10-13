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

Le téléchargement passe par le `Fetcheur` du pipeline d'ingestion
(`pipeline/web.py`) : la veille doit ouvrir les pages exactement comme
l'ingestion les a ouvertes, sinon elle sort en erreur là où l'archive a été
prise sans difficulté (certificats complétés par le magasin du système, repli
`curl_cffi`, délai par hôte). Il exige le groupe `pipeline` du venv
(`uv sync --group dev --group pipeline`), comme la prospection et l'ingestion.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aides_schema import DATA_DIR, Aide, charger_yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from snapshot_source import docx_bytes_to_text, est_docx, to_markdown

from catalogue.veille_text import flatten_markdown_links, parse_front_matter

if TYPE_CHECKING:
    from pipeline.web import Fetcheur, Page

SOURCES_DIR = DATA_DIR / "sources"

# Cache disque du texte extrait des PDF, clé par sha256 des octets. Le dossier
# est ignoré par git : c'est une matérialisation recalculable, pas une donnée.
# Sans lui, chaque passage relance `pdftotext` sur les ~175 PDF archivés
# (mesuré : 5 s par run, et autant pour l'audit qui recharge les baselines).
PDFTEXT_CACHE_DIR = DATA_DIR.parent / ".cache" / "pdftotext"

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

# Copie d'archive brute (`id_` : les octets d'origine, sans la barre de
# navigation de la Wayback Machine). Quelques snapshots ont été pris là faute
# de pouvoir ouvrir la page en ligne.
_WAYBACK_RE = re.compile(r"^https?://web\.archive\.org/web/\d+(?:id_)?/(https?://.+)$")


def est_http(url: str | None) -> bool:
    """URL téléchargeable. `mailto:`, `tel:`, un chemin relatif ne le sont pas.

    Une fiche peut légitimement porter `formulaire_url: mailto:...` (dépôt par
    courriel) : ce n'est pas une page à surveiller, et la passer au client HTTP
    faisait tomber tout le passage sur un `ValueError`.
    """
    return bool(url) and url.strip().lower().startswith(("http://", "https://"))  # type: ignore[union-attr]


def url_d_origine(url: str) -> tuple[str, Literal["direct", "proxy", "archive"]]:
    """L'URL de la page dont un snapshot est la copie, et le chemin emprunté.

    Un snapshot pris par le proxy jina ou dans la Wayback Machine porte l'URL
    INTERMÉDIAIRE dans son en-tête. Le prendre tel quel faisait surveiller le
    proxy ou l'archive (figée : toujours « inchangée », citations comprises)
    au lieu de la page en ligne, qui restait sans baseline et jamais diffée.
    """
    if url.startswith(JINA_PREFIX) and est_http(reste := url[len(JINA_PREFIX) :]):
        return reste, "proxy"
    if m := _WAYBACK_RE.match(url):
        return m.group(1), "archive"
    return url, "direct"


def corps_binaire(body: str) -> bool:
    """Snapshot `.md` dont le corps est un binaire décodé de force.

    Des ingestions anciennes ont archivé ainsi des .docx, .doc, .xls, .zip :
    « PK... » ou une bouillie de caractères de remplacement. Ce n'est ni une
    baseline (le diff contre un fichier frais serait 100 % de lignes changées),
    ni une source de citations.
    """
    tete = body.lstrip()[:4000]
    if tete.startswith("PK"):
        return True
    suspects = sum(1 for c in tete if c == "�" or (ord(c) < 32 and c not in "\n\r\t"))
    return len(tete) > 0 and suspects / len(tete) > 0.05


UrlRole = Literal["officielle", "snapshot", "formulaire"]

# Seuls ces types passent par html2text. Tout le reste — PDF, .docx des
# règlements départementaux, tableurs, archives — est d'abord comparé par sha
# d'octets : les passer à html2text produit du binaire décodé en « prose », qui
# diverge intégralement à chaque téléchargement. Un PDF est ensuite extrait en
# texte par `pdftotext` (voir `collect()`), ce qui le rend diffable et
# fouillable comme une page ; les autres binaires restent comparés par sha seul.
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


def _pdftotext(content: bytes) -> str | None:
    """Lance `pdftotext` sur des octets. None si l'outil ou l'extraction manque.

    Mode par défaut (pas `-layout`) : l'ordre de lecture rend mieux la prose
    continue des règlements, et l'effondrement des blancs de `normalize()` rend
    de toute façon l'indentation physique non signifiante. Lecture sur l'entrée
    standard : un PDF fraîchement téléchargé n'a pas de chemin sur disque.
    """
    try:
        out = subprocess.run(
            ["pdftotext", "-", "-"], input=content, capture_output=True, timeout=60, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        # `OSError` et pas seulement `FileNotFoundError` : sous WSL, un PATH qui
        # traverse les dossiers Windows rend un `pdftotext` non exécutable, et le
        # `PermissionError` qui en sort faisait planter le run entier au lieu de
        # dégrader le PDF en « illisible ». L'outil absent est un cas prévu, pas
        # une panne.
        return None
    return out.stdout.decode("utf-8", errors="replace") if out.returncode == 0 else None


def pdf_bytes_to_text(content: bytes) -> str | None:
    """Texte d'un PDF donné par ses octets, avec cache disque par sha256.

    Un échec d'extraction n'est jamais mis en cache : `pdftotext` peut manquer
    sur une machine et être là sur la suivante, et un cache vide figerait
    l'échec.
    """
    sha = hashlib.sha256(content).hexdigest()
    cache = PDFTEXT_CACHE_DIR / f"{sha}.txt"
    try:
        if cache.is_file():
            return cache.read_text(encoding="utf-8")
    except OSError:
        pass
    text = _pdftotext(content)
    if text is not None:
        try:
            PDFTEXT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache.write_text(text, encoding="utf-8")
        except OSError:
            # Un cache qu'on ne peut pas écrire n'est pas une panne : on aura
            # juste payé l'extraction.
            pass
    return text


@cache
def pdf_to_text(path: Path) -> str | None:
    """Texte d'un PDF archivé. None si l'outil ou l'extraction manque."""
    try:
        content = path.read_bytes()
    except OSError:
        return None
    return pdf_bytes_to_text(content)


def pdf_lisible(text: str | None) -> bool:
    """Un PDF dont on tire moins de `PDF_MIN_TEXT` caractères est un scan.

    UNE seule définition, partagée par les baselines et les PDF frais : un PDF
    illisible ne doit jamais faire passer ses citations pour disparues, quel que
    soit le côté (archive ou téléchargement) où il se trouve.
    """
    return text is not None and len(text.strip()) >= PDF_MIN_TEXT


def empreinte_texte(texte: str | None) -> str | None:
    """sha du texte d'un PDF, blancs écrasés. None s'il n'y a rien à lire.

    Pour les PDF trop courts pour servir de baseline (formulaire d'une page,
    PDF généré à la volée) : leurs octets changent à chaque requête, ce qui
    escaladait l'aide à chaque passage alors que le texte est identique.
    """
    if not texte or not texte.strip():
        return None
    return hashlib.sha256(" ".join(texte.split()).encode()).hexdigest()


def est_pdf(content: bytes | None) -> bool:
    return bool(content) and content[:5] == b"%PDF-"  # type: ignore[index]


def load_baselines(slug: str) -> tuple[list[tuple[str, str, str]], list[str], dict[str, str]]:
    """Documents archivés d'une aide, ses PDF illisibles, et leur provenance.

    Retourne [(nom, contenu, type)] consommable par `find_quote_in_any`. TOUS
    les snapshots du dossier sont chargés, pas seulement `source.snapshot` : une
    aide a souvent une page d'appel à projets, un règlement PDF et un
    formulaire, et une quote n'est justifiée que par l'un d'eux.

    Le troisième terme associe chaque nom de fichier à l'URL qu'il archive, lue
    dans l'en-tête du `.md` ou le sidecar `.pdf.meta.yaml`. Sans lui, l'étage B
    ne peut pas dire si le document qui justifie une quote a été re-téléchargé :
    `_snapshot_baselines` ne garde que le snapshot le PLUS RÉCENT par URL, alors
    que la recherche de quote balaye TOUS les snapshots et tombe volontiers sur
    un plus ancien. Les 9 aides dont une même page est archivée deux fois
    sortaient ainsi en « 0/n citation contrôlée » alors que leur page avait bien
    été revisitée — et leur nombre ne peut que croître, puisque chaque mise à
    jour ré-archive. Une alarme fausse dans un garde-fou n'est pas neutre :
    elle apprend à ne plus le lire.
    """
    directory = SOURCES_DIR / slug
    if not directory.is_dir():
        return [], [], {}
    docs: list[tuple[str, str, str]] = []
    illisibles: list[str] = []
    provenance: dict[str, str] = {}
    for path in sorted(directory.iterdir()):
        suffix = path.suffix.lower()
        if suffix == ".md":
            # Liens aplatis : les quotes ont été saisies depuis le rendu visuel
            # de la page, où l'URL d'une ancre en milieu de phrase n'apparaît pas.
            meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
            if corps_binaire(body):
                continue
            docs.append((path.name, flatten_markdown_links(body), "text"))
            if est_http(url := meta.get("url")):
                provenance[path.name] = url_d_origine(url)[0]
        elif suffix == ".pdf":
            text = pdf_to_text(path)
            if text is None:
                illisibles.append(f"{path.name} (pdftotext indisponible ou en échec)")
            elif not pdf_lisible(text):
                illisibles.append(f"{path.name} ({len(text.strip())} car. extraits)")
            else:
                docs.append((path.name, text, "pdf"))
            # Les 109 PDF antérieurs au sidecar n'ont pas de provenance : ils
            # restent des baselines de quotes, mais rien ne dira jamais que leur
            # source a été revisitée, faute de savoir laquelle c'est.
            sidecar = path.with_name(path.name + ".meta.yaml")
            if sidecar.is_file():
                meta = charger_yaml(sidecar.read_text(encoding="utf-8")) or {}
                if est_http(url := meta.get("url")):
                    provenance[path.name] = url_d_origine(url)[0]
    return docs, illisibles, provenance


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
    # Empreinte du texte d'un PDF archivé, même illisible (cf. `empreinte_texte`).
    baseline_empreinte_texte: str | None = None
    is_binary: bool = False

    @property
    def has_baseline(self) -> bool:
        # Un snapshot ancien sans sha dans son en-tête reste un terme de diff :
        # les deux définitions doivent dire la même chose, sinon une page diffée
        # (et escaladée) compte en même temps pour « sans baseline ».
        return self.baseline_sha is not None or self.baseline_body is not None

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
            if not est_http(url):
                continue
            url, chemin = url_d_origine(url)
            # Un corps binaire n'est pas comparable, et le markdown d'un proxy ne
            # sort pas de la même conversion que la page qu'on retéléchargera :
            # dans les deux cas l'URL reste surveillée, mais sans terme de diff.
            # Une page déjà archivée en direct garde sa baseline.
            comparable = chemin != "proxy" and not corps_binaire(body)
            if not comparable and url in baselines:
                continue
            baselines[url] = MonitoredUrl(
                url=url,
                role="snapshot",
                label=_label_of(path.stem),
                baseline_path=path if comparable else None,
                baseline_sha=sha if comparable else None,
                baseline_body=body if comparable else None,
            )
        elif path.name.endswith(".pdf.meta.yaml"):
            meta = charger_yaml(path.read_text(encoding="utf-8")) or {}
            if est_http(url := meta.get("url")):
                url = url_d_origine(url)[0]
                pdf = path.with_name(path.name.removesuffix(".meta.yaml"))
                # Le texte du PDF archivé est le terme de gauche du diff quand la
                # même URL rend un PDF frais lisible. Un scan (texte trop court)
                # n'a pas de corps : la comparaison se fera par sha seul.
                texte = pdf_to_text(pdf) if pdf.is_file() else None
                baselines[url] = MonitoredUrl(
                    url=url,
                    role="snapshot",
                    label=_label_of(path.name.removesuffix(".pdf.meta.yaml")),
                    baseline_path=pdf,
                    baseline_sha=meta.get("sha256"),
                    baseline_body=texte if pdf_lisible(texte) else None,
                    baseline_empreinte_texte=empreinte_texte(texte),
                    is_binary=True,
                )
    return baselines


def _label_of(stem: str) -> str | None:
    """« 2026-08-05-reglement » → « reglement » ; « 2026-08-05 » → None."""
    rest = stem[len("0000-00-00") :].lstrip("-")
    return rest or None


# Paramètres de requête qui ne désignent pas une ressource mais une campagne de
# suivi : deux URL qui n'en diffèrent que par eux servent la même page.
_PARAMS_SUIVI = ("utm_", "fbclid", "gclid", "mtm_", "pk_")


def cle_url(url: str) -> str:
    """Forme canonique d'une URL, pour la rapprocher de sa baseline.

    `url_officielle` est saisie dans la fiche par un humain ; l'URL de l'en-tête
    d'un snapshot est celle où le téléchargement a ABOUTI (`str(resp.url)`,
    redirections suivies). Entre les deux : `http`/`https`, `www.`, un slash
    final, un fragment, une campagne `utm_`. Mesuré au 2026-09-01 : 18 aides
    dont la page officielle n'était rattachée à aucune baseline alors que le
    dossier archivait bien la page — donc téléchargée deux fois et jamais
    diffée. Le rapprochement se fait sur cette clé, jamais sur l'égalité brute.
    """
    parts = urlsplit(url.strip())
    hote = parts.netloc.lower().removeprefix("www.")
    chemin = parts.path.rstrip("/") or "/"
    params = sorted(
        p for p in parts.query.split("&") if p and not p.lower().startswith(_PARAMS_SUIVI)
    )
    return f"{hote}{chemin}" + (f"?{'&'.join(params)}" if params else "")


def monitored_urls(aide: Aide) -> list[MonitoredUrl]:
    """URL surveillées pour une aide, dédupliquées, dans un ordre stable.

    `url_officielle` d'abord (c'est la page principale, dont la mort déclenche
    une escalade), puis les pages déjà snapshotées, puis `formulaire_url` — ce
    dernier n'est qu'un contrôle de vivacité : son contenu n'est ni diffé ni
    cité, seul son code HTTP compte.

    La déduplication se fait sur `cle_url` : une baseline archivée sous
    `https://www.site.fr/aide/` sert la page officielle saisie
    `http://site.fr/aide`, et cette page n'est pas surveillée deux fois.
    """
    baselines = _snapshot_baselines(aide.slug)
    # À clé égale, la dernière (tri par nom = tri par date) gagne.
    par_cle = {cle_url(url): m for url, m in sorted(baselines.items())}
    urls: list[MonitoredUrl] = []
    seen: set[str] = set()

    if est_http(officielle := aide.source.url_officielle):
        assert officielle is not None
        base = baselines.get(officielle) or par_cle.get(cle_url(officielle))
        urls.append(
            MonitoredUrl(
                url=officielle,
                role="officielle",
                label=base.label if base else None,
                baseline_path=base.baseline_path if base else None,
                baseline_sha=base.baseline_sha if base else None,
                baseline_body=base.baseline_body if base else None,
                baseline_empreinte_texte=base.baseline_empreinte_texte if base else None,
                is_binary=base.is_binary if base else not _est_textuel("", officielle),
            )
        )
        seen.add(cle_url(officielle))

    for url in sorted(baselines):
        if (cle := cle_url(url)) not in seen:
            urls.append(baselines[url])
            seen.add(cle)

    formulaire = aide.source.formulaire_url
    if est_http(formulaire) and cle_url(formulaire) not in seen:  # type: ignore[arg-type]
        assert formulaire is not None
        urls.append(MonitoredUrl(url=formulaire, role="formulaire"))
    return urls


def relier_redirections(col: AideCollect) -> None:
    """Une officielle sans baseline, redirigée vers une page archivée, hérite d'elle.

    `cle_url` rapproche les variantes d'écriture d'une même adresse ; il ne
    peut rien contre une redirection vers un AUTRE chemin ou un autre domaine
    (`ille-et-vilaine.fr/...` → `nous-vous-ille.fr/...`), connue seulement
    après téléchargement. Dans ce cas la page officielle et la page archivée
    sont la même ; on donne à l'officielle la baseline de la cible, et la cible
    quitte la liste — sinon la même page compterait pour deux URL distinctes,
    et `lignes_de_chrome` prendrait son vrai changement pour du gabarit.
    """
    off = col.page_principale
    if off is None or off.has_baseline:
        return
    res = col.fetched.get(off.url)
    if not (res and res.ok and res.url_finale):
        return
    cle = cle_url(res.url_finale)
    if cle == cle_url(off.url):
        return
    cible = next((m for m in col.urls if m.role == "snapshot" and cle_url(m.url) == cle), None)
    if cible is None:
        return
    heritee = replace(cible, url=off.url, role="officielle")
    col.urls = [heritee if m is off else m for m in col.urls if m is not cible]


# ---------------------------------------------------------------------------
# Téléchargement
# ---------------------------------------------------------------------------


@dataclass
class FetchResult:
    url: str
    status: int | None = None
    error: str | None = None
    # Adresse où le téléchargement a abouti, redirections suivies. C'est elle
    # que porte l'en-tête d'un snapshot : voir `relier_redirections`.
    url_finale: str | None = None
    # Texte brut tel que reçu — c'est lui qui porte le sha comparé à l'en-tête.
    raw_text: str | None = None
    # Markdown : terme de droite du diff, et support du contrôle des quotes.
    body_md: str | None = None
    sha256: str | None = None
    # Contenu non textuel (PDF, .docx, tableur). Ses octets sont conservés :
    # un PDF s'extrait en texte (`texte_pdf`) et se ré-archive tel quel quand il
    # a changé ; sans eux, un règlement modifié était vu par son sha puis oublié.
    is_binary: bool = False
    content: bytes | None = None
    # Texte tiré d'un PDF frais par `pdftotext`. None pour un binaire non PDF,
    # un PDF illisible ou un outil absent — jamais une chaîne vide « lisible ».
    texte_pdf: str | None = None
    # Document Word : son texte est dans `body_md`, et c'est lui que porte le
    # sha, comme dans l'en-tête de `write_docx_snapshot` (re-zipper un document
    # identique change ses octets, pas son texte).
    docx: bool = False
    via_proxy: bool = False
    elapsed_s: float = 0.0
    retried: bool = False

    @property
    def empreinte_texte(self) -> str | None:
        return empreinte_texte(self.texte_pdf)

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
        """La page n'existe plus — c'est une décision éditoriale, pas une panne.

        Une redirection restée en bout de chaîne compte aussi : sans `Location`,
        rien n'a pu la suivre. Vu sur maregionsud.fr le 2026-10-04 : la fiche
        d'un appel à projets retiré répond 301 sans destination et sert la liste
        des aides de la Région.
        """
        if self.status is not None and 300 <= self.status < 400:
            return True
        return self.status in (404, 410)

    @property
    def texte(self) -> str | None:
        """Contenu fouillable et diffable : markdown d'une page, ou texte d'un PDF.

        C'est LA définition de « cette URL a fourni un document » pour l'étage B.
        Un binaire qui répond 200 sans rien donner à lire (.docx, scan) rend None
        : le compter comme rafraîchi ferait passer pour disparues toutes les
        citations qu'il justifie.
        """
        if self.body_md:
            return self.body_md
        return self.texte_pdf if pdf_lisible(self.texte_pdf) else None

    @property
    def kind(self) -> Literal["text", "pdf"]:
        return "text" if self.body_md else "pdf"


def _depuis_page(murl: MonitoredUrl, page: Page, *, via_proxy: bool) -> FetchResult:
    """Traduit une `Page` du fetcheur partagé dans le vocabulaire de l'étage B."""
    result = FetchResult(url=murl.url, via_proxy=via_proxy)
    if page.erreur is not None:
        result.error = page.erreur
        return result
    result.status = page.status
    if not 200 <= page.status < 300:
        return result
    result.url_finale = page.url_finale
    result.is_binary = not _est_textuel(page.content_type, murl.url) or page.est_pdf
    if result.is_binary or page.est_docx:
        result.is_binary = True
        result.content = page.contenu
        if est_docx(page.contenu):
            # Un .docx se compare par son TEXTE : c'est ce que l'ingestion
            # archive (`write_docx_snapshot`), et un sha d'octets escaladait
            # l'aide à chaque passage, re-zippage oblige.
            texte = docx_bytes_to_text(page.contenu)
            result.docx = True
            result.body_md = texte or None
            result.sha256 = hashlib.sha256(texte.encode()).hexdigest()
        else:
            # Un binaire ne passe pas par html2text : un .docx y rendait
            # 111 000 caractères de ZIP illisible. Le texte d'un PDF est tiré
            # par `collect()`, hors des threads réseau.
            result.sha256 = hashlib.sha256(page.contenu).hexdigest()
        return result
    result.raw_text = page.texte
    result.sha256 = hashlib.sha256(page.texte.encode()).hexdigest()
    # Le proxy rend déjà du markdown : le reconvertir l'abîmerait.
    result.body_md = page.texte if via_proxy else to_markdown(page.texte)
    return result


def _fetch_one(fetcheur: Fetcheur, murl: MonitoredUrl, *, proxy: str | None) -> FetchResult:
    """Une URL, au plus deux essais. Ne lève jamais : une erreur est une donnée.

    Le contournement des pare-feux (en-têtes de navigateur après un 403, défi
    JavaScript, empreinte TLS de Chrome) est l'affaire du fetcheur ; ce qui
    reste ici est la seconde chance donnée à une panne transitoire.
    """
    via_proxy = proxy == "jina"
    target = f"{JINA_PREFIX}{murl.url}" if via_proxy else murl.url
    start = time.monotonic()
    result = FetchResult(url=murl.url, via_proxy=via_proxy)
    for attempt in (1, 2):
        try:
            result = _depuis_page(murl, fetcheur.get(target), via_proxy=via_proxy)
        except Exception as exc:
            # Rien de ce qu'une URL renvoie ne doit faire tomber le passage :
            # c'est ce qu'un `formulaire_url: mailto:` avait fait, après tout
            # le téléchargement, sans rapport ni manifeste.
            result = FetchResult(
                url=murl.url, via_proxy=via_proxy, error=f"{type(exc).__name__}: {exc}"
            )
        # Le 403 a déjà eu droit aux en-têtes de navigateur puis au repli
        # `curl_cffi` : le réémettre à l'identique ne changerait rien.
        if attempt == 1 and not result.ok and result.reessayable and result.status != 403:
            result.retried = True
            time.sleep(RETRY_BACKOFF_S)
            continue
        break
    result.retried = result.retried or attempt == 2
    result.elapsed_s = time.monotonic() - start
    return result


def _fetch_all(
    urls: list[MonitoredUrl], *, concurrency: int, timeout: float, proxy: str | None
) -> dict[str, FetchResult]:
    """Télécharge tout, une tâche par hôte, `concurrency` hôtes à la fois.

    Le fetcheur sérialise déjà un même hôte, avec une seconde entre deux
    requêtes. Répartir par URL laisserait tous les threads attendre le même
    verrou (les URL triées regroupent les hôtes) pendant que les autres sites
    restent sans requête ; répartir par hôte occupe chaque thread utilement.
    """
    # Import local : le fetcheur exige le groupe `pipeline` (truststore,
    # curl_cffi), alors que `load_baselines` et `cle_url` sont importés par le
    # lint et par d'autres scripts qui ne téléchargent rien.
    from pipeline.web import Fetcheur

    par_hote: dict[str, list[MonitoredUrl]] = defaultdict(list)
    for m in urls:
        par_hote[m.host].append(m)

    def traiter_hote(lot: list[MonitoredUrl]) -> list[FetchResult]:
        # Un fetcheur par hôte, donc par thread ; sans cache, le dédoublonnage
        # est déjà fait et un 503 mis en cache fausserait la seconde chance.
        with Fetcheur(timeout=timeout, taille_cache=0) as fetcheur:
            return [_fetch_one(fetcheur, m, proxy=proxy) for m in lot]

    # Les hôtes les plus chargés d'abord : ce sont eux qui bornent la durée.
    lots = sorted(par_hote.values(), key=len, reverse=True)
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        resultats = [r for lot in pool.map(traiter_hote, lots) for r in lot]
    return {r.url: r for r in resultats}


@dataclass
class AideCollect:
    """Tout ce que l'étage A sait d'une aide, avant toute interprétation."""

    slug: str
    urls: list[MonitoredUrl] = field(default_factory=list)
    fetched: dict[str, FetchResult] = field(default_factory=dict)
    baseline_docs: list[tuple[str, str, str]] = field(default_factory=list)
    pdf_illisibles: list[str] = field(default_factory=list)
    # Nom de fichier archivé → URL qu'il archive. Ce qui permet à l'étage B de
    # relier une quote trouvée dans un snapshot à l'URL re-téléchargée.
    baseline_urls: dict[str, str] = field(default_factory=dict)

    @property
    def page_principale(self) -> MonitoredUrl | None:
        return next((u for u in self.urls if u.role == "officielle"), None)

    def fresh_docs(self) -> list[tuple[str, str, str]]:
        """Contenus frais fouillables, pour le contrôle des quotes.

        Pages en markdown (liens aplatis, comme les baselines) ET texte des PDF
        frais lisibles, en type `pdf` : c'est ce qui rend recontrôlables les
        citations justifiées par un règlement PDF re-téléchargé.
        """
        docs = []
        for murl in self.urls:
            if murl.role == "formulaire":
                continue
            res = self.fetched.get(murl.url)
            if not (res and res.ok and (texte := res.texte)):
                continue
            if res.kind == "text":
                docs.append((murl.url, flatten_markdown_links(texte), "text"))
            else:
                docs.append((murl.url, texte, "pdf"))
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
        docs, illisibles, provenance = load_baselines(aide.slug)
        collects[aide.slug] = AideCollect(
            slug=aide.slug,
            urls=monitored_urls(aide),
            baseline_docs=docs,
            pdf_illisibles=illisibles,
            baseline_urls=provenance,
        )

    if offline:
        return collects

    # Dédupliqué : deux aides peuvent surveiller la même page (les aides
    # Hauts-de-France partagent leur guide), on ne la télécharge qu'une fois.
    par_url: dict[str, MonitoredUrl] = {}
    for col in collects.values():
        for murl in col.urls:
            par_url.setdefault(murl.url, murl)

    fetched = _fetch_all(
        sorted(par_url.values(), key=lambda m: m.url),
        concurrency=concurrency,
        timeout=timeout,
        proxy=proxy,
    )
    # Texte des PDF frais, une fois par URL et hors de la boucle réseau. Un
    # binaire qui n'est pas un PDF (.docx, tableur) reste sans texte : il n'est
    # comparable que par sha.
    for res in fetched.values():
        if res.ok and est_pdf(res.content):
            assert res.content is not None
            res.texte_pdf = pdf_bytes_to_text(res.content)

    for col in collects.values():
        col.fetched = {m.url: fetched[m.url] for m in col.urls if m.url in fetched}
        relier_redirections(col)
    return collects
