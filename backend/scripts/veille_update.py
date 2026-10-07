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

3. Une condition nouvelle ou disparue escalade, dès la première (décision du
   2026-10-04). C'est le changement que la veille existe pour voir, et le
   seul qu'elle ne sait pas écrire : ajoutée en `untyped`, une condition
   retirait l'aide entière du moteur ; annotée « disparue », elle continuait
   d'écarter des porteurs. Une ré-ingestion type, vérifie et coûte quelques
   centimes.

4. Une aide soumise au modèle voit ses pages RÉ-ARCHIVÉES, qu'il ait proposé
   une retouche ou non — sauf si Jev juge son « inchangé » suspect (point 5). Sans ça le pipeline n'est pas idempotent : la baseline
   resterait l'ancienne page, le passage suivant rejouerait le même diff — et
   une aide dont la page a bougé hors mandat repaierait un appel chaque jour.
   Pour une fiche modifiée, la preuve doit en plus voyager avec la
   modification, dans le même commit, sinon les citations fraîches seraient
   comptées en dette par `veille_quotes_audit.py`.

5. Jev (`veille_arbitre`), quand ses seuils sont réglés, encadre l'appel. AVANT :
   un diff qu'il juge hors mandat ne coûte pas d'appel au LLM, l'aide passe
   `inchange` et sa page est ré-archivée. APRÈS un « inchangé » : s'il juge que
   le changement touche le mandat, résumé du LLM à l'appui, la page n'est PAS
   ré-archivée et l'aide sort `suspect`. Un ré-archivage à tort efface le
   changement pour toujours ; une fausse alerte coûte une relecture.
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

from snapshot_source import NAME_RE, write_docx_snapshot, write_md_snapshot, write_pdf_snapshot
from veille_analyze import AideAnalysis, resume_diff
from veille_apply import appliquer
from veille_arbitre import Arbitre, ErreurDecision, note
from veille_collect import AideCollect, est_pdf
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

# Réponse rejetée renvoyée au modèle : assez pour qu'il se relise, pas assez
# pour doubler le prompt.
MAX_CHARS_REPONSE_REJETEE = 4_000

Etat = Literal["applique", "inchange", "escalade", "echec", "suspect"]


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
    # Cumulés sur TOUS les appels de l'aide, relance de correction comprise :
    # c'est la consommation réelle du passage, pas celle du dernier appel.
    tokens_in: int = 0
    tokens_out: int = 0
    latence_s: float = 0.0
    etape_echec: str | None = None
    # Empreinte du changement soumis (`veille_aides.empreinte_changement`),
    # mémorisée au manifeste en cas de refus pour ne pas repayer le même appel.
    empreinte: str = ""
    # Dernière réponse du modèle, conservée UNIQUEMENT en cas d'échec. Sans
    # elle, un rejet n'est pas rejouable : on connaît le motif, jamais ce qui
    # l'a provoqué. Mesuré au run pilote, où un échec d'édition sur `fctva` a
    # dû être reconstitué à la main.
    reponse_rejetee: str = ""
    # Notes de Jev (probabilité que le changement touche le mandat), par usage :
    # `filtre` avant l'appel, `garde` après un « inchangé ».
    jev: dict[str, float] = field(default_factory=dict)
    jev_cout_usd: float = 0.0
    jev_erreur: str = ""
    # Écartée par le filtre de Jev : aucun appel au LLM, ne compte pas sous
    # le plafond `--max-llm`.
    ecartee_par_jev: bool = False
    # Refus repris du manifeste, sans nouvel appel : un `suspect` reste au
    # rapport chaque semaine tant que sa page n'est pas ré-archivée.
    memorise: bool = False
    depuis: str = ""
    # Page ré-archivée sur demande humaine (`veille_aides.py --rearchiver`).
    rearchivee_a_la_main: bool = False

    @property
    def symbole(self) -> str:
        return {
            "applique": "→",
            "inchange": "=",
            "escalade": "✗",
            "echec": "!",
            "suspect": "?",
        }[self.etat]


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
    arbitre: Arbitre | None = None,
) -> MajResult:
    """Un appel (au plus deux) au modèle, puis l'écriture si tout passe."""
    res = MajResult(slug=aide.slug, modele=spec.alias)
    chemin = chemin or AIDES_DIR / f"{aide.slug}.yaml"

    documents = documents_a_soumettre(an, collect)
    if not documents:
        res.raison = "aucun contenu frais fouillable : rien à soumettre au modèle"
        res.etape_echec = "collecte"
        return res

    # Calculé UNE fois : l'ancrage des citations doit juger sur le diff
    # exactement tel que le modèle l'a vu. Le recalculer risquerait de refuser
    # une citation issue d'une ligne écartée par la troncature, ou d'en accepter
    # une que le modèle n'avait pas sous les yeux.
    diff = resume_diff(an, max_lignes=MAX_LIGNES_DIFF)

    if filtrable(an, diff, arbitre):
        assert arbitre is not None and arbitre.seuils.filtre is not None
        p = _juger(res, "filtre", arbitre, aide, diff)
        if p is not None and p < arbitre.seuils.filtre:
            res.etat = "inchange"
            res.ecartee_par_jev = True
            res.raison = f"bruit écarté par Jev ({note(p)})"
            if not dry_run:
                res.snapshots = rafraichir_snapshots(an, collect, jour=aujourd_hui)
            return res

    prompt = build_prompt(aide, documents, diff, aujourd_hui=aujourd_hui)
    system = system_pour(spec)

    applied = None
    reponse = ""
    relance_vide, corrections = False, 0
    while True:
        appel = call(spec, system, prompt)
        res.tentatives += 1
        res.cout_usd += appel.cost_usd or 0.0
        res.tokens_in += appel.input_tokens
        res.tokens_out += appel.output_tokens
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
        applied = appliquer(
            reponse,
            aide,
            chemin,
            documents,
            aujourd_hui=aujourd_hui.isoformat(),
            diff=diff,
            escalader_structure=True,
            lint_complet=True,
        )
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
        elif applied.etape == "structure":
            # Ce que la veille existe d'abord pour voir : la source a gagné ou
            # perdu un critère. Rien n'est écrit ; une ré-ingestion retype et
            # revérifie l'aide entière, pour quelques centimes.
            res.etat = "escalade"
            res.raison = " ; ".join(applied.erreurs) + " — ré-ingestion"
        elif applied.etape == "ancrage":
            # Pas un rejet sec : la proposition peut être juste et refléter une
            # divergence réelle entre la fiche et la source — simplement pas un
            # CHANGEMENT de la source, donc hors mandat de la veille. Elle part
            # à la relecture humaine plutôt qu'à la poubelle.
            res.etat = "escalade"
            res.raison = (
                f"{len(applied.erreurs)} citation(s) non ancrée(s) dans le diff : "
                "la fiche diverge peut-être de la source, mais la source n'a pas "
                "changé sur ces points — relecture humaine ou /ingest-aide"
            )
        else:
            premiere = applied.erreurs[0] if applied.erreurs else "sans détail"
            res.raison = f"validation en échec ({applied.etape}) : {premiere}"
        return res

    if applied.texte == chemin.read_text(encoding="utf-8"):
        # Le cas NORMAL et le plus fréquent : la page a bougé sur autre chose que
        # le mandat de la veille. Rien à écrire dans la fiche, et surtout pas de
        # fichier réécrit à l'identique.
        #
        # Mais la page, elle, EST ré-archivée : sans ça, la baseline restait
        # l'ancienne version, l'étage B rediffait le même écart au passage
        # suivant, et l'aide repayait un appel au modèle chaque jour pour la même
        # réponse — indéfiniment. Le verdict du modèle vaut pour la page qu'il a
        # lue ; c'est donc elle qui devient la baseline.
        res.etat = "inchange"
        res.raison = res.resume or "le modèle ne propose aucun changement dans son mandat"
        if arbitre is not None and arbitre.seuils.garde is not None and diff:
            p = _juger(res, "garde", arbitre, aide, diff, resume=res.resume)
            if p is not None and p >= arbitre.seuils.garde:
                # Pas de ré-archivage : la baseline reste l'ancienne page, le
                # changement reste visible au passage suivant.
                res.etat = "suspect"
                res.raison = f"changement possible non appliqué (Jev {note(p)}) : " + (
                    res.resume or "le modèle n'a rien proposé"
                )
                return res
        if not dry_run:
            res.snapshots = rafraichir_snapshots(an, collect, jour=aujourd_hui)
        return res

    res.etat = "applique"
    res.champs = applied.champs_touches
    res.raison = res.resume or ", ".join(applied.champs_touches)
    if not dry_run:
        assert applied.texte is not None
        chemin.write_text(applied.texte, encoding="utf-8")
        res.snapshots = rafraichir_snapshots(an, collect, jour=aujourd_hui)
    return res


def documents_a_soumettre(an: AideAnalysis, collect: AideCollect) -> list[tuple[str, str, str]]:
    """Les documents montrés au modèle : seules les pages qui ont bougé.

    Mesuré au banc de l'étage C sur le passage du 2026-10-04 (or-glm, 33
    changements réels) : toutes les pages de l'aide (16 000 jetons en moyenne,
    règlements PDF inchangés compris) ou les seules pages modifiées, la veille
    perd 2 à 3 changements dans les deux cas, l'écart restant dans la variance
    d'un essai à l'autre (1 à 4). Mais l'appel coûte 30 % de moins. Prévenir
    dans le prompt que les autres pages n'ont pas bougé faisait plutôt pire
    (3 à 4) : le modèle concluait plus souvent « inchangé ».
    Sans page modifiée (une citation disparue, rien d'autre), tout part.
    """
    docs = collect.fresh_docs()
    modifiees = {u.murl.url for u in an.urls if u.a_change}
    return [d for d in docs if d[0] in modifiees] or docs


def filtrable(an: AideAnalysis, diff: str, arbitre: Arbitre | None) -> bool:
    """Le filtre de Jev peut-il dispenser cette aide d'appel au LLM ?

    Jamais quand un autre signal que le diff parle : une citation disparue de
    la source, une date limite dépassée sur une page qui a bougé (le cas même
    d'un report d'échéance), ou une refonte que Jev vient de rétrograder — le
    plan l'envoie à l'étage C, pas au ré-archivage.
    """
    return (
        arbitre is not None
        and arbitre.seuils.filtre is not None
        and bool(diff)
        and not an.regressions
        and an.date_limite_perimee is None
        and not an.retrogradee
    )


def _juger(
    res: MajResult,
    usage: str,
    arbitre: Arbitre,
    aide: Aide,
    diff: str,
    *,
    resume: str | None = None,
) -> float | None:
    """Une note de Jev, ou `None` s'il est en panne : on fait alors sans lui."""
    try:
        j = arbitre.mandat(aide, diff, resume=resume)
    except ErreurDecision as exc:
        res.jev_erreur = str(exc)
        return None
    res.jev[usage] = j.p
    res.jev_cout_usd += j.cout_usd
    return j.p


def rafraichir_snapshots(an: AideAnalysis, collect: AideCollect, *, jour: date) -> list[str]:
    """Ré-archive les pages qui ont motivé la mise à jour. Voir le point 4 en tête.

    Seules les pages dont le diff a réellement bougé sont ré-écrites : le bruit
    de gabarit ayant déjà été retiré par l'étage B, `data/sources/` ne gonfle
    pas d'un snapshot par passage et par portail.

    Une page récupérée via proxy est exclue : son texte ne passe pas par la même
    chaîne de conversion que les baselines, et l'archiver ferait diverger tous
    les diffs suivants pour une raison purement technique.

    `jour` est la date du passage, celle-là même qui date la fiche : un passage
    entamé avant minuit ne doit pas laisser un snapshot du lendemain à côté d'un
    `verified_at` de la veille.
    """
    ecrits: list[str] = []
    for u in an.urls:
        res = collect.fetched.get(u.murl.url)
        if not (u.a_change and res and res.ok and not res.via_proxy):
            continue
        # Le label compose un nom de fichier. Ceux du dépôt viennent déjà de
        # `snapshot_source`, donc valides — mais un fichier renommé à la main
        # n'a pas à faire échouer une mise à jour par ailleurs correcte.
        label = u.murl.label if u.murl.label and NAME_RE.fullmatch(u.murl.label) else None
        if res.raw_text:
            ecrits.append(
                write_md_snapshot(an.slug, u.murl.url, res.raw_text, label=label, jour=jour).name
            )
        elif res.docx and res.content:
            # Un .docx s'archive par son texte, comme à l'ingestion : c'est lui
            # que la veille compare (cf. `write_docx_snapshot`).
            chemin, _texte = write_docx_snapshot(
                an.slug, res.content, url=u.murl.url, label=label, jour=jour
            )
            ecrits.append(chemin.name)
        elif est_pdf(res.content):
            # Un règlement PDF modifié est ré-archivé avec son sidecar de
            # provenance : c'est lui qui redeviendra la baseline, texte compris.
            # Les autres binaires (tableurs, archives) ne le sont pas : on ne
            # sait pas les relire, donc pas les comparer autrement que par sha.
            assert res.content is not None
            ecrits.append(
                write_pdf_snapshot(
                    an.slug, res.content, url=u.murl.url, label=label, jour=jour
                ).name
            )
    return ecrits


__all__ = [
    "MAX_LLM_DEFAUT",
    "documents_a_soumettre",
    "filtrable",
    "Etat",
    "MajResult",
    "mettre_a_jour",
    "prompt_correction",
    "rafraichir_snapshots",
]
