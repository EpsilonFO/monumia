"""
Snapshot d'une source officielle d'aide → data/sources/<slug>/.

La provenance est la base du workflow d'ingestion : chaque quote d'une
condition doit être vérifiable contre un snapshot daté, et la détection de
changement de règlement diffe les snapshots successifs.

- URL HTML  → markdown (html2text) avec en-tête de métadonnées (url, date, sha256)
- URL PDF   → copie binaire .pdf (lisible par l'agent via Read)
- Fichier local (PDF/HTML/MD) → copie avec en-tête quand c'est du texte

Run:
    cd backend && uv run python scripts/snapshot_source.py <slug> <url-ou-chemin> [label]

Imprime le chemin du snapshot créé (relatif à backend/).
"""

import hashlib
import re
import shutil
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import html2text
import httpx

BACKEND_DIR = Path(__file__).resolve().parent.parent
SOURCES_DIR = BACKEND_DIR / "data" / "sources"

UA = "Mozilla/5.0 (compatible; MonumiaIngest/1.0; +https://monumia.fr)"


def _meta_header(url: str, content_sha256: str) -> str:
    return (
        "---\n"
        f"url: {url}\n"
        f"fetched_at: {datetime.now(UTC).isoformat(timespec='seconds')}\n"
        f"sha256: {content_sha256}\n"
        "---\n\n"
    )


def _to_markdown(html: str) -> str:
    h = html2text.HTML2Text()
    h.body_width = 0  # pas de re-wrap : les quotes doivent rester cherchables
    h.ignore_images = True
    h.ignore_emphasis = True
    return h.handle(html)


def snapshot(slug: str, source: str, label: str | None = None) -> Path:
    if not re.fullmatch(r"[a-z0-9-]+", slug):
        raise SystemExit(f"slug invalide : {slug}")
    out_dir = SOURCES_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat() + (f"-{label}" if label else "")

    if source.startswith(("http://", "https://")):
        resp = httpx.get(source, headers={"User-Agent": UA}, follow_redirects=True, timeout=30)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "pdf" in content_type or source.lower().endswith(".pdf"):
            path = out_dir / f"{stamp}.pdf"
            path.write_bytes(resp.content)
        else:
            md = _to_markdown(resp.text)
            sha = hashlib.sha256(resp.text.encode()).hexdigest()
            path = out_dir / f"{stamp}.md"
            path.write_text(_meta_header(str(resp.url), sha) + md, encoding="utf-8")
    else:
        src = Path(source).expanduser()
        if not src.exists():
            raise SystemExit(f"fichier introuvable : {src}")
        if src.suffix.lower() == ".pdf":
            path = out_dir / f"{stamp}.pdf"
            shutil.copyfile(src, path)
        else:
            text = src.read_text(encoding="utf-8")
            body = _to_markdown(text) if src.suffix.lower() in (".html", ".htm") else text
            sha = hashlib.sha256(text.encode()).hexdigest()
            path = out_dir / f"{stamp}.md"
            path.write_text(_meta_header(f"file://{src}", sha) + body, encoding="utf-8")

    return path


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
