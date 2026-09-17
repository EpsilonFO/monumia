"""Étage 1 : d'un guide des aides à une liste d'URL candidates. Zéro LLM.

Le seul étage qui ne coûte aucun modèle — sauf sur un site inconnu, où un
unique appel sert à choisir la rubrique par laquelle entrer. Tout le reste est
du parcours de liens, et c'est délibéré : trier trois cents URL avec un modèle
quand un motif d'URL suffit, c'est payer pour un `grep`.

Les liens sont extraits du MARKDOWN de la page, pas de son HTML. Deux raisons :
`html2text` est déjà la brique qui produit les snapshots (donc un seul dialecte
de conversion dans tout le dépôt), et il rend le libellé du lien avec son
contexte de ligne — soit exactement le titre et l'extrait dont l'étage 2 a
besoin pour trier sans rouvrir la page.

La stratégie `sitemap` fait exception : un sitemap ne rend QUE des URL. Elle
ouvre donc chaque fiche pour son titre et son chapeau (`titre_et_chapeau`).
C'est du temps (une seconde par hôte) mais pas un centime, et le cache du
`Fetcheur` rend ces pages gratuites à l'étage 3, qui les rouvrira presque
toutes.
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import providall
from pipeline.etat import Tache
from pipeline.llm import Compteur
from pipeline.web import Fetcheur, Page
from veille_collect import cle_url

from aides_schema import Aide

from .territoires import Territoire

# Un extrait plus long qu'une phrase ou deux ne fait qu'alourdir le lot de tri,
# et c'est le titre qui porte l'essentiel de la décision.
MAX_CAR_EXTRAIT = 300
# Au-delà, on n'envoie pas la navigation d'un site à un modèle pour qu'il y
# trouve « la rubrique aides » : on lui en donne un échantillon représentatif.
MAX_LIENS_DECOUVERTE = 150
# Pages consécutives sans aucune nouveauté avant d'arrêter une pagination : la
# borne haute d'un patron est toujours une estimation, et beaucoup de guides
# rendent la dernière page à l'infini plutôt qu'un 404.
PAGES_STERILES = 2
# Ouvrir 244 fiches à une seconde par hôte prend quatre minutes : sans un mot
# toutes les 25 pages, le balayage paraît bloqué.
PAS_PROGRESSION = 25

# Un libellé de lien peut courir sur PLUSIEURS lignes. Sur un guide « en
# cartes » (Drupal Views, la plupart des sites régionaux récents), le <a>
# enveloppe l'étiquette thématique, le titre, le résumé, la liste des
# bénéficiaires et le « En savoir plus » : html2text en rend un libellé de dix
# lignes. Le balayage ligne à ligne les perdait en SILENCE — 0 candidat sur
# paysdelaloire.fr le 2026-09-11 alors que la page en portait douze, et 14
# liens perdus sur 187. `]` reste exclu du libellé, donc un lien ne peut
# toujours pas déborder sur le suivant ; la borne évite qu'un `]` manquant
# fasse avaler la moitié de la page.
MAX_CAR_LIBELLE = 2000
_LIEN_MD_RE = re.compile(rf"\[([^\]]{{0,{MAX_CAR_LIBELLE}}}?)\]\(\s*(<[^>]*>|[^)\s]+)[^)]*\)")
_PUCES = ("*", "-", "+")


@dataclass(frozen=True)
class Candidat:
    url: str
    titre: str = ""
    extrait: str = ""
    trouve_via: str = ""

    def json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


@dataclass
class Collecte:
    """Ce qu'un balayage a produit, et ce qui s'est mal passé en chemin."""

    candidats: list[Candidat] = field(default_factory=list)
    doublons: list[tuple[str, str]] = field(default_factory=list)
    # (url, slug, statut) des URL déjà connues de la file d'attente. Dans les
    # notes de la fiche, jamais dans candidats.jsonl : ce ne sont pas des
    # candidates, c'est ce qu'on a délibérément arrêté de proposer.
    en_file: list[tuple[str, str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    pages_visitees: int = 0

    def ecrire(self, chemin: Path) -> None:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text("".join(c.json() + "\n" for c in self.candidats), encoding="utf-8")

    @staticmethod
    def lire(chemin: Path) -> list[Candidat]:
        return [
            Candidat(**json.loads(ligne))
            for ligne in chemin.read_text(encoding="utf-8").splitlines()
            if ligne.strip()
        ]


class RubriqueAides(BaseModel):
    """Par où entrer dans un site dont on ne connaît pas la structure."""

    prefixes: list[str] = Field(
        description="Préfixes d'URL sous lesquels vivent les fiches d'aide, du plus "
        "prometteur au moins prometteur (3 au maximum)"
    )
    justification: str = ""


# ---------------------------------------------------------------------------
# Extraction de liens
# ---------------------------------------------------------------------------


def titre_du_libelle(libelle: str) -> str:
    """Le titre porté par un libellé de lien, même s'il court sur dix lignes.

    Sur une carte, les puces sont les étiquettes thématiques et la liste des
    bénéficiaires ; le titre du dispositif est la plus longue ligne qui n'en est
    pas une. Un libellé d'une seule ligne est rendu tel quel : c'est le cas
    courant, et il ne doit rien changer à ce que voyait l'étage 2.
    """
    lignes = [" ".join(li.split()) for li in libelle.splitlines()]
    lignes = [li for li in lignes if li]
    if len(lignes) <= 1:
        return lignes[0] if lignes else ""
    sans_puce = [li for li in lignes if not li.startswith(_PUCES)]
    return max(sans_puce or lignes, key=len)


def liens(page: Page) -> list[tuple[str, str, str]]:
    """(titre, URL absolue, bloc de contexte) de chaque lien d'une page.

    Les URL relatives sont résolues contre l'URL FINALE (redirections suivies) :
    résoudre contre l'URL demandée produirait des liens cassés dès qu'un guide
    redirige `/aides` vers `/aides-regionales/`.

    Le contexte est le bloc de lignes que le lien enjambe. Pour un lien sur une
    seule ligne — le cas courant — c'est exactement la ligne, comme avant.
    """
    md = page.markdown()
    sortie: list[tuple[str, str, str]] = []
    for m in _LIEN_MD_RE.finditer(md):
        cible = m.group(2).strip().strip("<>")
        if not cible or cible.startswith(("#", "mailto:", "javascript:", "tel:")):
            continue
        debut = md.rfind("\n", 0, m.start()) + 1
        fin = md.find("\n", m.end())
        bloc = md[debut:] if fin == -1 else md[debut:fin]
        sortie.append(
            (
                titre_du_libelle(m.group(1)),
                urljoin(page.url_finale, cible),
                " ".join(bloc.split()),
            )
        )
    return sortie


_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def titre_et_chapeau(page: Page) -> tuple[str, str]:
    """Le premier titre de niveau 1 du markdown (repli : la balise <title>) et le
    premier paragraphe qui le suit, plafonné à MAX_CAR_EXTRAIT. Vide si la page
    n'est pas lisible : c'est le garde-fou du tri qui prend le relais."""
    if not page.ok or not page.est_html:
        return "", ""
    md = page.markdown()
    m = _H1_RE.search(md)
    titre = " ".join(m.group(1).split()) if m else ""
    if not titre:
        t = _TITLE_RE.search(page.texte)
        titre = " ".join(t.group(1).split()) if t else ""
    chapeau = ""
    reste = md[m.end() :] if m else md
    for para in reste.split("\n\n"):
        texte = " ".join(para.split())
        if len(texte) >= 40 and not texte.startswith(("#", "*", "-", "[", "!", "|")):
            chapeau = texte[:MAX_CAR_EXTRAIT]
            break
    return titre, chapeau


def _candidats_de_page(page: Page, territoire: Territoire, via: str) -> list[Candidat]:
    vus: set[str] = set()
    retenus: list[Candidat] = []
    for titre, url, contexte in liens(page):
        url = url.split("#")[0]
        if url in vus or not territoire.fiche_probable(url):
            continue
        vus.add(url)
        retenus.append(
            Candidat(
                url=url,
                titre=titre,
                extrait=contexte[:MAX_CAR_EXTRAIT],
                trouve_via=via,
            )
        )
    return retenus


# ---------------------------------------------------------------------------
# Les quatre stratégies
# ---------------------------------------------------------------------------


def _liste_html(territoire: Territoire, fetcheur: Fetcheur, collecte: Collecte) -> list[Candidat]:
    trouves: list[Candidat] = []
    for guide in territoire.guides:
        page = fetcheur.get(guide)
        collecte.pages_visitees += 1
        if not _page_utilisable(page, guide, collecte):
            continue
        trouves += _candidats_de_page(page, territoire, "liste_html")
    return trouves


def _urls_dun_sitemap(url: str, fetcheur: Fetcheur, collecte: Collecte) -> list[str]:
    """Les `<loc>` d'un sitemap. Un sitemap muet est une note, pas une exception."""
    page = fetcheur.get(url)
    collecte.pages_visitees += 1
    if not page.ok:
        collecte.notes.append(f"sitemap injoignable : {url} → {page.erreur or page.status}")
        return []
    try:
        racine = ET.fromstring(page.contenu)
    except ET.ParseError as exc:
        collecte.notes.append(f"sitemap illisible : {url} → {exc}")
        return []
    # Le namespace sitemaps.org est systématique mais son URI varie : on filtre
    # sur le nom local plutôt que de coder un namespace en dur.
    urls = [
        (n.text or "").strip()
        for n in racine.iter()
        if n.tag.rsplit("}", 1)[-1] == "loc" and n.text
    ]
    collecte.notes.append(f"sitemap {url} : {len(urls)} URL énumérées")
    return urls


def _sitemap(territoire: Territoire, fetcheur: Fetcheur, collecte: Collecte) -> list[Candidat]:
    urls: list[str] = []
    for sitemap in territoire.strategie.urls_sitemap:
        urls += _urls_dun_sitemap(sitemap, fetcheur, collecte)
    # Dédoublonnage AVANT d'ouvrir : deux sitemaps d'un même site se recouvrent
    # volontiers, et chaque fiche ouverte coûte une seconde de délai d'hôte.
    fiches = [u for u in dict.fromkeys(urls) if territoire.fiche_probable(u)]

    # Un sitemap ne rend qu'une liste d'URL : sans titre ni chapeau, l'étage 2
    # trierait sur le seul slug — ce qui a coûté 173 pages jamais ouvertes le
    # 2026-09-08. On les ouvre ICI, et le cache du Fetcheur les rend gratuites
    # à la lecture.
    candidats: list[Candidat] = []
    injoignables = 0
    for i, u in enumerate(fiches, 1):
        page = fetcheur.get(u)
        collecte.pages_visitees += 1
        titre, chapeau = titre_et_chapeau(page)
        if not titre:
            injoignables += 1
        candidats.append(Candidat(url=u, titre=titre, extrait=chapeau, trouve_via="sitemap"))
        if i % PAS_PROGRESSION == 0 or i == len(fiches):
            print(f"    [1/3] {i}/{len(fiches)} fiche(s) ouverte(s) pour leur titre", flush=True)
    collecte.notes.append(
        f"sitemap : {len(fiches)} fiche(s) ouverte(s) pour leur titre, "
        f"{injoignables} sans titre lisible"
    )
    return candidats


def _pagination(territoire: Territoire, fetcheur: Fetcheur, collecte: Collecte) -> list[Candidat]:
    trouves: dict[str, Candidat] = {}
    steriles = 0
    for url in territoire.pages_paginees():
        page = fetcheur.get(url)
        collecte.pages_visitees += 1
        if not _page_utilisable(page, url, collecte):
            steriles += 1
            if steriles >= PAGES_STERILES:
                break
            continue
        avant = len(trouves)
        for candidat in _candidats_de_page(page, territoire, "pagination"):
            trouves.setdefault(candidat.url, candidat)
        if len(trouves) == avant:
            steriles += 1
            if steriles >= PAGES_STERILES:
                collecte.notes.append(
                    f"pagination arrêtée à {url} : {PAGES_STERILES} pages sans nouveauté"
                )
                break
        else:
            steriles = 0
    return list(trouves.values())


def _decouverte(
    territoire: Territoire,
    fetcheur: Fetcheur,
    collecte: Collecte,
    *,
    client: providall.Client | None = None,
    compteur: Compteur | None = None,
) -> list[Candidat]:
    """Site inconnu : on demande par où entrer, puis on explore de façon bornée."""
    depart = territoire.guides[0]
    accueil = fetcheur.get(depart)
    collecte.pages_visitees += 1
    if not _page_utilisable(accueil, depart, collecte):
        return []

    prefixes = _prefixes_probables(territoire, accueil, collecte, client=client, compteur=compteur)
    hote = urlsplit(accueil.url_finale).netloc
    strategie = territoire.strategie
    vus: set[str] = {accueil.url_finale}
    trouves: dict[str, Candidat] = {}
    file: deque[tuple[str, int]] = deque([(accueil.url_finale, 0)])

    while file and collecte.pages_visitees < strategie.max_pages:
        url, profondeur = file.popleft()
        page = accueil if url == accueil.url_finale else fetcheur.get(url)
        if url != accueil.url_finale:
            collecte.pages_visitees += 1
            if not page.ok or page.est_pdf:
                continue
        for _titre, lien, contexte in liens(page):
            lien = lien.split("#")[0]
            if urlsplit(lien).netloc != hote or lien in vus:
                continue
            if any(re.search(m, lien) for m in territoire.exclure):
                continue
            vus.add(lien)
            if territoire.fiche_probable(lien) and _sous_prefixe(lien, prefixes):
                trouves.setdefault(
                    lien,
                    Candidat(
                        url=lien,
                        titre=_titre,
                        extrait=contexte[:MAX_CAR_EXTRAIT],
                        trouve_via="decouverte",
                    ),
                )
            if profondeur < strategie.profondeur and _sous_prefixe(lien, prefixes):
                file.append((lien, profondeur + 1))
    if collecte.pages_visitees >= strategie.max_pages:
        collecte.notes.append(
            f"découverte arrêtée au plafond de {strategie.max_pages} pages — "
            "recette à préciser dans territoires.yaml"
        )
    return list(trouves.values())


def _sous_prefixe(url: str, prefixes: list[str]) -> bool:
    return not prefixes or any(url.startswith(p) for p in prefixes)


def _prefixes_probables(
    territoire: Territoire,
    accueil: Page,
    collecte: Collecte,
    *,
    client: providall.Client | None,
    compteur: Compteur | None,
) -> list[str]:
    """Les préfixes d'URL sous lesquels chercher — un appel LLM, ou rien.

    Sans modèle, on n'invente pas de préfixe : l'exploration part alors du seul
    plafond de pages, ce qui reste borné mais rend beaucoup plus de bruit.
    """
    echantillon = [u for _t, u, _c in liens(accueil)][:MAX_LIENS_DECOUVERTE]
    if client is None or not echantillon:
        return []
    prompt = "\n".join(
        [
            f"Site du guide des aides de {territoire.nom} ({territoire.type}), "
            f"accueil : {accueil.url_finale}.",
            "",
            "Voici les liens de navigation trouvés sur cette page. Indique les préfixes",
            "d'URL sous lesquels vivent les FICHES DE DISPOSITIF D'AIDE (subventions,",
            "appels à projets, accompagnements) — pas les actualités, ni les pages",
            "institutionnelles, ni les offres d'emploi. Trois préfixes au maximum, et",
            "seulement des préfixes réellement présents dans la liste.",
            "",
            *echantillon,
        ]
    )
    essai = client.try_complete_json(RubriqueAides, prompt)
    if compteur is not None:
        compteur.ajouter(essai.response, "decouverte")
    if essai.data is None:
        collecte.notes.append(f"découverte : le modèle n'a pas répondu ({essai.response.error})")
        return []
    # Un préfixe inventé enverrait l'exploration dans le vide : on ne garde que
    # ceux qui préfixent réellement un lien vu sur la page.
    retenus = [p for p in essai.data.prefixes if any(u.startswith(p) for u in echantillon)]
    ecartes = [p for p in essai.data.prefixes if p not in retenus]
    if ecartes:
        collecte.notes.append(f"découverte : préfixes inventés ignorés — {', '.join(ecartes)}")
    collecte.notes.append(
        f"découverte : préfixes retenus {retenus or '(aucun)'} — {essai.data.justification}"
    )
    return retenus


def _page_utilisable(page: Page, url: str, collecte: Collecte) -> bool:
    if not page.ok:
        collecte.notes.append(f"page en erreur : {url} → {page.erreur or f'HTTP {page.status}'}")
        return False
    if page.est_pdf:
        collecte.notes.append(f"page ignorée (PDF) : {url}")
        return False
    if len(page.markdown().strip()) < 500:
        collecte.notes.append(
            f"page vide ou SPA (contenu monté en JavaScript) : {url} — chercher la liste ailleurs"
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Dédoublonnage
# ---------------------------------------------------------------------------


def dedoublonner(
    candidats: list[Candidat],
    corpus: dict[str, Aide],
    file: dict[str, Tache] | None = None,
) -> tuple[list[Candidat], list[tuple[str, str]], list[tuple[str, str, str]]]:
    """Écarte ce que le catalogue ET la file d'attente contiennent déjà.

    Renvoie (retenus, (url, slug) du catalogue, (url, slug, statut) de la file).

    Le rapprochement se fait sur `cle_url` et jamais sur l'égalité brute : entre
    l'URL saisie dans une fiche et celle où le téléchargement aboutit, il y a
    couramment `http`/`https`, un `www.`, un slash final et une campagne `utm_`.

    La file compte TOUS ses statuts, `ignore` en tête. Sans elle, une URL déjà
    écartée à la main revenait au balayage suivant : `attribuer_slugs` lui
    donnait un slug suffixé `-2` (les slugs de la file sont dans `occupes`) et
    `etat.fusionner` la reposait en `a_valider` comme une inconnue. Les cinq
    `ignore` de Grand Est seraient revenus à chaque passage.
    """
    connues: dict[str, str] = {}
    for slug, aide in corpus.items():
        for url in (aide.source.url_officielle, aide.source.formulaire_url):
            if url:
                connues.setdefault(cle_url(url), slug)
    en_attente: dict[str, tuple[str, str]] = {}
    for slug, tache in (file or {}).items():
        if tache.url:
            en_attente.setdefault(cle_url(tache.url), (slug, tache.statut))
    retenus: list[Candidat] = []
    doublons: list[tuple[str, str]] = []
    en_file: list[tuple[str, str, str]] = []
    for candidat in candidats:
        cle = cle_url(candidat.url)
        slug = connues.get(cle)
        if slug:
            doublons.append((candidat.url, slug))
            continue
        connue = en_attente.get(cle)
        if connue:
            en_file.append((candidat.url, connue[0], connue[1]))
            continue
        retenus.append(candidat)
    return retenus, doublons, en_file


# ---------------------------------------------------------------------------
# Entrée
# ---------------------------------------------------------------------------


def collecter(
    territoire: Territoire,
    fetcheur: Fetcheur,
    corpus: dict[str, Aide],
    *,
    file: dict[str, Tache] | None = None,
    client_decouverte: providall.Client | None = None,
    compteur: Compteur | None = None,
) -> Collecte:
    """Balaye un territoire selon sa recette et rend ses candidats dédoublonnés."""
    collecte = Collecte()
    if not territoire.guides:
        collecte.notes.append(
            "aucun guide renseigné : compléter territoires.yaml "
            "(l'URL se cherche, elle ne se fabrique pas)"
        )
        return collecte

    match territoire.strategie.type:
        case "liste_html":
            bruts = _liste_html(territoire, fetcheur, collecte)
        case "sitemap":
            bruts = _sitemap(territoire, fetcheur, collecte)
        case "pagination":
            bruts = _pagination(territoire, fetcheur, collecte)
        case _:
            bruts = _decouverte(
                territoire, fetcheur, collecte, client=client_decouverte, compteur=compteur
            )

    uniques = list({c.url: c for c in bruts}.values())
    collecte.candidats, collecte.doublons, collecte.en_file = dedoublonner(uniques, corpus, file)
    collecte.notes.append(
        f"{len(uniques)} URL de fiche trouvées, {len(collecte.doublons)} déjà au catalogue, "
        f"{len(collecte.en_file)} déjà en file d'attente, "
        f"{len(collecte.candidats)} à trier ({collecte.pages_visitees} page(s) visitée(s))"
    )
    return collecte


__all__ = [
    "MAX_CAR_EXTRAIT",
    "MAX_CAR_LIBELLE",
    "PAGES_STERILES",
    "PAS_PROGRESSION",
    "Candidat",
    "Collecte",
    "RubriqueAides",
    "collecter",
    "dedoublonner",
    "liens",
    "titre_du_libelle",
    "titre_et_chapeau",
]
