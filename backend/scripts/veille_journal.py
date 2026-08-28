"""Sorties partagées par les outils de veille : tee console/fichier et cellules.

Extrait de `veille_aides.py` quand `veille_audit.py` a eu besoin des mêmes
trois primitives. Elles n'ont aucune dépendance sur le reste du pipeline, ce
qui permet de les importer depuis n'importe quel étage sans créer de cycle.
"""

from __future__ import annotations

from pathlib import Path


class Journal:
    """Tee console + fichier, à la manière de `ingest_aides_batch.py`."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, message: str = "") -> None:
        print(message, flush=True)
        self.lines.append(message)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")


def tokens_compacts(n: int) -> str:
    """Volume de tokens en notation compacte : 950, 12.4k, 103k."""
    if n < 1000:
        return str(n)
    if n < 10_000:
        return f"{n / 1000:.1f}k"
    return f"{round(n / 1000)}k"


def milliers(n: int) -> str:
    """12345 → « 12 345 ». Espace fine insécable, comme le veut le français.

    Un `f"{n:,}".replace(",", " ")` appliqué à une PHRASE entière mangeait aussi
    ses virgules de ponctuation (« tokens en entrée, 12 en sortie » devenait
    « tokens en entrée 12 en sortie ») : le formatage appartient au nombre, pas
    à la phrase qui le porte.
    """
    return f"{n:,}".replace(",", "\u202f")


def cellule(texte: str, largeur: int = 140) -> str:
    """Texte du modèle rendu inoffensif dans une cellule de tableau markdown.

    Le `resume` est du texte libre : un `|` ou un saut de ligne y casserait le
    tableau, donc le rapport, donc la revue.
    """
    plat = " ".join(texte.split()).replace("|", "\\|")
    return (plat[: largeur - 1] + "…") if len(plat) > largeur else (plat or "—")


__all__ = ["Journal", "cellule", "milliers", "tokens_compacts"]
