"""
Étage C, orchestration : du triage à l'écriture du YAML.

Ce module fait le lien entre l'étage B (qui a retenu une aide) et les deux
moitiés de l'étage C : `veille_llm` construit et passe l'appel, `veille_apply`
valide et édite. Il ne contient donc ni prompt ni logique d'édition — seulement
la conduite : un appel, au plus une nouvelle tentative, l'écriture, et le
ré-archivage de la preuve.

Quatre décisions y sont prises, et elles méritent d'être lues avant le code :

1. UNE seule nouvelle tentative, et seulement pour ce que le modèle a lui-même
   produit (JSON, schéma, références, citations). Un échec d'édition ou de
   différence profonde est NOTRE bug : le relancer brûlerait des jetons pour
   échouer pareil.

2. Un `changement_majeur` auto-déclaré fait basculer l'aide en
   ESCALADE_INGESTION. C'est la porte de sortie prévue : le modèle a le droit
   de dire « ça me dépasse », et c'est un bon résultat, pas un échec.

3. Au-delà de trois conditions nouvelles d'un coup, on escalade au lieu
   d'appliquer. Le problème n'est alors pas que la source a changé, mais que
   la fiche était incomplète — et une ré-ingestion type et vérifie, là où la
   veille ne ferait qu'empiler des conditions `untyped`.

4. Une aide réellement modifiée voit ses pages RÉ-ARCHIVÉES. Sans ça le
   pipeline n'est pas idempotent : la baseline resterait l'ancienne page, le
   passage suivant rejouerait le même diff, et les citations qu'on vient
   d'écrire seraient introuvables dans l'archive — comptées en dette de quotes
   par `veille_quotes_audit.py`. La preuve doit voyager avec la modification,
   dans le même commit.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aides_schema import AIDES_DIR, Aide

sys.path.insert(0, str(Path(__file__).resolve().parent))

from snapshot_source import NAME_RE, write_md_snapshot
from veille_analyze import AideAnalysis, resume_diff
from veille_apply import appliquer
from veille_collect import AideCollect
from veille_llm import ModelSpec, build_prompt, call, system_pour

# Plafond d'appels par passage. Un garde-fou de coût, mais surtout de RELECTURE :
# aucun humain ne relit sérieusement quarante diffs d'affilée, et la revue du
# `git diff` est le seul contrôle qui empêche une hallucination d'entrer dans
# les données. Aucun modèle mesuré n'atteignant zéro faux changement, ce plafond
# n'est pas provisoire.
MAX_LLM_DEFAUT = 20

# Lignes de diff montrées au modèle. Au-delà, ce n'est plus un changement
# circonscrit — l'étage B aurait dû escalader.
MAX_LIGNES_DIFF = 200

# Conditions nouvelles acceptées en une fois. Au-delà, ce n'est plus une
# retouche de règlement : la fiche était incomplète, et c'est une ré-ingestion
# qu'il lui faut — avec le typage et la vérification adversariale qui vont avec.
# Mesuré au run pilote : `region-bretagne-edifices-proteges-prives` en proposait
# HUIT d'un coup, toutes correctement citées, parce que la page consultée est
# plus fournie que la fiche. Les appliquer aurait fait entrer huit conditions
# non typées par la petite porte.
MAX_AJOUTS_CONDITIONS = 3

# Réponse rejetée renvoyée au modèle : assez pour qu'il se relise, pas assez
# pour doubler le prompt.
MAX_CHARS_REPONSE_REJETEE = 4_000

Etat = Literal["applique", "inchange", "escalade", "echec"]


@dataclass
class MajResult:
    """Sort d'une aide passée à l'étage C."""

    slug: str
    etat: Etat = "echec"
    modele: str = ""
    raison: str = ""
    resume: str = ""
    champs: list[str] = field(default_factory=list)
    erreurs: list[str] = field(default_factory=list)
    # Snapshots ré-écrits, pour que le rapport dise ce qui part au commit.
    snapshots: list[str] = field(default_factory=list)
    cosmetiques: int = 0
    tentatives: int = 0
    cout_usd: float = 0.0
    latence_s: float = 0.0
    etape_echec: str | None = None
    # Dernière réponse du modèle, conservée UNIQUEMENT en cas d'échec. Sans
    # elle, un rejet n'est pas rejouable : on connaît le motif, jamais ce qui
    # l'a provoqué. Mesuré au run pilote, où un échec d'édition sur `fctva` a
    # dû être reconstitué à la main.
    reponse_rejetee: str = ""

    @property
    def symbole(self) -> str:
        return {"applique": "→", "inchange": "=", "escalade": "✗", "echec": "!"}[self.etat]


def prompt_correction(prompt: str, reponse: str, erreurs: list[str]) -> str:
    """Prompt de la seconde tentative : le premier, plus le motif du rejet.

    Un tour supplémentaire dans le même message plutôt qu'un vrai dialogue :
    les adaptateurs de `veille_llm` sont volontairement mono-tour, et la
    correction attendue est mécanique (citer verbatim, retirer un champ hors
    périmètre) — pas une négociation.
    """
    return "\n".join(
        [
            prompt,
            "",
            "## Ta réponse précédente a été REJETÉE",
            "```json",
            reponse.strip()[:MAX_CHARS_REPONSE_REJETEE],
            "```",
            "",
            "Motifs du rejet :",
            *[f"- {e}" for e in erreurs[:10]],
            "",
            "Corrige et rends le JSON COMPLET. Un changement que tu ne peux pas "
            "justifier par une citation verbatim du contenu frais ci-dessus doit "
            "être retiré : une réponse vide vaut mieux qu'une réponse inventée.",
        ]
    )


def mettre_a_jour(
    aide: Aide,
    an: AideAnalysis,
    collect: AideCollect,
    spec: ModelSpec,
    *,
    aujourd_hui: date,
    dry_run: bool = False,
    chemin: Path | None = None,
) -> MajResult:
    """Un appel (au plus deux) au modèle, puis l'écriture si tout passe."""
    res = MajResult(slug=aide.slug, modele=spec.alias)
    chemin = chemin or AIDES_DIR / f"{aide.slug}.yaml"

    documents = collect.fresh_docs()
    if not documents:
        res.raison = "aucun contenu frais fouillable : rien à soumettre au modèle"
        res.etape_echec = "collecte"
        return res

    prompt = build_prompt(
        aide, documents, resume_diff(an, max_lignes=MAX_LIGNES_DIFF), aujourd_hui=aujourd_hui
    )
    system = system_pour(spec)

    applied = None
    reponse = ""
    relance_vide, corrections = False, 0
    while True:
        appel = call(spec, system, prompt)
        res.tentatives += 1
        res.cout_usd += appel.cost_usd or 0.0
        res.latence_s += appel.latency_s
        if not appel.ok:
            if appel.reponse_vide and not relance_vide:
                # Le fournisseur a répondu sans rien dire. Mesuré au run pilote :
                # 114 jetons de sortie facturés, `finish_reason: stop`, contenu
                # vide, en 2,4 s. Une relance à l'identique suffit. Les vraies
                # erreurs d'API (401, 429) ne sont PAS relancées : elles
                # échoueraient pareil et coûteraient un aller-retour par aide.
                relance_vide = True
                continue
            res.raison = f"appel au modèle en échec : {appel.error}"
            res.erreurs = [appel.error or "réponse vide"]
            res.etape_echec = "appel"
            return res
        reponse = appel.text
        applied = appliquer(reponse, aide, chemin, documents, aujourd_hui=aujourd_hui.isoformat())
        if applied.ok or not applied.rattrapable or corrections:
            break
        corrections += 1
        prompt = prompt_correction(prompt, reponse, applied.erreurs)

    assert applied is not None
    res.cosmetiques = applied.cosmetiques
    if applied.output is not None:
        res.resume = applied.output.resume.strip()

    if not applied.ok:
        res.erreurs = applied.erreurs
        res.etape_echec = applied.etape
        res.reponse_rejetee = reponse
        if applied.output is not None and applied.output.changement_majeur:
            res.etat = "escalade"
            res.raison = "changement majeur déclaré par le modèle : " + (
                applied.output.raison_changement_majeur or "sans raison fournie"
            )
        else:
            premiere = applied.erreurs[0] if applied.erreurs else "sans détail"
            res.raison = f"validation en échec ({applied.etape}) : {premiere}"
        return res

    ajouts = sum(1 for c in applied.output.conditions if c.op == "add") if applied.output else 0
    if ajouts > MAX_AJOUTS_CONDITIONS:
        res.etat = "escalade"
        res.raison = (
            f"{ajouts} conditions nouvelles proposées (seuil {MAX_AJOUTS_CONDITIONS}) : "
            "la fiche est incomplète, pas périmée — ré-ingestion plutôt que retouche"
        )
        return res

    if applied.texte == chemin.read_text(encoding="utf-8"):
        # Le cas NORMAL et le plus fréquent : la page a bougé sur autre chose que
        # le mandat de la veille. Rien à écrire, et surtout pas de fichier
        # réécrit à l'identique.
        res.etat = "inchange"
        res.raison = res.resume or "le modèle ne propose aucun changement dans son mandat"
        return res

    res.etat = "applique"
    res.champs = applied.champs_touches
    res.raison = res.resume or ", ".join(applied.champs_touches)
    if not dry_run:
        assert applied.texte is not None
        chemin.write_text(applied.texte, encoding="utf-8")
        res.snapshots = rafraichir_snapshots(an, collect)
    return res


def rafraichir_snapshots(an: AideAnalysis, collect: AideCollect) -> list[str]:
    """Ré-archive les pages qui ont motivé la mise à jour. Voir le point 4 en tête.

    Seules les pages dont le diff a réellement bougé sont ré-écrites : le bruit
    de gabarit ayant déjà été retiré par l'étage B, `data/sources/` ne gonfle
    pas d'un snapshot par passage et par portail.

    Une page récupérée via proxy est exclue : son texte ne passe pas par la même
    chaîne de conversion que les baselines, et l'archiver ferait diverger tous
    les diffs suivants pour une raison purement technique.
    """
    ecrits: list[str] = []
    for u in an.urls:
        res = collect.fetched.get(u.murl.url)
        if not (u.a_change and res and res.ok and res.raw_text and not res.via_proxy):
            continue
        # Le label compose un nom de fichier. Ceux du dépôt viennent déjà de
        # `snapshot_source`, donc valides — mais un fichier renommé à la main
        # n'a pas à faire échouer une mise à jour par ailleurs correcte.
        label = u.murl.label if u.murl.label and NAME_RE.fullmatch(u.murl.label) else None
        ecrits.append(write_md_snapshot(an.slug, u.murl.url, res.raw_text, label=label).name)
    return ecrits


__all__ = [
    "MAX_LLM_DEFAUT",
    "Etat",
    "MajResult",
    "mettre_a_jour",
    "prompt_correction",
    "rafraichir_snapshots",
]
