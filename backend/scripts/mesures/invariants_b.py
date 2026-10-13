"""Mesure : les invariants et pièges annoncés par la cartographie tiennent-ils dans le code ?

Commande (depuis backend/) :

    uv run python scripts/mesures/invariants_b.py

Porte sur l'orchestration, la prospection et la veille
(docs/refonte-pipeline/cartographie/{orchestration,prospection,veille}.md). Le
classement invariant par invariant est dans la note
docs/refonte-pipeline/notes/invariants-b.md ; ce script produit les chiffres et
les expériences qui l'étayent.

Aucun appel réseau : tous les clients HTTP reçoivent un `httpx.MockTransport`.
Aucun appel de modèle : l'ingestion est remplacée par une fonction factice, Jev
par un transport simulé. Aucun script du pipeline n'est lancé ; on importe des
modules (`pipeline.web`, `pipeline.verrou`, `pipeline.etat`,
`ingestion.orchestrateur`, `prospection.collecte`, `prospection.arbitre`,
`prospection.lecture`, `veille_aides`) sans rien écrire dans data/.

Écrit seulement dans `data/reviews/logs/refonte/2026-10-10-invariants-b-1/` :

- `resultats.json` : toutes les mesures, une clé par expérience (E1 à E10) ;
- `resume.txt` : la même chose en lignes lisibles ;
- `ecrivains.tsv` : qui écrit quel fichier partagé, avec ou sans verrou ;
- `bac-a-sable/` : fichiers jetables des expériences de verrou et de file
  (copies synthétiques, jamais la vraie file).

Durée : une minute environ (les expériences de politesse attendent de vraies
secondes, comme le Fetcheur).
"""

from __future__ import annotations

import contextlib
import io
import json
import math
import multiprocessing as mp
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

BACKEND = Path(__file__).resolve().parents[2]
RACINE = BACKEND.parent
SCRIPTS = BACKEND / "scripts"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(SCRIPTS))

SORTIE = BACKEND / "data/reviews/logs/refonte/2026-10-10-invariants-b-1"
BAC = SORTIE / "bac-a-sable"

RESULTATS: dict[str, object] = {}
LIGNES: list[str] = []


def dire(texte: str = "") -> None:
    LIGNES.append(texte)
    print(texte, flush=True)


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - m, 4), round(c + m, 4)]


def taux(k: int, n: int) -> dict:
    return {"k": k, "n": n, "p": round(k / n, 4) if n else None, "wilson95": wilson(k, n)}


def fmt(t: dict) -> str:
    if not t["n"]:
        return f"{t['k']}/0"
    lo, hi = t["wilson95"]
    return f"{t['k']}/{t['n']} = {100 * t['p']:.1f} % [{100 * lo:.1f} ; {100 * hi:.1f}]"


# ---------------------------------------------------------------------------
# E1 : la politesse du Fetcheur (pipeline/web.py)
# ---------------------------------------------------------------------------


def _transport_journal(journal: list, horloge, reponse):
    """Un transport simulé qui note (instant, hôte, chemin) de chaque requête."""
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        journal.append((horloge(), request.url.host, request.url.path))
        return reponse(request)

    return httpx.MockTransport(handler)


def _html(_request):
    import httpx

    return httpx.Response(
        200, text="<html>" + "x" * 800 + "</html>", headers={"content-type": "text/html"}
    )


def _ecarts(instants: list[float]) -> list[float]:
    s = sorted(instants)
    return [round(b - a, 3) for a, b in zip(s, s[1:], strict=False)]


def _enfant_politesse(depart, file_resultats, n: int) -> None:
    """Un processus qui fait `n` requêtes vers le même hôte, sur son propre Fetcheur."""
    sys.path.insert(0, str(SCRIPTS))
    from pipeline.web import Fetcheur

    journal: list = []
    f = Fetcheur(transport=_transport_journal(journal, time.time, _html), delai_s=1.0)
    depart.wait()
    for i in range(n):
        f.get(f"https://guide.example/fiche-{os.getpid()}-{i}")
    f.close()
    file_resultats.put([t for t, _h, _p in journal])


def e1_politesse() -> None:
    import httpx
    from pipeline.web import Fetcheur, Page, reinitialiser_delais

    dire("== E1 politesse du Fetcheur (transport simulé, délai réel de 1 s)")
    res: dict[str, object] = {}

    # a) même processus, deux Fetcheur, deux threads, même hôte
    reinitialiser_delais()
    journal: list = []
    t = _transport_journal(journal, time.monotonic, _html)
    f1, f2 = Fetcheur(transport=t, delai_s=1.0), Fetcheur(transport=t, delai_s=1.0)

    def rafale(f: Fetcheur, nom: str) -> None:
        for i in range(3):
            f.get(f"https://guide.example/{nom}-{i}")

    fils = [threading.Thread(target=rafale, args=(f, n)) for f, n in ((f1, "a"), (f2, "b"))]
    for th in fils:
        th.start()
    for th in fils:
        th.join()
    ecarts = _ecarts([x[0] for x in journal])
    res["intra_processus"] = {
        "requetes": len(journal),
        "ecart_min_s": min(ecarts),
        "ecarts": ecarts,
    }
    dire(
        f"  a) 1 processus, 2 Fetcheur x 3 requêtes : écart minimal {min(ecarts):.3f} s ({len(journal)} requêtes)"
    )

    # b) deux processus, même hôte : chacun a ses verrous de module
    ctx = mp.get_context("spawn")
    depart, q = ctx.Event(), ctx.Queue()
    procs = [ctx.Process(target=_enfant_politesse, args=(depart, q, 3)) for _ in range(2)]
    for p in procs:
        p.start()
    time.sleep(2.0)  # laisser les deux enfants importer httpx avant le départ commun
    depart.set()
    instants = [x for _ in procs for x in q.get(timeout=60)]
    for p in procs:
        p.join(timeout=60)
    ecarts = _ecarts(instants)
    sous_1s = sum(1 for e in ecarts if e < 0.9)
    res["inter_processus"] = {
        "requetes": len(instants),
        "ecart_min_s": min(ecarts),
        "ecarts_sous_0_9_s": sous_1s,
        "ecarts": ecarts,
    }
    dire(
        f"  b) 2 processus x 3 requêtes même hôte : écart minimal {min(ecarts):.3f} s, "
        f"{sous_1s}/{len(ecarts)} écarts sous 0,9 s"
    )

    # c) combien de requêtes un seul get() émet-il sur un 403 qui tient ?
    reinitialiser_delais()
    journal = []
    repli_appels: list[float] = []

    def toujours_403(_r):
        return httpx.Response(403, text="interdit", headers={"content-type": "text/html"})

    def repli(url: str, _timeout: float) -> Page:
        repli_appels.append(time.monotonic())
        return Page(
            url=url, url_finale=url, status=403, content_type="text/html", contenu=b"", texte=""
        )

    f = Fetcheur(
        transport=_transport_journal(journal, time.monotonic, toujours_403),
        delai_s=1.0,
        repli=repli,
    )
    f.get("https://guide.example/x")
    instants = [x[0] for x in journal] + repli_appels
    ecarts = _ecarts(instants)
    res["requetes_par_get_403"] = {
        "httpx": len(journal),
        "repli": len(repli_appels),
        "total": len(instants),
        "ecart_max_s": max(ecarts) if ecarts else None,
    }
    dire(
        f"  c) un get() sur un 403 persistant : {len(journal)} requêtes httpx + {len(repli_appels)} repli, "
        f"écart maximal {max(ecarts):.3f} s entre elles (le délai ne s'applique qu'une fois par get)"
    )

    # d) une réponse 503 est-elle mise en cache ?
    reinitialiser_delais()
    etat = {"n": 0}

    def puis_200(_r):
        etat["n"] += 1
        if etat["n"] == 1:
            return httpx.Response(503, text="surcharge")
        return _html(_r)

    f = Fetcheur(transport=httpx.MockTransport(puis_200), delai_s=0.0)
    p1, p2 = f.get("https://guide.example/y"), f.get("https://guide.example/y")
    res["cache_503"] = {"premier": p1.status, "second": p2.status, "requetes_emises": etat["n"]}
    dire(
        f"  d) 503 puis 200 sur la même URL, même Fetcheur : second get() rend {p2.status}, "
        f"{etat['n']} requête(s) émise(s)"
    )

    # e) une redirection vers un autre hôte n'est pas comptée pour cet hôte
    reinitialiser_delais()
    journal = []

    def redirige(r):
        if r.url.host == "a.example":
            return httpx.Response(302, headers={"location": "https://b.example/cible"})
        return _html(r)

    f = Fetcheur(transport=_transport_journal(journal, time.monotonic, redirige), delai_s=1.0)
    f.get("https://a.example/depart")
    f.get("https://b.example/autre")
    vers_b = [x[0] for x in journal if x[1] == "b.example"]
    ecart_b = round(vers_b[1] - vers_b[0], 3) if len(vers_b) == 2 else None
    res["redirection_autre_hote"] = {"requetes_vers_b": len(vers_b), "ecart_s": ecart_b}
    dire(
        f"  e) a.example redirige vers b.example, puis get(b.example) : écart entre les 2 requêtes vers b = {ecart_b} s"
    )
    RESULTATS["E1_politesse"] = res


# ---------------------------------------------------------------------------
# E2 : verrou et écriture atomique (pipeline/verrou.py)
# ---------------------------------------------------------------------------


def _valider_rien(_t: str) -> None:
    return None


def _enfant_ajouts(chemin: str, n: int, avec_verrou: bool, depart) -> None:
    sys.path.insert(0, str(SCRIPTS))
    from pipeline.verrou import ajouter_sous_verrou

    p = Path(chemin)
    depart.wait()
    for i in range(n):
        ligne = f"{os.getpid()}-{i}\n"
        if avec_verrou:
            ajouter_sous_verrou(p, ligne, valider=_valider_rien)
        else:
            # Le patron de fusionner_faits.py / retyper_faits.py : lire, modifier, write_text.
            courant = p.read_text(encoding="utf-8") if p.exists() else ""
            p.write_text(courant + ligne, encoding="utf-8")


def e2_verrou() -> None:
    from pipeline.verrou import ecrire_atomique

    dire("\n== E2 verrou et écriture atomique")
    res: dict[str, object] = {}
    ctx = mp.get_context("spawn")
    for avec in (True, False):
        cible = BAC / f"ajouts-{'verrou' if avec else 'sans-verrou'}.txt"
        cible.unlink(missing_ok=True)
        depart = ctx.Event()
        procs = [
            ctx.Process(target=_enfant_ajouts, args=(str(cible), 200, avec, depart))
            for _ in range(2)
        ]
        for p in procs:
            p.start()
        time.sleep(1.5)
        depart.set()
        for p in procs:
            p.join(timeout=120)
        lignes = cible.read_text(encoding="utf-8").splitlines() if cible.exists() else []
        cle = "avec_verrou" if avec else "sans_verrou_lire_modifier_ecrire"
        res[cle] = {
            "attendues": 400,
            "presentes": len(lignes),
            "perdues": taux(400 - len(lignes), 400),
        }
        dire(f"  a) 2 processus x 200 ajouts, {cle} : {len(lignes)}/400 lignes présentes")

    # b) ecrire_atomique appelé par deux threads d'un même processus SANS verrou :
    # le nom du temporaire ne dépend que du PID.
    cible = BAC / "atomique-meme-pid.txt"
    erreurs: Counter = Counter()

    def ecrit(n: int, tag: str) -> None:
        for i in range(n):
            try:
                ecrire_atomique(cible, f"{tag}-{i}\n" * 50)
            except Exception as exc:  # noqa: BLE001
                erreurs[type(exc).__name__] += 1

    fils = [threading.Thread(target=ecrit, args=(300, t)) for t in ("a", "b")]
    for th in fils:
        th.start()
    for th in fils:
        th.join()
    contenu = cible.read_text(encoding="utf-8").splitlines()
    melange = len({li.split("-")[0] for li in contenu}) > 1
    res["ecrire_atomique_deux_threads_sans_verrou"] = {
        "ecritures": 600,
        "exceptions": dict(erreurs),
        "fichier_final_melange": melange,
    }
    dire(
        f"  b) 2 threads x 300 ecrire_atomique sans verrou : exceptions {dict(erreurs) or 0}, fichier mêlé : {melange}"
    )

    # c) une écriture qui échoue en cours laisse-t-elle un temporaire ?
    cible = BAC / "atomique-echec.txt"
    cible.write_text("version saine\n", encoding="utf-8")
    try:
        ecrire_atomique(cible, "début\n" + "\udcff")
        leve = None
    except Exception as exc:  # noqa: BLE001
        leve = type(exc).__name__
    restes = sorted(p.name for p in BAC.glob(".atomique-echec.txt.tmp*"))
    res["ecrire_atomique_echec"] = {
        "exception": leve,
        "cible_intacte": cible.read_text(encoding="utf-8") == "version saine\n",
        "temporaires_laisses": restes,
    }
    dire(f"  c) écriture interrompue ({leve}) : cible intacte, temporaires laissés : {restes}")

    source = (SCRIPTS / "pipeline/verrou.py").read_text(encoding="utf-8")
    res["fsync_present"] = "fsync" in source
    dire(f"  d) os.fsync présent dans verrou.py : {res['fsync_present']}")
    RESULTATS["E2_verrou"] = res


# ---------------------------------------------------------------------------
# E3 : qui écrit les fichiers partagés, avec ou sans verrou (lecture statique)
# ---------------------------------------------------------------------------

PARTAGES = {
    "facts_pending.yaml": re.compile(r"FACTS_PENDING|pending_path|facts_pending"),
    "facts.yaml": re.compile(r"\bFACTS_FILE\b|facts_path|facts\.yaml"),
    "file-attente.yaml": re.compile(r"FILE_ATTENTE|args\.etat|etat_path"),
    "veille-state.yaml": re.compile(r"MANIFEST_PATH|write_manifest"),
}
ECRITURE = re.compile(
    r"\.write_text\(|os\.replace\(|ecrire_atomique\(|write_manifest\(|\bopen\([^)]*[\"']w"
)
VERROU = re.compile(
    r"verrou_fichier|ajouter_sous_verrou|reecrire_sous_verrou|mettre_a_jour\(|transition\(|fusionner\("
)


def e3_ecrivains() -> None:
    dire(
        "\n== E3 écrivains des fichiers partagés (scan statique de scripts/, hors mesures/ et tests)"
    )
    lignes_tsv = ["fichier_source\tligne\tfichier_partage_mentionne\tverrou_dans_le_fichier\tcode"]
    par_fichier: dict[str, dict] = {}
    for py in sorted(SCRIPTS.rglob("*.py")):
        rel = py.relative_to(BACKEND).as_posix()
        if "/mesures/" in rel or "/seeds/" in rel:
            continue
        texte = py.read_text(encoding="utf-8")
        cibles = [nom for nom, motif in PARTAGES.items() if motif.search(texte)]
        if not cibles:
            continue
        verrou = bool(VERROU.search(texte))
        for i, li in enumerate(texte.splitlines(), 1):
            if ECRITURE.search(li) and not li.strip().startswith("#"):
                lignes_tsv.append(f"{rel}\t{i}\t{','.join(cibles)}\t{verrou}\t{li.strip()[:120]}")
                par_fichier.setdefault(rel, {"cibles": cibles, "verrou": verrou, "lignes": []})[
                    "lignes"
                ].append(i)
    (SORTIE / "ecrivains.tsv").write_text("\n".join(lignes_tsv) + "\n", encoding="utf-8")
    RESULTATS["E3_ecrivains"] = par_fichier
    for rel, d in par_fichier.items():
        dire(
            f"  {rel} : {', '.join(d['cibles'])} ; verrou importé : {d['verrou']} ; écritures l. {d['lignes'][:8]}"
        )


# ---------------------------------------------------------------------------
# E4 : le budget global de l'orchestrateur (ingestion simulée)
# ---------------------------------------------------------------------------


def _file_synthetique(chemin: Path, n: int) -> list[str]:
    from pipeline.etat import Tache, ecrire

    slugs = [f"aide-{i:02d}" for i in range(n)]
    taches = {
        s: Tache(titre=s, url=f"https://x.example/{s}", territoire="test", statut="valide")
        for s in slugs
    }
    for p in (chemin, chemin.with_name(chemin.name + ".lock")):
        p.unlink(missing_ok=True)
    ecrire(chemin, taches)
    return slugs


def _faux_ingerer(cout: float | None, *, transitoire: bool = False, duree: float = 0.05):
    from ingestion.worker import ResultatIngestion
    from pipeline.llm import Compteur

    def ingerer(slug, _tache, _config, *, contexte, compteur):  # noqa: ARG001
        time.sleep(duree)
        local = Compteur()
        local.ajouter_decision(cout, 0, "faux")
        compteur.fusionner(local, f"aide:{slug}")  # comme worker.ingerer_aide : à la FIN
        return ResultatIngestion(
            slug=slug,
            ok=not transitoire,
            arret="erreur_modele" if transitoire else "termine",
            tours=1,
            cout_usd=cout or 0.0,
            cout_inconnu=cout is None,
            modele="faux",
            modele_verif="faux",
            debut="",
            fin="",
            motif_echec="aucun fichier YAML écrit" if transitoire else None,
            echec_transitoire=transitoire,
        )

    return ingerer


def e4_budget() -> None:
    from ingestion import orchestrateur
    from pipeline.etat import charger
    from pipeline.llm import Compteur

    dire("\n== E4 budget global et disjoncteur de l'orchestrateur (ingestion factice)")
    orchestrateur.ContextePartage = SimpleNamespace(construire=lambda _a: None)  # type: ignore[attr-defined]
    res: dict[str, object] = {}

    def lancer(
        n, parallele, budget_total, budget_aide, cout, *, duree=0.05, transitoire=False, disj=None
    ):
        chemin = BAC / "file-budget.yaml"
        slugs = _file_synthetique(chemin, n)
        config = SimpleNamespace(
            atelier=lambda _s: None, limites=SimpleNamespace(budget_usd=budget_aide)
        )
        compteur = Compteur()
        with contextlib.redirect_stdout(io.StringIO()):
            resultats = orchestrateur.executer(
                slugs,
                config,  # type: ignore[arg-type]
                parallele=parallele,
                budget_total=budget_total,
                etat_path=chemin,
                compteur=compteur,
                ingerer=_faux_ingerer(cout, transitoire=transitoire, duree=duree),
                disjoncteur=disj,
            )
        statuts = Counter(t.statut for t in charger(chemin).values())
        return {
            "aides_lancees": len(resultats),
            "depense": round(compteur.cout_usd, 4),
            "cout_inconnu": compteur.cout_inconnu,
            "budget_total": budget_total,
            "depassement": round(compteur.cout_usd - budget_total, 4),
            "statuts_finaux": dict(statuts),
        }

    for p in (1, 3, 10):
        r = lancer(30, p, 6.0, 1.5, 1.45)
        res[f"budget_parallele_{p}"] = r
        dire(
            f"  a) 30 aides à 1,45 $, plafond par aide 1,50 $, total 6,00 $, parallele={p} : "
            f"{r['aides_lancees']} lancées, {r['depense']:.2f} $ dépensés (dépassement {r['depassement']:+.2f} $)"
        )
    res["borne_theorique_balayage"] = {
        "formule": "total + (parallele - 1) x budget_aide, au plus",
        "parallele": 10,
        "budget_aide": 1.5,
        "budget_total": 60.0,
        "depassement_max_usd": round(9 * 1.5, 2),
    }
    dire(
        "     borne : dépassement <= (parallele - 1) x budget_aide ; défauts de balayage.py (10, 1,50 $) : 13,50 $ sur 60 $"
    )
    r = lancer(12, 3, 2.0, 1.5, None)
    res["budget_cout_inconnu"] = r
    dire(
        f"  b) coût inconnu (tarif absent), total 2,00 $ : {r['aides_lancees']}/12 lancées, budget sans effet"
    )

    disj = orchestrateur.Disjoncteur(dormir=lambda _s: None)
    r = lancer(20, 3, 50.0, 1.5, 0.0, transitoire=True, disj=disj)
    r["salves"] = disj.salves
    r["motif"] = disj.motif[:80]
    res["disjoncteur_tout_transitoire"] = r
    dire(
        f"  c) 20 aides en panne transitoire, parallele=3 : {r['aides_lancees']} lancées avant l'arrêt, "
        f"statuts finaux {r['statuts_finaux']}"
    )
    RESULTATS["E4_orchestrateur"] = res


# ---------------------------------------------------------------------------
# E5 : Jev, réponse au format changé (pipeline/decision.py, prospection/arbitre.py)
# ---------------------------------------------------------------------------


def e5_jev() -> None:
    import httpx
    from pipeline.decision import ClientDecision, ErreurDecision
    from pipeline.web import Fetcheur
    from prospection import arbitre, lecture
    from prospection.collecte import Candidat
    from prospection.territoires import Territoire

    dire("\n== E5 Jev : réponse au format changé (transport simulé)")
    res: dict[str, object] = {}

    def client(answers: dict) -> ClientDecision:
        def handler(_r):
            return httpx.Response(
                200, json={"answers": answers, "model": "simule", "usage": {"cost": 0.0}}
            )

        return ClientDecision(cle="factice", transport=httpx.MockTransport(handler), tentatives=1)

    format_change = {k: {"type": "noul", "value": 0.95} for k in arbitre.QUESTIONS}
    for k in ("destinataire", "objet", "categorie_ecart"):
        format_change[k] = {"type": "choice", "selected": "proprietaire_gestionnaire"}
    a = arbitre.arbitrer(client(format_change), "https://x.example/aide", "texte de page " * 50)
    res["cles_presentes_format_interne_change"] = {
        "deposable": a.deposable,
        "destinataire": a.destinataire,
        "bande": a.bande,
    }
    dire(
        f"  a) clés présentes, valeurs sous un autre nom : deposable={a.deposable}, destinataire={a.destinataire!r}, bande={a.bande}"
    )

    manque = {k: v for k, v in format_change.items() if k != "objet"}
    try:
        arbitre.arbitrer(client(manque), "https://x.example/aide", "texte")
        res["cle_absente"] = "aucune erreur"
    except ErreurDecision as exc:
        res["cle_absente"] = f"ErreurDecision : {str(exc)[:60]}"
    dire(f"  b) une clé de question absente : {res['cle_absente']}")

    # c) conséquence dans la lecture. Deux dérives : seules les probabilités
    # (noul) changent de nom, ou tout change de nom.
    appels_llm: list[int] = []

    class LLM:
        def try_complete_json(self, *a, **k):
            appels_llm.append(1)
            raise AssertionError("le LLM n'aurait pas dû être appelé")

    def page(_r):
        return httpx.Response(
            200,
            text="<html><h1>Restauration du patrimoine</h1><p>"
            + "Aide aux propriétaires. " * 60
            + "</p></html>",
            headers={"content-type": "text/html"},
        )

    f = Fetcheur(transport=httpx.MockTransport(page), delai_s=0.0)
    terr = Territoire(
        nom="Test", type="region", prefixe_slug="tt", statut="pret", guides=["https://x.example/"]
    )
    noul_seul = dict(format_change)
    noul_seul["destinataire"] = {"type": "choice", "choice": "proprietaire_gestionnaire"}
    noul_seul["objet"] = {"type": "choice", "choice": "bien_ou_lieu"}
    noul_seul["categorie_ecart"] = {"type": "choice", "choice": "objet_hors_lieu"}
    for nom, answers in (("noul_renomme", noul_seul), ("tout_renomme", format_change)):
        appels_llm.clear()
        try:
            le = lecture.lire(
                Candidat(url="https://x.example/aide", titre="Restauration"),
                terr,
                f,
                LLM(),  # type: ignore[arg-type]
                arbitre=client(answers),
            )
            res[f"lecture_{nom}"] = {
                "exception": None,
                "appels_llm": len(appels_llm),
                "ecartee": le.ecartee,
                "statut_file_qui_serait_ecrit": "ignore" if le.ecartee else "a_valider",
                "note": le.fiche.note if le.fiche else None,
            }
            dire(
                f"  c) lecture.lire, {nom} : {len(appels_llm)} appel LLM, page écartée={le.ecartee} "
                f"(file : {'ignore' if le.ecartee else 'a_valider'})"
            )
        except Exception as exc:  # noqa: BLE001, c'est précisément ce qu'on mesure
            res[f"lecture_{nom}"] = {"exception": f"{type(exc).__name__}: {str(exc)[:120]}"}
            dire(
                f"  c) lecture.lire, {nom} : lève {type(exc).__name__} (la docstring dit « ne lève jamais »)"
            )
    RESULTATS["E5_jev_format"] = res


# ---------------------------------------------------------------------------
# E6 : bornes de collecte (prospection/collecte.py)
# ---------------------------------------------------------------------------


def e6_collecte() -> None:
    import yaml
    from prospection.collecte import (
        MAX_REPETITIONS_SEGMENT,
        MAX_SEGMENTS_CHEMIN,
        chemin_en_boucle,
        liens,
    )

    dire("\n== E6 bornes de collecte : chemin_en_boucle et <base href>")
    res: dict[str, object] = {}
    # a) la concaténation de la Moselle, génération par génération
    gen = []
    chemin = "jcms/pl_17395/fr/subventions"
    for k in range(1, 8):
        chemin = (
            "jcms/pl_17395/fr/" + "/".join(["jcms", f"pl_{9000 + k}", "fr"] * k) + "/subventions"
        )
        url = f"https://www.moselle.fr/{chemin}"
        segs = [s for s in urlsplit(url).path.split("/") if s]
        gen.append(
            {
                "generation": k,
                "segments": len(segs),
                "max_repetition": max(Counter(segs).values()),
                "detectee": chemin_en_boucle(url),
            }
        )
    res["moselle_generations"] = gen
    premiere = next((g["generation"] for g in gen if g["detectee"]), None)
    dire(
        f"  a) concaténation jcms/<id>/fr répétée : première génération détectée = {premiere} (seuils : > {MAX_SEGMENTS_CHEMIN} segments ET > {MAX_REPETITIONS_SEGMENT} répétitions)"
    )
    for g in gen:
        dire(
            f"     gén. {g['generation']} : {g['segments']} segments, répétition max {g['max_repetition']}, détectée {g['detectee']}"
        )

    # b) toutes les URL connues du dépôt : faux positifs et profondeur
    urls: dict[str, str] = {}
    for f in sorted((BACKEND / "data/prospection").glob("*/candidats.jsonl")):
        for li in f.read_text(encoding="utf-8").splitlines():
            if li.strip():
                urls.setdefault(json.loads(li)["url"], f"candidats:{f.parent.name}")
    file = (
        yaml.load(
            (BACKEND / "data/prospection/file-attente.yaml").read_text(encoding="utf-8"),
            Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader),
        )
        or {}
    )
    for t in file.values():
        urls.setdefault(t["url"], "file")
    from aides_schema import charger_yaml

    for y in sorted((BACKEND / "data/aides").glob("*.yaml")):
        d = charger_yaml(y.read_text(encoding="utf-8")) or {}
        u = ((d.get("source") or {}).get("url_officielle")) or None
        if u:
            urls.setdefault(u, "catalogue")
    detectees = [u for u in urls if chemin_en_boucle(u)]
    profondes = [
        u for u in urls if len([s for s in urlsplit(u).path.split("/") if s]) > MAX_SEGMENTS_CHEMIN
    ]
    repet3 = [
        u
        for u in urls
        if (segs := [s for s in urlsplit(u).path.split("/") if s])
        and max(Counter(segs).values()) > MAX_REPETITIONS_SEGMENT
    ]
    res["urls_connues"] = {
        "n": len(urls),
        "par_origine": dict(Counter(urls.values())),
        "detectees_en_boucle": taux(len(detectees), len(urls)),
        "plus_de_12_segments": len(profondes),
        "un_segment_plus_de_2_fois": len(repet3),
        "exemples_repet3": repet3[:5],
    }
    dire(
        f"  b) {len(urls)} URL connues (candidats, file, catalogue) : détectées en boucle {fmt(taux(len(detectees), len(urls)))} ; "
        f"> 12 segments : {len(profondes)} ; un segment > 2 fois : {len(repet3)}"
    )

    # c) <base href> : quoté seulement ?
    from pipeline.web import Page

    def page(html: str) -> Page:
        return Page(
            url="https://x.fr/a/b/page",
            url_finale="https://x.fr/a/b/page",
            status=200,
            content_type="text/html",
            contenu=html.encode(),
            texte=html,
        )

    corps = '<a href="jcms/lw_2/fr/aide">Aide</a>' + "<p>" + "texte " * 200 + "</p>"
    quote = liens(page('<html><head><base href="https://x.fr/"></head>' + corps + "</html>"))
    sans_quote = liens(page("<html><head><base href=https://x.fr/></head>" + corps + "</html>"))
    res["base_href"] = {
        "guillemets": quote[0][1] if quote else None,
        "sans_guillemets": sans_quote[0][1] if sans_quote else None,
    }
    dire(
        f'  c) <base href="…"> : {res["base_href"]["guillemets"]} ; <base href=…> sans guillemets : {res["base_href"]["sans_guillemets"]}'
    )

    # d) la sitemap ouvre-t-elle tout avant d'appliquer le plafond ?
    import httpx
    from pipeline.web import Fetcheur
    from prospection.collecte import collecter
    from prospection.territoires import Strategie, Territoire

    ouvertes: list[str] = []

    def handler(r):
        if r.url.path.endswith("sitemap.xml"):
            locs = "".join(
                f"<url><loc>https://g.example/aides/fiche-{i}</loc></url>" for i in range(60)
            )
            return httpx.Response(
                200,
                text=f'<?xml version="1.0"?><urlset>{locs}</urlset>',
                headers={"content-type": "application/xml"},
            )
        ouvertes.append(r.url.path)
        return httpx.Response(
            200,
            text=f"<html><h1>Fiche {r.url.path}</h1><p>{'mot ' * 30}</p></html>",
            headers={"content-type": "text/html"},
        )

    terr = Territoire(
        nom="T",
        type="region",
        prefixe_slug="tt",
        statut="pret",
        guides=["https://g.example/sitemap.xml"],
        strategie=Strategie(type="sitemap", url="https://g.example/sitemap.xml", max_candidats=10),
    )
    with contextlib.redirect_stdout(io.StringIO()):
        col = collecter(terr, Fetcheur(transport=httpx.MockTransport(handler), delai_s=0.0), {})
    res["sitemap_plafond"] = {
        "max_candidats": 10,
        "fiches_ouvertes": len(ouvertes),
        "candidates_rendues": len(col.candidats),
        "plafonnee": col.plafonnee,
    }
    dire(
        f"  d) sitemap de 60 fiches, max_candidats=10 : {len(ouvertes)} fiches ouvertes (1 s chacune en vrai), {len(col.candidats)} rendues"
    )
    RESULTATS["E6_collecte"] = res


# ---------------------------------------------------------------------------
# E7 : hôtes partagés entre territoires (balayage parallèle = processus distincts)
# ---------------------------------------------------------------------------


def e7_territoires() -> None:
    from prospection.territoires import charger_territoires

    dire("\n== E7 hôtes de guide partagés entre clés de territoires.yaml")
    terr = charger_territoires()
    par_hote: dict[str, set[str]] = defaultdict(set)
    actifs = {k: t for k, t in terr.items() if t.statut != "sans_point_entree"}
    for k, t in actifs.items():
        for g in [*t.guides, *t.strategie.urls_sitemap, *t.pages_paginees()[:1]]:
            par_hote[urlsplit(g).netloc.lower()].add(k)
    partages = {h: sorted(ks) for h, ks in par_hote.items() if len(ks) > 1}
    # Les pages LUES (étage 3) ne sont pas toutes sur l'hôte du guide : quels
    # hôtes de la file servent plusieurs territoires ?
    from pipeline.etat import charger

    file = charger(BACKEND / "data/prospection/file-attente.yaml")
    hotes_file: dict[str, set[str]] = defaultdict(set)
    taches_par_hote: Counter = Counter()
    for t in file.values():
        h = urlsplit(t.url).netloc.lower()
        hotes_file[h].add(t.territoire)
        taches_par_hote[h] += 1
    multi = {h: len(ts) for h, ts in hotes_file.items() if len(ts) > 1}
    taches_multi = sum(taches_par_hote[h] for h in multi)
    RESULTATS["E7_hotes_file_multi_territoires"] = {
        "hotes": len(hotes_file),
        "hotes_multi_territoires": taux(len(multi), len(hotes_file)),
        "taches_sur_ces_hotes": taux(taches_multi, len(file)),
        "top": sorted(multi.items(), key=lambda kv: -kv[1])[:10],
    }
    dire(
        f"  file : {len(hotes_file)} hôtes ; servant plusieurs territoires {fmt(taux(len(multi), len(hotes_file)))}, "
        f"portant {fmt(taux(taches_multi, len(file)))} des tâches ; top {sorted(multi.items(), key=lambda kv: -kv[1])[:5]}"
    )
    RESULTATS["E7_territoires"] = {
        "territoires": len(terr),
        "avec_point_entree": len(actifs),
        "hotes": len(par_hote),
        "hotes_partages": partages,
        "multi_departements": {k: t.departements for k, t in terr.items() if t.departements},
    }
    dire(
        f"  {len(actifs)}/{len(terr)} territoires avec point d'entrée, {len(par_hote)} hôtes, {len(partages)} hôte(s) partagé(s) : {partages}"
    )


# ---------------------------------------------------------------------------
# E8 : la file d'attente telle qu'elle est (doublons, motifs, tri)
# ---------------------------------------------------------------------------


def e8_file() -> None:
    from pipeline.etat import charger, doublons_par_url
    from prospection.collecte import cle_fiche

    dire("\n== E8 file d'attente (lecture seule de data/prospection/file-attente.yaml)")
    file = charger(BACKEND / "data/prospection/file-attente.yaml")
    statuts = Counter(t.statut for t in file.values())
    ecartes = doublons_par_url(file)
    actifs = {s: v for s, v in ecartes.items() if file[s].statut not in ("ignore",)}
    groupes_actifs = Counter((file[s].statut, file[v].statut) for s, v in actifs.items())
    motif_sans_ignore = Counter(
        t.statut for t in file.values() if t.motif_ignore and t.statut != "ignore"
    )
    ignore_sans_motif = sum(1 for t in file.values() if t.statut == "ignore" and not t.motif_ignore)
    res = {
        "taches": len(file),
        "statuts": dict(statuts),
        "doublons_url_non_ignores": {
            "n": len(actifs),
            "paires_statut": {f"{a}->{b}": n for (a, b), n in groupes_actifs.items()},
        },
        "motif_ignore_sur_statut_autre": dict(motif_sans_ignore),
        "ignore_sans_motif": taux(ignore_sans_motif, statuts["ignore"]),
    }
    dire(f"  {len(file)} tâches, statuts {dict(statuts)}")
    dire(
        f"  doublons d'URL (cle_fiche) encore hors `ignore` : {len(actifs)} ; paires (écarté -> survivant) {dict(groupes_actifs)}"
    )
    dire(f"  motif_ignore porté par un statut autre qu'ignore : {dict(motif_sans_ignore)}")
    dire(f"  ignore sans motif : {fmt(res['ignore_sans_motif'])}")

    # Les écartées du TRI n'entrent pas dans la file : reviennent-elles ?
    cles_file = {cle_fiche(t.url) for t in file.values()}
    from aides_schema import charger_yaml

    cles_cat = set()
    for y in (BACKEND / "data/aides").glob("*.yaml"):
        d = charger_yaml(y.read_text(encoding="utf-8")) or {}
        for k in ("url_officielle", "formulaire_url"):
            if u := (d.get("source") or {}).get(k):
                cles_cat.add(cle_fiche(u))
    tri = Counter()
    hors = 0
    sans_info = 0
    for f in sorted((BACKEND / "data/prospection").glob("*/tri.jsonl")):
        for li in f.read_text(encoding="utf-8").splitlines():
            if not li.strip():
                continue
            d = json.loads(li)
            tri[d["decision"]] += 1
            if d["decision"] == "ecarter":
                c = cle_fiche(d["url"])
                if c not in cles_file and c not in cles_cat:
                    hors += 1
            if "sans titre ni contexte" in (d.get("motif") or ""):
                sans_info += 1
    n_ecart = tri["ecarter"]
    res["tri_suivis"] = {
        "decisions": dict(tri),
        "ecartees_au_tri": taux(n_ecart, sum(tri.values())),
        "ecartees_absentes_file_et_catalogue": taux(hors, n_ecart),
        "requalifiees_sans_info": sans_info,
    }
    dire(
        f"  tri.jsonl suivis par git : {dict(tri)} ; écartées par le modèle au tri {fmt(res['tri_suivis']['ecartees_au_tri'])}"
    )
    dire(
        f"  écartées au tri absentes de la file et du catalogue (re-proposées au balayage suivant) : {fmt(res['tri_suivis']['ecartees_absentes_file_et_catalogue'])}"
    )
    RESULTATS["E8_file"] = res


# ---------------------------------------------------------------------------
# E9 : gabarit de site et périmètre d'un passage de veille (--limit)
# ---------------------------------------------------------------------------


def e9_gabarit() -> None:
    import veille_aides
    from veille_analyze import CHROME_MIN_URLS

    from aides_schema import load_aide

    dire("\n== E9 gabarit de site : couverture selon le périmètre du passage de veille")
    manifeste = veille_aides.load_manifest()
    aides = {p.stem: load_aide(p) for p in sorted((BACKEND / "data/aides").glob("*.yaml"))}
    urls_par_slug = {
        s: [e["url"] for e in (manifeste.get(s) or {}).get("urls") or []] for s in aides
    }

    def couverture(selection: list[str]) -> dict:
        par_hote: dict[str, set[str]] = defaultdict(set)
        for s in selection:
            for u in urls_par_slug.get(s, []):
                par_hote[urlsplit(u).netloc.lower()].add(u)
        n_urls = sum(len(v) for v in par_hote.values())
        couvertes = sum(len(v) for v in par_hote.values() if len(v) >= CHROME_MIN_URLS)
        # Densité : combien d'URL du même hôte chaque URL voit-elle à côté d'elle,
        # dans ce passage et dans le parc entier ?
        dans_run = sorted(len(v) for v in par_hote.values() for _ in v)
        dans_parc = sorted(len(urls_parc[h]) for h, v in par_hote.items() for _ in v)
        return {
            "aides": len(selection),
            "urls": n_urls,
            "hotes": len(par_hote),
            "urls_sur_hote_reconnaissable": taux(couvertes, n_urls),
            "urls_meme_hote_mediane_run": dans_run[len(dans_run) // 2] if dans_run else None,
            "urls_meme_hote_mediane_parc": dans_parc[len(dans_parc) // 2] if dans_parc else None,
        }

    urls_parc: dict[str, set[str]] = defaultdict(set)
    for s in aides:
        for u in urls_par_slug.get(s, []):
            urls_parc[urlsplit(u).netloc.lower()].add(u)

    ordre = [
        a.slug
        for a in sorted(
            aides.values(), key=lambda a: (veille_aides.anciennete(a, manifeste), a.slug)
        )
    ]
    res = {"parc": couverture(list(aides))}
    for n in (10, 20, 50, 100):
        res[f"limit_{n}"] = couverture(ordre[:n])
    RESULTATS["E9_gabarit"] = res
    for k, v in res.items():
        dire(
            f"  {k:<10} {v['aides']:>4} aides, {v['urls']:>4} URL, {v['hotes']:>4} hôtes ; URL sur un hôte "
            f"où le gabarit se reconnaît : {fmt(v['urls_sur_hote_reconnaissable'])} ; URL du même hôte "
            f"(médiane) : {v['urls_meme_hote_mediane_run']} dans le passage, {v['urls_meme_hote_mediane_parc']} au parc"
        )


# ---------------------------------------------------------------------------
# E10 : fichiers .yaml.echec, fichiers ignorés suivis, journaux
# ---------------------------------------------------------------------------


def e10_divers() -> None:
    dire("\n== E10 état du dépôt")
    aides = BACKEND / "data/aides"
    echecs = sorted(aides.glob("*.yaml.echec"))
    entete = sum(
        1 for p in echecs if p.read_text(encoding="utf-8").startswith("# ÉCHEC D'INGESTION")
    )
    yamls = len(list(aides.glob("*.yaml")))
    vivantes_aussi = sum(1 for p in echecs if (aides / p.name.removesuffix(".echec")).exists())
    suivis_ignores = subprocess.run(
        ["git", "-C", str(RACINE), "ls-files", "-ci", "--exclude-standard"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()
    pipeline_suivis = [p for p in suivis_ignores if p.startswith("backend/")]
    RESULTATS["E10_depot"] = {
        "yaml": yamls,
        "yaml_echec": len(echecs),
        "echec_avec_entete_ingestion": entete,
        "echec_sans_entete": len(echecs) - entete,
        "echec_dont_le_yaml_vivant_existe": vivantes_aussi,
        "suivis_malgre_gitignore_backend": pipeline_suivis,
    }
    dire(
        f"  data/aides : {yamls} .yaml, {len(echecs)} .yaml.echec dont {entete} avec l'en-tête « # ÉCHEC D'INGESTION », {len(echecs) - entete} sans ; {vivantes_aussi} .echec ont aussi un .yaml vivant"
    )
    dire(f"  fichiers suivis malgré .gitignore sous backend/ : {len(pipeline_suivis)}")


def main() -> int:
    if BAC.exists():
        shutil.rmtree(BAC)
    BAC.mkdir(parents=True, exist_ok=True)
    e1_politesse()
    e2_verrou()
    e3_ecrivains()
    e4_budget()
    e5_jev()
    e6_collecte()
    e7_territoires()
    e8_file()
    e9_gabarit()
    e10_divers()
    (SORTIE / "resultats.json").write_text(
        json.dumps(RESULTATS, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    (SORTIE / "resume.txt").write_text("\n".join(LIGNES) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
