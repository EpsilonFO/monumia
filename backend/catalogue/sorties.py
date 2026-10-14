"""Les sorties du catalogue : une aide que son guide ne liste plus.

L'entrée (`catalogue.entree`) rebalaye chaque guide une fois par mois et ne
regarde que ce qui est NOUVEAU. Ce module regarde l'autre sens : ce que le guide
listait et ne liste plus.

L'absence d'un listing est un indice faible, jamais une preuve. Une recette de
collecte qui casse (anti-bot, pagination changée, refonte du site) fait
disparaître d'un coup tout un territoire ; une aide fermée entre deux appels à
projets quitte le guide puis y revient ; une fiche déplacée sort sous une URL et
rentre sous une autre. D'où quatre verrous, dans l'ordre :

1. **Le listing doit être sain** (`sante`) : aucune note de panne de la
   collecte, pas de plafond atteint, et au moins `SEUIL_CHUTE` des entrées du
   dernier listing sain. Un listing douteux n'est ni archivé, ni compté : il ne
   vaut ni présence ni absence.
2. **L'aide doit avoir été listée** par ce guide à un listing sain antérieur, et
   être rattachée au territoire (`aides_existantes`). Une aide nationale, la
   DRAC, un dispositif fiscal ne sont listés par aucun guide : leur absence ne
   dit rien.
3. **Absente `ABSENCES_AVANT_RETRAIT` listings sains de suite**, comme un
   formulaire mort de la veille.
4. **Sa propre page est morte** (`page_morte`) : 404, 410, redirection sans
   issue, ou redirection vers le guide ou la racine du site.

Les quatre réunis, et aucune fiche du listing ne porte un titre voisin (un
déplacement d'URL) : l'aide est retirée sans case (réglage `sorties: auto`,
décision de Félix du 2026-10-15). Son YAML part dans `data/catalogue/retirees/`
avec la date et le motif en tête : le diff git est la revue, et le loader ne
supprime rien en base, si bien que les dossiers et suivis déjà ouverts sur
l'aide restent lisibles.

Page vivante, ou titre voisin dans le listing : une case. Page injoignable
(réseau, 403, 5xx) : une note, l'aide reste due au passage suivant. Une panne
n'est jamais un jugement.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from catalogue.journal import Evenement, Vue, empreinte
from catalogue.registre import BACKEND

LISTINGS = BACKEND / "data" / "catalogue" / "listings"
RETIREES = BACKEND / "data" / "catalogue" / "retirees"

# Un listing qui a perdu plus d'un cinquième de ses entrées depuis le dernier
# listing sain est une collecte cassée jusqu'à preuve du contraire.
SEUIL_CHUTE = 0.8
ABSENCES_AVANT_RETRAIT = 2
# Au-delà, deux titres désignent la même aide : la fiche a changé d'URL.
SIMILARITE_DEPLACEMENT = 0.6
# Les notes de `prospection.collecte` qui disent qu'une partie du guide n'a pas
# été vue. Liste fermée : une note neuve de panne doit être ajoutée ici.
MARQUEURS_PANNE = (
    "injoignable",
    "illisible",
    "page en erreur",
    "page vide ou SPA",
    "n'a pas répondu",
    "aucun guide",
    "plafond",
)
# Une page du guide qui n'existe pas n'est pas une panne : c'est ainsi que finit
# une pagination (aube.fr répond 404 après sa dernière page, mesuré le
# 2026-10-15). Si une vraie page du guide disparaissait, la chute du nombre de
# fiches le dirait.
_FIN_DE_PAGINATION = re.compile(r"^page en erreur : \S+ → HTTP (?:404|410)$")


@dataclass
class Entree:
    url: str
    titre: str = ""
    slug: str | None = None


@dataclass
class Listing:
    """Tout ce qu'un guide a listé à ce passage, catalogue compris."""

    territoire: str
    entrees: list[Entree]
    notes: list[str] = field(default_factory=list)
    plafonnee: bool = False

    @property
    def presentes(self) -> dict[str, str]:
        """slug -> URL listée, pour les aides du catalogue."""
        return {e.slug: e.url for e in self.entrees if e.slug}

    @property
    def nouvelles(self) -> list[Entree]:
        return [e for e in self.entrees if not e.slug]


@dataclass
class Sortie:
    slug: str
    url: str
    absences: int
    issue: str  # retiree, case, panne
    motif: str
    deplacement: str | None = None


@dataclass
class Bilan:
    territoire: str
    sain: bool
    motif: str = ""
    entrees: int = 0
    suivies: int = 0
    sorties: list[Sortie] = field(default_factory=list)
    cases: list[Any] = field(default_factory=list)
    revenues: list[tuple[str, str]] = field(default_factory=list)


# ------------------------------------------------------------------ santé


def sante(listing: Listing, precedent: int | None) -> str | None:
    """Le motif pour lequel ce listing n'est pas fiable, ou `None`."""
    if not listing.entrees:
        return "listing vide"
    if listing.plafonnee:
        return "plafond de candidates atteint"
    for note in listing.notes:
        if _FIN_DE_PAGINATION.match(note):
            continue
        if any(m in note for m in MARQUEURS_PANNE):
            return f"collecte incomplète : {note[:200]}"
    if precedent and len(listing.entrees) < SEUIL_CHUTE * precedent:
        return (
            f"{len(listing.entrees)} entrées contre {precedent} au dernier listing sain "
            f"(seuil {SEUIL_CHUTE:.0%})"
        )
    return None


def objet_territoire(territoire: str) -> str:
    return f"t:{territoire}"


def historique(evenements: list[Evenement], territoire: str) -> list[Evenement]:
    """Les listings sains du territoire, du plus ancien au plus récent."""
    objet = objet_territoire(territoire)
    return [
        e
        for e in evenements
        if e.type == "decision"
        and e.objet == objet
        and e.decision == "listing"
        and e.issue == "sain"
    ]


def absences(slug: str, listings: list[set[str]]) -> int | None:
    """Listings sains consécutifs, en partant du plus récent, où l'aide manque.

    `None` si l'aide n'a jamais été listée : on ne suit pas ce qu'on n'a jamais vu.
    """
    for n, presentes in enumerate(reversed(listings)):
        if slug in presentes:
            return n
    return None


# ------------------------------------------------------------------ la page


def page_morte(page: Any, url: str, guides: list[str]) -> tuple[bool | None, str]:
    """(morte, motif) d'après ce que `Fetcheur.get(url)` a rendu. `None` : on ne sait pas."""
    from prospection.collecte import cle_fiche

    if page.erreur is not None:
        return None, f"injoignable : {page.erreur[:120]}"
    if page.status in (404, 410):
        return True, f"HTTP {page.status}"
    if 300 <= page.status < 400:
        return True, f"redirection sans issue (HTTP {page.status})"
    if page.status >= 400:
        # 403, 429, 5xx : l'anti-bot ou le serveur, pas une décision éditoriale.
        return None, f"HTTP {page.status}"
    finale = cle_fiche(page.url_finale)
    if finale != cle_fiche(url):
        if urlsplit(page.url_finale).path.strip("/") == "":
            return True, f"redirigée vers la racine du site ({page.url_finale})"
        if finale in {cle_fiche(g) for g in guides}:
            return True, f"redirigée vers le guide ({page.url_finale})"
    return False, "page en ligne"


_MOTS_VIDES = frozenset(
    {"au", "aux", "de", "des", "du", "en", "et", "la", "le", "les", "pour", "sur"}
    | {"un", "une", "dans", "par", "avec"}
)


def _mots(titre: str) -> set[str]:
    nu = unicodedata.normalize("NFKD", titre.lower())
    nu = "".join(c for c in nu if not unicodedata.combining(c))
    return {m for m in re.findall(r"[a-z0-9]+", nu) if m not in _MOTS_VIDES and len(m) > 1}


def similarite(a: str, b: str) -> float:
    ma, mb = _mots(a), _mots(b)
    if not ma or not mb:
        return 0.0
    return len(ma & mb) / len(ma | mb)


def deplacement(noms: list[str], nouvelles: list[Entree]) -> str | None:
    """L'URL d'une fiche nouvellement listée dont le titre est celui de l'aide."""
    meilleure, score = None, SIMILARITE_DEPLACEMENT
    for e in nouvelles:
        s = max((similarite(n, e.titre) for n in noms if n), default=0.0)
        if s >= score:
            meilleure, score = e.url, s
    return meilleure


# ------------------------------------------------------------------ écritures


def archiver(listing: Listing, dossier: Path = LISTINGS) -> Path:
    """Le listing sain, trié, une ligne par fiche : son diff git montre les entrées et les sorties."""
    from prospection.collecte import cle_fiche

    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"{listing.territoire}.jsonl"
    lignes = []
    for e in sorted(listing.entrees, key=lambda e: cle_fiche(e.url)):
        d: dict[str, str] = {"url": e.url}
        if e.titre:
            d["titre"] = " ".join(e.titre.split())
        if e.slug:
            d["slug"] = e.slug
        lignes.append(json.dumps(d, ensure_ascii=False))
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return chemin


def retirer(
    slug: str, motif: str, jour: dt.date, aides_dir: Path, retirees: Path = RETIREES
) -> Path | None:
    """Sort le YAML du catalogue, motif et date en tête. `None` si l'aide n'y est plus."""
    source = aides_dir / f"{slug}.yaml"
    if not source.exists():
        return None
    retirees.mkdir(parents=True, exist_ok=True)
    cible = retirees / f"{slug}.yaml"
    entete = f"# Retirée du catalogue le {jour.isoformat()} : {' '.join(motif.split())[:300]}\n"
    cible.write_text(entete + source.read_text(encoding="utf-8"), encoding="utf-8")
    source.unlink()
    return cible


def revenues(listing: Listing, retirees: Path = RETIREES) -> list[tuple[str, str]]:
    """(slug, url) des aides retirées que le guide liste de nouveau : à remettre à la main."""
    from prospection.collecte import cle_fiche

    from aides_schema import load_aide

    if not retirees.is_dir():
        return []
    listees = {cle_fiche(e.url): e.url for e in listing.nouvelles}
    trouvees = []
    for chemin in sorted(retirees.glob("*.yaml")):
        try:
            aide = load_aide(chemin)
        except Exception:
            continue
        for url in (aide.source.url_officielle, aide.source.formulaire_url):
            if url and cle_fiche(url) in listees:
                trouvees.append((aide.slug, listees[cle_fiche(url)]))
                break
    return trouvees


# ------------------------------------------------------------------ le passage


def traiter(
    listing: Listing,
    *,
    territoire: Any,
    corpus: dict[str, Any],
    evenements: list[Evenement],
    vue: Vue,
    fetcheur: Any,
    consigner: Any,
    jour: dt.date,
    automatique: bool = True,
    aides_dir: Path | None = None,
    listings: Path = LISTINGS,
    retirees: Path = RETIREES,
) -> Bilan:
    """Santé du listing, consignation, archive, puis les sorties du territoire."""
    from prospection.territoires import aides_existantes

    from aides_schema import AIDES_DIR
    from catalogue import cases as cases_mod
    from catalogue.cases import Case

    aides_dir = aides_dir or AIDES_DIR
    nom = listing.territoire
    passe = historique(evenements, nom)
    precedent = passe[-1].donnees.get("entrees") if passe else None
    motif = sante(listing, precedent)
    b = Bilan(nom, motif is None, motif or "", len(listing.entrees))
    presentes = listing.presentes
    consigner(
        Evenement(
            "decision",
            objet_territoire(nom),
            decision="listing",
            decideur="code",
            issue="sain" if b.sain else "douteux",
            donnees={
                "entrees": len(listing.entrees),
                "presentes": sorted(presentes),
                **({"motif": motif} if motif else {}),
            },
        )
    )
    if not b.sain:
        return b
    archiver(listing, listings)
    b.revenues = revenues(listing, retirees)
    if not passe:
        # Premier listing sain : la référence. Rien ne peut encore être sorti.
        return b

    series = [set(e.donnees.get("presentes") or ()) for e in passe] + [set(presentes)]
    rattachees = aides_existantes(nom, territoire, corpus)
    for slug in sorted(rattachees):
        n = absences(slug, series)
        if n is None:
            continue
        b.suivies += 1
        if n < ABSENCES_AVANT_RETRAIT:
            continue
        aide = rattachees[slug]
        url = aide.source.url_officielle
        if not url:
            b.sorties.append(Sortie(slug, "", n, "panne", "aucune url_officielle à vérifier"))
            continue
        morte, pourquoi = page_morte(fetcheur.get(url), url, territoire.guides)
        if morte is None:
            b.sorties.append(Sortie(slug, url, n, "panne", pourquoi))
            continue
        ailleurs = deplacement([aide.nom, aide.nom_court or ""], listing.nouvelles)
        etat = empreinte(f"{slug}|{url}|{'morte' if morte else 'vivante'}|{ailleurs or ''}")
        reponse = cases_mod.reponse(vue, "sortie", f"a:{slug}", etat)
        if reponse == "garder":
            continue
        sur = morte and ailleurs is None
        if reponse == "retirer" or (sur and automatique):
            raison = f"absente du guide {nom} depuis {n} listings, page {pourquoi}" + (
                " ; retrait décidé par Félix" if reponse == "retirer" else ""
            )
            if retirer(slug, raison, jour, aides_dir, retirees) is not None:
                b.sorties.append(Sortie(slug, url, n, "retiree", raison, ailleurs))
                consigner(
                    Evenement(
                        "decision",
                        f"a:{slug}",
                        decision="sortie",
                        decideur="felix" if reponse == "retirer" else "code",
                        issue="retiree",
                        donnees={"territoire": nom, "url": url, "absences": n, "motif": raison},
                    )
                )
            continue
        constat = f"absente du guide depuis {n} listings, page {pourquoi}" + (
            f", une fiche au titre voisin est listée : <{ailleurs}>" if ailleurs else ""
        )
        b.sorties.append(Sortie(slug, url, n, "case", constat, ailleurs))
        b.cases.append(
            Case(
                "sortie",
                f"a:{slug}",
                "aide que son guide ne liste plus",
                etat,
                {
                    "retirer": "elle n'existe plus : la retirer du catalogue",
                    "garder": "elle reste (je corrige son URL à la main si elle a changé)",
                },
                (f"<{url}>", f"Territoire `{nom}` : {constat}."),
            )
        )
    return b


def section(b: Bilan) -> list[str]:
    if not b.sain:
        return [f"Sorties : listing douteux, rien n'est compté ce passage ({b.motif})."]
    lignes = [
        f"Sorties : listing sain de {b.entrees} fiches, {b.suivies} aide(s) du catalogue suivie(s) sur ce guide."
    ]
    retirees = [s for s in b.sorties if s.issue == "retiree"]
    if retirees:
        lignes += ["", "Retirées du catalogue (dans `data/catalogue/retirees/`) :", ""]
        lignes += [f"- `{s.slug}` : {s.motif} <{s.url}>" for s in retirees]
    pannes = [s for s in b.sorties if s.issue == "panne"]
    if pannes:
        lignes += [
            "",
            "Sorties non vérifiées (la page n'a pas répondu, à revoir au passage suivant) :",
            "",
        ]
        lignes += [f"- `{s.slug}` : {s.motif}" for s in pannes]
    if b.revenues:
        lignes += [
            "",
            "Aides retirées que le guide liste de nouveau (à remettre dans `data/aides/`) :",
            "",
        ]
        lignes += [f"- `{slug}` <{url}>" for slug, url in b.revenues]
    return lignes
