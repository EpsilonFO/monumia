"""Importer l'état de l'ancien pipeline dans le journal (incrément I1b, section 3.4 d'`architecture.md`).

Commande, depuis `backend/` :

    uv run python -m catalogue convertir --journal <dossier> [--verifier]

Lit sans les modifier la file (`data/prospection/file-attente.yaml`) et ses
versions dans git, le manifeste de veille (`data/veille-state.yaml`) et les
siennes, les instantanés de `data/sources/`, les `.yaml` et `.yaml.echec` de
`data/aides/`, et ajoute au journal les événements `auteur: import` qui
manquent. La conversion réelle vers `data/catalogue/journal/` a été faite le
2026-10-11 (I9a) ; relancée, elle importe ce que l'ancienne chaîne a écrit
depuis (une opération qu'elle tient encore au registre). Formats, historique et comptes :
`docs/refonte-pipeline/notes/conversion-formats.md`.

Ce qui est importé, un événement par objet à son état courant :

- `file` : chaque tâche de la file, ses 21 champs tels qu'écrits, datée par le
  commit qui a introduit cet état (graphe des commits : l'état diffère de
  celui de tous les parents), affinée par `ingestion.fin` quand elle tombe
  dans la fenêtre ; son historique de statuts ; la provenance de son
  `motif_ignore`.
- `veille` : chaque entrée du manifeste, datée par son `checked_at`.
- `base` : pour chaque URL suivie d'une aide au catalogue, l'instantané contre
  lequel son YAML a été validé. Le dernier archivé, sauf quand le dernier
  passage de veille a vu un changement sans l'appliquer (escalade, ou
  `maj_llm` sans retouche à la date du passage) : l'instantané antérieur au
  passage, pour que le changement reste dû. Une aide vérifiée après le passage
  (ré-ingérée) garde le dernier.
- `catalogue` : les tâches `ingere` dont l'aide a quitté le catalogue, un écart
  voulu par Félix et non une anomalie (prompt de la mission, section 10).
- `contradiction` : une aide à la fois en `.yaml` et en `.yaml.echec`, une
  entrée de veille sur une aide hors catalogue, une tâche `ingere` qui porte un
  motif d'écart.

Relancé, `convertir` compare l'état courant à ce que le journal reprojette et
n'ajoute que ce qui diffère ; une contradiction déjà consignée ne se répète
pas. La reprojection prend, pour chaque objet, l'événement du run le plus
récent : la file et le manifeste se refont alors octet pour octet par leurs
propres écrivains (`--verifier`).

Les fiches de prospection et les JSONL de `data/prospection/<territoire>/`
portent la mémoire du tri sur titre (6 622 URL écartées qui ne sont que là) :
elle s'importera avec le portage de la prospection, sous la forme dont le tri
neuf aura besoin. Les fichiers restent dans git d'ici là.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import veille_aides
import yaml
from pipeline import etat

from catalogue.journal import Evenement, Journal, cle
from catalogue.veille_collect import cle_url, est_http, url_d_origine
from catalogue.veille_text import parse_front_matter

FILE = Path("backend/data/prospection/file-attente.yaml")
MANIFESTE = Path("backend/data/veille-state.yaml")
AIDES = Path("backend/data/aides")
SOURCES = Path("backend/data/sources")
RACINE = Path(__file__).resolve().parents[2]

STATUTS_INGESTION = ("ingere", "echec")


# ------------------------------------------------------------------ versions


@dataclass(frozen=True)
class Version:
    """Un état d'un fichier : un commit, ou le working tree s'il diffère de HEAD."""

    sha: str
    date: dt.datetime
    parents: tuple[str, ...]
    contenu: bytes


def _git(depot: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=depot, capture_output=True, text=True, check=True
    ).stdout


def _contenu(depot: Path, sha: str, chemin: Path) -> bytes | None:
    r = subprocess.run(
        ["git", "show", f"{sha}:{chemin.as_posix()}"], cwd=depot, capture_output=True
    )
    return r.stdout if r.returncode == 0 else None


def _date(texte: str) -> dt.datetime:
    return dt.datetime.fromisoformat(texte.strip()).astimezone(dt.UTC)


def versions(depot: Path, chemin: Path) -> list[Version]:
    """Les versions committées du fichier, parents avant enfants, puis le working tree s'il diffère."""
    shas = _git(depot, "log", "--topo-order", "--reverse", "--format=%H", "--", str(chemin)).split()
    liste: list[Version] = []
    for sha in shas:
        parents = tuple(_git(depot, "rev-list", "--parents", "-n1", sha).split()[1:])
        contenu = _contenu(depot, sha, chemin) or b""
        liste.append(
            Version(sha, _date(_git(depot, "log", "-1", "--format=%cI", sha)), parents, contenu)
        )
    sur_disque = depot / chemin
    if sur_disque.exists():
        tete = _contenu(depot, "HEAD", chemin)
        octets = sur_disque.read_bytes()
        if octets != tete:
            mtime = dt.datetime.fromtimestamp(sur_disque.stat().st_mtime, dt.UTC)
            liste.append(Version("worktree", mtime, ("HEAD",), octets))
    return liste


_LUS: dict[bytes, dict[str, Any]] = {}


def lire_yaml(contenu: bytes) -> dict[str, Any]:
    """Un mapping YAML (file ou manifeste), lu par le chargeur C comme le font leurs écrivains.

    Mémorisé par empreinte du contenu : les parents d'un commit portent souvent
    le même fichier qu'une version déjà lue, et la file pèse 3,3 Mo.
    """
    if not contenu:
        return {}
    empreinte_contenu = hashlib.sha256(contenu).digest()
    if empreinte_contenu in _LUS:
        return _LUS[empreinte_contenu]
    brut = yaml.load(contenu.decode("utf-8"), Loader=yaml.CSafeLoader) or {}
    # Le journal est en JSON : une valeur qui n'y survit pas casserait la
    # reprojection à l'octet. La file et le manifeste n'en ont aucune ; on le
    # vérifie plutôt que de le supposer.
    if json.loads(json.dumps(brut, ensure_ascii=False)) != brut:
        raise ValueError("valeur non JSON (date, ensemble...) : la reprojection ne tiendrait pas")
    _LUS[empreinte_contenu] = brut
    return brut


@dataclass(frozen=True)
class Changement:
    sha: str
    date: dt.datetime
    borne_basse: dt.datetime | None
    etat: dict[str, Any] | None


def changements(depot: Path, chemin: Path, liste: list[Version]) -> dict[str, list[Changement]]:
    """Par clé, les versions où son état diffère de celui qu'elle a chez chacun des parents.

    Comparer chaque version à la précédente dans le temps serait faux : la file
    a évolué sur deux branches à la fois (`88d46d5d` et `fdde0102`). Une fusion
    qui reprend l'état d'un de ses parents n'introduit rien.
    """
    par_sha: dict[str, tuple[dict[str, Any], dt.datetime | None]] = {}

    def etat_de(sha: str) -> tuple[dict[str, Any], dt.datetime | None]:
        if sha not in par_sha:
            contenu = _contenu(depot, sha, chemin)
            date = (
                _date(_git(depot, "log", "-1", "--format=%cI", sha))
                if contenu is not None
                else None
            )
            par_sha[sha] = (lire_yaml(contenu or b""), date)
        return par_sha[sha]

    resultat: dict[str, list[Changement]] = defaultdict(list)
    for v in liste:
        courant = lire_yaml(v.contenu)
        par_sha[v.sha] = (courant, v.date)
        parents = [etat_de(p) for p in v.parents] or [({}, None)]
        dates = [d for _, d in parents if d is not None]
        bas = max(dates) if dates else None
        cles = set(courant).union(*(set(e) for e, _ in parents))
        for k in sorted(cles):
            e = courant.get(k)
            if all(p.get(k) != e for p, _ in parents):
                resultat[k].append(Changement(v.sha, v.date, bas, e))
    return resultat


def _iso(d: dt.datetime) -> str:
    return d.astimezone(dt.UTC).isoformat(timespec="seconds")


def _introduction(histoire: list[Changement], etat_courant: dict[str, Any]) -> Changement | None:
    """Le dernier changement qui a produit l'état courant."""
    for c in reversed(histoire):
        if c.etat == etat_courant:
            return c
    return None


# ---------------------------------------------------------------- reprojection


def etats_importes(
    evenements: Iterable[Evenement], decision: str, cle_de: Callable[[Evenement], Any] | None = None
) -> dict[Any, Evenement]:
    """Pour chaque objet, l'événement d'import du run le plus récent (à run égal, le dernier lu)."""
    retenus: dict[Any, Evenement] = {}
    for e in evenements:
        if e.type != "import" or e.decision != decision:
            continue
        k = cle_de(e) if cle_de else e.objet
        anterieur = retenus.get(k)
        if anterieur is None or (e.run or "") >= (anterieur.run or ""):
            retenus[k] = e
    return retenus


def _presents(retenus: dict[Any, Evenement]) -> dict[str, dict[str, Any]]:
    return {
        e.objet.removeprefix("a:"): e.donnees["etat"]
        for e in retenus.values()
        if e.donnees.get("etat") is not None
    }


def reprojeter_file(evenements: Iterable[Evenement]) -> bytes:
    taches = _presents(etats_importes(evenements, "file"))
    return etat._en_yaml({s: etat.Tache.model_validate(t) for s, t in taches.items()}).encode()


def reprojeter_manifeste(evenements: Iterable[Evenement]) -> bytes:
    entrees = _presents(etats_importes(evenements, "veille"))
    with tempfile.TemporaryDirectory() as dossier:
        chemin = Path(dossier) / "veille-state.yaml"
        veille_aides.write_manifest(entrees, chemin)
        return chemin.read_bytes()


# ------------------------------------------------------------- file, manifeste


def provenance_motif(tache: dict[str, Any]) -> str | None:
    """Qui a écrit le `motif_ignore` : chaque forme de motif a un seul écrivain (note, section 7)."""
    motif = tache.get("motif_ignore")
    if not motif:
        return "sans_trace" if tache.get("statut") == "ignore" else None
    if motif.startswith("doublon d'URL de"):
        return "doublon_regle"
    if motif.startswith(
        ("test du destinataire", "requalification du 2026-10-04", "hors périmètre à l'ingestion")
    ):
        return "requalification_llm"
    if motif.startswith("hors périmètre"):
        return "lecture_llm"
    if motif.startswith(("tri humain du", "pas un dispositif demandable (arbitrage humain")):
        return "lot_approuve"
    return "autre"


def _date_tache(tache: dict[str, Any], c: Changement) -> dt.datetime:
    """La date du commit, ou `ingestion.fin` quand elle tombe dans la fenêtre du changement."""
    fin = (tache.get("ingestion") or {}).get("fin")
    if tache.get("statut") in STATUTS_INGESTION and fin:
        try:
            d = _date(fin)
        except ValueError:
            return c.date
        if (c.borne_basse is None or c.borne_basse <= d) and d <= c.date:
            return d
    return c.date


def _date_entree(entree: dict[str, Any], c: Changement) -> dt.datetime:
    """La date du passage de veille (`checked_at`, ou `tente_le` d'une erreur HTTP) ; le commit sinon."""
    jour = entree.get("checked_at") or entree.get("tente_le")
    if jour:
        try:
            d = dt.datetime.fromisoformat(str(jour)[:10]).replace(tzinfo=dt.UTC)
        except ValueError:
            return c.date
        if d <= c.date:
            return d
    return c.date


def _evenements_etat(
    decision: str,
    courant: dict[str, Any],
    histoire: dict[str, list[Changement]],
    deja: dict[Any, Evenement],
    run: str,
    dater: Callable[[dict[str, Any], Changement], dt.datetime],
    statut: str,
    enrichir: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> list[Evenement]:
    """Un événement par clé dont l'état courant diffère de celui que reprojette le journal."""
    evenements: list[Evenement] = []
    for k in sorted(courant):
        e = courant[k]
        connu = deja.get(f"a:{k}")
        if connu is not None and connu.donnees.get("etat") == e:
            continue
        h = histoire.get(k, [])
        intro = _introduction(h, e)
        t = dater(e, intro) if intro else None
        statuts = [
            [c.sha[:12], _iso(c.date), (c.etat or {}).get(statut)]
            for i, c in enumerate(h)
            if i == 0 or (c.etat or {}).get(statut) != (h[i - 1].etat or {}).get(statut)
        ]
        donnees: dict[str, Any] = {
            "etat": e,
            "commit": intro.sha[:12] if intro else None,
            "fenetre": [
                _iso(intro.borne_basse) if intro and intro.borne_basse else None,
                _iso(intro.date),
            ]
            if intro
            else None,
            "historique": statuts,
        }
        if enrichir:
            donnees.update(enrichir(e))
        evenements.append(
            Evenement(
                "import",
                f"a:{k}",
                decision=decision,
                t=_iso(t) if t else "",
                run=run,
                auteur="import",
                cle=cle("import", decision, k, e),
                issue=e.get(statut),
                donnees=donnees,
            )
        )
    for objet, connu in sorted(deja.items()):
        k = str(objet).removeprefix("a:")
        if k not in courant and connu.donnees.get("etat") is not None:
            evenements.append(
                Evenement(
                    "import",
                    f"a:{k}",
                    decision=decision,
                    run=run,
                    auteur="import",
                    cle=cle("import", decision, k, None),
                    issue="retiree",
                    donnees={"etat": None},
                )
            )
    return evenements


# --------------------------------------------------------------------- bases


@dataclass(frozen=True)
class Instantane:
    nom: str
    url: str
    cle: str
    label: str | None
    origine: str
    sha256: str | None


def _label(stem: str) -> str | None:
    """« 2026-08-05-reglement » → « reglement » ; « 2026-08-05 » → None (comme la veille)."""
    return stem[len("0000-00-00") :].lstrip("-") or None


def instantanes(dossier: Path) -> list[Instantane]:
    """Les instantanés d'une aide qui portent leur URL, triés par nom (donc par date), comme la veille."""
    if not dossier.is_dir():
        return []
    liste: list[Instantane] = []
    for p in sorted(dossier.iterdir()):
        if p.suffix == ".md":
            meta, _ = parse_front_matter(p.read_text(encoding="utf-8"))
            nom, stem = p.name, p.stem
        elif p.name.endswith(".meta.yaml"):
            meta = yaml.load(p.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader) or {}
            nom = p.name.removesuffix(".meta.yaml")
            stem = Path(nom).stem
        else:
            continue
        url = meta.get("url")
        if not est_http(url):
            continue
        url, origine = url_d_origine(str(url))
        liste.append(Instantane(nom, url, cle_url(url), _label(stem), origine, meta.get("sha256")))
    return sorted(liste, key=lambda i: i.nom)


def _verifiee_le(depot: Path, slug: str) -> str | None:
    chemin = depot / AIDES / f"{slug}.yaml"
    if not chemin.exists():
        return None
    brut = yaml.load(chemin.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader) or {}
    v = (brut.get("source") or {}).get("verified_at")
    return str(v)[:10] if v else None


def regle_de_base(entree: dict[str, Any], verifiee_le: str | None) -> tuple[bool, str]:
    """Le changement vu au dernier passage reste-t-il dû ? Et pourquoi."""
    passage = str(entree.get("checked_at") or "")[:10] or None
    statut = entree.get("status")
    retouche = (entree.get("maj") or {}).get("date")
    if statut == "escalade_ingestion":
        rouvrir, motif = True, "escalade"
    elif statut == "maj_llm" and (passage is None or str(retouche)[:10] != passage):
        rouvrir, motif = True, "inchange"
    elif statut == "maj_llm":
        return False, "retouche_appliquee"
    else:
        return False, str(statut)
    if passage and verifiee_le and verifiee_le > passage:
        return False, f"{motif}_reverifiee"
    return rouvrir, motif


def evenements_bases(
    depot: Path, manifeste: dict[str, Any], aides: set[str], deja: dict[Any, Evenement], run: str
) -> list[Evenement]:
    evenements: list[Evenement] = []
    for slug in sorted(manifeste):
        if slug not in aides:
            continue  # contradiction : la veille vise une aide hors catalogue
        entree = manifeste[slug]
        passage = str(entree.get("checked_at") or "")[:10] or None
        rouvrir, motif = regle_de_base(entree, _verifiee_le(depot, slug))
        index = instantanes(depot / SOURCES / slug)
        urls = entree.get("urls") or []
        cles_suivies = {cle_url(u["url"]) for u in urls}
        for u in urls:
            k = cle_url(u["url"])
            label = u.get("label")
            # Par l'URL, et par le label pour une page redirigée que la veille a
            # rattachée à l'instantané d'une autre adresse (`relier_redirections`) ;
            # jamais l'instantané d'une autre URL suivie de la même aide.
            candidats = [
                i
                for i in index
                if i.cle == k or (label and i.label == label and i.cle not in cles_suivies)
            ]
            if not candidats:
                continue
            hors_passage = [i for i in candidats if not (passage and i.nom.startswith(passage))]
            base = (hors_passage[-1] if hors_passage else None) if rouvrir else candidats[-1]
            donnees: dict[str, Any] = {
                "url": u["url"],
                "cle_url": k,
                "fichier": base.nom if base else None,
                "sha256": base.sha256 if base else None,
                "origine": base.origine if base else None,
                "dernier_archive": candidats[-1].nom,
                "du": rouvrir
                and (base is None or base.nom != candidats[-1].nom or motif == "escalade"),
                "regle": "avant_passage" if rouvrir else "dernier",
                "motif": motif,
                "passage": passage,
            }
            connu = deja.get((f"a:{slug}", k))
            if connu is not None and connu.donnees == donnees:
                continue
            evenements.append(
                Evenement(
                    "import",
                    f"a:{slug}",
                    decision="base",
                    t=f"{passage}T00:00:00+00:00" if passage else "",
                    run=run,
                    auteur="import",
                    cle=cle("import", "base", slug, k, donnees["fichier"]),
                    donnees=donnees,
                )
            )
    return evenements


def _cle_base(e: Evenement) -> tuple[str, str]:
    return (e.objet, e.donnees.get("cle_url", ""))


# ----------------------------------------------------- écarts et contradictions


def evenements_catalogue(
    depot: Path,
    file: dict[str, Any],
    aides: set[str],
    rebuts: set[str],
    deja: dict[Any, Evenement],
    run: str,
) -> list[Evenement]:
    """Les tâches `ingere` dont l'aide a quitté le catalogue : un écart voulu par Félix."""
    evenements: list[Evenement] = []
    for slug in sorted(file):
        tache = file[slug]
        if tache.get("statut") != "ingere" or slug in aides:
            continue
        donnees = {
            "fichier": f"{slug}.yaml.echec" if slug in rebuts else None,
            "decideur_presume": "felix",
        }
        connu = deja.get(f"a:{slug}")
        if connu is not None and connu.donnees == donnees:
            continue
        sortie = _git(
            depot,
            "log",
            "-1",
            "--diff-filter=DR",
            "--format=%cI",
            "--",
            str(AIDES / f"{slug}.yaml"),
        ).strip()
        fin = (tache.get("ingestion") or {}).get("fin")
        t = _iso(_date(sortie)) if sortie else (_iso(_date(fin)) if fin else "")
        evenements.append(
            Evenement(
                "import",
                f"a:{slug}",
                decision="catalogue",
                t=t,
                run=run,
                auteur="import",
                cle=cle("import", "catalogue", slug, donnees),
                issue="ecartee_apres_ingestion",
                donnees=donnees,
            )
        )
    return evenements


def evenements_contradictions(
    file: dict[str, Any],
    manifeste: dict[str, Any],
    aides: set[str],
    rebuts: set[str],
    connues: set[str],
    run: str,
) -> list[Evenement]:
    trouvees: list[tuple[str, str, dict[str, Any]]] = []
    for slug in sorted(aides & rebuts):
        trouvees.append(
            (slug, "yaml_et_echec", {"detail": "l'aide est en .yaml et en .yaml.echec"})
        )
    for slug in sorted(set(manifeste) - aides):
        trouvees.append(
            (
                slug,
                "veille_hors_catalogue",
                {"statut_veille": manifeste[slug].get("status"), "en_echec": slug in rebuts},
            )
        )
    for slug in sorted(file):
        t = file[slug]
        if t.get("statut") == "ingere" and t.get("motif_ignore") and slug in aides:
            trouvees.append((slug, "ingeree_malgre_ecart", {"motif_ignore": t["motif_ignore"]}))
    evenements: list[Evenement] = []
    for slug, nature, donnees in trouvees:
        k = cle("contradiction", nature, slug, donnees)
        if k in connues:
            continue
        evenements.append(
            Evenement(
                "contradiction",
                f"a:{slug}",
                decision=nature,
                run=run,
                auteur="import",
                cle=k,
                donnees=donnees,
            )
        )
    return evenements


# ------------------------------------------------------------------- commande


def _slugs(depot: Path, suffixe: str) -> set[str]:
    return {p.name.removesuffix(suffixe) for p in (depot / AIDES).glob(f"*{suffixe}")}


def convertir(depot: Path, journal: Journal, run: str | None = None) -> list[Evenement]:
    """Ajoute au journal ce qui manque de l'état ancien ; rend les événements ajoutés."""
    run = run or "convertir-" + dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    existants = list(journal.lire())

    v_file = versions(depot, FILE)
    v_manifeste = versions(depot, MANIFESTE)
    file = lire_yaml((depot / FILE).read_bytes()) if (depot / FILE).exists() else {}
    manifeste = lire_yaml((depot / MANIFESTE).read_bytes()) if (depot / MANIFESTE).exists() else {}
    aides, rebuts = _slugs(depot, ".yaml"), _slugs(depot, ".yaml.echec")

    nouveaux: list[Evenement] = []
    nouveaux += _evenements_etat(
        "file",
        file,
        changements(depot, FILE, v_file),
        etats_importes(existants, "file"),
        run,
        _date_tache,
        "statut",
        lambda t: {"provenance_motif": provenance_motif(t)},
    )
    nouveaux += _evenements_etat(
        "veille",
        manifeste,
        changements(depot, MANIFESTE, v_manifeste),
        etats_importes(existants, "veille"),
        run,
        _date_entree,
        "status",
    )
    nouveaux += evenements_bases(
        depot, manifeste, aides, etats_importes(existants, "base", _cle_base), run
    )
    nouveaux += evenements_catalogue(
        depot, file, aides, rebuts, etats_importes(existants, "catalogue"), run
    )
    connues = {e.cle for e in existants if e.type == "contradiction" and e.cle}
    nouveaux += evenements_contradictions(file, manifeste, aides, rebuts, connues, run)
    return journal.ajouter_lot(nouveaux)


def verifier(depot: Path, journal: Journal) -> list[str]:
    """Les écarts entre ce que le journal reprojette et les fichiers en service ; vide si aucun."""
    evenements = list(journal.lire())
    ecarts: list[str] = []
    for nom, chemin, reprojeter in (
        ("file", FILE, reprojeter_file),
        ("manifeste", MANIFESTE, reprojeter_manifeste),
    ):
        attendu = (depot / chemin).read_bytes() if (depot / chemin).exists() else b""
        obtenu = reprojeter(evenements) if attendu else b""
        if obtenu != attendu:
            lignes_a, lignes_o = attendu.decode().splitlines(), obtenu.decode().splitlines()
            n = next(
                (i for i, (a, o) in enumerate(zip(lignes_a, lignes_o, strict=False)) if a != o),
                min(len(lignes_a), len(lignes_o)),
            )
            ecarts.append(f"{nom} : premier écart ligne {n + 1}")
    return ecarts


def bilan(evenements: list[Evenement]) -> dict[str, Any]:
    """Les comptes que le rapport de conversion cite."""
    par_decision = Counter((e.type, e.decision) for e in evenements)
    bases = [e for e in etats_importes(evenements, "base", _cle_base).values()]
    file = _presents(etats_importes(evenements, "file"))
    return {
        "evenements": {f"{t}/{d}": n for (t, d), n in sorted(par_decision.items(), key=str)},
        "taches_par_statut": dict(Counter(t.get("statut") for t in file.values())),
        "provenance_motifs": dict(
            Counter(provenance_motif(t) for t in file.values() if provenance_motif(t))
        ),
        "bases_par_motif": dict(Counter(e.donnees["motif"] for e in bases)),
        "bases_dues": dict(Counter(e.donnees["motif"] for e in bases if e.donnees["du"])),
        "aides_avec_base_due": len({e.objet for e in bases if e.donnees["du"]}),
        "dues_sans_base": sum(1 for e in bases if e.donnees["du"] and e.donnees["fichier"] is None),
    }


def commande(dossier: Path, verifier_apres: bool = False, depot: Path = RACINE) -> int:
    journal = Journal(dossier)
    ajoutes = convertir(depot, journal)
    print(f"{len(ajoutes)} événements ajoutés à {dossier}")
    for k, n in sorted(Counter(f"{e.type}/{e.decision}" for e in ajoutes).items()):
        print(f"  {k} : {n}")
    if not verifier_apres:
        return 0
    ecarts = verifier(depot, journal)
    print(json.dumps(bilan(list(journal.lire())), ensure_ascii=False, indent=1))
    for e in ecarts:
        print(f"ÉCART {e}", file=sys.stderr)
    print("reprojection : " + ("identique à l'octet" if not ecarts else "différente"))
    return 1 if ecarts else 0
