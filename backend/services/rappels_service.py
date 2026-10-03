"""Rappels sur les aides d'un projet : quoi annoncer, et quand.

Deux familles d'évènements :

  * ÉCHÉANCE — une aide à portée dont la `dateLimite` approche. L'utilisateur
    choisit ses paliers (30 jours par défaut, plusieurs possibles). Lue dans
    le seul diagnostic du projet.
  * DISPONIBILITÉ — une aide devient déposable. Deux cas, une seule mécanique :
      - NOUVELLE : l'aide entre au catalogue (ingestion, typage achevé) et son
        guichet est ouvert ;
      - OUVERTURE : l'aide était fermée (« Disponibles bientôt ») et ne l'est
        plus, que sa `date_ouverture` soit atteinte ou que la veille ait posé
        les dates d'une nouvelle session.
    Rien ne se lit dans un diagnostic isolé : « vient de » suppose de savoir ce
    qui était vrai hier. D'où l'INSTANTANÉ du catalogue (`comparer_catalogue`),
    une ligne par aide, comparé chaque matin à l'état du jour. Le diagnostic
    du projet ne sert ensuite qu'à savoir à qui l'annoncer : l'aide doit être
    dans l'un des trois seaux du haut, ce qui veut dire qu'elle passe ses
    critères automatiques et qu'aucune réponse déjà donnée ne l'écarte.

Tout est pur : aucune I/O, aucun accès à Supabase, `today` toujours injecté.
Le script `scripts/rappels_aides.py` s'en sert pour décider quoi envoyer.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal

# Les trois seaux « à portée », ceux que la page projet affiche en haut. Une
# aide non éligible n'a pas d'échéance qui vaille un email.
BUCKETS_A_PORTEE: tuple[str, ...] = (
    "aidesEligibles",
    "aidesPotentiellementEligibles",
    "aidesAtteignables",
)

# Paliers de rappel par défaut, en jours avant la date limite.
PALIERS_DEFAUT: tuple[int, ...] = (30,)

# Bornes d'un palier saisi par l'utilisateur. Au-delà d'un an, le rappel
# précède le diagnostic ; en deçà de 0, il arrive après l'échéance.
PALIER_MIN = 0
PALIER_MAX = 365

# Une aide devenue disponible reste annonçable quelques jours. C'est le filet
# d'un envoi raté (Resend en panne, job qui n'a pas tourné) : le journal des
# envois empêche le doublon, la fenêtre laisse le rattrapage se faire. Un
# chantier créé entre-temps reçoit lui aussi l'annonce, ce qui est juste :
# l'aide vient bien d'ouvrir.
FENETRE_ANNONCE_JOURS = 7

# Libellé du seau d'arrivée, pour dire dans l'email OÙ l'aide vient d'atterrir.
LIBELLE_STATUT: dict[str, str] = {
    "eligible": "Éligible maintenant",
    "potentiel": "À confirmer",
    "atteignable": "À débloquer",
}


@dataclass(frozen=True)
class RappelEcheance:
    """Une aide à portée dont la date limite tombe dans `palier_jours` jours."""

    aide_id: str
    aide_nom: str
    statut: str
    montant_max: int | None
    date_limite: date
    jours_restants: int
    palier_jours: int


NatureDisponibilite = Literal["nouvelle", "ouverture"]


@dataclass(frozen=True)
class EtatAide:
    """Une ligne de l'instantané du catalogue (table `aides_veille_etat`).

    `entree_le` : le jour où le job a vu l'aide pour la première fois.
    `ouverte_depuis` : le jour où il l'a vue passer de fermée à ouverte, ou la
    voir entrer déjà ouverte. None tant qu'elle est fermée, et pour toutes les
    aides du tout premier passage, dont on ignore depuis quand elles le sont.
    """

    ouverte: bool
    entree_le: date
    ouverte_depuis: date | None


@dataclass(frozen=True)
class Disponibilite:
    """Une aide devenue déposable, à annoncer aux projets qui y ont droit."""

    aide_id: str
    nature: NatureDisponibilite
    depuis: date


@dataclass(frozen=True)
class RappelOuverture:
    """Une aide devenue disponible pour un projet, et le seau où elle atterrit."""

    aide_id: str
    aide_nom: str
    statut: str
    montant_max: int | None
    nature: NatureDisponibilite
    disponible_depuis: date
    date_limite: date | None


def normaliser_paliers(brut: object) -> tuple[int, ...]:
    """Nettoie les paliers venus des préférences utilisateur (jsonb libre).

    La colonne `notification_preferences` n'est qu'un jsonb : rien ne garantit
    ce qu'on y lit. On retient les entiers dans les bornes, sans doublon, du
    plus lointain au plus proche — et on retombe sur le défaut si la liste ne
    donne rien d'exploitable, plutôt que de priver l'utilisateur de rappels.
    """
    if not isinstance(brut, (list, tuple)):
        return PALIERS_DEFAUT
    valides: set[int] = set()
    for item in brut:
        # `bool` est un `int` en Python : True deviendrait un palier « 1 jour ».
        if isinstance(item, bool) or not isinstance(item, int):
            continue
        if PALIER_MIN <= item <= PALIER_MAX:
            valides.add(item)
    return tuple(sorted(valides, reverse=True)) or PALIERS_DEFAUT


def palier_courant(jours_restants: int, paliers: tuple[int, ...]) -> int | None:
    """Le palier auquel rattacher une échéance à `jours_restants` jours.

    C'est le plus PETIT palier encore à venir (le premier ≥ `jours_restants`),
    et cette règle vaut mieux qu'une égalité stricte pour deux raisons :

      * un job qui n'a pas tourné un matin ne fait pas sauter le rappel — le
        lendemain, le même palier est toujours le palier courant ;
      * un projet créé à J-10 reçoit tout de suite son rappel « 30 jours »,
        au lieu d'attendre une date déjà passée.

    Le journal des envois fait le reste : le palier ne se rappelle qu'une fois.
    Retourne None si l'échéance est passée, ou encore trop lointaine.
    """
    if jours_restants < 0:
        return None
    candidats = [p for p in paliers if p >= jours_restants]
    return min(candidats) if candidats else None


def _parse_date(valeur: object) -> date | None:
    """Date ISO du diagnostic (`aide_display_dict` sérialise en `YYYY-MM-DD`)."""
    if not isinstance(valeur, str) or not valeur:
        return None
    try:
        return date.fromisoformat(valeur[:10])
    except ValueError:
        return None


def matches_a_portee(diagnostic: dict) -> list[dict]:
    """Les matches des trois seaux du haut, dans l'ordre d'affichage."""
    matches: list[dict] = []
    for bucket in BUCKETS_A_PORTEE:
        for match in diagnostic.get(bucket) or []:
            if isinstance(match, dict) and isinstance(match.get("aide"), dict):
                matches.append(match)
    return matches


def echeances_a_rappeler(
    diagnostic: dict, today: date, paliers: tuple[int, ...]
) -> list[RappelEcheance]:
    """Aides à portée dont la date limite atteint un palier de rappel.

    Restreint aux aides déposables AUJOURD'HUI (`disponibilite == maintenant`) :
    une aide dont le guichet n'est pas encore ouvert n'a pas d'échéance qui
    presse, et une aide dont la session est passée est déjà en « bientôt ».
    Les dispositifs permanents n'ont pas de date limite et ne sortent jamais ici.
    """
    rappels: list[RappelEcheance] = []
    for match in matches_a_portee(diagnostic):
        if match.get("disponibilite", "maintenant") != "maintenant":
            continue
        aide = match["aide"]
        if aide.get("permanent"):
            continue
        date_limite = _parse_date(aide.get("dateLimite"))
        if date_limite is None:
            continue
        jours = (date_limite - today).days
        palier = palier_courant(jours, paliers)
        if palier is None:
            continue
        rappels.append(
            RappelEcheance(
                aide_id=str(aide.get("id")),
                aide_nom=str(aide.get("nom") or aide.get("nomCourt") or "Aide"),
                statut=str(match.get("statut") or ""),
                montant_max=aide.get("montantMax"),
                date_limite=date_limite,
                jours_restants=jours,
                palier_jours=palier,
            )
        )
    rappels.sort(key=lambda r: (r.jours_restants, r.aide_nom))
    return rappels


def comparer_catalogue(
    precedent: Mapping[str, EtatAide],
    ouvertes: Mapping[str, bool],
    today: date,
) -> dict[str, EtatAide]:
    """L'instantané du jour, à partir de celui de la veille.

    `ouvertes` : chaque aide du catalogue servi, et si son guichet est ouvert
    aujourd'hui (`disponibilite() == "maintenant"`).

    Un instantané VIDE est un premier passage : tout y entre sans date
    d'ouverture, donc rien ne s'annonce. Sans cette règle, le premier matin
    annoncerait le catalogue entier comme neuf.

    Une aide absente du jour (retirée, archivée) garde sa ligne telle quelle :
    si elle revient, elle n'est pas « nouvelle », et sa réouverture éventuelle
    se lit comme celle de n'importe quelle autre aide.
    """
    premier_passage = not precedent
    suivant = dict(precedent)
    for aide_id, ouverte in sorted(ouvertes.items()):
        avant = precedent.get(aide_id)
        if avant is None:
            suivant[aide_id] = EtatAide(
                ouverte=ouverte,
                entree_le=today,
                ouverte_depuis=today if ouverte and not premier_passage else None,
            )
        elif ouverte and not avant.ouverte:
            suivant[aide_id] = EtatAide(
                ouverte=True, entree_le=avant.entree_le, ouverte_depuis=today
            )
        elif not ouverte and avant.ouverte:
            suivant[aide_id] = EtatAide(
                ouverte=False, entree_le=avant.entree_le, ouverte_depuis=None
            )
    return suivant


def disponibilites_recentes(
    etat: Mapping[str, EtatAide],
    today: date,
    fenetre_jours: int = FENETRE_ANNONCE_JOURS,
) -> dict[str, Disponibilite]:
    """Les aides devenues disponibles depuis moins de `fenetre_jours` jours.

    NOUVELLE quand l'aide est entrée au catalogue le jour même où elle s'est
    ouverte, OUVERTURE sinon : une aide arrivée en « Disponibles bientôt »
    s'annonce le jour où son guichet ouvre, comme une réouverture.
    """
    dispos: dict[str, Disponibilite] = {}
    for aide_id, e in etat.items():
        if not e.ouverte or e.ouverte_depuis is None:
            continue
        ecart = (today - e.ouverte_depuis).days
        if ecart < 0 or ecart > fenetre_jours:
            continue
        nature: NatureDisponibilite = "nouvelle" if e.ouverte_depuis == e.entree_le else "ouverture"
        dispos[aide_id] = Disponibilite(aide_id=aide_id, nature=nature, depuis=e.ouverte_depuis)
    return dispos


def disponibles_pour_le_projet(
    diagnostic: dict, disponibilites: Mapping[str, Disponibilite]
) -> list[RappelOuverture]:
    """Parmi les aides devenues disponibles, celles qui valent pour ce projet.

    Le diagnostic du projet tranche : l'aide doit être dans l'un des trois
    seaux du haut, donc passer les critères automatiques de la fiche (région,
    département, protection, propriétaire…) sans qu'aucune réponse déjà donnée
    au questionnaire ne l'écarte. Un critère que le projet n'a jamais vu (le
    fait propre à une aide toute neuve) reste une incertitude : l'aide arrive
    en « À confirmer », et elle s'annonce.

    `disponibilite == maintenant` est revérifié ici : l'instantané dit que le
    guichet est ouvert pour le catalogue, le diagnostic le redit à la date du
    projet, et un désaccord (date figée en simulation) ne doit rien envoyer.
    """
    rappels: list[RappelOuverture] = []
    for match in matches_a_portee(diagnostic):
        if match.get("disponibilite", "maintenant") != "maintenant":
            continue
        aide = match["aide"]
        dispo = disponibilites.get(str(aide.get("id")))
        if dispo is None:
            continue
        rappels.append(
            RappelOuverture(
                aide_id=dispo.aide_id,
                aide_nom=str(aide.get("nom") or aide.get("nomCourt") or "Aide"),
                statut=str(match.get("statut") or ""),
                montant_max=aide.get("montantMax"),
                nature=dispo.nature,
                disponible_depuis=dispo.depuis,
                date_limite=_parse_date(aide.get("dateLimite")),
            )
        )
    # Les nouveautés d'abord, puis les plus récentes.
    rappels.sort(
        key=lambda o: (o.nature != "nouvelle", -o.disponible_depuis.toordinal(), o.aide_nom)
    )
    return rappels
