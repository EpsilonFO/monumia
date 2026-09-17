"""
Compare deux extractions d'une même aide — le banc d'essai des modèles.

    # une aide contre sa référence
    uv run python scripts/comparer_aides.py \\
        data/aides/hdf-jardins-en-scene.yaml /tmp/bench/glm/aides/hdf-jardins-en-scene.yaml \\
        --log /tmp/bench/glm/reviews/logs/ingest-hdf-jardins-en-scene.log \\
        --sources /tmp/bench/glm/sources/hdf-jardins-en-scene

    # la synthèse d'un banc d'essai complet, à coller dans la fiche de review
    uv run python scripts/comparer_aides.py tableau \\
        hdf-jardins-en-scene hdf-actes-fonds-appui-projets-locaux \\
        hdf-prit-patrimoine-decouverte \\
        --sortie /tmp/bench/glm-flash --sortie /tmp/bench/ds-flash --sortie /tmp/bench/ds-pro

La question à laquelle ce script répond n'est pas « les deux fichiers
diffèrent-ils » — ils diffèrent toujours — mais « le candidat a-t-il retrouvé
les mêmes EXIGENCES que la référence, et ne s'en est-il pas inventé ». D'où un
appariement des conditions qui ne se fie pas aux identifiants (un modèle nomme
`ouverture-publique` ce qu'un autre nomme `ouvert-au-public`) mais, dans
l'ordre : à l'identifiant, puis à la citation normalisée, puis au texte.

Les deux chiffres qui décident :

  - **rappel des exigences décisives** (`gate` + `modulateur`) : quelle part de
    ce qui pèse sur le diagnostic le candidat a-t-il retrouvé ? Une exigence
    manquée rend une aide éligible à quelqu'un qui ne l'est pas, ou lui promet
    un taux qu'il n'aura pas. Les conditions `effect: info` sont comptées à
    part : elles ne changent aucun résultat, elles nourrissent le dossier.
  - **précision des citations** : quelle part des citations du candidat se
    retrouve VRAIMENT dans les snapshots ? Une citation inventée est une faute
    de nature différente, et disqualifie un modèle même s'il a bon partout
    ailleurs.

Le reste (coût, tours, durée) départage à qualité comparable.
"""

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from veille_text import normalize

from aides_schema import Aide, Condition, load_aide

# En dessous, deux `text` ne décrivent pas la même exigence : mieux vaut deux
# conditions non appariées (visibles) qu'un appariement faux (invisible).
SEUIL_TEXTE = 0.7

# Deux modèles ne coupent pas leur citation aux mêmes bornes. La référence de
# `hdf-jardins-en-scene` finit sur « … EPCC communément appelé lieu
# intermédiaire », le candidat commence par « EPCC communément appelé lieu
# intermédiaire ou lieu de programmation en territoire » : ni égalité, ni
# inclusion, et l'appariement tombait — la même exigence DÉCISIVE comptée
# MANQUÉE et EN TROP à la fois (mesuré sur or-glm, 2026-09-06).
#
# Le test est géométrique, pas un seuil de similarité : deux citations sont
# deux FENÊTRES sur le même passage si l'une contient l'autre, ou si un suffixe
# de l'une est un préfixe de l'autre. Un bloc commun de 40 caractères qui tombe
# pile aux bornes des deux ne se produit pas par accident, là où un seuil de
# similarité assez bas pour rattraper ce cas apparierait n'importe quoi : sur
# cette paire, les vrais couples sont à 1,00 et les faux plafonnent à 0,51.
CHEVAUCHEMENT_MIN_CAR = 40

# Une exigence structurée peut légitimement vivre dans `hard_filters` plutôt
# que dans une condition typée — la doctrine le prescrit même. La référence de
# `hdf-jardins-en-scene` porte les deux et le DIT : la condition
# `projet-territoire-regional` a pour notes « Redondant avec
# hard_filters.regions — conservé pour l'affichage ». Un candidat qui ne garde
# que le filtre applique exactement la même restriction ; le compter manqué
# pénalise la doctrine.
FILTRE_POUR_CHAMP = {
    "monument.region": "regions",
    "monument.departement_num": "departements",
    "monument.proprietaire": "proprietaires",
    "monument.protection": "protections",
    "monument.etat_conservation": "etats_conservation",
}

# Une condition dont le `text` dépasse largement sa `quote` condense en général
# une LISTE (« Les propositions seront appréciées au regard des
# caractéristiques suivantes » suivi des onze critères repliés dedans). Le
# rappel des décisives devient alors un MINORANT, et il faut le dire : les
# exigences repliées sont bien absentes du diagnostic (une composite typée
# `info` ne pèse sur rien), mais elles ne sont pas invisibles à la relecture.
FACTEUR_COMPOSITE = 2.5
CAR_MIN_COMPOSITE = 200


# ---------------------------------------------------------------------------
# Appariement
# ---------------------------------------------------------------------------


def _recouvrement(gauche: str, droite: str) -> int:
    """Longueur du plus long suffixe de `gauche` qui soit un préfixe de `droite`."""
    for taille in range(min(len(gauche), len(droite)), CHEVAUCHEMENT_MIN_CAR - 1, -1):
        if gauche[-taille:] == droite[:taille]:
            return taille
    return 0


def meme_passage(a: str, b: str) -> bool:
    """Deux citations sont-elles deux fenêtres sur le même passage de la source ?

    Inclusion, ou chevauchement bord à bord (cf. `CHEVAUCHEMENT_MIN_CAR`).
    """
    x, y = normalize(a), normalize(b)
    if not x or not y or min(len(x), len(y)) < CHEVAUCHEMENT_MIN_CAR:
        return False
    if x in y or y in x:
        return True
    return bool(_recouvrement(x, y) or _recouvrement(y, x))


def apparier_conditions(
    reference: list[Condition], candidat: list[Condition]
) -> tuple[list[tuple[Condition, Condition]], list[Condition], list[Condition]]:
    """(paires, manquantes dans le candidat, en trop dans le candidat).

    Quatre passes, de la preuve la plus forte à la plus faible : identifiant
    identique, citation normalisée identique, citations qui sont deux fenêtres
    sur le même passage (cf. `meme_passage`), puis similarité du `text`.
    """
    restants = list(candidat)
    paires: list[tuple[Condition, Condition]] = []
    manquantes: list[Condition] = []

    def retirer(cond: Condition) -> None:
        restants.remove(cond)

    for ref in reference:
        trouve = next((c for c in restants if c.id == ref.id), None)
        if trouve is None and ref.quote:
            cible = normalize(ref.quote)
            trouve = next((c for c in restants if c.quote and normalize(c.quote) == cible), None)
        if trouve is None and ref.quote:
            trouve = next(
                (c for c in restants if c.quote and meme_passage(ref.quote, c.quote)),
                None,
            )
        if trouve is None:
            scores = [
                (SequenceMatcher(None, normalize(ref.text), normalize(c.text)).ratio(), i)
                for i, c in enumerate(restants)
            ]
            if scores:
                meilleur, index = max(scores)
                if meilleur >= SEUIL_TEXTE:
                    trouve = restants[index]
        if trouve is None:
            manquantes.append(ref)
        else:
            paires.append((ref, trouve))
            retirer(trouve)
    return paires, manquantes, restants


# ---------------------------------------------------------------------------
# Comparaison
# ---------------------------------------------------------------------------


@dataclass
class Divergence:
    condition: str
    champ: str
    reference: str
    candidat: str


@dataclass
class Comparaison:
    slug: str
    conditions_reference: int = 0
    conditions_candidat: int = 0
    communes: int = 0
    manquantes: list[str] = field(default_factory=list)
    en_trop: list[str] = field(default_factory=list)
    gates_reference: int = 0
    gates_retrouvees: int = 0
    # `gate` ET `modulateur` : tout ce qui pèse sur le résultat du diagnostic.
    # C'est ce rappel-là qui compte, pas celui des seuls gates — mesuré sur
    # hdf-jardins-en-scene, 3 gates pour 8 modulateurs : ne regarder que les
    # gates faisait lire « 0/3 » là où 6 exigences décisives sur 11 étaient
    # couvertes, et aurait disqualifié un modèle sur un chiffre faux.
    decisives_reference: int = 0
    decisives_retrouvees: int = 0
    # Exigences décisives que le candidat applique par un `hard_filters` au lieu
    # d'une condition typée : comptées RETROUVÉES (cf. `FILTRE_POUR_CHAMP`).
    couvertes_par_filtre: list[str] = field(default_factory=list)
    # Conditions du candidat qui condensent une liste (cf. `FACTEUR_COMPOSITE`) :
    # le rappel est un minorant quand il y en a.
    composites: list[str] = field(default_factory=list)
    divergences: list[Divergence] = field(default_factory=list)
    citations_candidat: int = 0
    citations_verifiees: int = 0
    champs_divergents: list[Divergence] = field(default_factory=list)
    # Vrai quand les `hard_filters` diffèrent : le rappel est alors à lire avec
    # prudence (cf. `avertissements`).
    filtres_divergents: bool = False

    @property
    def rappel_gates(self) -> float:
        return self.gates_retrouvees / self.gates_reference if self.gates_reference else 1.0

    @property
    def rappel_decisives(self) -> float:
        if not self.decisives_reference:
            return 1.0
        return self.decisives_retrouvees / self.decisives_reference

    @property
    def precision(self) -> float:
        """Part des conditions du candidat qui correspondent à la référence."""
        return self.communes / self.conditions_candidat if self.conditions_candidat else 0.0

    @property
    def quotes_ok(self) -> float:
        return (
            self.citations_verifiees / self.citations_candidat if self.citations_candidat else 0.0
        )

    @property
    def score(self) -> float:
        """Un seul nombre pour classer, dominé par le rappel des exigences décisives.

        Pondération assumée : rater une exigence qui pèse sur le diagnostic coûte
        plus cher que d'en ajouter une de trop (que la relecture humaine verra),
        et une citation inventée est une faute de nature — d'où son poids propre.
        """
        return round(
            100 * (0.5 * self.rappel_decisives + 0.25 * self.precision + 0.25 * self.quotes_ok), 1
        )

    def avertissements(self) -> list[str]:
        """Ce qui rend le score peu fiable sur cette paire — à lire avant de classer.

        Le comparateur apparie des CONDITIONS. Une exigence que le candidat a
        traitée dans `hard_filters` (ce que la doctrine prescrit pour un champ
        structuré : « un champ structuré relève de hard_filters ») n'y est donc
        pas créditée, et le rappel la compte comme manquée. Vu en vrai : un
        candidat qui posait `hard_filters.proprietaires` là où la référence
        posait un gate `user_fact` était pénalisé pour avoir eu raison.
        """
        avis: list[str] = []
        if self.filtres_divergents:
            avis.append(
                "les `hard_filters` diffèrent : une exigence traitée par un filtre "
                "structuré d'un côté et par une condition typée de l'autre est comptée "
                "MANQUÉE ici, sauf sur les dimensions connues de `FILTRE_POUR_CHAMP`. "
                "Relire les deux fichiers avant de conclure."
            )
        if self.composites:
            avis.append(
                f"{len(self.composites)} condition(s) du candidat condensent une liste "
                f"({', '.join(self.composites)}) : le rappel des décisives est un "
                "MINORANT. Les exigences repliées dedans sont bien inertes pour le "
                "diagnostic, mais elles sont citées et la relecture les voit."
            )
        if self.decisives_reference < 5:
            avis.append(
                f"seulement {self.decisives_reference} exigence(s) décisive(s) en "
                "référence : le rappel varie par paliers trop gros pour classer."
            )
        return avis


CHAMPS_AIDE = (
    "type",
    "categorie",
    # Le PÉRIMÈTRE de l'aide : sans lui, les conditions d'une aide d'un autre
    # métier polluent le questionnaire de tout le monde (cf. CLAUDE.md). Champ
    # le plus coûteux à rater, et il n'était pas comparé.
    "applies_if",
    "financement.taux_min",
    "financement.taux_max",
    "financement.montant_min",
    "financement.montant_max",
    "financement.plancher",
    "financement.assiette",
    "cumul.plafond_public_pct",
    "cumul.cumulable",
    "calendrier.permanent",
    "calendrier.date_ouverture",
    "calendrier.date_limite",
    "hard_filters.protections",
    "hard_filters.proprietaires",
    "hard_filters.regions",
    "hard_filters.departements",
)


def _lire(aide: Aide, chemin: str):
    valeur = aide
    for morceau in chemin.split("."):
        valeur = getattr(valeur, morceau)
    return valeur


def _couvert_par_filtre(ref: Condition, candidat: Aide) -> bool:
    """L'exigence de `ref` est-elle appliquée par un `hard_filters` du candidat ?

    Exige la MÊME valeur quand la condition de référence teste une égalité :
    un candidat qui filtrerait sur une autre région n'applique pas la même
    restriction, et le créditer masquerait une vraie erreur.
    """
    dimension = FILTRE_POUR_CHAMP.get(ref.field or "")
    if dimension is None:
        return False
    valeurs = getattr(candidat.hard_filters, dimension)
    if not valeurs:
        return False
    attendu = ref.predicate.root.get("eq") if ref.predicate else None
    return attendu is None or attendu in valeurs


def comparer(reference: Aide, candidat: Aide, documents=None) -> Comparaison:
    """Compare deux extractions. `documents` (snapshots) active l'audit des citations."""
    paires, manquantes, en_trop = apparier_conditions(reference.conditions, candidat.conditions)

    # Créditées AVANT de rendre les manquantes : une exigence appliquée par un
    # filtre structuré n'est pas manquée, elle est ailleurs.
    par_filtre = {c.id for c in manquantes if _couvert_par_filtre(c, candidat)}
    manquantes = [c for c in manquantes if c.id not in par_filtre]

    comp = Comparaison(
        slug=reference.slug,
        conditions_reference=len(reference.conditions),
        conditions_candidat=len(candidat.conditions),
        communes=len(paires),
        manquantes=[f"{c.id} [{c.kind}/{c.effect}]" for c in manquantes],
        en_trop=[f"{c.id} [{c.kind}/{c.effect}]" for c in en_trop],
        couvertes_par_filtre=sorted(par_filtre),
        composites=[
            c.id
            for c in candidat.conditions
            if len(c.text) >= CAR_MIN_COMPOSITE
            and len(c.text) >= FACTEUR_COMPOSITE * len(c.quote or "")
        ],
    )

    gates_ref = {c.id for c in reference.conditions if c.effect == "gate"}
    comp.gates_reference = len(gates_ref)
    comp.gates_retrouvees = sum(1 for ref, _cand in paires if ref.id in gates_ref) + sum(
        1 for i in par_filtre if i in gates_ref
    )
    decisives = {c.id for c in reference.conditions if c.effect in ("gate", "modulateur")}
    comp.decisives_reference = len(decisives)
    comp.decisives_retrouvees = sum(1 for ref, _cand in paires if ref.id in decisives) + sum(
        1 for i in par_filtre if i in decisives
    )

    for ref, cand in paires:
        for champ in ("kind", "effect", "fact", "field"):
            avant, apres = getattr(ref, champ), getattr(cand, champ)
            if avant != apres:
                comp.divergences.append(Divergence(ref.id, champ, str(avant), str(apres)))
        if (ref.predicate is None) != (cand.predicate is None) or (
            ref.predicate and cand.predicate and ref.predicate.root != cand.predicate.root
        ):
            comp.divergences.append(
                Divergence(
                    ref.id,
                    "predicate",
                    str(ref.predicate.root if ref.predicate else None),
                    str(cand.predicate.root if cand.predicate else None),
                )
            )

    for champ in CHAMPS_AIDE:
        avant, apres = _lire(reference, champ), _lire(candidat, champ)
        if avant != apres:
            comp.champs_divergents.append(Divergence("(aide)", champ, str(avant), str(apres)))
            if champ.startswith("hard_filters."):
                comp.filtres_divergents = True

    citees = [c for c in candidat.conditions if c.quote]
    comp.citations_candidat = len(citees)
    if documents:
        from veille_text import find_quote_in_any

        comp.citations_verifiees = sum(
            1 for c in citees if find_quote_in_any(c.quote or "", documents)[1].found
        )
    else:
        comp.citations_verifiees = len(citees)
    return comp


# ---------------------------------------------------------------------------
# Lecture du journal
# ---------------------------------------------------------------------------


@dataclass
class Journal:
    tours: int = 0
    cout_usd: float | None = None
    duree_s: float | None = None
    appels: dict[str, int] = field(default_factory=dict)
    elagages: int = 0
    relances: int = 0
    budget_epuise: bool = False


_TOUR_RE = re.compile(r"^--- tour (\d+) .*cumul \$([0-9.]+)", re.M)
_APPEL_RE = re.compile(r"^\[appel\] (\w+)\(", re.M)
_DUREE_RE = re.compile(r"durée ([0-9.]+) s")


def lire_log(chemin: Path) -> Journal:
    """Ce que le journal d'un run apprend : tours, coût, durée, outils, incidents.

    Lit le DERNIER run du fichier : le journal est ouvert en ajout, et rejouer
    une aide y empile un second bloc. Comparer sur le premier ferait mesurer un
    run qu'on a précisément voulu refaire.
    """
    texte = chemin.read_text(encoding="utf-8", errors="replace")
    bloc = texte.rsplit("=" * 78, 1)[-1] if "=" * 78 in texte else texte
    journal = Journal()
    tours = _TOUR_RE.findall(bloc)
    if tours:
        journal.tours = int(tours[-1][0])
        journal.cout_usd = float(tours[-1][1])
    if (duree := _DUREE_RE.search(bloc)) is not None:
        journal.duree_s = float(duree.group(1))
    for nom in _APPEL_RE.findall(bloc):
        journal.appels[nom] = journal.appels.get(nom, 0) + 1
    journal.elagages = bloc.count("[*] élagage")
    journal.relances = len(re.findall(r"\[\*\] relance \d+/", bloc))
    journal.budget_epuise = "avertissement de budget" in bloc
    return journal


# ---------------------------------------------------------------------------
# Rendu
# ---------------------------------------------------------------------------


def rendre(comp: Comparaison, journal: Journal | None) -> str:
    lignes = [
        f"# {comp.slug}",
        "",
        f"conditions : {comp.conditions_reference} en référence, "
        f"{comp.conditions_candidat} chez le candidat, {comp.communes} appariées",
        f"décisives  : {comp.decisives_retrouvees}/{comp.decisives_reference} exigences "
        f"gate+modulateur retrouvées ({comp.rappel_decisives:.0%})",
        f"  dont gates : {comp.gates_retrouvees}/{comp.gates_reference} ({comp.rappel_gates:.0%})",
        f"précision  : {comp.precision:.0%} des conditions du candidat correspondent",
        f"citations  : {comp.citations_verifiees}/{comp.citations_candidat} vérifiées "
        f"({comp.quotes_ok:.0%})",
        f"SCORE      : {comp.score}/100",
    ]
    if journal:
        cout = f"${journal.cout_usd:.4f}" if journal.cout_usd is not None else "?"
        duree = f"{journal.duree_s:.0f} s" if journal.duree_s is not None else "?"
        lignes += [
            "",
            f"run        : {journal.tours} tour(s), {cout}, {duree}, "
            f"{journal.elagages} élagage(s), {journal.relances} relance(s)"
            + (" — BUDGET ÉPUISÉ" if journal.budget_epuise else ""),
            "outils     : "
            + ", ".join(f"{n}×{c}" for n, c in sorted(journal.appels.items(), key=lambda x: -x[1])),
        ]
    if comp.manquantes:
        lignes += [
            "",
            f"MANQUANTES ({len(comp.manquantes)}) :",
            *(f"  - {m}" for m in comp.manquantes),
        ]
    if comp.couvertes_par_filtre:
        lignes += [
            "",
            f"COUVERTES PAR UN HARD_FILTER ({len(comp.couvertes_par_filtre)}) — comptées "
            "retrouvées :",
            *(f"  = {m}" for m in comp.couvertes_par_filtre),
        ]
    if comp.composites:
        lignes += [
            "",
            f"COMPOSITES DU CANDIDAT ({len(comp.composites)}) — une liste repliée en une "
            "condition :",
            *(f"  ≡ {m}" for m in comp.composites),
        ]
    if comp.en_trop:
        lignes += ["", f"EN TROP ({len(comp.en_trop)}) :", *(f"  + {m}" for m in comp.en_trop)]
    if comp.divergences:
        lignes += ["", f"TYPAGE DIVERGENT ({len(comp.divergences)}) :"]
        lignes += [
            f"  {d.condition} / {d.champ} : {d.reference} → {d.candidat}" for d in comp.divergences
        ]
    if comp.champs_divergents:
        lignes += ["", f"CHAMPS DE L'AIDE ({len(comp.champs_divergents)}) :"]
        lignes += [f"  {d.champ} : {d.reference} → {d.candidat}" for d in comp.champs_divergents]
    if avis := comp.avertissements():
        lignes += ["", "⚠ À LIRE AVANT DE CLASSER :"]
        lignes += [f"  - {a}" for a in avis]
    return "\n".join(lignes)


# ---------------------------------------------------------------------------
# Tableau de synthèse du banc d'essai
# ---------------------------------------------------------------------------


@dataclass
class Ligne:
    modele: str
    slug: str
    comparaison: Comparaison
    journal: Journal | None


def evaluer(reference_dir: Path, sortie: Path, slug: str) -> Ligne | None:
    """Compare une extraction candidate à sa référence, journal et snapshots compris.

    `None` quand le candidat n'a rien produit : un run qui a échoué n'a pas de
    fichier, et le faire compter comme un score de zéro serait moins lisible
    qu'une ligne « absent » dans le tableau.
    """
    candidat = sortie / "aides" / f"{slug}.yaml"
    if not candidat.exists():
        return None
    log = sortie / "reviews" / "logs" / f"ingest-{slug}.log"
    return Ligne(
        modele=sortie.name,
        slug=slug,
        comparaison=comparer(
            load_aide(reference_dir / f"{slug}.yaml"),
            load_aide(candidat),
            _charger_documents(sortie / "sources" / slug),
        ),
        journal=lire_log(log) if log.exists() else None,
    )


def tableau(lignes: list[Ligne], absents: list[tuple[str, str]]) -> str:
    """La synthèse à consigner dans data/reviews/<date>-benchmark-ingestion.md."""
    entete = (
        "| modèle | aide | décisives | précision | quotes OK | tours | coût | durée | score |\n"
        "|---|---|---|---|---|---|---|---|---|"
    )
    corps = []
    for ligne in lignes:
        c, j = ligne.comparaison, ligne.journal
        corps.append(
            f"| {ligne.modele} | {ligne.slug} | "
            f"{c.decisives_retrouvees}/{c.decisives_reference} ({c.rappel_decisives:.0%}) | "
            f"{c.precision:.0%} | {c.citations_verifiees}/{c.citations_candidat} "
            f"({c.quotes_ok:.0%}) | "
            f"{j.tours if j else '?'} | "
            f"{f'${j.cout_usd:.3f}' if j and j.cout_usd is not None else '?'} | "
            f"{f'{j.duree_s:.0f} s' if j and j.duree_s is not None else '?'} | "
            f"**{c.score}** |"
        )
    for modele, slug in absents:
        corps.append(f"| {modele} | {slug} | — | — | — | — | — | — | **échec** |")

    par_modele: dict[str, list[Ligne]] = {}
    for ligne in lignes:
        par_modele.setdefault(ligne.modele, []).append(ligne)
    moyennes = ["", "## Moyenne par modèle", ""]
    for modele, siennes in sorted(
        par_modele.items(), key=lambda kv: -sum(li.comparaison.score for li in kv[1]) / len(kv[1])
    ):
        score = sum(li.comparaison.score for li in siennes) / len(siennes)
        couts = [li.journal.cout_usd for li in siennes if li.journal and li.journal.cout_usd]
        rate = sum(1 for m, _ in absents if m == modele)
        moyennes.append(
            f"- **{modele}** : {score:.1f}/100 sur {len(siennes)} aide(s)"
            + (f", {sum(couts) / len(couts):.3f} $ en moyenne" if couts else "")
            + (f", {rate} échec(s)" if rate else "")
        )
    return "\n".join([entete, *corps, *moyennes])


def main_tableau(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="comparer_aides.py tableau",
        description="Synthèse d'un banc d'essai : plusieurs modèles sur plusieurs aides.",
    )
    parser.add_argument("slugs", nargs="+", help="aides de la vérité terrain")
    parser.add_argument(
        "--sortie",
        type=Path,
        action="append",
        required=True,
        default=[],
        help="dossier d'un run (--sortie de ingerer.py) ; répétable",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "aides",
        help="dossier des extractions de référence (défaut : data/aides)",
    )
    args = parser.parse_args(argv)

    lignes: list[Ligne] = []
    absents: list[tuple[str, str]] = []
    for sortie in args.sortie:
        for slug in args.slugs:
            ligne = evaluer(args.reference, sortie, slug)
            if ligne is None:
                absents.append((sortie.name, slug))
            else:
                lignes.append(ligne)
    if not lignes and not absents:
        print("Rien à comparer.")
        return 1
    print(tableau(lignes, absents))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "tableau":
        return main_tableau(argv[1:])
    parser = argparse.ArgumentParser(
        prog="comparer_aides.py",
        description="Compare une extraction candidate à une extraction de référence.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidat", type=Path)
    parser.add_argument("--log", type=Path, help="journal du run candidat")
    parser.add_argument(
        "--sources",
        type=Path,
        help="dossier de snapshots du candidat, pour vérifier ses citations",
    )
    parser.add_argument("--json", action="store_true", help="sortie machine")
    args = parser.parse_args(argv)

    reference = load_aide(args.reference)
    candidat = load_aide(args.candidat)
    documents = _charger_documents(args.sources) if args.sources else None
    comp = comparer(reference, candidat, documents)
    journal = lire_log(args.log) if args.log and args.log.exists() else None

    if args.json:
        print(
            json.dumps(
                {
                    **asdict(comp),
                    "score": comp.score,
                    "journal": asdict(journal) if journal else None,
                },
                ensure_ascii=False,
                indent=1,
            )
        )
    else:
        print(rendre(comp, journal))
    return 0


def _charger_documents(dossier: Path) -> list[tuple[str, str, str]]:
    """Snapshots d'un dossier, au format attendu par `find_quote_in_any`."""
    from veille_collect import pdf_to_text
    from veille_text import flatten_markdown_links, parse_front_matter

    documents: list[tuple[str, str, str]] = []
    for chemin in sorted(dossier.iterdir()) if dossier.is_dir() else []:
        if chemin.suffix.lower() == ".md":
            _meta, corps = parse_front_matter(chemin.read_text(encoding="utf-8", errors="replace"))
            documents.append((chemin.name, flatten_markdown_links(corps), "text"))
        elif chemin.suffix.lower() == ".pdf" and (texte := pdf_to_text(chemin)):
            documents.append((chemin.name, texte, "pdf"))
    return documents


if __name__ == "__main__":
    sys.exit(main())
