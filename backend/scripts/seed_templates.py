"""
Seed: bibliothèque de modèles (templates) de documents.

Lit `backend/seed/templates/manifest.json` + les fichiers de
`backend/seed/templates/files/`, téléverse chaque fichier dans le bucket
Storage `templates` (public) puis upsert la ligne correspondante dans la table
`templates`. Idempotent sur `slug` : réexécutable après remplacement des
fichiers par les vrais modèles.

Run:
    cd backend && uv run python3 scripts/seed_templates.py
"""

import json
import mimetypes
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env.local"), override=True)

from supabase import create_client

BUCKET = "templates"
SEED_DIR = os.path.join(os.path.dirname(__file__), "..", "seed", "templates")
FILES_DIR = os.path.join(SEED_DIR, "files")

# A couple of patrimoine-friendly mime types not always known to mimetypes.
_EXTRA_MIME = {
    ".md": "text/markdown",
    ".csv": "text/csv",
}


def _guess_mime(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext in _EXTRA_MIME:
        return _EXTRA_MIME[ext]
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def main() -> None:
    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

    with open(os.path.join(SEED_DIR, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)

    for entry in manifest:
        slug = entry["slug"]
        filename = entry["fichier"]
        local_path = os.path.join(FILES_DIR, filename)
        with open(local_path, "rb") as fh:
            content = fh.read()

        ext = os.path.splitext(filename)[1].lstrip(".").lower()
        mime = _guess_mime(filename)
        # Store under a slug-based path so re-runs overwrite the same object.
        storage_path = f"{slug}.{ext}"

        supabase.storage.from_(BUCKET).upload(
            storage_path,
            content,
            {"content-type": mime, "upsert": "true"},
        )

        row = {
            "slug": slug,
            "nom": entry["nom"],
            "description": entry.get("description"),
            "type_document": entry["type_document"],
            "tags": entry.get("tags", []),
            "categories_aide": entry.get("categories_aide", []),
            "organisme": entry.get("organisme"),
            "fichier_url": storage_path,
            "nom_fichier": filename,
            "extension": ext,
            "mime_type": mime,
            "taille_fichier": len(content),
            "source_url": entry.get("source_url"),
        }

        supabase.table("templates").upsert(row, on_conflict="slug").execute()
        print(f"  ✓ {slug} ({len(content)} o, {mime})")

    print(f"Seed terminé : {len(manifest)} modèles.")


if __name__ == "__main__":
    main()
