"""Confronter une liste d'URL externe à ce que nous avons — `prospecter.py comparer`.

Tant que deux pipelines coexistent (le nôtre et celui d'un collègue, ou une
liste tenue à la main), la seule question qui compte est : qu'est-ce qu'il a et
que nous n'avons pas, et POURQUOI. La réponse ne se lit pas dans la file
d'attente : une URL absente peut avoir été écartée au tri, écartée à la
lecture, ou jamais collectée — trois causes très différentes, et seule la
dernière fiche de prospection les distingue.

Ce module ne décide rien et n'écrit rien : il imprime trois listes.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.etat import Tache
from veille_collect import cle_url

from aides_schema import Aide

from .territoires import Territoire, aides_existantes

_URL_RE = re.compile(r"https?://\S+")
# Les deux formes de ligne d'une section « Écartées » : celle d'une page lue
# (« - **Titre** — url — motif ») et celle d'un écart au tri (« - url — motif »).
_ECARTEE_RE = re.compile(r"^-\s+(?:\*\*.*?\*\*\s+—\s+)?(https?://\S+)\s+—\s+(.*)$", re.M)
# Les notes techniques : « - non lue : url — motif », « - déjà au catalogue : url → `slug` ».
_NOTE_RE = re.compile(r"^-\s+([^:]+?)\s*:\s+(https?://\S+)\s*[—→]\s*(.*)$", re.M)


@dataclass
class Comparaison:
    """Trois listes, et de quoi dire pourquoi une URL manque."""

    communes: list[tuple[str, str]] = field(default_factory=list)
    externes_seules: list[tuple[str, str]] = field(default_factory=list)
    notres_seules: list[tuple[str, str]] = field(default_factory=list)
    fiche: str | None = None


def lire_urls(chemin: Path) -> list[str]:
    """Une URL par ligne. Tolère les commentaires, les puces et les tableaux."""
    trouvees: list[str] = []
    vues: set[str] = set()
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        if ligne.lstrip().startswith("#"):
            continue
        m = _URL_RE.search(ligne)
        if not m:
            continue
        url = m.group(0).rstrip(").,;|")
        if cle_url(url) not in vues:
            vues.add(cle_url(url))
            trouvees.append(url)
    return trouvees


def derniere_fiche(cle: str, reviews_dir: Path) -> Path | None:
    """La fiche de prospection la plus récente du territoire, ou rien."""
    fiches = sorted(reviews_dir.glob(f"*-prospection-{cle}.md"))
    return fiches[-1] if fiches else None


def motifs_de_la_fiche(markdown: str) -> dict[str, str]:
    """`cle_url` → ce que la fiche dit de cette URL (écart, erreur, doublon)."""
    motifs: dict[str, str] = {}
    bloc = markdown.split("## Écartées (et pourquoi)", 1)
    if len(bloc) == 2:
        ecartees = bloc[1].split("\n## ", 1)[0]
        for m in _ECARTEE_RE.finditer(ecartees):
            motifs.setdefault(cle_url(m.group(1)), f"écartée — {m.group(2).strip()}")
    notes = markdown.split("## Notes techniques", 1)
    if len(notes) == 2:
        for m in _NOTE_RE.finditer(notes[1]):
            motifs.setdefault(
                cle_url(m.group(2)), f"{m.group(1).strip()} — {m.group(3).strip()}".rstrip(" —")
            )
    return motifs


def _nos_urls(
    cle: str, territoire: Territoire, corpus: dict[str, Aide], file: dict[str, Tache]
) -> dict[str, str]:
    """`cle_url` → d'où nous la connaissons (« catalogue `slug` », « file `slug` (statut) »)."""
    notres: dict[str, str] = {}
    for slug, aide in aides_existantes(cle, territoire, corpus).items():
        for url in (aide.source.url_officielle, aide.source.formulaire_url):
            if url:
                notres.setdefault(cle_url(url), f"catalogue `{slug}`")
    for slug, tache in file.items():
        if tache.territoire == cle and tache.url:
            notres.setdefault(cle_url(tache.url), f"file `{slug}` ({tache.statut})")
    return notres


def comparer(
    cle: str,
    territoire: Territoire,
    externes: list[str],
    corpus: dict[str, Aide],
    file: dict[str, Tache],
    *,
    fiche: Path | None = None,
) -> Comparaison:
    """Confronte une liste externe au corpus, à la file et à la dernière fiche."""
    notres = _nos_urls(cle, territoire, corpus, file)
    motifs = motifs_de_la_fiche(fiche.read_text(encoding="utf-8")) if fiche else {}
    resultat = Comparaison(fiche=str(fiche) if fiche else None)
    vues: set[str] = set()
    for url in externes:
        c = cle_url(url)
        vues.add(c)
        if c in notres:
            resultat.communes.append((url, notres[c]))
        else:
            resultat.externes_seules.append((url, motifs.get(c, "jamais vue — pas même collectée")))
    for c, provenance in notres.items():
        if c not in vues:
            resultat.notres_seules.append((c, provenance))
    resultat.notres_seules.sort()
    return resultat


def rendre(comparaison: Comparaison, cle: str) -> str:
    """Les trois listes, pour la sortie standard."""
    lignes = [
        f"=== {cle} — {len(comparaison.communes)} commune(s), "
        f"{len(comparaison.externes_seules)} externe(s) seule(s), "
        f"{len(comparaison.notres_seules)} nôtre(s) seule(s)",
        f"fiche consultée : {comparaison.fiche or '(aucune)'}",
        "",
        f"--- Chez eux et pas chez nous ({len(comparaison.externes_seules)}) "
        "— le motif vient de notre fiche",
    ]
    for url, motif in comparaison.externes_seules:
        lignes.append(f"  {url}\n      {motif}")
    lignes += ["", f"--- Chez nous et pas chez eux ({len(comparaison.notres_seules)})"]
    for url, provenance in comparaison.notres_seules:
        lignes.append(f"  {url}  [{provenance}]")
    lignes += ["", f"--- Communes ({len(comparaison.communes)})"]
    for url, provenance in comparaison.communes:
        lignes.append(f"  {url}  [{provenance}]")
    return "\n".join(lignes) + "\n"


__all__ = [
    "Comparaison",
    "comparer",
    "derniere_fiche",
    "lire_urls",
    "motifs_de_la_fiche",
    "rendre",
]
