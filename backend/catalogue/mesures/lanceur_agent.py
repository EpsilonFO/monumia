"""Lanceur de l'agent d'ingestion pour le banc X : sources rejouées, appels relevés (I0, M3).

Commande, depuis le `backend/` d'une copie jetable du dépôt, avec l'interpréteur
du worktree (`uv` créerait un venv neuf dans la copie) :

    <worktree>/backend/.venv/bin/python -m catalogue.mesures.lanceur_agent \\
        --sources <worktree>/backend/data/sources/<slug> --appels <fichier.jsonl> -- \\
        --slug <slug> --sortie <dossier> --model or-glm --model-verif or-ds41 \\
        --sans-audit --tarif 0.15,0.50

Le lanceur prépare le processus de l'agent sans toucher à son code, puis appelle
`ingerer.main` avec les arguments qui suivent `--` :

- il copie les instantanés archivés de l'aide dans `<sortie>/sources/<slug>/`,
  que l'agent, son lint et son vérificateur lisent ;
- il remplace `Fetcheur.get` par une lecture de ces instantanés : une URL archivée
  rend son contenu, toute autre URL une erreur 404 « hors du banc ». L'agent et
  l'extraction structurée lisent ainsi les mêmes textes, et seuls les appels de
  modèle passent par le réseau ;
- il remplace les fonctions d'écriture appelées par l'outil `snapshotter` par le
  renvoi du fichier déjà archivé, pour que l'agent lise l'instantané d'origine et
  non une reconversion ;
- il enveloppe l'envoi de providall (`ChatCompletionsAdapter.send`) : chaque
  tentative, réussie ou non, est écrite dans `--appels` avec le modèle servi, le
  fournisseur, le coût facturé par OpenRouter (`usage.cost`), les jetons et la
  durée. Le journal de l'agent ne donne que l'alias demandé et un coût estimé.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pipeline import web
from providall.providers.openai_compat import ChatCompletionsAdapter

from catalogue.veille_collect import cle_url
from catalogue.veille_text import parse_front_matter

TYPE_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@dataclass(frozen=True)
class Archive:
    """Un document archivé, tel que le banc le rejoue."""

    url: str
    chemin: Path  # le fichier que lit l'agent : .md, ou .pdf
    nature: str  # md, pdf ou docx
    contenu: bytes
    corps: str  # le texte d'un .md (conversion comprise pour un .docx)


@dataclass(frozen=True)
class PageRejouee(web.Page):
    """Une page servie depuis l'archive ; son markdown est celui de l'instantané."""

    md: str = ""

    def markdown(self) -> str:
        return self.md


def _meta(chemin: Path) -> dict[str, Any]:
    """L'en-tête `.meta.yaml` d'un instantané binaire.

    Vide quand il manque : des archives de juillet 2026 n'en ont pas (le PDF de
    `hdf-etude-prealable-patrimoine`, ceux de `35-patrimoine`). Leur URL est
    alors inconnue, le fichier n'est pas servi par URL, mais l'agent le lit
    encore par l'outil `snapshots`, qui liste le dossier.
    """
    meta = chemin.with_name(chemin.name + ".meta.yaml")
    if not meta.exists():
        return {}
    return yaml.safe_load(meta.read_text(encoding="utf-8")) or {}


def indexer(dossier: Path) -> dict[str, Archive]:
    """Les documents d'un dossier d'instantanés, par URL canonique ; le plus récent l'emporte."""
    index: dict[str, Archive] = {}
    for chemin in sorted(dossier.iterdir()):
        nom = chemin.name
        if nom.endswith(".pdf"):
            meta = _meta(chemin)
            if meta.get("url"):
                index[cle_url(meta["url"])] = Archive(
                    meta["url"], chemin, "pdf", chemin.read_bytes(), ""
                )
        elif nom.endswith(".docx"):
            meta = _meta(chemin)
            converti = chemin.with_suffix(".md")
            if meta and meta.get("url") and converti.exists():
                _, corps = parse_front_matter(converti.read_text(encoding="utf-8"))
                index[cle_url(meta["url"])] = Archive(
                    meta["url"], converti, "docx", chemin.read_bytes(), corps
                )
        elif nom.endswith(".md") and not chemin.with_suffix(".docx").exists():
            entete, corps = parse_front_matter(chemin.read_text(encoding="utf-8"))
            if entete.get("url"):
                index[cle_url(entete["url"])] = Archive(
                    entete["url"], chemin, "md", corps.encode(), corps
                )
    return index


def rejouer(index: dict[str, Archive]) -> None:
    """Remplace le téléchargement et l'écriture des instantanés par la lecture de l'archive."""
    from ingestion import outils

    def trouver(url: str) -> Archive | None:
        return index.get(cle_url(url))

    def get(_self: web.Fetcheur, url: str) -> web.Page:
        a = trouver(url)
        if a is None:
            return web.Page(
                url=url,
                url_finale=url,
                status=404,
                content_type="",
                contenu=b"",
                texte="",
                erreur="hors du banc : document non archivé",
            )
        types = {"md": "text/html; charset=utf-8", "pdf": "application/pdf", "docx": TYPE_DOCX}
        return PageRejouee(
            url=url,
            url_finale=a.url,
            status=200,
            content_type=types[a.nature],
            contenu=a.contenu,
            texte=a.corps if a.nature == "md" else "",
            md=a.corps if a.nature == "md" else "",
        )

    def md(slug: str, url: str, raw_text: str, **_: Any) -> Path:
        a = trouver(url)
        if a is None or a.nature != "md":
            raise SystemExit(f"hors du banc : {url} n'est pas une page archivée")
        return a.chemin

    def pdf(slug: str, content: bytes, *, url: str | None = None, **_: Any) -> Path:
        a = trouver(url or "")
        if a is None or a.nature != "pdf":
            raise SystemExit(f"hors du banc : {url} n'est pas un PDF archivé")
        return a.chemin

    def docx(slug: str, content: bytes, *, url: str | None = None, **_: Any) -> tuple[Path, str]:
        a = trouver(url or "")
        if a is None or a.nature != "docx":
            raise SystemExit(f"hors du banc : {url} n'est pas un .docx archivé")
        return a.chemin, a.corps

    web.Fetcheur.get = get  # type: ignore[method-assign]
    outils.write_md_snapshot = md  # type: ignore[assignment]
    outils.write_pdf_snapshot = pdf  # type: ignore[assignment]
    outils.write_docx_snapshot = docx  # type: ignore[assignment]


# L'envoi d'origine, gardé une fois : appeler `relever` pour une nouvelle aide dans
# le même processus remplace l'enveloppe au lieu de l'empiler (le 2026-10-10,
# l'empilement a recopié les appels des aides suivantes dans les fichiers des
# précédentes, sans fausser leurs coûts, calculés à la fin de chaque aide).
_ENVOI_ORIGINAL = ChatCompletionsAdapter.send


def relever(appels: Path) -> None:
    """Écrit chaque tentative d'appel de modèle, réussie ou non, dans `appels`."""
    envoyer = _ENVOI_ORIGINAL
    verrou = threading.Lock()

    def ecrire(ligne: dict[str, Any]) -> None:
        with verrou, appels.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")

    def send(self: ChatCompletionsAdapter, req: Any, body: dict[str, Any]) -> Any:
        debut = time.monotonic()
        ligne: dict[str, Any] = {
            "t": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "alias": req.spec.alias,
            "modele_demande": req.spec.model_id,
            "role": req.label,
        }
        try:
            brut = envoyer(self, req, body)
        except Exception as exc:
            ligne.update(
                erreur=f"{type(exc).__name__}: {str(exc)[:300]}",
                duree_s=round(time.monotonic() - debut, 2),
            )
            ecrire(ligne)
            raise
        usage = getattr(brut, "usage", None)
        extra = getattr(usage, "model_extra", None) or {}
        cout = getattr(usage, "cost", None)
        if cout is None:
            cout = extra.get("cost")
        ligne.update(
            modele_servi=getattr(brut, "model", None),
            fournisseur=(getattr(brut, "model_extra", None) or {}).get("provider"),
            cout_usd=cout,
            jetons_entree=getattr(usage, "prompt_tokens", None),
            jetons_sortie=getattr(usage, "completion_tokens", None),
            duree_s=round(time.monotonic() - debut, 2),
        )
        ecrire(ligne)
        return brut

    ChatCompletionsAdapter.send = send  # type: ignore[method-assign]


def main() -> int:
    if "--" not in sys.argv:
        raise SystemExit(
            "usage : lanceur_agent --sources <dossier> --appels <fichier> -- <arguments d'ingerer.py>"
        )
    coupure = sys.argv.index("--")
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--sources", required=True)
    parseur.add_argument("--appels", required=True)
    args = parseur.parse_args(sys.argv[1:coupure])
    reste = sys.argv[coupure + 1 :]
    slug = reste[reste.index("--slug") + 1]
    sortie = Path(reste[reste.index("--sortie") + 1])

    cible = sortie / "sources" / slug
    if not cible.exists():
        shutil.copytree(args.sources, cible)
    rejouer(indexer(cible))
    relever(Path(args.appels))

    import ingerer

    return ingerer.main(reste)


if __name__ == "__main__":
    raise SystemExit(main())
