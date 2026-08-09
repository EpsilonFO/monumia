"""
Rattachement one-shot des libellés de `documents_requis` au référentiel de
pièces canoniques (data/pieces.yaml).

À USAGE UNIQUE, jamais appelé à l'exécution. Le résultat est de la donnée
statique versionnée dans git : en production, aucun modèle n'est sollicité.

Trois étapes :
  1. `--collecter`  : liste les libellés distincts et écrit le rapport de
                      relecture dans data/reviews/pieces-mapping-<date>.md
  2. `--proposer`   : soumet les libellés au modèle, vocabulaire cible fermé,
                      et écrit le mapping proposé dans le rapport
  3. `--appliquer`  : insère les piece_id validés dans les YAML d'aides

Le mapping validé vit dans data/reviews/pieces-mapping-<date>.yaml, relu à la
main avant `--appliquer`. Un libellé sans correspondance sûre reste absent du
mapping : c'est un résultat valide, pas un échec.

La relecture humaine de 845 libellés ne tient pas dans une journée : `--appliquer`
accepte donc `--mapping <chemin>` pour désigner le fichier relu, quelle que soit
sa date. Sans cet argument, le fichier du jour est utilisé.

Run :
    cd backend && uv run python scripts/map_pieces.py --collecter
    cd backend && uv run python scripts/map_pieces.py --proposer
    # relecture humaine du .yaml produit, sur plusieurs jours
    cd backend && uv run python scripts/map_pieces.py --appliquer \
        --mapping data/reviews/pieces-mapping-2026-08-09.yaml
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

import yaml
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aides_schema import AIDES_DIR, DATA_DIR
from pieces_schema import load_pieces

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

REVIEWS_DIR = DATA_DIR / "reviews"
MODELE = "claude-opus-5"
LOT = 40  # libellés par appel — au-delà, le modèle survole


def normaliser(label: str) -> str:
    """Forme canonique d'un libellé : minuscules, sans accent, espaces réduits.

    Sert de clé de mapping. Deux libellés qui ne diffèrent que par la casse ou
    l'accentuation partagent donc leur rattachement.
    """
    sans_accent = "".join(
        c for c in unicodedata.normalize("NFD", label) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sans_accent).strip().strip(".;:").lower()


def collecter_libelles(aides_dir: Path = AIDES_DIR) -> dict[str, list[str]]:
    """Libellé normalisé → slugs des aides qui le demandent, du plus fréquent au moins."""
    index: dict[str, list[str]] = {}
    for chemin in sorted(aides_dir.glob("*.yaml")):
        brut = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
        for doc in brut.get("documents_requis") or []:
            nom = doc.get("nom") if isinstance(doc, dict) else doc
            if not isinstance(nom, str) or not nom.strip():
                continue
            index.setdefault(normaliser(nom), []).append(chemin.stem)
    return dict(sorted(index.items(), key=lambda kv: -len(kv[1])))


def inserer_piece_ids(texte: str, mapping: dict[str, str]) -> tuple[str, int, list[str]]:
    """Insère `piece_id:` sous chaque `- nom:` du bloc documents_requis.

    Gère aussi les block scalars (>-, |, etc.) où le libellé s'étend sur plusieurs lignes.

    Patch TEXTUEL et non re-dump YAML : un `yaml.dump` réordonnerait les clés et
    reformaterait les 142 fiches, produisant un diff illisible.

    Un item qui porte déjà un piece_id est laissé tel quel (idempotence).

    Returns: (texte_patché, nombre_insérés, libellés_mappés_non_traités)
    """
    lignes = texte.split("\n")
    sortie: list[str] = []
    dans_bloc = False
    inserees = 0
    non_traites: list[str] = []

    i = 0
    while i < len(lignes):
        ligne = lignes[i]
        sortie.append(ligne)

        if ligne.startswith("documents_requis:"):
            dans_bloc = True
            i += 1
            continue

        # Toute clé de premier niveau referme le bloc.
        if dans_bloc and ligne and not ligne.startswith((" ", "-", "#")):
            dans_bloc = False
            i += 1
            continue

        if not dans_bloc:
            i += 1
            continue

        correspondance = re.match(r"^  - nom:\s*(.*)$", ligne)
        if not correspondance:
            i += 1
            continue

        valeur_brute = correspondance.group(1)

        # Cas 1: block scalar (>-, >, |, |-)
        if valeur_brute in (">-", ">", "|-", "|"):
            # Lire les lignes de continuation (indentation supérieure à 4 espaces)
            continuation_lines = []
            fin_bloc = i + 1
            while fin_bloc < len(lignes):
                ligne_suite = lignes[fin_bloc]
                # Les lignes de continuation sont indentées de 6+ espaces (2 for item, 4 for content)
                if ligne_suite.startswith("      "):
                    continuation_lines.append(ligne_suite[6:].rstrip())
                    fin_bloc += 1
                else:
                    # Fin du block scalar (y compris lignes vides et propriétés)
                    break

            # Plier les lignes (YAML `>` behavior)
            libelle_reconstruit = " ".join(ligne for ligne in continuation_lines if ligne).strip()

            # Vérifier si le libellé est lisible
            if not libelle_reconstruit or libelle_reconstruit[0] in (">", "|"):
                non_traites.append(f"(ligne {i + 1}) {libelle_reconstruit or '(vide)'}")
                for k in range(i + 1, fin_bloc):
                    sortie.append(lignes[k])
                i = fin_bloc
                continue

            normalized = normaliser(libelle_reconstruit)
            piece_id = mapping.get(normalized)

            if piece_id is not None:
                # Vérifier si déjà rattaché — regarder les propriétés après le bloc
                deja = False
                for k in range(fin_bloc, len(lignes)):
                    if not lignes[k].startswith("    "):
                        break
                    if lignes[k].startswith("    piece_id:"):
                        deja = True
                        break

                # Ajouter les lignes de continuation à la sortie
                for k in range(i + 1, fin_bloc):
                    sortie.append(lignes[k])

                if not deja:
                    # Insérer le piece_id après la dernière ligne du bloc
                    sortie.append(f"    piece_id: {piece_id}")
                    inserees += 1

                i = fin_bloc
                continue
            else:
                # Pas en mapping, mais enregistrer pour détection futur
                # (ne pas enregistrer comme non_traite puisqu'il n'est pas mappé)
                for k in range(i + 1, fin_bloc):
                    sortie.append(lignes[k])
                i = fin_bloc
                continue

        # Cas 2: valeur simple
        else:
            # Vérifier si le libellé est lisible
            libelle_simple = valeur_brute.strip()
            if not libelle_simple or libelle_simple[0] in (">", "|"):
                non_traites.append(f"(ligne {i + 1}) {libelle_simple or '(vide)'}")
                i += 1
                continue

            normalized = normaliser(libelle_simple)
            piece_id = mapping.get(normalized)
            if piece_id is None:
                i += 1
                continue

            # Déjà rattaché ? On regarde les lignes de propriétés de cet item.
            deja = False
            for suivante in lignes[i + 1 :]:
                if not suivante.startswith("    "):
                    break
                if suivante.startswith("    piece_id:"):
                    deja = True
                    break
            if deja:
                i += 1
                continue

            sortie.append(f"    piece_id: {piece_id}")
            inserees += 1
            i += 1

    return "\n".join(sortie), inserees, non_traites


def _prompt(libelles: list[str], pieces: dict) -> str:
    catalogue = "\n".join(f"- {pid} : {p.nom} ({p.portee})" for pid, p in pieces.items())
    liste = "\n".join(f"{i + 1}. {lab}" for i, lab in enumerate(libelles))
    return (
        "Tu rattaches des libellés de pièces de dossier administratif français à un "
        "référentiel FERMÉ de pièces canoniques.\n\n"
        f"Référentiel :\n{catalogue}\n\n"
        f"Libellés à rattacher :\n{liste}\n\n"
        "Règles :\n"
        "- ne réponds QUE par des identifiants du référentiel ci-dessus ;\n"
        "- si aucune pièce ne correspond avec certitude, réponds null — c'est le bon "
        "réflexe, une pièce propre à une seule aide n'a rien à réutiliser ;\n"
        "- ne rattache pas deux pièces différentes au même id par approximation.\n\n"
        'Réponds en JSON strict : {"resultats": [{"libelle": "...", "piece_id": "..." '
        'ou null, "confiance": "haute"|"moyenne"|"faible"}]}'
    )


def proposer(libelles: list[str]) -> dict[str, str]:
    """Un appel par lot de LOT libellés. Ne garde que les rattachements de confiance haute."""
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    pieces = load_pieces()
    connus = set(pieces)
    mapping: dict[str, str] = {}

    for debut in range(0, len(libelles), LOT):
        lot = libelles[debut : debut + LOT]
        reponse = client.messages.create(
            model=MODELE,
            max_tokens=8000,
            messages=[{"role": "user", "content": _prompt(lot, pieces)}],
        )
        texte = "".join(b.text for b in reponse.content if b.type == "text")
        brut = json.loads(texte[texte.index("{") : texte.rindex("}") + 1])
        for res in brut.get("resultats", []):
            pid = res.get("piece_id")
            # Anti-hallucination : un id hors référentiel est rejeté, pas corrigé.
            if pid in connus and res.get("confiance") == "haute":
                mapping[normaliser(res["libelle"])] = pid
        print(f"  lot {debut // LOT + 1} : {len(mapping)} rattachements cumulés")

    return mapping


def _chemin_rapport(suffixe: str) -> Path:
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    return REVIEWS_DIR / f"pieces-mapping-{date.today().isoformat()}.{suffixe}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collecter", action="store_true")
    parser.add_argument("--proposer", action="store_true")
    parser.add_argument("--appliquer", action="store_true")
    parser.add_argument(
        "--mapping",
        type=Path,
        default=None,
        metavar="CHEMIN",
        help=(
            "Fichier de mapping relu à appliquer. Par défaut, celui du jour "
            "(data/reviews/pieces-mapping-<aujourd'hui>.yaml) — insuffisant dès "
            "que la relecture s'étale sur plusieurs jours."
        ),
    )
    args = parser.parse_args()

    index = collecter_libelles()

    if args.collecter:
        lignes = [f"# Libellés de pièces — {date.today().isoformat()}", ""]
        lignes.append(
            f"{len(index)} libellés distincts, {sum(len(v) for v in index.values())} demandes."
        )
        lignes.append("")
        for libelle, slugs in index.items():
            lignes.append(f"- ({len(slugs)}×) {libelle}")
        chemin = _chemin_rapport("md")
        chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
        print(f"✓ {chemin}")
        return 0

    if args.proposer:
        mapping = proposer(list(index))
        chemin = _chemin_rapport("yaml")
        chemin.write_text(
            "# Mapping proposé — À RELIRE avant --appliquer.\n"
            "# Retirer une ligne = ne pas rattacher ce libellé.\n\n"
            + yaml.safe_dump(mapping, allow_unicode=True, sort_keys=True),
            encoding="utf-8",
        )
        print(f"✓ {chemin} — {len(mapping)}/{len(index)} libellés rattachés")
        return 0

    if args.appliquer:
        chemin = args.mapping or _chemin_rapport("yaml")
        if not chemin.exists():
            indice = (
                "" if args.mapping else " (lancer --proposer d'abord, ou passer --mapping <chemin>)"
            )
            print(f"✗ mapping introuvable : {chemin}{indice}")
            return 1
        mapping = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
        inconnus = set(mapping.values()) - set(load_pieces())
        if inconnus:
            print(f"✗ pièces inconnues dans le mapping : {sorted(inconnus)}")
            return 1
        total = 0
        tous_non_traites: list[str] = []
        for fiche in sorted(AIDES_DIR.glob("*.yaml")):
            texte, n, non_traites = inserer_piece_ids(fiche.read_text(encoding="utf-8"), mapping)
            if n:
                fiche.write_text(texte, encoding="utf-8")
                total += n
            tous_non_traites.extend(non_traites)
        print(f"✓ {total} piece_id insérés — relancer scripts/lint_aides_data.py")
        if tous_non_traites:
            print(
                f"⚠ {len(tous_non_traites)} libellés non traités (parsing ou insertion échouée) :"
            )
            for libelle in tous_non_traites:
                print(f"  - {libelle}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
