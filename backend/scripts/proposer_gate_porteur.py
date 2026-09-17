"""Backfill du gate « Bénéficiaires » des aides d'entreprise — PROPOSE, ne décide pas.

Une aide réservée aux entreprises qui ne dit pas QUI peut déposer reste vivante
pour une commune jusqu'à sa première question d'entreprise — et cette question
est posée. Seul `hard_filters` écarte en silence, et il parle du propriétaire du
BIEN, pas du porteur du dossier. Mesuré le 2026-09-17 sur un profil « commune,
classé, Grand Est, restauration » : 18 questions réellement posées dont 10
d'entreprise, contre 10 questions une fois le gate porteur posé.

Le corpus n'est pas deviné : c'est EXACTEMENT ce que la règle de lint
`check_porteur_entreprise` sort en erreur (elle est importée, pas réécrite). Le
marqueur `porteurs_concernes` de `facts.yaml` en est la source.

    uv run python scripts/proposer_gate_porteur.py             # fiche du jour
    uv run python scripts/proposer_gate_porteur.py --stdout    # sans écrire
    uv run python scripts/proposer_gate_porteur.py --appliquer # cas nets seulement

Déterministe, sans LLM ni réseau. Le passage « Bénéficiaires » est extrait des
snapshots archivés de l'aide (`data/sources/<slug>/`, PDF compris via
`load_baselines`), et la citation proposée est RECONTRÔLÉE dans le snapshot par
la même fonction que le lint `--quotes` : une extraction bancale n'est jamais
`net`. C'est le seul garde-fou qui vaille ici — le reste se relit au diff.

`--appliquer` est volontairement étroit :
  - la proposition est `net` (passage trouvé, citation recontrôlée, au moins un
    mot-clé entreprise, aucun mot-clé collectivité / association / particulier) ;
  - l'aide ne porte pas déjà un gate `statut_juridique_porteur`.
Tout le reste part dans la fiche avec son passage source et un Verdict vide.

L'insertion est TEXTUELLE, à la fin du bloc `conditions:` — un `yaml.dump`
effacerait les commentaires doctrinaux de 108 des 405 fiches.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from typing import NamedTuple

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lint_aides_data import check_porteur_entreprise, gate_porteur  # noqa: E402
from veille_collect import load_baselines  # noqa: E402
from veille_text import find_quote_in_any, normalize  # noqa: E402

from aides_schema import (  # noqa: E402
    AIDES_DIR,
    FACTS_FILE,
    FACTS_PENDING_FILE,
    FAIT_PORTEUR,
    Aide,
    load_aide,
    load_facts,
    load_pending_facts,
    predicate_leaves,
)

RACINE = Path(__file__).resolve().parent.parent
REVIEWS_DIR = RACINE / "data" / "reviews"

ID_CONDITION = "beneficiaires-porteur"

# Titres de section sous lesquels une source énonce QUI peut déposer. Liste
# FERMÉE : un titre deviné large ramènerait le paragraphe d'à côté, et la
# citation proposée serait fausse tout en ayant l'air sourcée.
# Relevés sur le corpus, pas devinés : « Pouvez-vous bénéficier de l'aide
# régionale ? » est le titre du gabarit grandest.fr, celui de 24 des snapshots
# du lot — l'ignorer laissait 32 aides sans passage.
TITRES_BENEFICIAIRES = (
    "beneficiaire",
    "structures eligibles",
    "qui peut",
    "pouvez-vous beneficier",
    "pour qui",
    "sont eligibles",
    "public vise",
    "publics vises",
    "porteurs eligibles",
)

# Un passage plus long n'est plus une puce « Bénéficiaires » : c'est la page.
MAX_PASSAGE = 600
# Une citation trop longue se retrouve mal dans le snapshot (repli de lignes,
# puces réécrites) et se relit mal au diff.
MAX_QUOTE = 300

# ---------------------------------------------------------------------------
# Mots-clés → options de `statut_juridique_porteur`
# ---------------------------------------------------------------------------
#
# Table FERMÉE, sur le texte NORMALISÉ (sans accents, minuscules). Elle ne
# décide rien toute seule : elle ne sert qu'à proposer un prédicat, que le diff
# git relit contre la `quote` posée juste au-dessus.

MOTS_ENTREPRISE: dict[str, tuple[str, ...]] = {
    "tpe": ("societe", "entreprise_individuelle"),
    "pme": ("societe", "entreprise_individuelle"),
    "eti": ("societe",),
    "entreprise": ("societe", "entreprise_individuelle"),
    "entreprises": ("societe", "entreprise_individuelle"),
    "societe": ("societe",),
    "societes": ("societe",),
    "sas": ("societe",),
    "sarl": ("societe",),
    "eurl": ("societe",),
    "scop": ("societe",),
    "scic": ("societe",),
    "artisan": ("entreprise_individuelle", "societe"),
    "artisans": ("entreprise_individuelle", "societe"),
    "artisanale": ("entreprise_individuelle", "societe"),
    "commercant": ("entreprise_individuelle", "societe"),
    "commercants": ("entreprise_individuelle", "societe"),
    "micro-entrepreneur": ("entreprise_individuelle",),
    "microentrepreneur": ("entreprise_individuelle",),
    "auto-entrepreneur": ("entreprise_individuelle",),
    "independant": ("entreprise_individuelle",),
    "independants": ("entreprise_individuelle",),
    "exploitant": ("entreprise_individuelle", "societe"),
    "exploitants": ("entreprise_individuelle", "societe"),
    "agriculteur": ("entreprise_individuelle", "societe"),
    "agriculteurs": ("entreprise_individuelle", "societe"),
    "gaec": ("societe",),
    "earl": ("societe",),
    "cuma": ("societe",),
}

# Les mots qui DISQUALIFIENT l'automatisme : dès qu'un porteur non-entreprise
# apparaît dans le passage, la liste des bénéficiaires n'est plus celle que la
# table sait écrire. La proposition part en fiche avec son passage.
#
# « région », « département » et « métropole » n'y sont PAS, et c'est délibéré :
# dans ce corpus ils nomment le FINANCEUR (« un prestataire référencé par la
# Région Grand Est ») bien plus souvent que le bénéficiaire, et les garder
# rendait non nettes 20 aides d'un coup. Le risque est couvert : une liste de
# bénéficiaires réellement publique nomme toujours aussi des communes, des
# collectivités, des EPCI ou des établissements publics — qui restent, eux,
# disqualifiants. Le sens inverse serait grave, celui-ci coûte une relecture.
MOTS_AUTRES: dict[str, tuple[str, ...]] = {
    "commune": ("public_commune",),
    "communes": ("public_commune",),
    "collectivite": ("public_commune", "public_epci", "public_departement", "public_region"),
    "collectivites": ("public_commune", "public_epci", "public_departement", "public_region"),
    "epci": ("public_epci",),
    "intercommunalite": ("public_epci",),
    "intercommunalites": ("public_epci",),
    "syndicat mixte": ("syndicat_mixte",),
    "parc naturel": ("syndicat_mixte",),
    "etablissement public": ("etablissement_public",),
    "etablissements publics": ("etablissement_public",),
    "association": ("association",),
    "associations": ("association",),
    "fondation": ("fondation",),
    "fondations": ("fondation",),
    "particulier": ("prive_personne_physique",),
    "particuliers": ("prive_personne_physique",),
    "personne physique": ("prive_personne_physique",),
    "personnes physiques": ("prive_personne_physique",),
    "sci": ("prive_sci",),
}

# Ordre d'affichage des options : celui de `statut_juridique_porteur`, pour que
# deux prédicats proposés se comparent à l'œil.
ORDRE_OPTIONS = [
    "prive_personne_physique",
    "prive_sci",
    "societe",
    "entreprise_individuelle",
    "association",
    "fondation",
    "etablissement_public",
    "public_commune",
    "public_epci",
    "public_metropole",
    "syndicat_mixte",
    "public_departement",
    "public_region",
    "public_etat",
]


class Proposition(NamedTuple):
    slug: str
    titre: str  #: titre de la section d'où vient le passage, "" si introuvable
    passage: str  #: le passage source, tel quel
    quote: str  #: la citation à poser, recontrôlée dans le snapshot
    options: list[str]  #: le prédicat proposé
    autres: list[str]  #: porteurs non-entreprise vus dans le passage
    net: bool  #: `--appliquer` l'écrit sans relecture préalable


class Permissif(NamedTuple):
    """Une aide dont le gate porteur EXISTE mais admet un porteur public.

    Certaines le méritent (cinéma municipal, desserte forestière), d'autres
    sont un gate recopié trop large. La fiche les met côte à côte, elle ne
    tranche pas.
    """

    slug: str
    options: list[str]
    faits: list[str]


# ---------------------------------------------------------------------------
# Extraction du passage « Bénéficiaires »
# ---------------------------------------------------------------------------

# Une ligne qui ouvre une section. Trois formes rencontrées dans les
# snapshots : titre markdown, ligne en gras seule, article de règlement (PDF).
_TITRE_MD = re.compile(r"^\s{0,3}#{1,6}\s+(?P<titre>.+?)\s*#*\s*$")
_TITRE_GRAS = re.compile(r"^\s*\*\*(?P<titre>[^*]{2,80})\*\*\s*:?\s*$")
_TITRE_ARTICLE = re.compile(r"^\s*(?P<titre>ARTICLE\s+\d+\b.*|Article\s+\d+\b.*)$")


def _titre_de(ligne: str) -> str | None:
    for motif in (_TITRE_MD, _TITRE_GRAS, _TITRE_ARTICLE):
        m = motif.match(ligne)
        if m:
            return m.group("titre").strip()
    return None


class Passage(NamedTuple):
    titre: str
    plat: str  #: le passage aplati, pour les mots-clés et la fiche
    lignes: list[str]  #: l'énumération des bénéficiaires, ligne à ligne, pour la citation


# Marqueurs de puce, à retirer d'une ligne avant d'en faire une citation : le
# snapshot normalisé ne les porte plus, et une quote qui les garde ne se
# retrouve pas.
_PUCE = re.compile(r"^\s*(?:[*+•-]\s+)+")

# Ce qui ferme l'énumération des bénéficiaires et ouvre autre chose : les
# critères de PROJET, les dépenses, le rappel de non-automaticité. Liste
# FERMÉE, relevée sur les snapshots. Sans elle, « La création d'une entreprise »
# — une ligne de la rubrique « Et si votre projet concerne : » — servait de
# citation pour désigner le bénéficiaire d'une aide ouverte à « un jeune de 18 à
# 29 ans », et le gate proposé aurait exclu ce jeune.
_PIVOTS = (
    "et si",
    "de plus",
    "par ailleurs",
    "si vous repondez",
    "projets soutenus",
    "depenses eligibles",
    "vous mettez en oeuvre",
    "le projet doit",
    "votre projet doit",
)


def _ferme_l_enumeration(ligne: str) -> bool:
    plat = normalize(ligne)
    return any(plat.startswith(pivot) for pivot in _PIVOTS)


def extraire_passage(texte: str) -> Passage | None:
    """La première section qui énonce les bénéficiaires.

    Le corps s'arrête au titre suivant — c'est la seule frontière fiable : les
    sources alternent puces, tableaux et paragraphes, et une coupe au nombre de
    lignes ramènerait les conditions d'éligibilité avec les bénéficiaires.

    Les lignes sont gardées SÉPARÉES en plus de l'aplati : une citation qui
    enjambe deux puces ne se retrouve jamais dans le snapshot, dont chaque
    ligne est normalisée pour elle-même.
    """
    lignes = texte.splitlines()
    for i, ligne in enumerate(lignes):
        titre = _titre_de(ligne)
        if titre is None:
            continue
        plat_titre = normalize(titre)
        if not any(mot in plat_titre for mot in TITRES_BENEFICIAIRES):
            continue
        corps: list[str] = []
        for suivante in lignes[i + 1 :]:
            if _titre_de(suivante) is not None:
                break
            nue = " ".join(_PUCE.sub("", suivante).split())
            if nue:
                corps.append(nue)
        joint = " ".join(corps)[:MAX_PASSAGE]
        if not joint:
            continue
        designations: list[str] = []
        for nue in corps:
            if _ferme_l_enumeration(nue):
                break
            designations.append(nue)
        return Passage(titre, joint, designations or corps[:1])
    return None


def _mots_vus(passage: str, table: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    plat = normalize(passage)
    return {mot: opts for mot, opts in table.items() if re.search(rf"\b{re.escape(mot)}\b", plat)}


def _premiere_phrase(passage: str) -> str:
    """Le `text` de la condition : la source, jamais une reformulation."""
    m = re.search(r"^(.{20,240}?[.;:])(?:\s|$)", passage)
    return (m.group(1) if m else passage[:240]).strip()


def tailler_quote(passage: Passage, documents: list[tuple[str, str, str]]) -> str:
    """La citation à poser, RECONTRÔLÉE dans le snapshot avant d'être proposée.

    Une citation inventée est la faute la plus grave du catalogue. Plutôt que
    de faire confiance à la découpe, on la vérifie ici avec la fonction du lint
    `--quotes` — et si aucune candidate ne passe en « exacte », la proposition
    n'est pas `net`.

    Les candidates, dans l'ordre : les lignes qui NOMMENT une catégorie
    d'entreprise — c'est la citation qui justifie le prédicat, elle doit donc
    porter le mot qui l'a fait choisir — puis, à défaut, la ligne d'attaque de
    la section et sa première phrase.

    L'ordre compte : sur le gabarit grandest.fr, la ligne d'attaque est
    « Vous pouvez bénéficier de l'aide, si vous êtes : » et la catégorie arrive
    à la puce suivante. Citer l'attaque laisserait un prédicat sans justification
    sous les yeux du relecteur.
    """
    tete = passage.lignes[0] if passage.lignes else ""
    parlantes = [ligne for ligne in passage.lignes if _mots_vus(ligne, MOTS_ENTREPRISE)]
    candidates = [*parlantes, tete, _premiere_phrase(tete)]
    for candidate in candidates:
        candidate = candidate.strip(" -–—•*")[:MAX_QUOTE]
        if len(candidate) < 20:
            continue
        _nom, match = find_quote_in_any(candidate, documents)
        # `baseline_pdf` vaut `exacte` ici : la citation EST dans le snapshot,
        # le statut ne dit que l'impossibilité de surveiller la page. Refuser
        # `degradee`, en revanche — une citation qu'on écrit aujourd'hui n'a
        # aucune raison de ne pas correspondre au caractère près.
        if match.status in ("exacte", "baseline_pdf") and not match.reconstitution:
            return candidate
    return ""


# ---------------------------------------------------------------------------
# Mots-clés → prédicat
# ---------------------------------------------------------------------------


def _trier(options: set[str]) -> list[str]:
    return [o for o in ORDRE_OPTIONS if o in options]


def analyser(aide: Aide, documents: list[tuple[str, str, str]]) -> Proposition:
    extrait = None
    for _nom, contenu, _type in documents:
        extrait = extraire_passage(contenu)
        if extrait:
            break
    if extrait is None:
        return Proposition(aide.slug, "", "", "", [], [], net=False)

    quote = tailler_quote(extrait, documents)
    # Les mots d'ENTREPRISE se lisent dans la CITATION, pas dans le passage
    # entier : le prédicat proposé doit être justifié par la quote posée juste
    # au-dessus de lui, c'est la règle du catalogue. Scanner les 600 caractères
    # rendait nettes trois aides dont la source dit « un jeune de 18 à 29 ans »
    # et dont le mot « entreprise » n'arrivait que vingt lignes plus loin.
    #
    # Les mots DISQUALIFIANTS, eux, se lisent dans le passage entier : un doute
    # vu n'importe où doit envoyer l'aide en relecture.
    entreprise = _mots_vus(quote, MOTS_ENTREPRISE)
    autres = _mots_vus(extrait.plat, MOTS_AUTRES)
    options: set[str] = set()
    for opts in entreprise.values():
        options.update(opts)
    for opts in _mots_vus(extrait.plat, MOTS_ENTREPRISE).values():
        options.update(opts)
    for opts in autres.values():
        options.update(opts)
    net = bool(entreprise) and not autres
    return Proposition(
        aide.slug,
        extrait.titre,
        extrait.plat,
        quote,
        _trier(options),
        _trier({o for opts in autres.values() for o in opts}),
        net=net,
    )


# ---------------------------------------------------------------------------
# Écriture
# ---------------------------------------------------------------------------

OPTIONS_PUBLIQUES = frozenset(
    {
        "public_commune",
        "public_epci",
        "public_metropole",
        "public_departement",
        "public_region",
        "public_etat",
    }
)

# Le bloc `conditions:` va jusqu'à la prochaine clé de premier niveau. Les
# fiches n'indentent pas toutes leurs puces pareil (0 ou 2 espaces) : c'est
# l'indentation EXISTANTE qui décide, jamais une préférence du script.
BLOC_CONDITIONS = re.compile(r"^conditions:\n(?P<corps>(?:(?!^[a-z_]+:).*\n)*)", re.M)


def _bloc_condition(proposition: Proposition, indent: int, jour: date) -> str:
    condition = {
        "id": ID_CONDITION,
        "text": _premiere_phrase(proposition.quote),
        "kind": "user_fact",
        "effect": "gate",
        "fact": FAIT_PORTEUR,
        "predicate": {"in": proposition.options},
        "quote": proposition.quote,
        "notes": (
            f"Gate posé par scripts/proposer_gate_porteur.py le {jour.isoformat()} depuis la "
            f"section « {proposition.titre} » du snapshot ; relu au diff."
        ),
    }
    brut = yaml.safe_dump(
        [condition], allow_unicode=True, sort_keys=False, width=1000, default_flow_style=False
    )
    marge = " " * indent
    return "".join(marge + ligne + "\n" for ligne in brut.splitlines())


def appliquer(proposition: Proposition, *, jour: date) -> bool:
    """Insère la condition à la fin du bloc `conditions:`, textuellement."""
    chemin = AIDES_DIR / f"{proposition.slug}.yaml"
    texte = chemin.read_text(encoding="utf-8")
    m = BLOC_CONDITIONS.search(texte)
    if not m:
        return False
    corps = m.group("corps")
    puces = [
        len(ligne) - len(ligne.lstrip())
        for ligne in corps.splitlines()
        if ligne.lstrip().startswith("- ")
    ]
    if not puces:
        return False
    # La fin du bloc, blancs de queue exclus : une condition insérée après une
    # ligne vide sortirait du bloc pour les lecteurs humains.
    fin = m.start() + len("conditions:\n") + len(corps.rstrip("\n")) + 1
    bloc = _bloc_condition(proposition, min(puces), jour)
    chemin.write_text(texte[:fin] + bloc + texte[fin:], encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Fiche de review
# ---------------------------------------------------------------------------


def _extrait(texte: str, taille: int = 160) -> str:
    plat = " ".join(texte.split()).replace("|", "\\|")
    return plat if len(plat) <= taille else plat[:taille] + "…"


def fiche(
    propositions: list[Proposition], permissifs: list[Permissif], jour: date, marques: list[str]
) -> str:
    nets = [p for p in propositions if p.net]
    douteux = [p for p in propositions if not p.net and p.passage]
    muets = [p for p in propositions if not p.passage]

    lignes = [
        f"# Gate « Bénéficiaires » — proposition du {jour.isoformat()}",
        "",
        "Corpus : les aides que `check_porteur_entreprise` sort en erreur, c'est-à-dire "
        "celles qui gatent un fait marqué `porteurs_concernes` sans dire qui peut déposer. "
        f"{len(marques)} fait(s) portent le marqueur.",
        "",
        "Le passage source vient des snapshots archivés de l'aide ; la citation proposée a "
        "été recontrôlée dans le snapshot par la fonction du lint `--quotes`. Ce que le "
        "script ne sait pas faire, il le laisse vide : la colonne **Verdict** est pour vous.",
        "",
        f"- {len(nets)} proposition(s) **nette(s)** — `--appliquer` les écrit ;",
        f"- {len(douteux)} passage(s) trouvé(s) mais **non net(s)** (porteur non-entreprise cité, "
        "ou citation non recontrôlée) ;",
        f"- {len(muets)} aide(s) **sans section Bénéficiaires** dans le snapshot ;",
        f"- {len(permissifs)} gate(s) porteur **permissif(s)** à vérifier.",
        "",
    ]

    def tableau(titre: str, intro: str, lot: list[Proposition], *, avec_options: bool) -> None:
        if not lot:
            return
        lignes.extend([f"## {titre}", "", intro, ""])
        entete = "| Aide | Section | Passage source | Options proposées | Verdict |"
        if not avec_options:
            entete = "| Aide | Section | Passage source | Porteurs vus | Verdict |"
        lignes.extend([entete, "|---|---|---|---|---|"])
        for p in sorted(lot, key=lambda p: p.slug):
            colonne = ", ".join(p.options) if avec_options else ", ".join(p.autres) or "—"
            lignes.append(
                f"| `{p.slug}` | {p.titre or '—'} | {_extrait(p.passage)} | {colonne} |  |"
            )
        lignes.append("")

    tableau(
        "Propositions nettes",
        "Passage trouvé, citation recontrôlée, mots-clés d'entreprise seulement. "
        "`--appliquer` pose le gate ; le diff git est la revue.",
        nets,
        avec_options=True,
    )
    tableau(
        "Passage trouvé, proposition non nette",
        "Le passage cite un porteur qui n'est pas une entreprise (ou sa citation ne s'est pas "
        "retrouvée au snapshot). À trancher à la main, ou par `/ingest-aide <slug>` en "
        "ré-extraction.",
        douteux,
        avec_options=False,
    )

    if muets:
        lignes.extend(
            [
                "## Sans section Bénéficiaires dans le snapshot",
                "",
                "Aucune section reconnue (`" + "`, `".join(TITRES_BENEFICIAIRES) + "`). "
                "La source la porte peut-être sous un autre titre, ou en corps de texte.",
                "",
            ]
            + [f"- `{p.slug}`" for p in sorted(muets, key=lambda p: p.slug)]
            + [""]
        )

    if permissifs:
        lignes.extend(
            [
                "## Gates porteur permissifs à vérifier",
                "",
                "Ces aides DISENT qui dépose — le lint est donc vert — mais admettent un "
                "porteur public tout en gatant un fait d'entreprise. Certaines le méritent "
                "(cinéma municipal, agroalimentaire, desserte forestière) ; les autres posent "
                "leurs questions de PME aux communes.",
                "",
                "| Aide | Prédicat actuel | Faits d'entreprise gatés |",
                "|---|---|---|",
            ]
            + [
                f"| `{p.slug}` | {', '.join(p.options)} | {', '.join(p.faits)} |"
                for p in sorted(permissifs, key=lambda p: p.slug)
            ]
            + [""]
        )
    return "\n".join(lignes) + "\n"


# ---------------------------------------------------------------------------


def _options_du_gate(aide: Aide) -> list[str]:
    valeurs: set[str] = set()
    clauses = [
        c.predicate for c in aide.conditions if c.effect == "gate" and c.fact == FAIT_PORTEUR
    ]
    if aide.applies_if and aide.applies_if.fact == FAIT_PORTEUR:
        clauses.append(aide.applies_if.predicate)
    for clause in clauses:
        for _op, valeur in predicate_leaves(clause.root):
            valeurs.update(valeur if isinstance(valeur, list) else [valeur])
    return _trier({v for v in valeurs if isinstance(v, str)})


def corpus(aides: dict[str, Aide], facts) -> tuple[list[str], list[Permissif]]:
    """(aides en erreur de lint, gates permissifs) — la règle du lint, pas une copie."""
    en_erreur: list[str] = []
    permissifs: list[Permissif] = []
    for slug, aide in aides.items():
        if check_porteur_entreprise(aide, facts):
            en_erreur.append(slug)
            continue
        if not gate_porteur(aide):
            continue
        marques = [
            c.fact
            for c in aide.conditions
            if c.effect == "gate"
            and c.fact
            and facts.get(c.fact)
            and facts[c.fact].porteurs_concernes
        ]
        options = _options_du_gate(aide)
        if marques and OPTIONS_PUBLIQUES & set(options):
            permissifs.append(Permissif(slug, options, sorted(set(marques))))
    return en_erreur, permissifs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stdout", action="store_true", help="imprimer sans écrire la fiche")
    parser.add_argument(
        "--appliquer", action="store_true", help="écrire les propositions NETTES dans les YAML"
    )
    args = parser.parse_args()

    load_facts.cache_clear()
    load_pending_facts.cache_clear()
    facts = {**load_facts(FACTS_FILE), **load_pending_facts(FACTS_PENDING_FILE)}
    marques = sorted(k for k, f in facts.items() if f.porteurs_concernes)

    aides = {p.stem: load_aide(p) for p in sorted(AIDES_DIR.glob("*.yaml"))}
    en_erreur, permissifs = corpus(aides, facts)

    propositions: list[Proposition] = []
    for slug in en_erreur:
        documents, _illisibles, _provenance = load_baselines(slug)
        propositions.append(analyser(aides[slug], documents))

    jour = date.today()
    if args.appliquer:
        ecrites = [
            p
            for p in propositions
            if p.net and not gate_porteur(aides[p.slug]) and appliquer(p, jour=jour)
        ]
        print(f"{len(ecrites)} gate(s) posé(s) — à relire au diff git :")
        for p in ecrites:
            print(f"  {p.slug} → in [{', '.join(p.options)}]")
        restantes = len(propositions) - len(ecrites)
        print(f"{restantes} aide(s) restent à trancher à la main (relancer sans --appliquer)")
        print("Puis : uv run python scripts/lint_aides_data.py --quotes")
        return 0

    texte = fiche(propositions, permissifs, jour, marques)
    if args.stdout:
        print(texte)
        return 0
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    chemin = REVIEWS_DIR / f"{jour.isoformat()}-proposition-gate-porteur.md"
    chemin.write_text(texte, encoding="utf-8")
    print(f"Fiche écrite : {chemin.relative_to(RACINE)}")
    print(
        f"{sum(1 for p in propositions if p.net)} proposition(s) nette(s) sur {len(propositions)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
