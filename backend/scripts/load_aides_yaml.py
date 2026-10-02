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
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env.local", override=True)

from supabase import Client, create_client

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
# Écritures d'aides simultanées au sein d'un lot. Assez pour masquer la latence
# réseau, assez peu pour ne pas ressembler à une rafale côté Supabase.
ECRITURES_PARALLELES = 8
#
# CHAQUE THREAD A SON PROPRE CLIENT (`client_du_thread`). Le client PostgREST
# parle HTTP/2, et un client partagé faisait passer les huit threads sur UNE
# connexion multiplexée, ce que le transport synchrone de httpcore ne tient pas :
# trames entremêlées, Cloudflare qui referme la connexion (`RemoteProtocolError:
# Server disconnected`, toutes les requêtes en vol d'un coup) ou rejette une
# requête mal formée (400 HTML « cloudflare », que PostgREST ne sait pas lire).
# Vu à chaque déploiement depuis la parallélisation du 2026-09-30, beta comme
# prod, jamais avant. Un client par thread = une connexion par thread.
#
# Les reprises restent, en filet : une connexion peut aussi tomber pour de vrai.
ESSAIS = 4


def _reprendre[T](action: Callable[[], T], quoi: str) -> T:
    """Exécute `action`, la rejoue sur une erreur de transport (attente 1, 2, 4 s).

    Ne rejouer que des actions IDEMPOTENTES : une requête dont la réponse s'est
    perdue a pu s'appliquer en base.
    """
    for essai in range(ESSAIS):
        try:
            return action()
        except httpx.TransportError as exc:
            if essai == ESSAIS - 1:
                raise
            attente = 2**essai
            print(f"  ↻ {quoi} : {type(exc).__name__}, nouvel essai dans {attente} s")
            time.sleep(attente)
    raise AssertionError("inatteignable")


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

    url, cle = os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"]
    supabase = create_client(url, cle)

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
            # Colonne `text` : plusieurs sources s'y écrivent séparées par une virgule.
            "auto_source": ", ".join(f.auto_sources) or None,
        }
        for key, f in facts.items()
    ]
    _reprendre(
        lambda: supabase.table("facts").upsert(fact_rows, on_conflict="key").execute(),
        "faits",
    )
    print(f"✓ {len(fact_rows)} faits upsertés")

    # ── Aides ───────────────────────────────────────────────────────────
    # Index des lignes existantes pour rattacher par slug, sinon par nom
    # (backfill des lignes créées par les anciens seeds, sans slug).
    existing = (
        _reprendre(
            lambda: supabase.table("aides_v3").select("id, nom, slug").execute(),
            "index des aides",
        )
    ).data or []
    by_slug = {r["slug"]: r["id"] for r in existing if r.get("slug")}
    by_nom = {r["nom"]: r["id"] for r in existing}

    # Les aides partent une par une (l'index unique sur `slug` est partiel,
    # PostgREST ne sait pas s'en servir pour un upsert groupé), mais leurs
    # conditions par lot : trois requêtes par aide, c'était ~1 400 allers-retours
    # sans un mot à l'écran, que beta.sh semblait attendre indéfiniment.
    #
    # Au sein d'un lot, les écritures d'aides partent en parallèle : ~600
    # requêtes à la suite, c'était une minute d'attente réseau par environnement
    # à chaque déploiement. Chaque aide est une ligne distincte, l'ordre est
    # indifférent. Le client, lui, ne se partage PAS (cf. ECRITURES_PARALLELES).
    local = threading.local()

    def client_du_thread() -> Client:
        if not hasattr(local, "client"):
            local.client = create_client(url, cle)
        return local.client

    def pousser(slug: str, aide: Aide) -> tuple[str, bool]:
        """Écrit une aide, rend (id, créée ?)."""
        db = client_du_thread()
        row = aide_to_row(aide)
        # `raison` (NOT NULL en base) — asymétrie transitoire : tant que les
        # YAML ne portent pas la finalité, un update ne doit pas écraser la
        # valeur déjà en base avec [] ; un insert doit en fournir une.
        if aide.raison:
            row["raison"] = aide.raison
        aide_id = by_slug.get(slug) or by_nom.get(aide.nom)
        if aide_id:
            _reprendre(
                lambda: db.table("aides_v3").update(row).eq("id", aide_id).execute(),
                slug,
            )
            return aide_id, False
        row.setdefault("raison", [])

        def inserer() -> str:
            # Un insert n'est pas idempotent : si la réponse d'un premier essai
            # s'est perdue, la ligne existe déjà. On la cherche avant d'écrire.
            deja = db.table("aides_v3").select("id").eq("slug", slug).execute().data
            if deja:
                return deja[0]["id"]
            return db.table("aides_v3").insert(row).execute().data[0]["id"]

        return _reprendre(inserer, slug), True

    created, updated = 0, 0
    items = list(aides.items())
    with ThreadPoolExecutor(max_workers=ECRITURES_PARALLELES) as pool:
        for start in range(0, len(items), LOT):
            lot = items[start : start + LOT]
            ecrites = list(pool.map(lambda item: pousser(*item), lot))
            lot_ids = [aide_id for aide_id, _ in ecrites]
            created += sum(1 for _, cree in ecrites if cree)
            updated += sum(1 for _, cree in ecrites if not cree)
            lot_conditions = [
                row
                for (_, aide), aide_id in zip(lot, lot_ids, strict=True)
                for row in condition_rows(aide, aide_id)
            ]

            # Effacer puis réinsérer, rejoués ENSEMBLE : la paire est idempotente,
            # l'insert seul ne l'est pas (il doublerait les conditions).
            def remplacer_conditions(ids: list[str] = lot_ids, rows: list = lot_conditions) -> None:
                supabase.table("aide_conditions").delete().in_("aide_id", ids).execute()
                if rows:
                    supabase.table("aide_conditions").insert(rows).execute()

            _reprendre(remplacer_conditions, f"conditions du lot {start // LOT + 1}")
            print(f"  {min(start + LOT, len(items))}/{len(items)} aides")

    print(f"✓ aides : {updated} mises à jour, {created} créées")
    print(
        "Note : les aides en base absentes de data/aides/ (ex. sync Aides-Territoires) "
        "ne sont pas touchées."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
