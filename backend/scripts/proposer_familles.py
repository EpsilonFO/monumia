"""Backfill des `familles` des aides — PROPOSE, ne décide pas.

La famille est l'axe de cadrage d'un projet « faire vivre le lieu » (cf.
data/TYPING.md, § `familles`). 129 aides `valorisation_rayonnement` n'en portent
aucune : elles se présentent donc à tous les projets, spectacles comme
hébergement. Ce script les propose, AVEC LEUR PROVENANCE, dans une fiche de
review — c'est le diff git qui fait la revue.

    uv run python scripts/proposer_familles.py             # fiche du jour
    uv run python scripts/proposer_familles.py --stdout    # sans écrire
    uv run python scripts/proposer_familles.py --appliquer  # cas nets seulement

Quatre provenances, par ordre de fiabilité DÉCROISSANTE — la première qui
répond gagne, et la fiche la nomme toujours :

1. `tri.jsonl` — la famille a DÉJÀ été décidée par un humain à la prospection,
   par URL. C'est ce travail que l'ingestion perdait ; le retrouver ne coûte
   rien et ne suppose rien.
2. `applies_if.fact` — le périmètre de l'aide, croisé avec la table du moteur
   (`FAITS_DEDUITS_DES_FAMILLES`) : une aide qui ne concerne que les lieux de
   diffusion relève des spectacles.
3. `hard_filters.travaux` — l'objet des travaux, quand il est renseigné.
4. `tags` — normalisés contre une table FERMÉE, avec liste noire des tags
   d'instrument, d'échelon et de géographie, qui ne disent rien du thème.

`--appliquer` est volontairement étroit : les seules provenances (1), (2) et —
quand l'objet des travaux est ENTIÈREMENT couvert par la table — (3), et rien
d'écrit sur une aide qui porte déjà des familles. Les tags n'y entrent jamais :
leur signal est partiel (« association » sur le Prix Orgue en France), et un
premier tag trop étroit rend l'aide invisible sans que rien ne le dise.

Le nombre de familles proposées, en revanche, n'est PAS un critère : ajouter une
famille ne peut qu'élargir la visibilité d'une aide (`hors_famille` n'écarte que
sur intersection vide). Le risque est tout entier dans le premier tag.

Les ambigus se tranchent à la main dans la fiche. L'insertion est TEXTUELLE,
après le bloc `raison:` — un `yaml.dump` détruirait les commentaires.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aides_schema import AIDES_DIR, FAMILLES, Aide, load_aide  # noqa: E402
from eligibility_engine import FAITS_DEDUITS_DES_FAMILLES, hors_projet  # noqa: E402
from labels import FAMILLES_LABELS  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent
PROSPECTION_DIR = RACINE / "data" / "prospection"
REVIEWS_DIR = RACINE / "data" / "reviews"

# Provenance (3) : objet des travaux → famille. Les trois derniers codes ne
# valent que pour une aide de restauration : une aide « concerts d'orgue » à
# `raison` valorisation serait sinon taguée bâti, et écartée d'un projet de
# spectacles.
FAMILLES_PAR_TRAVAUX: dict[str, str] = {
    "parcs_jardins": "parcs_jardins_paysages",
    "etude_prealable": "etudes_ingenierie",
    "chauffage": "energie_climat",
    "ventilation": "energie_climat",
    "protection_solaire": "energie_climat",
    "accessibilite": "accessibilite_publics",
    "mise_en_securite": "securite_risques",
}
TRAVAUX_SI_RESTAURATION: dict[str, str] = {
    "orgues": "restauration_bati",
    "mobilier": "restauration_bati",
    "archives": "restauration_bati",
}

# Provenance (4) : tags → famille. Table FERMÉE, volontairement courte : un tag
# est un texte libre (537 valeurs distinctes), et deviner large se paierait en
# faux négatifs silencieux.
FAMILLES_PAR_TAG: dict[str, str] = {
    "spectacle-vivant": "spectacles_manifestations",
    "festival": "spectacles_manifestations",
    "musique": "spectacles_manifestations",
    "concert": "spectacles_manifestations",
    "theatre": "spectacles_manifestations",
    "danse": "spectacles_manifestations",
    "mediation": "mediation_numerique_expositions",
    "musee": "mediation_numerique_expositions",
    "numerique": "mediation_numerique_expositions",
    "exposition": "mediation_numerique_expositions",
    "signaletique": "mediation_numerique_expositions",
    "scenographie": "mediation_numerique_expositions",
    "inventaire": "mediation_numerique_expositions",
    "tourisme": "tourisme_hebergement",
    "hebergement": "tourisme_hebergement",
    "gite": "tourisme_hebergement",
    "chambre-d-hotes": "tourisme_hebergement",
    "accessibilite": "accessibilite_publics",
    "handicap": "accessibilite_publics",
    "parcs-jardins": "parcs_jardins_paysages",
    "jardin": "parcs_jardins_paysages",
    "arboretum": "parcs_jardins_paysages",
    "paysage": "parcs_jardins_paysages",
    "biodiversite": "eau_nature_domaine",
    "nature": "eau_nature_domaine",
    "eau": "eau_nature_domaine",
    "foret": "eau_nature_domaine",
    "energie": "energie_climat",
    "transition-ecologique": "energie_climat",
    "rehabilitation-energetique": "energie_climat",
    "label": "labels_passerelles",
    "vie-associative": "vie_locale_associative",
    "association": "vie_locale_associative",
    "insertion": "activite_economique_lieu",
    "emploi": "activite_economique_lieu",
    "commerce": "activite_economique_lieu",
    "artisanat": "activite_economique_lieu",
    "etude": "etudes_ingenierie",
    "diagnostic": "etudes_ingenierie",
    "restauration": "restauration_bati",
    "securite": "securite_risques",
    "incendie": "securite_risques",
}

# Tags qui ne disent RIEN du thème : instrument de l'aide, échelon du financeur,
# géographie. Écartés avant la table ci-dessus, pour qu'un « subvention » ou un
# « bretagne » ne puisse pas déclencher un rapprochement par hasard.
TAGS_HORS_SUJET = re.compile(
    r"^(subvention|pret|avance|garantie|exoneration|deduction|credit-impot|mecenat"
    r"|souscription|appel-a-projets?|concours|prix|dotation|bourse"
    r"|region|regional|departement|departemental|commune|communal|intercommunalite"
    r"|epci|metropole|etat|europe|europeen|national|drac|feder|leader"
    r"|patrimoine|monument-historique|classe|inscrit|non-protege|spr|abords"
    r"|proprietaire|prive|public|collectivite)$"
)


class Proposition(NamedTuple):
    slug: str
    familles: list[str]
    #: Provenance, en clair, pour la fiche de review.
    provenance: str
    #: Le cas que `--appliquer` ose. Pas « une seule famille » : ajouter une
    #: famille ne peut qu'ÉLARGIR la visibilité de l'aide (`hors_famille`
    #: n'écarte que sur intersection vide), et le risque est tout entier dans le
    #: PREMIER tag, s'il est trop étroit. Une proposition de périmètre, qui vient
    #: d'une table écrite à la main, est donc sûre même à plusieurs familles ;
    #: une proposition par tags ne l'est jamais, son signal étant partiel.
    net: bool


def _normaliser_url(url: str) -> str:
    """Compare deux URL sans se faire piéger par le protocole ni le slash."""
    u = url.strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    u = u.split("#")[0].split("?")[0]
    return u.rstrip("/")


def charge_tri() -> dict[str, tuple[str, str]]:
    """URL normalisée → (famille, territoire), depuis les fiches de prospection.

    Seules les vraies familles sont retenues : `adjacente` et `hors_perimetre`
    sont des décisions de TRI (garder / écarter un candidat) et ne disent pas
    ce que l'aide finance.
    """
    index: dict[str, tuple[str, str]] = {}
    for fichier in sorted(PROSPECTION_DIR.glob("*/tri.jsonl")):
        territoire = fichier.parent.name
        for ligne in fichier.read_text(encoding="utf-8").splitlines():
            if not ligne.strip():
                continue
            try:
                entree = json.loads(ligne)
            except json.JSONDecodeError:
                continue
            famille, url = entree.get("famille"), entree.get("url")
            if famille in FAMILLES and isinstance(url, str):
                index.setdefault(_normaliser_url(url), (famille, territoire))
    return index


def _normaliser_tag(tag: str) -> str:
    t = tag.strip().lower()
    for avant, apres in (("é", "e"), ("è", "e"), ("ê", "e"), ("à", "a"), ("ô", "o"), ("û", "u")):
        t = t.replace(avant, apres)
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def proposer(aide: Aide, tri: dict[str, tuple[str, str]]) -> Proposition | None:
    """La proposition pour cette aide, ou None si aucun signal."""
    url = _normaliser_url(aide.source.url_officielle or "")
    if url and url in tri:
        famille, territoire = tri[url]
        return Proposition(aide.slug, [famille], f"tri.jsonl ({territoire})", net=True)

    if aide.applies_if and aide.applies_if.fact in FAITS_DEDUITS_DES_FAMILLES:
        familles = sorted(FAITS_DEDUITS_DES_FAMILLES[aide.applies_if.fact])
        return Proposition(aide.slug, familles, f"périmètre `{aide.applies_if.fact}`", net=True)

    travaux = list(aide.hard_filters.travaux or [])
    table_travaux = dict(FAMILLES_PAR_TRAVAUX)
    if "restauration_travaux" in aide.raison:
        table_travaux |= TRAVAUX_SI_RESTAURATION
    depuis_travaux = {table_travaux[t] for t in travaux if t in table_travaux}
    if depuis_travaux:
        # Le signal n'est NET que si la table couvre TOUTE la liste des travaux.
        # Sinon l'aide finance autre chose en plus, et la famille déduite ne dit
        # qu'une partie de son objet : les aides MH de la Région Grand Est
        # listent `etude_prealable` parmi six ouvrages, et « études et
        # ingénierie » seule les rendrait invisibles à un projet de toiture.
        restants = sorted(t for t in travaux if t not in table_travaux)
        provenance = f"hard_filters.travaux ({', '.join(sorted(travaux))})"
        if restants:
            provenance += f" — INCOMPLET, non couverts : {', '.join(restants)}"
        return Proposition(
            aide.slug,
            sorted(depuis_travaux),
            provenance,
            net=len(depuis_travaux) == 1 and not restants,
        )

    tags = [_normaliser_tag(t) for t in aide.tags]
    retenus = {
        FAMILLES_PAR_TAG[t]: t
        for t in tags
        if t in FAMILLES_PAR_TAG and not TAGS_HORS_SUJET.match(t)
    }
    if retenus:
        return Proposition(
            aide.slug,
            sorted(retenus),
            f"tags ({', '.join(sorted(retenus.values()))})",
            # Un tag est un texte libre : jamais net, même seul.
            net=False,
        )
    return None


def fiche(aides: dict[str, Aide], propositions: list[Proposition], sans_signal: list[str]) -> str:
    par_slug = {p.slug: p for p in propositions}
    nets = [p for p in propositions if p.net]
    # Deux populations à ne SURTOUT pas mélanger, faute de quoi la fiche se lit
    # comme « voici ce que Faire vivre va proposer » — ce qu'elle n'est pas.
    faire_vivre = {s for s in aides if not hors_projet(aides[s], {"valorisation_rayonnement"})}
    lignes = [
        f"# Proposition de familles — {date.today().isoformat()}",
        "",
        "> Fiche produite par `scripts/proposer_familles.py` (lecture seule par",
        "> défaut). Elle PROPOSE : chaque ligne se tranche à la main, puis le diff git",
        "> est la revue.",
        "",
        "Règle (data/TYPING.md, § `familles`) : ne poser une famille que si la source",
        "RESTREINT le thème. Vide = l'aide concerne tout projet (fail-open) ; un tag",
        "posé « au cas où » est un faux négatif SILENCIEUX — l'utilisateur ne verra",
        "jamais l'aide et rien ne le lui dira.",
        "",
        "## Ce que cette fiche n'est PAS",
        "",
        "Elle ne liste pas les aides que « Faire vivre et ouvrir le lieu » propose. Le",
        "premier filtre est la FINALITÉ (`raison`, `hors_projet`), et il agit AVANT les",
        "familles : une aide de `restauration_travaux` seule n'est jamais proposée à un",
        "projet « faire vivre », taguée ou pas. Les familles ne trient que ce qui a",
        "déjà passé ce filtre.",
        "",
        f"Sur les {len(aides)} aides sans famille :",
        "",
        f"- **{len(faire_vivre)} sont atteignables par « Faire vivre »** (`raison` portant",
        "  `valorisation_rayonnement`, ou `raison` vide donc fail-open). Ce sont les",
        "  SEULES dont l'absence de famille coûte des questions hors sujet à un projet",
        "  d'animation — à traiter en premier.",
        f"- **{len(aides) - len(faire_vivre)} ne le sont pas** : les taguer reste utile,",
        "  mais pour autre chose — les facettes de la page projet (mode découverte) et",
        "  les projets ANCIENS multi-intentions, qui voient l'étape des activités et",
        "  dont `FAMILLES_PAR_RAISON` complète le cadrage.",
        "",
        f"{len(propositions)} proposition(s) au total, dont {len(nets)} « nettes »",
        "(périmètre, ou objet des travaux entièrement couvert) que `--appliquer` sait",
        f"écrire. {len(sans_signal)} aide(s) sans aucun signal.",
        "",
        "## Par provenance",
        "",
    ]
    par_provenance = Counter(p.provenance.split(" (")[0] for p in propositions)
    for provenance, n in par_provenance.most_common():
        lignes.append(f"- {provenance} : {n}")

    def tableau(titre: str, intro: list[str], slugs: list[str]) -> None:
        lignes.extend(["", titre, ""])
        lignes.extend(intro)
        lignes.extend(
            ["", "| Aide | Famille(s) | Provenance | Net | Verdict |", "|---|---|---|:-:|---|"]
        )
        for slug in slugs:
            p = par_slug[slug]
            libelles = ", ".join(f"`{f}`" for f in p.familles)
            lignes.append(f"| `{slug}` | {libelles} | {p.provenance} | {'✓' if p.net else ''} | |")

    tableau(
        f"## Propositions — les {len([s for s in par_slug if s in faire_vivre])} aides "
        "atteignables par « Faire vivre »",
        [
            "Les prioritaires : sans famille, chacune traîne ses questions dans TOUS les",
            "projets d'animation, quel que soit leur thème.",
        ],
        [s for s in sorted(par_slug) if s in faire_vivre],
    )
    tableau(
        f"## Propositions — les {len([s for s in par_slug if s not in faire_vivre])} autres",
        [
            "Hors de portée de « Faire vivre » (leur `raison` l'exclut). Les taguer ne",
            "sert qu'aux facettes et aux projets anciens multi-intentions : sans urgence.",
        ],
        [s for s in sorted(par_slug) if s not in faire_vivre],
    )

    lignes += [
        "",
        f"## Les {len(sans_signal)} aides sans aucun signal",
        "",
        "À trancher à la main, en relisant leur description. Laisser vide est une",
        "réponse valable : l'aide concerne alors tout projet. `FV` marque celles",
        "qu'un projet « faire vivre » peut atteindre.",
        "",
    ]
    for slug in sans_signal:
        aide = aides[slug]
        description = " ".join((aide.description or "").split())[:200]
        marque = "**FV** " if slug in faire_vivre else ""
        lignes.append(f"- {marque}`{slug}` — {description}")
    lignes += ["", "## Référentiel", ""]
    for code, libelle in FAMILLES_LABELS.items():
        lignes.append(f"- `{code}` — {libelle}")
    return "\n".join(lignes) + "\n"


# Un bloc `raison:` et ses puces, quelle que soit leur indentation (les
# fichiers passés par un `yaml.dump` historique n'indentent pas les tirets).
BLOC_RAISON = re.compile(r"^raison:\n(?:[ ]*-[ ].*\n)+", re.M)


def appliquer(slug: str, familles: list[str]) -> bool:
    """Insère `familles:` après le bloc `raison:`, par édition textuelle.

    Jamais de `yaml.dump` : les fichiers d'aides sont commentés, et un
    aller-retour par le loader YAML les effacerait tous.
    """
    chemin = AIDES_DIR / f"{slug}.yaml"
    texte = chemin.read_text(encoding="utf-8")
    if re.search(r"^familles:", texte, re.M):
        return False
    bloc = "familles:\n" + "".join(f"  - {f}\n" for f in familles)
    m = BLOC_RAISON.search(texte)
    if not m:
        return False
    chemin.write_text(texte[: m.end()] + bloc + texte[m.end() :], encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stdout", action="store_true", help="imprimer sans écrire la fiche")
    parser.add_argument(
        "--appliquer",
        action="store_true",
        help="écrire les propositions NETTES (périmètre, ou objet des travaux couvert)",
    )
    args = parser.parse_args()

    toutes = {p.stem: load_aide(p) for p in sorted(AIDES_DIR.glob("*.yaml"))}
    sans_famille = {slug: a for slug, a in toutes.items() if not a.familles}
    tri = charge_tri()
    propositions: list[Proposition] = []
    sans_signal: list[str] = []
    for slug, aide in sans_famille.items():
        p = proposer(aide, tri)
        if p is None:
            sans_signal.append(slug)
        else:
            propositions.append(p)

    if args.appliquer:
        ecrites = [p for p in propositions if p.net and appliquer(p.slug, p.familles)]
        print(f"{len(ecrites)} aide(s) taguée(s) — à relire au diff git :")
        for p in ecrites:
            print(f"  {p.slug} → {p.familles[0]}  ({p.provenance})")
        restantes = len(propositions) - len(ecrites) + len(sans_signal)
        print(f"{restantes} aide(s) restent à trancher à la main (relancer sans --appliquer)")
        return

    texte = fiche(sans_famille, propositions, sans_signal)
    if args.stdout:
        print(texte)
        return
    chemin = REVIEWS_DIR / f"{date.today().isoformat()}-proposition-familles.md"
    chemin.write_text(texte, encoding="utf-8")
    print(f"fiche écrite : {chemin.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
