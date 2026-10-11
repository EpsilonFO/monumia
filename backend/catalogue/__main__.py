"""Les commandes du paquet : `uv run python -m catalogue <commande>`, depuis `backend/`.

- `convertir --journal <dossier> [--verifier]` : importe l'état de l'ancien
  pipeline (file, manifeste de veille, fiches, instantanés, YAML) dans un
  journal ; `--verifier` reprojette ensuite la file et le manifeste depuis ce
  journal et les compare octet pour octet aux fichiers en service.
- `veille --journal <dossier> [--a-blanc] [slug ...]` : un passage de veille
  (référence `base` du journal, mandat, garde, cases), le rapport de la
  semaine et la projection inverse vers `veille-state.yaml`.
- `semaine` : le run hebdomadaire planifiable (pré-vol, copie jetable,
  étapes que le registre donne à la nouvelle chaîne, recopie, rapport).
- `entree --territoire <nom> --journal <dossier>` : un territoire, de la
  collecte au jugement des pages (règle d'entrée de production portée).
- `ingestion --journal <dossier>` : les pages admises passent par l'agent
  sous contrat ; projection inverse vers `file-attente.yaml`.
- `banc V1-garde --preparer <dossier> | --lire <fichier>` : la session
  mensuelle d'étiquetage des cas de la zone prudente.
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
        help="dossier du journal à compléter (en service : data/catalogue/journal)",
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

    commandes.add_parser("semaine", help="le run hebdomadaire planifiable")

    k = commandes.add_parser("calibrer", help="recalibrer une décision fermée")
    k.add_argument("--decision", required=True)
    k.add_argument(
        "--modele", help="nom du modèle de décision à calibrer (défaut : celui du registre)"
    )

    en = commandes.add_parser("entree", help="un territoire : collecte, tri, jugement des pages")
    en.add_argument("--territoire", required=True)
    en.add_argument("--journal", type=Path, required=True)
    en.add_argument("--parties", type=Path)
    en.add_argument("--candidats", type=Path, help="liste figée de candidates (candidats.jsonl)")
    en.add_argument("--plafond", type=float, help="dépense maximale de l'étape, en dollars")
    en.add_argument("--file", type=Path, help="file d'attente contre laquelle dédoublonner")
    en.add_argument("--forcer", action="store_true", help="tourner hors registre (copies jetables)")

    ig = commandes.add_parser("ingestion", help="ingérer les pages admises par l'entrée")
    ig.add_argument("--journal", type=Path, required=True)
    ig.add_argument("--parties", type=Path)
    ig.add_argument("--a-blanc", action="store_true")
    ig.add_argument("--plafond", type=float, help="dépense maximale de l'étape, en dollars")
    ig.add_argument("--file", type=Path, help="file d'attente à projeter")
    ig.add_argument("--forcer", action="store_true", help="tourner hors registre (copies jetables)")

    b = commandes.add_parser("banc", help="session mensuelle d'étiquetage")
    b.add_argument("decision")
    b.add_argument("--journal", type=Path, default=None, help="défaut : data/catalogue/journal")
    b.add_argument("--preparer", type=Path, help="dossier neuf où exporter les cas à l'aveugle")
    b.add_argument("--lire", type=Path, help="fichier JSON des étiquettes rendues")

    args = parseur.parse_args(argv)
    if args.commande == "entree":
        from catalogue import entree

        return entree.commande(
            args.territoire,
            args.journal,
            args.parties,
            args.candidats,
            plafond=args.plafond,
            file=args.file,
            forcer=args.forcer,
        )
    if args.commande == "ingestion":
        from catalogue import ingestion

        return ingestion.commande(
            args.journal,
            args.parties,
            a_blanc=args.a_blanc,
            plafond=args.plafond,
            forcer=args.forcer,
            file=args.file,
        )
    if args.commande == "banc":
        from catalogue import banc
        from catalogue.journal import DOSSIER

        return banc.commande(args.decision, args.journal or DOSSIER, args.preparer, args.lire)
    if args.commande == "veille":
        from catalogue import veille

        return veille.commande(args.journal, args.slugs, a_blanc=args.a_blanc, parties=args.parties)
    if args.commande == "semaine":
        from catalogue import semaine

        return semaine.semaine()
    if args.commande == "calibrer":
        from catalogue import calibrer

        return calibrer.commande(args.decision, args.modele)
    if args.commande == "convertir":
        from catalogue import convertir

        return convertir.commande(args.journal, verifier_apres=args.verifier)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
