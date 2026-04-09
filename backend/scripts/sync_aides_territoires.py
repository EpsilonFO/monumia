"""
Sync aids tagged "Restaurer le patrimoine religieux" from aides-territoires.beta.gouv.fr
into the local aides_v2 table.

Run weekly:
    cd backend && uv run python3 scripts/sync_aides_territoires.py

Requires in backend/.env (or .env.local):
    SUPABASE_URL
    SUPABASE_SECRET_KEY
    AIDES_TERRITOIRES_API_TOKEN   # X-AUTH-TOKEN from your aides-territoires account
"""

import logging
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env.local"), override=True)

import httpx
from supabase import create_client

# ── Config ──────────────────────────────────────────────────────────────

AT_BASE_URL = "https://aides-territoires.beta.gouv.fr"
AT_API_TOKEN = os.environ["AIDES_TERRITOIRES_API_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SECRET_KEY"]
KEYWORD = "patrimoine religieux"
ITEMS_PER_PAGE = 50

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("sync_at")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── API helpers ─────────────────────────────────────────────────────────


def get_jwt() -> str:
    """Exchange X-AUTH-TOKEN for a JWT Bearer token."""
    resp = httpx.get(
        f"{AT_BASE_URL}/api/aids/",
        headers={"X-AUTH-TOKEN": AT_API_TOKEN, "Accept": "application/json"},
        params={"itemsPerPage": 1, "page": 1},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("token")
    if not token:
        raise RuntimeError(
            f"Expected JWT token from X-AUTH-TOKEN exchange, got: {list(data.keys())}"
        )
    log.info("JWT obtained")
    return token


def fetch_all_aids() -> list[dict]:
    """Paginate through /api/aids/ with keyword filter and collect all results."""
    jwt = get_jwt()
    aids: list[dict] = []
    page = 1

    with httpx.Client(timeout=30) as client:
        while True:
            params = {
                "keyword": KEYWORD,
                "itemsPerPage": ITEMS_PER_PAGE,
                "page": page,
            }
            headers = {
                "Authorization": f"Bearer {jwt}",
                "Accept": "application/json",
            }

            log.info("Fetching page %d …", page)
            resp = client.get(f"{AT_BASE_URL}/api/aids/", params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            aids.extend(results)
            log.info(
                "  → %d aids on this page (total so far: %d / %s)",
                len(results),
                len(aids),
                data.get("count", "?"),
            )

            if not data.get("next"):
                break
            page += 1
            time.sleep(0.3)  # gentle rate-limit

    return aids


# ── Mapping helpers ─────────────────────────────────────────────────────

# Map aides-territoires aid type names → our `type` enum values
TYPE_MAP: dict[str, str] = {
    "subvention": "subvention",
    "prêt": "pret",
    "avance remboursable": "pret",
    "autre aide financière": "subvention",
    "ingénierie technique": "label",
    "ingénierie financière": "subvention",
    "ingénierie juridique / administrative": "label",
    "conseil": "label",
    "certificat": "label",
    "label": "label",
}

# Map financers / program keywords → our `categorie` enum values
CATEGORIE_KEYWORDS: list[tuple[list[str], str]] = [
    (["drac", "ministère de la culture", "ministere de la culture"], "etat_drac"),
    (["europe", "feder", "fse", "interreg", "erasmus", "horizon"], "europe"),
    (["fondation"], "fondation"),
    (["mécénat", "mecenat", "mécène"], "mecenat"),
    (["région", "region", "conseil régional"], "region"),
    (
        ["département", "departement", "conseil départemental", "conseil departemental"],
        "departement",
    ),
]


def strip_html(html: str) -> str:
    """Convert HTML to plain text."""
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"</?(p|li|ul|ol|div|h[1-6]|tr|td|th)[^>]*>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def guess_categorie(aid: dict) -> str:
    """Best-effort mapping of financers/programs to our categorie enum."""
    text = " ".join(
        [
            *aid.get("financers", []),
            *aid.get("programs", []),
            *aid.get("categories", []),
        ]
    ).lower()

    for keywords, cat in CATEGORIE_KEYWORDS:
        if any(kw in text for kw in keywords):
            return cat
    return "etat_drac"  # safe default for patrimoine religieux


def guess_type(aid: dict) -> str:
    """Map aid_types list to our type enum. Prefer the first match."""
    if aid.get("is_call_for_project"):
        return "appel_a_projets"

    for at_type in aid.get("aid_types", []):
        mapped = TYPE_MAP.get(at_type.lower().strip())
        if mapped:
            return mapped

    for at_type_full in aid.get("aid_types_full", []):
        name = at_type_full.get("name", "").lower().strip()
        mapped = TYPE_MAP.get(name)
        if mapped:
            return mapped

    return "subvention"


def parse_date(val: str | None) -> str | None:
    """Return ISO date string or None."""
    if not val:
        return None
    return val[:10]  # already YYYY-MM-DD from the API


def build_organisme(aid: dict) -> str:
    financers = aid.get("financers", [])
    if financers:
        return " / ".join(financers)
    instructors = aid.get("instructors", [])
    if instructors:
        return " / ".join(instructors)
    return "Non précisé"


def build_eligibility(aid: dict) -> str | None:
    """Compose full eligibility text from multiple API fields."""
    sections: list[str] = []

    # État d'avancement du projet
    steps = aid.get("mobilization_steps", [])
    if steps:
        sections.append(
            "État d'avancement du projet pour bénéficier du dispositif : " + ", ".join(steps)
        )

    # Dépenses/actions couvertes
    destinations = aid.get("destinations", [])
    if destinations:
        sections.append("Dépenses/actions couvertes: " + ", ".join(destinations))

    # Bénéficiaires visés
    audiences = aid.get("targeted_audiences", [])
    if audiences:
        sections.append("Bénéficiaires visés : " + ", ".join(audiences))

    # Autres critères d'éligibilité (le champ eligibility de l'API)
    raw_eligibility = strip_html(aid.get("eligibility") or "")
    if raw_eligibility:
        sections.append(raw_eligibility)

    return "\n\n".join(sections) if sections else None


def transform_aid(aid: dict) -> dict:
    """Convert an aides-territoires API aid object to an aides_v2 row."""
    name = aid.get("name", "").strip()
    short_title = aid.get("short_title") or name
    if len(short_title) > 80:
        short_title = short_title[:77] + "…"

    description = strip_html(aid.get("description") or "") or "Pas de description disponible"
    eligibility = build_eligibility(aid)

    recurrence = (aid.get("recurrence") or "").lower()
    permanent = recurrence in ("récurrente", "permanente", "")

    taux_min = aid.get("subvention_rate_lower_bound")
    taux_max = aid.get("subvention_rate_upper_bound")

    tags = list(
        {
            *aid.get("programs", []),
            *aid.get("categories", []),
            "aides-territoires",
            "patrimoine religieux",
        }
    )

    return {
        "source_at_slug": aid["slug"],
        "nom": name,
        "nom_court": short_title,
        "description": description,
        "description_longue": description if len(description) > 200 else None,
        "categorie": guess_categorie(aid),
        "type": guess_type(aid),
        "organisme": build_organisme(aid),
        "montant_max": None,
        "taux_max": taux_max,
        "montant_min": taux_min,
        "plancher": None,
        "base_ttc": False,
        "commune_max_population": None,
        "cofinancement_requis": False,
        "architecte_requis": False,
        "conditions_eligibilite_detail": eligibility,
        "demarche_description": None,
        "documents_requis": [],
        "delai_instruction": None,
        "date_ouverture": parse_date(aid.get("start_date")),
        "date_limite": parse_date(aid.get("submission_deadline")),
        "permanent": permanent,
        "url_officielle": aid.get("origin_url"),
        "formulaire_url": aid.get("application_url"),
        "tags": tags,
    }


# ── Main ────────────────────────────────────────────────────────────────


def main():
    log.info("=== Sync aides-territoires → aides_v2 ===")
    log.info('Keyword: "%s"', KEYWORD)

    aids = fetch_all_aids()
    log.info("Fetched %d aids from API", len(aids))

    if not aids:
        log.warning("No aids found — check your API token and keyword")
        return

    created = 0
    updated = 0

    for aid in aids:
        slug = aid.get("slug")
        if not slug:
            log.warning("Skipping aid without slug: %s", aid.get("name", "?"))
            continue

        row = transform_aid(aid)

        existing = supabase.table("aides_v2").select("id").eq("source_at_slug", slug).execute()

        if existing.data:
            uuid = existing.data[0]["id"]
            supabase.table("aides_v2").update(row).eq("id", uuid).execute()
            updated += 1
            log.info("  ↻ updated: %s", row["nom_court"])
        else:
            result = supabase.table("aides_v2").insert(row).execute()
            uuid = result.data[0]["id"]
            created += 1
            log.info("  ✓ created: %s", row["nom_court"])

    log.info("=== Done! %d created, %d updated (total: %d) ===", created, updated, len(aids))


if __name__ == "__main__":
    main()
