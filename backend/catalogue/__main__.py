"""Les commandes du paquet : `uv run python -m catalogue <commande>`, depuis `backend/`.

- `convertir --journal <dossier> [--verifier]` : importe l'état de l'ancien
  pipeline (file, manifeste de veille, fiches, instantanés, YAML) dans un
  journal ; `--verifier` reprojette ensuite la file et le manifeste depuis ce
  journal et les compare octet pour octet aux fichiers en service.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(prog="python -m catalogue")
    commandes = parseur.add_subparsers(dest="commande", required=True)

    c = commandes.add_parser("convertir", help="importer l'état de l'ancien pipeline au journal")
    c.add_argument(
        "--journal",
        type=Path,
        required=True,
        help="dossier du journal à compléter ; avant la bascule, jamais data/catalogue/journal",
    )
    c.add_argument(
        "--verifier",
        action="store_true",
        help="reprojeter la file et le manifeste depuis le journal et les comparer à l'octet",
    )

    args = parseur.parse_args(argv)
    if args.commande == "convertir":
        from catalogue import convertir

        return convertir.commande(args.journal, verifier_apres=args.verifier)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
