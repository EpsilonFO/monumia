"""
Snapshot d'une source officielle d'aide → data/sources/<slug>/.

La provenance est la base du workflow d'ingestion : chaque quote d'une
condition doit être vérifiable contre un snapshot daté, et la détection de
changement de règlement diffe les snapshots successifs.

- URL HTML  → markdown (html2text) avec en-tête de métadonnées (url, date, sha256)
- URL PDF   → copie binaire .pdf (lisible par l'agent via Read) + sidecar de
              provenance `<stamp>.pdf.meta.yaml`
- Fichier local (PDF/HTML/MD) → copie avec en-tête quand c'est du texte

Le module s'utilise aussi comme bibliothèque : `to_markdown`,
`write_md_snapshot` et `write_pdf_snapshot` sont les briques que la veille
(`veille_collect.py`) réutilise pour archiver une page fraîche sans repasser
par le réseau, `snapshot()` ayant déjà téléchargé.

Run :
    cd backend && uv run python scripts/snapshot_source.py <slug> <url-ou-chemin> [label]

Imprime le chemin du snapshot créé (relatif à backend/).
"""

import hashlib
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import html2text
import httpx
import yaml

BACKEND_DIR = Path(__file__).resolve().parent.parent
SOURCES_DIR = BACKEND_DIR / "data" / "sources"

UA = "Mozilla/5.0 (compatible; MonumiaIngest/1.0; +https://monumia.fr)"

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
        resp = httpx.get(source, headers={"User-Agent": UA}, follow_redirects=True, timeout=30)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "pdf" in content_type or source.lower().endswith(".pdf"):
            return write_pdf_snapshot(slug, resp.content, url=str(resp.url), label=label)
        return write_md_snapshot(slug, str(resp.url), resp.text, label=label)

    src = Path(source).expanduser()
    if not src.exists():
        raise SystemExit(f"fichier introuvable : {src}")
    if src.suffix.lower() == ".pdf":
        return write_pdf_snapshot(slug, src.read_bytes(), label=label)
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
