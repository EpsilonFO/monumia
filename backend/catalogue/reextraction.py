"""Ré-extraire une aide en service, par l'agent sous contrat (incrément I4, sections 5 et 6.3 d'`architecture.md`).

Une escalade de veille (condition apparue ou disparue, refonte, changement
majeur) se traite par une ré-extraction : l'agent d'ingestion relit les sources
fraîches de l'aide et propose un YAML complet. Ce module ne lui laisse écrire
que ce que le contrat de données permet, au plus petit diff :

1. **Préparer** un dossier de sortie neuf : copie du YAML en service et de ses
   instantanés ; l'agent ne voit jamais `data/aides/` ni `data/sources/`.
2. **Lancer** `catalogue.agent` dans son propre groupe de processus, sous un
   délai ; le groupe est tué au délai et dans tous les cas en sortie.
3. **Classer** l'issue, lue dans `resultat.json` : panne (classe), refus par
   contrôle (motif), hors périmètre (case, jamais un retrait), acceptée.
4. **Retour** (règles de contenu) : les conditions se rapprochent par id, puis
   par citation, et aucun id n'est réattribué.
   - Une condition dont la citation figure toujours dans les pages fraîches
     reste à l'octet ; une condition endettée (citation déjà absente des
     instantanés de référence, ou sans citation) aussi.
   - Seules les conditions dont le passage cité a changé prennent le texte et
     la citation de l'agent ; sur une condition `user_fact`, ou à texte
     surchargeable, c'est une case (surcouche admin non lue).
   - Une divergence de `kind`, `effect`, `fact`, `field` ou `predicate` sur une
     condition gardée est une case, jamais une écriture.
   - Un retrait (`C-retrait-condition`) : seulement si la citation, retrouvée
     dans la référence, a disparu d'une page fraîche re-téléchargée, et que
     l'effet est `info` ; sinon une case.
   - Les conditions nouvelles de l'agent s'ajoutent, et leurs faits neufs
     deviennent des cases `H-fait` (décision 5).
   - Calendrier, financement, cumul : les valeurs de l'agent, si chaque date et
     chaque nombre figure tel quel dans les pages fraîches ; sinon une case.
     Un changement de ces sections ouvre une case « fiche à relire ».
   - Pièces, filtres, `applies_if`, familles : une divergence est une case.
     Le reste du YAML ne bouge pas.
5. **Accepter par écart** : seules les erreurs de lint que la ré-extraction
   introduit refusent l'écriture (clé stable, sans les valeurs du message) ;
   la dette connue ne fait ni échouer ni retirer.
6. **Écrire** par l'éditeur par plages, matérialiser les instantanés frais,
   ajouter les faits neufs en fin de `facts_pending.yaml`, et faire avancer la
   référence de veille. Une tentative refusée va dans
   `data/catalogue/rebuts/<slug>/`, et la version en service ne bouge pas.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aides_schema import AIDES_DIR, DATA_DIR, FACTS_PENDING_FILE, charger_yaml
from catalogue import controles
from catalogue.cases import Case
from catalogue.editeur import EditionImpossible, editer
from catalogue.registre import BACKEND
from catalogue.veille_collect import SOURCES_DIR, load_baselines
from catalogue.veille_text import find_quote_in_any

REBUTS = DATA_DIR / "catalogue" / "rebuts"
SORTIES = BACKEND / ".cache" / "catalogue" / "reextractions"
TYPAGE = ("kind", "effect", "fact", "field", "predicate")
SECTIONS = ("calendrier", "financement", "cumul")
SURVEILLES = ("documents_requis", "hard_filters", "applies_if", "familles")
OPTIONS_DIVERGENCE = {
    "garder": "garder la version en service",
    "voir": "vu, je corrige à la main",
}


# ------------------------------------------------------------------ lancement


@dataclass
class Lancement:
    resultat: dict[str, Any] | None
    panne: str | None
    sortie: Path
    duree_s: float


def preparer(slug: str, sortie: Path, aides: Path = AIDES_DIR, sources: Path = SOURCES_DIR) -> None:
    (sortie / "aides").mkdir(parents=True)
    (sortie / "en-service").mkdir()
    shutil.copy2(aides / f"{slug}.yaml", sortie / "aides" / f"{slug}.yaml")
    shutil.copy2(aides / f"{slug}.yaml", sortie / "en-service" / f"{slug}.yaml")
    if (sources / slug).is_dir():
        shutil.copytree(sources / slug, sortie / "sources" / slug)


def lancer(slug: str, sortie: Path, plafond: float, delai_s: float) -> Lancement:
    """L'agent dans son groupe de processus ; le groupe est tué au délai et en sortie."""
    debut = dt.datetime.now()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "catalogue.agent",
            "--slug",
            slug,
            "--sortie",
            str(sortie),
            "--plafond",
            str(plafond),
        ],
        cwd=BACKEND,
        start_new_session=True,
        stdout=(sortie / "agent.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    panne = None
    try:
        proc.wait(timeout=delai_s)
    except subprocess.TimeoutExpired:
        panne = "delai"
    finally:
        if proc.poll() is None:
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(proc.pid, sig)
                    proc.wait(timeout=10)
                    break
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    continue
    chemin = sortie / "resultat.json"
    resultat = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else None
    if resultat is None and panne is None:
        panne = "bug"
    return Lancement(resultat, panne, sortie, (dt.datetime.now() - debut).total_seconds())


def classer(r: dict[str, Any]) -> tuple[str, str, str | None]:
    """(issue, raison, classe de panne) d'une ré-extraction ou d'une ingestion terminée.

    Un refus ne vient que des contrôles du contenu, sur un agent arrivé au bout
    (`arret: termine`). Tout autre arrêt (fournisseur en panne, budget, tours
    épuisés, boucle) est une panne rejouable : le drapeau `echec_transitoire`
    de l'agent ne suffit pas, il n'est posé que si aucun YAML n'existe, ce qui
    n'arrive jamais en ré-extraction.
    """
    motif = str(r.get("motif_echec") or "")
    if r.get("panne_contrat"):
        return "panne", f"contrat : {r['panne_contrat']}", r["panne_contrat"]
    if r.get("verification_indisponible"):
        return (
            "panne",
            f"vérificateur indisponible : {r['verification_indisponible']}",
            "verification",
        )
    if r.get("echec_fatal"):
        return "panne", motif or "erreur fatale", "cle"
    if r.get("hors_perimetre"):
        cat, raison = r["hors_perimetre"]
        return "hors_perimetre", f"{cat} : {raison}", None
    arret = r.get("arret") or "termine"
    if not r.get("ok") and arret != "termine":
        if arret == "erreur_modele":
            bas = motif.lower()
            classe = "credits" if ("402" in bas or "credit" in bas) else "fournisseur"
        else:
            classe = f"agent_{arret}"
        return "panne", motif or f"agent arrêté sur « {arret} »", classe
    if r.get("echec_transitoire"):
        return "panne", motif or "panne du fournisseur", "fournisseur"
    if not r.get("ok"):
        return "refusee", motif or "refusée par les contrôles", None
    return "acceptee", "", None


# ------------------------------------------------------------------ retour


def documents(dossier: Path) -> tuple[list[tuple[str, str, str]], dict[str, str]]:
    """Les documents d'un dossier d'instantanés et l'URL de chacun, lus comme la veille et le lint les lisent."""
    from catalogue import veille_collect

    ancien = veille_collect.SOURCES_DIR
    try:
        veille_collect.SOURCES_DIR = dossier.parent
        docs, _, provenance = load_baselines(dossier.name)
    finally:
        veille_collect.SOURCES_DIR = ancien
    return docs, provenance


def _ou(quote: str | None, docs: list[tuple[str, str, str]]) -> str | None:
    """Le document où la citation se retrouve, ou `None`."""
    if not quote or not docs:
        return None
    nom, _ = find_quote_in_any(quote, docs)  # type: ignore[arg-type]
    return nom


SEUIL_PROCHE = 0.4


def recouvrement(a: Any, b: Any) -> float:
    """Indice de Jaccard des mots de deux citations."""
    ma = set(re.findall(r"\w+", str(a or "").lower()))
    mb = set(re.findall(r"\w+", str(b or "").lower()))
    return len(ma & mb) / len(ma | mb) if ma | mb else 0.0


def _norm(x: Any) -> Any:
    return json.loads(json.dumps(x, default=str))


@dataclass
class Retour:
    cible: dict[str, Any]
    cases: list[Case] = field(default_factory=list)
    changements: list[str] = field(default_factory=list)
    faits_neufs: list[str] = field(default_factory=list)


def _effet(c: dict[str, Any]) -> str:
    return c.get("effect") or ("info" if c.get("kind") in ("info", "discretionary") else "gate")


def retour(
    slug: str,
    ancien: dict[str, Any],
    agent: dict[str, Any],
    base: list[tuple[str, str, str]],
    frais: list[tuple[str, str, str]],
    faits_connus: set[str],
    etat: str,
    urls: dict[str, str] | None = None,
) -> Retour:
    """La cible que l'aide en service peut devenir, et les cases de ce qui ne s'écrit pas.

    `base` : les instantanés d'avant la ré-extraction ; `frais` : ceux que
    l'agent vient d'archiver ; `urls` : nom de fichier -> URL archivée.
    """
    from catalogue.veille_collect import cle_url

    objet = f"a:{slug}"
    urls = urls or {}
    r = Retour(cible=copy.deepcopy(ancien))

    def case(
        sorte: str, titre: str, lignes: list[str], options: dict[str, str] = OPTIONS_DIVERGENCE
    ) -> None:
        r.cases.append(Case(sorte, objet, titre, f"{etat}:{len(r.cases)}", options, tuple(lignes)))

    def frais_de(nom_base: str | None) -> list[tuple[str, str, str]]:
        """Les pages fraîches qui re-téléchargent le document `nom_base`."""
        url = urls.get(nom_base or "")
        if not url:
            return []
        return [d for d in frais if cle_url(urls.get(d[0], "")) == cle_url(url)]

    anciennes: list[dict[str, Any]] = list(ancien.get("conditions") or [])
    proposees: list[dict[str, Any]] = list(agent.get("conditions") or [])
    par_id = {c.get("id"): c for c in proposees}
    utilisees: set[int] = set()

    def rapprocher(c: dict[str, Any]) -> dict[str, Any] | None:
        a = par_id.get(c.get("id"))
        if a is not None and id(a) not in utilisees:
            utilisees.add(id(a))
            return a
        q = " ".join(str(c.get("quote") or "").split())
        for a in proposees:
            if q and id(a) not in utilisees and " ".join(str(a.get("quote") or "").split()) == q:
                utilisees.add(id(a))
                return a
        return None

    sortie: list[dict[str, Any]] = []
    for c in anciennes:
        a = rapprocher(c)
        q = c.get("quote")
        doc_base = _ou(q, base)
        if a is None:
            # Retrait seulement si le document qui portait la citation a été
            # re-téléchargé et ne la porte plus (C-retrait-condition).
            ses_frais = frais_de(doc_base) if doc_base else []
            if ses_frais and _ou(q, ses_frais) is None:
                if _effet(c) == "info":
                    r.changements.append(
                        f"condition retirée : {c.get('id')} (citation disparue de sa page)"
                    )
                    continue
                case(
                    "reextraction-retrait",
                    "retrait de condition proposé",
                    [
                        f"`{c.get('id')}` ({c.get('kind')}, {_effet(c)}) : sa citation a disparu de sa page fraîche.",
                        f"> {q}",
                    ],
                    {"retirer": "retirer la condition", "garder": "la garder"},
                )
            sortie.append(c)
            continue
        divergences = [k for k in TYPAGE if _norm(a.get(k)) != _norm(c.get(k))]
        if divergences:
            case(
                "reextraction-typage",
                "typage divergent",
                [
                    f"`{c.get('id')}` : l'agent propose {', '.join(f'{k} = {a.get(k)!r}' for k in divergences)} ; "
                    f"en service : {', '.join(f'{k} = {c.get(k)!r}' for k in divergences)}."
                ],
            )
        # Texte et citation ne bougent que si le passage cité a changé : citation
        # retrouvée dans la référence, absente de la page fraîche de son
        # document, et une citation neuve retrouvée dans une page fraîche.
        ses_frais = frais_de(doc_base) if doc_base else []
        change = (
            bool(ses_frais)
            and _ou(q, ses_frais) is None
            and _norm(a.get("quote")) != _norm(q)
            and _ou(a.get("quote"), frais) is not None
        )
        if not change:
            sortie.append(c)  # inchangée, endettée ou toujours citée : à l'octet
            continue
        if c.get("kind") == "user_fact" or c.get("predicate") is not None:
            case(
                "reextraction-texte",
                "texte de condition à revoir",
                [
                    f"`{c.get('id')}` : le passage cité a changé ; l'agent propose :",
                    f"> {a.get('quote')}",
                    f"Texte proposé : {a.get('text')}",
                ],
                {"voir": "vu, je corrige à la main", "garder": "garder la version en service"},
            )
            sortie.append(c)
            continue
        nouvelle = dict(c)
        nouvelle["text"], nouvelle["quote"] = a.get("text"), a.get("quote")
        r.changements.append(
            f"condition {c.get('id')} : texte et citation repris de sa page fraîche"
        )
        sortie.append(nouvelle)
    gardees = list(sortie)
    ids = {c.get("id") for c in sortie}
    for a in proposees:
        if id(a) in utilisees or a.get("id") in ids:
            continue  # jamais un id réattribué
        motifs = []
        if a.get("kind") in (None, "untyped"):
            motifs.append("condition non typée")
        if "effect" not in a:
            motifs.append("sans ligne `effect`")
        if a.get("kind") == "manual_check" and _effet(a) == "gate":
            motifs.append("`manual_check` en gate")
        if (
            a.get("kind") in ("auto", "user_fact", "manual_check")
            and _ou(a.get("quote"), frais + base) is None
        ):
            motifs.append("citation introuvable dans les instantanés")
        proche = max(
            ((recouvrement(a.get("quote"), c.get("quote")), c.get("id")) for c in gardees),
            default=(0.0, None),
        )
        if proche[0] >= SEUIL_PROCHE:
            motifs.append(f"citation qui recoupe à {proche[0]:.0%} celle de `{proche[1]}`, gardée")
        if motifs:
            case(
                "reextraction-condition",
                "condition neuve à valider",
                [
                    f"L'agent propose `{a.get('id')}` ({a.get('kind')}, {a.get('effect', 'sans effet')}) : {' ; '.join(motifs)}.",
                    f"> {a.get('quote')}",
                ],
                {"ajouter": "l'ajouter (à la main)", "ignorer": "ne pas l'ajouter"},
            )
            continue
        sortie.append(a)
        ids.add(a.get("id"))
        r.changements.append(f"condition ajoutée : {a.get('id')} ({a.get('kind')})")
        if a.get("kind") == "user_fact" and a.get("fact") and a["fact"] not in faits_connus:
            r.faits_neufs.append(a["fact"])
    r.cible["conditions"] = sortie

    # Calendrier, financement, cumul : clé par clé. Seule une date ou un nombre
    # écrit tel quel dans une page fraîche s'écrit ; tout autre changement
    # (booléen, texte, liste) est une case ; une clé que l'agent omet reste.
    texte_frais = controles.sans_accents("\n".join(d[1] for d in frais))
    for nom in SECTIONS:
        avant = ancien.get(nom) or {}
        apres = agent.get(nom) or {}
        if not isinstance(avant, dict) or not isinstance(apres, dict):
            continue
        acceptees: dict[str, Any] = {}
        en_case: list[str] = []
        for k, v in apres.items():
            if _norm(avant.get(k)) == _norm(v):
                continue
            if frais and controles.figure(v, texte_frais) is True:
                acceptees[k] = v
            else:
                en_case.append(f"{nom}.{k} : {avant.get(k)!r} → {v!r}")
        # Une échéance acceptée lève le dépôt permanent, que la source date.
        if (
            "date_limite" in acceptees
            and apres.get("permanent") is False
            and avant.get("permanent") is not False
        ):
            acceptees["permanent"] = False
            en_case = [x for x in en_case if not x.startswith(f"{nom}.permanent ")]
        if en_case:
            case("reextraction-valeur", f"{nom} : valeur à vérifier", [f"- {x}" for x in en_case])
        if acceptees:
            fusion = copy.deepcopy(avant)
            fusion.update(acceptees)
            r.cible[nom] = fusion
            r.changements.append(f"{nom} : {', '.join(sorted(acceptees))}")
    if any(ch.split(" :")[0] in SECTIONS for ch in r.changements) and ancien.get("fiche"):
        case(
            "reextraction-fiche",
            "bloc `fiche:` à relire",
            ["Le calendrier, le financement ou le cumul a changé."],
            {"vu": "relu ou régénéré"},
        )
    for nom in SURVEILLES:
        if _norm(ancien.get(nom)) != _norm(agent.get(nom)) and agent.get(nom) is not None:
            case(
                nom.replace("_", "-"),
                f"{nom} divergent",
                [
                    f"L'agent propose une autre valeur de `{nom}` ; la version en service est gardée."
                ],
            )
    for f in r.faits_neufs:
        case(
            "H-fait",
            f"fait neuf `{f}`",
            [f"Proposé par la ré-extraction de `{slug}`, ajouté en fin de `facts_pending.yaml`."],
            {"vu": "validé (déplacé dans facts.yaml) ou refusé, à la main, comme aujourd'hui"},
        )
    return r


# ------------------------------------------------------------------ acceptation par écart


def cle_erreur(message: str) -> str:
    """Une erreur de lint réduite à (aide, condition ou champ, règle) : stable d'une version à l'autre.

    La tête du message (« slug / id ») se garde telle quelle : deux conditions
    dont les ids ne diffèrent que par un chiffre restent deux erreurs. Seule la
    règle est débarrassée des valeurs qu'elle cite (nombres, extraits).
    """
    tete, sep, regle = message.partition(": ")
    if not sep:
        tete, regle = "", message
    regle = re.sub(r"«[^»]*»|\"[^\"]*\"|`[^`]*\d[^`]*`|\([^)]*\d[^)]*\)", "«»", regle)
    return tete + " : " + re.sub(r"\d", "0", regle)


def erreurs_nouvelles(avant: list[str], apres: list[str]) -> list[str]:
    deja = {cle_erreur(e) for e in avant}
    return [e for e in apres if cle_erreur(e) not in deja]


def lint_aide(dossier: Path, slug: str, pending: Path, sources: Path) -> list[str]:
    """Le lint d'une aide, citations cherchées dans `sources` (et non dans `data/sources/`)."""
    from lint_aides_data import lint

    from catalogue import veille_collect

    ancien = veille_collect.SOURCES_DIR
    try:
        veille_collect.SOURCES_DIR = sources
        rapport = lint([slug], quotes=True, aides_dir=dossier, pending_path=pending, ecriture=True)
    finally:
        veille_collect.SOURCES_DIR = ancien
    return list(rapport.erreurs)


# ------------------------------------------------------------------ faits


def blocs_faits(texte: str) -> dict[str, str]:
    """Les blocs de premier niveau de `facts_pending.yaml`, clé -> texte (commentaires d'en-tête compris)."""
    lignes = texte.split("\n")
    debuts = [i for i, ligne in enumerate(lignes) if re.match(r"^[a-z0-9_]+:", ligne)]
    blocs: dict[str, str] = {}
    for n, d in enumerate(debuts):
        tete = d
        while tete > 0 and lignes[tete - 1].startswith("#"):
            tete -= 1
        f = debuts[n + 1] if n + 1 < len(debuts) else len(lignes)
        while f > d + 1 and (not lignes[f - 1].strip() or lignes[f - 1].startswith("#")):
            f -= 1
        blocs[lignes[d].split(":", 1)[0]] = "\n".join(lignes[tete:f])
    return blocs


def ajouter_faits(cles: list[str], propose: Path, cible: Path = FACTS_PENDING_FILE) -> list[str]:
    """Ajoute en fin de fichier, sous verrou, les faits de l'agent absents de `cible` ; jamais de réécriture."""
    import fcntl

    venus = blocs_faits(propose.read_text(encoding="utf-8")) if propose.exists() else {}
    with cible.open("a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            texte = f.read()
            deja = blocs_faits(texte)
            ajoutes = [k for k in cles if k in venus and k not in deja]
            if ajoutes:
                f.write(
                    ("" if texte.endswith("\n") or not texte else "\n")
                    + "".join(f"\n{venus[k]}\n" for k in ajoutes)
                )
                f.flush()
                os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    return ajoutes


# ------------------------------------------------------------------ écriture


@dataclass
class Bilan:
    slug: str
    issue: str
    raison: str = ""
    panne: str | None = None
    cout_usd: float = 0.0
    duree_s: float = 0.0
    cases: list[Case] = field(default_factory=list)
    changements: list[str] = field(default_factory=list)
    texte: str | None = None
    snapshots: list[str] = field(default_factory=list)
    faits: list[str] = field(default_factory=list)


def rebut(slug: str, sortie: Path, motif: str, jour: dt.date, rebuts: Path = REBUTS) -> Path | None:
    """Range la tentative refusée hors du catalogue ; la version en service ne bouge pas."""
    for nom in (f"{slug}.yaml", f"{slug}.yaml.echec"):
        source = sortie / "aides" / nom
        if source.exists():
            cible = rebuts / slug / f"{jour.isoformat()}.yaml"
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_text(
                f"# Ré-extraction refusée le {jour.isoformat()} : {motif[:300]}\n"
                + source.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            return cible
    return None


def depense(sortie: Path) -> float:
    chemin = sortie / "appels.jsonl"
    if not chemin.exists():
        return 0.0
    total = 0.0
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        if ligne.strip():
            d = json.loads(ligne)
            # Un appel non facturé compte pour son plafond, jamais pour zéro.
            cout = d.get("cout_usd")
            total += float(cout if cout is not None else (d.get("cout_compte") or 0.0))
    return total


def reextraire(
    slug: str,
    *,
    plafond: float,
    delai_s: float,
    jour: dt.date,
    etat: str,
    sorties: Path = SORTIES,
    aides: Path = AIDES_DIR,
    sources: Path = SOURCES_DIR,
    pending: Path = FACTS_PENDING_FILE,
    rebuts: Path = REBUTS,
    ecrire: bool = True,
    lanceur: Any = None,
) -> Bilan:
    """Une ré-extraction complète, de la préparation à l'écriture. Ne lève pas : une erreur est une panne."""
    try:
        return _reextraire(
            slug,
            plafond=plafond,
            delai_s=delai_s,
            jour=jour,
            etat=etat,
            sorties=sorties,
            aides=aides,
            sources=sources,
            pending=pending,
            rebuts=rebuts,
            ecrire=ecrire,
            lanceur=lanceur,
        )
    except Exception as exc:  # noqa: BLE001 — une exception est une panne de l'objet, pas un jugement
        return Bilan(slug, "panne", f"{type(exc).__name__}: {exc}"[:300], panne="bug")


def _reextraire(
    slug: str,
    *,
    plafond: float,
    delai_s: float,
    jour: dt.date,
    etat: str,
    sorties: Path,
    aides: Path,
    sources: Path,
    pending: Path,
    rebuts: Path,
    ecrire: bool,
    lanceur: Any,
) -> Bilan:
    chemin = aides / f"{slug}.yaml"
    if not chemin.exists():
        # C-orpheline : jamais de ré-extraction d'une aide sans YAML en service.
        return Bilan(slug, "orpheline", "aucun YAML en service : contradiction, case de Félix")
    sortie = (
        sorties
        / f"{jour.isoformat()}-{slug}-{os.getpid()}-{dt.datetime.now().strftime('%H%M%S%f')}"
    )
    preparer(slug, sortie, aides, sources)
    # L'agent part du même facts_pending.yaml que celui où ses faits seront ajoutés.
    if pending.exists():
        shutil.copy2(pending, sortie / "facts_pending.yaml")
    lancement = (lanceur or lancer)(slug, sortie, plafond, delai_s)
    b = Bilan(slug, "panne", cout_usd=depense(sortie), duree_s=lancement.duree_s)
    if lancement.resultat is None:
        b.raison, b.panne = f"agent sans résultat ({lancement.panne})", lancement.panne
        return b
    issue, raison, classe = classer(lancement.resultat)
    b.issue, b.raison, b.panne = issue, raison, classe
    if issue == "hors_perimetre":
        b.cases.append(
            Case(
                "reextraction-hors-perimetre",
                f"a:{slug}",
                "l'agent juge l'aide hors périmètre",
                etat,
                {"garder": "la garder au catalogue", "ecarter": "l'écarter (à la main)"},
                (raison,),
            )
        )
        return b
    if issue == "refusee":
        if ecrire:
            rebut(slug, sortie, raison, jour, rebuts)
        return b
    if issue != "acceptee":
        return b

    texte_ancien = chemin.read_text(encoding="utf-8")
    ancien = charger_yaml(texte_ancien) or {}
    agent = charger_yaml((sortie / "aides" / f"{slug}.yaml").read_text(encoding="utf-8")) or {}
    noms_avant = (
        {p.name for p in (sources / slug).iterdir()} if (sources / slug).is_dir() else set()
    )
    tous, urls = documents(sortie / "sources" / slug)
    base = [d for d in tous if d[0] in noms_avant]
    frais = [d for d in tous if d[0] not in noms_avant]
    from aides_schema import load_facts, load_pending_facts

    connus = set(load_facts()) | set(load_pending_facts(pending))
    r = retour(slug, ancien, agent, base, frais, connus, etat, urls)
    b.cases, b.changements = r.cases, r.changements
    try:
        nouveau = editer(texte_ancien, r.cible)
    except EditionImpossible as exc:
        b.issue, b.raison, b.panne = "panne", f"éditeur : {exc}", "bug"
        return b
    if nouveau == texte_ancien:
        b.issue, b.raison = "inchangee", "rien à écrire dans le mandat de la ré-extraction"
        return b
    # Acceptation par écart : la dette connue ne refuse pas, une erreur neuve si.
    # Avant : la version en service contre ses instantanés ; après : la version
    # écrite contre ces instantanés plus ceux que l'agent vient d'archiver.
    essai = sortie / "essai"
    essai.mkdir(exist_ok=True)
    (essai / f"{slug}.yaml").write_text(nouveau, encoding="utf-8")
    pending_essai = sortie / "facts_pending.yaml"
    neuves = erreurs_nouvelles(
        lint_aide(sortie / "en-service", slug, pending, sources),
        lint_aide(
            essai, slug, pending_essai if pending_essai.exists() else pending, sortie / "sources"
        ),
    )
    if neuves:
        b.issue, b.raison = "refusee", "lint : " + " ; ".join(neuves[:3])
        if ecrire:
            rebut(slug, sortie, b.raison, jour, rebuts)
        return b
    b.issue, b.texte = "acceptee", nouveau
    # Les conditions NEUVES rattachées à leur famille (catalogue/espace.py) ;
    # celles que la ré-extraction garde à l'octet l'ont déjà été.
    ids_avant = {c.get("id") for c in ancien.get("conditions") or [] if isinstance(c, dict)}
    ids_apres = {
        c.get("id")
        for c in (charger_yaml(nouveau) or {}).get("conditions") or []
        if isinstance(c, dict)
    }
    if neuves := {str(i) for i in ids_apres - ids_avant if i}:
        from catalogue import espace as espace_mod

        ecarts, _panne = espace_mod.controler_aide(slug, nouveau, seulement=neuves)
        b.cases += ecarts
    if ecrire:
        # Ordre de la section 7.6 : les faits, puis les instantanés et le YAML.
        b.faits = ajouter_faits(r.faits_neufs, pending_essai, pending)
        (sources / slug).mkdir(parents=True, exist_ok=True)
        for p in sorted((sortie / "sources" / slug).iterdir()):
            if p.name not in noms_avant:
                shutil.copy2(p, sources / slug / p.name)
                b.snapshots.append(p.name)
        temporaire = chemin.with_name(f".{chemin.name}.{os.getpid()}.tmp")
        temporaire.write_text(nouveau, encoding="utf-8")
        temporaire.replace(chemin)
    return b
