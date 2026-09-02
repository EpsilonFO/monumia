"""Rappels calendaires sur les aides d'un projet : quoi annoncer, et quand.

Deux évènements, tous deux lus dans le résultat d'un diagnostic déterministe :

  * ÉCHÉANCE — une aide à portée dont la `dateLimite` approche. L'utilisateur
    choisit ses paliers (30 jours par défaut, plusieurs possibles).
  * OUVERTURE — une aide qui patientait dans « Disponibles bientôt » et dont la
    `dateOuverture` vient d'être franchie. Le basculement vers « Éligible
    maintenant » / « À confirmer » / « À débloquer » n'a rien à déclencher : il
    se recalcule tout seul à chaque diagnostic (`disponibilite()` compare les
    dates du calendrier à la date du jour). Ce module ne fait que le CONSTATER
    pour pouvoir l'annoncer.

Tout est pur : aucune I/O, aucun accès à Supabase, `today` toujours injecté.
Le script `scripts/rappels_aides.py` s'en sert pour décider quoi envoyer.
"""

from dataclasses import dataclass
from datetime import date

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

# Une ouverture ne s'annonce que dans les jours qui suivent le franchissement.
# Sans cette fenêtre, le tout premier passage du job réveillerait l'historique
# entier : chaque aide ouverte depuis des années serait annoncée comme neuve.
# Sept jours laissent de la marge pour un job qui n'aurait pas tourné.
FENETRE_OUVERTURE_JOURS = 7

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


@dataclass(frozen=True)
class RappelOuverture:
    """Une aide dont le guichet vient d'ouvrir, et le seau où elle atterrit."""

    aide_id: str
    aide_nom: str
    statut: str
    montant_max: int | None
    date_ouverture: date
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


def ouvertures_franchies(
    diagnostic: dict, today: date, fenetre_jours: int = FENETRE_OUVERTURE_JOURS
) -> list[RappelOuverture]:
    """Aides dont la date d'ouverture vient d'être franchie.

    Le signal est double : la `dateOuverture` est atteinte, ET l'aide est
    effectivement passée en « maintenant » — c'est-à-dire qu'elle a bien quitté
    « Disponibles bientôt » pour l'un des trois seaux du haut. Une aide ouverte
    mais dont la date limite est déjà passée reste en « bientôt » et n'annonce
    donc rien : il n'y aurait rien à déposer.

    La fenêtre borne le rattrapage. Elle laisse hors du champ le cas d'une aide
    qui rebasculerait en « maintenant » sans date d'ouverture (une session
    reconduite dont seule la date limite est repoussée) : rien ne dit alors
    quel jour le guichet a rouvert.
    """
    ouvertures: list[RappelOuverture] = []
    for match in matches_a_portee(diagnostic):
        if match.get("disponibilite", "maintenant") != "maintenant":
            continue
        aide = match["aide"]
        date_ouverture = _parse_date(aide.get("dateOuverture"))
        if date_ouverture is None:
            continue
        ecart = (today - date_ouverture).days
        if ecart < 0 or ecart > fenetre_jours:
            continue
        ouvertures.append(
            RappelOuverture(
                aide_id=str(aide.get("id")),
                aide_nom=str(aide.get("nom") or aide.get("nomCourt") or "Aide"),
                statut=str(match.get("statut") or ""),
                montant_max=aide.get("montantMax"),
                date_ouverture=date_ouverture,
                date_limite=_parse_date(aide.get("dateLimite")),
            )
        )
    ouvertures.sort(key=lambda o: (-o.date_ouverture.toordinal(), o.aide_nom))
    return ouvertures
