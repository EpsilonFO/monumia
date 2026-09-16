"""Audit des `raison` des aides bi-raison — aide à la relecture, lecture seule.

`raison` répond à « pour quel projet l'utilisateur doit-il voir cette aide ? »,
pas à « de quoi l'aide parle-t-elle ? » (cf. data/TYPING.md, § `raison`). Une
aide taguée `restauration_travaux` ET `valorisation_rayonnement` reste candidate
pour un projet « faire vivre le lieu » et y traîne TOUTES ses questions de
chantier : c'est le symptôme rapporté par le testeur du 2026-09-16.

Le sens d'un tag ne s'automatise pas. Ce script ne décide donc rien : il sort
une fiche de review qui range les aides bi-raison par SIGNAL, à trancher à la
main, puis c'est le diff git qui fait la revue.

    uv run python scripts/auditer_raisons.py            # fiche du jour
    uv run python scripts/auditer_raisons.py --stdout    # sans écrire

Aucune écriture dans `data/aides/` : jamais, par construction.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aides_schema import (  # noqa: E402
    AIDES_DIR,
    Aide,
    FactDef,
    load_aide,
    load_facts,
    load_pending_facts,
)

REVIEWS_DIR = Path(__file__).resolve().parent.parent / "data" / "reviews"

# Faits de CHANTIER : si tous les gates `user_fact` d'une aide portent là-dessus,
# l'aide ne sait rien demander à un projet sans travaux — signal fort que
# `valorisation_rayonnement` est de trop. Clé du fait ou fragment de clé.
MOTIFS_FAITS_TRAVAUX = re.compile(
    r"travaux|chantier|maitre_d_oeuvre|architecte|devis|autorisation_urbanisme"
    r"|diagnostic|etude_prealable|maconnerie|toiture|charpente",
    re.I,
)

# La description parle-t-elle d'une action SANS chantier ? C'est ce qui justifie
# le second tag. Volontairement large : un seul mot suffit à lever le signal,
# pour que la fiche signale peu et juste.
MOTIFS_SANS_CHANTIER = re.compile(
    r"m[ée]diation|animation|programmation|spectacle|festival|concert|exposition"
    r"|visite|accueil|public|tourisme|h[ée]bergement|insertion|formation"
    r"|emploi|num[ée]rique|sc[ée]nograph|signal[ée]tique|[ée]v[ée]nement"
    r"|manifestation|r[ée]sidence|atelier|p[ée]dagog|jeune|accessibilit",
    re.I,
)

MOTIFS_CHANTIER = re.compile(
    r"restaur|travaux|chantier|r[ée]nov|r[ée]habilit|sauvegarde|conservation"
    r"|consolidation|ma[çc]onnerie|toiture|charpente|couverture",
    re.I,
)


def charge_aides() -> dict[str, Aide]:
    return {p.stem: load_aide(p) for p in sorted(AIDES_DIR.glob("*.yaml"))}


def _texte(aide: Aide) -> str:
    return " ".join(filter(None, (aide.nom, aide.description, aide.description_longue)))


def _gates_user_fact(aide: Aide) -> list[str]:
    return [
        c.fact for c in aide.conditions if c.kind == "user_fact" and c.effect == "gate" and c.fact
    ]


class Signaux(NamedTuple):
    """Ce que la fiche sait dire d'une aide bi-raison, sans rien décider."""

    #: Tous ses gates `user_fact` portent sur des faits de travaux : elle n'a
    #: rien à demander à un projet sans chantier. Signal décisif mais rare —
    #: presque toute aide gate `statut_juridique_porteur`.
    tous_travaux: bool
    #: Faits de CHANTIER qu'elle gate, donc les questions hors sujet qu'elle
    #: coûte à un projet « faire vivre le lieu ». C'est le coût réel du tag.
    faits_travaux: list[str]
    #: Sa description parle de chantier sans nommer d'action sans chantier :
    #: le second tag n'a pas d'assise dans le texte.
    chantier_seul: bool
    #: Ce qu'elle saurait demander à un projet d'animation — le contre-argument
    #: à lire AVANT de retirer un tag.
    faits_hors_travaux: list[str]


def _signaux(aide: Aide, facts: dict[str, FactDef]) -> Signaux:
    gates = [f for f in _gates_user_fact(aide) if f in facts]
    hors_travaux = sorted({f for f in gates if not MOTIFS_FAITS_TRAVAUX.search(f)})
    texte = _texte(aide)
    return Signaux(
        tous_travaux=bool(gates) and not hors_travaux,
        faits_travaux=sorted({f for f in gates if MOTIFS_FAITS_TRAVAUX.search(f)}),
        chantier_seul=bool(MOTIFS_CHANTIER.search(texte))
        and not MOTIFS_SANS_CHANTIER.search(texte),
        faits_hors_travaux=hors_travaux,
    )


def fiche(aides: dict[str, Aide], facts: dict[str, FactDef]) -> str:
    biraison = {
        slug: aide
        for slug, aide in sorted(aides.items())
        if {"restauration_travaux", "valorisation_rayonnement"} <= set(aide.raison)
    }
    lignes: list[str] = [
        f"# Audit des `raison` bi-raison — {date.today().isoformat()}",
        "",
        "> Fiche produite par `scripts/auditer_raisons.py` (lecture seule). Elle ne",
        "> décide rien : chaque ligne se tranche à la main, puis le diff git est la",
        "> revue.",
        "",
        "Règle (data/TYPING.md, § `raison`) : une aide qui finance ou récompense des",
        "travaux porte `restauration_travaux` ; elle porte AUSSI",
        "`valorisation_rayonnement` seulement si elle finance une action SANS",
        "chantier (programmation, médiation, accueil, insertion, tourisme). Une",
        "condition d'ouverture au public ou de valorisation APRÈS les travaux ne fait",
        "pas une finalité.",
        "",
        f"{len(biraison)} aide(s) bi-raison sur {len(aides)}.",
        "",
        "Trois signaux :",
        "",
        "- `T` — tous les gates `user_fact` de l'aide portent sur des faits de travaux :",
        "  elle n'a rien à demander à un projet sans chantier. Décisif, mais rare",
        "  (presque toute aide gate `statut_juridique_porteur`).",
        "- `N` — combien de faits de CHANTIER elle gate, donc les questions hors sujet",
        "  qu'elle coûte à un projet « faire vivre le lieu ». C'est le coût réel du tag :",
        "  une aide bi-raison à `N = 0` ne gêne personne, la relire est sans urgence.",
        "- `D` — sa description parle de chantier sans nommer d'action sans chantier :",
        "  le second tag n'a pas d'assise dans le texte.",
        "",
        "La colonne « hors travaux » dit ce que l'aide saurait demander à un projet",
        "d'animation : c'est le contre-argument à lire AVANT de retirer un tag.",
        "",
        "| Aide | Type | T | N | D | Faits hors travaux | Verdict (à remplir) |",
        "|---|---|:-:|--:|:-:|---|---|",
    ]
    signaux = {slug: _signaux(aide, facts) for slug, aide in biraison.items()}
    for slug, aide in biraison.items():
        s = signaux[slug]
        libelles = [f"`{f}`" for f in s.faits_hors_travaux][:6]
        lignes.append(
            f"| `{slug}` | {aide.type} | {'✓' if s.tous_travaux else ''} "
            f"| {len(s.faits_travaux)} | {'✓' if s.chantier_seul else ''} "
            f"| {', '.join(libelles) or '—'} | |"
        )

    # À relire en premier : celles dont le tag COÛTE des questions et dont le
    # texte ne nomme aucune action sans chantier. Les deux ensemble, parce que
    # `D` seul n'est qu'un défaut de rédaction et `N` seul peut être légitime.
    a_trancher = [slug for slug, s in signaux.items() if s.chantier_seul and s.faits_travaux]
    lignes += [
        "",
        f"## Les {len(a_trancher)} aides à relire en premier",
        "",
        "Signal `D` ET au moins un fait de chantier gaté : le tag coûte des questions",
        "hors sujet, et le texte ne nomme aucune action sans chantier pour le justifier.",
        "",
    ]
    for slug in a_trancher:
        aide = biraison[slug]
        s = signaux[slug]
        description = " ".join((aide.description or "").split())[:300]
        lignes += [
            f"### `{slug}`",
            "",
            f"- **{aide.nom}** ({aide.organisme}) — {aide.type}",
            f"- {description}",
            f"- Faits de chantier gatés : {', '.join(f'`{f}`' for f in s.faits_travaux)}",
            "",
        ]
    return "\n".join(lignes) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stdout", action="store_true", help="imprimer sans écrire la fiche de review"
    )
    args = parser.parse_args()

    aides = charge_aides()
    facts = {**load_facts(), **load_pending_facts()}
    texte = fiche(aides, facts)
    if args.stdout:
        print(texte)
        return
    chemin = REVIEWS_DIR / f"{date.today().isoformat()}-audit-raisons.md"
    chemin.write_text(texte, encoding="utf-8")
    print(f"fiche écrite : {chemin.relative_to(chemin.parent.parent.parent)}")


if __name__ == "__main__":
    main()
