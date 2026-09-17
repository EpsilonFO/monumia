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
  - un `transport` injectable, pour tester sans réseau.
"""

from __future__ import annotations

import sys
import threading
import time
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx

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


def _hote(url: str) -> str:
    return urlsplit(url).netloc.lower()


def _attendre_son_tour(hote: str, delai_s: float) -> None:
    """Respecte le délai minimal depuis la dernière requête vers cet hôte."""
    with _garde:
        precedent = _dernier_appel.get(hote)
    if precedent is not None:
        reste = delai_s - (time.monotonic() - precedent)
        if reste > 0:
            time.sleep(reste)
    with _garde:
        _dernier_appel[hote] = time.monotonic()


class Fetcheur:
    """Client HTTP réutilisable. Un par worker ; les verrous d'hôte sont communs."""

    def __init__(
        self,
        *,
        entetes: str = "standard",
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        delai_s: float = DELAI_HOTE_S,
        taille_cache: int = TAILLE_CACHE,
    ) -> None:
        if entetes not in ("standard", "navigateur"):
            raise ValueError(f"entetes inconnu : {entetes!r} (standard | navigateur)")
        self.entetes = entetes
        self.delai_s = delai_s
        self.taille_cache = taille_cache
        self._client = httpx.Client(
            headers=self._entetes_de_depart(),
            follow_redirects=True,
            timeout=timeout,
            transport=transport,
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
        except httpx.HTTPError as exc:
            return Page(
                url=url,
                url_finale=url,
                status=0,
                content_type="",
                contenu=b"",
                texte="",
                erreur=f"{type(exc).__name__}: {exc}",
            )
        return Page(
            url=url,
            url_finale=str(resp.url),
            status=resp.status_code,
            content_type=resp.headers.get("content-type", "").split(";")[0].strip().lower(),
            contenu=resp.content,
            # `resp.text` sur un PDF produirait des méga-octets de mojibake :
            # le texte n'a de sens que pour les réponses textuelles.
            texte="" if resp.content[:5] == b"%PDF-" else resp.text,
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


__all__ = ["DELAI_HOTE_S", "TAILLE_CACHE", "Fetcheur", "Page", "reinitialiser_delais"]
