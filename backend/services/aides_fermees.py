"""Les aides fermées : sorties du catalogue alors qu'un utilisateur y travaillait.

Une aide que son guide ne liste plus et dont la page est morte quitte le
catalogue sans case (`catalogue/sorties.py`) : son YAML part dans
`data/catalogue/retirees/`, une date et un motif en tête. Pour qui ne l'avait
vue que dans un diagnostic, elle disparaît simplement : le moteur ne lit que
`data/aides/`. Pour qui avait commencé les démarches (un dossier, un suivi :
le même critère que `routers.aides._deja_engage`), elle ne doit pas finir sur
« Aide introuvable » : au premier clic, un panneau explique la fermeture, puis
le dossier n'apparaît plus jamais pour ce compte.

Sauf une demande déjà DÉPOSÉE (dossier soumis, suivi déposé, accordé ou
refusé) : la fermeture d'un dispositif n'annule pas une demande en
instruction, et une aide obtenue reste l'histoire du projet. Celle-là reste
visible ; le panneau dit seulement que la demande suit son cours.

« Vu » se retient par compte, dans `users.aides_fermees_vues` (slug -> date),
sur le patron de `guides_vus`. Le masquage se fait côté serveur, dans les
listes (`GET /dossiers`, `GET /dashboard`, `GET /projets/{id}/aide-suivis`) :
masquer à l'affichage laisserait le dossier dans le cache local du front.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from aides_schema import DATA_DIR, charger_yaml

RETIREES = DATA_DIR / "catalogue" / "retirees"
ENTETE = re.compile(r"^# Retirée du catalogue le (\d{4}-\d{2}-\d{2})")
#: Statuts de suivi d'une demande partie chez le financeur.
DEPOSES = frozenset({"depose", "accorde", "refuse"})


@dataclass(frozen=True)
class AideFermee:
    slug: str
    nom: str
    fermee_le: str  # AAAA-MM-JJ

    def pour(self, deposee: bool) -> dict[str, Any]:
        return {"nom": self.nom, "fermeeLe": self.fermee_le, "deposee": deposee}


def fermees(dossier: Path | None = None) -> dict[str, AideFermee]:
    """slug -> aide fermée, relu quand le dossier change (un retrait, une remise en service)."""
    dossier = dossier or RETIREES
    if not dossier.is_dir():
        return {}
    signature = tuple(sorted((p.name, p.stat().st_mtime_ns) for p in dossier.glob("*.yaml")))
    return _lire(dossier, signature)


@lru_cache(maxsize=4)
def _lire(dossier: Path, signature: tuple[tuple[str, int], ...]) -> dict[str, AideFermee]:
    sortie: dict[str, AideFermee] = {}
    for nom_fichier, _ in signature:
        chemin = dossier / nom_fichier
        try:
            texte = chemin.read_text(encoding="utf-8")
            data = charger_yaml(texte) or {}
        except Exception:  # noqa: BLE001 — un fichier illisible ne ferme rien
            continue
        m = ENTETE.match(texte)
        slug = str(data.get("slug") or chemin.stem)
        nom = str(data.get("nom_court") or data.get("nom") or slug)
        sortie[slug] = AideFermee(slug, nom, m.group(1) if m else "")
    return sortie


def deposee(dossier_statut: str | None, suivi_statuts: list[str | None]) -> bool:
    return dossier_statut == "soumis" or any(s in DEPOSES for s in suivi_statuts)


def vues(supabase: Any, user_id: str) -> dict[str, str]:
    """Les aides fermées dont ce compte a lu le panneau. Une lecture qui échoue
    (migration pas encore appliquée) ne masque rien : le dossier reste visible,
    annoté, ce qui est le sens sûr."""
    try:
        res = (
            supabase.table("users")
            .select("aides_fermees_vues")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception:  # noqa: BLE001
        return {}
    valeur = ((res.data if res else None) or {}).get("aides_fermees_vues")
    return valeur if isinstance(valeur, dict) else {}


def marquer_vue(supabase: Any, user_id: str, slug: str, quand: datetime) -> dict[str, str]:
    courant = vues(supabase, user_id)
    nouvelles = {**courant, slug: quand.isoformat()}
    supabase.table("users").update({"aides_fermees_vues": nouvelles}).eq("id", user_id).execute()
    return nouvelles


def _statuts_suivis(supabase: Any, paires: set[tuple[str, str]]) -> dict[tuple[str, str], list]:
    """Les statuts de suivi, tous comptes confondus, de chaque (projet, aide) fermée."""
    if not paires:
        return {}
    res = (
        supabase.table("aide_suivis")
        .select("projet_id,aide_id,statut")
        .in_("projet_id", sorted({p for p, _ in paires}))
        .in_("aide_id", sorted({a for _, a in paires}))
        .execute()
    )
    statuts: dict[tuple[str, str], list] = {}
    for r in (res.data if res else None) or []:
        statuts.setdefault((r["projet_id"], r["aide_id"]), []).append(r.get("statut"))
    return statuts


def appliquer_aux_dossiers(
    supabase: Any, user_id: str, dossiers: list[dict], *, masquer: bool = True
) -> list[dict]:
    """Annote les dossiers d'une aide fermée (`aide_fermee`), et retire ceux que le compte a vus.

    Rien n'est lu en base tant qu'aucun dossier ne porte sur une aide fermée :
    le cas courant ne coûte pas une requête.
    """
    ferm = fermees()
    touches = [d for d in dossiers if d.get("aide_id") in ferm]
    if not touches:
        return dossiers
    statuts = _statuts_suivis(supabase, {(d["projet_id"], d["aide_id"]) for d in touches})
    vus = vues(supabase, user_id) if masquer else {}
    sortie = []
    for d in dossiers:
        f = ferm.get(d.get("aide_id") or "")
        if f is None:
            sortie.append(d)
            continue
        dep = deposee(d.get("statut"), statuts.get((d["projet_id"], d["aide_id"]), []))
        if f.slug in vus and not dep:
            continue
        sortie.append({**d, "aide_fermee": f.pour(dep)})
    return sortie


def filtrer_suivis(
    supabase: Any, user_id: str, suivis: list[dict], dossiers: list[dict] | None = None
) -> list[dict]:
    """Retire les suivis d'une aide fermée que le compte a vue, sauf demande déposée.

    `dossiers` : ceux du même périmètre, s'ils sont en main (un dossier soumis
    garde son suivi même quand le suivi n'est pas encore passé à « déposé »).
    """
    ferm = fermees()
    if not any(s.get("aide_id") in ferm for s in suivis):
        return suivis
    vus = vues(supabase, user_id)
    if not vus:
        return suivis
    soumis = {(d["projet_id"], d["aide_id"]) for d in dossiers or [] if d.get("statut") == "soumis"}
    return [
        s
        for s in suivis
        if not (
            s.get("aide_id") in ferm
            and s.get("aide_id") in vus
            and s.get("statut") not in DEPOSES
            and (s.get("projet_id"), s.get("aide_id")) not in soumis
        )
    ]


def deposee_pour(supabase: Any, user_id: str, slug: str) -> bool:
    """Une demande de ce compte sur cette aide est-elle partie chez le financeur ?"""
    dossiers = (
        supabase.table("dossiers").select("statut").eq("user_id", user_id).eq("aide_id", slug)
    ).execute()
    suivis = (
        supabase.table("aide_suivis").select("statut").eq("user_id", user_id).eq("aide_id", slug)
    ).execute()
    return any(
        deposee(d.get("statut"), []) for d in (dossiers.data if dossiers else None) or []
    ) or any(s.get("statut") in DEPOSES for s in (suivis.data if suivis else None) or [])


def erreur(f: AideFermee, deposee_: bool) -> dict[str, Any]:
    """Le corps du 410 que rend une aide fermée à qui y travaillait."""
    return {"code": "aide_fermee", "message": "Cette aide n'est plus proposée.", **f.pour(deposee_)}
