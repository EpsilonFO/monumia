"""
Veille des aides : re-visiter les sources officielles et mettre à jour ce qui a bougé.

    cd backend && uv run python scripts/veille_aides.py --report-only
    cd backend && uv run python scripts/veille_aides.py --limit 10 --dry-run
    cd backend && uv run python scripts/veille_aides.py --limit 10

Étages A (collecte) et B (analyse) : entièrement déterministes, zéro LLM. Ils
produisent un manifeste (`data/veille-state.yaml`) et un rapport
(`data/reviews/<date>-veille.md`).

Étage C : un appel structuré par aide classée MAJ_LLM, plafonné par `--max-llm`.
C'est le SEUL étage qui écrit dans `data/aides/` et `data/sources/`, et il ne le
fait qu'après une chaîne de validation qui vérifie chaque citation dans la page
fraîchement téléchargée. Aucun modèle mesuré n'atteint zéro faux changement : le
`git diff` doit être relu avant commit, c'est la dernière barrière.

`--report-only` s'arrête après l'étage B ; `--dry-run` va jusqu'au bout mais
n'écrit aucun fichier d'aide.

Codes de sortie : 0 terminé ; 1 erreur fatale ; 2 au moins une escalade, une
erreur HTTP à retenter ou une mise à jour en échec.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aides_schema import AIDES_DIR, DATA_DIR, Aide, load_aide

sys.path.insert(0, str(Path(__file__).resolve().parent))

from urllib.parse import urlsplit

from veille_analyze import (
    CHROME_MIN_URLS,
    STATUTS,
    AideAnalysis,
    analyze_all,
    hotes_affames,
    resume_diff,
)
from veille_collect import DEFAULT_CONCURRENCY, DEFAULT_TIMEOUT, collect
from veille_journal import Journal, cellule, milliers, tokens_compacts
from veille_llm import MODELE_DEFAUT, resoudre_modele
from veille_update import MAX_LLM_DEFAUT, MajResult, mettre_a_jour

MANIFEST_PATH = DATA_DIR / "veille-state.yaml"
REVIEWS_DIR = DATA_DIR / "reviews"
LOG_DIR = REVIEWS_DIR / "logs"

SYMBOLES = {
    "OK": "✓",
    "MAJ_LLM": "~",
    "ESCALADE_INGESTION": "✗",
    "ERREUR_HTTP": "!",
    "SANS_BASELINE": "?",
    "DATE_PERIMEE_SOURCE_INCHANGEE": "⏱",
}

# Statut adossé à une vérification partielle des citations. Volontairement
# distinct des symboles de statut : ce n'est pas un statut, c'est une réserve
# sur la portée de celui qui est affiché.
SYMBOLE_COUVERTURE = "○"


def soeurs_du_parc(hote: str, deja: set[str]) -> list[str]:
    """Slugs du parc dont l'URL officielle est sur cet hôte, hors ceux du run.

    Relit les YAML du dossier : les aides sœurs sont par définition celles que
    le run N'A PAS chargées, donc introuvables dans son propre périmètre.
    """
    trouves: list[str] = []
    for chemin in sorted(AIDES_DIR.glob("*.yaml")):
        if chemin.stem in deja:
            continue
        try:
            aide = load_aide(chemin)
        except Exception:
            # Une fiche illisible ne doit pas faire échouer un avertissement.
            continue
        url = aide.source.url_officielle or ""
        if url and urlsplit(url).netloc.lower() == hote:
            trouves.append(aide.slug)
    return trouves


def alerter_chrome_affame(analyses: dict[str, AideAnalysis], collects: dict, log: Journal) -> None:
    """Prévient quand le périmètre du run rend un `MAJ_LLM` peu fiable.

    Ne dit rien quand aucune aide d'un hôte affamé n'a bougé : la famine ne
    produit pas de faux `OK`, seulement de faux `MAJ_LLM`.
    """
    affames = hotes_affames(collects)
    if not affames:
        return
    suspects: dict[str, list[str]] = {}
    for slug, an in analyses.items():
        if an.statut not in ("MAJ_LLM", "ESCALADE_INGESTION"):
            continue
        for u in an.urls:
            if u.murl.host in affames and u.a_change:
                suspects.setdefault(u.murl.host, []).append(slug)
                break
    if not suspects:
        return
    log("")
    log("  ⚠ périmètre trop étroit pour distinguer le gabarit du contenu :")
    log(f"    le détecteur de chrome exige {CHROME_MIN_URLS} URL d'un même hôte ; en dessous, un")
    log("    menu de site peut passer pour un changement de règlement.")
    for hote, slugs in sorted(suspects.items()):
        log(f"    {hote} — {affames[hote]} URL vue(s), {len(slugs)} aide(s) concernée(s)")
        soeurs = soeurs_du_parc(hote, set(analyses))
        if soeurs:
            log(
                f"      relancer avec ses sœurs pour trancher :\n"
                f"      uv run python scripts/veille_aides.py "
                f"{' '.join(sorted(set(slugs)) + soeurs)} --report-only"
            )


# ---------------------------------------------------------------------------
# Manifeste
# ---------------------------------------------------------------------------


def traiter_acquittements(
    analyses: dict[str, AideAnalysis], manifest: dict, nouveaux: Sequence[str] = ()
) -> list[str]:
    """Fait taire les échéances dépassées qu'un humain a déjà arbitrées.

    `DATE_PERIMEE_SOURCE_INCHANGEE` ressortait à l'identique à chaque run — 24
    aides au 2026-09-01 — sans aucun moyen de dire « vu, c'est une annonce sans
    année, on attend que la source bouge ». L'acquittement est clé par la date
    limite : si la fiche ou la source change de date, l'alerte revient. Il vit
    dans le manifeste (`ack`), reporté d'un run à l'autre comme `maj` et `audit`.

    `nouveaux` : slugs à acquitter lors de CE run (`--acquitter`). Retourne les
    slugs effectivement acquittés aujourd'hui.
    """
    poses: list[str] = []
    for slug in nouveaux:
        an = analyses.get(slug)
        if an and an.statut == "DATE_PERIMEE_SOURCE_INCHANGEE" and an.date_limite_perimee:
            entree = manifest.setdefault(slug, {})
            entree["ack"] = {"date_perimee": an.date_limite_perimee.isoformat()}
            poses.append(slug)
    for slug, an in analyses.items():
        ack = (manifest.get(slug) or {}).get("ack") or {}
        if (
            an.statut == "DATE_PERIMEE_SOURCE_INCHANGEE"
            and an.date_limite_perimee
            and ack.get("date_perimee") == an.date_limite_perimee.isoformat()
        ):
            an.statut = "OK"
            an.raisons = [
                f"échéance dépassée ({an.date_limite_perimee}) acquittée, source inchangée"
            ]
    return poses


def load_manifest(path: Path = MANIFEST_PATH) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def anciennete(aide: Aide, manifest: dict) -> date:
    """Date de dernier contrôle, humain ou automatique. `date.min` si jamais vu.

    On prend le MAXIMUM des deux : une aide ré-ingérée à la main hier n'a pas
    besoin d'être re-visitée aujourd'hui parce que la veille ne l'a jamais vue.
    """
    entry = manifest.get(aide.slug) or {}
    checked = entry.get("checked_at")
    if isinstance(checked, str):
        checked = date.fromisoformat(checked)
    return max(aide.source.verified_at or date.min, checked or date.min)


def update_manifest(
    manifest: dict,
    analyses: dict[str, AideAnalysis],
    majs: dict[str, MajResult],
    today: date,
) -> dict:
    """Fusionne les résultats du run dans le manifeste existant.

    Les aides non traitées conservent leur entrée : un run partiel
    (`--limit`, une liste de slugs) ne doit pas effacer l'historique du reste.
    """
    merged = dict(manifest)
    for slug, an in analyses.items():
        # Les URL sont une LISTE d'enregistrements et non un dictionnaire indexé
        # par URL : au-delà de 128 caractères, une clé YAML bascule dans la forme
        # explicite « ? clé / : valeur », et nos URL dépassent régulièrement.
        # Le fichier est committé et relu à la main — sa lisibilité prime sur
        # l'élégance de l'indexation. Tri par URL pour un diff stable.
        urls = sorted(
            (
                {
                    "url": u.murl.url,
                    **({"label": u.murl.label} if u.murl.label else {}),
                    "sha256": u.result.sha256,
                }
                for u in an.urls
                if u.result and u.result.ok and u.result.sha256
            ),
            key=lambda e: e["url"],
        )
        ancienne_entree = manifest.get(slug) or {}
        entree: dict = {"status": an.statut.lower()}
        if an.statut == "ERREUR_HTTP":
            # Rien n'a été vérifié : dater le contrôle d'aujourd'hui enverrait
            # l'aide en fin de file d'ancienneté, donc hors d'un `--limit` au
            # passage suivant — l'inverse de « à retenter ». Elle garde sa date
            # précédente, ou aucune si elle n'a jamais été vue.
            if ancienne := ancienne_entree.get("checked_at"):
                entree["checked_at"] = ancienne
        else:
            entree["checked_at"] = today.isoformat()
        if urls:
            entree["urls"] = urls
        # Trace de la dernière retouche automatique. Conservée d'un run à
        # l'autre : c'est ce qui permet de répondre « quand la veille a-t-elle
        # touché cette fiche, et à quoi » sans fouiller l'historique git.
        maj = majs.get(slug)
        ancienne_maj = ancienne_entree.get("maj")
        if maj is not None and maj.etat == "applique":
            entree["maj"] = {
                "date": today.isoformat(),
                "modele": maj.modele,
                "champs": maj.champs,
            }
        elif ancienne_maj:
            entree["maj"] = ancienne_maj
        # L'audit d'exhaustivité (`veille_audit.py`) écrit sa propre clé dans la
        # MÊME entrée. La veille reconstruit la sienne de zéro à chaque passage :
        # sans ce report explicite, un run de veille effacerait l'historique
        # d'audit et le ferait tout re-payer au passage suivant.
        if audit := ancienne_entree.get("audit"):
            entree["audit"] = audit
        # Acquittement d'échéance (voir `traiter_acquittements`) : même report.
        if ack := ancienne_entree.get("ack"):
            entree["ack"] = ack
        merged[slug] = entree
    return merged


def write_manifest(manifest: dict, path: Path = MANIFEST_PATH) -> None:
    # `sort_keys` : le manifeste est committé, son ordre doit être stable d'un
    # run à l'autre sinon chaque passage produit un diff illisible.
    # `width` : au-delà de 80 colonnes, PyYAML bascule les clés longues dans la
    # forme explicite « ? clé / : valeur ». C'est du YAML valide, mais nos clés
    # SONT des URL longues, et le fichier deviendrait illisible en relecture.
    path.write_text(
        yaml.safe_dump(
            manifest,
            allow_unicode=True,
            sort_keys=True,
            default_flow_style=False,
            width=10**6,
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------


def _section_majs(majs: dict[str, MajResult], mode: str) -> list[str]:
    """Ce que l'étage C a produit : les diffs à relire, puis ce qui a échoué."""
    if not majs:
        return []
    appliquees = [m for m in majs.values() if m.etat == "applique"]
    echecs = [m for m in majs.values() if m.etat == "echec"]
    inchangees = [m for m in majs.values() if m.etat == "inchange"]
    cout = sum(m.cout_usd for m in majs.values())
    tok_in = sum(m.tokens_in for m in majs.values())
    tok_out = sum(m.tokens_out for m in majs.values())

    out = [
        "## Étage C",
        "",
        f"{len(majs)} aide(s) soumise(s) au modèle pour {cout:.3f} $ "
        f"({milliers(tok_in)} tokens en entrée, {milliers(tok_out)} en sortie) : "
        + f"{len(appliquees)} mise(s) à jour, {len(inchangees)} sans changement dans le "
        f"mandat, {len(echecs)} en échec.",
        "",
    ]
    if appliquees:
        if mode == "dry-run":
            out += [
                "> **À blanc** : rien n'a été écrit. Relancer sans `--dry-run` pour "
                "appliquer, puis relire le `git diff`.",
                "",
            ]
        else:
            out += [
                "> Ces fiches sont MODIFIÉES sur disque. Aucun modèle mesuré n'atteint "
                "zéro faux changement : relire chaque diff avant de committer.",
                "",
            ]
        out += [
            "| aide | champs touchés | résumé du modèle | snapshots ré-archivés |",
            "|---|---|---|---|",
        ]
        for m in sorted(appliquees, key=lambda m: m.slug):
            champs = ", ".join(f"`{c}`" for c in m.champs) or "—"
            snaps = ", ".join(m.snapshots) or "—"
            out.append(f"| {m.slug} | {champs} | {cellule(m.resume)} | {snaps} |")
        out += [
            "",
            "```",
            "git diff -- data/aides data/sources",
            "```",
            "",
        ]
    if rearchivees := [m for m in inchangees if m.snapshots]:
        out += [
            "### Pages ré-archivées sans retouche de fiche",
            "",
            "Le modèle a lu la page modifiée et n'a rien trouvé dans son mandat. La "
            "nouvelle version devient la baseline : sans ça, la même page repasserait "
            "au modèle à chaque run.",
            "",
            *(
                f"- **{m.slug}** — {', '.join(m.snapshots)} : {cellule(m.resume, 120)}"
                for m in sorted(rearchivees, key=lambda m: m.slug)
            ),
            "",
        ]
    if echecs:
        out += [
            "### Mises à jour en échec",
            "",
            "Le modèle a répondu mais la validation a refusé d'écrire. Rien n'a été "
            "modifié : c'est le comportement voulu, et l'aide reste à traiter.",
            "",
        ]
        for m in sorted(echecs, key=lambda m: m.slug):
            out.append(f"- **{m.slug}** ({m.etape_echec}) — {m.raison}")
            out += [f"  - {e}" for e in m.erreurs[:3]]
        out.append("")
    return out


def build_report(
    analyses: dict[str, AideAnalysis],
    today: date,
    duree_s: float,
    *,
    offline: bool = False,
    majs: dict[str, MajResult] | None = None,
    mode: str = "report-only",
) -> str:
    majs = majs or {}
    par_statut: dict[str, list[AideAnalysis]] = {s: [] for s in STATUTS}
    for an in analyses.values():
        par_statut[an.statut].append(an)

    portee = {
        "report-only": "Étages A+B uniquement : aucun YAML d'aide n'a été modifié.",
        "dry-run": "Étage C exécuté à blanc : les mises à jour ont été calculées et "
        "validées, aucun fichier n'a été écrit.",
        "complet": "Étage C exécuté : toute mise à jour listée plus bas a été ÉCRITE "
        "dans `data/aides/`. Relire le `git diff` avant de committer.",
    }[mode]
    out: list[str] = [
        f"# Veille des aides — {today.isoformat()}",
        "",
        f"{len(analyses)} aide(s) contrôlée(s) en {duree_s / 60:.1f} min. {portee}",
        "",
    ]
    if offline:
        # Sans cet avertissement, un `OK` de run hors-ligne se lirait « aucun
        # changement » alors qu'aucune source n'a été consultée.
        out += [
            "> **Run hors-ligne** : aucune source n'a été téléchargée. Les statuts "
            "`OK` ne signifient PAS « inchangé », seulement « rien à signaler sans "
            "réseau ». Seuls le périmètre de surveillance, les échéances et les "
            "baselines manquantes sont significatifs ici.",
            "",
        ]
    out += [
        "| statut | aides | signification |",
        "|---|---:|---|",
    ]
    legendes = {
        "ESCALADE_INGESTION": "ré-ingestion complète nécessaire",
        "MAJ_LLM": "changement circonscrit, candidat à la mise à jour assistée",
        "DATE_PERIMEE_SOURCE_INCHANGEE": "échéance passée mais source identique — arbitrage humain",
        "ERREUR_HTTP": "source injoignable, à retenter",
        "SANS_BASELINE": "rien à quoi comparer",
        "OK": "aucun changement détecté",
    }
    for statut in STATUTS:
        out.append(f"| `{statut}` | {len(par_statut[statut])} | {legendes[statut]} |")
    out.append("")

    out += _section_majs(majs, mode)

    if escalades := par_statut["ESCALADE_INGESTION"]:
        out += ["## Escalades — ré-ingestion complète", ""]
        for an in escalades:
            out.append(f"- **{an.slug}** — {' ; '.join(an.raisons)}")
        slugs = " ".join(an.slug for an in escalades)
        out += [
            "",
            "Commande prête :",
            "",
            "```",
            f"uv run python scripts/ingest_aides_batch.py {slugs}",
            "```",
            "",
        ]

    if circonscrits := par_statut["MAJ_LLM"]:
        out += [
            "## Changements circonscrits",
            "",
            "Ce que l'étage B a vu bouger, page par page. Une aide traitée par "
            "l'étage C porte le verdict du modèle sous son diff ; les autres "
            "attendent un passage sans `--max-llm` atteint.",
            "",
        ]
        for an in circonscrits:
            out.append(f"### {an.slug}")
            out.append("")
            for raison in an.raisons:
                out.append(f"- {raison}")
            if (maj := majs.get(an.slug)) is not None:
                out.append(f"- **étage C ({maj.modele})** — {maj.etat} : {maj.raison}")
            elif mode != "report-only":
                out.append("- **étage C** — non traitée (plafond `--max-llm` atteint)")
            if diff := resume_diff(an):
                out += ["", "```diff", diff, "```"]
            out.append("")

    if dates := par_statut["DATE_PERIMEE_SOURCE_INCHANGEE"]:
        out += [
            "## Échéances passées, source inchangée",
            "",
            "La source annonce souvent une période sans année (« du 1er septembre au "
            "31 octobre »). Aucun automatisme ne peut trancher : à confirmer à la main.",
            "",
            "| aide | date limite | ancienneté |",
            "|---|---|---:|",
        ]
        for an in sorted(dates, key=lambda a: a.date_limite_perimee or date.min):
            jours = (today - an.date_limite_perimee).days if an.date_limite_perimee else 0
            out.append(f"| {an.slug} | {an.date_limite_perimee} | {jours} j |")
        out.append("")

    if erreurs := par_statut["ERREUR_HTTP"]:
        out += ["## Sources injoignables — à retenter", ""]
        for an in erreurs:
            out.append(f"- **{an.slug}** — {' ; '.join(an.raisons)}")
        out += [
            "",
            "```",
            f"uv run python scripts/veille_aides.py {' '.join(a.slug for a in erreurs)}",
            "```",
            "",
        ]

    if sans := par_statut["SANS_BASELINE"]:
        out += [
            "## Sans baseline",
            "",
            "Aucun snapshot exploitable : la veille ne peut rien détecter tant que "
            "l'aide n'a pas été ingérée avec provenance.",
            "",
        ]
        for an in sans:
            out.append(f"- **{an.slug}** — {' ; '.join(an.raisons)}")
        out.append("")

    # Signaux transverses : ils ne déclenchent aucune action automatique mais
    # décrivent l'état de la matière première.
    # Même attribution que `veille_quotes_audit.py`, sinon les deux outils
    # annonceraient deux chiffres différents pour « la dette de quotes ». Une
    # aide dont le règlement PDF ne s'extrait pas n'a pas de dette : elle a un
    # problème d'extraction, comptabilisé plus bas.
    dette = [
        (an.slug, len(an.dette_quotes))
        for an in analyses.values()
        if an.dette_quotes and not an.pdf_illisibles and an.statut != "SANS_BASELINE"
    ]
    non_recontrolables = sum(len(an.non_recontrolables) for an in analyses.values())
    illisibles = [(an.slug, p) for an in analyses.values() for p in an.pdf_illisibles]
    if dette or illisibles or non_recontrolables:
        out += ["## Qualité des preuves (aucune action automatique)", ""]
        if dette:
            total = sum(n for _, n in dette)
            out.append(
                f"- **{total} citation(s) déjà introuvables dans leur propre baseline**, "
                f"sur {len(dette)} aide(s) — dette préexistante, jamais escaladée par la "
                "veille. Décompte limité aux aides que CE run a pu contrôler ; le total "
                "du parc, PDF illisibles et aides non surveillables compris, est donné par "
                "`uv run python scripts/veille_quotes_audit.py`."
            )
        if non_recontrolables:
            out.append(
                f"- **{non_recontrolables} citation(s) non recontrôlables** ce run : le "
                "document qui les justifie (souvent un PDF sans URL connue) n'a pas été "
                "re-téléchargé. Leur absence du contenu frais ne prouve rien."
            )
        if illisibles:
            out.append(f"- **{len(illisibles)} PDF illisible(s)** (scan probable) :")
            out += [f"  - {slug} : {p}" for slug, p in illisibles]
        out.append("")

    # Portée des statuts rassurants, aide par aide. Le décompte global de
    # citations non recontrôlables ci-dessus ne dit pas SUR QUELLES aides le
    # verdict est creux — or c'est la seule question qui compte pour décider
    # quoi relire à la main.
    creuses = sorted(
        (
            a
            for a in analyses.values()
            if a.statut in ("OK", "DATE_PERIMEE_SOURCE_INCHANGEE")
            and a.couverture_quotes[1]
            and a.couverture_quotes[0] < a.couverture_quotes[1]
        ),
        key=lambda a: (a.couverture_quotes[0] / a.couverture_quotes[1], a.slug),
    )
    if creuses:
        out += [
            "## Portée des statuts — couverture partielle des citations",
            "",
            "Ces aides n'ont **pas** vu leurs conditions revérifiées, ou seulement "
            "en partie : le document qui les justifie n'est pas dans le périmètre "
            "de surveillance. Le statut affiché ne porte que sur les pages "
            "re-téléchargées. Une couverture de `0/n` ne prouve rien du règlement.",
            "",
            "| aide | statut | citations contrôlées |",
            "|---|---|---:|",
        ]
        for an in creuses:
            n, tot = an.couverture_quotes
            marque = " ⚠" if n == 0 else ""
            out.append(f"| {an.slug} | `{an.statut}` | {n}/{tot}{marque} |")
        out.append("")

    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def run_stage_c(
    args: argparse.Namespace,
    aides: dict[str, Aide],
    analyses: dict[str, AideAnalysis],
    collects: dict,
    today: date,
    log: Journal,
) -> dict[str, MajResult]:
    """Soumet au modèle les aides retenues par l'étage B, dans l'ordre d'ancienneté.

    Séquentiel, et pas par lot : chaque fiche est écrite dès qu'elle est
    validée, donc une interruption laisse un état cohérent et relisable plutôt
    qu'un demi-lot en mémoire. Le facteur limitant est de toute façon la
    relecture humaine, pas la latence.
    """
    if args.report_only or args.offline:
        return {}
    # Itération sur `aides` et non sur `analyses` : c'est le seul dictionnaire
    # dont l'ordre porte l'ancienneté, et c'est lui qui décide qui passe sous
    # le plafond `--max-llm`.
    candidats = [s for s in aides if s in analyses and analyses[s].statut == "MAJ_LLM"]
    if not candidats:
        return {}

    spec = resoudre_modele(args.model)
    if not spec.cle_presente:
        log("")
        log(
            f"⚠ étage C ignoré : {spec.env_key} absente de backend/.env — "
            f"{len(candidats)} aide(s) restent à mettre à jour."
        )
        return {}

    retenus = candidats[: args.max_llm]
    log("")
    log(f"{'=' * 70}")
    log(
        f"ÉTAGE C — {len(retenus)}/{len(candidats)} aide(s), modèle {spec.alias}"
        + (" — à blanc, aucune écriture" if args.dry_run else "")
    )
    log(f"{'=' * 70}")

    majs: dict[str, MajResult] = {}
    for i, slug in enumerate(retenus, 1):
        maj = mettre_a_jour(
            aides[slug],
            analyses[slug],
            collects[slug],
            spec,
            aujourd_hui=today,
            dry_run=args.dry_run,
        )
        majs[slug] = maj
        log(
            f"  [{i}/{len(retenus)}] {maj.symbole} {slug:<46} "
            f"{maj.cout_usd * 100:>5.2f}¢ {maj.latence_s:>5.1f}s "
            f"{tokens_compacts(maj.tokens_in):>6}↑{tokens_compacts(maj.tokens_out):>6}↓  "
            f"{cellule(maj.raison, 52)}"
        )
        if maj.reponse_rejetee:
            # Dans le log, pas dans le rapport : c'est de la matière de
            # débogage, et le rapport doit rester relisable.
            log(f"      réponse rejetée : {maj.reponse_rejetee.strip()}")
        if maj.etat == "escalade":
            # Le modèle a déclaré forfait : l'aide sort du périmètre de la
            # retouche automatique et rejoint la file de ré-ingestion.
            analyses[slug].statut = "ESCALADE_INGESTION"
            analyses[slug].raisons.append(maj.raison)

    if len(candidats) > len(retenus):
        log(
            f"  … {len(candidats) - len(retenus)} aide(s) laissée(s) de côté : plafond "
            f"--max-llm={args.max_llm}. Relancer après relecture pour la suite."
        )
    tok_in = sum(m.tokens_in for m in majs.values())
    tok_out = sum(m.tokens_out for m in majs.values())
    log(
        f"  coût de l'étage C : {sum(m.cout_usd for m in majs.values()):.3f} $"
        f"  —  {milliers(tok_in)} tokens en entrée, {milliers(tok_out)} en sortie"
    )
    return majs


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="veille_aides.py",
        description="Re-visite les sources officielles des aides et met à jour ce qui a changé.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("slugs", nargs="*", help="aides à contrôler (défaut : toutes)")
    p.add_argument(
        "--report-only",
        action="store_true",
        help="étages A+B seulement : zéro LLM, zéro écriture",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="étage C compris, mais sans écrire un seul fichier",
    )
    p.add_argument(
        "--max-llm",
        type=int,
        default=MAX_LLM_DEFAUT,
        help=f"plafond d'appels au modèle par passage (défaut : {MAX_LLM_DEFAUT})",
    )
    p.add_argument(
        "--model",
        default=MODELE_DEFAUT,
        help=(
            f"modèle de l'étage C (défaut : {MODELE_DEFAUT}, réglé par VEILLE_MODEL "
            "dans backend/.env). Alias du registre, ou `fournisseur:identifiant` ; "
            "`uv run python scripts/veille_llm.py` liste les deux."
        ),
    )
    p.add_argument("--limit", type=int, help="ne traiter que les N aides les plus anciennes")
    p.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    p.add_argument(
        "--proxy",
        choices=("jina",),
        help="proxy d'extraction anti-bot (contenu utilisé pour les quotes, pas pour le diff)",
    )
    p.add_argument(
        "--offline",
        action="store_true",
        help="ne rien télécharger : inspecte le périmètre de surveillance seul",
    )
    p.add_argument(
        "--acquitter",
        action="store_true",
        help=(
            "pour les slugs donnés en DATE_PERIMEE_SOURCE_INCHANGEE : arbitrage humain "
            "rendu, ne plus alerter tant que la date limite ne change pas"
        ),
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    import time

    args = parse_args(argv if argv is not None else sys.argv[1:])
    log = Journal()
    today = date.today()

    # Un VEILLE_MODEL mal saisi doit dire lequel et proposer les valeurs
    # valides, pas dérouler une KeyError au milieu d'un passage.
    try:
        resoudre_modele(args.model)
    except KeyError as exc:
        print(f"ERREUR : {exc.args[0]}", file=sys.stderr)
        return 1

    if args.acquitter and (not args.slugs or args.offline):
        print(
            "ERREUR : --acquitter exige des slugs explicites et un run en ligne "
            "(le manifeste n'est pas écrit hors ligne).",
            file=sys.stderr,
        )
        return 1

    if args.slugs:
        paths = [AIDES_DIR / f"{s}.yaml" for s in args.slugs]
        if manquants := [p.stem for p in paths if not p.exists()]:
            print(f"ERREUR : YAML introuvable pour : {', '.join(manquants)}", file=sys.stderr)
            return 1
    else:
        paths = sorted(AIDES_DIR.glob("*.yaml"))

    try:
        aides = {p.stem: load_aide(p) for p in paths}
    except Exception as exc:
        print(f"ERREUR : YAML invalide — {exc}", file=sys.stderr)
        return 1

    manifest = load_manifest()
    ordre = sorted(aides.values(), key=lambda a: (anciennete(a, manifest), a.slug))
    if args.limit:
        ordre = ordre[: args.limit]
    aides = {a.slug: a for a in ordre}

    log(f"{'=' * 70}")
    log(f"VEILLE DES AIDES — {today.isoformat()}")
    log(f"{'=' * 70}")
    log(f"{len(aides)} aide(s), triées des plus anciennement vérifiées aux plus récentes.")
    if args.offline:
        log("Mode hors-ligne : aucun téléchargement, périmètre de surveillance seul.")

    start = time.monotonic()
    collects = collect(
        list(aides.values()),
        concurrency=args.concurrency,
        timeout=args.timeout,
        proxy=args.proxy,
        offline=args.offline,
    )
    n_urls = len({m.url for c in collects.values() for m in c.urls})
    log(f"{n_urls} URL distinctes surveillées.")

    analyses = analyze_all(aides, collects, today=today)
    acquittees = traiter_acquittements(
        analyses, manifest, nouveaux=args.slugs if args.acquitter else []
    )
    if acquittees:
        log(f"{len(acquittees)} échéance(s) dépassée(s) acquittée(s) : {', '.join(acquittees)}")
    if args.acquitter and (refusees := sorted(set(args.slugs) - set(acquittees))):
        log(
            f"⚠ non acquittée(s), statut différent de DATE_PERIMEE_SOURCE_INCHANGEE : "
            f"{', '.join(refusees)}"
        )
    log(f"collecte et analyse terminées en {(time.monotonic() - start) / 60:.1f} min.")

    majs = run_stage_c(args, aides, analyses, collects, today, log)
    duree = time.monotonic() - start

    log("")
    log(f"{'=' * 70}")
    log("RÉCAP")
    log(f"{'=' * 70}")
    compte = Counter(an.statut for an in analyses.values())
    for statut in STATUTS:
        if compte[statut]:
            log(f"  {SYMBOLES[statut]} {statut:<32} {compte[statut]}")
    for statut in STATUTS:
        if statut == "OK":
            continue
        for an in sorted(
            (a for a in analyses.values() if a.statut == statut), key=lambda a: a.slug
        ):
            log(f"    {SYMBOLES[statut]} {an.slug:<50} {an.raisons[0] if an.raisons else ''}")

    alerter_chrome_affame(analyses, collects, log)

    # Réserve sur la portée des statuts rassurants. Sans cette section, un `OK`
    # dont aucune citation n'a pu être recontrôlée se lit « l'aide est à jour »,
    # alors qu'il ne dit rien du document qui porte les critères. L'information
    # existait déjà dans la section « Qualité des preuves » du rapport ; en
    # pratique on ne lit que le RÉCAP, donc elle doit être ici.
    partielles = sorted(
        (
            a
            for a in analyses.values()
            if a.statut in ("OK", "DATE_PERIMEE_SOURCE_INCHANGEE")
            and a.couverture_quotes[1]
            and a.couverture_quotes[0] < a.couverture_quotes[1]
        ),
        key=lambda a: (a.couverture_quotes[0] / a.couverture_quotes[1], a.slug),
    )
    if partielles:
        log("")
        log("  couverture partielle des citations — le statut ne porte que sur les")
        log("  pages effectivement re-téléchargées, pas sur le règlement :")
        for an in partielles:
            n, tot = an.couverture_quotes
            alerte = "  ← ne prouve rien" if n == 0 else ""
            log(
                f"    {SYMBOLE_COUVERTURE} {an.slug:<50} {n}/{tot} citation(s) contrôlée(s){alerte}"
            )

    if args.report_only or args.offline:
        mode = "report-only"
    else:
        mode = "dry-run" if args.dry_run else "complet"

    if not args.offline:
        # Hors ligne, aucune source n'a été consultée : dater le contrôle
        # d'aujourd'hui ferait passer tout le parc pour vérifié.
        write_manifest(update_manifest(manifest, analyses, majs, today))
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REVIEWS_DIR / f"{today.isoformat()}-veille.md"
    report_path.write_text(
        build_report(analyses, today, duree, offline=args.offline, majs=majs, mode=mode),
        encoding="utf-8",
    )

    log("")
    if args.offline:
        log("manifeste : NON mis à jour (--offline)")
    else:
        log(f"manifeste : {MANIFEST_PATH.relative_to(DATA_DIR.parent)}")
    log(f"rapport   : {report_path.relative_to(DATA_DIR.parent)}")
    log(f"durée     : {duree / 60:.1f} min")
    appliquees = [m for m in majs.values() if m.etat == "applique"]
    rearchivees = [m for m in majs.values() if m.etat == "inchange" and m.snapshots]
    if appliquees:
        log("")
        log(
            f"{len(appliquees)} fiche(s) modifiée(s)"
            + (" — à blanc, rien sur disque." if args.dry_run else " sur disque.")
        )
    if rearchivees:
        log(
            f"{len(rearchivees)} aide(s) sans retouche de fiche mais dont la page a été "
            "ré-archivée (nouvelle baseline)."
        )
    if (appliquees or rearchivees) and not args.dry_run:
        log("Relire avant commit : git diff -- data/aides data/sources")
    log.save(LOG_DIR / f"veille-{today.isoformat()}.log")

    echecs = any(m.etat == "echec" for m in majs.values())
    return 2 if compte["ESCALADE_INGESTION"] or compte["ERREUR_HTTP"] or echecs else 0


if __name__ == "__main__":
    sys.exit(main())
