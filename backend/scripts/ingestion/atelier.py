"""L'atelier d'un slug : où tout ce qui le concerne s'écrit.

Un seul objet porte les six chemins d'une ingestion (YAML, snapshots, review,
journal, ontologie, faits proposés), et TOUS les outils passent par lui. C'est
ce qui rend deux choses possibles d'un coup :

  - le banc d'essai : `--sortie /tmp/bench/glm` redirige l'atelier entier, donc
    cinq modèles peuvent ingérer la même aide sans se marcher dessus ni salir
    `data/` ;
  - la borne : `resoudre_snapshot` refuse tout chemin qui sort du dossier du
    slug, donc un modèle qui invente `../../.env` obtient une erreur, pas un
    fichier.

Le banc d'essai a une limite qu'il faut connaître : `snapshot_source` et
`veille_collect` lisent leur dossier de sources dans une GLOBALE de module.
Rediriger un atelier redirige donc le processus entier — un seul dossier de
sortie à la fois, ce qui est le cas d'usage (un run = un modèle).
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snapshot_source
import veille_collect

from aides_schema import AIDES_DIR, DATA_DIR, FACTS_FILE, FACTS_PENDING_FILE

BACKEND_DIR = DATA_DIR.parent
SOURCES_DIR = DATA_DIR / "sources"
REVIEWS_DIR = DATA_DIR / "reviews"
LOGS_DIR = REVIEWS_DIR / "logs"

EXTENSIONS_SNAPSHOT = (".md", ".pdf")


@dataclass(frozen=True)
class Atelier:
    """Les chemins d'une ingestion. Immuable : un worker n'en change pas en route."""

    slug: str
    aides_dir: Path
    sources_dir: Path
    reviews_dir: Path
    logs_dir: Path
    facts_path: Path
    pending_path: Path
    jour: date

    @property
    def yaml_path(self) -> Path:
        return self.aides_dir / f"{self.slug}.yaml"

    @property
    def yaml_echec_path(self) -> Path:
        """Où atterrit un YAML qui n'a pas passé les post-contrôles.

        Le suffixe `.yaml.echec` sort du glob `*.yaml` : le fichier reste
        lisible pour comprendre ce qui a raté, mais ni le lint, ni le moteur,
        ni le loader ne le verront.
        """
        return self.aides_dir / f"{self.slug}.yaml.echec"

    @property
    def review_path(self) -> Path:
        return self.reviews_dir / f"{self.jour.isoformat()}-ingest-{self.slug}.md"

    @property
    def log_path(self) -> Path:
        return self.logs_dir / f"ingest-{self.slug}.log"

    @property
    def dossier_sources(self) -> Path:
        return self.sources_dir / self.slug

    @property
    def dossiers_catalogue(self) -> tuple[Path, ...]:
        """Où chercher qui RÉFÉRENCE un fait : le catalogue entier, run compris.

        Au banc d'essai, `aides_dir` ne contient que les aides du run — deux ou
        trois fichiers. S'y arrêter ferait passer pour orphelins les 499 faits
        en attente proposés par tout le reste du catalogue, à chaque lint de
        l'agent comme dans l'audit de fin de run. Les deux dossiers sont donc
        rendus, et `AIDES_DIR` n'apparaît qu'une fois en run normal.
        """
        if self.aides_dir.resolve() == AIDES_DIR.resolve():
            return (self.aides_dir,)
        return (self.aides_dir, AIDES_DIR)

    def snapshots(self) -> list[Path]:
        """Snapshots archivés du slug, triés (donc du plus ancien au plus récent)."""
        if not self.dossier_sources.is_dir():
            return []
        return sorted(
            p
            for p in self.dossier_sources.iterdir()
            if p.suffix.lower() in EXTENSIONS_SNAPSHOT and p.is_file()
        )

    def resoudre_snapshot(self, chemin: str) -> Path:
        """Chemin d'un snapshot du slug, quelle que soit la forme donnée.

        Accepte un nom nu (`2026-09-06.md`), un chemin relatif à `backend/`
        (`data/sources/<slug>/2026-09-06.md`) ou un absolu. Tout ce qui, une
        fois résolu, sort du dossier du slug est refusé — c'est la seule
        barrière entre un modèle qui se trompe de chemin et le reste du dépôt.
        """
        brut = Path(chemin.strip())
        candidat = brut if brut.is_absolute() else self.dossier_sources / brut.name
        if not brut.is_absolute() and len(brut.parts) > 1:
            # Chemin relatif à backend/ : on le prend tel quel, la borne
            # ci-dessous tranchera.
            candidat = (BACKEND_DIR / brut).resolve()
        candidat = candidat.resolve()
        dossier = self.dossier_sources.resolve()
        if candidat != dossier and dossier not in candidat.parents:
            raise ValueError(
                f"chemin hors du dossier de l'aide : {chemin!r} — "
                f"les snapshots de {self.slug} vivent dans {self.dossier_sources}"
            )
        if not candidat.is_file():
            raise FileNotFoundError(f"snapshot introuvable : {chemin!r}")
        return candidat

    def relatif(self, chemin: Path) -> str:
        """Chemin tel qu'il s'écrit dans un YAML : relatif à `backend/` si possible."""
        try:
            return str(chemin.resolve().relative_to(BACKEND_DIR))
        except ValueError:
            return str(chemin)

    def preparer(self) -> None:
        for dossier in (self.aides_dir, self.dossier_sources, self.reviews_dir, self.logs_dir):
            dossier.mkdir(parents=True, exist_ok=True)


def atelier_standard(slug: str, *, jour: date | None = None) -> Atelier:
    """L'atelier qui écrit dans le vrai `backend/data/`."""
    return Atelier(
        slug=slug,
        aides_dir=AIDES_DIR,
        sources_dir=SOURCES_DIR,
        reviews_dir=REVIEWS_DIR,
        logs_dir=LOGS_DIR,
        facts_path=FACTS_FILE,
        pending_path=FACTS_PENDING_FILE,
        jour=jour or date.today(),
    )


def atelier_redirige(slug: str, sortie: Path, *, jour: date | None = None) -> Atelier:
    """Atelier isolé sous `sortie/` — le banc d'essai, et rien d'autre.

    `facts_pending.yaml` est COPIÉ depuis le vrai fichier plutôt que créé vide :
    un modèle qui repropose un fait déjà en attente doit se le voir refuser ici
    comme il se le verrait refuser en vrai, sinon le banc d'essai mesure une
    situation qui n'existe pas.
    """
    sortie = Path(sortie).resolve()
    pending = sortie / "facts_pending.yaml"
    sortie.mkdir(parents=True, exist_ok=True)
    if not pending.exists():
        if FACTS_PENDING_FILE.exists():
            shutil.copyfile(FACTS_PENDING_FILE, pending)
        else:
            pending.write_text("", encoding="utf-8")
    atelier = Atelier(
        slug=slug,
        aides_dir=sortie / "aides",
        sources_dir=sortie / "sources",
        reviews_dir=sortie / "reviews",
        logs_dir=sortie / "reviews" / "logs",
        facts_path=FACTS_FILE,
        pending_path=pending,
        jour=jour or date.today(),
    )
    rediriger_sources(atelier.sources_dir)
    atelier.preparer()
    return atelier


def rediriger_sources(dossier: Path) -> None:
    """Fait pointer `snapshot_source` et `veille_collect` sur `dossier`.

    Les deux modules lisent leur dossier de sources dans une globale, à chaque
    appel — il n'y a donc rien d'autre à faire que de la remplacer. Global au
    PROCESSUS : appelé une fois au démarrage d'un run redirigé.

    Corollaire pour les tests : ce que l'on redirige, il faut le RESTAURER
    (`restaurer_sources`, en `addCleanup`). Un test qui laisse la globale sur
    son tmpdir fait échouer, plus tard et ailleurs, tout code qui lit les vrais
    snapshots — l'oubli s'est déjà payé d'un test de veille rouge sans rapport
    apparent avec l'ingestion.
    """
    dossier = Path(dossier).resolve()
    dossier.mkdir(parents=True, exist_ok=True)
    snapshot_source.SOURCES_DIR = dossier
    veille_collect.SOURCES_DIR = dossier


def restaurer_sources() -> None:
    """Rend à `snapshot_source` et `veille_collect` le vrai `data/sources/`."""
    snapshot_source.SOURCES_DIR = SOURCES_DIR
    veille_collect.SOURCES_DIR = SOURCES_DIR


__all__ = [
    "BACKEND_DIR",
    "LOGS_DIR",
    "REVIEWS_DIR",
    "SOURCES_DIR",
    "Atelier",
    "atelier_redirige",
    "atelier_standard",
    "rediriger_sources",
    "restaurer_sources",
]
