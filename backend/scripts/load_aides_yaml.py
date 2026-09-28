"""
Loader : data/aides/*.yaml + data/facts.yaml → Supabase (upsert).

Git est la source de vérité ; ce script synchronise la base dans UN SEUL sens
(YAML → DB). Ne jamais éditer une aide directement en base : la modification
serait écrasée au prochain run.

Identité : `slug`. Les lignes existantes sans slug (créées par les anciens
seeds) sont rattachées par `nom` au premier run, puis le slug est posé.

Compatibilité moteur actuel : `conditions_eligibilite_detail` est régénéré
depuis les puces YAML (format «- ») pour que la phase LLM continue de tourner
pendant le shadow mode. Les conditions typées vont dans `aide_conditions`.

Prérequis : migration 20260611120000_aides_v3_slug_facts_conditions.sql.

Run:
    cd backend && uv run python scripts/load_aides_yaml.py [--dry-run]
"""

import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env.local", override=True)

from supabase import create_client

from aides_schema import Aide, load_all_aides, load_facts, load_pending_facts
from eligibility_engine import engine_ready_aides


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def aide_to_row(aide: Aide) -> dict:
    """Projette une Aide YAML sur les colonnes d'aides_v3."""
    bullets = "\n".join(f"- {c.text}" for c in aide.conditions)
    hf = aide.hard_filters
    return {
        "slug": aide.slug,
        "nom": aide.nom,
        "nom_court": aide.nom_court,
        "organisme": aide.organisme,
        "categorie": aide.categorie,
        "type": aide.type,
        "description": aide.description,
        "description_longue": aide.description_longue,
        "url_officielle": aide.source.url_officielle,
        "formulaire_url": aide.source.formulaire_url,
        "verified_at": _iso(aide.source.verified_at),
        "montant_min": aide.financement.montant_min,
        "montant_max": aide.financement.montant_max,
        "taux_min": aide.financement.taux_min,
        "taux_max": aide.financement.taux_max,
        "plancher": aide.financement.plancher,
        "base_ttc": aide.financement.base_ttc,
        "permanent": aide.calendrier.permanent,
        "date_ouverture": _iso(aide.calendrier.date_ouverture),
        "date_limite": _iso(aide.calendrier.date_limite),
        "delai_instruction": aide.calendrier.delai_instruction,
        "protections": hf.protections,
        "proprietaires": hf.proprietaires,
        "travaux": hf.travaux,
        "regions": hf.regions,
        "departements": hf.departements,
        "etats_conservation": hf.etats_conservation,
        "commune_max_population": hf.commune_max_population,
        "architecte_requis": aide.flags.architecte_requis,
        "cofinancement_requis": aide.flags.cofinancement_requis,
        "conditions_eligibilite_detail": bullets or None,
        "demarche_description": aide.demarche,
        "documents_requis": [d.model_dump() for d in aide.documents_requis],
        "tags": aide.tags,
        # Familles thématiques. Écrites sans condition, à l'inverse de `raison`
        # (cf. l'upsert plus bas) : la colonne est neuve, aucune valeur en base
        # ne précède le YAML, donc rien à préserver — le YAML est la vérité.
        "familles": aide.familles,
    }


def _applies_if_json(c) -> dict | None:
    """Sérialise AppliesIf en jsonb — cible `fact` ou `field` selon le cas."""
    if c.applies_if is None:
        return None
    out: dict = {"predicate": c.applies_if.predicate.root}
    if c.applies_if.fact:
        out["fact"] = c.applies_if.fact
    if c.applies_if.field:
        out["field"] = c.applies_if.field
    return out


def condition_rows(aide: Aide, aide_id: str) -> list[dict]:
    rows = []
    for pos, c in enumerate(aide.conditions, 1):
        rows.append(
            {
                "aide_id": aide_id,
                "position": pos,
                "condition_key": c.id,
                "text": c.text,
                "kind": c.kind,
                "effect": c.effect,
                "fact_key": c.fact,
                "field": c.field,
                "predicate": c.predicate.root if c.predicate else None,
                "applies_if": _applies_if_json(c),
                "quote": c.quote,
                "notes": c.notes,
            }
        )
    return rows


# Aides par lot de conditions. Borné par la longueur d'URL du `delete ... in`
# (un UUID fait 36 caractères), pas par la base.
LOT = 50


def main() -> int:
    # Sous `docker exec` sans TTY, la sortie est bufferisée par blocs : rien ne
    # s'affichait avant la fin du script. Ligne par ligne, on voit où il en est.
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]
    dry_run = "--dry-run" in sys.argv
    ready_only = "--ready-only" in sys.argv

    # Approuvés + en attente : aide_conditions.fact_key a une FK vers facts(key),
    # or les aides clean référencent déjà des faits de facts_pending.yaml. On doit
    # donc pousser les deux, sinon l'insert des conditions viole la contrainte.
    facts = {**load_facts(), **load_pending_facts()}
    aides = load_all_aides()
    if ready_only:
        # Ne pousser que les aides « engine-ready » (zéro condition untyped) —
        # celles que le moteur déterministe sait traiter.
        aides = engine_ready_aides(aides)
    print(
        f"{len(facts)} faits, {len(aides)} aides chargés depuis data/"
        f"{' (engine-ready uniquement)' if ready_only else ''}"
    )

    if dry_run:
        print("--dry-run : validation OK, aucune écriture")
        return 0

    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

    # ── Faits ───────────────────────────────────────────────────────────
    fact_rows = [
        {
            "key": key,
            "type": f.type,
            "scope": f.scope,
            "question": f.question,
            "options": [o.model_dump() for o in f.options] if f.options else None,
            "unit": f.unit,
            "help": f.help,
            "auto_source": f.auto_source,
        }
        for key, f in facts.items()
    ]
    supabase.table("facts").upsert(fact_rows, on_conflict="key").execute()
    print(f"✓ {len(fact_rows)} faits upsertés")

    # ── Aides ───────────────────────────────────────────────────────────
    # Index des lignes existantes pour rattacher par slug, sinon par nom
    # (backfill des lignes créées par les anciens seeds, sans slug).
    existing = (supabase.table("aides_v3").select("id, nom, slug").execute()).data or []
    by_slug = {r["slug"]: r["id"] for r in existing if r.get("slug")}
    by_nom = {r["nom"]: r["id"] for r in existing}

    # Les aides partent une par une (l'index unique sur `slug` est partiel,
    # PostgREST ne sait pas s'en servir pour un upsert groupé), mais leurs
    # conditions par lot : trois requêtes par aide, c'était ~1 400 allers-retours
    # sans un mot à l'écran, que beta.sh semblait attendre indéfiniment.
    created, updated = 0, 0
    items = list(aides.items())
    for start in range(0, len(items), LOT):
        lot_ids: list[str] = []
        lot_conditions: list[dict] = []
        for slug, aide in items[start : start + LOT]:
            row = aide_to_row(aide)
            # `raison` (NOT NULL en base) — asymétrie transitoire : tant que les
            # YAML ne portent pas la finalité, un update ne doit pas écraser la
            # valeur déjà en base avec [] ; un insert doit en fournir une.
            if aide.raison:
                row["raison"] = aide.raison
            aide_id = by_slug.get(slug) or by_nom.get(aide.nom)
            if aide_id:
                supabase.table("aides_v3").update(row).eq("id", aide_id).execute()
                updated += 1
            else:
                row.setdefault("raison", [])
                result = supabase.table("aides_v3").insert(row).execute()
                aide_id = result.data[0]["id"]
                created += 1
            lot_ids.append(aide_id)
            lot_conditions.extend(condition_rows(aide, aide_id))

        supabase.table("aide_conditions").delete().in_("aide_id", lot_ids).execute()
        if lot_conditions:
            supabase.table("aide_conditions").insert(lot_conditions).execute()
        print(f"  {min(start + LOT, len(items))}/{len(items)} aides")

    print(f"✓ aides : {updated} mises à jour, {created} créées")
    print(
        "Note : les aides en base absentes de data/aides/ (ex. sync Aides-Territoires) "
        "ne sont pas touchées."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
