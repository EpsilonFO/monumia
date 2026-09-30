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
from dataclasses import asdict, dataclass, field, replace
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

# --- A1 : la clé de fiche --------------------------------------------------
#
# `cle_url` normalise déjà le protocole, le `www.`, le slash final et les
# campagnes `utm_`. Il lui manque la PAGINATION : sur un guide Typo3,
# `?tx_news_pi1[currentPage]=1&cHash=abc` et `…=2&cHash=def` sont la même fiche
# vue deux fois, et 22 paires de doublons du lot des quatre régions viennent de
# là (`16-developpement-local`, `-2`, `-3`).
#
# La liste est FERMÉE et le restera. Un site a parfaitement le droit
# d'identifier ses fiches par `?page=<slug>` — le jour où une fiche disparaît,
# c'est ici qu'il faudra regarder, et une liste fermée se relit ; une heuristique
# ne se relit pas. `id`, `dispositif`, `aide`, `node`, `ref` ne sont JAMAIS
# touchés : ce sont des identifiants, pas de la pagination.
_PARAMS_PAGINATION = frozenset(
    {"page", "p", "start", "offset", "no_cache", "chash", "cursor", "from"}
)
_PARAM_PAGINATION_RE = re.compile(
    r"^(?:tx_\w+(?:_pi\d+)?\[(?:currentpage|pointer|page)\]"
    r"|\w*\[@widget_\d+\]"
    r"|\w*\[currentpage\])$"
)


def _est_pagination(parametre: str) -> bool:
    """Le paramètre nomme-t-il une page de liste, et non une fiche ?"""
    nom = parametre.split("=", 1)[0].strip().lower()
    return nom in _PARAMS_PAGINATION or bool(_PARAM_PAGINATION_RE.match(nom))


def cle_fiche(url: str) -> str:
    """`cle_url` débarrassée de la pagination : deux pages d'une même fiche, une clé.

    C'est la clé de groupement du dédoublonnage, à l'étage 1 comme sur la file
    entière (`pipeline.etat.doublons_par_url`). Les deux doivent grouper
    pareil, sans quoi une paire écartée ici reviendrait par là.
    """
    base = cle_url(url)
    chemin, _, requete = base.partition("?")
    if not requete:
        return base
    gardes = [p for p in requete.split("&") if p and not _est_pagination(p)]
    return chemin + (f"?{'&'.join(gardes)}" if gardes else "")


# --- A2 : un document n'est pas une fiche ----------------------------------
#
# 4 paires de doublons du lot viennent d'un `.doc` ou d'un `.zip` pris pour une
# fiche de dispositif (`54-appui-aux-territoires-54-fonctionnement`). Le motif
# `pdf_probable` ne connaissait que `.pdf` : un règlement en `.docx` passait
# donc l'étage 1 comme une page, se faisait lire par un modèle qui n'y
# comprenait rien, et finissait ingéré à côté de la vraie fiche.
EXTENSIONS_DOCUMENT = (
    ".pdf",
    ".doc",
    ".docx",
    ".odt",
    ".xls",
    ".xlsx",
    ".ods",
    ".ppt",
    ".pptx",
    ".zip",
    ".rtf",
)
# Au-delà, ce n'est plus le règlement d'un dispositif mais la médiathèque du
# site : la lecture applique déjà la même borne, et l'ingestion snapshote
# chacun de ces fichiers.
MAX_DOCUMENTS_PAR_PAGE = 25


def est_document(url: str) -> bool:
    """L'URL désigne-t-elle un fichier à télécharger plutôt qu'une page ?"""
    return url.lower().split("?")[0].split("#")[0].endswith(EXTENSIONS_DOCUMENT)


# --- A3 : un chemin qui tourne en rond -------------------------------------
#
# Moselle (57), 2026-09-18 : le site rend ses liens relatifs sans `/` initial,
# que `urljoin` concatène au chemin courant — `jcms/pl_17395/fr/jcms/pl_9352/…`,
# puis `…/fr/jcms/pl_17395/fr/jcms/…`, et le serveur répond 200 à chaque fois.
# 24 185 candidates fausses, autant d'appels de tri, 7 704 lectures en erreur,
# deux heures perdues. Le motif est reconnaissable : un segment qui revient.
MAX_SEGMENTS_CHEMIN = 12
MAX_REPETITIONS_SEGMENT = 2


def chemin_en_boucle(
    url: str,
    *,
    max_segments: int = MAX_SEGMENTS_CHEMIN,
    max_repetitions: int = MAX_REPETITIONS_SEGMENT,
) -> bool:
    """Le chemin de cette URL trahit-il une concaténation en boucle ?

    Deux signaux, tous deux nécessaires pour éviter les faux positifs : un
    chemin ANORMALEMENT profond, et un segment qui s'y répète. Un site peut
    légitimement ranger une fiche à huit niveaux ; aucun ne répète trois fois
    `jcms` dans une URL valide.
    """
    segments = [s for s in urlsplit(url).path.split("/") if s]
    if len(segments) <= max_segments:
        return False
    compte: dict[str, int] = {}
    for segment in segments:
        compte[segment] = compte.get(segment, 0) + 1
        if compte[segment] > max_repetitions:
            return True
    return False


# Un libellé de lien peut courir sur PLUSIEURS lignes. Sur un guide « en
# cartes » (Drupal Views, la plupart des sites régionaux récents), le <a>
# enveloppe l'étiquette thématique, le titre, le résumé, la liste des
# bénéficiaires et le « En savoir plus » : html2text en rend un libellé de dix
# lignes. Le balayage ligne à ligne les perdait en SILENCE — 0 candidat sur
# paysdelaloire.fr le 2026-09-11 alors que la page en portait douze, et 14
# liens perdus sur 187. `]` reste exclu du libellé, donc un lien ne peut
# toujours pas déborder sur le suivant ; la borne évite qu'un `]` manquant
# fasse avaler la moitié de la page.
#
# Un niveau de crochets ÉQUILIBRÉS est admis dans le libellé : les cartes de
# herault.fr finissent leur extrait par « [...] », et html2text le recopie tel
# quel. Le premier `]` fermait alors le libellé, et 29 liens sur 34 du guide
# disparaissaient (2026-09-28).
MAX_CAR_LIBELLE = 2000
_LIEN_MD_RE = re.compile(
    rf"\[((?:[^\[\]]|\[[^\[\]]{{0,200}}\]){{0,{MAX_CAR_LIBELLE}}}?)\]"
    r"\(\s*(<[^>]*>|[^)\s]+)[^)]*\)"
)
_PUCES = ("*", "-", "+")


@dataclass(frozen=True)
class Candidat:
    url: str
    titre: str = ""
    extrait: str = ""
    trouve_via: str = ""
    # Les fichiers téléchargeables liés depuis cette page : règlement, cadre
    # d'intervention, formulaire. Collectés ICI parce que c'est le seul étage
    # qui voit tous les liens d'une page, et transmis jusqu'à `urls_pdf` de la
    # tâche — la lecture les re-cherchait, et un `.docx` lui échappait.
    documents: tuple[str, ...] = ()

    def json(self) -> str:
        donnees = asdict(self)
        # Un champ vide ne s'écrit pas : les `candidats.jsonl` des balayages
        # précédents n'ont pas cette clé, et le relire ne doit pas exiger de
        # les réécrire.
        if not donnees["documents"]:
            donnees.pop("documents")
        else:
            donnees["documents"] = list(donnees["documents"])
        return json.dumps(donnees, ensure_ascii=False)


@dataclass
class Collecte:
    """Ce qu'un balayage a produit, et ce qui s'est mal passé en chemin."""

    candidats: list[Candidat] = field(default_factory=list)
    # Vrai quand le balayage s'est arrêté sur le plafond de candidates plutôt
    # que d'avoir tout vu : la fiche doit le dire en tête, sinon une recette
    # bancale passe pour un guide pauvre.
    plafonnee: bool = False
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
        candidats = []
        for ligne in chemin.read_text(encoding="utf-8").splitlines():
            if not ligne.strip():
                continue
            donnees = json.loads(ligne)
            donnees["documents"] = tuple(donnees.get("documents") or ())
            candidats.append(Candidat(**donnees))
        return candidats


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


_BASE_RE = re.compile(r"""<base\s[^>]*href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


def _base_des_liens(page: Page) -> str:
    """L'URL contre laquelle résoudre les liens relatifs : `<base href>` s'il y en a un.

    Les sites JCMS (loire.fr, rhone.fr, moselle.fr) écrivent des liens relatifs
    à la racine du site et déclarent `<base href="https://…/">` : résolus
    contre l'URL de la page, ils sortaient concaténés
    (`/jcms/lw_1/fr/jcms/lw_2/…`), et c'est ce qui faisait boucler la Moselle.
    """
    m = _BASE_RE.search((page.texte or "")[:50_000])
    if not m:
        return page.url_finale
    try:
        return urljoin(page.url_finale, m.group(1).strip())
    except ValueError:
        return page.url_finale


def liens(page: Page) -> list[tuple[str, str, str]]:
    """(titre, URL absolue, bloc de contexte) de chaque lien d'une page.

    Les URL relatives sont résolues contre l'URL FINALE (redirections suivies) :
    résoudre contre l'URL demandée produirait des liens cassés dès qu'un guide
    redirige `/aides` vers `/aides-regionales/`.

    Le contexte est le bloc de lignes que le lien enjambe. Pour un lien sur une
    seule ligne — le cas courant — c'est exactement la ligne, comme avant.
    """
    md = page.markdown()
    base = _base_des_liens(page)
    sortie: list[tuple[str, str, str]] = []
    for m in _LIEN_MD_RE.finditer(md):
        cible = m.group(2).strip().strip("<>")
        # `[Vous êtes ici]( "Vous êtes ici")` : un lien sans adresse, dont seul le
        # titre subsiste. La cible capturée est alors le début du titre, et
        # yonne.fr donnait 116 candidates en `…/"Vous`, toutes en 404 (2026-09-29).
        if not cible or cible.startswith(("#", "mailto:", "javascript:", "tel:", '"', "'")):
            continue
        try:
            absolue = urljoin(base, cible)
        except ValueError:
            # `href="http://[…"` : urljoin y voit une adresse IPv6 mal formée et
            # lève. Vu le 2026-09-28 sur tarn.fr, où un seul lien cassé faisait
            # tomber la collecte du territoire et de tous ceux qui suivaient.
            continue
        debut = md.rfind("\n", 0, m.start()) + 1
        fin = md.find("\n", m.end())
        bloc = md[debut:] if fin == -1 else md[debut:fin]
        sortie.append((titre_du_libelle(m.group(1)), absolue, " ".join(bloc.split())))
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


def documents_de_page(page: Page, territoire: Territoire) -> tuple[str, ...]:
    """Les fichiers téléchargeables liés depuis cette page, dans l'ordre vu.

    Le règlement d'un dispositif pend presque toujours de sa fiche : le
    ramasser ici évite à la lecture de le re-chercher, et surtout évite qu'un
    `.docx` — que `pdf_probable` ne reconnaissait pas — soit pris pour une
    fiche et ingéré à côté de la vraie.
    """
    trouves: list[str] = []
    for _titre, url, _contexte in liens(page):
        url = url.split("#")[0]
        if (est_document(url) or territoire.pdf_probable(url)) and url not in trouves:
            trouves.append(url)
    return tuple(trouves[:MAX_DOCUMENTS_PAR_PAGE])


def _candidats_de_page(page: Page, territoire: Territoire, via: str) -> list[Candidat]:
    """Les fiches liées depuis cette page. Un document n'en est jamais une (A2).

    Une URL liée deux fois garde le premier libellé NON VIDE : une carte qui
    commence par un lien image vers la même fiche donnait un titre vide
    (mesdemarches.cantal.fr, 2026-09-28), et le tri jugeait l'URL seule.
    """
    vus: dict[str, int] = {}
    retenus: list[Candidat] = []
    for titre, url, contexte in liens(page):
        url = url.split("#")[0]
        if est_document(url) or territoire.pdf_probable(url):
            continue
        if url in vus:
            i = vus[url]
            if not retenus[i].titre and titre:
                retenus[i] = replace(retenus[i], titre=titre, extrait=contexte[:MAX_CAR_EXTRAIT])
            continue
        if chemin_en_boucle(url) or not territoire.fiche_probable(url):
            continue
        vus[url] = len(retenus)
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
        # Un sitemap peut arriver précédé d'un blanc — seine-et-marne.fr (Drupal
        # simple_sitemap) émet un saut de ligne AVANT la déclaration XML, et
        # `fromstring` refuse alors tout le document (« XML or text declaration
        # not at start of entity »). Le guide entier disparaissait en silence,
        # réduit à une note technique.
        racine = ET.fromstring(page.contenu.lstrip())
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
    # Groupement sur `cle_fiche` et non sur l'URL brute : un sitemap Typo3
    # énumère volontiers les pages paginées d'un même dispositif.
    par_cle: dict[str, str] = {}
    for u in urls:
        if territoire.fiche_probable(u) and not est_document(u) and not chemin_en_boucle(u):
            par_cle.setdefault(cle_fiche(u), u)
    fiches = list(par_cle.values())

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
        candidats.append(
            Candidat(
                url=u,
                titre=titre,
                extrait=chapeau,
                trouve_via="sitemap",
                documents=documents_de_page(page, territoire) if page.ok and page.est_html else (),
            )
        )
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

    boucles = 0
    documents_ignores = 0
    while file and collecte.pages_visitees < strategie.max_pages:
        if len(trouves) >= strategie.max_candidats:
            collecte.plafonnee = True
            break
        url, profondeur = file.popleft()
        page = accueil if url == accueil.url_finale else fetcheur.get(url)
        if url != accueil.url_finale:
            collecte.pages_visitees += 1
            if not page.ok or page.est_pdf:
                continue
        # Les documents de cette page appartiennent à cette page : si elle est
        # elle-même une candidate, ils la suivent jusqu'à `urls_pdf`.
        candidat_courant = trouves.get(url)
        if candidat_courant is not None and not candidat_courant.documents:
            trouves[url] = replace(candidat_courant, documents=documents_de_page(page, territoire))
        for _titre, lien, contexte in liens(page):
            lien = lien.split("#")[0]
            if urlsplit(lien).netloc != hote or lien in vus:
                continue
            if any(re.search(m, lien) for m in territoire.exclure):
                continue
            # Le piège de la Moselle : `urljoin` concatène un lien relatif sans
            # `/` au chemin courant, le serveur répond 200, et l'exploration
            # s'enfonce. Testé AVANT `vus.add` — une URL en boucle ne doit ni
            # être retenue, ni servir de point de départ.
            if chemin_en_boucle(lien):
                boucles += 1
                continue
            vus.add(lien)
            if est_document(lien) or territoire.pdf_probable(lien):
                documents_ignores += 1
                continue
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
    if boucles:
        collecte.notes.append(
            f"découverte : {boucles} URL à chemin répétitif ignorées (liens relatifs "
            "concaténés — le serveur répond 200 sur des chemins en boucle)"
        )
    if documents_ignores:
        collecte.notes.append(
            f"découverte : {documents_ignores} document(s) téléchargeable(s) écarté(s) "
            "des candidates"
        )
    if collecte.plafonnee:
        collecte.notes.append(
            f"arrêt propre : plafond de {strategie.max_candidats} candidates atteint — "
            "recette à préciser dans territoires.yaml"
        )
    elif collecte.pages_visitees >= strategie.max_pages:
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

    Le rapprochement se fait sur `cle_fiche` et jamais sur l'égalité brute :
    entre l'URL saisie dans une fiche et celle où le téléchargement aboutit, il
    y a couramment `http`/`https`, un `www.`, un slash final, une campagne
    `utm_` — et, depuis 2026-09, le numéro de page d'une liste Typo3 (A1).

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
                connues.setdefault(cle_fiche(url), slug)
    en_attente: dict[str, tuple[str, str]] = {}
    for slug, tache in (file or {}).items():
        if tache.url:
            en_attente.setdefault(cle_fiche(tache.url), (slug, tache.statut))
    retenus: list[Candidat] = []
    doublons: list[tuple[str, str]] = []
    en_file: list[tuple[str, str, str]] = []
    for candidat in candidats:
        cle = cle_fiche(candidat.url)
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
    max_candidats: int | None = None,
) -> Collecte:
    """Balaye un territoire selon sa recette et rend ses candidats dédoublonnés.

    `max_candidats` borne ce que le balayage rend, et il borne du même coup le
    tri et la lecture — les deux étages qui coûtent un modèle n'avaient
    AUCUN plafond. Moselle, 2026-09-18 : 24 185 candidates, autant d'appels de
    tri, 7 704 lectures en erreur, deux heures. Un plafond ne corrige pas une
    mauvaise recette ; il rend son coût fini et le dit dans la fiche.
    """
    collecte = Collecte()
    plafond = max_candidats if max_candidats is not None else territoire.strategie.max_candidats
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

    # Dédoublonnage sur `cle_fiche` : trois pages d'une même liste Typo3 ne
    # font qu'une fiche. À clé égale, on garde l'URL la plus courte en
    # paramètres — la page de fiche, pas celle qui porte un `cHash` de
    # navigation.
    par_cle: dict[str, Candidat] = {}
    for candidat in bruts:
        cle = cle_fiche(candidat.url)
        garde = par_cle.get(cle)
        if garde is None or len(candidat.url) < len(garde.url):
            # Les documents survivent au remplacement : c'est la page ouverte
            # qui les a vus, pas la variante la plus courte.
            if garde is not None and garde.documents and not candidat.documents:
                candidat = replace(candidat, documents=garde.documents)
            par_cle[cle] = candidat
    uniques = list(par_cle.values())
    if len(uniques) > plafond:
        collecte.plafonnee = True
        collecte.notes.append(
            f"arrêt propre : plafond de {plafond} candidates — {len(uniques)} trouvées, "
            "les suivantes ne sont ni triées ni lues ; recette à préciser dans "
            "territoires.yaml"
        )
        uniques = uniques[:plafond]
    collecte.candidats, collecte.doublons, collecte.en_file = dedoublonner(uniques, corpus, file)
    collecte.notes.append(
        f"{len(uniques)} URL de fiche trouvées, {len(collecte.doublons)} déjà au catalogue, "
        f"{len(collecte.en_file)} déjà en file d'attente, "
        f"{len(collecte.candidats)} à trier ({collecte.pages_visitees} page(s) visitée(s))"
    )
    return collecte


__all__ = [
    "EXTENSIONS_DOCUMENT",
    "MAX_CAR_EXTRAIT",
    "MAX_CAR_LIBELLE",
    "PAGES_STERILES",
    "PAS_PROGRESSION",
    "MAX_DOCUMENTS_PAR_PAGE",
    "Candidat",
    "Collecte",
    "RubriqueAides",
    "chemin_en_boucle",
    "cle_fiche",
    "collecter",
    "dedoublonner",
    "documents_de_page",
    "est_document",
    "liens",
    "titre_du_libelle",
    "titre_et_chapeau",
]
