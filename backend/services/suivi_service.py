"""Logique pure du suivi des aides : validation, application d'un changement de
statut (avec historique), calcul de l'état d'un projet. Aucune dépendance DB."""

from datetime import UTC, datetime

STATUTS = ("a_faire", "en_preparation", "depose", "accorde", "refuse")
TERMINAUX = ("accorde", "refuse")
MOTIFS = (
    "inegibilite",
    "budget_epuise",
    "dossier_incomplet",
    "non_prioritaire",
    "hors_delai",
    "autre",
)


class SuiviValidationError(ValueError):
    """Payload de suivi invalide (statut, montant ou motif)."""


def validate_payload(payload: dict) -> None:
    statut = payload.get("statut")
    if statut not in STATUTS:
        raise SuiviValidationError(f"Statut invalide : {statut!r}")

    montant = payload.get("montant_obtenu")
    if montant is not None and (
        isinstance(montant, bool) or not isinstance(montant, int | float) or montant < 0
    ):
        raise SuiviValidationError("montant_obtenu doit être un nombre positif")

    motif = payload.get("motif_refus_code")
    if motif is not None and motif not in MOTIFS:
        raise SuiviValidationError(f"Motif de refus invalide : {motif!r}")


def _clean_by_statut(statut: str, payload: dict) -> dict:
    """Annule les champs sans rapport avec le statut courant."""
    return {
        "statut": statut,
        "montant_obtenu": payload.get("montant_obtenu") if statut == "accorde" else None,
        "motif_refus_code": payload.get("motif_refus_code") if statut == "refuse" else None,
        "motif_refus_detail": payload.get("motif_refus_detail") if statut == "refuse" else None,
        "note": payload.get("note"),
    }


def apply_statut_change(existing: dict | None, payload: dict, now: str | None = None) -> dict:
    """Retourne les champs à upserter. Ajoute une entrée d'historique quand le
    statut change (ou à la création)."""
    validate_payload(payload)
    now = now or datetime.now(UTC).isoformat()
    statut = payload["statut"]

    fields = _clean_by_statut(statut, payload)

    historique = list((existing or {}).get("historique") or [])
    previous_statut = (existing or {}).get("statut")
    if previous_statut != statut:
        historique.append({"statut": statut, "at": now})

    fields["historique"] = historique
    fields["updated_at"] = now
    return fields


def compute_etat_projet(cloture_at: str | None, suivis: list[dict]) -> str:
    """'boucle' si clôturé ; 'pret_a_cloturer' si ≥1 suivi et tous terminaux ;
    sinon 'ouvert'."""
    if cloture_at:
        return "boucle"
    if suivis and all(s.get("statut") in TERMINAUX for s in suivis):
        return "pret_a_cloturer"
    return "ouvert"


def statut_suivi_au_depot(actuel: str | None, *, depose: bool) -> str | None:
    """Statut que prend le suivi d'une aide quand son dossier est marqué déposé
    (`depose=True`) ou rouvert (`depose=False`) ; None = ne pas y toucher.

    Le dépôt fait avancer un suivi resté en amont (« À faire », « En
    préparation », ou absent) jusqu'à « Déposé ». La réouverture ne défait que
    ce que le dépôt a posé : un suivi « Déposé » revient « En préparation », une
    décision (accordé, refusé) n'est jamais effacée.
    """
    if depose:
        return "depose" if actuel in (None, "a_faire", "en_preparation") else None
    return "en_preparation" if actuel == "depose" else None
