"""Lance ingest_aide_agent.py (agent DeepSeek) sur une liste de slugs, en séquence.

Chaque aide est ré-extraite depuis sa source.url_officielle (résolue par
ingest_aide_agent.py). Un échec n'interrompt pas le batch. La sortie complète
de chaque run est loggée dans data/reviews/logs/<slug>.log, la fiche de review
dans data/reviews/<slug>-deepseek-review.md.

Usage :
    cd backend && uv run python scripts/ingest_aides_batch.py <slug> [slug ...]

Exemple — toutes les aides de Normandie :
    uv run python scripts/ingest_aides_batch.py \
        region-normandie \
        normandie-non-proteges-tpn \
        normandie-evenements-touristiques \
        normandie-amenagement-equipement-lieux-culturels \
        eure-mon-village-mon-amour \
        feder-normandie-tourisme-responsable
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
AGENT_SCRIPT = BACKEND_DIR / "scripts" / "ingest_aide_agent.py"
LOG_DIR = BACKEND_DIR / "data" / "reviews" / "logs"


def main() -> int:
    slugs = sys.argv[1:]
    if not slugs:
        print(__doc__)
        return 1

    missing = [s for s in slugs if not (BACKEND_DIR / "data" / "aides" / f"{s}.yaml").exists()]
    if missing:
        print(f"ERREUR : YAML introuvable pour : {', '.join(missing)}", file=sys.stderr)
        return 1

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, str] = {}

    for i, slug in enumerate(slugs, 1):
        print(f"\n{'=' * 70}\n[{i}/{len(slugs)}] {slug}\n{'=' * 70}", flush=True)
        log_path = LOG_DIR / f"{slug}.log"
        start = time.monotonic()
        with log_path.open("w", encoding="utf-8") as log:
            proc = subprocess.Popen(
                [sys.executable, str(AGENT_SCRIPT), slug],
                cwd=str(BACKEND_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            assert proc.stdout is not None
            for line in proc.stdout:  # tee : console + fichier de log
                print(line, end="", flush=True)
                log.write(line)
            code = proc.wait()
        elapsed = time.monotonic() - start
        results[slug] = "OK" if code == 0 else f"ÉCHEC (exit {code})"
        print(
            f"\n→ {slug} : {results[slug]} en {elapsed / 60:.1f} min — log : {log_path.relative_to(BACKEND_DIR)}"
        )

    print(f"\n{'=' * 70}\nRÉCAP BATCH\n{'=' * 70}")
    for slug, status in results.items():
        print(f"  {'✓' if status == 'OK' else '✗'} {slug:<55} {status}")
    print(
        "\nFiches de review dans data/reviews/ — relecture humaine requise avant commit/chargement."
    )
    return 0 if all(s == "OK" for s in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
