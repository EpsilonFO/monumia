"""Lance le skill `ingest-aide` avec un agent DeepSeek appelé par API.

Réimplémente une boucle agentique minimale (tool-calling OpenAI-compatible) :
le SKILL.md sert de prompt système, l'agent dispose d'outils fichiers/bash,
et l'étape 4 (vérification adversariale) est déléguée à un sous-agent frais
via l'outil `spawn_verifier` (conversation vierge, outils en lecture seule).

Usage :
    cd backend && uv run python scripts/ingest_aide_agent.py <slug> [url|pdf ...] \
        [--model deepseek-v4-pro] [--max-turns 80]

Prérequis : DEEPSEEK_API_KEY dans l'environnement (ou backend/.env).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
SKILL_PATH = REPO_ROOT / ".claude" / "skills" / "ingest-aide" / "SKILL.md"

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = (
    "deepseek-v4-pro"  # tool-calling OK, contexte 1M (deepseek-chat déprécié au 2026-07-24)
)
MAX_TOOL_OUTPUT = 60_000  # caractères renvoyés au modèle par appel d'outil
BASH_TIMEOUT = 300  # secondes

# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------


def _truncate(text: str, limit: int = MAX_TOOL_OUTPUT) -> str:
    if len(text) <= limit:
        return text
    return (
        text[:limit]
        + f"\n\n[... tronqué : {len(text) - limit} caractères omis. Relis avec offset/limit.]"
    )


def _resolve(path: str) -> Path:
    """Résout un chemin relatif à la racine du repo, sans en sortir."""
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    p = p.resolve()
    if not p.is_relative_to(REPO_ROOT):
        raise ValueError(f"Chemin hors du repo interdit : {path}")
    return p


def tool_read_file(path: str, offset: int = 0, limit: int = 800) -> str:
    p = _resolve(path)
    if not p.exists():
        return f"ERREUR : fichier introuvable : {path}"
    if p.suffix.lower() == ".pdf":
        # DeepSeek ne lit pas les PDF : extraction texte via pdftotext si dispo
        try:
            out = subprocess.run(
                ["pdftotext", "-layout", str(p), "-"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if out.returncode == 0:
                lines = out.stdout.splitlines()
                return _truncate("\n".join(lines[offset : offset + limit]))
            return f"ERREUR pdftotext : {out.stderr[:500]}"
        except FileNotFoundError:
            return "ERREUR : pdftotext non installé (brew install poppler). Passe par snapshot_source.py qui convertit en markdown."
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as e:  # noqa: BLE001
        return f"ERREUR de lecture : {e}"
    total = len(lines)
    chunk = lines[offset : offset + limit]
    body = "\n".join(f"{offset + i + 1}\t{line}" for i, line in enumerate(chunk))
    header = f"[{path} — lignes {offset + 1}-{offset + len(chunk)} sur {total}]\n"
    return _truncate(header + body)


def tool_write_file(path: str, content: str) -> str:
    p = _resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"OK : {len(content)} caractères écrits dans {p.relative_to(REPO_ROOT)}"


def tool_edit_file(path: str, old_string: str, new_string: str) -> str:
    p = _resolve(path)
    if not p.exists():
        return f"ERREUR : fichier introuvable : {path}"
    text = p.read_text(encoding="utf-8")
    count = text.count(old_string)
    if count == 0:
        return "ERREUR : old_string introuvable dans le fichier (correspondance exacte requise)."
    if count > 1:
        return f"ERREUR : old_string présent {count} fois — fournis un extrait plus long et unique."
    p.write_text(text.replace(old_string, new_string, 1), encoding="utf-8")
    return "OK : remplacement effectué."


def tool_bash(command: str) -> str:
    try:
        out = subprocess.run(
            command,
            shell=True,
            cwd=str(BACKEND_DIR),
            capture_output=True,
            text=True,
            timeout=BASH_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return f"ERREUR : timeout après {BASH_TIMEOUT}s"
    parts = []
    if out.stdout:
        parts.append(out.stdout)
    if out.stderr:
        parts.append(f"[stderr]\n{out.stderr}")
    parts.append(f"[exit code: {out.returncode}]")
    return _truncate("\n".join(parts))


def tool_web_fetch(url: str) -> str:
    """Fetch exploratoire d'une URL → markdown, SANS créer de snapshot.

    Pour décider si une page mérite un snapshot (snapshot_source.py reste la
    seule référence citables des quotes).
    """
    import html2text
    import httpx

    try:
        resp = httpx.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; MonumiaIngest/1.0; +https://monumia.fr)"
            },
            follow_redirects=True,
            timeout=30,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        return f"ERREUR HTTP : {e}"
    content_type = resp.headers.get("content-type", "")
    if "pdf" in content_type or url.lower().endswith(".pdf"):
        return (
            "C'est un PDF : snapshotte-le directement via snapshot_source.py puis lis le snapshot."
        )
    h = html2text.HTML2Text()
    h.body_width = 0
    h.ignore_images = True
    return _truncate(
        f"[fetch exploratoire — les quotes doivent venir d'un SNAPSHOT, pas d'ici]\nurl finale : {resp.url}\n\n{h.handle(resp.text)}"
    )


TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Lit un fichier texte (ou PDF via pdftotext) du repo. Chemins relatifs à la racine du repo. Renvoie les lignes numérotées.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "offset": {
                        "type": "integer",
                        "description": "Ligne de départ (0-indexée), défaut 0",
                    },
                    "limit": {"type": "integer", "description": "Nombre de lignes, défaut 800"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Écrit (ou écrase) un fichier. Chemin relatif à la racine du repo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Remplacement exact d'une chaîne unique dans un fichier (équivalent str-replace).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": (
                "Fetch exploratoire d'une URL (rendu markdown, non sauvegardé). Sert à repérer "
                "les bonnes pages/PDF (règlement, conditions) avant de les snapshotter. "
                "INTERDIT d'en citer des quotes : toute quote vient d'un snapshot."
            ),
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": f"Exécute une commande shell (cwd = backend/, timeout {BASH_TIMEOUT}s). Sert notamment pour snapshot_source.py et lint_aides_data.py.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
]

VERIFIER_SPEC = {
    "type": "function",
    "function": {
        "name": "spawn_verifier",
        "description": (
            "Étape 4 du skill : lance un sous-agent adversarial FRAIS (qui n'a pas vu ton "
            "raisonnement) avec le prompt fourni. Il dispose de read_file et bash (lecture seule). "
            "Renvoie son rapport final."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Le prompt de vérification adversariale, construit selon le modèle du skill.",
                },
            },
            "required": ["prompt"],
        },
    },
}

# ---------------------------------------------------------------------------
# Boucle agentique
# ---------------------------------------------------------------------------


def _file_block(path: Path, max_chars: int = 120_000) -> str:
    """Contenu d'un fichier balisé pour injection dans un prompt."""
    rel = path.relative_to(REPO_ROOT)
    if not path.exists():
        return f'<fichier path="{rel}">(inexistant)</fichier>'
    text = path.read_text(encoding="utf-8", errors="replace")
    return f'<fichier path="{rel}">\n{_truncate(text, max_chars)}\n</fichier>'


def _verifier_context(slug: str) -> str:
    """Pré-charge YAML, schéma et snapshots texte pour le vérificateur (économise ses tours de lecture)."""
    parts = [
        _file_block(BACKEND_DIR / "data" / "aides" / f"{slug}.yaml"),
        _file_block(BACKEND_DIR / "aides_schema.py"),
    ]
    src_dir = BACKEND_DIR / "data" / "sources" / slug
    if src_dir.exists():
        for p in sorted(src_dir.iterdir()):
            if p.suffix == ".md":
                parts.append(_file_block(p))
            elif p.suffix == ".pdf":
                parts.append(
                    f"(snapshot PDF non inliné, lis-le avec read_file : {p.relative_to(REPO_ROOT)})"
                )
    return "\n\n".join(parts)


def run_agent_loop(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    tools_spec: list[dict],
    dispatch,
    max_turns: int,
    label: str,
) -> str:
    """Boucle tool-calling standard. Renvoie le dernier message texte de l'agent."""
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    for turn in range(max_turns):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools_spec,
            temperature=0.0,
        )
        msg = resp.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        if msg.content:
            print(f"\n[{label} · tour {turn + 1}] {msg.content}\n", flush=True)

        if not msg.tool_calls:
            return msg.content or ""

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError as e:
                result = f"ERREUR : arguments JSON invalides : {e}"
            else:
                preview = json.dumps(args, ensure_ascii=False)[:200]
                print(f"[{label}] ▶ {name}({preview})", flush=True)
                try:
                    result = dispatch(name, args)
                except Exception as e:  # noqa: BLE001
                    result = f"ERREUR outil {name} : {e}"
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})

    return "ERREUR : max_turns atteint sans réponse finale."


def make_dispatch(
    client: OpenAI,
    model: str,
    max_turns: int,
    allow_write: bool = True,
    slug: str | None = None,
    verifier_model: str | None = None,
):
    def dispatch(name: str, args: dict) -> str:
        if name == "read_file":
            return tool_read_file(args["path"], args.get("offset", 0), args.get("limit", 800))
        if name == "web_fetch":
            return tool_web_fetch(args["url"])
        if name == "bash":
            return tool_bash(args["command"])
        if name == "write_file":
            if not allow_write:
                return "ERREUR : outil non autorisé pour le vérificateur."
            return tool_write_file(args["path"], args["content"])
        if name == "edit_file":
            if not allow_write:
                return "ERREUR : outil non autorisé pour le vérificateur."
            return tool_edit_file(args["path"], args["old_string"], args["new_string"])
        if name == "spawn_verifier":
            print("\n[verifier] === lancement du sous-agent adversarial ===\n", flush=True)
            vmodel = verifier_model or model
            context = (
                f"\n\n=== FICHIERS PRÉ-CHARGÉS (déjà à jour, ne les relis pas) ===\n\n{_verifier_context(slug)}"
                if slug
                else ""
            )
            report = run_agent_loop(
                client=client,
                model=vmodel,
                system_prompt=(
                    "Tu es un vérificateur adversarial de données d'éligibilité. "
                    "Tu travailles dans le repo Monumia (cwd des commandes bash : backend/). "
                    "Tu disposes des outils read_file et bash (lecture seule : n'écris rien). "
                    "Le YAML, le schéma et les snapshots texte sont déjà fournis dans le "
                    "message : ne les relis pas, sers-toi de read_file uniquement pour les PDF "
                    "ou un fichier manquant. "
                    "Suis strictement la mission donnée par l'utilisateur et termine par un "
                    "rapport structuré : pour chaque problème, sévérité (bloquant/mineur), "
                    "citation source, correction proposée. Si rien sur un axe, dis-le."
                ),
                user_prompt=args["prompt"] + context,
                tools_spec=[
                    t for t in TOOLS_SPEC if t["function"]["name"] in ("read_file", "bash")
                ],
                dispatch=make_dispatch(client, vmodel, max_turns, allow_write=False),
                max_turns=max_turns,
                label="verifier",
            )
            return _truncate("RAPPORT DU VÉRIFICATEUR ADVERSARIAL :\n\n" + report)
        return f"ERREUR : outil inconnu {name}"

    return dispatch


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingestion d'une aide via un agent DeepSeek (skill ingest-aide)."
    )
    parser.add_argument("slug", help="Slug de l'aide (backend/data/aides/<slug>.yaml)")
    parser.add_argument(
        "sources", nargs="*", help="URL(s) ou chemin(s) PDF des sources officielles"
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL, help=f"Modèle DeepSeek (défaut : {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--verifier-model",
        default=None,
        help="Modèle du vérificateur adversarial (défaut : même que --model). Ex. deepseek-v4-flash pour accélérer.",
    )
    parser.add_argument(
        "--max-turns", type=int, default=80, help="Tours max de la boucle agentique (défaut : 80)"
    )
    args = parser.parse_args()

    load_dotenv(BACKEND_DIR / ".env")
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print(
            "ERREUR : DEEPSEEK_API_KEY absent de l'environnement (ou backend/.env).",
            file=sys.stderr,
        )
        return 1

    skill = SKILL_PATH.read_text(encoding="utf-8")
    # Retire le frontmatter YAML du SKILL.md
    if skill.startswith("---"):
        skill = skill.split("---", 2)[2]

    system_prompt = f"""Tu es un agent d'ingestion de données pour Monumia.
Tu travailles dans le repo situé à la racine ; les commandes bash s'exécutent dans backend/.
Tu disposes des outils : read_file, write_file, edit_file, bash, web_fetch, spawn_verifier.

Adaptations du skill à ton harnais :
- ÉTAPE 0 DÉJÀ FAITE : le contenu de README.md, aides_schema.py, facts.yaml et du
  YAML existant de l'aide est fourni dans le message utilisateur. NE LES RELIS PAS
  avec read_file, ça gaspille des tours. read_file sert pour les snapshots et tout
  fichier non fourni.
- « Lire » un fichier = read_file. Les PDF passent par pdftotext automatiquement.
- web_fetch sert UNIQUEMENT à explorer (trouver le règlement, la page conditions).
  Toute source retenue DOIT être snapshotée via snapshot_source.py, et les quotes
  viennent exclusivement du snapshot.
- L'étape 4 (vérification adversariale) se fait via l'outil spawn_verifier :
  construis le prompt selon le modèle du skill et passe-le tel quel.
- Les snapshots se font via bash : `uv run python scripts/snapshot_source.py ...`.
- Le lint via bash : `uv run python scripts/lint_aides_data.py`.
- Ta DERNIÈRE réponse (sans appel d'outil) doit être la fiche de review humaine
  de l'étape 5, complète. Ensuite STOP : pas de commit, pas de load_aides_yaml.py.

Voici le skill à exécuter à la lettre :

{skill}"""

    # Sources : arguments CLI, sinon source.url_officielle du YAML existant
    sources = list(args.sources)
    aide_path = BACKEND_DIR / "data" / "aides" / f"{args.slug}.yaml"
    if not sources:
        if not aide_path.exists():
            print(
                f"ERREUR : {aide_path.relative_to(REPO_ROOT)} n'existe pas et aucune source fournie.\n"
                "Pour une nouvelle aide, passe au moins une URL ou un PDF en argument.",
                file=sys.stderr,
            )
            return 1
        import yaml

        data = yaml.safe_load(aide_path.read_text(encoding="utf-8")) or {}
        url = (data.get("source") or {}).get("url_officielle")
        if not url:
            print(
                f"ERREUR : pas de source.url_officielle dans {aide_path.relative_to(REPO_ROOT)} "
                "et aucune source fournie en argument.",
                file=sys.stderr,
            )
            return 1
        sources = [url]
        print(f"Source résolue depuis le YAML : {url}")

    sources_txt = "\n".join(f"- {s}" for s in sources)
    etape0 = "\n\n".join(
        _file_block(p)
        for p in (
            BACKEND_DIR / "data" / "README.md",
            BACKEND_DIR / "aides_schema.py",
            BACKEND_DIR / "data" / "facts.yaml",
            aide_path,
        )
    )

    user_prompt = f"""/ingest-aide {args.slug}

Slug : {args.slug}
Sources fournies :
{sources_txt}

Exécute le skill de bout en bout (étapes 0 à 5) et termine par la fiche de review.

=== ÉTAPE 0 PRÉ-CHARGÉE (contenu à jour, ne pas relire ces fichiers) ===

{etape0}"""

    client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)
    dispatch = make_dispatch(
        client,
        args.model,
        args.max_turns,
        slug=args.slug,
        verifier_model=args.verifier_model,
    )

    final = run_agent_loop(
        client=client,
        model=args.model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        tools_spec=TOOLS_SPEC + [VERIFIER_SPEC],
        dispatch=dispatch,
        max_turns=args.max_turns,
        label="agent",
    )

    review_dir = BACKEND_DIR / "data" / "reviews"
    review_dir.mkdir(parents=True, exist_ok=True)
    review_path = review_dir / f"{args.slug}-deepseek-review.md"
    review_path.write_text(final, encoding="utf-8")
    print(
        f"\n{'=' * 70}\nFiche de review sauvegardée : {review_path.relative_to(REPO_ROOT)}\n{'=' * 70}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
