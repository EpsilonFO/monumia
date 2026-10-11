"""Jeu E : les pages entrantes après le tri, étiquetées à l'aveugle (I0, mesure M1).

Commandes, depuis backend/ :

    uv run python -m catalogue.mesures.jeu_e tirer
    uv run python -m catalogue.mesures.jeu_e telecharger <dossier>
    uv run python -m catalogue.mesures.jeu_e regle <dossier>
    uv run python -m catalogue.mesures.jeu_e analyser <dossier> <etiquettes.json>

`tirer` réunit la population : toutes les pages lues après le tri, dans tous les
`lectures.jsonl` du checkout principal et des worktrees `prospection`,
`fusion-prospection-veille` et `refonte-pipeline`, dédoublonnées par
`veille_collect.cle_url` (la lecture la plus récente l'emporte). Un balayage ne
relit pas une page déjà en file : le seul fichier le plus récent d'un territoire
manquerait donc le résidu. Il tire 100 pages dans le résidu `a_valider` de la
file de cette branche et 200 dans le reste (graine 20261011), et crée
backend/data/reviews/logs/refonte/<date>-jeu-e-<n>/ avec echantillon.jsonl
(identifiant aveugle, URL, strate, probabilité d'inclusion, ce que la lecture de
production avait dit) et population.json.

`telecharger` ouvre chaque page avec le Fetcheur du pipeline (une seconde par
hôte) et l'extrait comme la lecture de prospection (`_texte_a_juger`, tronqué à
25 000 caractères, documents liés de `_documents_lies`) : pages/<id>.md,
index.tsv (identifiant et URL finale, tout ce que voient les juges) et
telechargements.jsonl.

`regle` (payant, plafond 1 $) fait juger chaque page par la règle d'entrée de
production, dans son état exact : Jev (`prospection.arbitre.arbitrer`, dont on
garde les distributions complètes), puis, hors de la bande basse, le LLM de
lecture `or-glm` avec la consigne et le prompt de production, puis la correction
de `lecture._appliquer_arbitrage` et la règle de promotion de la file. Une panne
de Jev n'est pas suppléée par le LLM seul : la page est notée en panne. Sortie
dans un sous-dossier neuf regle-<k>/ : reponses.jsonl et resume.txt.

`analyser` croise les étiquettes (sortie du workflow d'étiquetage) et les
réponses de chaque exécution de `regle`, pondère chaque page par l'inverse de sa
probabilité d'inclusion, et écrit analyse.json et analyse.txt.

Rien n'est écrit sous backend/data/ hors du dossier de sortie ; le cache
pdftotext de veille_collect va dans backend/.cache/, ignoré par git.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

from pipeline import etat, llm
from pipeline.decision import ClientDecision, Decision, ErreurDecision
from pipeline.web import Fetcheur
from prospection import arbitre, lecture
from prospection.territoires import charger_territoires

from catalogue.mesures.stats import Proportion, ponderee
from catalogue.veille_collect import cle_url

BACKEND = Path(__file__).resolve().parents[2]
LOGS = BACKEND / "data" / "reviews" / "logs" / "refonte"
FILE_ATTENTE = BACKEND / "data" / "prospection" / "file-attente.yaml"
# Le checkout principal et les worktrees dont on lit les lectures : la
# disposition est celle du Mac de Félix (worktrees sous .claude/worktrees/).
CHECKOUT_PRINCIPAL = BACKEND.parents[3]
RACINES = (
    CHECKOUT_PRINCIPAL / "backend",
    CHECKOUT_PRINCIPAL / ".claude" / "worktrees" / "prospection" / "backend",
    CHECKOUT_PRINCIPAL / ".claude" / "worktrees" / "fusion-prospection-veille" / "backend",
    BACKEND,
)

GRAINE = 20261011
TAILLES = {"residu": 100, "reste": 200}
MODELE_LECTURE = "or-glm"
PLAFOND_REGLE_USD = 1.0
# Réservé avant chaque page : Jev (0,0006 $) plus une lecture `or-glm`
# (0,0007 $ en moyenne), avec une marge pour les pages longues.
RESERVE_PAGE_USD = 0.004
VERDICTS = ("retenue", "indeterminee", "ecartee")


# --------------------------------------------------------------------------
# Outils
# --------------------------------------------------------------------------


def _lire_jsonl(chemin: Path) -> list[dict[str, Any]]:
    return [json.loads(ligne) for ligne in chemin.read_text(encoding="utf-8").splitlines() if ligne]


def _dossier_neuf(sujet: str) -> Path:
    date = dt.date.today().isoformat()
    n = 1
    while (LOGS / f"{date}-{sujet}-{n}").exists():
        n += 1
    dossier = LOGS / f"{date}-{sujet}-{n}"
    dossier.mkdir(parents=True)
    return dossier


def _sous_dossier_neuf(dossier: Path, sujet: str) -> Path:
    k = 1
    while (dossier / f"{sujet}-{k}").exists():
        k += 1
    sortie = dossier / f"{sujet}-{k}"
    sortie.mkdir()
    return sortie


def verdict(destinataire: str, objet: str, categorie_ecart: str | None) -> str:
    """Le verdict de la lecture de production (`lecture.LectureFiche`), sur trois issues."""
    categorie = None if categorie_ecart in (None, "", "aucune") else categorie_ecart
    if etat.retenir(destinataire, objet) and categorie != "non_dispositif":
        return "retenue"
    if etat.indetermine(destinataire, objet, categorie):
        return "indeterminee"
    return "ecartee"


# --------------------------------------------------------------------------
# tirer
# --------------------------------------------------------------------------


def _population() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    fichiers = sorted(
        (
            f
            for racine in RACINES
            for f in (racine / "data" / "prospection").glob("*/lectures.jsonl")
        ),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    pages: dict[str, dict[str, Any]] = {}
    doublons = 0
    for fichier in fichiers:
        for ligne in fichier.read_text(encoding="utf-8").splitlines():
            if not ligne.strip():
                continue
            entree = json.loads(ligne)
            cle = cle_url(entree["url"])
            if cle in pages:
                doublons += 1
                continue
            pages[cle] = {
                "url": entree["url"],
                "territoire": fichier.parent.name,
                "erreur_lecture": entree.get("erreur"),
                "fiche_lecture": entree.get("fiche"),
                "source": str(fichier),
            }
    meta = {
        "fichiers": [
            {
                "chemin": str(f),
                "mtime": dt.datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds"),
            }
            for f in fichiers
        ],
        "lectures_dedoublonnees": doublons,
    }
    return pages, meta


def tirer(_: argparse.Namespace) -> int:
    pages, meta = _population()
    taches = etat.charger(FILE_ATTENTE)
    residu = {cle_url(t.url) for t in taches.values() if t.statut == "a_valider"}
    strates = {
        "residu": sorted(c for c in pages if c in residu),
        "reste": sorted(c for c in pages if c not in residu),
    }
    rng = random.Random(GRAINE)
    tirees: list[tuple[str, str, float]] = []
    for strate, cles in strates.items():
        n = min(TAILLES[strate], len(cles))
        tirees.extend((strate, cle, n / len(cles)) for cle in rng.sample(cles, n))
    rng.shuffle(tirees)

    dossier = _dossier_neuf("jeu-e")
    with (dossier / "echantillon.jsonl").open("w", encoding="utf-8") as f:
        for i, (strate, cle, p) in enumerate(tirees, 1):
            page = pages[cle]
            ligne = {
                "id": f"e{i:03d}",
                "url": page["url"],
                "cle": cle,
                "territoire": page["territoire"],
                "strate": strate,
                "p_inclusion": p,
                "erreur_lecture": page["erreur_lecture"],
                "fiche_lecture": page["fiche_lecture"],
                "source": page["source"],
            }
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    meta.update(
        {
            "graine": GRAINE,
            "population": {s: len(c) for s, c in strates.items()},
            "tirage": {s: min(TAILLES[s], len(c)) for s, c in strates.items()},
            "residu_file": len(residu),
            "residu_hors_population": len(residu - set(pages)),
        }
    )
    (dossier / "population.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(dossier)
    resume = {k: meta[k] for k in ("population", "tirage", "residu_file", "residu_hors_population")}
    print(json.dumps(resume, ensure_ascii=False))
    print(
        f"fichiers lus : {len(meta['fichiers'])} ; lectures dédoublonnées : {meta['lectures_dedoublonnees']}"
    )
    return 0


# --------------------------------------------------------------------------
# telecharger
# --------------------------------------------------------------------------


def telecharger(args: argparse.Namespace) -> int:
    dossier = Path(args.dossier)
    echantillon = _lire_jsonl(dossier / "echantillon.jsonl")
    territoires = charger_territoires()
    pages = dossier / "pages"
    pages.mkdir()
    debut = time.monotonic()
    with (
        Fetcheur() as fetcheur,
        (dossier / "telechargements.jsonl").open("w", encoding="utf-8") as journal,
        (dossier / "index.tsv").open("w", encoding="utf-8") as index,
    ):
        index.write("id\turl\n")
        for i, e in enumerate(echantillon, 1):
            page = fetcheur.get(e["url"])
            texte, raison = lecture._texte_a_juger(page) if page.ok else ("", None)
            texte = texte[: lecture.MAX_CAR_PAGE]
            territoire = territoires.get(e["territoire"])
            documents = (
                lecture._documents_lies(page, territoire, None)
                if texte and territoire is not None
                else []
            )
            if texte:
                (pages / f"{e['id']}.md").write_text(texte, encoding="utf-8")
                index.write(f"{e['id']}\t{page.url_finale}\n")
            ligne = {
                "id": e["id"],
                "url": e["url"],
                "url_finale": page.url_finale,
                "statut": page.status,
                "est_pdf": page.est_pdf if page.ok else None,
                "erreur": page.erreur,
                "raison_sans_texte": raison,
                "longueur": len(texte),
                "documents": documents,
                "territoire_connu": territoire is not None,
            }
            journal.write(json.dumps(ligne, ensure_ascii=False) + "\n")
            journal.flush()
            print(
                f"[{i}/{len(echantillon)}] {e['id']} {page.status} {len(texte)} car. {raison or page.erreur or ''}"
            )
    print(f"fini en {time.monotonic() - debut:.0f} s")
    return 0


# --------------------------------------------------------------------------
# regle
# --------------------------------------------------------------------------


class _Enregistreur:
    """Passe les appels au client Jev et garde la dernière décision complète.

    `arbitre.arbitrer` ne rend que le choix le plus probable de chaque question ;
    la combinaison candidate a besoin des distributions entières. Les intercepter
    ici laisse le code de production intact.
    """

    def __init__(self, client: ClientDecision) -> None:
        self.client = client
        self.derniere: Decision | None = None

    def decider(self, etat_jev: Any, questions: dict[str, Any]) -> Decision:
        self.derniere = self.client.decider(etat_jev, questions)
        return self.derniere


def _distributions(d: Decision) -> dict[str, Any]:
    return {
        nom: {"type": r.type, "choix": r.choix, "noul": r.noul, "probabilites": r.probabilites}
        for nom, r in d.reponses.items()
    }


def _cout_facture(reponse: Any) -> float | None:
    """Le coût que rend OpenRouter dans la réponse, s'il y est.

    `Response.raw` de providall est l'objet du SDK OpenAI, pas un dict : le coût,
    champ propre à OpenRouter, se lit dans les champs supplémentaires de `usage`.
    """
    brut = getattr(reponse, "raw", None)
    usage = brut.get("usage") if isinstance(brut, dict) else getattr(brut, "usage", None)
    if usage is None:
        return None
    if isinstance(usage, dict):
        cout = usage.get("cost")
    else:
        cout = getattr(usage, "cost", None)
        if cout is None:
            cout = (getattr(usage, "model_extra", None) or {}).get("cost")
    return float(cout) if isinstance(cout, int | float) else None


def _juger(
    e: dict[str, Any],
    t: dict[str, Any],
    texte: str,
    jev: _Enregistreur,
    lecteur: Any,
    systeme: str,
) -> dict[str, Any]:
    debut = time.monotonic()
    ligne: dict[str, Any] = {"id": e["id"], "strate": e["strate"]}
    arbitrage: arbitre.Arbitrage | None = None
    for essai in range(2):
        try:
            arbitrage = arbitre.arbitrer(jev, t["url_finale"], texte)  # type: ignore[arg-type]
            break
        except ErreurDecision as exc:
            ligne["panne"] = f"jev (essai {essai + 1}) : {exc}"
            time.sleep(5)
    if arbitrage is None or jev.derniere is None:
        ligne.update(cout_usd=0.0, duree_s=round(time.monotonic() - debut, 2))
        return ligne
    ligne.pop("panne", None)
    ligne.update(
        bande=arbitrage.bande,
        jev=arbitrage.en_dict(),
        jev_distributions=_distributions(jev.derniere),
        jev_jetons=arbitrage.jetons_entree,
        cout_jev=arbitrage.cout_usd,
    )
    cout = arbitrage.cout_usd or 0.0
    if arbitrage.bande == "ecartee":
        ligne.update(verdict="ecartee", promue=False, motif="écartée par Jev sans lecture")
    else:
        prompt = "\n\n".join(
            [
                f"URL : {t['url_finale']}",
                "Documents liés depuis cette page (les seuls que tu peux citer dans `urls_pdf`) :\n"
                + ("\n".join(f"  {u}" for u in t["documents"]) or "  (aucun)"),
                "--- Texte du document PDF ---" if t["est_pdf"] else "--- Contenu de la page ---",
                texte,
            ]
        )
        essai = lecteur.try_complete_json(lecture.LectureFiche, prompt, system=systeme)
        reponse = essai.response
        facture = _cout_facture(reponse)
        estime = getattr(reponse, "cost_usd", None)
        ligne.update(
            modele_llm=getattr(reponse, "model", None),
            cout_llm_estime=estime,
            cout_llm_facture=facture,
        )
        cout += facture if facture is not None else (estime or RESERVE_PAGE_USD)
        if essai.data is None:
            ligne["panne"] = f"lecture : {getattr(reponse, 'error', None)}"
        else:
            fiche = essai.data
            lu = {
                "destinataire": fiche.destinataire,
                "objet": fiche.objet,
                "categorie_ecart": fiche.categorie_ecart,
                "famille": fiche.famille,
            }
            fiche.urls_pdf = [u for u in fiche.urls_pdf if u in t["documents"]]
            correction = lecture._appliquer_arbitrage(fiche, arbitrage)
            tache = etat.Tache(
                titre=fiche.titre or t["url"],
                url=t["url"],
                territoire=e["territoire"],
                famille=fiche.famille,
                destinataire=fiche.destinataire,
                objet=fiche.objet,
                categorie_ecart=fiche.categorie_ecart,
            )
            motif = etat.motif_non_promotion(tache)
            ligne.update(
                llm=lu,
                correction=correction,
                verdict=verdict(fiche.destinataire, fiche.objet, fiche.categorie_ecart),
                promue=motif is None,
                motif=motif,
                titre=fiche.titre,
            )
    ligne.update(cout_usd=round(cout, 6), duree_s=round(time.monotonic() - debut, 2))
    return ligne


def regle(args: argparse.Namespace) -> int:
    dossier = Path(args.dossier)
    sortie = _sous_dossier_neuf(dossier, "regle")
    llm.charger_env()
    jev = _Enregistreur(ClientDecision())
    lecteur = llm.client_pour("lecture", MODELE_LECTURE)
    systeme = lecture.consigne(lecture.SKILL_PROSPECTION)
    telechargements = {t["id"]: t for t in _lire_jsonl(dossier / "telechargements.jsonl")}
    depense = 0.0
    lignes: list[dict[str, Any]] = []
    with (sortie / "reponses.jsonl").open("w", encoding="utf-8") as f:
        for e in _lire_jsonl(dossier / "echantillon.jsonl"):
            t = telechargements.get(e["id"])
            if t is None or not t["longueur"]:
                continue
            if depense + RESERVE_PAGE_USD > PLAFOND_REGLE_USD:
                print(f"plafond atteint avant {e['id']} ({depense:.4f} $)")
                break
            texte = (dossier / "pages" / f"{e['id']}.md").read_text(encoding="utf-8")
            ligne = _juger(e, t, texte, jev, lecteur, systeme)
            depense += ligne["cout_usd"]
            lignes.append(ligne)
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
            f.flush()
            print(
                f"{e['id']} {ligne.get('bande')} {ligne.get('verdict')} {ligne.get('panne') or ''}"
            )
    jev.client.fermer()
    resume = [
        f"pages jugées : {len(lignes)} ; dépense comptée : {depense:.4f} $",
        f"pannes : {sum('panne' in x for x in lignes)}",
        f"bandes : {dict(Counter(x.get('bande') for x in lignes))}",
        f"verdicts : {dict(Counter(x.get('verdict') for x in lignes))}",
        f"promues : {sum(bool(x.get('promue')) for x in lignes)}",
        f"modèles LLM servis : {dict(Counter(x.get('modele_llm') for x in lignes if x.get('modele_llm')))}",
    ]
    (sortie / "resume.txt").write_text("\n".join(resume) + "\n", encoding="utf-8")
    print("\n".join(resume))
    return 0


# --------------------------------------------------------------------------
# analyser
# --------------------------------------------------------------------------


# Ce qu'écrit un juge quand le texte extrait n'a rien à juger (menus, fil
# d'Ariane, titre seul). Relevé par la relecture adverse du 2026-10-10 : ces
# pages avaient été étiquetées, souvent « indéterminées » faute de texte, et
# gonflaient les pages à revoir et les pertes.
MOTIF_SANS_CONTENU = re.compile(
    r"ne contient (que|rien)|uniquement (de |du |des |le |la |les )?(menu|navigation)"
    r"|seulement (le |la |les )?(menu|navigation)|que (le |la |les |des )?(menu|navigation|bandeau)"
    r"|aucun contenu|pas de contenu|on ne peut (pas )?(juger|trancher)"
    r"|impossible de (juger|trancher)|s'arrête (avant|au)|texte (extrait )?(se limite|réduit)",
    re.I,
)


def pages_sans_contenu(dossier: Path, etiquettes_brutes: list[dict[str, Any]]) -> dict[str, str]:
    """Les pages dont le texte extrait n'a rien à juger, avec la raison.

    Deux règles : un contenu binaire décodé comme du texte (en-tête JFIF d'une
    image), ou la justification d'un juge ou de l'arbitre qui dit que le texte
    extrait ne contient que la navigation. Ces pages sortent des mesures, comme
    le prévoyait le plan (« une page sans texte exploitable est comptée à part,
    sans étiquette ») ; en production, le contrôle `C-inexploitable` doit les
    arrêter avant tout décideur.
    """
    sortie: dict[str, str] = {}
    for chemin in sorted((dossier / "pages").glob("*.md")):
        tete = chemin.read_bytes()[:200]
        if b"JFIF" in tete or b"\x00" in tete:
            sortie[chemin.stem] = "contenu binaire"
    for e in etiquettes_brutes:
        textes = " ".join(
            str(v.get("justification", ""))
            for k in ("juge1", "juge2", "arbitre", "final")
            if isinstance(v := e.get(k), dict)
        )
        if e["id"] not in sortie and MOTIF_SANS_CONTENU.search(textes):
            sortie[e["id"]] = "le texte extrait ne contient que la navigation"
    return sortie


def _etiquette(e: dict[str, Any]) -> str | None:
    final = e.get("final")
    if not final:
        return None
    return verdict(final["destinataire"], final["objet"], final.get("categorie_ecart"))


def _taux(cas: list[tuple[bool, float]]) -> dict[str, Any]:
    p: Proportion = ponderee(cas)
    brut = sum(1 for x, _ in cas if x)
    return {
        "pondere": round(p.p, 4),
        "bas": round(p.bas, 4),
        "haut": round(p.haut, 4),
        "effectif": round(p.effectif, 1),
        "brut": f"{brut}/{len(cas)}",
        "texte": f"{brut}/{len(cas)} brut ; {p.texte(pondere=True)}",
    }


def _mesures_regle(
    reponses: dict[str, dict[str, Any]],
    etiquettes: dict[str, str],
    poids: dict[str, float],
    ids: list[str],
) -> dict[str, Any]:
    jugees = [i for i in ids if i in reponses and "panne" not in reponses[i] and i in etiquettes]
    a_revoir = [i for i in jugees if etiquettes[i] in ("retenue", "indeterminee")]
    a_retenir = [i for i in jugees if etiquettes[i] == "retenue"]
    admises = [i for i in jugees if reponses[i].get("promue")]
    retenues = [i for i in jugees if reponses[i].get("verdict") == "retenue"]
    non_ecartees = [i for i in jugees if reponses[i].get("verdict") != "ecartee"]

    def doute(i: str) -> bool:
        return reponses[i].get("verdict") != "ecartee" and not reponses[i].get("promue")

    return {
        "pages_jugees": len(jugees),
        "bandes": dict(Counter(reponses[i].get("bande") for i in jugees)),
        "verdicts": dict(Counter(reponses[i].get("verdict") for i in jugees)),
        "part_doute_lecture": _taux(
            [(reponses[i].get("verdict") == "indeterminee", poids[i]) for i in jugees]
        ),
        "part_doute_file": _taux([(doute(i), poids[i]) for i in jugees]),
        "part_non_ecartee": _taux([(i in non_ecartees, poids[i]) for i in jugees]),
        "pertes_a_revoir": _taux(
            [(reponses[i].get("verdict") == "ecartee", poids[i]) for i in a_revoir]
        ),
        "pertes_strictes": _taux(
            [(reponses[i].get("verdict") == "ecartee", poids[i]) for i in a_retenir]
        ),
        "admises_a_tort": _taux([(etiquettes[i] == "ecartee", poids[i]) for i in admises]),
        "retenues_a_tort": _taux([(etiquettes[i] == "ecartee", poids[i]) for i in retenues]),
    }


def analyser(args: argparse.Namespace) -> int:
    dossier = Path(args.dossier)
    echantillon = {e["id"]: e for e in _lire_jsonl(dossier / "echantillon.jsonl")}
    telechargements = {t["id"]: t for t in _lire_jsonl(dossier / "telechargements.jsonl")}
    brut = json.loads(Path(args.etiquettes).read_text(encoding="utf-8"))
    etiquettes = {e["id"]: v for e in brut if (v := _etiquette(e)) is not None}
    poids = {i: 1.0 / e["p_inclusion"] for i, e in echantillon.items()}
    vides = {} if args.avec_pages_vides else pages_sans_contenu(dossier, brut)
    exploitables = [i for i, t in telechargements.items() if t["longueur"] and i not in vides]
    etiquetees = [i for i in exploitables if i in etiquettes]

    resultat: dict[str, Any] = {
        "echantillon": len(echantillon),
        "exploitables": len(exploitables),
        "inexploitables": _taux(
            [(not telechargements[i]["longueur"] or i in vides, poids[i]) for i in echantillon]
        ),
        "sans_contenu_jugeable": {
            "pages": len(vides),
            "etiquettes": dict(Counter(etiquettes.get(i) for i in vides)),
            "liste": vides,
        },
        "etiquetees": len(etiquetees),
        "etiquettes": dict(Counter(etiquettes[i] for i in etiquetees)),
        "prevalence_retenue": _taux([(etiquettes[i] == "retenue", poids[i]) for i in etiquetees]),
        "prevalence_a_revoir": _taux(
            [(etiquettes[i] in ("retenue", "indeterminee"), poids[i]) for i in etiquetees]
        ),
        "par_strate": {},
        "regles": {},
    }
    for strate in ("residu", "reste"):
        ids = [i for i in etiquetees if echantillon[i]["strate"] == strate]
        resultat["par_strate"][strate] = {
            "etiquetees": len(ids),
            "etiquettes": dict(Counter(etiquettes[i] for i in ids)),
        }

    executions = sorted(p for p in dossier.glob("regle-*") if (p / "reponses.jsonl").exists())
    verdicts_par_execution: list[dict[str, str | None]] = []
    for execution in executions:
        reponses = {r["id"]: r for r in _lire_jsonl(execution / "reponses.jsonl")}
        verdicts_par_execution.append({i: r.get("verdict") for i, r in reponses.items()})
        bloc = {"pannes": sum("panne" in r for r in reponses.values())}
        bloc["ensemble"] = _mesures_regle(reponses, etiquettes, poids, etiquetees)
        for strate in ("residu", "reste"):
            ids = [i for i in etiquetees if echantillon[i]["strate"] == strate]
            bloc[strate] = _mesures_regle(reponses, etiquettes, poids, ids)
        resultat["regles"][execution.name] = bloc
    if len(verdicts_par_execution) >= 2:
        a, b = verdicts_par_execution[:2]
        communs = [i for i in a if i in b and a[i] and b[i]]
        resultat["accord_entre_executions"] = f"{sum(a[i] == b[i] for i in communs)}/{len(communs)}"

    suffixe = "-toutes" if args.avec_pages_vides else ""
    (dossier / f"analyse{suffixe}.json").write_text(
        json.dumps(resultat, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    texte = [
        f"échantillon {resultat['echantillon']}, exploitables {resultat['exploitables']}, étiquetées {resultat['etiquetees']}",
        f"inexploitables : {resultat['inexploitables']['texte']}",
        f"étiquettes : {resultat['etiquettes']}",
        f"prévalence retenue : {resultat['prevalence_retenue']['texte']}",
        f"prévalence à revoir : {resultat['prevalence_a_revoir']['texte']}",
    ]
    for strate, bloc in resultat["par_strate"].items():
        texte.append(f"strate {strate} : {bloc}")
    for nom, bloc in resultat["regles"].items():
        texte.append(f"== {nom} (pannes {bloc['pannes']})")
        for portee in ("ensemble", "residu", "reste"):
            m = bloc[portee]
            texte.append(
                f"  [{portee}] jugées {m['pages_jugees']} ; bandes {m['bandes']} ; verdicts {m['verdicts']}"
            )
            for cle in (
                "part_doute_lecture",
                "part_doute_file",
                "pertes_a_revoir",
                "pertes_strictes",
                "admises_a_tort",
                "retenues_a_tort",
            ):
                texte.append(f"    {cle} : {m[cle]['texte']}")
    if "accord_entre_executions" in resultat:
        texte.append(
            f"accord des verdicts entre les deux exécutions : {resultat['accord_entre_executions']}"
        )
    (dossier / f"analyse{suffixe}.txt").write_text("\n".join(texte) + "\n", encoding="utf-8")
    print("\n".join(texte))
    return 0


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sous = parseur.add_subparsers(dest="commande", required=True)
    sous.add_parser("tirer").set_defaults(fonction=tirer)
    for nom, fonction in (("telecharger", telecharger), ("regle", regle)):
        p = sous.add_parser(nom)
        p.add_argument("dossier")
        p.set_defaults(fonction=fonction)
    p = sous.add_parser("analyser")
    p.add_argument("dossier")
    p.add_argument("etiquettes")
    p.add_argument("--avec-pages-vides", action="store_true")
    p.set_defaults(fonction=analyser)
    args = parseur.parse_args()
    return args.fonction(args)


if __name__ == "__main__":
    raise SystemExit(main())
