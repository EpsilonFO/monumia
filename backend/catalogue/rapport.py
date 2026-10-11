"""Le rapport de la semaine : le seul fichier que Félix lit (section 8 d'`architecture.md`).

`data/reviews/AAAA-MM-JJ-semaine.md` : un en-tête qui se lit en une minute,
puis les cases à trancher, puis ce qui a été écrit, puis le stock. Il s'écrit
même après un arrêt précoce : chaque partie du run y dépose sa section, et ce
module ne fait que les assembler.
"""

from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from catalogue.cases import Case


@dataclass
class Section:
    titre: str
    lignes: list[str]


@dataclass
class Rapport:
    jour: dt.date
    run: str
    entete: list[str] = field(default_factory=list)
    cases: list[Case] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)

    def rendre(self) -> str:
        lignes = [f"# Semaine du {self.jour.isoformat()}", "", f"Run `{self.run}`.", ""]
        lignes += ["## En-tête", "", *self.entete, ""]
        lignes += ["## À trancher", ""]
        if self.cases:
            lignes += [
                "Coche une option par case, enregistre : le run suivant lit tes réponses. "
                "Une case non cochée reste.",
                "",
            ]
            for c in self.cases:
                lignes += c.rendre()
        else:
            lignes += ["Rien.", ""]
        for s in self.sections:
            lignes += [f"## {s.titre}", "", *s.lignes, ""]
        return "\n".join(lignes).rstrip() + "\n"

    def ecrire(self, dossier: Path) -> Path:
        dossier.mkdir(parents=True, exist_ok=True)
        chemin = dossier / f"{self.jour.isoformat()}-semaine.md"
        # Deux runs le même jour : le second ne perd pas les cases du premier.
        n = 2
        while chemin.exists():
            chemin = dossier / f"{self.jour.isoformat()}-semaine-{n}.md"
            n += 1
        temporaire = chemin.with_suffix(".md.tmp")
        temporaire.write_text(self.rendre(), encoding="utf-8")
        temporaire.replace(chemin)
        return chemin


def compte(c: Counter[str]) -> str:
    return ", ".join(f"{k} {v}" for k, v in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])))


def parties_json(
    entete: list[str], cases: list[Case], sections: list[Section], *, depense: float = 0.0
) -> str:
    """Les parties d'un rapport, pour qu'une étape lancée en sous-processus les rende au run."""
    return json.dumps(
        {
            "entete": entete,
            "cases": [
                {
                    "sorte": c.sorte,
                    "objet": c.objet,
                    "titre": c.titre,
                    "etat": c.etat,
                    "options": c.options,
                    "contexte": list(c.contexte),
                }
                for c in cases
            ],
            "sections": [{"titre": s.titre, "lignes": s.lignes} for s in sections],
            "depense": depense,
        },
        ensure_ascii=False,
    )


def ajouter_parties(rapport: Rapport, texte: str) -> float:
    """Ajoute les parties d'une étape au rapport ; rend la dépense que l'étape déclare."""
    d = json.loads(texte)
    rapport.entete += d["entete"]
    rapport.cases += [
        Case(c["sorte"], c["objet"], c["titre"], c["etat"], c["options"], tuple(c["contexte"]))
        for c in d["cases"]
    ]
    rapport.sections += [Section(x["titre"], x["lignes"]) for x in d["sections"]]
    return float(d.get("depense") or 0.0)
