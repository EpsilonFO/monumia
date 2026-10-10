"""La veille du catalogue dans le paquet (incrément I2, sections 4 et 10 d'`architecture.md`).

Commande, depuis `backend/` d'une copie jetable du dépôt tant que le registre
laisse la veille à l'ancienne chaîne :

    uv run python -m catalogue veille --journal <dossier>

Ce qui est repris tel quel de l'ancienne veille, parce que mesuré :
- la collecte et l'analyse (`veille_collect.collect`, `veille_analyze.analyze_all`,
  les neuf règles et le gabarit calculé sur tout le parc) ;
- l'appel du mandat, dans son état exact (même consigne, schéma dans la
  consigne, `json_object`, température 0, effort `medium`, 16 000 jetons), une
  relance de correction, la validation et l'édition par plages de
  `veille_apply.appliquer` avec ses deux garde-fous ;
- la garde de Jev (`veille_arbitre.QUESTIONS_MANDAT`, `etat_mandat`).

Ce qui change :
- **La référence de comparaison est `base`**, l'instantané contre lequel le YAML
  a été validé, lu dans le journal, et non le dernier fichier archivé. Elle
  n'avance que sur une retouche écrite, un « inchangé » que la garde note sous
  le bas de la zone prudente (0,05), ou une réponse de Félix. Entre 0,05 et le
  seuil d'escalade (0,45), elle reste : le changement ressort la semaine
  suivante, sans coût puisque les verdicts sont mémorisés, et rien n'est perdu.
- **Une panne n'est jamais un jugement** : un appel en panne laisse l'aide due,
  sans refus mémorisé ; Jev en panne, la référence reste.
- **Ce que le code ne peut pas trancher devient une case de Félix** au lieu
  d'une écriture : valeur déduite, retouche d'une condition, escalade (jusqu'à
  la ré-extraction d'I4), échéance périmée, page injoignable deux fois.
- Chaque décision, panne et case est au journal, avec le modèle servi et le
  coût facturé ; une décision à entrées identiques est reprise sans appel.
- Le manifeste `veille-state.yaml` est réécrit par projection inverse
  (`veille_aides.update_manifest`), pour que l'ancienne veille, relancée,
  retrouve les mêmes changements en attente.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import veille_aides
from veille_analyze import AideAnalysis, _panne_generalisee, analyze_all, resume_diff
from veille_apply import ApplyResult, appliquer
from veille_arbitre import QUESTIONS_MANDAT, etat_mandat
from veille_collect import (
    SOURCES_DIR,
    AideCollect,
    MonitoredUrl,
    charger_yaml,
    cle_url,
    corps_binaire,
    empreinte_texte,
    est_http,
    pdf_lisible,
    pdf_to_text,
    url_d_origine,
)
from veille_llm import SYSTEM, build_prompt, json_schema
from veille_text import parse_front_matter
from veille_update import (
    MAX_LIGNES_DIFF,
    MajResult,
    documents_a_soumettre,
    prompt_correction,
    rafraichir_snapshots,
)

from aides_schema import AIDES_DIR, DATA_DIR, Aide, load_aide
from catalogue import cases as cases_mod
from catalogue import controles
from catalogue.budget import Budget, BudgetEpuise
from catalogue.cases import Case
from catalogue.journal import Evenement, Journal, Vue, cle, empreinte
from catalogue.openrouter import Client, Panne
from catalogue.registre import Registre

BACKEND = Path(__file__).resolve().parents[1]
BLOBS = BACKEND / ".cache" / "catalogue" / "blobs"
REVIEWS = DATA_DIR / "reviews"
# Version de l'étape : elle entre dans les clés de mémorisation, pour qu'un
# changement de la conduite de l'étage C ne reprenne pas les verdicts d'avant.
VERSION = "veille@1"
JETONS_SORTIE = 16_000
# Consigne du mandat telle que l'ancienne veille l'envoie à un fournisseur sans
# sortie structurée native (`veille_llm.system_pour`) : le schéma y est joint.
CONSIGNE = (
    SYSTEM
    + "\n\nTa réponse doit valider ce schéma JSON, sans clé supplémentaire :\n"
    + json.dumps(json_schema(), ensure_ascii=False, indent=1)
)
EMPREINTE_CONSIGNE = empreinte(CONSIGNE)
EMPREINTE_QUESTIONS = empreinte(json.dumps(QUESTIONS_MANDAT, sort_keys=True, ensure_ascii=False))

OPTIONS_ESCALADE = {
    "rearchiver": "la page a changé sans effet sur la fiche, ou je l'ai corrigée : la référence avance",
    "reextraire": "à ré-extraire (incrément I4)",
}
OPTIONS_PROPOSITION = {
    "appliquer": "la retouche proposée est juste : l'écrire",
    "rearchiver": "ne pas l'écrire, la page devient la référence",
}


# ------------------------------------------------------------------ référence


def bases_en_vigueur(evenements: list[Evenement]) -> dict[tuple[str, str], dict[str, Any]]:
    """La référence de chaque (aide, URL) : le dernier événement `base`, importé ou non."""
    bases: dict[tuple[str, str], dict[str, Any]] = {}
    for e in evenements:
        if e.decision == "base" and e.type in ("import", "decision"):
            bases[(e.objet, e.donnees.get("cle_url", ""))] = e.donnees
    return bases


def baseline_de(slug: str, fichier: str, sources: Path = SOURCES_DIR) -> dict[str, Any] | None:
    """Les champs de `MonitoredUrl` qui décrivent l'instantané `fichier`, lu comme la veille le lit.

    Même lecture que `veille_collect._snapshot_baselines`, pour un fichier donné
    au lieu du plus récent : corps sans en-tête d'une page, texte d'un PDF
    lisible, aucun corps pour un proxy ou un contenu binaire.
    """
    chemin = sources / slug / fichier
    if fichier.endswith(".pdf"):
        sidecar = chemin.with_name(chemin.name + ".meta.yaml")
        if not (chemin.is_file() and sidecar.is_file()):
            return None
        meta = charger_yaml(sidecar.read_text(encoding="utf-8")) or {}
        texte = pdf_to_text(chemin)
        return {
            "baseline_path": chemin,
            "baseline_sha": meta.get("sha256"),
            "baseline_body": texte if pdf_lisible(texte) else None,
            "baseline_empreinte_texte": empreinte_texte(texte),
            "is_binary": True,
        }
    if not chemin.is_file():
        return None
    meta, corps = parse_front_matter(chemin.read_text(encoding="utf-8"))
    url = meta.get("url")
    if not est_http(url):
        return None
    comparable = url_d_origine(str(url))[1] != "proxy" and not corps_binaire(corps)
    return {
        "baseline_path": chemin if comparable else None,
        "baseline_sha": meta.get("sha256") if comparable else None,
        "baseline_body": corps if comparable else None,
        "baseline_empreinte_texte": None,
        "is_binary": False,
    }


def appliquer_bases(
    collects: dict[str, AideCollect],
    bases: dict[tuple[str, str], dict[str, Any]],
    sources: Path = SOURCES_DIR,
) -> int:
    """Remplace la référence du dernier archivé par `base`, là où elles diffèrent. Rend le nombre d'URL."""
    remplacees = 0
    for slug, col in collects.items():
        nouvelles: list[MonitoredUrl] = []
        for m in col.urls:
            b = bases.get((f"a:{slug}", cle_url(m.url)))
            fichier = (b or {}).get("fichier")
            actuel = m.baseline_path.name if m.baseline_path else None
            if m.role == "formulaire" or not fichier or fichier == actuel:
                nouvelles.append(m)
                continue
            champs = baseline_de(slug, fichier, sources)
            if champs is None:
                nouvelles.append(m)
                continue
            nouvelles.append(replace(m, **champs))
            remplacees += 1
        col.urls = nouvelles
    return remplacees


def garder_frais(an: AideAnalysis, col: AideCollect, blobs: Path) -> dict[str, str]:
    """Range les pages fraîches qui ont changé, par empreinte, tant que `base` n'avance pas."""
    gardes: dict[str, str] = {}
    for u in an.urls:
        res = col.fetched.get(u.murl.url)
        if not (u.a_change and res and res.ok):
            continue
        contenu = res.content if res.content is not None else (res.raw_text or "").encode()
        if contenu:
            gardes[u.murl.url] = garder_blob(blobs, contenu)
    return gardes


# ------------------------------------------------------------------ résultats


@dataclass
class Resultat:
    """Ce que la veille a fait d'une aide pendant un passage."""

    slug: str
    statut: str
    issue: str
    raison: str = ""
    champs: list[str] = field(default_factory=list)
    garde: float | None = None
    cout_usd: float = 0.0
    cases: list[Case] = field(default_factory=list)
    snapshots: list[str] = field(default_factory=list)
    texte: str | None = None
    panne: str | None = None
    memorise: bool = False

    @property
    def base_avance(self) -> bool:
        return self.issue in ("retouche", "inchange", "rearchivee")


@dataclass
class Contexte:
    registre: Registre
    journal: Journal
    vue: Vue
    client: Client | None
    budget: Budget
    run: str
    aujourd_hui: dt.date
    blobs: Path = BLOBS
    ecrire: bool = True
    sources: Path = SOURCES_DIR
    # (slug, contenu du YAML) pour rejouer sur une version d'avant ; sinon le fichier.
    chemin_yaml: Callable[[str], Path] = lambda slug: AIDES_DIR / f"{slug}.yaml"

    def consigner(self, e: Evenement) -> Evenement:
        e = replace(e, run=self.run) if e.run is None else e
        e = self.journal.ajouter(e)
        self.vue.prendre(e)
        return e


def empreinte_changement(an: AideAnalysis) -> str:
    return veille_aides.empreinte_changement(an)


# ------------------------------------------------------------------ étage C


def _appel_mandat(ctx: Contexte, prompt: str, slug: str) -> tuple[str, float | None, str]:
    """Un appel du mandat : (texte, coût facturé, modèle servi). Lève `Panne` ou `BudgetEpuise`."""
    assert ctx.client is not None
    m = ctx.registre.modele("veille")
    reservation = ctx.budget.reserver(
        m.plafond_usd(len(CONSIGNE + prompt) // 2, JETONS_SORTIE), f"veille {slug}"
    )
    cout: float | None = None
    try:
        r = ctx.client.completer(
            m.nom,
            [{"role": "system", "content": CONSIGNE}, {"role": "user", "content": prompt}],
            objet_json=True,
            temperature=0,
            effort=m.effort,
            max_tokens=JETONS_SORTIE,
            acceptes=m.acceptes,
            delai_s=m.delai_s,
            role="veille",
        )
        cout = r.cout_usd
        return r.texte, r.cout_usd, r.modele_servi
    finally:
        ctx.budget.regler(reservation, cout)


def garder_blob(blobs: Path, contenu: bytes) -> str:
    """Range un contenu par son empreinte (écriture atomique) et rend l'empreinte."""
    sha = hashlib.sha256(contenu).hexdigest()
    blobs.mkdir(parents=True, exist_ok=True)
    cible = blobs / sha
    if not cible.exists():
        temporaire = blobs / f".{sha}.{dt.datetime.now().timestamp()}"
        temporaire.write_bytes(contenu)
        temporaire.replace(cible)
    return sha


def _garde(ctx: Contexte, aide: Aide, etat: dict[str, Any]) -> tuple[float, float | None, str]:
    """La probabilité que le changement touche le mandat. Lève `Panne` ou `BudgetEpuise`."""
    assert ctx.client is not None
    m = ctx.registre.modele("decision")
    reservation = ctx.budget.reserver(m.plafond_usd(32_000, 0), f"garde {aide.slug}")
    cout: float | None = None
    try:
        d = ctx.client.decider(
            m.nom, etat, QUESTIONS_MANDAT, acceptes=m.acceptes, delai_s=m.delai_s, role="garde"
        )
        cout = d.cout_usd
        return d.avis["touche"].proba("true"), d.cout_usd, d.modele_servi
    finally:
        ctx.budget.regler(reservation, cout)


def _proposer(
    ctx: Contexte, aide: Aide, chemin: Path, documents: list[tuple[str, str, str]], diff: str
) -> tuple[ApplyResult, str, float, str]:
    """L'appel du mandat et sa validation, avec une relance de correction comme l'ancienne veille."""
    prompt = build_prompt(aide, documents, diff, aujourd_hui=ctx.aujourd_hui)
    cout = 0.0
    corrections = 0
    modele = ""
    while True:
        texte, c, modele = _appel_mandat(ctx, prompt, aide.slug)
        cout += c or 0.0
        applique = appliquer(
            texte,
            aide,
            chemin,
            documents,
            aujourd_hui=ctx.aujourd_hui.isoformat(),
            diff=diff,
            escalader_structure=True,
            lint_complet=True,
        )
        if applique.ok or not applique.rattrapable or corrections:
            return applique, texte, cout, modele
        corrections += 1
        prompt = prompt_correction(prompt, texte, applique.erreurs)


def _rejouer(
    ctx: Contexte,
    aide: Aide,
    chemin: Path,
    documents: list[tuple[str, str, str]],
    diff: str,
    texte: str,
) -> ApplyResult:
    return appliquer(
        texte,
        aide,
        chemin,
        documents,
        aujourd_hui=ctx.aujourd_hui.isoformat(),
        diff=diff,
        escalader_structure=True,
        lint_complet=True,
    )


def _issue_echec(applique: ApplyResult) -> tuple[str, str]:
    """(issue, raison) d'une proposition refusée, avec les catégories de l'ancienne veille."""
    if applique.output is not None and applique.output.changement_majeur:
        return "escalade", "changement majeur déclaré par le modèle : " + (
            applique.output.raison_changement_majeur or "sans raison fournie"
        )
    if applique.etape == "structure":
        return "escalade", " ; ".join(applique.erreurs) + " (ré-extraction)"
    if applique.etape == "ancrage":
        return "escalade", (
            f"{len(applique.erreurs)} citation(s) non ancrée(s) dans le diff : la fiche diverge "
            "peut-être de la source, sans changement de la source sur ces points"
        )
    premiere = applique.erreurs[0] if applique.erreurs else "sans détail"
    return "echec", f"validation en échec ({applique.etape}) : {premiere}"


def _avancer(ctx: Contexte, an: AideAnalysis, col: AideCollect, res: Resultat, motif: str) -> None:
    """La référence avance : les pages fraîches qui ont changé entrent dans `data/sources/`."""
    if not ctx.ecrire:
        return
    from catalogue.convertir import instantanes

    res.snapshots = rafraichir_snapshots(an, col, jour=ctx.aujourd_hui)
    ecrits = set(res.snapshots)
    for i in instantanes(ctx.sources / an.slug):
        if i.nom in ecrits:
            ctx.consigner(
                Evenement(
                    "decision",
                    f"a:{an.slug}",
                    decision="base",
                    decideur="code",
                    issue="avance",
                    cle=cle("base", an.slug, i.cle, i.nom),
                    donnees={
                        "url": i.url,
                        "cle_url": i.cle,
                        "fichier": i.nom,
                        "sha256": i.sha256,
                        "origine": i.origine,
                        "motif": motif,
                    },
                )
            )


def _case_proposition(
    slug: str, titre: str, etat: str, applique: ApplyResult, motifs: list[str], reponse: str
) -> Case:
    resume = applique.output.resume.strip() if applique.output else ""
    return Case(
        sorte="veille-proposition",
        objet=f"a:{slug}",
        titre=titre,
        etat=etat,
        options=OPTIONS_PROPOSITION,
        contexte=(
            f"Résumé du modèle : {resume or '(aucun)'}",
            *[f"- {m}" for m in motifs],
            f"Champs : {', '.join(applique.champs_touches)}",
        ),
        donnees={"reponse": reponse},
    )


def etage_c(
    ctx: Contexte, aide: Aide, an: AideAnalysis, col: AideCollect, res: Resultat
) -> MajResult | None:
    """Le mandat d'une aide `MAJ_LLM`, garde comprise. Rend le `MajResult` de la projection inverse."""
    slug = aide.slug
    etat = empreinte_changement(an)
    chemin = ctx.chemin_yaml(slug)
    documents = documents_a_soumettre(an, col)
    diff = resume_diff(an, max_lignes=MAX_LIGNES_DIFF)
    frais = garder_frais(an, col, ctx.blobs)

    def maj(etat_maj: str, raison: str, champs: list[str] | None = None) -> MajResult:
        # Ce que l'ancienne veille aurait mémorisé : la projection inverse en dépend.
        return MajResult(
            slug=slug,
            etat=etat_maj,  # type: ignore[arg-type]
            modele=ctx.registre.modele("veille").nom,
            raison=raison,
            champs=champs or [],
            empreinte=etat,
            snapshots=res.snapshots,
        )

    # Une réponse de Félix sur CET état du changement passe avant tout appel.
    reponse_felix = cases_mod.reponse(ctx.vue, "veille-proposition", f"a:{slug}", etat) or (
        cases_mod.reponse(ctx.vue, "veille-escalade", f"a:{slug}", etat)
    )
    if reponse_felix == "rearchiver":
        res.issue, res.raison = "rearchivee", "référence avancée sur réponse de Félix"
        _avancer(ctx, an, col, res, "felix")
        return maj("inchange", res.raison)

    if not documents:
        res.issue, res.raison = "panne", "aucun contenu frais fouillable"
        res.panne = "contenu_inexploitable"
        ctx.consigner(
            Evenement("panne", f"a:{slug}", decision="veille", issue="contenu_inexploitable")
        )
        return None

    m_veille = ctx.registre.modele("veille")
    cle_maj = cle(VERSION, "veille", slug, etat, m_veille.nom, EMPREINTE_CONSIGNE, _lire(chemin))
    memo = ctx.vue.memo(cle_maj)
    texte_modele = (memo.donnees.get("reponse") or "") if memo is not None else ""
    if texte_modele and (
        memo is not None and memo.issue != "retouche" or reponse_felix == "appliquer"
    ):
        # Même changement, même fiche, même modèle et même consigne : la réponse
        # mémorisée se revalide sans appel (la validation est du code).
        applique = _rejouer(ctx, aide, chemin, documents, diff, texte_modele)
        res.memorise = True
    else:
        try:
            applique, texte_modele, cout, servi = _proposer(ctx, aide, chemin, documents, diff)
        except Panne as exc:
            res.issue, res.raison, res.panne = "panne", str(exc), exc.classe
            ctx.consigner(
                Evenement(
                    "panne",
                    f"a:{slug}",
                    decision="veille",
                    decideur="llm",
                    modele=m_veille.nom,
                    issue=exc.classe,
                    donnees={"message": str(exc)[:300], "frais": frais},
                )
            )
            return None
        res.cout_usd += cout
        if not applique.ok:
            issue_llm, raison_llm = _issue_echec(applique)
        else:
            issue_llm = "retouche" if applique.texte != _lire(chemin) else "inchange"
            raison_llm = ""
        ctx.consigner(
            Evenement(
                "decision",
                f"a:{slug}",
                decision="veille",
                decideur="llm",
                modele=servi,
                issue=issue_llm,
                cle=cle_maj,
                donnees={
                    "reponse": texte_modele,
                    "raison": raison_llm,
                    "resume": applique.output.resume.strip() if applique.output else "",
                    "champs": applique.champs_touches,
                    "cout_usd": cout,
                    "etat": etat,
                    "frais": frais,
                },
            )
        )

    if reponse_felix == "appliquer" and applique.ok and applique.texte != _lire(chemin):
        return _ecrire(ctx, aide, an, col, res, applique, maj, felix=True)

    if not applique.ok:
        issue, raison = _issue_echec(applique)
        res.issue, res.raison = issue, raison
        res.cases.append(
            Case(
                sorte="veille-escalade",
                objet=f"a:{slug}",
                titre="escalade de veille" if issue == "escalade" else "retouche refusée",
                etat=etat,
                options=OPTIONS_ESCALADE,
                contexte=(f"Motif : {raison}", f"Diff :\n\n```diff\n{diff[:3000]}\n```"),
            )
        )
        return maj(issue, raison)

    if applique.texte == _lire(chemin):
        resume = applique.output.resume.strip() if applique.output else ""
        return _garder(ctx, aide, an, col, res, diff, resume, etat, maj)

    assert applique.output is not None
    protegees = controles.conditions_protegees(applique.output)
    deduites = controles.valeurs_deduites(applique.output, documents)
    notes = controles.notes_non_ancrees(applique.output)
    if protegees or deduites or notes:
        motifs = [
            f"retouche d'une condition ({c}) : la surcouche admin n'est pas lue" for c in protegees
        ]
        motifs += [
            f"note réécrite sans citation ({c}) : rien ne l'ancre dans le diff" for c in notes
        ]
        motifs += [f"valeur absente telle quelle des pages fraîches : {v}" for v in deduites]
        res.issue = "case"
        res.raison = " ; ".join(motifs)
        res.champs = applique.champs_touches
        res.cases.append(
            _case_proposition(
                slug, "retouche à valider", etat, applique, motifs, texte_modele or ""
            )
        )
        return maj("suspect", res.raison)
    return _ecrire(ctx, aide, an, col, res, applique, maj)


def _lire(chemin: Path) -> str:
    return chemin.read_text(encoding="utf-8")


def _ecrire(
    ctx: Contexte,
    aide: Aide,
    an: AideAnalysis,
    col: AideCollect,
    res: Resultat,
    applique: ApplyResult,
    maj: Callable[..., MajResult],
    *,
    felix: bool = False,
) -> MajResult:
    assert applique.texte is not None and applique.output is not None
    chemin = ctx.chemin_yaml(aide.slug)
    ancien = charger_yaml(_lire(chemin)) or {}
    res.issue = "retouche"
    res.champs = applique.champs_touches
    res.raison = applique.output.resume.strip() or ", ".join(applique.champs_touches)
    res.texte = applique.texte
    if ctx.ecrire:
        chemin.write_text(applique.texte, encoding="utf-8")
    _avancer(ctx, an, col, res, "felix" if felix else "retouche")
    for r in controles.residus(ancien, applique.output, applique.texte):
        res.cases.append(
            Case(
                sorte="veille-residu",
                objet=f"a:{aide.slug}",
                titre="ancienne valeur restée dans l'aide",
                etat=empreinte(applique.texte),
                options={"vu": "corrigé à la main, ou sans objet"},
                contexte=(r,),
            )
        )
    return maj("applique", res.raison, res.champs)


def _garder(
    ctx: Contexte,
    aide: Aide,
    an: AideAnalysis,
    col: AideCollect,
    res: Resultat,
    diff: str,
    resume: str,
    etat: str,
    maj: Callable[..., MajResult],
) -> MajResult:
    """Un « inchangé » du modèle : la garde de Jev décide si la référence avance."""
    seuils = ctx.registre.decisions["V1-garde"].seuils
    escalade, bas = seuils["escalade"], seuils["zone_prudente_bas"]
    m = ctx.registre.modele("decision")
    m_veille = ctx.registre.modele("veille")
    cle_garde = cle(
        VERSION,
        "V1",
        aide.slug,
        empreinte(diff),
        resume,
        m_veille.nom,
        EMPREINTE_CONSIGNE,
        EMPREINTE_QUESTIONS,
        m.nom,
    )
    memo = ctx.vue.memo(cle_garde)
    if memo is not None:
        p = float(memo.donnees["p"])
        res.memorise = True
    else:
        etat_jev = etat_mandat(aide, diff, resume)
        blob = garder_blob(
            ctx.blobs, json.dumps(etat_jev, ensure_ascii=False, sort_keys=True).encode()
        )
        try:
            p, cout, servi = _garde(ctx, aide, etat_jev)
        except Panne as exc:
            res.issue, res.raison, res.panne = (
                "zone_prudente",
                f"garde en panne : {exc}",
                exc.classe,
            )
            ctx.consigner(
                Evenement(
                    "panne",
                    f"a:{aide.slug}",
                    decision="V1-garde",
                    decideur="jev",
                    modele=m.nom,
                    issue=exc.classe,
                    donnees={"message": str(exc)[:300]},
                )
            )
            return maj("suspect", res.raison)
        res.cout_usd += cout or 0.0
        zone = "avance" if p < bas else ("prudente" if p < escalade else "escalade")
        ctx.consigner(
            Evenement(
                "decision",
                f"a:{aide.slug}",
                decision="V1-garde",
                decideur="jev",
                modele=servi,
                issue=zone,
                cle=cle_garde,
                donnees={
                    "p": p,
                    "seuils": seuils,
                    "cout_usd": cout,
                    "etat": etat,
                    "resume": resume,
                    "etat_jev": blob,
                },
            )
        )
    res.garde = p
    if p < bas:
        res.issue, res.raison = "inchange", resume or "aucun changement dans le mandat"
        _avancer(ctx, an, col, res, "garde")
        return maj("inchange", res.raison)
    if p < escalade:
        res.issue = "zone_prudente"
        res.raison = f"« inchangé » noté {p:.2f} par la garde : la référence reste"
        return maj("suspect", res.raison)
    res.issue = "case"
    res.raison = f"changement possible non appliqué (garde {p:.2f}) : {resume or 'rien proposé'}"
    res.cases.append(
        Case(
            sorte="veille-escalade",
            objet=f"a:{aide.slug}",
            titre="« inchangé » suspect",
            etat=etat,
            options=OPTIONS_ESCALADE,
            contexte=(
                f"Garde de Jev : {p:.2f} (seuil {escalade})",
                f"Résumé du modèle : {resume or '(aucun)'}",
                f"Diff :\n\n```diff\n{diff[:3000]}\n```",
            ),
        )
    )
    return maj("suspect", res.raison)


# ------------------------------------------------------------------ passage


def _pannes_precedentes(vue_evenements: list[Evenement], slug: str, run: str) -> int:
    """Nombre de runs distincts, avant celui-ci, où l'aide a été injoignable."""
    return len(
        {
            e.run
            for e in vue_evenements
            if e.type == "panne"
            and e.objet == f"a:{slug}"
            and e.decision == "collecte"
            and e.run != run
        }
    )


def traiter(
    ctx: Contexte, aide: Aide, an: AideAnalysis, col: AideCollect, historique: list[Evenement]
) -> tuple[Resultat, MajResult | None]:
    res = Resultat(slug=aide.slug, statut=an.statut, issue="ok")
    statut = an.statut
    if statut in ("OK", "SANS_BASELINE"):
        res.issue = statut.lower()
        return res, None
    if statut == "ERREUR_HTTP":
        codes = [u.result.status for u in an.erreurs if u.result is not None]
        classe = "anti_robot" if 403 in codes else "reseau_hote"
        res.issue, res.panne = "panne", classe
        res.raison = an.raisons[0] if an.raisons else classe
        precedentes = _pannes_precedentes(historique, aide.slug, ctx.run)
        ctx.consigner(
            Evenement(
                "panne",
                f"a:{aide.slug}",
                decision="collecte",
                issue=classe,
                donnees={"raison": res.raison, "codes": codes},
            )
        )
        if precedentes >= 1:
            res.cases.append(
                Case(
                    sorte="veille-injoignable",
                    objet=f"a:{aide.slug}",
                    titre="source injoignable",
                    etat=empreinte(f"{classe}:{ctx.run}"),
                    options={"vu": "vu ; la source reste suivie"},
                    contexte=(f"{precedentes + 1} passages de suite : {res.raison}",),
                )
            )
        return res, None
    if statut == "DATE_PERIMEE_SOURCE_INCHANGEE":
        assert an.date_limite_perimee is not None
        res.issue = "case"
        res.raison = an.raisons[0] if an.raisons else "échéance périmée, source inchangée"
        res.cases.append(
            Case(
                sorte="veille-echeance",
                objet=f"a:{aide.slug}",
                titre="échéance périmée, source inchangée",
                etat=an.date_limite_perimee.isoformat(),
                options={
                    "acquitter": "vu : ne plus alerter tant que la date ne change pas",
                    "attendre": "laisser l'alerte",
                },
                contexte=(res.raison,),
            )
        )
        return res, None
    if statut == "ESCALADE_INGESTION":
        etat = empreinte_changement(an)
        res.issue, res.raison = "case", "; ".join(an.raisons)
        if cases_mod.reponse(ctx.vue, "veille-escalade", f"a:{aide.slug}", etat) == "rearchiver":
            res.issue = "rearchivee"
            _avancer(ctx, an, col, res, "felix")
            return res, MajResult(slug=aide.slug, etat="inchange", empreinte=etat)
        garder_frais(an, col, ctx.blobs)
        res.cases.append(
            Case(
                sorte="veille-escalade",
                objet=f"a:{aide.slug}",
                titre="escalade de l'analyse",
                etat=etat,
                options=OPTIONS_ESCALADE,
                contexte=tuple(f"- {r}" for r in an.raisons),
            )
        )
        return res, None
    # MAJ_LLM
    try:
        return res, etage_c(ctx, aide, an, col, res)
    except BudgetEpuise as exc:
        res.issue, res.raison, res.panne = "panne", str(exc), "budget"
        ctx.consigner(Evenement("panne", f"a:{aide.slug}", decision="veille", issue="budget"))
        return res, None


@dataclass
class Bilan:
    resultats: dict[str, Resultat]
    remplacees: int
    acquittees: list[str]
    ambigues: list[str]
    depense: float
    couts_inconnus: int

    @property
    def cases(self) -> list[Case]:
        return [c for r in self.resultats.values() for c in r.cases]

    def compte(self) -> Counter[str]:
        return Counter(r.issue for r in self.resultats.values())


def passer(
    ctx: Contexte,
    aides: dict[str, Aide],
    collects: dict[str, AideCollect],
    *,
    manifeste: Path | None = None,
) -> Bilan:
    """Un passage : référence du journal, analyse, mandat, garde, cases, projection inverse."""
    historique = list(ctx.journal.lire())
    remplacees = appliquer_bases(collects, bases_en_vigueur(historique), ctx.sources)
    analyses = analyze_all(aides, collects, today=ctx.aujourd_hui)

    manifest = veille_aides.load_manifest(manifeste) if manifeste else {}
    a_acquitter = [
        slug
        for slug, an in analyses.items()
        if an.date_limite_perimee is not None
        and cases_mod.reponse(
            ctx.vue, "veille-echeance", f"a:{slug}", an.date_limite_perimee.isoformat()
        )
        == "acquitter"
    ]
    acquittees = veille_aides.traiter_acquittements(analyses, manifest, nouveaux=a_acquitter)

    resultats: dict[str, Resultat] = {}
    majs: dict[str, MajResult] = {}
    for slug, aide in aides.items():
        if slug not in analyses:
            continue
        try:
            res, maj = traiter(ctx, aide, analyses[slug], collects[slug], historique)
        except Exception as exc:  # une aide en bug ne doit pas arrêter le passage
            res, maj = Resultat(slug, analyses[slug].statut, "panne", str(exc)[:300]), None
            res.panne = "bug"
            ctx.consigner(
                Evenement(
                    "panne",
                    f"a:{slug}",
                    decision="veille",
                    issue="bug",
                    donnees={"message": f"{type(exc).__name__}: {exc}"[:500]},
                )
            )
        resultats[slug] = res
        if maj is not None:
            majs[slug] = maj

    if manifeste is not None and ctx.ecrire:
        fusion = veille_aides.update_manifest(manifest, analyses, majs, ctx.aujourd_hui)
        veille_aides.write_manifest(fusion, manifeste)
    return Bilan(
        resultats,
        remplacees,
        acquittees,
        [],
        ctx.budget.depense,
        ctx.budget.couts_inconnus,
    )


def charger_aides(slugs: list[str] | None = None) -> dict[str, Aide]:
    chemins = (
        [AIDES_DIR / f"{s}.yaml" for s in slugs] if slugs else sorted(AIDES_DIR.glob("*.yaml"))
    )
    return {p.stem: load_aide(p) for p in chemins}


# ------------------------------------------------------------------ commande


def section(bilan: Bilan) -> list[str]:
    """La section « Veille » du rapport de la semaine."""
    r = bilan.resultats
    compte = bilan.compte()
    lignes = [
        f"{len(r)} aides suivies ; issues : {', '.join(f'{k} {v}' for k, v in compte.most_common())}.",
        f"Références lues dans le journal à la place du dernier archivé : {bilan.remplacees} URL.",
        f"Dépense de la veille : {bilan.depense:.4f} $ facturés"
        + (f", {bilan.couts_inconnus} appel(s) sans coût facturé" if bilan.couts_inconnus else "")
        + ".",
    ]
    if bilan.acquittees:
        lignes.append(f"Échéances acquittées : {', '.join(bilan.acquittees)}.")
    retouches = [x for x in r.values() if x.issue == "retouche"]
    if retouches:
        lignes += ["", "### Retouches écrites", ""]
        lignes += [f"- `{x.slug}` : {', '.join(x.champs)} — {x.raison[:200]}" for x in retouches]
    zone = sorted((x for x in r.values() if x.issue == "zone_prudente"), key=lambda x: x.slug)
    if zone:
        lignes += [
            "",
            "### Zone prudente de la garde (la référence reste ; jugées à la session d'étiquetage)",
            "",
        ]
        lignes += [f"- `{x.slug}` : {x.raison}" for x in zone]
    pannes = Counter(x.panne for x in r.values() if x.panne)
    if pannes:
        lignes += ["", f"Pannes, par classe : {', '.join(f'{k} {v}' for k, v in pannes.items())}."]
        lignes += [
            f"- `{x.slug}` ({x.panne}) : {x.raison[:160]}"
            for x in sorted(r.values(), key=lambda x: x.slug)
            if x.panne and x.panne not in ("reseau_hote", "anti_robot")
        ]
    return lignes


def commande(
    journal: Path,
    slugs: list[str],
    *,
    a_blanc: bool = False,
    reviews: Path = REVIEWS,
    parties: Path | None = None,
) -> int:
    """`python -m catalogue veille` : un passage complet, le rapport, la projection inverse."""
    import secrets

    from veille_collect import collect

    from catalogue import registre as registre_mod
    from catalogue.rapport import Rapport, Section, parties_json

    reg = registre_mod.charger()
    jour = dt.date.today()
    run = f"{jour.isoformat()}-veille-{secrets.token_hex(2)}"
    j = Journal(journal)
    vue = Vue(list(j.lire()))
    reponses, ambigues = cases_mod.relire(reviews.glob("*-semaine*.md"), vue, run)
    if reponses:
        j.ajouter_lot(reponses)
        for e in reponses:
            vue.prendre(e)
    appels = BACKEND / ".cache" / "catalogue" / "appels" / f"{run}.jsonl"
    appels.parent.mkdir(parents=True, exist_ok=True)
    ctx = Contexte(
        registre=reg,
        journal=j,
        vue=vue,
        client=Client(journal=appels),
        budget=Budget(reg.budgets.run.plafond_usd),
        run=run,
        aujourd_hui=jour,
        ecrire=not a_blanc,
    )
    aides = charger_aides(slugs or None)
    collects = collect(list(aides.values()))
    if _panne_generalisee(collects):
        # Plus de 30 % des URL en échec : aucune étape payante sur des pages manquantes.
        rapport = Rapport(jour, run)
        rapport.entete = [
            "- Veille arrêtée : panne réseau générale (plus de 30 % des URL en échec)."
        ]
        if parties is not None:
            parties.write_text(parties_json(rapport.entete, [], []), encoding="utf-8")
        else:
            print(f"rapport : {rapport.ecrire(reviews)}")
        return CODE_RESEAU
    bilan = passer(ctx, aides, collects, manifeste=None if a_blanc else veille_aides.MANIFEST_PATH)
    bilan.ambigues = ambigues
    rapport = Rapport(jour, run)
    rapport.entete = [
        f"- Veille : {len(bilan.resultats)} aides, {len(bilan.cases)} case(s), "
        f"{bilan.depense:.4f} $ facturés" + (" (à blanc, rien d'écrit)" if a_blanc else "") + ".",
        f"- Réponses de Félix relues : {len(reponses)}"
        + (f" ; cases illisibles (plusieurs choix) : {', '.join(ambigues)}" if ambigues else "")
        + ".",
    ]
    rapport.cases = bilan.cases
    rapport.sections.append(Section("Veille", section(bilan)))
    if parties is not None:
        # Lancée par `semaine` : le run compose un seul rapport avec les parties de chaque étape.
        parties.write_text(
            parties_json(rapport.entete, rapport.cases, rapport.sections), encoding="utf-8"
        )
    else:
        print(f"rapport : {rapport.ecrire(reviews)}")
    print(f"issues : {dict(bilan.compte())} ; dépense {bilan.depense:.4f} $")
    return code_de_sortie(bilan)


CODE_BUDGET, CODE_RESEAU, CODE_CLE, CODE_BUGS = 2, 3, 4, 7


def code_de_sortie(bilan: Bilan) -> int:
    """Le code du passage, du plus grave au moins grave (section 9 d'`architecture.md`)."""
    pannes = Counter(r.panne for r in bilan.resultats.values() if r.panne)
    if pannes.keys() & {"credits", "cle", "modele_substitue"}:
        return CODE_CLE
    if pannes["bug"] > 5:
        return CODE_BUGS
    if pannes["budget"]:
        return CODE_BUDGET
    return 0
