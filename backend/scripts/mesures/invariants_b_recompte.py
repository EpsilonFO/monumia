"""Recompte adverse de docs/refonte-pipeline/notes/invariants-b.md.

Commande (depuis backend/) :

    uv run python scripts/mesures/invariants_b_recompte.py

Écrit indépendamment du script du mesureur (`invariants_b.py`, non importé).
Aucun appel réseau (httpx.MockTransport partout), aucun appel de modèle
(ingestion factice, Jev simulé). Lecture seule de data/ et du checkout
principal ; écriture seulement sous
data/reviews/logs/refonte/2026-10-10-invariants-b-recompte-1/ (resultats.json,
resume.txt, bac-a-sable/).
"""

from __future__ import annotations

import collections
import glob
import json
import math
import multiprocessing as mp
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import yaml

BACKEND = Path(__file__).resolve().parents[2]
RACINE = BACKEND.parent
sys.path.insert(0, str(BACKEND / "scripts"))
sys.path.insert(0, str(BACKEND))

SORTIE = BACKEND / "data/reviews/logs/refonte/2026-10-10-invariants-b-recompte-1"
BAC = SORTIE / "bac-a-sable"
PRINCIPAL = Path("/Users/felixollivier/monumia/backend")

R: dict = {}
LIGNES: list[str] = []


def log(cle: str, valeur) -> None:
    R[cle] = valeur
    LIGNES.append(f"{cle} : {json.dumps(valeur, ensure_ascii=False, default=str)}")
    print(LIGNES[-1], flush=True)


def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * (c - h), 1), round(100 * (c + h), 1)]


# ---------------------------------------------------------------------------
# R1 : décompte des verdicts dans les tableaux de la note
# ---------------------------------------------------------------------------


def r1_verdicts() -> None:
    note = (RACINE / "docs/refonte-pipeline/notes/invariants-b.md").read_text(encoding="utf-8")
    par = collections.Counter()
    qualifies = []
    for ligne in note.splitlines():
        m = re.match(r"^\| ([OPV])([IP])(\d+) \|", ligne)
        if not m:
            continue
        cellules = [c.strip() for c in ligne.strip().strip("|").split("|")]
        verdict = cellules[2]
        base = verdict.split(" (")[0]
        par[(m.group(2), base)] += 1
        if "(" in verdict:
            qualifies.append(f"{cellules[0]}: {verdict}")
    log("R1_verdicts", {f"{k}:{v}": n for (k, v), n in sorted(par.items())})
    log("R1_verdicts_qualifies", qualifies)
    n_inv = sum(n for (k, _), n in par.items() if k == "I")
    k_inv = par[("I", "confirmé")]
    log("R1_invariants_confirmes", {"k": k_inv, "n": n_inv, "ic95": wilson(k_inv, n_inv)})
    # Nombre d'énoncés de premier niveau dans la cartographie
    carto = {}
    for nom in ("orchestration", "prospection", "veille"):
        texte = (RACINE / f"docs/refonte-pipeline/cartographie/{nom}.md").read_text(
            encoding="utf-8"
        )
        sec = None
        c = collections.Counter()
        for ligne in texte.splitlines():
            if ligne.startswith("## "):
                sec = ligne[3:].strip()
            elif sec in ("Invariants", "Pièges") and ligne.startswith("- "):
                c[sec] += 1
        carto[nom] = dict(c)
    log("R1_cartographie_enonces", carto)


# ---------------------------------------------------------------------------
# R2 : verrou et écriture atomique
# ---------------------------------------------------------------------------


def _ajouts_verrou(chemin: str, ident: int, n: int) -> None:
    from pipeline.verrou import ajouter_sous_verrou

    for i in range(n):
        ajouter_sous_verrou(Path(chemin), f"p{ident}-{i}\n", valider=lambda _t: None)


def _ajouts_sans_verrou(chemin: str, ident: int, n: int) -> None:
    p = Path(chemin)
    for i in range(n):
        texte = p.read_text(encoding="utf-8") if p.exists() else ""
        p.write_text(texte + f"p{ident}-{i}\n", encoding="utf-8")


def _compter(chemin: Path) -> int:
    lignes = [x for x in chemin.read_text(encoding="utf-8").splitlines() if x.strip()]
    return len(set(lignes))


def r2_verrou() -> None:
    BAC.mkdir(parents=True, exist_ok=True)
    ctx = mp.get_context("spawn")
    resultats = {"avec_verrou": [], "sans_verrou": []}
    for essai in range(5):
        for mode, fn in (("avec_verrou", _ajouts_verrou), ("sans_verrou", _ajouts_sans_verrou)):
            chemin = BAC / f"ajouts-{mode}-{essai}.txt"
            chemin.write_text("", encoding="utf-8")
            procs = [ctx.Process(target=fn, args=(str(chemin), j, 200)) for j in range(2)]
            for p in procs:
                p.start()
            for p in procs:
                p.join()
            resultats[mode].append(_compter(chemin))
    log("R2a_ajouts_gardes_sur_400_par_essai", resultats)

    # Écriture atomique : threads du même processus, même cible, sans verrou
    from pipeline.verrou import ecrire_atomique, verrou_fichier

    def ecrivain(cible: Path, erreurs: list, avec_verrou: bool) -> None:
        for i in range(200):
            try:
                if avec_verrou:
                    with verrou_fichier(cible):
                        ecrire_atomique(cible, f"{i}\n" * 50)
                else:
                    ecrire_atomique(cible, f"{i}\n" * 50)
            except Exception as exc:  # noqa: BLE001
                erreurs.append(type(exc).__name__)

    collisions = {"sans_verrou": [], "avec_verrou": []}
    for essai in range(5):
        for mode in ("sans_verrou", "avec_verrou"):
            cible = BAC / f"atomique-{mode}-{essai}.txt"
            erreurs: list[str] = []
            ths = [
                threading.Thread(target=ecrivain, args=(cible, erreurs, mode == "avec_verrou"))
                for _ in range(3)
            ]
            for t in ths:
                t.start()
            for t in ths:
                t.join()
            collisions[mode].append(len(erreurs))
    log("R2b_exceptions_sur_600_ecritures_par_essai", collisions)

    # Exposition : appels de ecrire_atomique hors verrou, par cible
    log(
        "R2c_appels_ecrire_atomique_hors_verrou",
        {
            "ingestion/outils.py:687": "atelier.yaml_path (un slug par worker)",
            "ingestion/outils.py:900": "atelier.review_path (un slug par worker)",
            "ingestion/outils.py:967": "atelier.review_path (un slug par worker)",
            "pipeline/etat.py:247 (ecrire)": "file-attente, appelants sous verrou",
        },
    )


# ---------------------------------------------------------------------------
# R3 : Fetcheur poli
# ---------------------------------------------------------------------------


def _horodater(reqs: list) -> httpx.MockTransport:
    def handler(req: httpx.Request) -> httpx.Response:
        reqs.append((time.time(), str(req.url)))
        return httpx.Response(200, text="<html>ok</html>", headers={"content-type": "text/html"})

    return httpx.MockTransport(handler)


def _processus_fetch(ident: int, depart: float, file) -> None:
    sys.path.insert(0, str(BACKEND / "scripts"))
    from pipeline.web import Fetcheur

    reqs: list = []
    while time.time() < depart:
        time.sleep(0.001)
    with Fetcheur(transport=_horodater(reqs), delai_s=1.0) as f:
        for i in range(3):
            f.get(f"https://hote-commun.example/p{ident}-{i}")
    file.put(reqs)


def r3_fetcheur() -> None:
    from pipeline.web import Fetcheur, Page, reinitialiser_delais

    # (a) deux threads, deux Fetcheur, même hôte, dans un processus
    ecarts_intra = []
    for _ in range(2):
        reinitialiser_delais()
        reqs: list = []

        def un(ident: int, reqs=reqs) -> None:
            with Fetcheur(transport=_horodater(reqs), delai_s=1.0) as f:
                for i in range(3):
                    f.get(f"https://hote-commun.example/t{ident}-{i}")

        ths = [threading.Thread(target=un, args=(j,)) for j in range(2)]
        for t in ths:
            t.start()
        for t in ths:
            t.join()
        ts = sorted(t for t, _ in reqs)
        ecarts_intra.append(round(min(b - a for a, b in zip(ts, ts[1:], strict=False)), 3))
    log("R3a_ecart_min_intra_processus_s", ecarts_intra)

    # (b) deux processus
    ctx = mp.get_context("spawn")
    essais = []
    for _ in range(3):
        q = ctx.Queue()
        depart = time.time() + 3.0
        procs = [ctx.Process(target=_processus_fetch, args=(j, depart, q)) for j in range(2)]
        for p in procs:
            p.start()
        tous = q.get() + q.get()
        for p in procs:
            p.join()
        ts = sorted(t for t, _ in tous)
        ecarts = [round(b - a, 3) for a, b in zip(ts, ts[1:], strict=False)]
        essais.append({"ecarts": ecarts, "sous_0_9": sum(1 for e in ecarts if e < 0.9)})
    log("R3b_inter_processus", essais)

    # (c) 403 persistant : requêtes émises par un get()
    reinitialiser_delais()
    vues: list = []

    def h403(req: httpx.Request) -> httpx.Response:
        vues.append(time.monotonic())
        return httpx.Response(403, text="interdit")

    replis: list = []

    def repli(url: str, timeout: float) -> Page:
        replis.append(time.monotonic())
        return Page(url=url, url_finale=url, status=403, content_type="", contenu=b"", texte="")

    with Fetcheur(transport=httpx.MockTransport(h403), delai_s=1.0, repli=repli) as f:
        t0 = time.monotonic()
        f.get("https://bloque.example/a")
        duree = time.monotonic() - t0
    log(
        "R3c_403_persistant",
        {"httpx": len(vues), "repli": len(replis), "duree_totale_s": round(duree, 3)},
    )

    # (d) 503 mis en cache
    reinitialiser_delais()
    n503: list = []

    def h503(req: httpx.Request) -> httpx.Response:
        n503.append(1)
        return httpx.Response(503, text="indisponible")

    with Fetcheur(transport=httpx.MockTransport(h503), delai_s=0.0) as f:
        p1 = f.get("https://panne.example/a")
        p2 = f.get("https://panne.example/a")
    log("R3d_503", {"requetes": len(n503), "statuts": [p1.status, p2.status]})


# ---------------------------------------------------------------------------
# R4 : hôtes partagés entre territoires
# ---------------------------------------------------------------------------


def r4_hotes() -> None:
    from prospection.collecte import cle_fiche  # noqa: F401

    T = yaml.safe_load((BACKEND / "data/prospection/territoires.yaml").read_text())
    ht = collections.defaultdict(set)
    for k, v in T.items():
        for g in v.get("guides") or []:
            ht[urlsplit(g).netloc.lower()].add(k)
    log(
        "R4a_hotes_guides",
        {
            "territoires": len(T),
            "hotes": len(ht),
            "partages": sorted(h for h, s in ht.items() if len(s) > 1),
        },
    )
    F = yaml.safe_load((BACKEND / "data/prospection/file-attente.yaml").read_text())
    hf = collections.defaultdict(set)
    nb = collections.Counter()
    for t in F.values():
        h = urlsplit(t["url"]).netloc.lower()
        hf[h].add(t.get("territoire"))
        nb[h] += 1
    multi = [h for h, s in hf.items() if len(s) > 1]
    log(
        "R4b_hotes_file",
        {
            "taches": len(F),
            "hotes": len(hf),
            "multi": multi,
            "taches_multi": sum(nb[h] for h in multi),
            "ic95": wilson(len(multi), len(hf)),
        },
    )
    # Extension : hôtes des URL triées (toutes candidates) par territoire, checkout principal
    hc = collections.defaultdict(set)
    nlig = collections.Counter()
    for f in glob.glob(str(PRINCIPAL / "data/prospection/*/tri.jsonl")):
        terr = Path(f).parent.name
        for ligne in Path(f).read_text(encoding="utf-8").splitlines():
            if not ligne.strip():
                continue
            try:
                u = json.loads(ligne)["url"]
            except Exception:  # noqa: BLE001
                continue
            h = urlsplit(u).netloc.lower()
            hc[h].add(terr)
            nlig[h] += 1
    multi_c = sorted(
        ((h, sorted(s)) for h, s in hc.items() if len(s) > 1), key=lambda x: -len(x[1])
    )
    log(
        "R4c_hotes_candidats_principal",
        {
            "hotes": len(hc),
            "hotes_multi_territoires": len(multi_c),
            "ic95": wilson(len(multi_c), len(hc)),
            "lignes_sur_hotes_multi": sum(nlig[h] for h, _ in multi_c),
            "lignes": sum(nlig.values()),
            "exemples": multi_c[:8],
        },
    )


# ---------------------------------------------------------------------------
# R5 : bornes de collecte
# ---------------------------------------------------------------------------


def r5_collecte() -> None:
    from pipeline.web import Fetcheur, reinitialiser_delais
    from prospection.collecte import chemin_en_boucle, cle_fiche, collecter
    from prospection.territoires import Territoire

    # (a) générations Moselle : liens relatifs sans « / » initial
    base = "https://www.moselle.fr/jcms/pl_17395/fr/subventions-aux-associations"
    url = base
    gens = []
    for g in range(1, 8):
        rel = f"jcms/pl_{9000 + g}/fr/fiche-{g}"
        from urllib.parse import urljoin

        url = urljoin(url, rel)
        segs = [s for s in urlsplit(url).path.split("/") if s]
        gens.append({"gen": g, "segments": len(segs), "boucle": chemin_en_boucle(url)})
    log("R5a_generations", gens)

    # (b) URL connues touchées par le filtre
    connues: set[str] = set()
    for f in glob.glob(str(BACKEND / "data/prospection/*/candidats.jsonl")):
        for ligne in Path(f).read_text(encoding="utf-8").splitlines():
            if ligne.strip():
                try:  # noqa: SIM105
                    connues.add(json.loads(ligne)["url"])
                except Exception:  # noqa: BLE001
                    pass
    F = yaml.safe_load((BACKEND / "data/prospection/file-attente.yaml").read_text())
    connues |= {t["url"] for t in F.values()}
    for p in glob.glob(str(BACKEND / "data/aides/*.yaml")):
        s = (yaml.safe_load(Path(p).read_text(encoding="utf-8")) or {}).get("source") or {}
        for k in ("url_officielle", "formulaire_url"):
            if s.get(k):
                connues.add(s[k])
    k = sum(1 for u in connues if chemin_en_boucle(u))
    log("R5b_urls_connues_en_boucle", {"k": k, "n": len(connues), "ic95": wilson(k, len(connues))})
    # même mesure élargie aux tri.jsonl du checkout principal (toutes candidates)
    autres: set[str] = set()
    for f in glob.glob(str(PRINCIPAL / "data/prospection/*/tri.jsonl")):
        if Path(f).parent.name == "57":
            continue
        for ligne in Path(f).read_text(encoding="utf-8").splitlines():
            if ligne.strip():
                try:  # noqa: SIM105
                    autres.add(json.loads(ligne)["url"])
                except Exception:  # noqa: BLE001
                    pass
    k2 = sum(1 for u in autres if chemin_en_boucle(u))
    prof = collections.Counter(len([s for s in urlsplit(u).path.split("/") if s]) for u in autres)
    log(
        "R5b2_candidates_principal_hors_57_en_boucle",
        {"k": k2, "n": len(autres), "ic95": wilson(k2, len(autres)), "max_segments": max(prof)},
    )

    # (c) sitemap : fiches ouvertes contre candidates rendues
    reinitialiser_delais()
    ouvertes: list[str] = []
    fiches = [f"https://sm.example/aides/fiche-{i}" for i in range(60)]
    xml = (
        '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{u}</loc></url>" for u in fiches)
        + "</urlset>"
    )

    def h(req: httpx.Request) -> httpx.Response:
        u = str(req.url)
        if u.endswith("sitemap.xml"):
            return httpx.Response(200, content=xml.encode(), headers={"content-type": "text/xml"})
        ouvertes.append(u)
        return httpx.Response(
            200,
            text=f"<html><head><title>{u}</title></head><body><h1>{u}</h1></body></html>",
            headers={"content-type": "text/html"},
        )

    terr = Territoire(
        nom="Test",
        type="departement",
        prefixe_slug="zz",
        statut="pret",
        guides=["https://sm.example/sitemap.xml"],
        strategie={
            "type": "sitemap",
            "url": "https://sm.example/sitemap.xml",
            "max_candidats": 10,
        },
        motif_fiche=r"^https://sm\.example/aides/fiche-\d+$",
    )
    with Fetcheur(transport=httpx.MockTransport(h), delai_s=0.0) as f:
        col = collecter(terr, f, {}, file={})
    log(
        "R5c_sitemap",
        {"fiches_ouvertes": len(ouvertes), "candidates_rendues": len(col.candidats)},
    )
    # (d) plafond appliqué AVANT le dédoublonnage contre la file : 10 premières déjà connues
    from pipeline.etat import Tache

    reinitialiser_delais()
    ouvertes.clear()
    file = {
        f"zz-{i}": Tache(titre="x", url=fiches[i], territoire="zz", statut="ignore")
        for i in range(10)
    }
    with Fetcheur(transport=httpx.MockTransport(h), delai_s=0.0) as f:
        col2 = collecter(terr, f, {}, file=file)
    log(
        "R5d_plafond_avant_dedoublonnage",
        {
            "fiches_ouvertes": len(ouvertes),
            "deja_en_file": len(col2.en_file),
            "nouvelles_rendues": len(col2.candidats),
            "nouvelles_existantes": 50,
        },
    )
    _ = cle_fiche


# ---------------------------------------------------------------------------
# R6 : Moselle
# ---------------------------------------------------------------------------


def r6_moselle() -> None:
    res = {}
    for nom in ("2026-09-18-0052-prospection-57.log", "2026-09-18-0152-prospection-57.log"):
        p = BACKEND / "data/reviews/logs/balayage" / nom
        texte = p.read_text(encoding="utf-8")
        m = re.search(r"\[1/3\] (\d+) candidat", texte)
        m2 = re.search(r"\[3/3\] (\d+) page\(s\) à lire", texte)
        lots = re.findall(r"\[2/3\] lot (\d+)/(\d+)", texte)
        statuts = collections.Counter(
            mm.group(2) for mm in re.finditer(r"\[3/3\]\s+(\d+)/\d+\s+(\S+)", texte)
        )
        res[nom] = {
            "candidates": int(m.group(1)) if m else None,
            "a_lire": int(m2.group(1)) if m2 else None,
            "dernier_lot": lots[-1] if lots else None,
            "lectures": dict(statuts),
            "tentees": sum(statuts.values()),
        }
    log("R6_moselle", res)


# ---------------------------------------------------------------------------
# R7 : tri, file, catalogue
# ---------------------------------------------------------------------------


def r7_tri_file() -> None:
    from prospection.collecte import cle_fiche

    F = yaml.safe_load((BACKEND / "data/prospection/file-attente.yaml").read_text())
    fk = {cle_fiche(t["url"]) for t in F.values() if t.get("url")}
    cat: set[str] = set()
    for p in glob.glob(str(BACKEND / "data/aides/*.yaml")):
        s = (yaml.safe_load(Path(p).read_text(encoding="utf-8")) or {}).get("source") or {}
        for k in ("url_officielle", "formulaire_url"):
            if s.get(k):
                cat.add(cle_fiche(s[k]))

    def compter(fichiers: list[str], exclure: set[str]) -> dict:
        dec = collections.Counter()
        ec: list[str] = []
        par_fichier = {}
        for f in sorted(fichiers):
            terr = Path(f).parent.name
            if terr in exclure:
                continue
            c = collections.Counter()
            for ligne in Path(f).read_text(encoding="utf-8").splitlines():
                if not ligne.strip():
                    continue
                try:
                    r = json.loads(ligne)
                except Exception:  # noqa: BLE001
                    continue
                c[r.get("decision")] += 1
                if r.get("decision") == "ecarter":
                    ec.append(r["url"])
            par_fichier[terr] = dict(c)
            dec += c
        n = sum(dec.values())
        cles = {cle_fiche(u) for u in ec}
        absents = sum(1 for u in cles if u not in fk and u not in cat)
        return {
            "fichiers": len(par_fichier),
            "decisions": dict(dec),
            "n": n,
            "ecarter_ic95": wilson(dec["ecarter"], n),
            "ecarter_distincts": len(cles),
            "absents_file_catalogue": absents,
            "absents_ic95": wilson(absents, len(cles)),
            "par_fichier": par_fichier,
        }

    suivis = glob.glob(str(BACKEND / "data/prospection/*/tri.jsonl"))
    log("R7a_tri_suivis", compter(suivis, set()))
    principal = glob.glob(str(PRINCIPAL / "data/prospection/*/tri.jsonl"))
    log("R7b_tri_principal_hors_57", compter(principal, {"57"}))

    # file : ignore sans motif, motif sur un autre statut, doublons
    ign = [t for t in F.values() if t["statut"] == "ignore"]
    sans = sum(1 for t in ign if not (t.get("motif_ignore") or "").strip())
    autres = collections.Counter(
        t["statut"] for t in F.values() if t["statut"] != "ignore" and t.get("motif_ignore")
    )
    groupes = collections.defaultdict(list)
    for t in F.values():
        groupes[cle_fiche(t["url"])].append(t["statut"])
    combos = collections.Counter(tuple(sorted(v)) for v in groupes.values() if len(v) > 1)
    log(
        "R7c_file",
        {
            "taches": len(F),
            "statuts": dict(collections.Counter(t["statut"] for t in F.values())),
            "ignore_sans_motif": [sans, len(ign), wilson(sans, len(ign))],
            "motif_sur_autre_statut": dict(autres),
            "groupes_doublons_par_statuts": {"+".join(k): v for k, v in combos.items()},
        },
    )


# ---------------------------------------------------------------------------
# R8 : budget, coût inconnu, disjoncteur (orchestrateur réel, ingestion factice)
# ---------------------------------------------------------------------------


def _file_sandbox(chemin: Path, n: int) -> list[str]:
    from pipeline.etat import Tache, ecrire

    slugs = [f"zz-aide-{i:02d}" for i in range(n)]
    ecrire(
        chemin,
        {
            s: Tache(titre=s, url=f"https://x.example/{s}", territoire="zz", statut="valide")
            for s in slugs
        },
    )
    return slugs


def r8_budget() -> None:
    import random

    from ingestion import orchestrateur as orch
    from ingestion.boucle import Limites
    from ingestion.worker import ConfigIngestion, ResultatIngestion
    from pipeline.llm import Compteur

    def fabrique(cout: float | None, duree, transitoire: bool = False):
        def ingerer(slug, tache, config, *, contexte=None, compteur=None):
            local = Compteur()
            time.sleep(duree() if callable(duree) else duree)
            local.ajouter_decision(cout, 0, "factice")
            if compteur is not None:
                compteur.fusionner(local, f"aide:{slug}")
            return ResultatIngestion(
                slug=slug,
                ok=not transitoire,
                arret="termine" if not transitoire else "erreur_modele",
                tours=1,
                cout_usd=cout or 0.0,
                cout_inconnu=cout is None,
                modele="factice",
                modele_verif="factice",
                debut="",
                fin="",
                motif_echec="panne" if transitoire else None,
                echec_transitoire=transitoire,
            )

        return ingerer

    def lancer(par, budget, cout, duree, n=30, transitoire=False, disj=None):
        chemin = BAC / f"file-{par}-{budget}-{cout}-{transitoire}-{time.time_ns()}.yaml"
        slugs = _file_sandbox(chemin, n)
        config = ConfigIngestion(
            limites=Limites(budget_usd=1.5), sortie=BAC / "atelier", journaliser=False
        )
        comp = Compteur()
        import contextlib
        import io

        with contextlib.redirect_stdout(io.StringIO()):
            res = orch.executer(
                slugs,
                config,
                parallele=par,
                budget_total=budget,
                etat_path=chemin,
                compteur=comp,
                ingerer=fabrique(cout, duree, transitoire),
                disjoncteur=disj,
            )
        from pipeline.etat import charger

        statuts = collections.Counter(t.statut for t in charger(chemin).values())
        return len(res), round(comp.cout_usd, 2), dict(statuts)

    budget = {}
    for par in (1, 3, 10):
        budget[f"p{par}_duree_fixe"] = lancer(par, 6.0, 1.45, 0.05)[:2]
        random.seed(par)
        budget[f"p{par}_duree_aleatoire"] = [
            lancer(par, 6.0, 1.45, lambda: random.uniform(0.01, 0.2))[:2] for _ in range(3)
        ]
    log("R8a_budget_6_dollars_aides_1_45", budget)

    lim = Limites()
    p, b, total = 10, 1.5, 60.0
    borne_note = (p - 1) * b
    borne_agent = round((total - b) + p * b * lim.facteur_arret_dur - total, 2)
    log(
        "R8b_bornes",
        {
            "facteur_arret_dur": lim.facteur_arret_dur,
            "borne_note_(p-1)xb": borne_note,
            "borne_agent_seul_(B-b)+p*1.25b-B": borne_agent,
            "processus_ingerer_par_balayage_(1+relances)": 3,
            "plafond_par_balayage_sans_verification_ni_dernier_appel": round(
                3 * (total + borne_agent), 2
            ),
        },
    )
    log("R8c_cout_inconnu_budget_2", lancer(3, 2.0, None, 0.01, n=12))

    class Dormeur:
        def __call__(self, s):
            return None

    disj = orch.Disjoncteur(dormir=Dormeur())
    log(
        "R8d_disjoncteur_p3_20_pannes",
        lancer(3, 1000.0, 0.0, 0.02, n=20, transitoire=True, disj=disj),
    )


# ---------------------------------------------------------------------------
# R9 : Jev, valeurs au format changé
# ---------------------------------------------------------------------------


def r9_jev() -> None:
    from pipeline.decision import ClientDecision, Decision, Reponse
    from prospection import arbitre

    class Faux(ClientDecision):
        def __init__(self, reponses):
            self._r = reponses

        def decider(self, etat, questions):
            return Decision(
                reponses=self._r,
                modele="faux",
                id="",
                jetons_entree=0,
                cout_usd=0.0,
                latence_s=0.0,
                brut={},
            )

    nominal = {
        "deposable": Reponse(type="noul", noul=0.9),
        "destinataire": Reponse(type="choice", choix="proprietaire_gestionnaire"),
        "objet": Reponse(type="choice", choix="bien_ou_lieu"),
        "dispositif": Reponse(type="noul", noul=0.9),
        "categorie_ecart": Reponse(type="choice", choix="objet_hors_lieu"),
    }
    # Dérive : clés présentes, mais la probabilité arrive sous un autre nom
    # (`noul` absent, `probabilities: {yes: …}`) et le choix sous un libellé anglais.
    derive = {
        "deposable": Reponse(type="noul", noul=None, probabilites={"yes": 0.9}),
        "destinataire": Reponse(type="choice", choix="owner_manager"),
        "objet": nominal["objet"],
        "dispositif": Reponse(type="noul", noul=None, probabilites={"yes": 0.9}),
        "categorie_ecart": nominal["categorie_ecart"],
    }
    out = {}
    for nom, rep in (("nominal", nominal), ("derive", derive)):
        a = arbitre.arbitrer(Faux(rep), "https://x", "texte", s=arbitre.Seuils())
        out[nom] = {"deposable": a.deposable, "bande": a.bande, "categorie": a.categorie_ecart}
    log("R9_jev", out)


# ---------------------------------------------------------------------------
# R10 : gabarit de veille
# ---------------------------------------------------------------------------


def r10_gabarit() -> None:
    from veille_aides import anciennete, load_manifest
    from veille_collect import monitored_urls

    from aides_schema import load_aide

    manifest = load_manifest()
    aides = {
        Path(p).stem: load_aide(Path(p))
        for p in sorted(glob.glob(str(BACKEND / "data/aides/*.yaml")))
    }
    ordre = sorted(aides.values(), key=lambda a: (anciennete(a, manifest), a.slug))
    urls_par_aide = {}
    for a in ordre:
        lst = []
        for m in monitored_urls(a):
            pdf = m.url.lower().split("?")[0].endswith(".pdf") or (
                m.baseline_path is not None and str(m.baseline_path).endswith(".pdf")
            )
            diffable = m.baseline_body is not None and not m.is_binary
            lst.append((m.url, urlsplit(m.url).netloc.lower(), diffable and not pdf, diffable))
        urls_par_aide[a.slug] = lst

    def mesure(sel: list) -> dict:
        tous = {}
        for a in sel:
            for u, h, html, diff in urls_par_aide[a.slug]:
                tous[u] = (h, html, diff)
        par_hote = collections.Counter(h for h, _, _ in tous.values())
        k = sum(1 for h, _, _ in tous.values() if par_hote[h] >= 2)
        html = {u: v for u, v in tous.items() if v[1]}
        ph = collections.Counter(h for h, _, _ in html.values())
        kh = sum(1 for h, _, _ in html.values() if ph[h] >= 2)
        return {
            "aides": len(sel),
            "url": len(tous),
            "hotes": len(par_hote),
            "url_hote_2plus": [k, len(tous), wilson(k, len(tous))],
            "url_html_diffables": len(html),
            "url_html_hote_2plus_html": [kh, len(html), wilson(kh, len(html))],
        }

    res = {"parc": mesure(ordre)}
    for lim in (10, 20, 50, 100):
        res[f"limit{lim}"] = mesure(ordre[:lim])
    res["manifeste_entrees"] = len(manifest)
    res["aides_absentes_du_manifeste"] = sum(1 for s in aides if s not in manifest)
    log("R10_gabarit", res)


# ---------------------------------------------------------------------------
# R11 : .yaml.echec, fichiers ignorés suivis, traces de Jev
# ---------------------------------------------------------------------------


def r11_divers() -> None:
    d = BACKEND / "data/aides"
    ech = sorted(d.glob("*.yaml.echec"))
    entete = sum(
        1 for p in ech if "# ÉCHEC D'INGESTION" in p.read_text(encoding="utf-8").splitlines()[0]
    )
    vivants = [p.name for p in ech if (d / p.name[: -len(".echec")]).exists()]
    hist = subprocess.run(
        [
            "git",
            "-C",
            str(RACINE),
            "log",
            "--all",
            "--format=",
            "--name-only",
            "--diff-filter=A",
            "--",
            "backend/data/aides/*.yaml",
        ],
        capture_output=True,
        text=True,
    ).stdout.split()
    hist_set = {Path(x).name for x in hist}
    retirees = [
        p.name
        for p in ech
        if not (d / p.name[: -len(".echec")]).exists() and p.name[: -len(".echec")] in hist_set
    ]
    log(
        "R11a_echec",
        {
            "yaml": len(list(d.glob("*.yaml"))),
            "echec": len(ech),
            "entete_premiere_ligne": entete,
            "sans_entete": len(ech) - entete,
            "avec_yaml_vivant": len(vivants),
            "echec_dont_le_yaml_a_ete_committe_puis_retire": len(retirees),
        },
    )
    ign = subprocess.run(
        ["git", "-C", str(RACINE), "ls-files", "-ci", "--exclude-standard"],
        capture_output=True,
        text=True,
    ).stdout.split()
    log(
        "R11b_ignores_suivis",
        {
            "total_depot": len(ign),
            "sous_backend": sum(1 for x in ign if x.startswith("backend/")),
            "extensions_backend": dict(
                collections.Counter(x.rsplit(".", 1)[-1] for x in ign if x.startswith("backend/"))
            ),
        },
    )
    lignes = 0
    avec = 0
    for base in (BACKEND, PRINCIPAL):
        for f in glob.glob(str(base / "data/prospection/*/lectures.jsonl")):
            for ligne in Path(f).read_text(encoding="utf-8").splitlines():
                if ligne.strip():
                    lignes += 1
                    avec += '"arbitrage"' in ligne
    jev_commit = subprocess.run(
        [
            "git",
            "-C",
            str(RACINE),
            "log",
            "-1",
            "--format=%h %ad",
            "--date=short",
            "-S",
            '"arbitrage": le.arbitrage',
            "--",
            "backend/scripts/prospecter.py",
        ],
        capture_output=True,
        text=True,
    ).stdout.strip()
    journaux = sorted((BACKEND / "data/reviews/logs/balayage").glob("*.log"))
    dates = collections.Counter(p.name[:10] for p in journaux)
    log(
        "R11c_jev_traces",
        {
            "lignes_lectures_worktree_et_principal": lignes,
            "avec_cle_arbitrage": avec,
            "commit_qui_ecrit_la_cle": jev_commit,
            "journaux_balayage_par_date": dict(dates),
            "journaux_mentionnant_jev": sum(
                1 for p in journaux if "jev" in p.read_text(encoding="utf-8").lower()
            ),
        },
    )


def main() -> int:
    SORTIE.mkdir(parents=True, exist_ok=True)
    BAC.mkdir(parents=True, exist_ok=True)
    for fn in (
        r1_verdicts,
        r4_hotes,
        r5_collecte,
        r6_moselle,
        r7_tri_file,
        r11_divers,
        r9_jev,
        # r10 AVANT r8 : l'orchestrateur redirige veille_collect.SOURCES_DIR
        # (ingestion/atelier.py:189-205, global au processus) vers le bac à sable.
        r10_gabarit,
        r8_budget,
        r2_verrou,
        r3_fetcheur,
    ):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            import traceback

            log(f"ERREUR_{fn.__name__}", f"{type(exc).__name__}: {exc}")
            traceback.print_exc()
    (SORTIE / "resultats.json").write_text(
        json.dumps(R, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (SORTIE / "resume.txt").write_text("\n".join(LIGNES) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
