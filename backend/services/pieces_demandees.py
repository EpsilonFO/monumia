"""
Les pièces que demandent les aides d'un projet : la liste « À déposer pour vos
aides » de la page Mes documents.

Fonction pure, sur un diagnostic déjà calculé : le digest du dashboard l'appelle
pour chaque projet, sans aucune requête de plus. Le référentiel
(data/pieces.yaml) donne le nom, la description et le type de chaque pièce ;
les aides YAML donnent, par `documents_requis[].piece_id`, qui la demande.

Seules comptent les aides À PORTÉE (éligibles, potentiellement éligibles,
atteignables) : ce sont celles pour lesquelles un dossier peut se monter. Une
aide non éligible qui demande un RIB ne rend pas le RIB plus utile.
"""

from __future__ import annotations

from pieces_schema import load_pieces

# Les pièces propres à UN financeur : son formulaire, la lettre qu'on lui
# adresse. Elles portent un `piece_id` parce que le référentiel les nomme, mais
# on ne les réutilise jamais d'un dossier à l'autre (le Cerfa de la DRAC ne sert
# pas à la Fondation du patrimoine). Les proposer au dépôt « une fois pour tous
# les dossiers » serait faux : elles se remplissent dans chaque dossier.
PIECES_PROPRES_AU_FINANCEUR = frozenset({"formulaire_demande", "courrier_demande_subvention"})

_SEAUX_A_PORTEE = ("aidesEligibles", "aidesPotentiellementEligibles", "aidesAtteignables")


def pieces_demandees(result: dict, *, masquer_bientot: bool = False) -> list[dict]:
    """Les pièces demandées par les aides à portée d'un diagnostic.

    Une entrée par pièce du référentiel citée au moins une fois, avec les ids
    des aides qui la citent (dédoublonnés et triés) : le front fait l'union sur
    les projets ouverts d'un monument, où la même aide peut revenir deux fois.
    Triées par nombre d'aides décroissant, puis par id pour un ordre stable.

    `masquer_bientot` suit le digest : une aide dont le guichet n'est pas ouvert
    perd ses `documentsRequis` hors offre (cf. `retirer_les_modalites`). Les
    compter ici rendrait par la bande ce que la fiche retient.
    """
    referentiel = load_pieces()
    aides_par_piece: dict[str, set[str]] = {}
    for seau in _SEAUX_A_PORTEE:
        for match in result.get(seau) or []:
            if masquer_bientot and match.get("disponibilite") == "bientot":
                continue
            aide = match.get("aide") or {}
            aide_id = aide.get("id")
            if not aide_id:
                continue
            for doc in aide.get("documentsRequis") or aide.get("documents_requis") or []:
                if not isinstance(doc, dict):
                    continue
                piece_id = doc.get("piece_id") or doc.get("pieceId")
                if piece_id in PIECES_PROPRES_AU_FINANCEUR or piece_id not in referentiel:
                    continue
                aides_par_piece.setdefault(piece_id, set()).add(str(aide_id))

    pieces = []
    for piece_id, aides in aides_par_piece.items():
        piece = referentiel[piece_id]
        pieces.append(
            {
                "pieceId": piece_id,
                "nom": piece.nom,
                "description": piece.description,
                "typeDocument": piece.type_document,
                "portee": piece.portee,
                "aideIds": sorted(aides),
            }
        )
    pieces.sort(key=lambda p: (-len(p["aideIds"]), p["pieceId"]))
    return pieces
