"""Réglages communs à toute la suite de tests.

`MONUMIA_ESPACE=0` coupe l'espace d'embedding et Jev dans les outils de
l'ingestion et ses contrôles (`catalogue/espace.py`) : `db.py` charge
`.env.local`, la clé OpenRouter serait donc là, et un test ferait des appels
payants et non déterministes. Les tests de l'espace l'injectent eux-mêmes.
"""

import os

os.environ["MONUMIA_ESPACE"] = "0"
