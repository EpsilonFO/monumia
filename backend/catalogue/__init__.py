"""Le paquet de la refonte des pipelines du catalogue : prospection, ingestion, veille.

Il vit hors de `backend/scripts/` pour que pyright l'analyse
(`backend/pyrightconfig.json`). Jusqu'à la bascule, il réutilise des modules
de l'ancien pipeline (normalisation des citations, collecte, Fetcheur) : ils
s'importent depuis `backend/scripts/`, que pyright résout par `extraPaths` et
que l'on ajoute ici au chemin d'import. Ce raccord disparaît quand les modules
gardés auront été déplacés dans le paquet (incrément I5 d'`architecture.md`).
"""

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.append(str(_SCRIPTS))
