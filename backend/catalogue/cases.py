"""Les cases de Félix : une question fermée posée dans le rapport, relue au run suivant.

Une case naît quand le code ne peut pas trancher seul (valeur déduite, retouche
d'une condition sans export de la surcouche admin, escalade de veille, échéance
périmée...). Elle s'écrit dans le rapport de la semaine
(`data/reviews/AAAA-MM-JJ-semaine.md`) sous la forme d'une liste de choix à
cocher dans l'éditeur :

    ### 3f9c1a2b7e44 · region-x-aide · escalade de veille
    <!-- case 3f9c1a2b7e44 veille-escalade a:region-x-aide 8be1c0d29a77f3e1 -->
    Ce qui a changé...
    - [ ] `rearchiver` : la page a changé sans effet sur la fiche
    - [ ] `reextraire` : à ré-extraire

Le run suivant relit les rapports, et chaque case cochée devient un événement
`felix` du journal, qui porte l'empreinte de l'état que Félix a vu. Une
réponse ne vaut que pour cet état : si la source change encore, la case revient
avec un nouvel état, et l'ancienne réponse ne s'applique plus.

Une case où plusieurs choix sont cochés n'est pas lue : elle est signalée.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from catalogue.journal import Evenement, Vue, cle

_MARQUEUR = re.compile(r"^<!-- case (\w+) (\S+) (\S+) (\S+) -->$")

#: Les cases dont la non-réponse est le bon défaut : la version en service
#: reste, ou ce n'est qu'un constat. Elles vont sous « Pour information » et ne
#: se répètent pas d'un rapport à l'autre. Toute autre sorte, y compris une
#: sorte neuve, est « À trancher » : sans réponse, un changement de la source
#: reste non appliqué et le catalogue vieillit.
SORTES_INFORMATIVES = frozenset(
    {
        # Ré-extraction : l'agent propose autre chose, la version en service est gardée.
        "reextraction-typage",
        "documents-requis",
        "familles",
        "hard-filters",
        "applies-if",
        # Veille : constats sans écriture possible.
        "veille-injoignable",
        "veille-echeance",
    }
)
_COCHEE = re.compile(r"^- \[[xX]\] `([\w-]+)`")
_TITRE = re.compile(r"^#{1,3} ")


@dataclass(frozen=True)
class Case:
    sorte: str
    objet: str
    titre: str
    # Empreinte de l'état que la case montre : une réponse ne vaut que pour lui.
    etat: str
    options: dict[str, str]
    contexte: tuple[str, ...] = ()
    donnees: dict[str, Any] = field(default_factory=dict, compare=False)

    @property
    def id(self) -> str:
        return cle("case", self.sorte, self.objet, self.etat)[:12]

    @property
    def a_trancher(self) -> bool:
        return self.sorte not in SORTES_INFORMATIVES

    def rendre(self) -> list[str]:
        lignes = [
            f"### {self.id} · {self.objet.removeprefix('a:')} · {self.titre}",
            f"<!-- case {self.id} {self.sorte} {self.objet} {self.etat} -->",
            "",
            *self.contexte,
        ]
        if self.contexte:
            lignes.append("")
        lignes += [f"- [ ] `{code}` : {libelle}" for code, libelle in self.options.items()]
        return lignes + [""]


@dataclass(frozen=True)
class Reponse:
    case: str
    sorte: str
    objet: str
    etat: str
    option: str

    def evenement(self, run: str | None = None) -> Evenement:
        return Evenement(
            "felix",
            self.objet,
            decision=self.sorte,
            run=run,
            auteur="felix",
            issue=self.option,
            cle=cle("felix", self.case, self.option),
            donnees={"case": self.case, "etat": self.etat},
        )


def lire(texte: str) -> tuple[list[Reponse], list[str]]:
    """Les cases cochées d'un rapport, et les cases illisibles (plusieurs choix cochés)."""
    reponses: list[Reponse] = []
    ambigues: list[str] = []
    courante: tuple[str, str, str, str] | None = None
    cochees: list[str] = []

    def clore() -> None:
        if courante is None:
            return
        if len(cochees) == 1:
            reponses.append(Reponse(*courante, cochees[0]))
        elif len(cochees) > 1:
            ambigues.append(courante[0])

    for ligne in texte.splitlines():
        if m := _MARQUEUR.match(ligne.strip()):
            clore()
            courante, cochees = (m.group(1), m.group(2), m.group(3), m.group(4)), []
        elif courante is not None and (m := _COCHEE.match(ligne.strip())):
            cochees.append(m.group(1))
        elif _TITRE.match(ligne) and courante is not None and not ligne.startswith("### "):
            clore()
            courante, cochees = None, []
    clore()
    return reponses, ambigues


def deja_posees(rapports: Iterable[Path]) -> set[str]:
    """Les identifiants des cases déjà écrites dans ces rapports."""
    ids: set[str] = set()
    for chemin in rapports:
        for ligne in chemin.read_text(encoding="utf-8").splitlines():
            if m := _MARQUEUR.match(ligne.strip()):
                ids.add(m.group(1))
    return ids


def relire(
    rapports: Iterable[Path], vue: Vue, run: str | None = None
) -> tuple[list[Evenement], list[str]]:
    """Les réponses de Félix encore absentes du journal, et les cases ambiguës."""
    deja = set(vue.cles)
    nouveaux: list[Evenement] = []
    ambigues: list[str] = []
    for chemin in sorted(rapports):
        reponses, mauvaises = lire(chemin.read_text(encoding="utf-8"))
        ambigues += mauvaises
        for r in reponses:
            e = r.evenement(run)
            if e.cle not in deja:
                deja.add(e.cle)
                nouveaux.append(e)
    return nouveaux, ambigues


def reponse(vue: Vue, sorte: str, objet: str, etat: str) -> str | None:
    """L'option que Félix a cochée pour cet état précis, s'il y en a une."""
    e = vue.felix.get((objet, sorte))
    if e is None or e.donnees.get("etat") != etat:
        return None
    return e.issue
