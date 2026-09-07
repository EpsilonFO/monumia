"""
Snapshot d'une source officielle d'aide → data/sources/<slug>/.

La provenance est la base du workflow d'ingestion : chaque quote d'une
condition doit être vérifiable contre un snapshot daté, et la détection de
changement de règlement diffe les snapshots successifs.

- URL HTML  → markdown (html2text) avec en-tête de métadonnées (url, date, sha256)
- URL PDF   → copie binaire .pdf (lisible par l'agent via Read) + sidecar de
              provenance `<stamp>.pdf.meta.yaml`
- URL DOCX  → texte extrait, archivé en .md (cf. `docx_bytes_to_text`)
- Fichier local (PDF/DOCX/HTML/MD) → copie avec en-tête quand c'est du texte

Le module s'utilise aussi comme bibliothèque : `to_markdown`,
`write_md_snapshot` et `write_pdf_snapshot` sont les briques que la veille
(`veille_collect.py`) réutilise pour archiver une page fraîche sans repasser
par le réseau, `snapshot()` ayant déjà téléchargé.

Run :
    cd backend && uv run python scripts/snapshot_source.py <slug> <url-ou-chemin> [label]

Imprime le chemin du snapshot créé (relatif à backend/).
"""

import hashlib
import io
import re
import sys
import time
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

import html2text
import httpx
import yaml

BACKEND_DIR = Path(__file__).resolve().parent.parent
SOURCES_DIR = BACKEND_DIR / "data" / "sources"

UA = "Mozilla/5.0 (compatible; MonumiaIngest/1.0; +https://monumia.fr)"

# Identité de repli pour les sources derrière un WAF qui refuse tout client ne
# ressemblant pas à un navigateur. Mesuré sur www.normandie.fr le 2026-08-19 :
# ni l'UA de navigateur seul, ni les `Sec-Fetch-*` seuls, ni `Accept-Language`
# seul ne passent — c'est leur COMBINAISON qui obtient un 200. L'UA `UA`
# ci-dessus, honnête, reste l'identité par défaut : on ne bascule ici qu'après
# un 403, source par source, jamais d'emblée.
UA_NAVIGATEUR = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
HEADERS_NAVIGATEUR = {
    "User-Agent": UA_NAVIGATEUR,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    # Décisif, et pas seulement décoratif : le WAF de normandie.fr rend 403 sur
    # le défaut de httpx (`gzip, deflate, zstd`) comme sur `gzip, deflate`, et
    # 200 dès que `br` figure dans la liste. D'où la dépendance `brotli` : sans
    # elle, httpx annoncerait un encodage qu'il ne sait pas décoder et lèverait
    # une ImportError si le serveur choisissait brotli.
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}

# « Shield » à défi JavaScript : au lieu de la page, le serveur rend un script
# d'une trentaine de lignes qui pose un cookie calculé puis redirige. La réponse
# fait 200 et moins d'un kilo-octet — donc ni 403 ni erreur, juste une page vide
# de substance, ce qui sortait en ERREUR_HTTP sur les 10 aides d'AURA.
#
# Les constantes sont LUES dans le script au lieu d'être codées en dur : le
# multiplicateur est un paramètre du dispositif, pas une propriété du protocole,
# et le jour où il change on veut continuer à passer sans nouvelle release.
_SHIELD_CALCUL = re.compile(r"\(\s*challenge\s*\*\s*(\d+)\s*\)\s*%\s*(\d+)")
_SHIELD_COOKIE = re.compile(r"""setCookie\(\s*["']([^"']+)["']\s*,\s*challenge""")
# Au-delà, ce n'est pas une page de défi mais un document : on ne va pas
# chercher un script dans 80 Ko de HTML légitime.
_SHIELD_TAILLE_MAX = 8192


def resoudre_shield(contenu: bytes) -> tuple[str, str] | None:
    """(nom, valeur) du cookie à poser, ou None si ce n'est pas une page de défi.

    Le défi est un simple `(Date.now() * k) % m`. On le rejoue en Python ; rien
    n'est deviné, tout est lu dans la page.
    """
    if len(contenu) > _SHIELD_TAILLE_MAX:
        return None
    texte = contenu.decode("utf-8", errors="replace")
    calcul = _SHIELD_CALCUL.search(texte)
    cookie = _SHIELD_COOKIE.search(texte)
    if not calcul or not cookie:
        return None
    multiplicateur, modulo = int(calcul.group(1)), int(calcul.group(2))
    if modulo == 0:
        return None
    # `Date.now()` : millisecondes depuis l'epoch.
    challenge = int(time.time() * 1000)
    return cookie.group(1), f"{challenge}:{(challenge * multiplicateur) % modulo}"


# Slug ET label composent un nom de fichier : sans validation, un label du type
# « ../../secrets » ferait écrire hors du dossier des sources.
NAME_RE = re.compile(r"[a-z0-9-]+")

# Suffixes de désambiguïsation quand deux sources DIFFÉRENTES sont snapshotées
# le même jour sous le même label (ex. deux pages d'un même règlement).
_VARIANTS = ("", *(f"-{c}" for c in "bcdefghijklmnopqrstuvwxyz"))

# Le sha256 de l'en-tête, lu sans parser tout le document. Volontairement local
# plutôt qu'emprunté à `veille_text` : ce module écrit l'en-tête, il doit rester
# autonome — c'est l'outil que l'agent d'ingestion appelle en ligne de commande.
_HEADER_SHA_RE = re.compile(r"\A---\r?\n.*?^sha256:[ \t]*([0-9a-f]{64})[ \t]*$", re.DOTALL | re.M)


def _meta_header(url: str, content_sha256: str) -> str:
    return (
        "---\n"
        f"url: {url}\n"
        f"fetched_at: {datetime.now(UTC).isoformat(timespec='seconds')}\n"
        f"sha256: {content_sha256}\n"
        "---\n\n"
    )


def to_markdown(html: str) -> str:
    h = html2text.HTML2Text()
    h.body_width = 0  # pas de re-wrap : les quotes doivent rester cherchables
    h.ignore_images = True
    h.ignore_emphasis = True
    # Sans ça, html2text rabat sur l'ASCII les accents écrits en entités HTML
    # (`&agrave;` → « a ») : « s'adresse à tous les propriétaires » devenait
    # « s'adresse a tous les proprietaires » dans l'archive, et toute quote
    # prise dessus était un faux verbatim. Mesuré sur pass-renovation.hautsde
    # france.fr le 2026-09-04. Le sha256 de l'en-tête porte sur le HTML brut,
    # pas sur ce markdown : aucune baseline de veille n'en dépend.
    h.unicode_snob = True
    return h.handle(html)


def _validate_names(slug: str, label: str | None) -> None:
    if not NAME_RE.fullmatch(slug):
        raise SystemExit(f"slug invalide : {slug}")
    if label is not None and not NAME_RE.fullmatch(label):
        raise SystemExit(f"label invalide : {label}")


def _prepare(slug: str, label: str | None, jour: date | None = None) -> tuple[Path, str]:
    """Valide les noms, crée le dossier de l'aide, retourne (dossier, horodatage).

    `jour` est la date du PASSAGE, pas celle de l'écriture. Un appelant qui en
    porte une (la veille date tout son passage d'un seul coup) la fournit, sinon
    c'est aujourd'hui. Sans ça, un passage qui franchit minuit archiverait la
    preuve à une date que la fiche qu'il vient d'écrire ne porte pas.
    """
    _validate_names(slug, label)
    out_dir = SOURCES_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir, (jour or date.today()).isoformat() + (f"-{label}" if label else "")


def _resolve_target(
    out_dir: Path, stamp: str, suffix: str, sha: str, read_sha
) -> tuple[Path, bool]:
    """Chemin d'écriture du jour, et si le contenu y est DÉJÀ archivé.

    Trois issues, dans cet ordre :
      - le fichier du jour n'existe pas          → on l'écrit
      - il existe avec le même sha256            → on le réutilise, sans réécrire
      - il existe avec un contenu différent      → variante `-b`, `-c`…

    Sans cette résolution, deux snapshots du même jour s'écrasaient en silence :
    le second effaçait la preuve du premier, alors que c'est précisément leur
    différence qui documente un changement de règlement. Réutiliser le fichier
    identique plutôt que le réécrire garde par ailleurs le `git diff` vide quand
    rien n'a bougé — c'est cette revue humaine du diff qui valide la veille.
    """
    for variant in _VARIANTS:
        path = out_dir / f"{stamp}{variant}{suffix}"
        if not path.exists():
            return path, False
        if read_sha(path) == sha:
            return path, True
    raise SystemExit(f"plus de 26 snapshots distincts le même jour pour {out_dir.name}/{stamp}")


def _read_md_sha(path: Path) -> str | None:
    m = _HEADER_SHA_RE.match(path.read_text(encoding="utf-8", errors="replace"))
    return m.group(1) if m else None


# --- .docx -----------------------------------------------------------------
#
# Les guides d'aides régionaux publient volontiers leur règlement
# d'intervention en .docx, et c'est là que vivent les critères fins. Sans
# conversion, l'archive contenait le ZIP brut (« PK...[Content_Types].xml ») :
# illisible pour l'agent, et aucune quote ne pouvait s'y retrouver. Mesuré sur
# hdf-jardins-en-scene le 2026-09-06 — 8 des 34 conditions de la référence, dont
# 2 exigences décisives et l'assiette de financement, ne sont citables QUE
# depuis les deux annexes .docx. Le pipeline manuel les convertissait à la main,
# hors bande ; celui payé à l'API n'avait pas de mains.
#
# Stdlib volontairement : un .docx est un ZIP contenant `word/document.xml`,
# et l'extraction du texte ne vaut pas une dépendance de plus.
_NS_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_NS_MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
_DOCX_ENTREE = "word/document.xml"


def est_docx(content: bytes) -> bool:
    """Vrai si ces octets sont un document Word (ZIP portant `word/document.xml`).

    Le test porte sur le CONTENU, pas sur l'extension ni le content-type : un
    .xlsx et un .zip commencent par la même signature `PK\\x03\\x04`.
    """
    if content[:4] != b"PK\x03\x04":
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            return _DOCX_ENTREE in archive.namelist()
    except (zipfile.BadZipFile, OSError):
        return False


def _texte_paragraphe(paragraphe: ElementTree.Element) -> str:
    """Texte des runs de CE paragraphe, sans descendre dans ceux qu'il contient.

    Une zone de texte Word porte ses propres `w:p` : les parcourir depuis le
    paragraphe qui les ancre sortait leur contenu deux fois, une fois agrégé
    dans l'ancre et une fois pour lui-même. Chaque paragraphe ne rend donc que
    ses propres runs, les imbriqués étant rendus pour leur compte, dans l'ordre
    du document.
    """
    morceaux: list[str] = []

    def descendre(noeud: ElementTree.Element) -> None:
        for enfant in noeud:
            if enfant.tag == f"{_NS_W}p":
                continue
            if enfant.tag == f"{_NS_W}t":
                morceaux.append(enfant.text or "")
            elif enfant.tag == f"{_NS_W}tab":
                morceaux.append("\t")
            elif enfant.tag in (f"{_NS_W}br", f"{_NS_W}cr"):
                morceaux.append("\n")
            descendre(enfant)

    descendre(paragraphe)
    return "".join(morceaux).strip()


def docx_bytes_to_text(content: bytes) -> str:
    """Texte d'un .docx, un paragraphe par ligne. Chaîne vide si illisible.

    Les paragraphes des cellules de tableau sont des `w:p` comme les autres :
    ils ressortent donc en lignes, ce qui suffit pour citer un règlement. Rend
    "" plutôt que de lever — un document illisible est une donnée que
    l'appelant signale, pas une exception (même contrat que `pdf_bytes_to_text`).
    """
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            xml = archive.read(_DOCX_ENTREE)
        racine = ElementTree.fromstring(xml)
    except (KeyError, zipfile.BadZipFile, OSError, ElementTree.ParseError):
        return ""
    # Word duplique le contenu des zones de texte dans une branche de repli
    # `mc:Fallback` destinée aux lecteurs anciens : le même encadré y figure
    # une seconde fois, en VML.
    replis = {p for repli in racine.iter(f"{_NS_MC}Fallback") for p in repli.iter(f"{_NS_W}p")}
    lignes = [
        texte
        for paragraphe in racine.iter(f"{_NS_W}p")
        if paragraphe not in replis and (texte := _texte_paragraphe(paragraphe))
    ]
    return "\n\n".join(lignes) + "\n" if lignes else ""


def write_docx_snapshot(
    slug: str,
    content: bytes,
    *,
    url: str | None = None,
    label: str | None = None,
    jour: date | None = None,
) -> tuple[Path, str]:
    """Archive le TEXTE d'un .docx en .md. Retourne (chemin, texte extrait).

    Contrairement au PDF, c'est le texte converti qui est archivé et dont le
    sha256 est pris — et c'est plus juste ici : re-zipper un document identique
    change ses octets (horodatages internes), donc un sha sur le binaire
    signalerait un changement de règlement à chaque re-téléchargement.
    """
    texte = docx_bytes_to_text(content)
    chemin = write_md_snapshot(
        slug,
        url or f"docx://{slug}",
        texte,
        label=label,
        body_is_markdown=True,
        jour=jour,
    )
    return chemin, texte


def write_md_snapshot(
    slug: str,
    url: str,
    raw_text: str,
    *,
    label: str | None = None,
    body_is_markdown: bool = False,
    jour: date | None = None,
) -> Path:
    """Archive une source textuelle. `raw_text` est le contenu BRUT récupéré.

    Le sha256 de l'en-tête porte sur `raw_text`, pas sur le markdown écrit :
    c'est ce qui permet à la veille de comparer une page fraîchement
    téléchargée à sa baseline sans avoir à la reconvertir.

    `body_is_markdown=True` quand la source est déjà du texte (fichier .md, page
    récupérée via un proxy) : la conversion html2text l'abîmerait.
    """
    out_dir, stamp = _prepare(slug, label, jour)
    sha = hashlib.sha256(raw_text.encode()).hexdigest()
    path, already = _resolve_target(out_dir, stamp, ".md", sha, _read_md_sha)
    if not already:
        body = raw_text if body_is_markdown else to_markdown(raw_text)
        path.write_text(_meta_header(url, sha) + body, encoding="utf-8")
    return path


def write_pdf_snapshot(
    slug: str,
    content: bytes,
    *,
    url: str | None = None,
    label: str | None = None,
    jour: date | None = None,
) -> Path:
    """Archive un PDF et sa provenance.

    Un PDF ne peut pas porter d'en-tête de métadonnées : la provenance va dans
    un sidecar `<stamp>.pdf.meta.yaml`. Sans lui, un règlement archivé n'est
    plus rattachable à son URL et la veille ne peut ni le re-télécharger ni
    dater son contenu — c'est le cas des 109 PDF déjà présents dans le dépôt,
    qui resteront sans provenance (ils sont antérieurs à ce sidecar).
    """
    out_dir, stamp = _prepare(slug, label, jour)
    sha = hashlib.sha256(content).hexdigest()
    path, already = _resolve_target(
        out_dir, stamp, ".pdf", sha, lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    )
    if not already:
        path.write_bytes(content)
    sidecar = path.with_name(path.name + ".meta.yaml")
    # Jamais réécrit : un sidecar existant porte la date de la VRAIE première
    # récupération, et le rafraîchir polluerait le diff pour rien.
    if not sidecar.exists():
        meta = {"fetched_at": datetime.now(UTC).isoformat(timespec="seconds"), "sha256": sha}
        if url:
            meta["url"] = url
        sidecar.write_text(
            yaml.safe_dump(meta, allow_unicode=True, sort_keys=True), encoding="utf-8"
        )
    return path


def snapshot(slug: str, source: str, label: str | None = None) -> Path:
    # Validation AVANT le téléchargement : un slug fautif ne doit pas coûter un
    # aller-retour réseau, ni sortir sur une erreur httpx qui masque la cause.
    _validate_names(slug, label)
    if source.startswith(("http://", "https://")):
        # Client plutôt que `httpx.get` : franchir le shield exige de conserver
        # un cookie entre deux requêtes.
        with httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=30) as client:
            resp = client.get(source)
            if resp.status_code == 403:
                # WAF anti-bot : un 403 est déterministe, seul un changement
                # d'identité a une chance de passer (cf. HEADERS_NAVIGATEUR).
                resp = client.get(source, headers=HEADERS_NAVIGATEUR)
            if (defi := resoudre_shield(resp.content)) is not None:
                nom, valeur = defi
                client.cookies.set(nom, valeur, domain=urlsplit(str(resp.url)).netloc)
                resp = client.get(source, headers=HEADERS_NAVIGATEUR)
            resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "pdf" in content_type or source.lower().endswith(".pdf"):
            return write_pdf_snapshot(slug, resp.content, url=str(resp.url), label=label)
        if est_docx(resp.content):
            return write_docx_snapshot(slug, resp.content, url=str(resp.url), label=label)[0]
        return write_md_snapshot(slug, str(resp.url), resp.text, label=label)

    src = Path(source).expanduser()
    if not src.exists():
        raise SystemExit(f"fichier introuvable : {src}")
    if src.suffix.lower() == ".pdf":
        return write_pdf_snapshot(slug, src.read_bytes(), label=label)
    if src.suffix.lower() == ".docx":
        return write_docx_snapshot(slug, src.read_bytes(), url=f"file://{src}", label=label)[0]
    return write_md_snapshot(
        slug,
        f"file://{src}",
        src.read_text(encoding="utf-8"),
        label=label,
        body_is_markdown=src.suffix.lower() not in (".html", ".htm"),
    )


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    slug, source = sys.argv[1], sys.argv[2]
    label = sys.argv[3] if len(sys.argv) > 3 else None
    path = snapshot(slug, source, label)
    print(path.relative_to(BACKEND_DIR))
    return 0


if __name__ == "__main__":
    sys.exit(main())
