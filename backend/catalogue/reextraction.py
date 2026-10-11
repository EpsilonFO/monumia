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

from veille_collect import SOURCES_DIR, load_baselines
from veille_text import find_quote_in_any

from aides_schema import AIDES_DIR, DATA_DIR, FACTS_PENDING_FILE, charger_yaml
from catalogue import controles
from catalogue.cases import Case
from catalogue.editeur import EditionImpossible, editer
from catalogue.registre import BACKEND

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
    """(issue, raison, classe de panne) d'une ré-extraction terminée."""
    if r.get("panne_contrat"):
        return "panne", f"contrat : {r['panne_contrat']}", r["panne_contrat"]
    if r.get("verification_indisponible"):
        return (
            "panne",
            f"vérificateur indisponible : {r['verification_indisponible']}",
            "verification",
        )
    if r.get("echec_fatal"):
        return "panne", r.get("motif_echec") or "erreur fatale", "cle"
    if r.get("echec_transitoire"):
        return "panne", r.get("motif_echec") or "panne du fournisseur", "fournisseur"
    if r.get("hors_perimetre"):
        cat, motif = r["hors_perimetre"]
        return "hors_perimetre", f"{cat} : {motif}", None
    if not r.get("ok"):
        return "refusee", r.get("motif_echec") or "refusée par les contrôles", None
    return "acceptee", "", None


# ------------------------------------------------------------------ retour


def _documents(dossier: Path, noms: set[str] | None = None) -> list[tuple[str, str, str]]:
    """Les documents d'un dossier d'instantanés, lus comme la veille et le lint les lisent."""
    import veille_collect

    ancien = veille_collect.SOURCES_DIR
    try:
        veille_collect.SOURCES_DIR = dossier.parent
        docs, _, _ = load_baselines(dossier.name)
    finally:
        veille_collect.SOURCES_DIR = ancien
    return [d for d in docs if noms is None or d[0] in noms]


def _trouvee(quote: str | None, docs: list[tuple[str, str, str]]) -> bool:
    if not quote or not docs:
        return False
    nom, _ = find_quote_in_any(quote, docs)  # type: ignore[arg-type]
    return nom is not None


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


def retour(
    slug: str,
    ancien: dict[str, Any],
    agent: dict[str, Any],
    base: list[tuple[str, str, str]],
    frais: list[tuple[str, str, str]],
    faits_connus: set[str],
    etat: str,
) -> Retour:
    """La cible que l'aide en service peut devenir, et les cases de ce qui ne s'écrit pas."""
    objet = f"a:{slug}"
    r = Retour(cible=copy.deepcopy(ancien))

    def case(
        sorte: str, titre: str, lignes: list[str], options: dict[str, str] = OPTIONS_DIVERGENCE
    ) -> None:
        r.cases.append(Case(sorte, objet, titre, f"{etat}:{len(r.cases)}", options, tuple(lignes)))

    anciennes: list[dict[str, Any]] = list(ancien.get("conditions") or [])
    proposees: list[dict[str, Any]] = list(agent.get("conditions") or [])
    par_id = {c.get("id"): c for c in proposees}
    utilisees: set[int] = set()

    def rapprocher(c: dict[str, Any]) -> dict[str, Any] | None:
        a = par_id.get(c.get("id"))
        if a is not None:
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
        en_base, en_frais = _trouvee(q, base), _trouvee(q, frais)
        if a is None:
            if en_base and frais and not en_frais:
                if (
                    c.get(
                        "effect", "info" if c.get("kind") in ("info", "discretionary") else "gate"
                    )
                    == "info"
                ):
                    r.changements.append(
                        f"condition retirée : {c.get('id')} (citation disparue de la source)"
                    )
                    continue
                case(
                    "reextraction-retrait",
                    "retrait de condition proposé",
                    [
                        f"`{c.get('id')}` ({c.get('kind')}, {c.get('effect', 'gate')}) : sa citation a disparu des pages fraîches.",
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
                    f"`{c.get('id')}` : l'agent propose {', '.join(f'{k} = {a.get(k)!r}' for k in divergences)} ; en service : {', '.join(f'{k} = {c.get(k)!r}' for k in divergences)}."
                ],
            )
        if (
            not q
            or not en_base
            or en_frais
            or (a.get("quote") == q and a.get("text") == c.get("text"))
        ):
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
            f"condition {c.get('id')} : texte et citation repris de la source fraîche"
        )
        sortie.append(nouvelle)
    for a in proposees:
        if id(a) in utilisees:
            continue
        if a.get("id") in {c.get("id") for c in sortie}:
            continue  # jamais un id réattribué
        proche = max(
            ((recouvrement(a.get("quote"), c.get("quote")), c.get("id")) for c in sortie),
            default=(0.0, None),
        )
        if proche[0] >= SEUIL_PROCHE:
            # Une condition neuve qui recoupe une condition gardée est peut-être
            # la même, réécrite : l'ajouter ferait un doublon, la jeter une perte.
            case(
                "reextraction-proche",
                "condition proche d'une condition en service",
                [
                    f"L'agent propose `{a.get('id')}`, dont la citation recoupe à {proche[0]:.0%} celle de `{proche[1]}` (gardée).",
                    f"> {a.get('quote')}",
                ],
                {"ajouter": "c'est une exigence distincte : l'ajouter", "ignorer": "c'est la même"},
            )
            continue
        sortie.append(a)
        r.changements.append(f"condition ajoutée : {a.get('id')} ({a.get('kind')})")
        if a.get("kind") == "user_fact" and a.get("fact") and a["fact"] not in faits_connus:
            r.faits_neufs.append(a["fact"])
    r.cible["conditions"] = sortie

    texte_frais = controles.sans_accents("\n".join(d[1] for d in frais))
    for nom in SECTIONS:
        avant, apres = _norm(ancien.get(nom) or {}), _norm(agent.get(nom) or {})
        if avant == apres:
            continue
        changees = {k: v for k, v in apres.items() if avant.get(k) != v}
        deduites = [
            f"{nom}.{k} = {v}"
            for k, v in changees.items()
            if controles.figure(v, texte_frais) is False
        ]
        if deduites or not frais:
            case(
                "reextraction-valeur",
                f"{nom} : valeur à vérifier",
                [f"- {d}" for d in deduites] or ["- aucune page fraîche re-téléchargée"],
            )
            continue
        if nom in ancien or apres:
            r.cible[nom] = agent.get(nom)
            r.changements.append(f"{nom} : {', '.join(sorted(changees))}")
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
            {"valider": "valider", "refuser": "refuser"},
        )
    return r


# ------------------------------------------------------------------ acceptation par écart


def cle_erreur(message: str) -> str:
    """Une erreur de lint sans les valeurs qu'elle cite : ce qui la rend stable d'une version à l'autre."""
    sans = re.sub(r"«[^»]*»|\"[^\"]*\"", "«»", message)
    return re.sub(r"\d", "0", sans)


def erreurs_nouvelles(avant: list[str], apres: list[str]) -> list[str]:
    deja = {cle_erreur(e) for e in avant}
    return [e for e in apres if cle_erreur(e) not in deja]


def lint_aide(dossier: Path, slug: str, pending: Path) -> list[str]:
    from lint_aides_data import lint

    rapport = lint([slug], quotes=True, aides_dir=dossier, pending_path=pending, ecriture=True)
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
    """Ajoute en fin de fichier les faits de l'agent absents de `cible` ; jamais de réécriture."""
    texte = cible.read_text(encoding="utf-8") if cible.exists() else ""
    deja = blocs_faits(texte)
    venus = blocs_faits(propose.read_text(encoding="utf-8")) if propose.exists() else {}
    ajoutes = [k for k in cles if k in venus and k not in deja]
    if ajoutes:
        with cible.open("a", encoding="utf-8") as f:
            f.write(
                ("" if texte.endswith("\n") else "\n") + "".join(f"\n{venus[k]}\n" for k in ajoutes)
            )
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
            total += float(d.get("cout_usd") or d.get("cout_compte") or 0.0)
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
    chemin = aides / f"{slug}.yaml"
    if not chemin.exists():
        # C-orpheline : jamais de ré-extraction d'une aide sans YAML en service.
        return Bilan(slug, "orpheline", "aucun YAML en service : contradiction, case de Félix")
    sortie = (
        sorties
        / f"{jour.isoformat()}-{slug}-{os.getpid()}-{dt.datetime.now().strftime('%H%M%S%f')}"
    )
    preparer(slug, sortie, aides, sources)
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
    tous = _documents(sortie / "sources" / slug)
    base = [d for d in tous if d[0] in noms_avant]
    frais = [d for d in tous if d[0] not in noms_avant]
    from aides_schema import load_facts, load_pending_facts

    connus = set(load_facts()) | set(load_pending_facts(pending))
    r = retour(slug, ancien, agent, base, frais, connus, etat)
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
    essai = sortie / "essai"
    essai.mkdir(exist_ok=True)
    (essai / f"{slug}.yaml").write_text(nouveau, encoding="utf-8")
    pending_essai = sortie / "facts_pending.yaml"
    neuves = erreurs_nouvelles(
        lint_aide(sortie / "en-service", slug, pending),
        lint_aide(essai, slug, pending_essai if pending_essai.exists() else pending),
    )
    if neuves:
        b.issue, b.raison = "refusee", "lint : " + " ; ".join(neuves[:3])
        if ecrire:
            rebut(slug, sortie, b.raison, jour, rebuts)
        return b
    b.issue, b.texte = "acceptee", nouveau
    if ecrire:
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
