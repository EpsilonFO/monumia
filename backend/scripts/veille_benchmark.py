"""
Benchmark de l'étage C : quel modèle mettre à jour une fiche sans rien inventer.

    cd backend && uv run python scripts/veille_benchmark.py --models ds-flash,ds-pro
    cd backend && uv run python scripts/veille_benchmark.py --raw --cases sauvegarde-inchange

C'est aussi le test d'intégration de l'étage C : il exerce la chaîne complète
(prompt → appel → validation → édition → assertion de différence profonde) sur
des cas dont la réponse est connue.

Deux modes :
  --raw   appel nu. Mesure le MODÈLE : ce qu'il produit sans filet.
  défaut  chaîne complète avec sa nouvelle tentative. Mesure le SYSTÈME.
Un modèle qui hallucine mais dont les inventions sont toutes rattrapées par le
grep de citations est bon en mode système et mauvais en mode brut — les deux
chiffres se lisent ensemble.

La métrique reine est `faux chg` : une proposition que le gold n'attendait pas.
Un faux changement passe par la validation quand il est correctement cité, et
finit dans le YAML. Le classement se fait dessus d'abord, sur le coût ensuite.

Codes de sortie : 0 terminé ; 1 erreur fatale (gold invalide, aucun modèle).
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aides_schema import AIDES_DIR, DATA_DIR, charger_yaml, load_aide

sys.path.insert(0, str(Path(__file__).resolve().parent))

from veille_apply import VeilleLLMOutput, appliquer, parse_output
from veille_collect import SOURCES_DIR
from veille_llm import REGISTRE, ModelSpec, build_prompt, call, resoudre_modele, system_pour
from veille_text import flatten_markdown_links, normalized_diff, parse_front_matter

GOLDS_PATH = DATA_DIR / "veille-golds.yaml"
REVIEWS_DIR = DATA_DIR / "reviews"


# ---------------------------------------------------------------------------
# Cas de référence
# ---------------------------------------------------------------------------


@dataclass
class Gold:
    id: str
    slug: str
    type: str
    snapshot: str
    edits: list[dict[str, str]] = field(default_factory=list)
    attendu: dict[str, Any] = field(default_factory=dict)
    commentaire: str = ""

    @property
    def negatif(self) -> bool:
        return self.type == "negatif"

    def sections_attendues(self) -> dict[str, set[str]]:
        return {
            nom: set(self.attendu.get(nom, []))
            for nom in ("calendrier", "financement", "cumul")
            if self.attendu.get(nom)
        }

    def conditions_attendues(self) -> dict[str, set[str]]:
        return {c["id"]: set(c.get("champs", [])) for c in self.attendu.get("conditions", [])}

    @property
    def ajouts_attendus(self) -> int:
        return int(self.attendu.get("conditions_ajoutees", 0))


def charger_golds(chemin: Path = GOLDS_PATH) -> list[Gold]:
    brut = charger_yaml(chemin.read_text(encoding="utf-8")) or []
    return [Gold(**cas) for cas in brut]


def contenu_frais(gold: Gold) -> tuple[str, str]:
    """(baseline, contenu frais) après application des modifications du gold.

    Chaque `avant` doit exister littéralement : sans ce contrôle, un snapshot
    rafraîchi ferait silencieusement passer un cas positif pour un cas négatif,
    et le benchmark mesurerait autre chose que ce qu'il annonce.
    """
    chemin = SOURCES_DIR / gold.slug / gold.snapshot
    if not chemin.exists():
        raise SystemExit(f"gold « {gold.id} » : snapshot introuvable — {chemin}")
    baseline = flatten_markdown_links(parse_front_matter(chemin.read_text(encoding="utf-8"))[1])
    frais = baseline
    for edit in gold.edits:
        avant, apres = edit["avant"], edit["apres"]
        if avant not in frais:
            raise SystemExit(
                f"gold « {gold.id} » : texte à remplacer absent du snapshot — « {avant[:70]} »"
            )
        frais = frais.replace(avant, apres, 1)
    return baseline, frais


# ---------------------------------------------------------------------------
# Notation
# ---------------------------------------------------------------------------


@dataclass
class Score:
    gold: str
    modele: str
    json_ok: bool = False
    # Métrique reine : propositions que le gold n'attendait pas.
    faux_changements: list[str] = field(default_factory=list)
    attendus_trouves: int = 0
    attendus_total: int = 0
    ajouts: int = 0
    quotes_ok: int = 0
    quotes_total: int = 0
    cosmetiques: int = 0
    escalade: bool = False
    applique: bool = False
    etape_echec: str | None = None
    erreurs: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0

    @property
    def rappel(self) -> float:
        return self.attendus_trouves / self.attendus_total if self.attendus_total else 1.0


def noter(
    gold: Gold, out: VeilleLLMOutput | None, escalade: bool
) -> tuple[list[str], int, int, int]:
    """(faux changements, attendus trouvés, attendus au total, ajouts)."""
    sections_att = gold.sections_attendues()
    conditions_att = gold.conditions_attendues()
    total = sum(len(v) for v in sections_att.values()) + len(conditions_att) + gold.ajouts_attendus

    if out is None:
        return ([] if escalade else []), 0, total, 0

    faux: list[str] = []
    trouves = 0

    for nom in ("calendrier", "financement", "cumul"):
        section = getattr(out, nom)
        if section is None:
            continue
        attendus = sections_att.get(nom, set())
        for champ in section.champs:
            if champ in attendus:
                trouves += 1
            else:
                faux.append(f"{nom}.{champ}")

    ajouts = 0
    for chg in out.conditions:
        if chg.op == "add":
            ajouts += 1
            if ajouts > gold.ajouts_attendus:
                faux.append(f"+condition {chg.id}")
            else:
                trouves += 1
            continue
        if chg.id not in conditions_att:
            faux.append(f"condition {chg.id} ({chg.op})")
            continue
        trouves += 1
    return faux, trouves, total, ajouts


# ---------------------------------------------------------------------------
# Exécution
# ---------------------------------------------------------------------------


def executer(gold: Gold, spec: ModelSpec, *, raw: bool, aujourd_hui: date, log) -> Score:
    score = Score(gold=gold.id, modele=spec.alias)
    aide = load_aide(AIDES_DIR / f"{gold.slug}.yaml")
    baseline, frais = contenu_frais(gold)
    documents = [(gold.snapshot, frais, "text")]
    diff = normalized_diff(baseline, frais).text

    prompt = build_prompt(aide, documents, diff, aujourd_hui=aujourd_hui)
    # Avant l'appel : un modèle à raisonnement peut répondre en plusieurs
    # minutes, et un terminal muet se lit « bloqué ».
    log(f"      {spec.alias:<10} … appel en cours (~{len(prompt) // 4} tokens de prompt)")
    appel = call(spec, system_pour(spec), prompt)
    score.input_tokens = appel.input_tokens
    score.output_tokens = appel.output_tokens
    score.cost_usd = appel.cost_usd or 0.0
    score.latency_s = appel.latency_s

    if not appel.ok:
        score.erreurs = [appel.error or "réponse vide"]
        score.etape_echec = "appel"
        log(f"      {spec.alias:<10} ÉCHEC APPEL — {appel.error}")
        return score

    out, erreurs, etape = parse_output(appel.text, gold.slug)
    score.json_ok = out is not None
    if out is None:
        score.erreurs, score.etape_echec = erreurs, etape
        log(f"      {spec.alias:<10} JSON/schéma invalide — {erreurs[0][:70]}")
        return score

    score.escalade = out.changement_majeur
    faux, trouves, total, ajouts = noter(gold, out, out.changement_majeur)
    score.faux_changements, score.attendus_trouves = faux, trouves
    score.attendus_total, score.ajouts = total, ajouts

    if raw:
        log(_ligne_resume(gold, score))
        return score

    # Mode système : la chaîne complète, jusqu'à l'écriture (en mémoire).
    chemin = AIDES_DIR / f"{gold.slug}.yaml"
    res = appliquer(appel.text, aide, chemin, documents, aujourd_hui=aujourd_hui.isoformat())
    score.applique = res.ok
    score.cosmetiques = res.cosmetiques
    if not res.ok:
        score.etape_echec = res.etape
        score.erreurs = res.erreurs[:4]
    # Ce que le grep de citations a laissé passer : mesure du filet, pas du modèle.
    quotes = _compter_quotes(out)
    score.quotes_total = quotes
    score.quotes_ok = quotes if res.etape != "quote" else 0
    log(_ligne_resume(gold, score))
    return score


def _compter_quotes(out: VeilleLLMOutput) -> int:
    n = sum(1 for s in (out.calendrier, out.financement, out.cumul) if s is not None)
    for chg in out.conditions:
        if chg.op == "add" or (chg.champs and "quote" in chg.champs):
            n += 1
    return n


def _ligne_resume(gold: Gold, s: Score) -> str:
    marque = "✓" if not s.faux_changements and (gold.negatif or s.rappel == 1.0) else "✗"
    return (
        f"      {s.modele:<10} {marque} faux={len(s.faux_changements):<2} "
        f"rappel={s.rappel:>4.0%} appliqué={'oui' if s.applique else 'non':<3} "
        f"{s.cost_usd * 100:>6.2f}¢ {s.latency_s:>5.1f}s"
        + (f"  [{s.etape_echec}]" if s.etape_echec else "")
    )


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------


def rapport(scores: list[Score], golds: list[Gold], raw: bool, aujourd_hui: date) -> str:
    par_modele: dict[str, list[Score]] = {}
    for s in scores:
        par_modele.setdefault(s.modele, []).append(s)

    out = [
        f"# Benchmark de l'étage C — {aujourd_hui.isoformat()}",
        "",
        f"Mode : **{'brut (appel nu, mesure du modèle)' if raw else 'système (chaîne complète)'}**. "
        f"{len(golds)} cas × {len(par_modele)} modèle(s).",
        "",
        "La colonne qui décide est **faux chg** : une proposition que le cas de "
        "référence n'attendait pas. Zéro est le seul score acceptable — un faux "
        "changement correctement cité franchit toute la validation et finit dans "
        "le YAML. Le coût départage ensuite.",
        "",
        "| modèle | JSON ok | faux chg | rappel | appliqué | cosmétiques | escal. | tok in/out | ¢/aide | s/aide |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for modele, liste in sorted(
        par_modele.items(),
        key=lambda kv: (
            sum(len(s.faux_changements) for s in kv[1]),
            sum(s.cost_usd for s in kv[1]),
        ),
    ):
        n = len(liste)
        out.append(
            f"| `{modele}` | {sum(s.json_ok for s in liste)}/{n} "
            f"| **{sum(len(s.faux_changements) for s in liste)}** "
            f"| {sum(s.rappel for s in liste) / n:.0%} "
            f"| {sum(s.applique for s in liste)}/{n} "
            f"| {sum(s.cosmetiques for s in liste)} "
            f"| {sum(s.escalade for s in liste)} "
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
            f"{gold.commentaire.strip()}",
            "",
            "| modèle | faux chg | rappel | appliqué | échec | détail |",
            "|---|---:|---:|---:|---|---|",
        ]
        for s in lignes:
            faux = ", ".join(s.faux_changements[:4]) or "—"
            detail = s.erreurs[0][:110] if s.erreurs else ""
            out.append(
                f"| `{s.modele}` | {len(s.faux_changements)} | {s.rappel:.0%} "
                f"| {'oui' if s.applique else 'non'} | {s.etape_echec or '—'} | {faux} {detail} |"
            )
        out.append("")

    classement = sorted(
        par_modele.items(),
        key=lambda kv: (
            sum(len(s.faux_changements) for s in kv[1]),
            sum(s.cost_usd for s in kv[1]),
        ),
    )
    if classement:
        gagnant, liste = classement[0]
        out += [
            "## Modèle retenu",
            "",
            f"**`{gagnant}`** — {sum(len(s.faux_changements) for s in liste)} faux changement(s), "
            f"{sum(s.cost_usd for s in liste) / len(liste) * 100:.2f} ¢ par aide en moyenne.",
            "",
            "À reporter dans `VEILLE_MODEL` de `backend/.env` (ou, pour changer le "
            "défaut du dépôt, dans `MODELE_DEFAUT` de `scripts/veille_llm.py`).",
            "",
        ]
    absents = [a for a, s in REGISTRE.items() if not s.cle_presente]
    if absents:
        out += [
            "## Modèles non testés",
            "",
            f"Clé absente de l'environnement : {', '.join(f'`{a}`' for a in absents)}. "
            "Le tableau ci-dessus ne les classe pas — ajouter la clé dans `backend/.env` "
            "et relancer. Les identifiants marqués « À VÉRIFIER » par "
            "`uv run python scripts/veille_llm.py` sont à confirmer auprès du "
            "fournisseur au même moment.",
            "",
        ]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="veille_benchmark.py", description=__doc__)
    p.add_argument(
        "--models", help="alias séparés par des virgules (défaut : ceux dont la clé est présente)"
    )
    p.add_argument("--cases", help="ids de cas séparés par des virgules (défaut : tous)")
    p.add_argument("--raw", action="store_true", help="appel nu, sans la chaîne de validation")
    p.add_argument("--list-models", action="store_true")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    if args.list_models:
        from veille_llm import table_registre

        print(table_registre())
        return 0

    golds = charger_golds()
    if args.cases:
        voulus = set(args.cases.split(","))
        golds = [g for g in golds if g.id in voulus]
        if not golds:
            print(f"ERREUR : aucun cas parmi {sorted(voulus)}", file=sys.stderr)
            return 1

    if args.models:
        specs = []
        for alias in args.models.split(","):
            try:
                specs.append(resoudre_modele(alias))
            except KeyError as exc:
                print(f"ERREUR : {exc.args[0]}", file=sys.stderr)
                return 1
    else:
        specs = [s for s in REGISTRE.values() if s.cle_presente]
    if not specs:
        print(
            "ERREUR : aucun modèle utilisable — aucune clé d'API dans backend/.env.\n"
            "         `uv run python scripts/veille_llm.py` liste le registre.",
            file=sys.stderr,
        )
        return 1

    aujourd_hui = date.today()
    lignes_log: list[str] = []

    def log(msg: str = "") -> None:
        print(msg, flush=True)
        lignes_log.append(msg)

    log("=" * 70)
    log(f"BENCHMARK ÉTAGE C — {aujourd_hui.isoformat()} — mode {'brut' if args.raw else 'système'}")
    log("=" * 70)
    log(f"{len(golds)} cas × {len(specs)} modèle(s) : {', '.join(s.alias for s in specs)}")
    manquants = [s.alias for s in specs if not s.cle_presente]
    if manquants:
        log(f"⚠ clé absente pour : {', '.join(manquants)} — ces modèles seront en échec d'appel")

    debut = time.monotonic()
    scores: list[Score] = []
    for gold in golds:
        log(f"\n  {gold.id} ({gold.type})")
        for spec in specs:
            scores.append(executer(gold, spec, raw=args.raw, aujourd_hui=aujourd_hui, log=log))

    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    suffixe = "-raw" if args.raw else ""
    chemin = REVIEWS_DIR / f"{aujourd_hui.isoformat()}-benchmark-veille{suffixe}.md"
    chemin.write_text(rapport(scores, golds, args.raw, aujourd_hui), encoding="utf-8")

    log("")
    log("=" * 70)
    total_faux = sum(len(s.faux_changements) for s in scores)
    log(f"faux changements, tous modèles confondus : {total_faux}")
    log(
        f"coût total : {sum(s.cost_usd for s in scores):.3f} $   durée : {(time.monotonic() - debut) / 60:.1f} min"
    )
    log(f"rapport : {chemin.relative_to(DATA_DIR.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
