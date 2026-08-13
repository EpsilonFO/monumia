"""
Reprise des pièces déjà déposées dans un nouveau dossier.

Beaucoup d'aides demandent la même pièce (le corpus compte 1019 demandes pour
une centaine de pièces réelles). Quand un utilisateur a déjà fourni son RIB ou
son titre de propriété, le redemander est une friction pure.

Ce service prend une checklist et y rattache les documents déjà détenus, dans
un état `repris` que l'utilisateur doit confirmer — jamais `fourni`. Un dossier
ne se déclare donc jamais complet tout seul.

Frontière : ce module est le SEUL du lot à toucher la base. `dossier_service`
reste une fonction pure, ce qui le garde testable sans mock.
"""

from __future__ import annotations

from datetime import UTC, datetime

from supabase import Client

from pieces_schema import Piece, load_pieces
from services.project_access import filter_visible_documents, my_project_roles

# Statuts d'items qu'on ne touche jamais : l'utilisateur s'en est déjà occupé.
STATUTS_INTOUCHABLES = ("fourni", "en_attente", "repris")


def age_mois(date_iso: str | None, now: datetime) -> int | None:
    """Écart en mois calendaires entre la date du document et `now`.

    Ce n'est PAS un nombre de mois pleins : seuls les couples (année, mois) sont
    comparés, sans tenir compte du jour. Le 31 janvier et le 1er février sont
    donc à « 1 mois » d'écart. L'approximation vaut ±1 mois ; elle est assumée,
    le seuil ne sert qu'à signaler un document ancien à relire, jamais à trancher
    une échéance.

    None si la date est absente ou illisible : une date illisible ne doit pas
    faire échouer la reprise, on préfère un document non marqué à un dossier qui
    ne se remplit pas.
    """
    if not date_iso:
        return None
    try:
        dt = datetime.fromisoformat(date_iso)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return (now.year - dt.year) * 12 + (now.month - dt.month)


def choisir_document(docs: list[dict]) -> dict | None:
    """Le document le plus récent d'un lot, selon date_document sinon date_upload."""
    if not docs:
        return None
    return max(docs, key=lambda d: d.get("date_document") or d.get("date_upload") or "")


def _est_perime(piece: Piece, doc: dict, now: datetime) -> bool:
    if not piece.perissable or piece.seuil_alerte_mois is None:
        return False
    age = age_mois(doc.get("date_document") or doc.get("date_upload"), now)
    return age is not None and age > piece.seuil_alerte_mois


def _stock(
    supabase: Client, piece_ids: set[str], monument_id: str, user_id: str
) -> dict[str, list[dict]]:
    """Documents visibles par `user_id` incarnant l'une des pièces demandées.

    Le filtre SQL est large (mes documents OU ceux du projet) ; c'est
    `filter_visible_documents` qui applique la règle de visibilité, comme pour
    la liste des documents. Aucun chemin d'accès parallèle.
    """
    if not piece_ids:
        return {}

    rows = (
        supabase.table("documents")
        .select("*")
        .in_("piece_id", sorted(piece_ids))
        .is_("trashed_at", "null")
        .or_(f"user_id.eq.{user_id},monument_ids.cs.{{{monument_id}}}")
        .execute()
        .data
        or []
    )
    # Défense en profondeur : la corbeille est revérifiée en Python plutôt que
    # de faire confiance au seul `.is_()`, car un document jeté proposé à la
    # reprise serait une régression silencieuse. Le coût est nul (liste courte).
    rows = [r for r in rows if not r.get("trashed_at")]

    visibles = filter_visible_documents(rows, user_id, my_project_roles(supabase, user_id))

    par_piece: dict[str, list[dict]] = {}
    for row in visibles:
        pid = row.get("piece_id")
        if pid in piece_ids:
            par_piece.setdefault(pid, []).append(row)
    return par_piece


def _candidat(
    piece: Piece,
    doc_par_piece: dict,
    piece_id: str,
    monument_id: str,
    user_id: str,
    refuses: set[str],
) -> dict | None:
    """Document réutilisable pour cette pièce, selon sa portée.

    `porteur` est propre au demandeur : même visible (co-membre d'équipe), le
    document d'un tiers ne doit jamais être rattaché silencieusement à ma place.
    Il traverse en revanche tous ses projets — c'est tout l'intérêt d'un RIB.

    `monument` et `operation` sont bornées au projet. Une opération est financée
    par PLUSIEURS aides : déposer à la Fondation du patrimoine et à la DETR pour
    les mêmes travaux, c'est joindre deux fois le même plan de financement et les
    mêmes devis. La frontière de réutilisation d'une pièce d'opération est donc
    la campagne de travaux, pas le dossier. Le risque résiduel — proposer le
    devis d'une campagne achevée — est couvert par la péremption : ces pièces
    sont périssables, et une pièce trop ancienne s'affiche en avertissement.

    `refuses` : fichiers que l'utilisateur a explicitement retirés de CET item.
    Sans cette mémoire, la reprise automatique reproposerait à chaque visite le
    fichier qui vient d'être refusé. Le refus porte sur un fichier précis, pas
    sur la pièce : un autre fichier de la même étiquette reste proposable.
    """
    docs = [d for d in doc_par_piece.get(piece_id, []) if d.get("id") not in refuses]
    if piece.portee == "porteur":
        docs = [d for d in docs if d.get("user_id") == user_id]
    else:
        docs = [d for d in docs if monument_id in (d.get("monument_ids") or [])]
    return choisir_document(docs)


def apply_reuse(
    supabase: Client,
    checklist: list[dict],
    monument_id: str,
    user_id: str,
    *,
    now: datetime | None = None,
) -> tuple[list[dict], int]:
    """Rattache aux items éligibles les documents déjà détenus.

    Renvoie une NOUVELLE checklist (la source n'est pas mutée) et le nombre
    d'items repris. Le résultat dépend de `user_id` : le stock est filtré par sa
    visibilité, ce qui est le comportement voulu.
    """
    now = now or datetime.now(UTC)
    pieces = load_pieces()

    demandes = {
        item.get("pieceId")
        for item in checklist
        if item.get("pieceId") in pieces and item.get("statut") not in STATUTS_INTOUCHABLES
    }
    if not demandes:
        return [dict(item) for item in checklist], 0

    doc_par_piece = _stock(supabase, demandes, monument_id, user_id)

    nouvelle: list[dict] = []
    repris = 0
    for item in checklist:
        copie = dict(item)
        piece_id = copie.get("pieceId")
        piece = pieces.get(piece_id) if piece_id else None

        if piece is None or copie.get("statut") in STATUTS_INTOUCHABLES:
            nouvelle.append(copie)
            continue

        doc = _candidat(
            piece,
            doc_par_piece,
            piece_id,
            monument_id,
            user_id,
            set(copie.get("refuses") or []),
        )
        if doc is None:
            nouvelle.append(copie)
            continue

        copie["statut"] = "repris"
        copie["documentId"] = doc["id"]
        copie["origine"] = "repris"
        copie["perime"] = _est_perime(piece, doc, now)
        repris += 1
        nouvelle.append(copie)

    return nouvelle, repris
