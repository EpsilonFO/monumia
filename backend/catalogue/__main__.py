"""Les commandes du paquet : `uv run python -m catalogue <commande>`, depuis `backend/`.

- `convertir --journal <dossier> [--verifier]` : importe l'état de l'ancien
  pipeline (file, manifeste de veille, fiches, instantanés, YAML) dans un
  journal ; `--verifier` reprojette ensuite la file et le manifeste depuis ce
  journal et les compare octet pour octet aux fichiers en service.
- `veille --journal <dossier> [--a-blanc] [slug ...]` : un passage de veille
  (référence `base` du journal, mandat, garde, cases), le rapport de la
  semaine et la projection inverse vers `veille-state.yaml`. Avant la bascule,
  seulement dans une copie jetable du dépôt.
- `calibrer --decision <id> [--modele <nom>]` : rejoue une décision sur ses
  étalons et propose des seuils.
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

    v = commandes.add_parser("veille", help="un passage de veille")
    v.add_argument("--journal", type=Path, required=True)
    v.add_argument(
        "--a-blanc", action="store_true", help="n'écrire ni YAML, ni instantané, ni manifeste"
    )
    v.add_argument(
        "--parties", type=Path, help="rendre les parties du rapport en JSON (lancé par semaine)"
    )
    v.add_argument("slugs", nargs="*")

    k = commandes.add_parser("calibrer", help="recalibrer une décision fermée")
    k.add_argument("--decision", required=True)
    k.add_argument(
        "--modele", help="nom du modèle de décision à calibrer (défaut : celui du registre)"
    )

    args = parseur.parse_args(argv)
    if args.commande == "veille":
        from catalogue import veille

        return veille.commande(args.journal, args.slugs, a_blanc=args.a_blanc, parties=args.parties)
    if args.commande == "calibrer":
        from catalogue import calibrer

        return calibrer.commande(args.decision, args.modele)
    if args.commande == "convertir":
        from catalogue import convertir

        return convertir.commande(args.journal, verifier_apres=args.verifier)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
