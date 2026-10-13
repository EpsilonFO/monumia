"""Un fetcheur poli, qui sait franchir les WAF déjà rencontrés.

Toute la connaissance des sites hostiles est déjà dans `snapshot_source` : la
séquence 403 → en-têtes de navigateur (normandie.fr / Akamai) et la résolution
du défi JavaScript (AURA). Elle est reprise ici telle quelle plutôt que
réécrite — un second dialecte de contournement divergerait du premier au
premier site qui change.

Ce que ce module ajoute, et que `snapshot()` n'avait pas besoin d'avoir :
  - un verrou et un délai minimal PAR HÔTE, partagés par tous les workers : la
    prospection ouvre des dizaines de pages du même guide régional, et rien ne
    fait fermer une porte plus vite qu'une rafale parallèle ;
  - un cache mémoire, parce qu'une même page est souvent visitée deux fois
    (exploration puis snapshot) ;
  - un `transport` injectable, pour tester sans réseau ;
  - la vérification des certificats par le magasin du SYSTÈME (`truststore`) et
    non par le seul bundle `certifi` : eurelien.fr sert une chaîne incomplète
    que curl et le navigateur complètent, pas certifi ;
  - un repli par `curl_cffi`, qui se présente avec l'empreinte TLS de Chrome,
    quand httpx refuse une réponse malformée (dordogne.fr et ses deux en-têtes
    `Transfer-Encoding`) ou qu'un 403 résiste aux en-têtes de navigateur.

Le repli ne franchit PAS un challenge Cloudflare (« Just a moment… » :
bretagne.bzh, haute-vienne.fr, sondés le 2026-09-28) : il y faudrait un vrai
navigateur, ce que ce module ne pilote pas.
"""

from __future__ import annotations

import fcntl
import os
import re
import ssl
import sys
import threading
import time
from collections import OrderedDict, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import truststore

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snapshot_source import (
    HEADERS_NAVIGATEUR,
    UA,
    docx_bytes_to_text,
    est_docx,
    resoudre_shield,
    to_markdown,
)

# Délai minimal entre deux requêtes vers le MÊME hôte. Une seconde est ce que
# demandent la plupart des `robots.txt` des sites publics ; les hôtes
# différents ne s'attendent pas les uns les autres.
DELAI_HOTE_S = 1.0
# Un sitemap régional dépasse 200 fiches (Grand Est : 244) ; en dessous, la
# lecture retélécharge ce que la collecte vient d'ouvrir.
TAILLE_CACHE = 400

# Partagés au niveau module : deux `Fetcheur` construits par deux workers
# doivent quand même se relayer sur le même hôte.
_verrous_hote: dict[str, threading.Lock] = defaultdict(threading.Lock)
_dernier_appel: dict[str, float] = {}
_garde = threading.Lock()

TYPES_HTML = ("text/html", "application/xhtml")

# Un seul contexte pour tous les clients : un `SSLContext` se partage entre
# threads, et le construire relit le magasin de certificats du système.
_CONTEXTE_TLS = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


@dataclass(frozen=True)
class Page:
    """Ce qu'une URL a rendu. Une page en erreur est une donnée, pas une exception."""

    url: str
    url_finale: str
    status: int
    content_type: str
    contenu: bytes
    texte: str
    erreur: str | None = None

    @property
    def ok(self) -> bool:
        return self.erreur is None and 200 <= self.status < 300

    @property
    def est_pdf(self) -> bool:
        return self.contenu[:5] == b"%PDF-" or "pdf" in self.content_type

    @property
    def est_docx(self) -> bool:
        """Un règlement d'intervention en .docx est fréquent sur les guides régionaux.

        Sans ce cas, `texte` est le ZIP décodé en force et `markdown()` rendait
        « PK...[Content_Types].xml » : rien de citable (cf. `docx_bytes_to_text`).
        """
        return "wordprocessingml" in self.content_type or est_docx(self.contenu)

    @property
    def est_html(self) -> bool:
        return self.content_type.startswith(TYPES_HTML) or (
            not self.content_type and "<html" in self.texte[:2000].lower()
        )

    def markdown(self) -> str:
        """Markdown de la page. Vide pour un PDF — son texte s'extrait ailleurs.

        Un PDF n'a rien à faire dans html2text : c'est `veille_collect.
        pdf_bytes_to_text` qui sait le lire, et il vit une couche plus haut
        (il dépend du schéma des aides). Un .docx, lui, se convertit ici : le
        faire une couche plus haut laisserait `explorer_url` rendre du binaire.
        """
        if not self.ok or self.est_pdf:
            return ""
        if self.est_docx:
            return docx_bytes_to_text(self.contenu)
        return to_markdown(self.texte) if self.est_html else self.texte


Repli = Callable[[str, float], Page]


def _page_en_erreur(url: str, erreur: str) -> Page:
    return Page(
        url=url, url_finale=url, status=0, content_type="", contenu=b"", texte="", erreur=erreur
    )


def telecharger_comme_chrome(url: str, timeout: float) -> Page:
    """Le repli : une requête dont la poignée de main TLS est celle de Chrome.

    Import local : `curl_cffi` embarque sa propre libcurl, et la plupart des runs
    n'en ont jamais besoin.
    """
    from curl_cffi import requests as curl_requests

    try:
        resp = curl_requests.get(
            url,
            impersonate="chrome",
            headers={"Accept-Language": HEADERS_NAVIGATEUR["Accept-Language"]},
            timeout=timeout,
            allow_redirects=True,
        )
    except curl_requests.RequestsError as exc:
        return _page_en_erreur(url, f"curl_cffi {type(exc).__name__}: {exc}")
    contenu = resp.content
    return Page(
        url=url,
        url_finale=str(resp.url),
        status=resp.status_code,
        content_type=resp.headers.get("content-type", "").split(";")[0].strip().lower(),
        contenu=contenu,
        texte="" if contenu[:5] == b"%PDF-" else resp.text,
    )


def _hote(url: str) -> str:
    return urlsplit(url).netloc.lower()


def _attendre_son_tour(hote: str, delai_s: float) -> None:
    """Respecte le délai minimal depuis la dernière requête vers cet hôte.

    Deux niveaux : entre les fils du processus (verrou et horodatage en
    mémoire), puis entre les processus de la machine (`_attendre_entre_processus`).
    """
    with _garde:
        precedent = _dernier_appel.get(hote)
    if precedent is not None:
        reste = delai_s - (time.monotonic() - precedent)
        if reste > 0:
            time.sleep(reste)
    if delai_s > 0:
        _attendre_entre_processus(hote, delai_s)
    with _garde:
        _dernier_appel[hote] = time.monotonic()


def _dossier_hotes() -> Path | None:
    """Où vit l'horodatage partagé de chaque hôte. `MONUMIA_HOTES=""` le désactive."""
    valeur = os.environ.get("MONUMIA_HOTES")
    if valeur == "":
        return None
    return Path(valeur) if valeur else Path.home() / ".cache" / "monumia" / "hotes"


def _attendre_entre_processus(hote: str, delai_s: float) -> None:
    """Le délai par hôte vaut pour toute la machine, pas pour un seul processus.

    La refonte fait tourner plusieurs processus à la fois (trois extractions en
    parallèle, la collecte, la veille) : le verrou en mémoire ne les voit pas,
    et un guide régional bloqué casserait aussi la veille de Félix. Un fichier
    par hôte, verrouillé (`flock`) le temps de lire l'heure du dernier appel,
    d'attendre et d'écrire la nouvelle. Une erreur de fichier ne bloque pas le
    téléchargement : le verrou en mémoire reste.
    """
    dossier = _dossier_hotes()
    if dossier is None:
        return
    nom = re.sub(r"[^a-z0-9.-]", "_", hote.lower()) or "_"
    try:
        dossier.mkdir(parents=True, exist_ok=True)
        with (dossier / f"{nom}.lock").open("a+", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.seek(0)
                texte = f.read().strip()
                try:
                    dernier = float(texte) if texte else 0.0
                except ValueError:
                    dernier = 0.0
                reste = delai_s - (time.time() - dernier)
                if reste > 0:
                    time.sleep(min(reste, delai_s))
                f.seek(0)
                f.truncate()
                f.write(f"{time.time():.6f}")
                f.flush()
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except OSError:
        return


class Fetcheur:
    """Client HTTP réutilisable. Un par worker ; les verrous d'hôte sont communs.

    `repli` vaut `telecharger_comme_chrome` par défaut, SAUF quand un `transport`
    est injecté : un transport de test coupe le réseau, repli compris. Un test
    qui veut exercer le repli passe le sien.
    """

    def __init__(
        self,
        *,
        entetes: str = "standard",
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        delai_s: float = DELAI_HOTE_S,
        taille_cache: int = TAILLE_CACHE,
        repli: Repli | None = None,
    ) -> None:
        if entetes not in ("standard", "navigateur"):
            raise ValueError(f"entetes inconnu : {entetes!r} (standard | navigateur)")
        self.entetes = entetes
        self.delai_s = delai_s
        self.timeout = timeout
        self.taille_cache = taille_cache
        self._repli = repli if repli is not None or transport else telecharger_comme_chrome
        self._client = httpx.Client(
            headers=self._entetes_de_depart(),
            follow_redirects=True,
            timeout=timeout,
            transport=transport,
            verify=_CONTEXTE_TLS,
        )
        self._cache: OrderedDict[str, Page] = OrderedDict()
        self._cache_lock = threading.Lock()

    def _entetes_de_depart(self) -> dict[str, str]:
        return dict(HEADERS_NAVIGATEUR) if self.entetes == "navigateur" else {"User-Agent": UA}

    # ------------------------------------------------------------------ API

    def get(self, url: str) -> Page:
        if (page := self._du_cache(url)) is not None:
            return page
        hote = _hote(url)
        with _verrous_hote[hote]:
            _attendre_son_tour(hote, self.delai_s)
            page = self._telecharger(url)
        self._mettre_en_cache(url, page)
        return page

    def markdown(self, url: str) -> str:
        return self.get(url).markdown()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Fetcheur:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # -------------------------------------------------------------- interne

    def _telecharger(self, url: str) -> Page:
        try:
            resp = self._client.get(url)
            # Un 403 est déterministe : seul un changement d'identité a une
            # chance de passer. On ne bascule qu'APRÈS le refus, jamais d'emblée
            # (cf. le commentaire de HEADERS_NAVIGATEUR).
            if resp.status_code == 403 and self.entetes != "navigateur":
                resp = self._client.get(url, headers=HEADERS_NAVIGATEUR)
            if (defi := resoudre_shield(resp.content)) is not None:
                nom, valeur = defi
                self._client.cookies.set(nom, valeur, domain=_hote(str(resp.url)))
                resp = self._client.get(url, headers=HEADERS_NAVIGATEUR)
        except httpx.RemoteProtocolError as exc:
            # Le serveur a bien répondu, mais d'une façon que httpx refuse
            # (dordogne.fr : deux `Transfer-Encoding`) ; libcurl est plus tolérant.
            return self._par_le_repli(url, _page_en_erreur(url, f"{type(exc).__name__}: {exc}"))
        except httpx.HTTPError as exc:
            # DNS, délai, certificat : changer de client n'y ferait rien.
            return _page_en_erreur(url, f"{type(exc).__name__}: {exc}")
        page = Page(
            url=url,
            url_finale=str(resp.url),
            status=resp.status_code,
            content_type=resp.headers.get("content-type", "").split(";")[0].strip().lower(),
            contenu=resp.content,
            # `resp.text` sur un PDF produirait des méga-octets de mojibake :
            # le texte n'a de sens que pour les réponses textuelles.
            texte="" if resp.content[:5] == b"%PDF-" else resp.text,
        )
        # Les en-têtes de navigateur ont déjà été essayés : si le 403 tient,
        # c'est l'empreinte TLS de httpx qui est reconnue, pas ses en-têtes.
        return self._par_le_repli(url, page) if page.status == 403 else page

    def _par_le_repli(self, url: str, echec: Page) -> Page:
        """La page du repli si elle aboutit ; sinon l'échec d'origine, qui dit mieux la cause."""
        if self._repli is None:
            return echec
        page = self._repli(url, self.timeout)
        if page.ok:
            return page
        if echec.erreur is None:
            return echec
        return replace(
            echec, erreur=f"{echec.erreur} ; repli : {page.erreur or f'HTTP {page.status}'}"
        )

    def _du_cache(self, url: str) -> Page | None:
        with self._cache_lock:
            page = self._cache.get(url)
            if page is not None:
                self._cache.move_to_end(url)
            return page

    def _mettre_en_cache(self, url: str, page: Page) -> None:
        # Une panne réseau n'est pas mise en cache : elle est souvent
        # transitoire, et la figer condamnerait l'URL pour tout le run.
        if page.erreur is not None:
            return
        with self._cache_lock:
            self._cache[url] = page
            self._cache.move_to_end(url)
            while len(self._cache) > self.taille_cache:
                self._cache.popitem(last=False)


def reinitialiser_delais() -> None:
    """Oublie les derniers appels par hôte. Réservé aux tests."""
    with _garde:
        _dernier_appel.clear()


__all__ = [
    "DELAI_HOTE_S",
    "TAILLE_CACHE",
    "Fetcheur",
    "Page",
    "Repli",
    "reinitialiser_delais",
    "telecharger_comme_chrome",
]
