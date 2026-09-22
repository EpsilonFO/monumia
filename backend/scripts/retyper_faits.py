"""Retype les conditions qui citent un fait, puis retire le fait. Table YAML.

Script de MIGRATION, jumeau de `fusionner_faits.py` et jetable comme lui : il
sert à résorber le lot du 2026-09-18 (563 faits proposés pour 643 aides, dont
431 cités par UNE seule aide). Les gardes posées à l'écriture — plafond de trois
faits par aide, refus des booléens à seuil, refus des questions de 500
caractères — sont là pour que le passif ne se reconstitue pas.

    uv run python scripts/retyper_faits.py data/fusions/lot-s-engage.yaml --dry-run
    uv run python scripts/retyper_faits.py --s-engage --dry-run
    uv run python scripts/retyper_faits.py data/fusions/lot-s-engage.yaml

Le mandat est ÉTROIT, comme celui de `fusionner_faits.py`, et pour la même
raison : une condition qu'on retype garde son `text` et sa `quote` — ce qui
change, c'est son STATUT dans le moteur, pas ce que la source dit.

  - un `s_engage_*` devient `kind: info` + `effect: info` : un engagement du
    demandeur se vérifie au dossier, pas au questionnaire. 48 faits du lot, 59
    gates, et personne ne répond « non » à « acceptez-vous la charte ? » ;
  - tout autre fait devient `kind: manual_check` + `effect: info` : une exigence
    propre à une aide, qu'aucun fait partageable ne porte, s'affiche « à
    confirmer avec l'organisme » plutôt que de poser une question à tous les
    propriétaires.

Dans les deux cas, `fact`, `predicate` et `derogation_possible` disparaissent,
et `notes` gagne une ligne de provenance. Le fait est ensuite retiré de
`facts_pending.yaml` — ou de `facts.yaml` si la ligne le dit (voir `source`).

Format de la table :

    retypages:
      - fait: s_engage_charte_qualite
        motif: Engagement du demandeur, vérifié au dossier.
      - fait: itineraire_eligible_pdipr
        motif: Liste d'exclusions propre au règlement, aucune portée partagée.
      - fait: demande_deposee_avant_demarrage
        motif: Formalité de dépôt ; le critère réel est `etat_travaux`.
        source: facts.yaml   # fait APPROUVÉ : le retrait est décidé ici
        kind: info           # le préfixe ne le donne pas

`source` et `kind` sont OPTIONNELS et ne changent rien quand ils manquent :
sans `source`, le fait se lit et se retire de `facts_pending.yaml` et un fait
approuvé est refusé ; sans `kind`, il se déduit du préfixe. Les deux sont là
pour que la décision s'écrive dans la TABLE — relue, commitée, diffable — et
non dans un drapeau de ligne de commande.

Ce que le script REFUSE, et rien de ce qui suit n'est négociable :

  - un fait approuvé (`facts.yaml`) SANS `source: facts.yaml` sur sa ligne : le
    retirer est une décision humaine, et elle s'écrit ;
  - un fait cité par un `applies_if` : c'est un périmètre, pas une condition —
    le retyper changerait la portée de l'aide, pas le statut d'un critère ;
  - un `kind` hors des deux que ce script produit (`info`, `manual_check`).

Les fichiers d'aide que `safe_dump(safe_load(t)) != t` — porteurs de
commentaires ou d'une mise en forme qu'une réécriture entière détruirait — ne
sont plus refusés : ils passent par une réécriture TEXTUELLE du seul bloc de la
condition visée (`_reecrire_textuellement`), le reste du fichier n'étant pas
touché d'un caractère. Un invariant vérifié avant toute écriture compare le
fichier réécrit à ce que `_retyper_condition` produit ; s'il échoue, le fichier
entier est refusé et nommé. 58 des 109 fichiers du lot des engagements sont dans
ce cas — la voie `safe_dump` seule aurait laissé plus de la moitié du lot à la
main.

Neutre pour le cliquet `manual_check` : celui-ci ne compte que les `gate` et les
`manual_check` sans `notes`, et ce script produit des `effect: info` avec notes.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ingestion.faits import _decouper_bloc
from lint_aides_data import lint

from aides_schema import (
    AIDES_DIR,
    FACTS_FILE,
    FACTS_PENDING_FILE,
    Aide,
    load_facts,
    load_pending_facts,
)

#: Préfixe des faits d'ENGAGEMENT. Un `s_engage_*` décrit ce que le demandeur
#: promet de faire, pas une propriété du bien ou du porteur : il n'a jamais sa
#: place dans le questionnaire, parce que la réponse est toujours « oui ».
PREFIXE_ENGAGEMENT = "s_engage_"

#: Les deux `kind` que ce script produit, et les seuls que `kind:` accepte dans
#: la table. Élargir la liste, c'est élargir le mandat.
KINDS_AUTORISES = ("info", "manual_check")

#: Les deux fichiers d'ontologie, valeurs admises de `source:`.
SOURCE_PENDING = "facts_pending.yaml"
SOURCE_APPROUVE = "facts.yaml"


@dataclass(frozen=True)
class Retypage:
    """Une ligne de la table."""

    fait: str
    motif: str = ""
    #: D'où retirer le fait. Vide = `facts_pending.yaml`, le cas ordinaire.
    #: `facts.yaml` dit que le fait est APPROUVÉ et que son retrait est décidé —
    #: la décision humaine que le script exige est cette ligne-là.
    source: str = ""
    #: `kind` imposé par la table, quand le préfixe ne le donne pas
    #: (`demande_deposee_avant_demarrage` est une promesse sans être un
    #: `s_engage_*`).
    kind_declare: str = ""

    @property
    def approuve(self) -> bool:
        return self.source == SOURCE_APPROUVE

    @property
    def kind(self) -> str:
        """Celui de la table, sinon `info` pour un engagement, `manual_check`.

        La distinction n'est pas cosmétique : une `info` ne s'affiche pas comme
        un critère à vérifier (l'utilisateur n'a rien à faire d'un engagement
        qu'il prendra en signant), un `manual_check` si.
        """
        if self.kind_declare:
            return self.kind_declare
        return "info" if self.fait.startswith(PREFIXE_ENGAGEMENT) else "manual_check"


@dataclass
class Rapport:
    """Ce que la migration a fait, ou ferait. `erreurs` non vide = rien n'est écrit."""

    erreurs: list[str] = field(default_factory=list)
    #: fait → [slug/condition] retypés
    retypages: dict[str, list[str]] = field(default_factory=dict)
    retires: list[str] = field(default_factory=list)
    fichiers_touches: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.erreurs

    @property
    def conditions(self) -> int:
        return sum(len(v) for v in self.retypages.values())

    def texte(self) -> str:
        lignes: list[str] = []
        for fait, cibles in sorted(self.retypages.items()):
            lignes.append(f"  {fait}  →  {len(cibles)} condition(s) : {', '.join(cibles)}")
        lignes.append(
            f"  TOTAL : {self.conditions} condition(s) retypée(s), "
            f"{len(self.fichiers_touches)} fichier(s) d'aide, "
            f"{len(self.retires)} fait(s) retiré(s)"
        )
        for e in self.erreurs:
            lignes.append(f"  ERREUR : {e}")
        return "\n".join(lignes)


# ---------------------------------------------------------------------------
# Lecture et validation de la table
# ---------------------------------------------------------------------------


def charger_table(chemin: Path) -> tuple[list[Retypage], list[str]]:
    """Lit la table YAML. Rend (retypages, erreurs de forme)."""
    try:
        brut = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return [], [f"table illisible : {exc}"]
    if not isinstance(brut, dict) or not isinstance(brut.get("retypages"), list):
        return [], ["la table doit être un objet avec une liste `retypages`"]
    retypages, erreurs = [], []
    for i, ligne in enumerate(brut["retypages"], 1):
        if not isinstance(ligne, dict) or not ligne.get("fait"):
            erreurs.append(f"retypage n° {i} : `fait` manquant")
            continue
        source = str(ligne.get("source") or "")
        if source and source not in (SOURCE_PENDING, SOURCE_APPROUVE):
            erreurs.append(
                f"retypage n° {i} : `source: {source}` inconnu — "
                f"{SOURCE_PENDING} ou {SOURCE_APPROUVE}"
            )
            continue
        kind = str(ligne.get("kind") or "")
        if kind and kind not in KINDS_AUTORISES:
            erreurs.append(
                f"retypage n° {i} : `kind: {kind}` hors du mandat — {' ou '.join(KINDS_AUTORISES)}"
            )
            continue
        retypages.append(
            Retypage(
                fait=str(ligne["fait"]),
                motif=str(ligne.get("motif") or ""),
                source=source,
                kind_declare=kind,
            )
        )
    return retypages, erreurs


def table_des_engagements(pending: dict) -> list[Retypage]:
    """Tous les `s_engage_*` du fichier en attente, sans distinction.

    Les EXCEPTIONS se retirent à la main de la table produite : un engagement qui
    porte une contrainte durable et réutilisable — « conserver 15 ans »,
    « maintenir la plantation 7 ans », « ouvrir au public » — mérite de rester
    un fait, de préférence sous la forme d'un integer (`duree_*_ans`) qui porte
    sa durée dans le prédicat. Le script ne sait pas les reconnaître, et
    prétendre le contraire ferait perdre en silence des critères qui comptent.
    """
    return [
        Retypage(fait=cle, motif="Engagement du demandeur, affiché dans le dossier.")
        for cle in sorted(pending)
        if cle.startswith(PREFIXE_ENGAGEMENT)
    ]


def _round_trip_stable(chemin: Path) -> bool:
    """Le fichier survit-il à `safe_load` puis `safe_dump` sans rien perdre ?

    C'est le seul test qui distingue un YAML écrit par `ecrire_aide` — que l'on
    peut réécrire sans dommage — d'un fichier annoté à la main, dont les
    commentaires seraient effacés en silence.
    """
    texte = chemin.read_text(encoding="utf-8")
    try:
        charge = yaml.safe_load(texte)
    except yaml.YAMLError:
        return False
    return yaml.safe_dump(charge, allow_unicode=True, sort_keys=False, width=100) == texte


def verifier(
    retypages: list[Retypage],
    facts: dict,
    pending: dict,
    *,
    aides_dir: Path = AIDES_DIR,
) -> list[str]:
    """Tout ce qui doit être vrai AVANT d'écrire quoi que ce soit.

    Le refus porte sur la table ENTIÈRE : une migration à moitié appliquée
    laisserait des aides citant un fait supprimé, et le lint ne dirait pas
    lesquelles rattraper.
    """
    erreurs: list[str] = []
    vus: set[str] = set()
    for r in retypages:
        if r.approuve:
            if r.fait not in facts:
                erreurs.append(
                    f"« {r.fait} » porte `source: {SOURCE_APPROUVE}` mais n'y est pas — "
                    "ligne à corriger avant de retirer quoi que ce soit."
                )
        elif r.fait in facts:
            erreurs.append(
                f"« {r.fait} » est APPROUVÉ (facts.yaml) — le retirer est une décision "
                f"humaine : l'écrire dans la table (`source: {SOURCE_APPROUVE}`)."
            )
        elif r.fait not in pending:
            erreurs.append(f"« {r.fait} » n'est pas dans facts_pending.yaml — déjà retypé ?")
        if r.fait in vus:
            erreurs.append(f"« {r.fait} » apparaît deux fois dans la table")
        vus.add(r.fait)

    cles = {r.fait for r in retypages}
    for chemin in sorted(aides_dir.glob("*.yaml")):
        try:
            aide = Aide.model_validate(yaml.safe_load(chemin.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001 — le lint le dira mieux
            erreurs.append(f"{chemin.stem} : illisible ({exc})")
            continue
        if aide.applies_if and aide.applies_if.fact in cles:
            erreurs.append(
                f"{chemin.stem} : `applies_if` d'aide sur « {aide.applies_if.fact} » — c'est un "
                "PÉRIMÈTRE, pas une condition. Le retyper changerait la portée de l'aide : "
                "hors du mandat de ce script."
            )
        for cond in aide.conditions:
            if cond.applies_if and cond.applies_if.fact in cles:
                erreurs.append(
                    f"{chemin.stem} / {cond.id} : `applies_if` de condition sur "
                    f"« {cond.applies_if.fact} » — clause d'applicabilité, hors mandat."
                )
    return erreurs


def _conditions_visees(aide: Aide, cles: set[str]) -> list[str]:
    """Les ids de condition qui gatent (ou citent) l'un des faits de la table."""
    return [c.id for c in aide.conditions if c.fact in cles]


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


#: Clés que le retypage EFFACE d'une condition. Seule liste, lue par les deux
#: voies d'écriture (`safe_dump` et réécriture textuelle).
CLES_EFFACEES = ("fact", "predicate", "derogation_possible")


def _notes_retypees(brut: dict, r: Retypage, jour: date) -> str:
    """Les `notes` de la condition retypée : celles d'avant, plus la provenance."""
    notes = str(brut.get("notes") or "").strip()
    provenance = (
        f"Retypé le {jour.isoformat()} : {r.motif or 'exigence propre à cette aide'} "
        f"(ex-fait {r.fait})."
    )
    return f"{notes} {provenance}".strip() if notes else provenance


def _retyper_condition(brut: dict, r: Retypage, jour: date) -> dict:
    """La condition réécrite : `text` et `quote` intacts, le reste effacé.

    `text` et `quote` sont ce que la SOURCE dit, et ce script ne lit aucune
    source : il n'a rien à en dire. Ce qu'il change est le statut de la
    condition dans le moteur.

    C'est aussi la RÉFÉRENCE de la réécriture textuelle : ce qu'elle doit
    produire, clé par clé, faute de quoi le fichier est refusé.
    """
    sortie = {
        cle: val
        for cle, val in brut.items()
        if cle not in (*CLES_EFFACEES, "kind", "effect", "notes")
    }
    # L'ordre des clés suit celui d'`ecrire_aide` : id, text, kind, effect, …
    ordonne: dict = {}
    for cle in ("id", "text"):
        if cle in sortie:
            ordonne[cle] = sortie.pop(cle)
    ordonne["kind"] = r.kind
    ordonne["effect"] = "info"
    ordonne["notes"] = _notes_retypees(brut, r, jour)
    ordonne.update(sortie)
    return ordonne


# ---------------------------------------------------------------------------
# Réécriture TEXTUELLE d'un bloc de condition
#
# Pour les 58 fichiers du lot qu'un humain a annotés : `safe_dump` du fichier
# entier effacerait ses commentaires, qui sont précisément ce que la relecture
# a produit. On ne touche donc que les lignes du bloc visé, et on vérifie
# ensuite que le fichier rendu charge EXACTEMENT le retypage attendu.
# ---------------------------------------------------------------------------


def _bloc_scalaire(cle: str, valeur: str, indent: int) -> list[str]:
    """Les lignes YAML d'une clé scalaire, indentées. L'échappement vient de PyYAML."""
    brut = yaml.safe_dump({cle: valeur}, allow_unicode=True, sort_keys=False, width=100)
    return [(" " * indent + li) if li.strip() else li for li in brut.splitlines(keepends=True)]


def _bornes_conditions(lignes: list[str]) -> tuple[int, int] | None:
    """(début, fin) des lignes de la section `conditions:` de premier niveau."""
    depart = next((i for i, li in enumerate(lignes) if re.match(r"^conditions:\s*$", li)), None)
    if depart is None:
        return None
    for i in range(depart + 1, len(lignes)):
        li = lignes[i]
        if not li.strip() or li[:1] in (" ", "\t") or li.lstrip().startswith(("-", "#")):
            continue
        return depart, i  # première clé de premier niveau qui suit
    return depart, len(lignes)


def _bloc_condition(lignes: list[str], cond_id: str) -> tuple[int, int, int] | None:
    """(début, fin, indentation des clés) du bloc d'une condition, ou None.

    None dès que la forme n'est pas celle attendue — `id` ailleurs qu'en
    première clé de l'item, section `conditions` absente. L'appelant refuse
    alors le fichier : mieux vaut le nommer que le réécrire de travers.
    """
    section = _bornes_conditions(lignes)
    if section is None:
        return None
    debut_section, fin_section = section
    entete = re.compile(rf"^(\s*)-(\s+)id:\s*{re.escape(cond_id)}\s*$")
    for i in range(debut_section + 1, fin_section):
        m = entete.match(lignes[i])
        if m is None:
            continue
        prefixe = m.group(1) + "-"
        indent_cle = len(m.group(1)) + 1 + len(m.group(2))
        fin = fin_section
        for j in range(i + 1, fin_section):
            suite = lignes[j]
            if suite.startswith(prefixe) and suite[len(prefixe) :][:1] in (" ", "\t"):
                fin = j
                break
        return i, fin, indent_cle
    return None


def _segments(lignes: list[str], indent_cle: int) -> list[tuple[str | None, list[str]]]:
    """Découpe le CORPS d'un bloc de condition en (clé, lignes). Clé None = orphelin."""
    cle_re = re.compile(rf"^ {{{indent_cle}}}([A-Za-z_][A-Za-z0-9_]*):")
    segments: list[tuple[str | None, list[str]]] = []
    for li in lignes:
        m = cle_re.match(li)
        if m is not None:
            segments.append((m.group(1), [li]))
        elif segments:
            segments[-1][1].append(li)
        else:
            segments.append((None, [li]))
    return segments


def _detacher_queue(corps: list[str], indent_cle: int) -> tuple[list[str], list[str]]:
    """Sépare d'un segment les lignes de fin qui ne lui appartiennent pas.

    Une ligne vide, ou un commentaire MOINS indenté que les clés, n'est pas la
    valeur de la clé : c'est le séparateur ou le titre de section qui annonce
    l'entrée suivante. Sans ce détachement, retirer `fact:` ou régénérer
    `notes:` emporterait au passage un commentaire que la relecture a écrit —
    vu une fois, sur `merite-arboretums-de-france`.

    Un `#` PLUS indenté que les clés est du TEXTE dans un scalaire replié, pas
    un commentaire : il reste où il est.
    """
    fin = len(corps)
    while fin > 0:
        li = corps[fin - 1]
        nu = li.strip()
        if nu and (not nu.startswith("#") or len(li) - len(li.lstrip()) >= indent_cle):
            break
        fin -= 1
    return corps[:fin], corps[fin:]


def _reecrire_condition(
    lignes: list[str], brut_cond: dict, r: Retypage, jour: date
) -> list[str] | None:
    """Le bloc d'une condition, retypé sur place. None si la forme échappe."""
    trouve = _bloc_condition(lignes, str(brut_cond.get("id") or ""))
    if trouve is None:
        return None
    debut, fin, indent_cle = trouve
    marge = " " * indent_cle
    sortie: list[str] = [lignes[debut]]
    vues: set[str] = set()
    queue: list[str] = []
    for cle, brut_segment in _segments(lignes[debut + 1 : fin], indent_cle):
        corps, queue = _detacher_queue(brut_segment, indent_cle)
        if cle in CLES_EFFACEES:
            sortie.extend(queue)  # le segment part, ce qui le suivait reste
            continue
        if cle in ("kind", "effect", "notes"):
            vues.add(cle)
            if cle == "kind":
                sortie.append(f"{marge}kind: {r.kind}\n")
            elif cle == "effect":
                sortie.append(f"{marge}effect: info\n")
            else:
                sortie.extend(
                    _bloc_scalaire("notes", _notes_retypees(brut_cond, r, jour), indent_cle)
                )
            sortie.extend(queue)
            continue
        sortie.extend(corps)
        sortie.extend(queue)
    # Clés absentes du fichier (valeurs par défaut du schéma) : le retypage les
    # rend explicites, sinon l'invariant verrait la différence et refuserait.
    # Elles s'insèrent AVANT la queue du dernier segment, qui annonce la suite.
    ajouts: list[str] = []
    if "kind" not in vues:
        ajouts.append(f"{marge}kind: {r.kind}\n")
    if "effect" not in vues:
        ajouts.append(f"{marge}effect: info\n")
    if "notes" not in vues:
        ajouts.extend(_bloc_scalaire("notes", _notes_retypees(brut_cond, r, jour), indent_cle))
    if ajouts and queue and sortie[-len(queue) :] == queue:
        sortie[len(sortie) - len(queue) : len(sortie)] = ajouts + queue
    else:
        sortie.extend(ajouts)
    return lignes[:debut] + sortie + lignes[fin:]


def _reecrire_textuellement(
    texte: str, cibles: list[dict], par_cle: dict[str, Retypage], jour: date
) -> str | None:
    """Le fichier avec les seuls blocs visés retypés. None si l'un échappe."""
    lignes = texte.splitlines(keepends=True)
    for brut_cond in cibles:
        rendu = _reecrire_condition(lignes, brut_cond, par_cle[brut_cond["fact"]], jour)
        if rendu is None:
            return None
        lignes = rendu
    return "".join(lignes)


def appliquer(
    retypages: list[Retypage],
    *,
    aides_dir: Path = AIDES_DIR,
    pending_path: Path = FACTS_PENDING_FILE,
    facts_path: Path = FACTS_FILE,
    jour: date | None = None,
    ecrire: bool = False,
) -> Rapport:
    """Applique (ou simule) la table. N'écrit RIEN si la vérification échoue."""
    jour = jour or date.today()
    load_facts.cache_clear()
    load_pending_facts.cache_clear()
    facts = load_facts(facts_path)
    pending = load_pending_facts(pending_path)
    rapport = Rapport(erreurs=verifier(retypages, facts, pending, aides_dir=aides_dir))
    if not rapport.ok:
        return rapport

    par_cle = {r.fait: r for r in retypages}
    nouveaux: dict[Path, str] = {}
    for chemin in sorted(aides_dir.glob("*.yaml")):
        texte = chemin.read_text(encoding="utf-8")
        brut = yaml.safe_load(texte)
        conditions = brut.get("conditions") or []
        cibles = [c for c in conditions if (c.get("fact") or "") in par_cle]
        if not cibles:
            continue
        attendu = {
            **brut,
            "conditions": [
                _retyper_condition(c, par_cle[c["fact"]], jour)
                if (c.get("fact") or "") in par_cle
                else c
                for c in conditions
            ],
        }
        try:
            Aide.model_validate(attendu)
        except Exception as exc:  # noqa: BLE001
            rapport.erreurs.append(f"{chemin.stem} : le retypage produit un YAML invalide — {exc}")
            continue
        if _round_trip_stable(chemin):
            contenu = yaml.safe_dump(attendu, allow_unicode=True, sort_keys=False, width=100)
        else:
            # Fichier annoté : on ne touche que les blocs visés, et on vérifie
            # que le fichier rendu charge EXACTEMENT le retypage attendu — un
            # découpage qui aurait mordu sur un voisin se voit ici, avant
            # l'écriture, et le fichier entier est refusé plutôt que réparé.
            contenu = _reecrire_textuellement(texte, cibles, par_cle, jour)
            if contenu is None or yaml.safe_load(contenu) != attendu:
                rapport.erreurs.append(
                    f"{chemin.stem} : la réécriture textuelle ne rend pas le retypage attendu. "
                    f"Conditions visées : {', '.join(c['id'] for c in cibles)}. "
                    "À retyper à la main."
                )
                continue
        nouveaux[chemin] = contenu
        for cond in cibles:
            rapport.retypages.setdefault(cond["fact"], []).append(f"{chemin.stem}/{cond['id']}")
        rapport.fichiers_touches.append(chemin.stem)
    if not rapport.ok:
        return rapport

    # Chaque fait part de SON fichier : `facts_pending.yaml` par défaut,
    # `facts.yaml` pour ceux dont la table porte la décision de retrait.
    ontologies = {
        pending_path: (pending, [r.fait for r in retypages if not r.approuve]),
        facts_path: (facts, [r.fait for r in retypages if r.approuve]),
    }
    textes: dict[Path, str] = {}
    for chemin, (avant, cles) in ontologies.items():
        if not cles:
            continue
        texte_ontologie, erreurs = _retirer_faits(chemin, cles, set(avant))
        rapport.erreurs.extend(erreurs)
        if not erreurs:
            textes[chemin] = texte_ontologie
            rapport.retires.extend(cles)
    if not rapport.ok:
        return rapport

    if ecrire:
        for chemin, contenu in nouveaux.items():
            chemin.write_text(contenu, encoding="utf-8")
        for chemin, contenu in textes.items():
            chemin.write_text(
                (contenu.rstrip("\n") + "\n") if contenu.strip() else "", encoding="utf-8"
            )
    return rapport


def _retirer_faits(chemin: Path, cles: list[str], avant: set[str]) -> tuple[str, list[str]]:
    """Retire des blocs de faits d'un fichier d'ontologie, TEXTUELLEMENT.

    Découpage textuel et jamais `safe_load` puis `safe_dump` : `facts.yaml`
    porte en tête la table des fusions et, bloc par bloc, les justifications que
    la relecture humaine a arbitrées — un dump les effacerait toutes.

    Le même invariant que `fusionner_faits` clôt l'affaire : le fichier réécrit
    porte exactement les faits d'avant, moins ceux qu'on retire. Un découpage
    qui aurait mordu sur un voisin se voit ici, avant l'écriture.
    """
    texte = chemin.read_text(encoding="utf-8")
    erreurs: list[str] = []
    for cle in cles:
        bornes = _decouper_bloc(texte, cle)
        if bornes is None:
            erreurs.append(f"« {cle} » introuvable en tête de ligne dans {chemin.name}")
            continue
        debut, fin = bornes
        lignes = texte.splitlines(keepends=True)
        texte = "".join(lignes[:debut] + lignes[fin:])
    if erreurs:
        return texte, erreurs

    attendu = avant - set(cles)
    obtenu = set(yaml.safe_load(texte) or {})
    if obtenu != attendu:
        erreurs.append(
            f"{chemin.name} : le retrait aurait emporté d'autres faits (perdus : "
            f"{sorted(attendu - obtenu) or 'aucun'}, "
            f"en trop : {sorted(obtenu - attendu) or 'aucun'})"
        )
    return texte, erreurs


# ---------------------------------------------------------------------------
# Retrait des orphelins
# ---------------------------------------------------------------------------


def orphelins(pending: dict, *, aides_dir: Path = AIDES_DIR) -> list[str]:
    """Les faits proposés qu'aucune aide du catalogue ne référence.

    37 dans le lot du 2026-09-18 : l'agent a changé d'avis et laissé le
    brouillon derrière lui. Ils ne posent de question à personne — ils
    encombrent la relecture.
    """
    from lint_aides_data import faits_references_dans

    return sorted(set(pending) - faits_references_dans(aides_dir))


def retirer_orphelins(
    *,
    aides_dir: Path = AIDES_DIR,
    pending_path: Path = FACTS_PENDING_FILE,
    facts_path: Path = FACTS_FILE,
    jour: date | None = None,
    ecrire: bool = False,
) -> Rapport:
    """Retire les orphelins. Aucune condition n'est touchée — il n'y en a aucune."""
    load_pending_facts.cache_clear()
    pending = load_pending_facts(pending_path)
    cles = orphelins(pending, aides_dir=aides_dir)
    if not cles:
        return Rapport()
    table = [Retypage(fait=c, motif="Orphelin : aucune aide ne le référence.") for c in cles]
    return appliquer(
        table,
        aides_dir=aides_dir,
        pending_path=pending_path,
        facts_path=facts_path,
        jour=jour,
        ecrire=ecrire,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="retyper_faits.py",
        description="Retype les conditions qui citent un fait, puis retire le fait.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("table", type=Path, nargs="?", help="table de retypage YAML")
    ap.add_argument(
        "--s-engage",
        action="store_true",
        help="table implicite : tous les `s_engage_*` de facts_pending.yaml "
        "(retirer à la main ceux qui portent une contrainte durable)",
    )
    ap.add_argument(
        "--retirer-orphelins",
        action="store_true",
        help="table implicite : les faits proposés qu'aucune aide ne référence",
    )
    ap.add_argument("--dry-run", action="store_true", help="afficher sans rien écrire")
    ap.add_argument(
        "--sans-lint", action="store_true", help="ne pas rejouer le lint après écriture"
    )
    args = ap.parse_args(argv)

    modes = sum(bool(x) for x in (args.table, args.s_engage, args.retirer_orphelins))
    if modes != 1:
        ap.error("donner une table, ou --s-engage, ou --retirer-orphelins — un seul des trois")

    if args.retirer_orphelins:
        rapport = retirer_orphelins(ecrire=not args.dry_run)
        print(f"{len(rapport.retires)} orphelin(s)")
        print(rapport.texte())
    else:
        if args.s_engage:
            load_pending_facts.cache_clear()
            retypages = table_des_engagements(load_pending_facts())
            erreurs: list[str] = []
            print(f"{len(retypages)} fait(s) `{PREFIXE_ENGAGEMENT}*` dans facts_pending.yaml")
            print("  ⚠ Relire la liste : un engagement qui porte une contrainte DURABLE")
            print("    (conservation 15 ans, ouverture au public) mérite de rester un fait,")
            print("    de préférence en integer `duree_*_ans`. Le script ne les distingue pas.")
        else:
            retypages, erreurs = charger_table(args.table)
        if erreurs:
            for e in erreurs:
                print(f"ERREUR : {e}")
            return 2
        rapport = appliquer(retypages, ecrire=not args.dry_run)
        print(rapport.texte())

    if not rapport.ok:
        print("\nRien n'a été écrit.")
        return 1
    if args.dry_run:
        print("\n--dry-run : rien n'a été écrit.")
        return 0

    if args.sans_lint:
        return 0
    print("\nLint du catalogue après retypage :")
    resultat = lint()
    for e in resultat.erreurs[:20]:
        print(f"  {e}")
    print("  ✓ lint OK" if resultat.ok else f"  ✗ {len(resultat.erreurs)} erreur(s)")
    return 0 if resultat.ok else 1


if __name__ == "__main__":
    sys.exit(main())
