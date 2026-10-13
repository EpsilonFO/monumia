"""Télécharge le lot aveugle de l'échantillon de contrôle du tri sur titre.

Commande, depuis backend/ :

    uv run python scripts/mesures/tri_titre_echantillon.py

Entrée : backend/data/reviews/logs/refonte/2026-10-10-tri-titre-1/lot_aveugle.jsonl,
150 URL (100 écartées au tri sur titre, 50 gardées au même tri) mêlées sous un
identifiant aveugle, tirées par scripts/mesures/tri_titre.py (graine 20261010).

Sortie, dans backend/data/reviews/logs/refonte/2026-10-10-tri-titre-echantillon-1/ :

- pages/<id_aveugle>.md : le texte que la lecture de prospection aurait jugé,
  par la même extraction (prospection.lecture._texte_a_juger : markdown de la
  page, ou texte du PDF), tronqué à lecture.MAX_CAR_PAGE comme en production ;
- telechargements.jsonl : une ligne par URL (statut HTTP, URL finale, erreur,
  raison de l'absence de texte, longueur du texte).

Un seul processus et le Fetcheur du pipeline : une seconde au moins entre deux
requêtes au même hôte. Aucun appel de modèle. Rien n'est écrit sous
backend/data/ hors du dossier de sortie ; le cache pdftotext de veille_collect
va dans backend/.cache/, ignoré par git.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

from pipeline.web import Fetcheur  # noqa: E402
from prospection.lecture import MAX_CAR_PAGE, _texte_a_juger  # noqa: E402

LOGS = SCRIPTS.parent / "data" / "reviews" / "logs" / "refonte"
ENTREE = LOGS / "2026-10-10-tri-titre-1" / "lot_aveugle.jsonl"
SORTIE = LOGS / "2026-10-10-tri-titre-echantillon-1"


def main() -> int:
    lot = [json.loads(ligne) for ligne in ENTREE.read_text(encoding="utf-8").splitlines() if ligne]
    pages = SORTIE / "pages"
    pages.mkdir(parents=True, exist_ok=False)
    debut = time.monotonic()
    with (
        Fetcheur() as fetcheur,
        (SORTIE / "telechargements.jsonl").open("w", encoding="utf-8") as journal,
    ):
        for i, entree in enumerate(lot, 1):
            ident, url = entree["id_aveugle"], entree["url"]
            page = fetcheur.get(url)
            texte, raison = _texte_a_juger(page) if page.ok else ("", None)
            texte = texte[:MAX_CAR_PAGE]
            if texte:
                (pages / f"{ident}.md").write_text(texte, encoding="utf-8")
            ligne = {
                "id_aveugle": ident,
                "url": url,
                "url_finale": page.url_finale,
                "status": page.status,
                "erreur": page.erreur,
                "pdf": page.est_pdf,
                "raison_sans_texte": raison,
                "longueur": len(texte),
            }
            journal.write(json.dumps(ligne, ensure_ascii=False) + "\n")
            journal.flush()
            print(
                f"[{i}/{len(lot)}] {ident} {page.status} {len(texte)} car. {raison or page.erreur or ''}"
            )
    print(f"fini en {time.monotonic() - debut:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
