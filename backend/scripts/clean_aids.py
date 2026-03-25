"""
Nettoie all_aids.txt en ne gardant que les lignes au format :
  nombre.nombre — titre
Exemple : 13.3 — Dispositif Denormandie
"""

import re
from pathlib import Path

file_path = Path(__file__).parent / "all_aids.txt"

pattern = re.compile(r"^\d+\.\d+\s*—\s*.+")

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

kept = [line.strip() for line in lines if pattern.match(line.strip())]

with open(file_path, "w", encoding="utf-8") as f:
    f.write("\n".join(kept) + "\n")

print(f"{len(kept)} lignes conservées sur {len(lines)} lignes totales.")
