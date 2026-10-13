"""Alias : `veille_collect` vit désormais dans `backend/catalogue/veille_collect.py` (refonte, incrément I5).

L'ancien chemin d'import reste valable pour les scripts et les tests : ce fichier
remplace son propre module par celui du paquet, si bien que `import veille_collect` rend
le même objet module, et qu'une affectation comme `veille_collect.X = ...` (les
redirections de `ingestion/atelier.py`) vise le vrai module. L'alias disparaît
avec l'ancien code (incrément I9b).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalogue import veille_collect as _module  # noqa: E402

sys.modules[__name__] = _module
