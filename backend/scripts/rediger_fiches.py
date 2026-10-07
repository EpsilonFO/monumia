"""
Rédaction du bloc `fiche:` des aides : le skill `/rediger-fiche`, payé à l'API.

    # une ou plusieurs aides
    uv run python scripts/rediger_fiches.py --slug drac-mh-classes --slug cvl-festivals

    # les aides qui n'ont pas encore de fiche, par lots
    uv run python scripts/rediger_fiches.py --sans-fiche --limite 30 --parallele 4

    # les fiches que le lint signale « à relire » (source revérifiée depuis)
    uv run python scripts/rediger_fiches.py --a-relire

Le prompt système EST le skill : `.claude/skills/rediger-fiche/SKILL.md`, suivi de
`.claude/skills/ecriture-propre/SKILL.md`. Modifier l'un ou l'autre change la
rédaction dès le run suivant, il n'y a pas de doctrine recopiée ici.

Modèle : `LLM_MODEL_REDACTION` dans `backend/.env`, ou `--model`.

Ce que la commande NE FAIT JAMAIS : `git add`, un commit, `load_aides_yaml.py`.
Elle réécrit le bloc `fiche:` en fin de fichier et rien d'autre ; le diff git est
la relecture. Une fiche que les contrôles refusent n'est pas écrite.
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.llm import Compteur, charger_env, client_pour, resolution_pour

from aides_schema import AIDES_DIR, Aide, Fiche, load_aide

RACINE = Path(__file__).resolve().parent.parent.parent
SKILL_REDACTION = RACINE / ".claude" / "skills" / "rediger-fiche" / "SKILL.md"
SKILL_ECRITURE = RACINE / ".claude" / "skills" / "ecriture-propre" / "SKILL.md"
#: La fiche étalon, jointe au prompt : un exemple vaut mieux qu'un gabarit.
EXEMPLE = "drac-mh-classes"

ENTETE_FICHE = (
    "# Rédaction de la page de l'aide (skill rediger-fiche). Le moteur ne la lit\n"
    "# pas : `text` et `quote` restent la transcription de la source.\n"
)
_TIRETS_LONGS = ("—", "–")


# ---------------------------------------------------------------------------
# Le bloc dans le fichier
# ---------------------------------------------------------------------------


class _Dumper(yaml.SafeDumper):
    """Les textes longs en bloc replié (`>-`), comme le reste du catalogue."""


def _chaine(dumper: yaml.SafeDumper, texte: str) -> yaml.Node:
    return dumper.represent_scalar(
        "tag:yaml.org,2002:str", texte, style=">" if len(texte) > 72 else None
    )


_Dumper.add_representer(str, _chaine)


def _elaguer(valeur: object) -> object:
    """Retire les champs vides : une ligne `detail: null` n'apprend rien au relecteur."""
    if isinstance(valeur, dict):
        propre = {k: _elaguer(v) for k, v in valeur.items()}
        return {k: v for k, v in propre.items() if v not in (None, [], {})}
    if isinstance(valeur, list):
        return [_elaguer(v) for v in valeur]
    return valeur


def bloc_yaml(fiche: Fiche) -> str:
    return yaml.dump(
        {"fiche": _elaguer(fiche.model_dump())},
        Dumper=_Dumper,
        allow_unicode=True,
        sort_keys=False,
        width=88,
    )


def retirer_fiche(texte: str) -> str:
    """Le YAML sans son bloc `fiche:`, qui est TOUJOURS le dernier du fichier.

    Un bloc suivi d'une autre clé de premier niveau n'a pas été écrit par ce
    script : on refuse plutôt que de couper au mauvais endroit.
    """
    lignes = texte.split("\n")
    debut = next((i for i, li in enumerate(lignes) if li.startswith("fiche:")), None)
    if debut is None:
        return texte
    suite = [li for li in lignes[debut + 1 :] if li and not li.startswith((" ", "#"))]
    if suite:
        raise ValueError(
            f"le bloc `fiche:` n'est pas le dernier du fichier (suivi de {suite[0]!r})"
        )
    entete = ENTETE_FICHE.rstrip("\n").split("\n")
    if lignes[debut - len(entete) : debut] == entete:
        debut -= len(entete)
    return "\n".join(lignes[:debut]).rstrip("\n") + "\n"


def ecrire_fiche(chemin: Path, fiche: Fiche) -> None:
    base = retirer_fiche(chemin.read_text(encoding="utf-8"))
    chemin.write_text(base + "\n" + ENTETE_FICHE + bloc_yaml(fiche), encoding="utf-8")


# ---------------------------------------------------------------------------
# Contrôles
# ---------------------------------------------------------------------------


def normaliser(aide: Aide, fiche: Fiche, jour: date) -> Fiche:
    """Ce que le modèle n'a pas à décider : la date, la valeur du calendrier, et
    l'absence de rubrique sur un gate (il forme la sienne)."""
    fiche.redige_le = jour
    if fiche.essentiel.calendrier:
        fiche.essentiel.calendrier.valeur = None
    gates = {c.id for c in aide.conditions if c.effect == "gate"}
    for cid, point in fiche.points.items():
        if cid in gates:
            point.theme = None
    return fiche


def controler(aide: Aide, fiche: Fiche) -> list[str]:
    """Les refus. Chacun empêche l'écriture : une fiche fausse se lit en tête de page."""
    erreurs: list[str] = []
    ids = [c.id for c in aide.conditions]
    orphelins = sorted(set(fiche.points) - set(ids))
    orphelins += [c.condition for c in fiche.conseils if c.condition and c.condition not in ids]
    if orphelins:
        erreurs.append(f"conditions inconnues : {orphelins}")
    pieces = sorted(set(fiche.pieces) - {d.nom for d in aide.documents_requis})
    if pieces:
        erreurs.append(f"pièces inconnues : {pieces}")
    manquants = [i for i in ids if i not in fiche.points]
    if manquants:
        erreurs.append(f"conditions sans point : {manquants}")
    sans_theme = [
        cid
        for cid, p in fiche.points.items()
        if p.theme is None and cid in ids and aide.conditions[ids.index(cid)].effect != "gate"
    ]
    if sans_theme:
        erreurs.append(f"points sans rubrique : {sans_theme}")
    # Les clés de `pieces` sont le `nom` du YAML, tiret compris : c'est justement
    # ce que la fiche renomme. Seuls les libellés affichés comptent.
    texte = bloc_yaml(fiche.model_copy(update={"pieces": {}})) + "\n".join(fiche.pieces.values())
    if any(t in texte for t in _TIRETS_LONGS):
        erreurs.append("tiret cadratin ou demi-cadratin dans la fiche")
    if fiche.titre and len(fiche.titre) > 80:
        erreurs.append(f"titre de {len(fiche.titre)} caractères")
    return erreurs


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------


def _corps(skill: Path) -> str:
    """Le SKILL.md sans son en-tête YAML."""
    texte = skill.read_text(encoding="utf-8")
    if texte.startswith("---"):
        texte = texte.split("---", 2)[2]
    return texte.strip()


def consigne(aides_dir: Path = AIDES_DIR) -> str:
    exemple = aides_dir / f"{EXEMPLE}.yaml"
    return "\n\n".join(
        [
            "Tu rédiges le bloc `fiche:` d'UNE aide du catalogue Monumia. Tu rends la "
            "fiche en JSON, au schéma demandé ; la date et la mise en YAML sont faites "
            "après toi.",
            _corps(SKILL_REDACTION),
            "# Style : le skill ecriture-propre\n\n" + _corps(SKILL_ECRITURE),
            f"# Exemple complet : {exemple.name}\n\n```yaml\n"
            + exemple.read_text(encoding="utf-8")
            + "\n```",
        ]
    )


def prompt_pour(chemin: Path) -> str:
    source = retirer_fiche(chemin.read_text(encoding="utf-8"))
    # La liste explicite : sans elle, un modèle léger omettait le bloc `points`
    # en entier sur une aide à vingt conditions (8 refus sur 24 le 2026-10-04).
    ids = [c.id for c in load_aide(chemin).conditions]
    attendus = (
        "\n\nLe bloc `points` doit contenir exactement une entrée par condition, "
        f"ni plus ni moins ({len(ids)}) : " + ", ".join(ids)
        if ids
        else ""
    )
    return f"Aide à rédiger : {chemin.name}\n\n```yaml\n{source}\n```{attendus}"


# Réponse refusée renvoyée au modèle : assez pour qu'il la complète plutôt que
# de tout réécrire, pas assez pour doubler le prompt.
MAX_CHARS_REPONSE_REFUSEE = 12_000


def prompt_correction(prompt: str, fiche: Fiche, erreurs: list[str]) -> str:
    """Le prompt d'origine, plus la fiche refusée et les motifs du refus."""
    refusee = fiche.model_dump_json(exclude_none=True)[:MAX_CHARS_REPONSE_REFUSEE]
    return "\n".join(
        [
            prompt,
            "",
            "## Ta fiche précédente a été REFUSÉE",
            "```json",
            refusee,
            "```",
            "",
            "Motifs du refus :",
            *[f"- {e}" for e in erreurs],
            "",
            "Corrige ces points et rends la fiche COMPLÈTE.",
        ]
    )


# ---------------------------------------------------------------------------
# Sélection et run
# ---------------------------------------------------------------------------


def a_relire(aide: Aide) -> bool:
    f, verifiee = aide.fiche, aide.source.verified_at
    return bool(f and f.redige_le and verifiee and verifiee > f.redige_le)


def selectionner(args: argparse.Namespace, aides_dir: Path = AIDES_DIR) -> list[Path]:
    if args.slug:
        return [aides_dir / f"{s}.yaml" for s in args.slug]
    chemins = []
    for chemin in sorted(aides_dir.glob("*.yaml")):
        aide = load_aide(chemin)
        if (args.sans_fiche and aide.fiche is None) or (args.a_relire and a_relire(aide)):
            chemins.append(chemin)
    return chemins[: args.limite] if args.limite else chemins


@dataclass
class Resultat:
    slug: str
    erreurs: list[str] = field(default_factory=list)


# Corrections accordées après un refus des contrôles. Mesuré le 2026-10-04 avec
# glm-5.3-flash : sans seconde chance, 12 fiches refusées sur 24 (points omis,
# tiret cadratin, titre trop long), dont 8 à nouveau à un second lancement à froid.
MAX_CORRECTIONS = 2


def rediger(chemin: Path, client, systeme: str, compteur: Compteur, jour: date) -> Resultat:
    aide = load_aide(chemin)
    prompt = prompt_pour(chemin)
    erreurs: list[str] = []
    for _tentative in range(1 + MAX_CORRECTIONS):
        essai = client.try_complete_json(Fiche, prompt, system=systeme)
        compteur.ajouter(essai.response, "redaction")
        if essai.data is None:
            erreurs = [f"réponse inexploitable : {essai.response.error}"]
            continue
        fiche = normaliser(aide, essai.data, jour)
        erreurs = controler(aide, fiche)
        if not erreurs:
            ecrire_fiche(chemin, fiche)
            return Resultat(aide.slug, [])
        prompt = prompt_correction(prompt_pour(chemin), fiche, erreurs)
    return Resultat(aide.slug, erreurs)


def construire_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rediger_fiches.py",
        description="Rédige le bloc `fiche:` d'aides du catalogue.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--slug", action="append", default=[], help="aide à rédiger")
    mode.add_argument("--sans-fiche", action="store_true", help="les aides sans bloc `fiche:`")
    mode.add_argument("--a-relire", action="store_true", help="les fiches antérieures à la source")
    p.add_argument("--limite", type=int, default=0, help="nombre d'aides au plus")
    p.add_argument("--parallele", type=int, default=1, help="appels simultanés")
    p.add_argument("--budget-total", type=float, default=0.0, help="plafond en dollars")
    p.add_argument("--model", default=None, help="l'emporte sur LLM_MODEL_REDACTION")
    p.add_argument("--dry-run", action="store_true", help="liste la sélection, n'appelle rien")
    return p


def main(argv: list[str] | None = None) -> int:
    args = construire_parser().parse_args(argv)
    charger_env()
    chemins = selectionner(args)
    absents = [c.name for c in chemins if not c.exists()]
    if absents:
        print(f"introuvables : {absents}", file=sys.stderr)
        return 1
    try:
        modele = str(resolution_pour("redaction", args.model))
    except Exception:
        modele = None
    print(f"{len(chemins)} aide(s) · modèle {modele or 'AUCUN (LLM_MODEL_REDACTION ou --model)'}")
    if args.dry_run:
        for c in chemins:
            print(f"  {c.stem}")
        return 0
    if modele is None:
        return 1

    client = client_pour("redaction", args.model)
    systeme = consigne()
    compteur = Compteur()
    jour = date.today()
    resultats: list[Resultat] = []
    # Par vagues de `parallele` : le budget se relit entre deux vagues. Tout
    # soumettre d'un coup le rendrait décoratif, le lot serait parti avant que
    # le premier coût ne remonte.
    largeur = max(1, args.parallele)
    with ThreadPoolExecutor(max_workers=largeur) as pool:
        for i in range(0, len(chemins), largeur):
            if args.budget_total and compteur.cout_usd >= args.budget_total:
                print(
                    f"budget de {args.budget_total} $ atteint, {len(chemins) - i} aide(s) non traitée(s)"
                )
                break
            vague = {
                pool.submit(rediger, c, client, systeme, compteur, jour): c
                for c in chemins[i : i + largeur]
            }
            for futur in as_completed(vague):
                try:
                    r = futur.result()
                except Exception as e:  # une aide qui casse n'arrête pas le lot
                    r = Resultat(vague[futur].stem, [f"{type(e).__name__} : {e}"])
                resultats.append(r)
                print(f"{'ok   ' if not r.erreurs else 'ÉCHEC'} {r.slug}")
                for e in r.erreurs:
                    print(f"        {e}")

    ecrites = [r.slug for r in resultats if not r.erreurs]
    cout = f"{compteur.cout_usd:.2f} $" + (" (sous-estimé)" if compteur.cout_inconnu else "")
    print(
        f"\n{len(ecrites)} fiche(s) écrite(s) sur {len(resultats)} · "
        f"{compteur.appels} appel(s) · {cout}"
    )
    if ecrites:
        print(
            "\nÀ faire à la main :\n"
            "  uv run python scripts/lint_aides_data.py\n"
            "  git diff data/aides/   # c'est la relecture\n"
            "  puis le commit"
        )
    return 0 if len(ecrites) == len(resultats) else 1


if __name__ == "__main__":
    sys.exit(main())
