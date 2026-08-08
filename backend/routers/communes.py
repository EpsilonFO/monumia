import re
import unicodedata

from fastapi import APIRouter, Depends, Query
from supabase import Client

from db import get_supabase

router = APIRouter(prefix="/communes", tags=["communes"])

COLUMNS = (
    "code_insee, nom_commune, departement, departement_num, region, arrondissement, population"
)


def _tokens(q: str) -> list[str]:
    """Découpe la saisie en tokens alphanumériques sans accents.

    `communes.nom_commune_matching` contient le nom en minuscules sans accents,
    tirets conservés. Passer par des tokens rend la recherche indifférente aux
    accents ET aux séparateurs (« saint jean » trouve « Saint-Jean »), et écarte
    au passage les métacaractères d'ILIKE (`%`, `_`) : le motif n'est construit
    que de [a-z0-9], donc rien d'injectable.
    """
    nfkd = unicodedata.normalize("NFKD", q)
    plain = "".join(c for c in nfkd if not unicodedata.combining(c)).lower()
    return [t for t in re.split(r"[^a-z0-9]+", plain) if t]


def _row(r: dict) -> dict:
    return {
        "codeInsee": r["code_insee"],
        "nom": r["nom_commune"],
        "departement": r["departement"],
        "codeDepartement": r["departement_num"],
        "region": r["region"],
        "arrondissement": r.get("arrondissement"),
        "population": r.get("population"),
    }


@router.get("/search")
def search_communes(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, le=50),
    supabase: Client = Depends(get_supabase),
):
    """Recherche de communes par nom, insensible à la casse et aux accents.

    Deux passes, dans cet ordre : les noms qui COMMENCENT par la saisie, puis
    ceux qui la CONTIENNENT (« gome » → Gomené, Gometz-la-Ville…, puis
    Colleville-Montgomery, Trégomeur…). Deux requêtes plutôt qu'un tri en
    mémoire : sur « saint », les milliers de correspondances « contient »
    noieraient les préfixes si on tronquait avant de trier.
    """
    tokens = _tokens(q)
    if not tokens:
        return []
    body = "%".join(tokens)

    def fetch(pattern: str, count: int) -> list[dict]:
        return (
            supabase.table("communes")
            .select(COLUMNS)
            .ilike("nom_commune_matching", pattern)
            .order("nom_commune")
            .limit(count)
            .execute()
            .data
        )

    rows = fetch(f"{body}%", limit)
    if len(rows) < limit:
        seen = {r["code_insee"] for r in rows}
        rows += [r for r in fetch(f"%{body}%", limit * 2) if r["code_insee"] not in seen]

    return [_row(r) for r in rows[:limit]]
