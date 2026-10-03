"""
Reconstitue la provenance des PDF archivés sans sidecar `<stamp>.pdf.meta.yaml`.

    cd backend && uv run python scripts/backfill_pdf_sidecars.py --dry-run
    cd backend && uv run python scripts/backfill_pdf_sidecars.py --offline
    cd backend && uv run python scripts/backfill_pdf_sidecars.py 56-circulation-oeuvres

Sans sidecar, un règlement PDF n'est rattachable à aucune URL : la veille ne
peut ni le re-télécharger ni le differ, et toutes les conditions qu'il justifie
sortent en « citation non recontrôlable ». Un `OK` sur une telle aide ne porte
alors que sur sa page d'atterrissage HTML. C'est le cas des 109 PDF antérieurs
au sidecar, dont 23 aides tirent 100 % de leurs citations.

L'URL n'est enregistrée nulle part — une seule est retrouvable depuis
`source.url_officielle`. On la redécouvre donc, par ordre de coût croissant :

1. `source.url_officielle`, quand elle pointe directement le PDF ;
2. les liens `.pdf` des `.md` archivés, relatifs résolus contre l'URL de leur
   en-tête. Gratuit, et daté du même jour que le PDF : c'est la page telle
   qu'elle était quand le PDF a été récupéré ;
3. les liens `.pdf` de la page officielle fraîchement téléchargée (sauf
   `--offline`) ;
4. `--url`, pour l'URL qu'un humain a retrouvée à la main quand les trois
   premières sources ont échoué. Elle est confrontée au PDF archivé comme
   toutes les autres : proposer une URL ne la fait pas accepter.

Chaque candidate est téléchargée puis confrontée au PDF archivé :

- sha256 identique          -> `sha`, certitude ;
- texte très proche         -> `texte`, le document a été mis à jour depuis
                               l'archivage mais l'URL est la bonne ;
- en dessous du seuil       -> rien n'est écrit, l'aide est listée à la main.

Un sidecar porte le sha du PDF **archivé**, pas celui du téléchargement : c'est
la baseline, et c'est ce qui permettra à la veille de détecter la prochaine
modification. Le champ `match` garde la preuve du rattachement pour audit.

Codes de sortie : 0 terminé ; 1 erreur fatale.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aides_schema import AIDES_DIR, Aide, load_aide

sys.path.insert(0, str(Path(__file__).resolve().parent))

from snapshot_source import HEADERS_NAVIGATEUR, SOURCES_DIR, UA, resoudre_shield
from veille_collect import pdf_to_text
from veille_text import parse_front_matter

# Liens PDF d'un markdown : `](...pdf)`. Relatifs acceptés, résolus plus tard
# contre l'URL de l'en-tête du snapshot.
LIEN_MD = re.compile(r"\]\(([^)\s]+?\.pdf)\)", re.I)
# Idem dans du HTML brut, pour la découverte réseau. `href` simple ou quoté.
LIEN_HTML = re.compile(r"""href\s*=\s*["']?([^"'>\s]+?\.pdf)["'>\s]""", re.I)

# En dessous, on ne rattache pas : deux règlements d'un même département
# partagent assez de formules pour se ressembler vaguement, et un faux sidecar
# ferait diffier la veille contre le mauvais document pour toujours.
SEUIL_DEFAUT = 0.75
TIMEOUT_DEFAUT = 30.0
REVIEWS_DIR = Path("data/reviews")


@dataclass
class Rattachement:
    """Ce qu'on a pu conclure pour un PDF archivé."""

    pdf: Path
    url: str | None = None
    preuve: str | None = None
    score: float = 0.0
    candidates_testees: int = 0
    echecs: list[str] = field(default_factory=list)

    @property
    def resolu(self) -> bool:
        return self.url is not None


def _normalise(texte: str) -> str:
    """Texte comparable : casse et blancs écrasés.

    `pdftotext` ne rend pas deux fois exactement la même chose selon la version
    et l'encodage des polices ; sans cet écrasement le score s'effondre sur des
    documents pourtant identiques.
    """
    return re.sub(r"\s+", " ", texte).strip().lower()


def _similarite(a: str, b: str) -> float:
    """Proximité de deux textes de PDF, bornée en coût.

    `SequenceMatcher` est quadratique : sur deux règlements de 200 000
    caractères il partirait en minutes. On compare un préfixe généreux, ce qui
    suffit à distinguer « même document » de « autre document » — deux
    règlements différents divergent dès leur titre.
    """
    limite = 40_000
    return SequenceMatcher(None, a[:limite], b[:limite]).quick_ratio()


def pdfs_sans_sidecar(aide: Aide) -> list[Path]:
    directory = SOURCES_DIR / aide.slug
    if not directory.is_dir():
        return []
    return sorted(
        p for p in directory.glob("*.pdf") if not p.with_name(p.name + ".meta.yaml").exists()
    )


def candidates_hors_ligne(aide: Aide) -> list[str]:
    """URL de PDF déductibles sans réseau, dans l'ordre de confiance."""
    urls: list[str] = []
    officielle = aide.source.url_officielle or ""
    if officielle.lower().endswith(".pdf"):
        urls.append(officielle)
    directory = SOURCES_DIR / aide.slug
    if directory.is_dir():
        for md in sorted(directory.glob("*.md")):
            meta, body = parse_front_matter(md.read_text(encoding="utf-8"))
            base = meta.get("url") or officielle
            if not base:
                continue
            for lien in LIEN_MD.findall(body):
                urls.append(urljoin(base, lien))
    # Dédoublonnage en préservant l'ordre : la première occurrence porte la
    # meilleure confiance.
    return list(dict.fromkeys(urls))


def _get(client: httpx.Client, url: str) -> httpx.Response | None:
    """GET franchissant WAF et shield. None si la page reste inaccessible.

    Point de sortie réseau UNIQUE du script : la découverte des liens et le
    téléchargement des candidates doivent franchir les mêmes obstacles. Câbler
    le contournement d'un seul côté fait échouer la découverte en silence.
    """
    try:
        resp = client.get(url)
        if resp.status_code == 403:
            resp = client.get(url, headers=HEADERS_NAVIGATEUR)
        if (defi := resoudre_shield(resp.content)) is not None:
            nom, valeur = defi
            client.cookies.set(nom, valeur, domain=urlsplit(str(resp.url)).netloc)
            resp = client.get(url, headers=HEADERS_NAVIGATEUR)
    except httpx.HTTPError:
        return None
    return resp if resp.is_success else None


def candidates_reseau(aide: Aide, client: httpx.Client) -> list[str]:
    """Liens PDF de la page officielle vivante. Silencieux en cas d'échec."""
    officielle = aide.source.url_officielle
    if not officielle or officielle.lower().endswith(".pdf"):
        return []
    resp = _get(client, officielle)
    if resp is None:
        return []
    return list(
        dict.fromkeys(urljoin(str(resp.url), lien) for lien in LIEN_HTML.findall(resp.text))
    )


def telecharger(url: str, client: httpx.Client) -> bytes | None:
    resp = _get(client, url)
    if resp is None:
        return None
    # Une page d'erreur HTML rendue en 200 n'est pas un PDF : sans ce garde-fou
    # on comparerait du HTML au texte d'un règlement.
    if not resp.content.startswith(b"%PDF"):
        return None
    return resp.content


def rattacher(
    pdf: Path,
    urls: list[str],
    client: httpx.Client,
    *,
    seuil: float,
    cache: dict[str, bytes | None],
    scratch: Path,
) -> Rattachement:
    r = Rattachement(pdf=pdf)
    sha_archive = hashlib.sha256(pdf.read_bytes()).hexdigest()
    texte_archive: str | None = None

    for url in urls:
        if url not in cache:
            cache[url] = telecharger(url, client)
        contenu = cache[url]
        if contenu is None:
            r.echecs.append(f"{url} (injoignable ou non-PDF)")
            continue
        r.candidates_testees += 1

        if hashlib.sha256(contenu).hexdigest() == sha_archive:
            r.url, r.preuve, r.score = url, "sha", 1.0
            return r

        # Comparaison texte : `pdf_to_text` prend un chemin, d'où le fichier
        # temporaire. Le PDF archivé n'est extrait qu'une fois.
        if texte_archive is None:
            texte_archive = _normalise(pdf_to_text(pdf) or "")
        if not texte_archive:
            r.echecs.append(f"{url} (PDF archivé illisible, comparaison impossible)")
            continue
        tmp = scratch / "candidat.pdf"
        tmp.write_bytes(contenu)
        texte_frais = _normalise(pdf_to_text(tmp) or "")
        tmp.unlink(missing_ok=True)
        if not texte_frais:
            r.echecs.append(f"{url} (candidat illisible)")
            continue
        score = _similarite(texte_archive, texte_frais)
        if score > r.score:
            r.score = score
            if score >= seuil:
                r.url, r.preuve = url, f"texte-{score:.2f}"
    if r.url is None and r.score:
        r.echecs.append(f"meilleur score {r.score:.2f} < seuil {seuil:.2f}")
    return r


def ecrire_sidecar(r: Rattachement, *, dry_run: bool) -> Path:
    sidecar = r.pdf.with_name(r.pdf.name + ".meta.yaml")
    meta = {
        # Le sha du PDF ARCHIVÉ : c'est la baseline de la veille. Y mettre celui
        # du téléchargement masquerait une modification déjà survenue.
        "sha256": hashlib.sha256(r.pdf.read_bytes()).hexdigest(),
        "url": r.url,
        # Provenance reconstituée, pas constatée : `fetched_at` daterait un
        # téléchargement qui n'a jamais eu lieu à cette date. On garde la trace
        # de la reconstitution et de sa preuve pour un audit ultérieur.
        "backfilled_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "match": r.preuve,
    }
    if not dry_run:
        sidecar.write_text(
            yaml.safe_dump(meta, allow_unicode=True, sort_keys=True), encoding="utf-8"
        )
    return sidecar


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="backfill_pdf_sidecars.py",
        description="Reconstitue la provenance des PDF archivés sans sidecar.",
    )
    p.add_argument("slugs", nargs="*", help="aides à traiter (défaut : toutes)")
    p.add_argument("--dry-run", action="store_true", help="ne rien écrire")
    p.add_argument(
        "--offline",
        action="store_true",
        help="candidates locales seulement — n'établit aucune preuve, sert à cadrer",
    )
    p.add_argument(
        "--url",
        action="append",
        default=[],
        metavar="URL",
        help="candidate supplémentaire, retrouvée à la main (répétable). Essayée AVANT "
        "les candidates déduites, et soumise à la même confrontation : c'est le PDF "
        "archivé qui tranche, pas l'intention de qui la propose.",
    )
    p.add_argument("--limit", type=int, help="ne traiter que les N premières aides")
    p.add_argument("--seuil", type=float, default=SEUIL_DEFAUT)
    p.add_argument("--timeout", type=float, default=TIMEOUT_DEFAUT)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    # `--url` désigne le PDF d'UNE aide. Étalée sur tout le parc, la même URL
    # serait confrontée à 106 PDF : au mieux du bruit réseau, au pire un
    # rattachement fortuit sur un document voisin.
    if args.url and len(args.slugs) != 1:
        print("ERREUR : --url exige exactement un slug.", file=sys.stderr)
        return 1
    if args.slugs:
        paths = [AIDES_DIR / f"{s}.yaml" for s in args.slugs]
        if manquants := [p.stem for p in paths if not p.exists()]:
            print(f"ERREUR : YAML introuvable pour : {', '.join(manquants)}", file=sys.stderr)
            return 1
    else:
        paths = sorted(AIDES_DIR.glob("*.yaml"))

    travail: list[tuple[Aide, list[Path]]] = []
    for p in paths:
        try:
            aide = load_aide(p)
        except Exception as exc:
            print(f"ERREUR : {p.name} illisible — {exc}", file=sys.stderr)
            return 1
        if pdfs := pdfs_sans_sidecar(aide):
            travail.append((aide, pdfs))
    if args.limit:
        travail = travail[: args.limit]

    total_pdf = sum(len(pdfs) for _, pdfs in travail)
    print("=" * 70)
    print(f"BACKFILL DES SIDECARS PDF — {len(travail)} aide(s), {total_pdf} PDF")
    if args.offline:
        print("Mode hors-ligne : candidates listées, aucune preuve établie.")
    if args.dry_run:
        print("À blanc : aucun sidecar ne sera écrit.")
    print("=" * 70)

    scratch = Path(".backfill-tmp")
    scratch.mkdir(exist_ok=True)
    resolus: list[Rattachement] = []
    restants: list[tuple[str, Rattachement]] = []
    try:
        with httpx.Client(
            headers={"User-Agent": UA}, follow_redirects=True, timeout=args.timeout
        ) as client:
            for aide, pdfs in travail:
                urls = list(dict.fromkeys([*args.url, *candidates_hors_ligne(aide)]))
                if args.offline:
                    for pdf in pdfs:
                        etat = f"{len(urls)} candidate(s) locale(s)" if urls else "aucune candidate"
                        print(f"  ? {aide.slug:<46} {pdf.name:<34} {etat}")
                    continue
                if not urls:
                    urls = candidates_reseau(aide, client)
                elif args.url:
                    # Une URL fournie à la main ne doit pas priver l'aide de la
                    # découverte réseau : si elle se révèle fausse, les liens de
                    # la page vivante restent la meilleure chance suivante.
                    urls += [u for u in candidates_reseau(aide, client) if u not in urls]
                cache: dict[str, bytes | None] = {}
                for pdf in pdfs:
                    r = rattacher(pdf, urls, client, seuil=args.seuil, cache=cache, scratch=scratch)
                    if r.resolu:
                        ecrire_sidecar(r, dry_run=args.dry_run)
                        resolus.append(r)
                        print(f"  + {aide.slug:<46} {pdf.name:<34} {r.preuve}")
                    else:
                        restants.append((aide.slug, r))
                        motif = r.echecs[0] if r.echecs else "aucune candidate"
                        print(f"  - {aide.slug:<46} {pdf.name:<34} {motif}")
    finally:
        for f in scratch.iterdir():
            f.unlink(missing_ok=True)
        scratch.rmdir()

    if args.offline:
        return 0

    print()
    print("=" * 70)
    print(f"RÉCAP — {len(resolus)}/{total_pdf} PDF rattachés")
    print("=" * 70)
    par_preuve: dict[str, int] = {}
    for r in resolus:
        cle = (r.preuve or "").split("-")[0]
        par_preuve[cle] = par_preuve.get(cle, 0) + 1
    for cle, n in sorted(par_preuve.items()):
        print(f"  {cle:<10} {n}")
    if restants:
        print(f"  non rattachés : {len(restants)} — à re-snapshoter à la main :")
        for slug, r in restants[:40]:
            print(f"    {slug:<46} {r.pdf.name}")

    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    jour = datetime.now(UTC).date().isoformat()
    rapport = REVIEWS_DIR / f"{jour}-backfill-sidecars.md"
    lignes = [
        f"# Backfill des sidecars PDF — {jour}",
        "",
        f"{len(resolus)}/{total_pdf} PDF rattachés à une URL"
        + (" (à blanc, rien n'a été écrit)." if args.dry_run else "."),
        "",
        "## Rattachés",
        "",
        "| PDF | preuve | URL |",
        "|---|---|---|",
    ]
    lignes += [f"| {r.pdf.parent.name}/{r.pdf.name} | `{r.preuve}` | {r.url} |" for r in resolus]
    if restants:
        lignes += [
            "",
            "## Non rattachés",
            "",
            "Aucune URL candidate n'a résisté au contrôle. Ces PDF restent hors "
            "du périmètre de surveillance : les citations qu'ils justifient "
            "continueront de sortir en « non recontrôlable ». Les re-snapshoter "
            "avec `snapshot_source.py <slug> <url-du-pdf>` est le seul remède.",
            "",
            "| PDF | motif |",
            "|---|---|",
        ]
        lignes += [
            f"| {r.pdf.parent.name}/{r.pdf.name} | {'; '.join(r.echecs) or 'aucune candidate'} |"
            for _, r in restants
        ]
    rapport.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print(f"\nrapport : {rapport}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
