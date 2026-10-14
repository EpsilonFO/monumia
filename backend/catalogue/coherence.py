"""Cohérence du typage : les conditions qui posent la même exigence, et leurs typages qui divergent.

Commande, depuis backend/ :

    uv run --no-sync python -m catalogue.coherence
    uv run --no-sync python -m catalogue.coherence --sans-jev   # paires et plongements seuls

La même exigence (« les travaux ne doivent pas avoir commencé au dépôt »,
« le bien doit être inscrit ou classé ») revient dans des dizaines d'aides, et
chaque ingestion l'a typée pour son compte : `user_fact` sur un fait, sur un
autre, `manual_check`, `info`. Le diagnostic en dépend : une exigence typée
`info` n'écarte personne. Ce module retrouve ces familles et les met devant
Félix, une case par famille ; il ne modifie RIEN dans `data/aides/`.

Trois étages, chacun à sa place :

1. Plongements (rôle `plongement` du registre) : chaque condition est comparée
   à toutes les autres, sur son seul `text`, sans consigne (mesuré : avec la
   consigne de Qwen3, les cosinus se tassent entre 0,86 et 0,94 et aucun seuil
   ne sépare plus rien). Les paires d'aides différentes au-dessus de `--seuil`
   sont candidates. L'embedding ne fait que proposer.
2. Jev (rôle `decision`) juge chaque paire candidate : même critère, même thème
   mais autre critère, ou sans rapport. Il lit les textes, ce que l'embedding
   ne fait pas. Le seuil `SEUIL_MEME` se règle sur un échantillon étiqueté.
3. Le code compare chaque condition à ses voisins DIRECTS confirmés par Jev :
   quand leur typage dominant n'est pas le sien, elle est signalée. Les
   signalements sont groupés par transition (« typée X, ses voisins disent
   Y ») et classés par impact ; c'est sur ces groupes que porte l'arbitrage.

Pourquoi des voisins directs et pas des familles : les composantes connexes
des paires « même critère » ont formé deux familles de 1 943 et 1 595
conditions (2026-10-14), parce qu'une condition composite (« le demandeur doit
être une commune… et le projet dépasser 10 000 € ») relie deux critères, et que
Jev est généreux (médiane 0,79). Même à 0,95 une famille garde 421 membres ; une
liaison moyenne, à l'inverse, éclate un critère en centaines de petites
familles. Le voisinage direct ne chaîne pas, et c'est le contrôle même qui
tournera à l'ingestion : ce qu'on valide sur le stock est ce qu'on branchera.

La majorité des voisins ne DÉCIDE rien : elle signale. La doctrine a changé le
2026-09-21 et la majorité peut être l'ancienne ; chaque groupe se tranche dans
un sens, dans l'autre, ou pas du tout.

Pourquoi « même critère » et non « même exigence » : le typage (`kind`, `fact`)
dit CE QUI est vérifié, le prédicat dit la valeur. « doit être classé » et « ne
doit pas être protégé » portent sur le même fait et doivent avoir le même
`kind` ; seul le prédicat diffère. La négation, que l'embedding confond, ne
change donc rien ici. Elle compte en revanche pour fusionner deux FAITS, d'où
le refus des polarités opposées dans `fusionner_faits.py`.

Les jugements de Jev sont gardés par empreinte des questions, du modèle et des
deux textes, dans `data/catalogue/coherence/jugements.jsonl`, suivi par git et
en ajout seul : ses probabilités varient d'un appel à l'autre (jusqu'à 0,08), et
un jugement déjà rendu est repris plutôt que rejugé, comme dans le journal du
catalogue. Sans cela, un écart signalé une semaine disparaîtrait la suivante
sans que rien n'ait changé.

Sorties :
  - `data/reviews/<date>-coherence-conditions.md` : la fiche, une case par
    groupe de signalements, les plus graves d'abord, et les faits qui se
    recouvrent ;
  - `data/coherence/<date>-ecarts.yaml` : les mêmes groupes en table, avec un
    champ `retenu` vide que l'arbitrage remplit ; les propositions de
    `data/coherence/propositions.yaml` (clé : les deux typages) y sont reportées ;
  - `data/reviews/logs/refonte/<date>-coherence-<n>/` (hors git) : paires,
    jugements, échantillon d'étiquetage.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from aides_schema import AIDES_DIR, Condition, load_all_aides
from catalogue import registre as registre_mod
from catalogue.journal import cle as cle_decision
from catalogue.journal import empreinte
from catalogue.openrouter import Client, Panne, choix
from catalogue.plongements import Plongeur, plus_proches

BACKEND = Path(__file__).resolve().parents[1]
REVIEWS = BACKEND / "data" / "reviews"
TABLES = BACKEND / "data" / "coherence"
LOGS = REVIEWS / "logs" / "refonte"
JUGEMENTS = BACKEND / "data" / "catalogue" / "coherence" / "jugements.jsonl"
PROPOSITIONS = TABLES / "propositions.yaml"

SEUIL_COSINUS = 0.75
VOISINS = 15
#: Probabilité de « même critère » au-dessus de laquelle deux conditions sont
#: voisines. Mesurée le 2026-10-14 sur 180 paires étiquetées à l'aveugle
#: (`data/reviews/2026-10-14-coherence-conditions.md`) : précision 97 à 100 %,
#: rappel 56 à 62 % des paires « même critère ». À 0,9 la précision ne gagne
#: rien et le rappel tombe à 43-48 % ; entre 0,5 et 0,8, 70 à 77 % seulement
#: des paires sont « même critère ».
SEUIL_MEME = 0.8
#: La mesure qui fonde `SEUIL_MEME`, recopiée dans chaque fiche.
MESURE_SEUIL = [
    "Mesuré le 2026-10-14 sur 180 paires candidates tirées en six tranches de "
    "probabilité « même critère » (30 par tranche, graine 20261014), étiquetées à "
    "l'aveugle par deux sous-agents Claude (accord 166/180). Sorties dans "
    "`data/reviews/logs/refonte/2026-10-14-coherence-1/` (hors git).",
    "",
    "| Tranche Jev | Paires du stock | « Même critère » (deux juges / au moins un) |",
    "|---|---|---|",
    "| 0 à 0,5 | 7 901 | 15 / 23 sur 30 |",
    "| 0,5 à 0,8 | 6 465 | 21 / 23 sur 30 |",
    "| 0,8 à 0,9 | 3 435 | 26 / 30 sur 30 |",
    "| 0,9 à 0,95 | 2 683 | 30 sur 30 |",
    "| 0,95 à 0,98 | 2 869 | 30 sur 30 |",
    "| 0,98 à 1 | 5 205 | 30 sur 30 |",
    "",
    "Pondéré par la taille des tranches, le seuil de 0,8 garde des paires à 97-100 % "
    "« même critère » et en retrouve 56 à 62 % ; 0,9 n'améliore pas la précision et ne "
    "retrouve que 43 à 48 %. Jev est sous-confiant, comme le dit `docs/jev.md` : l'audit "
    "manque donc des écarts, mais ceux qu'il signale reposent sur des voisines sûres. "
    "Limite : les deux juges sont du même modèle, leurs erreurs communes ne se voient pas.",
]
#: Un signalement demande au moins ce nombre de voisins confirmés…
MIN_VOISINS = 3
#: … et un typage dominant qui pèse au moins cette part des voisins (pondérée
#: par la probabilité de Jev).
PART_DOMINANTE = 0.6
PARALLELISME_JEV = 8
TAILLE_CITATION = 600

MEME = "meme_critere"
VOISIN = "meme_theme"
AUTRE = "sans_rapport"

QUESTIONS: dict[str, Any] = {
    "relation": choix(
        "A et B sont deux conditions tirées des règlements de deux aides au patrimoine "
        "différentes. Vérifient-elles la même chose chez le demandeur, son bien ou son "
        "projet, de sorte qu'un questionnaire d'éligibilité devrait les traiter avec la "
        "même question ? Les valeurs exigées peuvent différer (seuils, listes, dates, "
        "territoires), et l'une peut être une exclusion quand l'autre est une exigence.",
        {
            MEME: (
                "Même critère : elles portent sur la même information (le statut "
                "juridique du demandeur, la protection monument historique du bien, le "
                "non-commencement des travaux au dépôt, la population de la commune, le "
                "montant minimal des travaux…), ou énoncent la même règle de procédure "
                "ou la même réserve du financeur."
            ),
            VOISIN: (
                "Même thème, critère différent : elles parlent du même sujet mais ne "
                "vérifient pas la même chose (un plancher de dépenses et un plafond "
                "d'aide, l'âge du bâtiment et sa protection, une exigence et une "
                "modalité de calcul ou de versement)."
            ),
            AUTRE: "Sans rapport : elles se ressemblent par les mots sans parler de la même chose.",
        },
    )
}
EMPREINTE_QUESTIONS = empreinte(json.dumps(QUESTIONS, ensure_ascii=False, sort_keys=True))


# --------------------------------------------------------------------------
# Conditions et typage
# --------------------------------------------------------------------------


Typage = tuple[str, str, str | None]


@dataclass(frozen=True)
class Ligne:
    slug: str
    nom: str
    condition: Condition
    #: Les champs lus que les `hard_filters` de l'aide tranchent déjà.
    couverts: frozenset[str] = frozenset()
    #: Les typages qui pèsent, portés par les AUTRES conditions de la même aide.
    ailleurs: frozenset[Typage] = frozenset()
    #: La place de la condition dans son aide : avec le slug, l'ordre canonique
    #: d'une paire (`paire`), donc la clé sous laquelle Jev l'a jugée.
    rang: int = 0

    @property
    def ref(self) -> str:
        return f"{self.slug}#{self.condition.id}"

    @property
    def texte(self) -> str:
        return " ".join(self.condition.text.split())

    @property
    def typage(self) -> tuple[str, str, str | None]:
        """Ce qui doit être le même dans une famille : le kind, l'effect, et ce qui est lu."""
        c = self.condition
        return (c.kind, c.effect, c.fact or c.field)


def libelle(typage: tuple[str, str, str | None]) -> str:
    kind, effect, cible = typage
    return f"{kind}/{effect}" + (f"/{cible}" if cible else "")


def pese(typage: Typage) -> bool:
    """La condition peut-elle écarter une aide ou en changer le taux ?"""
    kind, effect, _ = typage
    return effect != "info" and kind in ("user_fact", "auto")


#: Champ lu par une condition `auto` → clés de `hard_filters` qui le tranchent.
#: Une condition `info` sur une exigence que ces filtres portent déjà est
#: correcte (TYPING.md : « Couvert par hard_filters ») : elle ne se compare pas
#: comme une exigence oubliée.
CHAMPS_FILTRES: dict[str, tuple[str, ...]] = {
    "monument.protection": ("protections",),
    "monument.proprietaire": ("proprietaires",),
    "monument.region": ("regions", "departements"),
    "monument.departement_num": ("departements",),
    "commune.population": ("commune_max_population",),
}


def _couverts(filtres: Any) -> frozenset[str]:
    return frozenset(
        champ for champ, cles in CHAMPS_FILTRES.items() if any(getattr(filtres, c) for c in cles)
    )


def charger() -> list[Ligne]:
    lignes = []
    for slug, aide in load_all_aides(AIDES_DIR).items():
        couverts = _couverts(aide.hard_filters)
        typages = [(c.kind, c.effect, c.fact or c.field) for c in aide.conditions]
        for k, c in enumerate(aide.conditions):
            ailleurs = frozenset(t for m, t in enumerate(typages) if m != k and pese(t))
            lignes.append(Ligne(slug, aide.nom, c, couverts, ailleurs, k))
    return lignes


def lignes_de(slug: str, aide: Any) -> list[Ligne]:
    """Les lignes d'une seule aide (validée), comme `charger` les construit."""
    couverts = _couverts(aide.hard_filters)
    typages = [(c.kind, c.effect, c.fact or c.field) for c in aide.conditions]
    return [
        Ligne(
            slug,
            aide.nom,
            c,
            couverts,
            frozenset(t for m, t in enumerate(typages) if m != k and pese(t)),
            k,
        )
        for k, c in enumerate(aide.conditions)
    ]


def paire(a: Ligne, b: Ligne) -> tuple[Ligne, Ligne]:
    """L'ordre canonique d'une paire : celui de l'audit (slug, puis place dans l'aide).

    L'état soumis à Jev en dépend, donc la clé de son jugement : sans un ordre
    fixe, la même paire vue depuis l'autre condition serait rejugée.
    """
    return (a, b) if (a.slug, a.rang) <= (b.slug, b.rang) else (b, a)


def concorde(ligne: Ligne, typage: Typage) -> bool:
    """La condition est-elle typée `typage`, ou l'exigence est-elle déjà portée ailleurs ?

    Une condition qui ne pèse pas est cohérente avec un typage qui pèse quand son
    aide le porte déjà : par ses `hard_filters` (TYPING.md : « Couvert par
    hard_filters ») ou par une autre de ses conditions (un règlement qui répète
    ses bénéficiaires). L'exigence n'est pas oubliée, elle n'est pas posée deux
    fois.
    """
    if ligne.typage == typage:
        return True
    if pese(ligne.typage) or not pese(typage):
        return False
    kind, effect, cible = typage
    couvert = kind == "auto" and effect == "gate" and cible in ligne.couverts
    return couvert or typage in ligne.ailleurs


# --------------------------------------------------------------------------
# Paires candidates
# --------------------------------------------------------------------------


def paires_candidates(
    lignes: list[Ligne], plongeur: Plongeur, seuil: float, voisins: int
) -> dict[tuple[int, int], float]:
    """Les paires de conditions d'aides différentes dont le cosinus atteint `seuil`."""
    vecteurs = plongeur.vecteurs([ln.texte for ln in lignes])
    rangs, scores = plus_proches(vecteurs, vecteurs, voisins + 1)
    paires: dict[tuple[int, int], float] = {}
    for i in range(len(lignes)):
        for j, s in zip(rangs[i], scores[i], strict=True):
            j = int(j)
            if s < seuil or lignes[j].slug == lignes[i].slug:
                continue
            paires[(min(i, j), max(i, j))] = round(float(s), 4)
    return paires


# --------------------------------------------------------------------------
# Jugement de Jev
# --------------------------------------------------------------------------


def _etat(a: Ligne, b: Ligne) -> dict[str, Any]:
    def un(ln: Ligne) -> dict[str, str]:
        sortie = {"aide": ln.nom, "condition": ln.texte}
        if ln.condition.quote:
            sortie["citation"] = " ".join(ln.condition.quote.split())[:TAILLE_CITATION]
        return sortie

    return {"A": un(a), "B": un(b)}


class Juge:
    """Jev sur des états, chaque jugement gardé une fois pour toutes.

    Une ligne par jugement dans `fichier` : `{"k": empreinte, "p": distribution}`.
    L'empreinte couvre les questions, le modèle et l'état : changer une
    consigne ou de modèle rejuge, rien d'autre. Écriture en ajout seul, sous
    verrou de fichier (l'agent d'ingestion et le run peuvent écrire tour à
    tour). Une panne ne s'écrit jamais : elle rend `None`, et le passage
    suivant rejuge.
    """

    def __init__(self, fichier: Path = JUGEMENTS, client: Client | None = None) -> None:
        reg = registre_mod.charger()
        self.modele = reg.modele("decision")
        self.fichier = fichier
        self._verrou = threading.Lock()
        self._client = client
        self.connus: dict[str, dict[str, float]] = {}
        self.cout_usd = 0.0
        self.appels = 0
        self.pannes: Counter[str] = Counter()
        if fichier.exists():
            for ligne in fichier.read_text(encoding="utf-8").splitlines():
                if ligne.strip():
                    d = json.loads(ligne)
                    self.connus[d["k"]] = d["p"]

    def cle(self, etat: dict[str, Any], questions: dict[str, Any] | None = None) -> str:
        empreinte_q = (
            EMPREINTE_QUESTIONS
            if questions is None
            else empreinte(json.dumps(questions, ensure_ascii=False, sort_keys=True))
        )
        return cle_decision(empreinte_q, self.modele.nom, etat)

    def juger(
        self,
        etat: dict[str, Any],
        questions: dict[str, Any] | None = None,
        question: str = "relation",
    ) -> dict[str, float] | None:
        """La distribution de `question`, ou None si Jev est en panne (rien n'est gardé)."""
        cle = self.cle(etat, questions)
        if cle in self.connus:
            return self.connus[cle]
        if self._client is None:
            with self._verrou:
                if self._client is None:
                    self._client = Client()
        try:
            decision = self._client.decider(
                self.modele.nom,
                etat,
                questions or QUESTIONS,
                acceptes=self.modele.acceptes,
                delai_s=self.modele.delai_s,
                role="coherence",
            )
        except Panne as exc:
            with self._verrou:
                self.pannes[exc.classe] += 1
            return None
        probabilites = {k: round(v, 4) for k, v in decision.avis[question].probabilites.items()}
        with self._verrou:
            self.appels += 1
            self.cout_usd += decision.cout_usd or 0.0
            self.connus[cle] = probabilites
            self._ajouter({"k": cle, "p": probabilites})
        return probabilites

    def _ajouter(self, ligne: dict[str, Any]) -> None:
        self.fichier.parent.mkdir(parents=True, exist_ok=True)
        with self.fichier.open("a", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.write(json.dumps(ligne, ensure_ascii=False, separators=(",", ":")) + "\n")
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def fermer(self) -> None:
        if self._client is not None:
            self._client.fermer()


def juger_paires(
    lignes: list[Ligne], paires: dict[tuple[int, int], float], juge: Juge
) -> dict[tuple[int, int], dict[str, float]]:
    jugements: dict[tuple[int, int], dict[str, float]] = {}
    with ThreadPoolExecutor(PARALLELISME_JEV) as pool:
        futurs = {pool.submit(juge.juger, _etat(lignes[i], lignes[j])): (i, j) for i, j in paires}
        for n, futur in enumerate(as_completed(futurs), 1):
            probabilites = futur.result()
            if probabilites is not None:
                jugements[futurs[futur]] = probabilites
            if n % 1000 == 0 and juge.appels:
                print(
                    f"  {n}/{len(paires)} paires jugées, {juge.appels} appels, {juge.cout_usd:.3f} $"
                )
    return jugements


# --------------------------------------------------------------------------
# Écarts au voisinage
# --------------------------------------------------------------------------

IMPACTS = {
    "elimination": "l'un des deux typages peut écarter l'aide, l'autre n'écarte personne",
    "fait": "le même critère est lu sur des faits ou des champs différents",
    "modulation": "même lecture, rôle différent (gate, modulateur)",
    "affichage": "aucun ne pèse sur le diagnostic, seul l'affichage diffère",
}
ORDRE_IMPACT = list(IMPACTS)


def impact(typages: Counter[Typage]) -> str:
    pesent = {t for t in typages if pese(t)}
    if pesent and any(not pese(t) for t in typages):
        return "elimination"
    if len({t[2] for t in typages if t[2]}) > 1:
        return "fait"
    if not pesent:
        return "affichage"
    return "modulation"


def voisinage(
    n: int, jugements: dict[tuple[int, int], dict[str, float]], seuil: float
) -> list[dict[int, float]]:
    """Pour chaque condition, ses voisins confirmés et la probabilité « même critère »."""
    voisins: list[dict[int, float]] = [{} for _ in range(n)]
    for (i, j), d in jugements.items():
        p = d.get(MEME, 0.0)
        if p >= seuil:
            voisins[i][j] = p
            voisins[j][i] = p
    return voisins


@dataclass
class Signalement:
    indice: int
    attendu: Typage
    part: float
    voisins: list[int]
    #: Le prédicat le plus fréquent chez les voisins au typage attendu, et sa part.
    predicat: Any = None
    part_predicat: float = 0.0


def _predicat(c: Condition) -> str | None:
    return json.dumps(c.predicate.root, ensure_ascii=False, sort_keys=True) if c.predicate else None


@dataclass(frozen=True)
class Dominante:
    """Le typage que portent les voisines confirmées d'une condition."""

    attendu: Typage
    part: float
    porteurs: list[Ligne]
    predicat: Any
    part_predicat: float


def dominante(
    ligne: Ligne,
    autour: list[tuple[Ligne, float]],
    min_voisins: int = MIN_VOISINS,
    part_dominante: float = PART_DOMINANTE,
) -> Dominante | None:
    """Le typage dominant des voisines confirmées (pondéré par Jev), s'il est net.

    Une voisine couverte par ses filtres compte pour le typage `auto` qu'ils
    valent, quand c'est celui de la condition examinée.
    """
    if len(autour) < min_voisins:
        return None
    poids: Counter[Typage] = Counter()
    for voisine, p in autour:
        t = ligne.typage if concorde(voisine, ligne.typage) else voisine.typage
        poids[t] += p
    attendu, w = poids.most_common(1)[0]
    part = w / sum(poids.values())
    if part < part_dominante:
        return None
    porteurs = [v for v, _p in autour if v.typage == attendu]
    predicat, n_pred = (
        Counter(_predicat(v.condition) for v in porteurs).most_common(1)[0]
        if porteurs
        else (None, 0)
    )
    return Dominante(
        attendu=attendu,
        part=round(part, 3),
        porteurs=porteurs,
        predicat=json.loads(predicat) if predicat else None,
        part_predicat=round(n_pred / len(porteurs), 3) if porteurs else 0.0,
    )


def signaler(
    lignes: list[Ligne],
    voisins: list[dict[int, float]],
    min_voisins: int = MIN_VOISINS,
    part_dominante: float = PART_DOMINANTE,
) -> list[Signalement]:
    """Les conditions dont le typage n'est pas celui, dominant, de leurs voisins confirmés."""
    sortie = []
    for i, autour in enumerate(voisins):
        d = dominante(
            lignes[i], [(lignes[j], p) for j, p in autour.items()], min_voisins, part_dominante
        )
        if d is None or concorde(lignes[i], d.attendu):
            continue
        sortie.append(
            Signalement(
                indice=i,
                attendu=d.attendu,
                part=d.part,
                voisins=sorted(autour, key=lambda j: -autour[j]),
                predicat=d.predicat,
                part_predicat=d.part_predicat,
            )
        )
    return sortie


@dataclass
class Groupe:
    """Les conditions d'un même désaccord entre deux typages, dans les deux sens.

    « typée X, voisines Y » et « typée Y, voisines X » sont une seule question :
    quel est le typage canonique de ce critère ? Les séparer ferait trancher
    deux fois la même chose, et possiblement dans deux sens contraires.
    """

    typages: tuple[Typage, Typage]
    signalements: list[Signalement] = field(default_factory=list)

    @property
    def impact(self) -> str:
        return impact(Counter(self.typages))

    def sens(self, lignes: list[Ligne], actuel: Typage) -> list[Signalement]:
        return sorted(
            (s for s in self.signalements if lignes[s.indice].typage == actuel),
            key=lambda s: -s.part,
        )


def grouper(lignes: list[Ligne], signalements: list[Signalement]) -> list[Groupe]:
    groupes: dict[tuple[Typage, Typage], Groupe] = {}
    for s in signalements:
        a, b = sorted((lignes[s.indice].typage, s.attendu), key=libelle)
        groupes.setdefault((a, b), Groupe((a, b))).signalements.append(s)
    return sorted(
        groupes.values(),
        key=lambda g: (ORDRE_IMPACT.index(g.impact), -len(g.signalements), libelle(g.typages[0])),
    )


def recouvrements(
    lignes: list[Ligne], voisins: list[dict[int, float]], minimum: int = 3
) -> list[tuple[str, str, int, list[tuple[int, int]]]]:
    """Les paires de faits (ou de champs) dont des conditions sont voisines confirmées.

    Deux faits qui portent souvent des conditions « même critère » sont
    candidats à la fusion, ou l'un des deux est mal choisi. La polarité n'est
    pas regardée : c'est à `fusionner_faits.py` de la refuser.
    """
    paires: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)
    for i, autour in enumerate(voisins):
        fi = lignes[i].typage[2]
        for j in autour:
            fj = lignes[j].typage[2]
            if i < j and fi and fj and fi != fj:
                paires[tuple(sorted((fi, fj)))].append((i, j))  # type: ignore[arg-type]
    return sorted(
        ((a, b, len(v), v) for (a, b), v in paires.items() if len(v) >= minimum),
        key=lambda x: -x[2],
    )


# --------------------------------------------------------------------------
# Sorties
# --------------------------------------------------------------------------


def _coupe(texte: str, n: int = 220) -> str:
    return texte if len(texte) <= n else texte[: n - 1].rstrip() + "…"


def _id_groupe(k: int) -> str:
    return f"G{k:03d}"


def cle_groupe(g: Groupe) -> str:
    """La clé d'un groupe dans `propositions.yaml` : stable d'une exécution à l'autre."""
    return " <> ".join(libelle(t) for t in g.typages)


def lire_propositions(chemin: Path = PROPOSITIONS) -> dict[str, dict[str, Any]]:
    if not chemin.exists():
        return {}
    return yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}


def ecrire_fiche(
    chemin: Path,
    lignes: list[Ligne],
    groupes: list[Groupe],
    faits: list[tuple[str, str, int, list[tuple[int, int]]]],
    meta: dict[str, Any],
    propositions: dict[str, dict[str, Any]],
) -> None:
    par_impact = Counter(g.impact for g in groupes)
    signales_par_impact: Counter[str] = Counter()
    for g in groupes:
        signales_par_impact[g.impact] += len(g.signalements)
    sortie = [
        f"# Cohérence du typage des conditions, {meta['date']}",
        "",
        "Conditions dont le typage (`kind`, `effect`, fait ou champ lu) n'est pas celui de "
        "leurs voisines : les conditions d'autres aides que Jev juge porter sur le même "
        "critère. Produit par `python -m catalogue.coherence`, qui ne modifie aucune aide.",
        "",
        "Ne sont pas signalées les conditions qui n'écartent personne quand leur aide porte "
        "déjà l'exigence ailleurs : par ses `hard_filters` (protection, propriétaire, "
        "région, département, population) ou par une autre de ses conditions.",
        "",
        "Comment arbitrer : un groupe réunit les deux sens d'un même désaccord, les "
        "conditions typées X entourées de Y et celles typées Y entourées de X. Dans "
        f"`{meta['table']}`, écrire pour chaque groupe `retenu` : l'un des deux typages "
        "(il devient celui de tous les membres), `laisser` (divergence voulue) ou "
        "`au_cas_par_cas`, avec `sauf: [refs]` pour exclure des membres. La majorité "
        "n'est qu'un repère : la doctrine a changé le 2026-09-21, et la majorité peut "
        "être l'ancienne.",
        "",
        "## Chiffres",
        "",
        f"- {meta['conditions']} conditions, {meta['aides']} aides.",
        f"- {meta['paires']} paires candidates (cosinus ≥ {meta['seuil_cosinus']}, "
        f"{meta['voisins']} voisins), {meta['jugees']} jugées par Jev, {meta['liens']} "
        f"confirmées (« même critère » ≥ {meta['seuil_meme']}).",
        f"- {meta['signalements']} conditions signalées (au moins {meta['min_voisins']} "
        f"voisines confirmées, typage dominant ≥ {meta['part_dominante']:.0%}), en "
        f"{len(groupes)} groupes : "
        + ", ".join(
            f"`{i}` {par_impact[i]} groupes / {signales_par_impact[i]} conditions"
            for i in ORDRE_IMPACT
        )
        + ".",
        f"- Coût de cette exécution : {meta['cout_jev']:.3f} $ de Jev ({meta['appels_jev']} "
        f"appels neufs, le reste repris du cache), {meta['cout_plongements']:.4f} $ de "
        "plongements. Premier jugement du stock complet : 1,04 $.",
        "",
        "Impacts :",
        "",
        *[f"- `{k}` : {v}." for k, v in IMPACTS.items()],
        "",
        "## Seuil de Jev",
        "",
        *MESURE_SEUIL,
        "",
        "## Groupes",
        "",
    ]
    for k, g in enumerate(groupes, 1):
        a, b = g.typages
        sortie += [
            f"### {_id_groupe(k)} · {g.impact} · `{libelle(a)}` ↔ `{libelle(b)}`, "
            f"{len(g.signalements)} conditions",
            "",
            "- [ ] retenu : …",
            "",
        ]
        proposition = propositions.get(cle_groupe(g))
        if proposition:
            predicat = proposition.get("predicat")
            sortie += [
                f"Proposition : `{proposition['proposition']}`"
                + (f", prédicat `{json.dumps(predicat, ensure_ascii=False)}`" if predicat else "")
                + f". {' '.join(str(proposition.get('motif', '')).split())}",
                "",
            ]
        for actuel, attendu in ((a, b), (b, a)):
            sens = g.sens(lignes, actuel)
            if not sens:
                continue
            sortie += [f"Typées `{libelle(actuel)}`, voisines `{libelle(attendu)}` :", ""]
            for s in sens:
                ln = lignes[s.indice]
                exemple = lignes[next(j for j in s.voisins if lignes[j].typage == attendu)]
                pred = (
                    f", prédicat voisin `{json.dumps(s.predicat, ensure_ascii=False)}` "
                    f"({s.part_predicat:.0%})"
                    if s.predicat
                    else ""
                )
                sortie += [
                    f"- {ln.ref} ({len(s.voisins)} voisines, {s.part:.0%} `{libelle(attendu)}`{pred})",
                    f"  - cette condition : {_coupe(ln.texte)}",
                    f"  - voisine ({exemple.ref}) : {_coupe(exemple.texte)}",
                ]
            sortie.append("")
    sortie += [
        "## Faits qui se recouvrent",
        "",
        "Paires de faits (ou de champs) dont les conditions sont souvent voisines « même "
        "critère ». Candidats à la fusion, ou l'un des deux est mal choisi. La polarité "
        "n'est pas vérifiée ici.",
        "",
        "| Fait A | Fait B | Paires voisines | Exemple A | Exemple B |",
        "|---|---|---|---|---|",
    ]
    for a, b, n, exemples in faits:
        i, j = exemples[0]
        x, y = (lignes[i], lignes[j]) if lignes[i].typage[2] == a else (lignes[j], lignes[i])
        sortie.append(f"| `{a}` | `{b}` | {n} | {_coupe(x.texte, 120)} | {_coupe(y.texte, 120)} |")
    sortie.append("")
    chemin.write_text("\n".join(sortie), encoding="utf-8")


def ecrire_table(
    chemin: Path,
    lignes: list[Ligne],
    groupes: list[Groupe],
    propositions: dict[str, dict[str, Any]],
) -> None:
    entete = (
        "# Écarts de typage au voisinage, produits par catalogue/coherence.py.\n"
        "# Arbitrage : `retenu` = l'un des deux `typages` (il devient celui de tous les\n"
        "# membres), `laisser` ou `au_cas_par_cas` ; `sauf` = refs exclues.\n"
        "# Rien n'est appliqué tant que le script d'application n'existe pas.\n"
    )
    corps = {
        "groupes": [
            {
                "id": _id_groupe(k),
                "impact": g.impact,
                "typages": [libelle(t) for t in g.typages],
                "proposition": (propositions.get(cle_groupe(g)) or {}).get("proposition"),
                "predicat_propose": (propositions.get(cle_groupe(g)) or {}).get("predicat"),
                "retenu": None,
                "sauf": [],
                "membres": [
                    {
                        "ref": lignes[s.indice].ref,
                        "actuel": libelle(lignes[s.indice].typage),
                        "part_voisines": s.part,
                        "voisines": [lignes[j].ref for j in s.voisins],
                        "predicat_voisin": s.predicat,
                        "part_predicat": s.part_predicat,
                    }
                    for actuel in g.typages
                    for s in g.sens(lignes, actuel)
                ],
            }
            for k, g in enumerate(groupes, 1)
        ]
    }
    chemin.write_text(
        entete + yaml.safe_dump(corps, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )


def _dossier_neuf(date: str) -> Path:
    n = 1
    while (LOGS / f"{date}-coherence-{n}").exists():
        n += 1
    dossier = LOGS / f"{date}-coherence-{n}"
    dossier.mkdir(parents=True)
    return dossier


def main() -> int:
    parseur = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parseur.add_argument("--seuil", type=float, default=SEUIL_COSINUS)
    parseur.add_argument("--voisins", type=int, default=VOISINS)
    parseur.add_argument("--seuil-meme", type=float, default=SEUIL_MEME)
    parseur.add_argument("--min-voisins", type=int, default=MIN_VOISINS)
    parseur.add_argument("--part-dominante", type=float, default=PART_DOMINANTE)
    parseur.add_argument("--sans-jev", action="store_true")
    args = parseur.parse_args()

    date = dt.date.today().isoformat()
    lignes = charger()
    print(f"{len(lignes)} conditions")
    plongeur = Plongeur()
    try:
        paires = paires_candidates(lignes, plongeur, args.seuil, args.voisins)
    finally:
        plongeur.fermer()
    print(f"{len(paires)} paires candidates")
    dossier = _dossier_neuf(date)
    with (dossier / "paires.jsonl").open("w", encoding="utf-8") as f:
        for (i, j), s in sorted(paires.items(), key=lambda x: -x[1]):
            ligne = {"a": lignes[i].ref, "b": lignes[j].ref, "cosinus": s}
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    if args.sans_jev:
        print(dossier)
        return 0

    juge = Juge()
    try:
        jugements = juger_paires(lignes, paires, juge)
    finally:
        juge.fermer()
    if juge.pannes:
        print(f"pannes de Jev : {dict(juge.pannes)} (paires laissées de côté, à rejouer)")
    with (dossier / "jugements.jsonl").open("w", encoding="utf-8") as f:
        for (i, j), d in jugements.items():
            ligne = {"a": lignes[i].ref, "b": lignes[j].ref, "cosinus": paires[(i, j)], "jev": d}
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")

    voisins = voisinage(len(lignes), jugements, args.seuil_meme)
    signalements = signaler(lignes, voisins, args.min_voisins, args.part_dominante)
    groupes = grouper(lignes, signalements)
    faits = recouvrements(lignes, voisins)

    TABLES.mkdir(parents=True, exist_ok=True)
    # Jamais d'écrasement : une table du jour peut porter l'arbitrage de Félix.
    suffixe, n = "", 1
    while (TABLES / f"{date}-ecarts{suffixe}.yaml").exists() or (
        REVIEWS / f"{date}-coherence-conditions{suffixe}.md"
    ).exists():
        n += 1
        suffixe = f"-{n}"
    table = TABLES / f"{date}-ecarts{suffixe}.yaml"
    fiche = REVIEWS / f"{date}-coherence-conditions{suffixe}.md"
    meta = {
        "date": date,
        "table": table.relative_to(BACKEND).as_posix(),
        "conditions": len(lignes),
        "aides": len({ln.slug for ln in lignes}),
        "paires": len(paires),
        "seuil_cosinus": args.seuil,
        "voisins": args.voisins,
        "jugees": len(jugements),
        "liens": sum(len(v) for v in voisins) // 2,
        "seuil_meme": args.seuil_meme,
        "min_voisins": args.min_voisins,
        "part_dominante": args.part_dominante,
        "signalements": len(signalements),
        "groupes": len(groupes),
        "cout_plongements": plongeur.cout_usd,
        "cout_jev": juge.cout_usd,
        "appels_jev": juge.appels,
        "empreinte_questions": EMPREINTE_QUESTIONS,
    }
    propositions = lire_propositions()
    ecrire_fiche(fiche, lignes, groupes, faits, meta, propositions)
    ecrire_table(table, lignes, groupes, propositions)
    (dossier / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(dossier)
    print(fiche)
    print(json.dumps({k: v for k, v in meta.items() if k != "table"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
