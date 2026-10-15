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

from catalogue.cases import Case, deja_posees


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

    def rendre(self, deja: set[str] | frozenset[str] = frozenset()) -> str:
        """Le rapport. `deja` : les cases déjà posées dans un rapport précédent ;
        une case pour information qui y figure n'est pas répétée."""
        lignes = [f"# Semaine du {self.jour.isoformat()}", "", f"Run `{self.run}`.", ""]
        lignes += ["## En-tête", "", *self.entete, ""]
        a_trancher = [c for c in self.cases if c.a_trancher]
        infos = [c for c in self.cases if not c.a_trancher]
        nouvelles = [c for c in infos if c.id not in deja]
        lignes += [f"## À trancher ({len(a_trancher)})", ""]
        if a_trancher:
            lignes += [
                "Sans réponse, le changement vu dans la source n'est pas appliqué et l'ancienne "
                "valeur reste servie. Coche une option par case, enregistre : le run suivant lit "
                "tes réponses. Une case non cochée reste.",
                "",
            ]
            for c in a_trancher:
                lignes += c.rendre()
        else:
            lignes += ["Rien.", ""]
        lignes += [f"## Pour information ({len(infos)})", ""]
        if infos:
            lignes += [
                "Sans réponse, la version en service reste : c'est le bon défaut. Ne coche que "
                "si tu veux agir.",
                "",
            ]
        if nouvelles:
            sortes = Counter(c.titre for c in nouvelles)
            lignes += [
                "<details>",
                f"<summary>{len(nouvelles)} nouvelle(s) : {compte(sortes)}</summary>",
                "",
            ]
            for c in nouvelles:
                lignes += c.rendre()
            lignes += ["</details>", ""]
        if len(nouvelles) < len(infos):
            lignes += [
                f"{len(infos) - len(nouvelles)} autre(s), déjà posée(s) dans un rapport précédent "
                "et inchangée(s), ne sont pas répétée(s) : y répondre là-bas vaut toujours.",
                "",
            ]
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
        deja = deja_posees(p for p in dossier.glob("*-semaine*.md") if p != chemin)
        temporaire.write_text(self.rendre(deja), encoding="utf-8")
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
