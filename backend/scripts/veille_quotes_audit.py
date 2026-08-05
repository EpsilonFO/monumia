"""
Audit de la dette de quotes : chaque citation est-elle retrouvable dans les
snapshots déjà archivés de son aide ?

ZÉRO réseau, zéro LLM — on ne compare que des fichiers du dépôt. C'est le
calibrage de `veille_text.normalize()` avant de brancher la veille : tant que
des quotes authentiques ressortent « absentes » à cause d'une apostrophe courbe
ou d'un accent perdu par pdftotext, le triage escaladerait des dizaines d'aides
à tort. Une fois la normalisation calée, le résidu est la VRAIE dette de
quotes — citations obsolètes, tronquées, ou justifiées par une source qui n'a
jamais été archivée — et c'est une donnée d'entrée du travail de veille, pas un
bug.

Le chiffre à surveiller est « retrouvées seulement après normalisation » : c'est
la mesure de ce que cette normalisation rachète.

Référence au 2026-08-05, sur 142 aides et 2 019 quotes : 94 % des 1 848 quotes
vérifiables sont retrouvées, dont 203 grâce à la normalisation seule et 47 par
retouche (élision, ponctuation de clôture). Restent 99 quotes de dette réelle
sur 56 aides, et 171 quotes hors portée (7 aides sans snapshot exploitable,
6 PDF de règlement qui ne s'extraient pas). Un écart marqué à ce point de
référence signale une régression de la normalisation, pas une évolution des
sources : ce script ne touche pas au réseau.

Run :
    cd backend && uv run python scripts/veille_quotes_audit.py [slug ...] [--details=N]
"""

import subprocess
import sys
from collections import Counter
from functools import cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aides_schema import AIDES_DIR, DATA_DIR, Aide, load_aide

sys.path.insert(0, str(Path(__file__).resolve().parent))

from veille_text import (
    QuoteMatch,
    find_quote_in_any,
    flatten_markdown_links,
    strip_front_matter,
)

SOURCES_DIR = DATA_DIR / "sources"

# En-dessous de ce ratio de préfixe commun, une quote introuvable est réputée
# avoir disparu de la source ; au-dessus, elle y est encore mais divergente
# (chiffre modifié, phrase remaniée, citation tronquée à la saisie). Les deux
# cas appellent des actions opposées — supprimer la condition vs corriger la
# citation — d'où la séparation dans le rapport.
PREFIX_DIVERGENCE = 0.30

# En-dessous de ce nombre de caractères extraits, un PDF de règlement est réputé
# ILLISIBLE : c'est un scan (ou un export d'images) dont `pdftotext` ne tire que
# les en-têtes. Mesuré : 7 PDF du dépôt sur 109 sont dans ce cas, dont 3 rendent
# zéro caractère, et ils portent à eux seuls une centaine de quotes.
#
# Les compter comme baseline serait deux fois trompeur : leurs quotes seraient
# imputées à la « dette » alors qu'elles n'ont jamais été vérifiables, et leurs
# maigres en-têtes produiraient des diagnostics de préfixe qui n'ont aucun sens.
# On les isole donc dans une catégorie propre, auditable.
PDF_MIN_TEXT = 1000


@cache
def pdf_to_text(path: Path) -> str | None:
    """Texte d'un PDF via `pdftotext`. None si l'outil ou l'extraction manque.

    Mode par défaut (pas `-layout`) : l'ordre de lecture rend mieux la prose
    continue des règlements, et l'effondrement des blancs de `normalize()` rend
    de toute façon l'indentation physique non signifiante.
    """
    try:
        out = subprocess.run(
            ["pdftotext", str(path), "-"], capture_output=True, timeout=60, check=False
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return out.stdout.decode("utf-8", errors="replace") if out.returncode == 0 else None


def load_baselines(slug: str) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Documents archivés d'une aide, et la liste de ses PDF illisibles.

    TOUS les snapshots du dossier sont chargés, pas seulement `source.snapshot` :
    une aide a souvent une page d'appel à projets, un règlement PDF et un
    formulaire, et une quote n'est justifiée que par l'un d'eux.
    """
    directory = SOURCES_DIR / slug
    if not directory.is_dir():
        return [], []
    docs: list[tuple[str, str, str]] = []
    illisibles: list[str] = []
    for path in sorted(directory.iterdir()):
        suffix = path.suffix.lower()
        if suffix == ".md":
            # Liens aplatis : les quotes ont été saisies depuis le rendu visuel
            # de la page, où l'URL d'une ancre en milieu de phrase n'apparaît pas.
            body = strip_front_matter(path.read_text(encoding="utf-8"))
            docs.append((path.name, flatten_markdown_links(body), "text"))
        elif suffix == ".pdf":
            text = pdf_to_text(path)
            if text is None:
                illisibles.append(f"{path.name} (pdftotext indisponible ou en échec)")
            elif len(text.strip()) < PDF_MIN_TEXT:
                illisibles.append(f"{path.name} ({len(text.strip())} car. extraits)")
            else:
                docs.append((path.name, text, "pdf"))
    return docs, illisibles


def audit_aide(aide: Aide) -> tuple[list[tuple[str, QuoteMatch, str | None]], list[str], bool]:
    """Retourne [(id de condition, correspondance, document)], les PDF illisibles
    et la présence d'au moins une baseline exploitable."""
    baselines, illisibles = load_baselines(aide.slug)
    results = []
    for cond in aide.conditions:
        if not cond.quote:
            continue
        name, match = find_quote_in_any(cond.quote, baselines)  # type: ignore[arg-type]
        results.append((cond.id, match, name))
    return results, illisibles, bool(baselines)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    details = 20
    for arg in sys.argv[1:]:
        if arg.startswith("--details="):
            details = int(arg.split("=", 1)[1])

    paths = (
        [AIDES_DIR / f"{slug}.yaml" for slug in args] if args else sorted(AIDES_DIR.glob("*.yaml"))
    )

    statuses: Counter[str] = Counter()
    sans_quote = 0
    reconstitutions: Counter[str] = Counter()
    aides_sans_baseline: list[tuple[str, list[str]]] = []
    pdf_illisibles: list[tuple[str, str]] = []
    # (ratio de préfixe, slug, id de condition, quote) — trié pour l'affichage.
    residu: list[tuple[float, str, str, str]] = []
    par_aide: Counter[str] = Counter()
    n_aides = 0

    for path in paths:
        if not path.exists():
            print(f"✗ aide inconnue : {path.stem}")
            return 1
        aide = load_aide(path)
        n_aides += 1
        results, illisibles, has_baseline = audit_aide(aide)
        sans_quote += sum(1 for c in aide.conditions if not c.quote)
        pdf_illisibles.extend((aide.slug, nom) for nom in illisibles)
        if not has_baseline:
            aides_sans_baseline.append((aide.slug, illisibles))
            statuses["non_verifiable"] += len(results)
            continue
        for cond_id, match, _doc in results:
            if match.reconstitution:
                reconstitutions[match.reconstitution] += 1
            if match.found:
                statuses[match.status] += 1
            elif illisibles:
                # L'aide garde une baseline lisible (sa page HTML), mais son
                # règlement PDF ne s'extrait pas : une quote introuvable ici
                # s'explique d'abord par l'extraction, pas par la citation.
                # L'imputer à la dette accuserait le travail d'ingestion à tort.
                statuses["absente_pdf_illisible"] += 1
            else:
                statuses["absente"] += 1
                par_aide[aide.slug] += 1
                quote = next(c.quote for c in aide.conditions if c.id == cond_id) or ""
                residu.append((match.prefix_ratio, aide.slug, cond_id, quote))

    verifiables = statuses["exacte"] + statuses["degradee"] + statuses["baseline_pdf"]
    total = verifiables + statuses["absente"]
    hors_portee = statuses["non_verifiable"] + statuses["absente_pdf_illisible"]
    print(f"aides   : {n_aides}")
    print(f"quotes  : {total + hors_portee} au total, {sans_quote} condition(s) sans quote")

    if total:
        print(
            f"\nvérifiables : {total} — retrouvées {verifiables} ({verifiables * 100 // total} %)"
        )
        print(f"  exacte        {statuses['exacte']:>4}  verbatim, source inchangée")
        print(f"  degradee      {statuses['degradee']:>4}  ← rachetées par la normalisation")
        print(f"  baseline_pdf  {statuses['baseline_pdf']:>4}  justifiées par un PDF")
        print(f"  absente       {statuses['absente']:>4}  ← dette réelle")
        total_recon = sum(reconstitutions.values())
        print(f"  dont {total_recon} reconstituée(s) — la quote a dû être retouchée pour matcher :")
        print(
            f"    élision (« ... », « [...] »)   {reconstitutions['elision']:>4}\n"
            f"    ponctuation de clôture        {reconstitutions['ponctuation_finale']:>4}"
        )

    print(f"\nhors portée de la vérification : {hors_portee} quote(s)")
    print(f"  {statuses['non_verifiable']:>4}  aide sans aucun snapshot exploitable")
    print(f"  {statuses['absente_pdf_illisible']:>4}  aide dont le règlement PDF ne s'extrait pas")

    if aides_sans_baseline:
        print(f"\naides sans aucun snapshot exploitable ({len(aides_sans_baseline)}) :")
        for slug, illisibles in aides_sans_baseline:
            motif = f" — PDF illisible : {', '.join(illisibles)}" if illisibles else ""
            print(f"  {slug}{motif}")

    if pdf_illisibles:
        print(
            f"\nPDF illisibles ({len(pdf_illisibles)}, < {PDF_MIN_TEXT} car. extraits) — "
            "scans probables, à re-snapshoter depuis la page HTML ou à océriser :"
        )
        for slug, nom in pdf_illisibles:
            print(f"  {slug}/{nom}")

    if residu:
        divergentes = [r for r in residu if r[0] >= PREFIX_DIVERGENCE]
        disparues = [r for r in residu if r[0] < PREFIX_DIVERGENCE]
        print(
            f"\ndette réelle : {len(residu)} quote(s) sur {len(par_aide)} aide(s) — "
            f"{len(divergentes)} divergente(s), {len(disparues)} introuvable(s)"
        )
        print("  aides les plus endettées :")
        for slug, n in par_aide.most_common(10):
            print(f"    {slug:<44} {n}")
        if details:
            print(
                f"\n  détail ({min(details, len(residu))}/{len(residu)}, "
                "les plus divergentes d'abord — préfixe = part de la quote encore présente) :"
            )
            for ratio, slug, cond_id, quote in sorted(residu, reverse=True)[:details]:
                extrait = " ".join(quote.split())[:100]
                print(f"    [{ratio:>5.0%}] {slug} / {cond_id}")
                print(
                    f"            « {extrait}… »"
                    if len(quote) > 100
                    else f"            « {extrait} »"
                )

    # Diagnostic : jamais bloquant. La dette de quotes est un état de fait du
    # dépôt, pas une régression à empêcher de merger.
    return 0


if __name__ == "__main__":
    sys.exit(main())
