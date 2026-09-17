"""Faits DURABLES d'un monument — ce qu'un nouveau projet n'a pas à redemander.

62 faits de l'ontologie ont `scope: monument` (une propriété du bien : est-ce
une église ? y a-t-il un orgue ? le site est-il ouvert au public ?) et 40
`scope: proprietaire` (revenus, régime fiscal, statut juridique). Ils sont
redemandés à CHAQUE projet, alors que `FactDef.scope` est documenté depuis
l'origine comme pilotant la réutilisation.

Ce module est PUR : il ne lit ni la base ni le réseau, et ne dépend que des
lignes de projets qu'on lui passe. La route qui l'appelle vit dans
`routers/projets.py`.

Ce qu'il n'est PAS : un héritage implicite à la frontière du moteur. La reprise
est une COPIE explicite, faite à la création du projet et persistée dans son
`questionnaire` — c'est ce qui permet de la modifier projet par projet (une
toiture refaite n'a pas le même état sanitaire d'un chantier à l'autre) et de la
montrer à l'utilisateur (« N réponses reprises de vos autres projets »).
"""

from __future__ import annotations

from aides_schema import OPTIONS_BOOLEEN_IMPLICITES, FactDef
from eligibility_engine import libelle_tranche

#: Les deux scopes qui décrivent quelque chose de STABLE : le bien, et la
#: personne. `projet` en est exclu par définition — c'est ce qui change d'un
#: chantier à l'autre, et le reprendre ferait dire à un nouveau projet ce que
#: disait le précédent.
SCOPES_DURABLES = frozenset({"monument", "proprietaire"})


def faits_durables(
    projets: list[dict],
    facts: dict[str, FactDef],
) -> tuple[dict[str, object], dict[str, str]]:
    """Réponses durables du monument, et le projet d'où chacune vient.

    Les projets sont SUPERPOSÉS, du plus ancien au plus récent, clé par clé : le
    plus récent l'emporte PAR CLÉ. Ne pas prendre « le dernier projet qui a des
    réponses » — un projet A à dix faits suivi d'un projet B à trois en perdrait
    sept.

    Les projets CLÔTURÉS comptent : un chantier terminé décrit toujours le même
    bien, et son questionnaire est souvent le plus complet.

    Sont ignorées : les clés réservées (préfixe `_`, qui portent le cadrage et
    non des faits), les clés absentes de l'ontologie (un fait retiré depuis), et
    les faits de scope `projet`.
    """
    reponses: dict[str, object] = {}
    source: dict[str, str] = {}
    for projet in sorted(projets, key=lambda p: (p.get("updated_at") or "", p.get("id") or "")):
        questionnaire = projet.get("questionnaire") or {}
        if not isinstance(questionnaire, dict):
            continue
        projet_id = projet.get("id") or ""
        for cle, valeur in questionnaire.items():
            if cle.startswith("_"):
                continue
            fait = facts.get(cle)
            if fait is None or fait.scope not in SCOPES_DURABLES:
                continue
            reponses[cle] = valeur
            source[cle] = projet_id
    return reponses, source


def libelle_reponse(fait: FactDef, valeur: object) -> str | None:
    """Libellé LISIBLE d'une réponse reprise, ou None si on ne sait pas le dire.

    Nécessaire parce que la valeur persistée est un identifiant d'option
    (« oui », « ge40000 ») : l'afficher tel quel ne dit rien à personne.

    Les tranches d'un fait numérique sont relues depuis leur IDENTIFIANT
    (`libelle_tranche`) : elles sont fabriquées par le moteur depuis les seuils
    des aides candidates, qu'on n'a pas ici, mais l'identifiant porte ses propres
    bornes (`lt5`, `5_9`, `ge5`) — le libellé se reconstruit donc à l'identique,
    par les mêmes fonctions que celles qui l'ont produit.
    """
    if fait.type in ("integer", "number") and isinstance(valeur, str):
        return libelle_tranche(valeur, fait.unit)
    options = list(fait.options or (OPTIONS_BOOLEEN_IMPLICITES if fait.type == "boolean" else []))
    if not options:
        return None
    par_id = {o.id: o.label for o in options}
    # Un `multi_enum` porte une LISTE de cases cochées.
    if isinstance(valeur, (list, tuple)):
        libelles = [par_id[v] for v in valeur if v in par_id]
        return ", ".join(libelles) or None
    return par_id.get(str(valeur))


def details_reprises(
    reponses: dict[str, object],
    source: dict[str, str],
    facts: dict[str, FactDef],
    titres: dict[str, str | None],
) -> list[dict]:
    """De quoi NOMMER les réponses reprises à l'écran.

    Le bandeau du questionnaire annonçait un nombre sans dire lesquelles, et
    renvoyait pour les corriger vers la fiche de l'aide — où elles ne sont pas :
    une réponse reprise n'est plus une incertitude, donc le moteur ne rend plus
    sa question, donc aucune fiche ne l'offre. Les nommer ici est la seule façon
    de rendre la reprise vérifiable par l'utilisateur.

    Trié par question, pour que la liste ne bouge pas d'un affichage à l'autre.
    """
    details = []
    for cle, valeur in reponses.items():
        fait = facts.get(cle)
        if fait is None:
            continue
        projet_id = source.get(cle, "")
        details.append(
            {
                "fact": cle,
                "question": fait.question,
                "reponse": libelle_reponse(fait, valeur),
                "projetId": projet_id,
                "projetTitre": titres.get(projet_id),
            }
        )
    return sorted(details, key=lambda d: d["question"])
