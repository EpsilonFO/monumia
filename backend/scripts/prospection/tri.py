"""Étage 2 : trier au kilo, sans ouvrir les pages.

Une région rend deux à trois cents URL de dispositifs, dont dix à vingt
intéressent un propriétaire de monument. Les ouvrir toutes coûterait autant que
l'ingestion elle-même : on trie d'abord sur le titre et l'extrait, par lots, et
on n'ouvre (étage 3) que les retenues et les douteuses.

La doctrine du tri n'est pas écrite ici : elle est EXTRAITE du skill
`prospecter-aides-region` (les étapes « Le spectre » et « Le test
d'admission »), comme le prompt d'ingestion l'est du sien. Une seule source de
vérité pour ce qu'on retient et ce qu'on écarte.

Cinq précautions, toutes apprises du même travers des modèles en lot :
  - une URL absente de la réponse devient `douteux`, jamais `ecarter` — un
    oubli ne doit pas se lire comme un refus ;
  - une URL inventée est ignorée ;
  - un lot en échec passe en entier en `douteux`, et l'étage 3 tranchera ;
  - un `ecarter` prononcé sur une candidate SANS titre ni contexte redevient
    `douteux` : c'est la seule décision irréversible du pipeline, et la prendre
    sur un slug d'URL a coûté 173 pages jamais ouvertes le 2026-09-08 ;
  - une décision autre qu'`ecarter` ne peut pas être rangée `hors_perimetre`.

Les deux dernières sont des garde-fous du CODE, pas du prompt : la consigne les
dit aussi, mais un modèle en lot de 25 n'en fait qu'à sa tête une fois sur dix.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import providall
from pipeline.llm import Compteur

from aides_schema import Aide

from .collecte import Candidat
from .territoires import Territoire

TAILLE_LOT = 25

# Motif posé par le code, jamais par le modèle : la fiche compte les
# requalifications dessus, et `--rejouer` doit les retrouver dans tri.jsonl.
MOTIF_SANS_TITRE = "écart sur l'URL seule, sans titre ni contexte, requalifié en douteux"

Famille = Literal[
    "restauration_bati",
    "energie_climat",
    "eau_nature_domaine",
    "securite_risques",
    "parcs_jardins_paysages",
    "hebergement_touristique",
    "tourisme_visite",
    "activite_economique_lieu",
    "spectacles_manifestations",
    "vie_locale_associative",
    "mediation_numerique_expositions",
    "accessibilite_publics",
    "etudes_ingenierie",
    "labels_passerelles",
    "adjacente",
    "hors_perimetre",
]

# Le `Literal` seul ne dit rien au modèle : « eau_nature_domaine » ne se devine
# pas, et une famille mal comprise est une aide rangée n'importe où. La
# description tient sur une ligne et part dans les deux prompts.
FAMILLES_DESCRIPTION: dict[str, str] = {
    "restauration_bati": (
        "travaux sur le bâti, protégé ou non, y compris le mobilier attaché "
        "(orgues, cloches, vitraux)"
    ),
    "energie_climat": (
        "rénovation énergétique, chauffage et énergies renouvelables (géothermie, bois, "
        "réseaux de chaleur, solaire), adaptation au changement climatique, matériaux "
        "biosourcés, AMO énergie"
    ),
    "eau_nature_domaine": (
        "eau et sécheresse, cours d'eau et plans d'eau (moulins, douves, étangs), "
        "biodiversité, Natura 2000, vergers, haies, mares — quand l'aide s'adresse aux "
        "PROPRIÉTAIRES. Ni production agricole ou viticole, ni élevage, ni filière : ce "
        "sont les aides d'un métier. NI LA FORÊT, entièrement écartée depuis le "
        "2026-09-22 (sylviculture, boisement, desserte, filière bois) — le bois ÉNERGIE "
        "qui chauffe un bâtiment relève d'energie_climat, pas d'ici"
    ),
    "securite_risques": (
        "catastrophes naturelles, inondations, incendie, foudre, sûreté, mise en sécurité"
    ),
    "parcs_jardins_paysages": "parcs et jardins, arbres, paysages, abords",
    "hebergement_touristique": (
        "l'HÉBERGEMENT lui-même : gîte, chambre d'hôtes, meublé, hôtel, hostel, "
        "hébergement collectif, hôtellerie de plein air, insolite"
    ),
    "tourisme_visite": (
        "le lieu OUVERT À LA VISITE et ce qui l'entoure : mise en tourisme, accueil des "
        "visiteurs, itinérance et randonnée, évènementiel touristique, promotion et "
        "stratégie touristique d'un territoire. Scindé de l'hébergement le 2026-09-22 : "
        "un gîte et un sentier de randonnée ne posent pas les mêmes questions"
    ),
    "activite_economique_lieu": (
        "reconversion et nouvel usage, tiers-lieux, commerce, artisanat ou ESS installés "
        "dans le lieu : l'immobilier, l'aménagement et l'équipement du LIEU. Ni prêt "
        "d'honneur, ni garantie, ni innovation, ni transmission, ni croissance TPE — un "
        "château-hôtel est une PME, mais l'aide aux PME est l'aide d'un métier"
    ),
    "spectacles_manifestations": (
        "le LIEU qui accueille : salle de diffusion, aménagement acoustique, résidence "
        "dans le lieu, programmation portée par le propriétaire. Ni la compagnie, ni "
        "l'artiste, ni le festival organisateur, ni la pratique amateur"
    ),
    "vie_locale_associative": (
        "une association GESTIONNAIRE pour son lieu (locaux, investissement immobilier, "
        "événement patrimonial dans le lieu), une commune pour son bâti, la mémoire "
        "locale qu'elle porte. Ni le fonctionnement ni les activités des associations "
        "en général, ni la formation des bénévoles, ni le sport"
    ),
    "mediation_numerique_expositions": (
        "signalétique, scénographie, numérique, expositions, publications, inventaire"
    ),
    "accessibilite_publics": "accessibilité, accueil des publics, handicap",
    "etudes_ingenierie": "études préalables, diagnostics, ingénierie, AMO",
    "labels_passerelles": "labels et dispositifs qui ouvrent l'accès à d'autres aides",
    "adjacente": "utile au monument sans entrer dans une famille ci-dessus : à garder",
    "hors_perimetre": "absolument rien à voir (voir la liste fermée du skill)",
}
FAMILLES: tuple[str, ...] = tuple(FAMILLES_DESCRIPTION)


def familles_rendues() -> str:
    return "\n".join(f"  {f} : {d}" for f, d in FAMILLES_DESCRIPTION.items())


Decision = Literal["retenir", "ecarter", "douteux"]

SKILL_PROSPECTION = (
    Path(__file__).resolve().parent.parent.parent.parent
    / ".claude"
    / "skills"
    / "prospecter-aides-region"
    / "SKILL.md"
)


class TriCandidat(BaseModel):
    url: str
    decision: Decision
    # `adjacente` et non `hors_perimetre` : une décision autre qu'`ecarter` ne
    # peut pas être « rien à voir », et le défaut se lit tel quel dans la fiche.
    famille: Famille = "adjacente"
    motif: str = Field(default="", description="Une phrase : pourquoi cette décision")


class Lot(BaseModel):
    resultats: list[TriCandidat] = []


def doctrine(skill_path: Path = SKILL_PROSPECTION) -> str:
    """Le spectre et le test d'admission, extraits du skill de prospection."""
    from ingestion.contexte import section

    md = skill_path.read_text(encoding="utf-8")
    return "\n\n".join(
        [
            section(md, "Étape 2").rstrip(),
            section(md, "Étape 3").rstrip(),
        ]
    )


def prompt_systeme(
    territoire: Territoire, existantes: dict[str, Aide], skill_path: Path = SKILL_PROSPECTION
) -> str:
    """Doctrine du skill + ce que le catalogue contient DÉJÀ pour ce territoire.

    La liste des aides déjà ingérées n'est pas décorative : sans elle, le modèle
    retient consciencieusement des dispositifs que la fiche re-proposera et que
    l'humain devra écarter un par un.
    """
    deja = (
        "\n".join(f"  {slug} — {aide.nom}" for slug, aide in sorted(existantes.items()))
        or "  (aucune)"
    )
    return "\n\n".join(
        [
            doctrine(skill_path),
            "---",
            "# Familles (champ `famille`)\n" + familles_rendues(),
            f"# Territoire prospecté : {territoire.nom}",
            "Aides DÉJÀ présentes dans le catalogue pour ce territoire — les écarter\n"
            "si tu les reconnais (`decision: ecarter`, motif « déjà au catalogue ») :\n" + deja,
            "# Ta tâche\n\n"
            "Pour CHAQUE URL de la liste qui suit, rends une décision. Tu ne vois que\n"
            "le titre du lien et sa ligne de contexte : quand cela ne suffit pas pour\n"
            "trancher, réponds `douteux` — la page sera ouverte et le test du\n"
            "destinataire appliqué pour de bon à l'étape suivante. `douteux` est une\n"
            "réponse normale et peu coûteuse ; `ecarter` à tort fait perdre une aide\n"
            "définitivement.\n\n"
            "Quand le titre ET le contexte sont vides, tu ne sais RIEN de la page :\n"
            "`ecarter` est alors interdit, réponds `douteux`. Le code convertira de\n"
            "toute façon.\n\n"
            "À ce stade, `ecarter` est réservé à deux cas, et à eux seuls :\n"
            "  - le titre NOMME un métier ou une activité tierce — « installation des\n"
            "    jeunes agriculteurs », « aide aux compagnies professionnelles »,\n"
            "    « prêt d'honneur création d'entreprise », « concours de pâtisserie »,\n"
            "    « bourse d'écriture », « chorales et fanfares » : l'aide s'adresse à\n"
            "    ce métier, pas au propriétaire d'un lieu ;\n"
            "  - le titre montre que l'aide n'a ABSOLUMENT rien à voir avec un\n"
            "    monument, son domaine, une activité qui s'y tient ou la structure qui\n"
            "    le porte.\n\n"
            "Pour tout le reste, `douteux` — y compris quand tu penses que la page\n"
            "sera finalement écartée : c'est la lecture qui juge le destinataire, pas\n"
            "toi. Ne réserve `retenir` qu'aux titres où le lieu ou son propriétaire\n"
            "est manifestement le destinataire.\n"
            "Rends une entrée par URL, avec l'URL RECOPIÉE À L'IDENTIQUE.",
        ]
    )


def lots(candidats: list[Candidat], taille: int = TAILLE_LOT) -> Iterator[list[Candidat]]:
    for debut in range(0, len(candidats), taille):
        yield candidats[debut : debut + taille]


def _rendre_lot(lot: list[Candidat]) -> str:
    return "\n\n".join(
        f"URL : {c.url}\nTitre : {c.titre or '(sans titre)'}\nContexte : {c.extrait or '(aucun)'}"
        for c in lot
    )


def sans_information(c: Candidat) -> bool:
    """Ni titre ni contexte : la seule chose connue de cette page est son URL."""
    return not c.titre.strip() and not c.extrait.strip()


def trier_lot(
    lot: list[Candidat],
    client: providall.Client,
    systeme: str,
    *,
    compteur: Compteur | None = None,
) -> list[TriCandidat]:
    """Trie un lot. Ne lève jamais : en cas d'échec, tout le lot devient douteux."""
    essai = client.try_complete_json(Lot, _rendre_lot(lot), system=systeme)
    if compteur is not None:
        compteur.ajouter(essai.response, "tri")
    connues = {c.url for c in lot}
    if essai.data is None:
        return [
            TriCandidat(url=c.url, decision="douteux", motif="lot non trié (modèle indisponible)")
            for c in lot
        ]
    # Les URL inventées sont jetées, les oubliées deviennent douteuses : dans
    # les deux cas le tri ne peut que retarder une décision, jamais en prendre
    # une que le modèle n'a pas prise.
    par_url = {r.url: r for r in essai.data.resultats if r.url in connues}
    sortie: list[TriCandidat] = []
    for c in lot:
        t = par_url.get(
            c.url,
            TriCandidat(url=c.url, decision="douteux", motif="absente de la réponse du modèle"),
        )
        # Une élimination est la seule décision irréversible du pipeline. Prise
        # sur un slug d'URL, elle a perdu sécheresse, géothermie et Natura 2000
        # le 2026-09-08 : sans titre ni contexte, elle redevient un doute.
        if t.decision == "ecarter" and sans_information(c):
            t = t.model_copy(
                update={"decision": "douteux", "motif": f"{MOTIF_SANS_TITRE} ({t.motif})"}
            )
        # « On la garde, mais elle n'a rien à voir » ne veut rien dire : la
        # fiche la rangerait sous une famille qui dit le contraire de la
        # décision.
        if t.decision != "ecarter" and t.famille == "hors_perimetre":
            t = t.model_copy(update={"famille": "adjacente"})
        sortie.append(t)
    return sortie


def trier(
    candidats: list[Candidat],
    territoire: Territoire,
    existantes: dict[str, Aide],
    client: providall.Client,
    *,
    compteur: Compteur | None = None,
    taille_lot: int = TAILLE_LOT,
    skill_path: Path = SKILL_PROSPECTION,
    progression: Callable[[int, int, list[TriCandidat]], None] | None = None,
) -> list[TriCandidat]:
    """Trie tous les lots. `progression(i, n, tries_du_lot)` est appelé après chacun.

    Dix appels séquentiels de 30 à 40 s sans un mot : le 2026-09-08, un
    balayage de 239 candidats a paru bloqué pendant vingt minutes alors qu'il
    avançait normalement. Le rappel sert à le dire.
    """
    systeme = prompt_systeme(territoire, existantes, skill_path)
    resultats: list[TriCandidat] = []
    tous = list(lots(candidats, taille_lot))
    for i, lot in enumerate(tous, 1):
        tries = trier_lot(lot, client, systeme, compteur=compteur)
        resultats += tries
        if progression is not None:
            progression(i, len(tous), tries)
    return resultats


def a_lire(tries: list[TriCandidat]) -> list[str]:
    """Les URL que l'étage 3 doit ouvrir : retenues et douteuses."""
    return [t.url for t in tries if t.decision in ("retenir", "douteux")]


__all__ = [
    "FAMILLES",
    "FAMILLES_DESCRIPTION",
    "MOTIF_SANS_TITRE",
    "SKILL_PROSPECTION",
    "TAILLE_LOT",
    "Decision",
    "Famille",
    "Lot",
    "TriCandidat",
    "a_lire",
    "doctrine",
    "familles_rendues",
    "lots",
    "prompt_systeme",
    "sans_information",
    "trier",
    "trier_lot",
]
