"""Le journal du catalogue : chaque décision, panne, bail ou réponse de Félix, en ajout seul.

Un fichier par mois, `backend/data/catalogue/journal/AAAA-MM.jsonl`, une ligne
JSON par événement, suivi par git : il remplace l'état réécrit en entier de
l'ancien pipeline (la file de 3,3 Mo, le manifeste de veille), dont
l'historique des décisions se perdait à chaque transition.

- Écriture : sous verrou exclusif (`flock`) sur le fichier du mois, ligne
  entière puis `fsync`. Deux processus qui écrivent en même temps ne mêlent
  jamais leurs lignes.
- Lecture : tous les mois dans l'ordre. Une dernière ligne tronquée (un run tué
  au milieu d'une écriture) est ignorée et comptée ; une ligne illisible au
  milieu d'un fichier est une corruption, et la lecture s'arrête.
- Mémorisation : `cle()` résume les entrées d'une décision (texte, questions,
  modèle, consigne...). Une décision déjà prise à entrées identiques se
  reprend au lieu de se rejuger : Jev n'est pas déterministe (écart jusqu'à
  0,08 sur un même état, mesuré le 2026-10-10), et rejuger ferait changer des
  issues sans que rien n'ait changé. Une panne ne se mémorise jamais.
"""

from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
DOSSIER = BACKEND / "data" / "catalogue" / "journal"

TYPES = ("decision", "panne", "bail", "felix", "import", "contradiction", "valide")
AUTEURS = ("pipeline", "felix", "import")
# Préfixes d'objet : un document (URL canonique), une aide (slug), un fait (clé),
# un run.
PREFIXES = ("d:", "a:", "f:", "r:")


class JournalCorrompu(Exception):
    """Une ligne illisible ailleurs qu'en fin de fichier."""


@dataclass(frozen=True)
class Evenement:
    type: str
    objet: str
    decision: str | None = None
    t: str = ""
    run: str | None = None
    auteur: str = "pipeline"
    cle: str | None = None
    decideur: str | None = None
    modele: str | None = None
    issue: str | None = None
    donnees: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.type not in TYPES:
            raise ValueError(f"type d'événement inconnu : {self.type}")
        if self.auteur not in AUTEURS:
            raise ValueError(f"auteur inconnu : {self.auteur}")
        if not self.objet.startswith(PREFIXES):
            raise ValueError(f"objet sans préfixe connu : {self.objet}")

    def en_dict(self) -> dict[str, Any]:
        brut = {
            "t": self.t,
            "type": self.type,
            "objet": self.objet,
            "decision": self.decision,
            "run": self.run,
            "auteur": self.auteur,
            "cle": self.cle,
            "decideur": self.decideur,
            "modele": self.modele,
            "issue": self.issue,
            "donnees": self.donnees,
        }
        return {k: v for k, v in brut.items() if v not in (None, {}, "")}

    @classmethod
    def depuis_dict(cls, brut: dict[str, Any]) -> Evenement:
        return cls(
            type=brut["type"],
            objet=brut["objet"],
            decision=brut.get("decision"),
            t=brut.get("t", ""),
            run=brut.get("run"),
            auteur=brut.get("auteur", "pipeline"),
            cle=brut.get("cle"),
            decideur=brut.get("decideur"),
            modele=brut.get("modele"),
            issue=brut.get("issue"),
            donnees=brut.get("donnees") or {},
        )


def cle(*morceaux: Any) -> str:
    """Empreinte stable des entrées d'une décision (16 caractères hexadécimaux)."""
    canonique = json.dumps(morceaux, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonique.encode()).hexdigest()[:16]


def empreinte(texte: str | bytes) -> str:
    """Empreinte courte d'un texte (questions, consigne, état) : 12 caractères hexadécimaux."""
    donnees = texte.encode() if isinstance(texte, str) else texte
    return hashlib.sha256(donnees).hexdigest()[:12]


class Journal:
    def __init__(self, dossier: Path = DOSSIER) -> None:
        self.dossier = dossier
        self.lignes_ignorees: list[str] = []

    def _fichier(self, t: str) -> Path:
        return self.dossier / f"{t[:7]}.jsonl"

    def ajouter(self, e: Evenement) -> Evenement:
        """Ajoute un événement ; l'horodatage se pose ici s'il manque."""
        return self.ajouter_lot([e])[0]

    def ajouter_lot(self, evenements: Iterable[Evenement]) -> list[Evenement]:
        """Ajoute des événements dans l'ordre donné : un verrou et un `fsync` par fichier de mois.

        La conversion de l'état ancien écrit des milliers d'événements d'un coup ;
        un `fsync` par ligne la rendrait lente pour rien. Un run tué pendant
        l'écriture laisse au pire une dernière ligne tronquée, que `lire` ignore.
        """
        maintenant = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
        ecrits: list[Evenement] = []
        par_fichier: dict[Path, list[str]] = {}
        for e in evenements:
            if not e.t:
                e = Evenement.depuis_dict({**e.en_dict(), "t": maintenant})
            ecrits.append(e)
            ligne = json.dumps(e.en_dict(), ensure_ascii=False, sort_keys=True) + "\n"
            par_fichier.setdefault(self._fichier(e.t), []).append(ligne)
        if par_fichier:
            self.dossier.mkdir(parents=True, exist_ok=True)
        for fichier, lignes in sorted(par_fichier.items()):
            with fichier.open("a", encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    f.write("".join(lignes))
                    f.flush()
                    os.fsync(f.fileno())
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        return ecrits

    def lire(self) -> Iterator[Evenement]:
        """Tous les événements, du plus ancien mois au plus récent, dans l'ordre d'écriture."""
        self.lignes_ignorees = []
        if not self.dossier.is_dir():
            return
        for fichier in sorted(self.dossier.glob("*.jsonl")):
            lignes = fichier.read_text(encoding="utf-8").split("\n")
            # Un fichier bien formé finit par un saut de ligne : le dernier
            # morceau est vide. Sinon, c'est une écriture interrompue.
            fin = lignes[-1]
            for numero, ligne in enumerate(lignes[:-1], start=1):
                if not ligne.strip():
                    continue
                try:
                    yield Evenement.depuis_dict(json.loads(ligne))
                except (json.JSONDecodeError, KeyError, ValueError) as exc:
                    raise JournalCorrompu(f"{fichier.name}:{numero} : {exc}") from exc
            if fin.strip():
                try:
                    yield Evenement.depuis_dict(json.loads(fin))
                except (json.JSONDecodeError, KeyError, ValueError):
                    self.lignes_ignorees.append(f"{fichier.name} : dernière ligne tronquée")


class Vue:
    """Ce qu'on demande au journal pendant un run : la mémoire des décisions."""

    def __init__(self, evenements: Iterator[Evenement] | list[Evenement]) -> None:
        self.par_cle: dict[str, Evenement] = {}
        self.derniere: dict[tuple[str, str], Evenement] = {}
        self.felix: dict[tuple[str, str], Evenement] = {}
        # Toutes les clés vues, réponses de Félix comprises : relire un ancien
        # rapport ne doit pas rejouer une réponse déjà consignée.
        self.cles: set[str] = set()
        for e in evenements:
            self.prendre(e)

    def prendre(self, e: Evenement) -> None:
        if e.cle:
            self.cles.add(e.cle)
        if e.type == "decision" and e.decision:
            if e.cle:
                self.par_cle[e.cle] = e
            self.derniere[(e.objet, e.decision)] = e
        elif e.type == "felix" and e.decision:
            self.felix[(e.objet, e.decision)] = e

    def memo(self, cle_decision: str) -> Evenement | None:
        """La décision déjà prise à entrées identiques, s'il y en a une."""
        return self.par_cle.get(cle_decision)

    def issue(self, objet: str, decision: str) -> str | None:
        """L'issue en vigueur : celle de Félix prime sur toute décision de modèle."""
        humain = self.felix.get((objet, decision))
        if humain is not None:
            return humain.issue
        e = self.derniere.get((objet, decision))
        return e.issue if e is not None else None
