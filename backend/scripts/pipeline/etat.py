"""La file d'attente des aides à ingérer : `data/prospection/file-attente.yaml`.

Un dict YAML à clé = slug, trié, versionné — même idiome que
`data/veille-state.yaml`, et pour la même raison : c'est le diff git qui rend
lisible ce que la prospection a proposé et ce que l'ingestion en a fait.

Le cycle d'un slug :

    a_valider ──(prospecter.py valider)──> valide ──> en_cours ──> ingere
        │                                                │
        └──(prospecter.py ignorer)──> ignore             └──────> echec

`a_valider` est le point de contrôle humain : la prospection ne décide jamais
seule d'ingérer. `--auto` le franchit sans attendre, c'est son seul effet.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict

from .verrou import ecrire_atomique, verrou_fichier

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BACKEND_DIR / "data"
PROSPECTION_DIR = DATA_DIR / "prospection"
FILE_ATTENTE = PROSPECTION_DIR / "file-attente.yaml"

Statut = Literal["a_valider", "valide", "ignore", "en_cours", "ingere", "echec"]
STATUTS: tuple[str, ...] = ("a_valider", "valide", "ignore", "en_cours", "ingere", "echec")

Priorite = Literal["haute", "normale", "basse"]

# --- Le test du destinataire (SKILL prospecter, Étape 3) -------------------
#
# À qui la source s'adresse-t-elle, et en quelle qualité ? C'est ce couple, et
# lui seul, qui décide de l'entrée au catalogue : une aide à une troupe de
# théâtre est l'aide de la troupe, pas celle du propriétaire qui l'accueille.
# Le thème, lui, reste large — c'est la famille qui le porte.
#
# `indetermine` est le DÉFAUT des deux, et ce n'est pas de la prudence
# décorative : une tâche indéterminée reste `a_valider`, donc sous les yeux d'un
# humain, au lieu d'être promue en silence. Un modèle qui oublie le champ ne
# doit pas faire entrer l'aide.
Destinataire = Literal["proprietaire_gestionnaire", "activite_tiers", "personne", "indetermine"]
DESTINATAIRES: tuple[str, ...] = (
    "proprietaire_gestionnaire",
    "activite_tiers",
    "personne",
    "indetermine",
)

Objet = Literal["bien_ou_lieu", "activite_dans_le_lieu", "hors_lieu", "indetermine"]
OBJETS: tuple[str, ...] = ("bien_ou_lieu", "activite_dans_le_lieu", "hors_lieu", "indetermine")

#: Les cinq catégories d'exclusion observées sur le lot des quatre régions,
#: plus les deux formes (un guide-agrégat n'est pas un dispositif ; une dépense
#: sans rapport avec le lieu ne l'est pas davantage). Sert à TRIER la fiche de
#: tri, pas à décider : la décision est le couple destinataire × objet.
CategorieEcart = Literal[
    "metier_agricole",
    "entreprise_generale",
    "organisateur_artiste",
    "pratique_amateur",
    "aide_personne",
    "non_dispositif",
    "objet_hors_lieu",
]
CATEGORIES_ECART: tuple[str, ...] = (
    "metier_agricole",
    "entreprise_generale",
    "organisateur_artiste",
    "pratique_amateur",
    "aide_personne",
    "non_dispositif",
    "objet_hors_lieu",
)

#: Les deux objets qu'un propriétaire porte lui-même, pour son lieu.
OBJETS_RETENUS: frozenset[str] = frozenset({"bien_ou_lieu", "activite_dans_le_lieu"})


def retenir(destinataire: str, objet: str) -> bool:
    """Le test du destinataire, au seul endroit où il s'écrit.

    Calculé, jamais rendu par le modèle : `retenir: true` était la valeur par
    défaut de la lecture, et 57 % des candidates douteuses du tri passaient ainsi
    en retenues (497 sur 869). Demander deux jugements descriptifs — à QUI, et
    sur QUOI — et en dériver la décision retire au modèle la possibilité de
    dire « oui » par défaut : il faudrait qu'il se trompe deux fois, sur deux
    questions dont la seconde ne suggère aucune réponse.
    """
    return destinataire == "proprietaire_gestionnaire" and objet in OBJETS_RETENUS


class Ingestion(BaseModel):
    """Ce que le dernier passage d'ingestion a produit pour ce slug.

    Absent du YAML tant que rien n'a tourné. Toujours FUSIONNÉ et jamais
    remplacé en bloc : `tentatives` doit survivre à une reprise, sinon un slug
    qui échoue en boucle ne se distingue plus d'un slug neuf.
    """

    model_config = ConfigDict(extra="forbid")

    debut: str | None = None
    fin: str | None = None
    modele: str | None = None
    modele_verif: str | None = None
    tours: int | None = None
    cout_usd: float | None = None
    review: str | None = None
    motif_echec: str | None = None
    tentatives: int = 0


class Tache(BaseModel):
    """Une aide candidate : d'où elle vient, où elle en est."""

    model_config = ConfigDict(extra="forbid")

    titre: str
    url: str
    # Documents à snapshoter en plus de la page (règlement, cadre d'intervention).
    urls_pdf: list[str] = []
    territoire: str
    # Les départements que cette tâche couvre, quand le territoire en couvre
    # plusieurs : la Collectivité européenne d'Alsace instruit pour le 67 ET le
    # 68, et 17 de ses dispositifs sont entrés deux fois au catalogue faute de
    # le dire. Dicté au modèle pour qu'il écrive `hard_filters.departements`.
    departements: list[str] = []
    famille: str | None = None
    # Qui peut déposer, d'après la page de prospection. Transmis tel quel à
    # l'ingestion, qui doit le VÉRIFIER sur la source et le typer en gate
    # `statut_juridique_porteur` : cette donnée était lue à la prospection puis
    # perdue entre la fiche markdown et la file.
    beneficiaires: str | None = None
    # Le verdict du test du destinataire, tel que la lecture l'a rendu. Ces deux
    # champs GOUVERNENT la promotion (`promouvables`) : ils ne sont pas une
    # annotation, c'est le point de contrôle qui manquait entre le tri et
    # l'écriture des YAML.
    destinataire: Destinataire = "indetermine"
    objet: Objet = "indetermine"
    categorie_ecart: CategorieEcart | None = None
    # Ce que la lecture a compris de l'aide, en une phrase. Écrit depuis
    # toujours dans les `lectures.jsonl` et dans la fiche markdown, jamais
    # transmis à l'ingestion (`worker.ingerer_aide` passait `note=None`) : 56
    # notes disaient « retenu par défaut » et 48 « doute sérieux » sans que
    # l'agent d'ingestion en sache rien. C'est la matière de l'`applies_if` de
    # périmètre qu'une aide hors `restauration_bati` doit porter.
    note: str | None = None
    # Deux signaux que la lecture produisait et que la file perdait.
    doublon_probable: str | None = None
    source_unique_vulgarisation: bool = False
    priorite: Priorite = "normale"
    statut: Statut = "a_valider"
    # Posé par l'ingestion quand la review a été écrite au plafond de
    # vérifications, bloquants non re-vérifiés : c'est la liste de relecture
    # humaine, et elle doit survivre au run qui l'a produite.
    a_relire: bool = False
    # Pourquoi cette tâche est `ignore` : hors périmètre (avec sa catégorie),
    # doublon d'URL, décision humaine. Sans motif, un `ignore` est
    # indistinguable d'un oubli et reviendra au balayage suivant.
    motif_ignore: str | None = None
    doublon_de: str | None = None
    ajoute_le: date | None = None
    # Fiche de prospection qui l'a proposée, chemin relatif à backend/.
    fiche: str | None = None
    ingestion: Ingestion | None = None

    @property
    def retenue(self) -> bool:
        """Le test du destinataire appliqué à cette tâche."""
        return retenir(self.destinataire, self.objet)


def _en_yaml(taches: dict[str, Tache]) -> str:
    brut: dict[str, Any] = {}
    for slug, tache in taches.items():
        # `mode="json"` pour que les dates sortent en chaînes ISO plutôt qu'en
        # objets `datetime.date`, que `safe_dump` écrirait sans guillemets.
        donnees = tache.model_dump(mode="json")
        # Les champs vides du haut de fiche disparaissent (bruit dans le diff) ;
        # ceux du bloc `ingestion` restent, `motif_echec: null` compris — c'est
        # là qu'on veut lire explicitement « aucun motif d'échec ».
        #
        # `False` et `[]` s'omettent au même titre que `None` : sans ça, les dix
        # champs ajoutés en 2026-09 écriraient `a_relire: false`,
        # `source_unique_vulgarisation: false` et `departements: []` sur les
        # 1 234 entrées de la file, et le diff d'une ingestion deviendrait
        # illisible. Ce qui est absent vaut le défaut du modèle, qui est
        # précisément la valeur omise.
        brut[slug] = {
            k: v for k, v in donnees.items() if v is not None and v is not False and v != []
        }
    return yaml.safe_dump(brut, allow_unicode=True, sort_keys=True, width=1000)


def charger(chemin: Path = FILE_ATTENTE) -> dict[str, Tache]:
    """Fichier absent ou vide ⇒ file vide (premier run)."""
    if not chemin.exists():
        return {}
    brut = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    return {slug: Tache.model_validate(valeur) for slug, valeur in brut.items()}


def ecrire(chemin: Path, taches: dict[str, Tache]) -> None:
    ecrire_atomique(chemin, _en_yaml(taches))


def fusionner(chemin: Path, nouvelles: dict[str, Tache]) -> list[str]:
    """Ajoute les slugs inconnus, laisse les connus tranquilles. Renvoie les ajoutés.

    Non destructive par construction : une seconde prospection du même
    territoire re-propose forcément les mêmes dispositifs, et écraser leur
    `statut` remettrait à `a_valider` des aides déjà ingérées — ou pire,
    effacerait un `ignore` que l'utilisateur avait posé à la main.

    Seul `urls_pdf` est COMPLÉTÉ sur une tâche existante : un règlement PDF
    découvert au second passage est une information neuve, et l'ajouter ne
    contredit aucune décision humaine.
    """
    with verrou_fichier(chemin):
        courant = charger(chemin)
        ajoutes: list[str] = []
        for slug, tache in nouvelles.items():
            existante = courant.get(slug)
            if existante is None:
                courant[slug] = tache
                ajoutes.append(slug)
                continue
            manquants = [u for u in tache.urls_pdf if u not in existante.urls_pdf]
            if manquants:
                courant[slug] = existante.model_copy(
                    update={"urls_pdf": [*existante.urls_pdf, *manquants]}
                )
        ecrire(chemin, courant)
    return ajoutes


def mettre_a_jour(chemin: Path, slug: str, **champs: Any) -> Tache:
    """Modifie une tâche sous verrou (relit, modifie, réécrit). Renvoie la tâche à jour.

    `ingestion` est le seul champ FUSIONNÉ plutôt que remplacé : le worker
    n'écrit que ce qu'il vient d'apprendre (le coût à la fin, le motif d'échec
    en cas de rejet) et ne doit pas effacer ce que la tentative précédente
    avait consigné.
    """
    with verrou_fichier(chemin):
        courant = charger(chemin)
        tache = courant.get(slug)
        if tache is None:
            raise KeyError(f"slug absent de la file d'attente : {slug}")
        if "ingestion" in champs:
            fusion = champs["ingestion"]
            if isinstance(fusion, Ingestion):
                fusion = fusion.model_dump(exclude_unset=True)
            base = tache.ingestion.model_dump() if tache.ingestion else {}
            champs = {**champs, "ingestion": Ingestion.model_validate({**base, **(fusion or {})})}
        maj = Tache.model_validate({**tache.model_dump(), **champs})
        courant[slug] = maj
        ecrire(chemin, courant)
    return maj


def transition(chemin: Path, slug: str, vers: Statut, *, depuis: Sequence[str]) -> bool:
    """Change le statut SI le statut courant est l'un de `depuis`, sinon False.

    C'est le jeton qui empêche deux orchestrateurs de prendre la même aide :
    `transition(..., "en_cours", depuis=("valide",))` est atomique sous le
    verrou, donc un seul des deux l'obtient. Un `False` n'est pas une erreur,
    c'est « quelqu'un d'autre l'a déjà ».
    """
    with verrou_fichier(chemin):
        courant = charger(chemin)
        tache = courant.get(slug)
        if tache is None or tache.statut not in depuis:
            return False
        courant[slug] = tache.model_copy(update={"statut": vers})
        ecrire(chemin, courant)
    return True


def selectionner(
    etat: dict[str, Tache],
    *,
    statuts: Iterable[str] = ("valide",),
    territoires: Iterable[str] | None = None,
    slugs: Iterable[str] | None = None,
) -> list[str]:
    """Slugs retenus, triés par priorité (haute d'abord) puis par ordre alphabétique."""
    voulus = set(statuts)
    filtre_terr = set(territoires) if territoires else None
    filtre_slugs = set(slugs) if slugs else None
    rang = {"haute": 0, "normale": 1, "basse": 2}
    retenus = [
        slug
        for slug, t in etat.items()
        if t.statut in voulus
        and (filtre_terr is None or t.territoire in filtre_terr)
        and (filtre_slugs is None or slug in filtre_slugs)
    ]
    return sorted(retenus, key=lambda s: (rang[etat[s].priorite], s))


# ---------------------------------------------------------------------------
# Promotion : ce qui a le droit de passer en `valide`
# ---------------------------------------------------------------------------

#: Les deux familles qui ne sont pas un classement mais un aveu d'incertitude.
#: `adjacente` est le DÉFAUT du tri comme de la lecture : promouvoir sur cette
#: valeur, c'est promouvoir parce que personne n'a tranché.
FAMILLES_NON_PROMOUVABLES: frozenset[str] = frozenset({"adjacente", "hors_perimetre"})


def motif_non_promotion(tache: Tache) -> str | None:
    """Pourquoi cette tâche reste `a_valider`, ou `None` si elle peut passer.

    Un motif plutôt qu'un booléen : `prospecter.py valider` sans slug l'imprime
    en face de chaque restante, et c'est ce qui rend le point de contrôle
    humain praticable. Une liste de 140 slugs sans motif ne se relit pas.
    """
    if tache.statut != "a_valider":
        return f"statut {tache.statut}"
    if tache.destinataire == "indetermine" or tache.objet == "indetermine":
        return "destinataire ou objet indéterminé — à trancher à la main"
    if not tache.retenue:
        categorie = f" ({tache.categorie_ecart})" if tache.categorie_ecart else ""
        return f"hors périmètre : destinataire {tache.destinataire}, objet {tache.objet}{categorie}"
    if (tache.famille or "adjacente") in FAMILLES_NON_PROMOUVABLES:
        return f"famille {tache.famille or 'adjacente'} — à ranger avant d'ingérer"
    return None


def promouvables(taches: dict[str, Tache], cles: Iterable[str], *, tout: bool = False) -> list[str]:
    """Parmi `cles`, les slugs qui peuvent passer de `a_valider` à `valide`.

    C'est le point de contrôle qui manquait : `valider_en_attente` promouvait
    TOUT ce qui était `a_valider`, y compris les 140 candidates que le tri avait
    rangées `adjacente` et les 5 qu'il avait dites `hors_perimetre`. 643 aides
    sont entrées au catalogue sans qu'aucun humain ni aucune règle ne se soit
    interposé entre le tri et l'écriture des YAML.

    `tout=True` rend l'ancien comportement, et il a un usage légitime : une
    file relue et corrigée à la main, dont l'utilisateur assume la promotion en
    bloc. Ce n'est plus le défaut.
    """
    voulus = [c for c in cles if c in taches]
    if tout:
        return sorted(c for c in voulus if taches[c].statut == "a_valider")
    return sorted(c for c in voulus if motif_non_promotion(taches[c]) is None)


# ---------------------------------------------------------------------------
# Doublons d'URL
# ---------------------------------------------------------------------------

#: Qui survit à une collision d'URL, du plus fort au plus faible. Un `ingere`
#: gagne toujours : le YAML existe, l'écarter perdrait le travail payé.
_RANG_SURVIE = {"ingere": 0, "en_cours": 1, "valide": 2, "a_valider": 3, "echec": 4, "ignore": 5}


def doublons_par_url(taches: dict[str, Tache], *, cle=None) -> dict[str, str]:
    """slug écarté → slug survivant, pour toute la file groupée par URL de fiche.

    `collecte.dedoublonner` ne dédoublonne qu'à l'étage 1, contre le catalogue
    et contre la file au moment du balayage. Ça ne suffit pas : 51 aides déjà
    au catalogue sont revenues en `-2` avec la MÊME URL, parce que
    `lecture.slug_final` résout une collision de slug par un suffixe numérique
    au lieu d'y voir un doublon, et parce qu'un `--rejouer` repasse derrière le
    dédoublonnage. D'où ce second filet, qui regarde la file ENTIÈRE juste avant
    la promotion.

    Le groupement se fait sur `cle_fiche` (importée paresseusement : c'est
    `prospection.collecte` qui la porte, et ce module-ci est SON import). Les
    paramètres de pagination en sont retirés, sans quoi les trois pages d'un
    même dispositif Typo3 (`?tx_news_pi1[currentPage]=1&cHash=…`) restent trois
    fiches distinctes.
    """
    if cle is None:
        from prospection.collecte import cle_fiche as cle

    groupes: dict[str, list[str]] = {}
    for slug, tache in taches.items():
        groupes.setdefault(cle(tache.url), []).append(slug)

    ecartes: dict[str, str] = {}
    for membres in groupes.values():
        if len(membres) < 2:
            continue
        survivant = min(
            membres,
            key=lambda s: (
                _RANG_SURVIE.get(taches[s].statut, 9),
                taches[s].ajoute_le or date.max,
                s,
            ),
        )
        for slug in membres:
            if slug != survivant:
                ecartes[slug] = survivant
    return ecartes


__all__ = [
    "CATEGORIES_ECART",
    "DATA_DIR",
    "DESTINATAIRES",
    "FAMILLES_NON_PROMOUVABLES",
    "FILE_ATTENTE",
    "OBJETS",
    "OBJETS_RETENUS",
    "PROSPECTION_DIR",
    "STATUTS",
    "CategorieEcart",
    "Destinataire",
    "Ingestion",
    "Objet",
    "Priorite",
    "Statut",
    "Tache",
    "charger",
    "doublons_par_url",
    "ecrire",
    "fusionner",
    "mettre_a_jour",
    "motif_non_promotion",
    "promouvables",
    "retenir",
    "selectionner",
    "transition",
]
