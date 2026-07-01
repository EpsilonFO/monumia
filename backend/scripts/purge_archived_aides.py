"""
Purge : supprime d'`aides_v3` les aides YAML qui ont disparu de data/aides/*.yaml
(typiquement déplacées dans data/aides/archives/).

Pourquoi un script dédié : `load_aides_yaml.py` ne supprime jamais — il ne touche
pas aux lignes absentes des YAML, pour ne pas effacer les aides venues d'un autre
canal (sync Aides-Territoires). Une purge doit donc être explicite et prudente.

Garde-fous :
  - On ne supprime QUE les lignes gérées par les YAML : `slug` renseigné. Les
    aides importées depuis Aides-Territoires (tag « aides-territoires ») sont
    épargnées même si un slug a été posé.
  - On épargne aussi toute aide encore référencée par un dossier ou un suivi
    utilisateur (`dossiers.aide_id` / `aide_suivis.aide_id`, qui stockent le slug
    ou l'uuid). Supprimer une telle aide laisserait une référence pendante.
  - `aide_conditions` part automatiquement (FK ON DELETE CASCADE).

Dry-run par défaut : le script n'écrit RIEN sans `--apply`.

Run:
    cd backend && uv run python scripts/purge_archived_aides.py            # rapport seul
    cd backend && uv run python scripts/purge_archived_aides.py --apply    # supprime
"""

import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env.local", override=True)

from supabase import create_client

from aides_schema import load_all_aides


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _is_referenced(supabase, slug: str, aide_id: str) -> bool:
    """True si un dossier ou un suivi pointe vers cette aide (par slug ou uuid)."""
    keys = [k for k in (slug, aide_id) if k]
    for table in ("dossiers", "aide_suivis"):
        res = supabase.table(table).select("aide_id").in_("aide_id", keys).limit(1).execute()
        if res.data:
            return True
    return False


def main() -> int:
    apply = "--apply" in sys.argv

    current_slugs = set(load_all_aides().keys())
    print(f"{len(current_slugs)} aides actives dans data/aides/*.yaml")

    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

    rows = supabase.table("aides_v3").select("id, nom, slug, tags").execute().data or []

    # Candidats : lignes gérées par les YAML (slug posé), hors import
    # Aides-Territoires, dont le slug a disparu des YAML actifs.
    candidates = [
        r
        for r in rows
        if r.get("slug")
        and "aides-territoires" not in (r.get("tags") or [])
        and r["slug"] not in current_slugs
    ]

    to_delete, protected = [], []
    for r in candidates:
        if _is_referenced(supabase, r["slug"], r["id"]):
            protected.append(r)
        else:
            to_delete.append(r)

    print(f"\n{len(candidates)} aide(s) absente(s) des YAML actifs :")
    for r in to_delete:
        print(f"  - À SUPPRIMER : {r['slug']}  ({r['nom']})")
    for r in protected:
        print(f"  - ÉPARGNÉE (référencée par un dossier/suivi) : {r['slug']}  ({r['nom']})")

    if not to_delete:
        print("\nRien à supprimer.")
        return 0

    if not apply:
        print(f"\n--dry-run : {len(to_delete)} suppression(s) prévue(s). Relancer avec --apply.")
        return 0

    ids = [r["id"] for r in to_delete]
    # aide_conditions part en cascade (FK ON DELETE CASCADE).
    supabase.table("aides_v3").delete().in_("id", ids).execute()
    print(f"\n✓ {len(ids)} aide(s) supprimée(s).")
    if protected:
        print(f"  {len(protected)} épargnée(s) car référencée(s) — à traiter à la main si besoin.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
