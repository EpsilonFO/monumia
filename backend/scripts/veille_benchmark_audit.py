"""
Benchmark de l'audit d'exhaustivité (étage D) : quel modèle relève ce qui manque
sans rien inventer.

    cd backend && uv run python scripts/veille_benchmark_audit.py --models ds-flash,glm-flash
    cd backend && uv run python scripts/veille_benchmark_audit.py --cases sauvegarde-intacte

Hors ligne : le corpus est celui des snapshots archivés (`collect(offline=True)`),
comme l'audit le fait déjà pour toute page non re-téléchargeable. Seul le modèle
est appelé.

Deux familles de cas (`data/veille-golds-audit.yaml`) :
  - `intacte` : la fiche du dépôt, réputée complète. Tout `absent`/`divergent`
    est un faux manquant.
  - `retrait` : une condition réelle retirée de la fiche. Le modèle doit la
    retrouver (un `absent` dont la citation recoupe la sienne) et rien d'autre.

La métrique reine est `faux` : un manquant que le cas n'attendait pas. Un faux
manquant correctement cité franchit toute la validation et finit dans le YAML en
`untyped` — puis dans le moteur, une fois typé. Le rappel départage ensuite, puis
le coût.

Codes de sortie : 0 terminé ; 1 erreur fatale (gold invalide, aucun modèle).
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aides_schema import AIDES_DIR, DATA_DIR, Aide, charger_yaml, load_aide

sys.path.insert(0, str(Path(__file__).resolve().parent))

from veille_apply import _localiser_condition
from veille_audit import (
    SYSTEM_AUDIT,
    AuditLLMOutput,
    Corpus,
    CritereAudit,
    build_prompt_audit,
    construire_corpus,
    valider,
)
from veille_collect import collect
from veille_llm import REGISTRE, ModelSpec, call, json_schema, resoudre_modele, system_pour
from veille_text import find_quote_in_any, normalize

GOLDS_PATH = DATA_DIR / "veille-golds-audit.yaml"
REVIEWS_DIR = DATA_DIR / "reviews"

# Deux citations « recoupent » le même passage si l'une contient l'autre, ou si
# elles tombent à moins de cette distance (en caractères normalisés) dans le
# même document : le modèle cite rarement exactement les bornes de la fiche.
FENETRE_RECOUPEMENT = 400
MIN_CHARS_INCLUSION = 20


# ---------------------------------------------------------------------------
# Cas de référence
# ---------------------------------------------------------------------------


@dataclass
class Gold:
    id: str
    slug: str
    type: str
    condition: str | None = None
    commentaire: str = ""

    @property
    def retrait(self) -> bool:
        return self.type == "retrait"


def charger_golds(chemin: Path = GOLDS_PATH) -> list[Gold]:
    brut = charger_yaml(chemin.read_text(encoding="utf-8")) or []
    golds = [Gold(**cas) for cas in brut]
    for g in golds:
        if g.type not in ("intacte", "retrait"):
            raise SystemExit(f"gold « {g.id} » : type inconnu {g.type!r}")
        if g.retrait and not g.condition:
            raise SystemExit(f"gold « {g.id} » : `retrait` exige `condition`")
    return golds


@dataclass
class Cas:
    """Un gold préparé : la fiche (éventuellement amputée), son corpus, la cible."""

    gold: Gold
    aide: Aide
    texte_fiche: str
    corpus: Corpus
    # Condition retirée, pour un cas `retrait`.
    retiree: dict | None = None


def preparer(gold: Gold) -> Cas:
    """Fiche et corpus d'un cas, hors ligne. Échoue si le cas ne mesure rien.

    Le retrait est une ÉDITION CHIRURGICALE du texte (mêmes primitives que
    l'éditeur de la veille) : la fiche soumise reste un vrai fichier du dépôt
    à une condition près, pas une re-sérialisation.
    """
    chemin = AIDES_DIR / f"{gold.slug}.yaml"
    if not chemin.exists():
        raise SystemExit(f"gold « {gold.id} » : fiche introuvable — {chemin}")
    aide = load_aide(chemin)
    texte = chemin.read_text(encoding="utf-8")
    col = collect([aide], offline=True)[aide.slug]

    retiree = None
    if gold.retrait:
        cible = next((c for c in aide.conditions if c.id == gold.condition), None)
        if cible is None:
            raise SystemExit(f"gold « {gold.id} » : condition « {gold.condition} » absente")
        if not cible.quote:
            raise SystemExit(f"gold « {gold.id} » : la condition retirée n'a pas de quote")
        _, match = find_quote_in_any(cible.quote, col.baseline_docs)  # type: ignore[arg-type]
        if not match.found:
            raise SystemExit(
                f"gold « {gold.id} » : la citation de « {gold.condition} » n'est plus dans "
                "l'archive — le cas ne mesurerait pas ce qu'il annonce"
            )
        lignes = texte.split("\n")
        span = _localiser_condition(lignes, cible.id)
        if span is None:
            raise SystemExit(f"gold « {gold.id} » : condition « {cible.id} » non localisée")
        debut, fin = span
        # Une ligne vide de séparation suit souvent l'item : on l'emporte avec.
        if fin < len(lignes) and not lignes[fin].strip():
            fin += 1
        texte = "\n".join(lignes[:debut] + lignes[fin:])
        aide = Aide.model_validate(charger_yaml(texte))
        retiree = cible.model_dump(mode="json")

    corpus = construire_corpus(aide, col)
    if corpus.vide:
        raise SystemExit(f"gold « {gold.id} » : aucun snapshot lisible pour {gold.slug}")
    return Cas(gold=gold, aide=aide, texte_fiche=texte, corpus=corpus, retiree=retiree)


# ---------------------------------------------------------------------------
# Notation
# ---------------------------------------------------------------------------


def recoupe(quote_a: str, quote_b: str, corpus: Corpus) -> bool:
    """Les deux citations désignent-elles le même passage de la source ?"""
    a, b = normalize(quote_a), normalize(quote_b)
    if not a or not b:
        return False
    if a == b:
        return True
    court, long_ = sorted((a, b), key=len)
    if len(court) >= MIN_CHARS_INCLUSION and court in long_:
        return True
    for _nom, contenu, _kind in corpus.documents():
        hay = normalize(contenu)
        ia, ib = hay.find(a), hay.find(b)
        if ia != -1 and ib != -1 and abs(ia - ib) <= FENETRE_RECOUPEMENT:
            return True
    return False


@dataclass
class Score:
    gold: str
    modele: str
    json_ok: bool = False
    # Métrique reine : manquants que le cas n'attendait pas.
    faux: list[str] = field(default_factory=list)
    retrouvee: bool | None = None  # None pour un cas `intacte`
    criteres: int = 0
    conformes_ecartes: int = 0
    escalade: bool = False
    etape_echec: str | None = None
    erreurs: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0

    @property
    def reussi(self) -> bool:
        """Réponse acceptée telle quelle, sans faux manquant ni retrait raté.

        Une réponse refusée par la validation n'est pas un succès même si son
        relevé est irréprochable : en production elle coûte une relance, et au
        second refus l'aide sort en `echec`. Le premier benchmark la comptait ✓
        et masquait qu'un modèle oubliait un `cond_id` sur un cas sur deux.
        """
        return (
            self.json_ok
            and self.etape_echec is None
            and not self.faux
            and self.retrouvee is not False
        )


def noter(cas: Cas, out: AuditLLMOutput, score: Score) -> None:
    absents: list[CritereAudit] = out.absents
    if cas.retiree is not None:
        quote = cas.retiree.get("quote") or ""
        trouves = [c for c in absents if recoupe(quote, c.quote, cas.corpus)]
        score.retrouvee = bool(trouves)
        absents = [c for c in absents if c not in trouves]
    score.faux = [f"+{c.id}" for c in absents] + [f"~{c.cond_id}" for c in out.divergents]
    if out.fiche_incomplete:
        score.escalade = True
        # Une fiche du dépôt déclarée « à ré-ingérer » est une fausse alerte.
        score.faux.append("fiche_incomplete")


# ---------------------------------------------------------------------------
# Exécution
# ---------------------------------------------------------------------------


def executer(cas: Cas, spec: ModelSpec, *, aujourd_hui: date, log, timeout: float) -> Score:
    score = Score(gold=cas.gold.id, modele=spec.alias)
    prompt = build_prompt_audit(cas.aide, cas.corpus, aujourd_hui=aujourd_hui)
    # Une ligne AVANT l'appel : un modèle à raisonnement peut mettre plusieurs
    # minutes à répondre, et un terminal muet pendant ce temps se lit « bloqué ».
    log(
        f"      {spec.alias:<10} … appel en cours (~{len(prompt) // 4} tokens de prompt, "
        f"délai {timeout:.0f} s)"
    )
    appel = call(
        spec,
        system_pour(spec, SYSTEM_AUDIT, AuditLLMOutput),
        prompt,
        schema=json_schema(AuditLLMOutput),
        timeout=timeout,
    )
    score.input_tokens, score.output_tokens = appel.input_tokens, appel.output_tokens
    score.cost_usd, score.latency_s = appel.cost_usd or 0.0, appel.latency_s
    if not appel.ok:
        score.erreurs, score.etape_echec = [appel.error or "réponse vide"], "appel"
        log(f"      {spec.alias:<10} ÉCHEC APPEL — {appel.error}")
        return score

    out, erreurs, etape, ecartes = valider(appel.text, cas.aide, cas.corpus)
    score.json_ok = out is not None
    score.conformes_ecartes = ecartes
    if out is None:
        score.erreurs, score.etape_echec = erreurs, etape
        log(f"      {spec.alias:<10} JSON/schéma invalide — {erreurs[0][:70]}")
        return score
    score.criteres = len(out.criteres) + ecartes
    if erreurs:
        # Validation refusée : ce que le modèle voulait écrire n'entrerait pas.
        # On note quand même le relevé brut, pour voir CE qu'il inventait.
        score.erreurs, score.etape_echec = erreurs, etape
    noter(cas, out, score)
    log(_ligne(score))
    return score


def _ligne(s: Score) -> str:
    marque = "✓" if s.reussi else "✗"
    rappel = "—" if s.retrouvee is None else ("oui" if s.retrouvee else "NON")
    return (
        f"      {s.modele:<10} {marque} faux={len(s.faux):<2} retrouvée={rappel:<3} "
        f"critères={s.criteres:<3} {s.cost_usd * 100:>6.2f}¢ {s.latency_s:>5.1f}s"
        + (f"  [{s.etape_echec}]" if s.etape_echec else "")
    )


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------


def rapport(scores: list[Score], golds: list[Gold], aujourd_hui: date) -> str:
    par_modele: dict[str, list[Score]] = {}
    for s in scores:
        par_modele.setdefault(s.modele, []).append(s)

    def cle(kv):
        liste = kv[1]
        return (
            sum(len(s.faux) for s in liste),
            sum(1 for s in liste if s.retrouvee is False),
            sum(s.cost_usd for s in liste),
        )

    out = [
        f"# Benchmark de l'audit d'exhaustivité — {aujourd_hui.isoformat()}",
        "",
        f"{len(golds)} cas × {len(par_modele)} modèle(s), corpus hors ligne (snapshots archivés).",
        "",
        "La colonne qui décide est **faux** : un manquant que le cas n'attendait pas. "
        "Zéro est le seul score acceptable — un faux manquant correctement cité entre "
        "dans le YAML en `untyped`, puis dans le moteur une fois typé. Les retraits "
        "non retrouvés départagent ensuite, le coût en dernier.",
        "",
        "| modèle | JSON ok | faux | retraits retrouvés | critères/cas | écartés | tok in/out | ¢/cas | s/cas |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for modele, liste in sorted(par_modele.items(), key=cle):
        n = len(liste)
        retraits = [s for s in liste if s.retrouvee is not None]
        out.append(
            f"| `{modele}` | {sum(s.json_ok for s in liste)}/{n} "
            f"| **{sum(len(s.faux) for s in liste)}** "
            f"| {sum(1 for s in retraits if s.retrouvee)}/{len(retraits)} "
            f"| {sum(s.criteres for s in liste) / n:.0f} "
            f"| {sum(s.conformes_ecartes for s in liste)} "
            f"| {sum(s.input_tokens for s in liste) // n}/{sum(s.output_tokens for s in liste) // n} "
            f"| {sum(s.cost_usd for s in liste) / n * 100:.2f} "
            f"| {sum(s.latency_s for s in liste) / n:.1f} |"
        )

    out += ["", "## Détail par cas", ""]
    for gold in golds:
        lignes = [s for s in scores if s.gold == gold.id]
        if not lignes:
            continue
        out += [
            f"### `{gold.id}` ({gold.type}) — {gold.slug}",
            "",
            gold.commentaire.strip(),
            "",
            "| modèle | faux | retrouvée | critères | échec | détail |",
            "|---|---:|---|---:|---|---|",
        ]
        for s in lignes:
            retrouvee = "—" if s.retrouvee is None else ("oui" if s.retrouvee else "non")
            detail = ", ".join(s.faux[:5]) or "—"
            if s.erreurs:
                detail += f" · {s.erreurs[0][:100]}"
            out.append(
                f"| `{s.modele}` | {len(s.faux)} | {retrouvee} | {s.criteres} "
                f"| {s.etape_echec or '—'} | {detail} |"
            )
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="veille_benchmark_audit.py", description=__doc__)
    p.add_argument("--models", help="alias séparés par des virgules (défaut : clés présentes)")
    p.add_argument("--cases", help="ids de cas séparés par des virgules (défaut : tous)")
    p.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="délai par appel en secondes (défaut : 600 ; un modèle à raisonnement non "
        "plafonné peut dépasser 400 s)",
    )
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    golds = charger_golds()
    if args.cases:
        voulus = set(args.cases.split(","))
        golds = [g for g in golds if g.id in voulus]
        if not golds:
            print(f"ERREUR : aucun cas parmi {sorted(voulus)}", file=sys.stderr)
            return 1

    if args.models:
        try:
            specs = [resoudre_modele(a) for a in args.models.split(",")]
        except KeyError as exc:
            print(f"ERREUR : {exc.args[0]}", file=sys.stderr)
            return 1
    else:
        specs = [s for s in REGISTRE.values() if s.cle_presente]
    if not specs:
        print(
            "ERREUR : aucun modèle utilisable — aucune clé d'API dans backend/.env.",
            file=sys.stderr,
        )
        return 1

    aujourd_hui = date.today()
    lignes_log: list[str] = []

    def log(msg: str = "") -> None:
        print(msg, flush=True)
        lignes_log.append(msg)

    log("=" * 70)
    log(f"BENCHMARK AUDIT — {aujourd_hui.isoformat()}")
    log("=" * 70)
    log(f"{len(golds)} cas × {len(specs)} modèle(s) : {', '.join(s.alias for s in specs)}")

    debut = time.monotonic()
    scores: list[Score] = []
    with tempfile.TemporaryDirectory():
        for gold in golds:
            cas = preparer(gold)
            log(
                f"\n  {gold.id} ({gold.type}) — {len(cas.corpus.docs)} document(s), portée {cas.corpus.portee}"
            )
            for spec in specs:
                scores.append(
                    executer(cas, spec, aujourd_hui=aujourd_hui, log=log, timeout=args.timeout)
                )

    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    chemin = REVIEWS_DIR / f"{aujourd_hui.isoformat()}-benchmark-audit.md"
    chemin.write_text(rapport(scores, golds, aujourd_hui), encoding="utf-8")

    log("")
    log("=" * 70)
    log(f"faux manquants, tous modèles confondus : {sum(len(s.faux) for s in scores)}")
    log(f"retraits non retrouvés : {sum(1 for s in scores if s.retrouvee is False)}")
    log(
        f"coût total : {sum(s.cost_usd for s in scores):.3f} $   durée : {(time.monotonic() - debut) / 60:.1f} min"
    )
    log(f"rapport : {chemin.relative_to(DATA_DIR.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
