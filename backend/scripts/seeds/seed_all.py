"""
Peuple une base vide : communes, communes_historique, EPCI, merimee_buildings.

Enchaîne les quatre scripts de seed dans le seul ordre qui fonctionne :
seed_communes_historique.py et seed_communes_epci.py lisent tous deux la table
`communes` pour ne garder que les codes qui existent encore, donc seed_communes.py
passe forcément en premier.

Les variables d'environnement chargées ici sont transmises aux sous-processus, ce
qui neutralise au passage le `load_dotenv` de seed_merimee.py qui pointe encore
sur backend/scripts/.env (chemin resté figé quand le fichier a migré dans seeds/).

Usage, la stack locale démarrée (`supabase start`) :
    cd backend && uv run python scripts/seeds/seed_all.py

Aucune variable à exporter : l'URL et la clé d'écriture sont lues dans
`supabase status`. Pour cibler une autre base, poser SUPABASE_URL et
SUPABASE_SERVICE_KEY (ou SUPABASE_SECRET_KEY) dans l'environnement ou dans
backend/.env.local / backend/.env — elles gardent la priorité — et ajouter
--remote.

Les CSV téléchargés (COG INSEE, population, Mérimée) sont supprimés une fois le
peuplement terminé. En cas d'échec ils sont conservés : les scripts les réutilisent
tels quels, une reprise ne retélécharge donc rien.

Options :
    --skip <etape>   ignorer une étape (répétable) : communes, historique, epci, merimee
    --remote         autoriser une cible qui n'est pas la base locale (garde-fou)
    --garder-csv     ne pas supprimer les CSV téléchargés à la fin
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

SEEDS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SEEDS_DIR.parent.parent

# (nom court, script, description) — l'ordre de la liste EST l'ordre d'exécution.
ETAPES = [
    ("communes", "seed_communes.py", "communes (COG INSEE 2026 + population)"),
    ("historique", "seed_communes_historique.py", "communes_historique (fusions et renommages)"),
    ("epci", "seed_communes_epci.py", "communes.epci_siren / epci_nom (geo.api.gouv.fr)"),
    ("merimee", "seed_merimee.py", "merimee_buildings (CSV data.gouv)"),
]

# Dossiers où les scripts déposent les sources téléchargées, tous sous seeds/.
CACHES = [
    SEEDS_DIR / "cog_ensemble_2026_csv",  # seed_communes.py + seed_communes_historique.py
    SEEDS_DIR / "ensemble",  # population INSEE, seed_communes.py
    SEEDS_DIR / "merimee_csv",  # seed_merimee.py
]

# Tables à recompter en fin de course, pour vérifier que le peuplement a pris.
CONTROLES = [
    ("communes", None),
    ("communes_historique", None),
    ("communes (EPCI renseigné)", "epci_siren"),
    ("merimee_buildings", None),
]


def charger_env() -> None:
    """Charge .env.local puis .env, dans l'ordre de priorité du backend."""
    for nom in (".env.local", ".env"):
        chemin = BACKEND_DIR / nom
        if chemin.exists():
            load_dotenv(chemin)
            print(f"Variables chargées depuis {chemin}")


def env_locale_depuis_cli() -> None:
    """Complète l'environnement depuis `supabase status`, si la stack locale tourne.

    Évite d'avoir à exporter les clés à la main : le CLI est déjà la source de
    vérité pour l'URL et les clés de la base locale. Ne touche à rien si les
    variables sont déjà posées (un .env, ou un export volontaire vers une autre
    base, gardent la priorité).
    """
    if os.environ.get("SUPABASE_URL") and cle_service():
        return

    resultat = subprocess.run(
        ["supabase", "status", "-o", "env"],
        cwd=BACKEND_DIR.parent,
        capture_output=True,
        text=True,
    )
    if resultat.returncode != 0:
        print(
            "❌ Impossible de lire `supabase status` : la stack locale ne tourne pas ?\n"
            "   Lancer `supabase start`, ou poser SUPABASE_URL et SUPABASE_SERVICE_KEY\n"
            "   à la main pour cibler une autre base."
        )
        raise SystemExit(2)

    valeurs = {}
    for ligne in resultat.stdout.splitlines():
        if "=" in ligne:
            nom, _, valeur = ligne.partition("=")
            valeurs[nom.strip()] = valeur.strip().strip('"')

    # SUPABASE_SERVICE_KEY pour les seeds, SUPABASE_SECRET_KEY pour le reste du
    # backend (db.py, load_aides_yaml.py) : les deux conventions cohabitent.
    correspondances = {
        "SUPABASE_URL": "API_URL",
        "SUPABASE_SERVICE_KEY": "SERVICE_ROLE_KEY",
        "SUPABASE_SECRET_KEY": "SECRET_KEY",
    }
    poses = []
    for cible, source in correspondances.items():
        if not os.environ.get(cible) and valeurs.get(source):
            os.environ[cible] = valeurs[source]
            poses.append(cible)
    if poses:
        print(f"Clés locales lues dans `supabase status` : {', '.join(poses)}")


def cle_service() -> str | None:
    """La clé d'écriture, sous l'un ou l'autre de ses deux noms."""
    return os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SECRET_KEY")


def verifier_cible(autoriser_remote: bool) -> str:
    url = os.environ.get("SUPABASE_URL")
    cle = cle_service()
    if not url or not cle:
        print("❌ SUPABASE_URL et SUPABASE_SERVICE_KEY (ou SUPABASE_SECRET_KEY) sont requis.")
        raise SystemExit(2)

    # Les seeds lisent SUPABASE_SERVICE_KEY et lui seul : aligner les deux noms
    # pour qu'un .env qui ne définit que SUPABASE_SECRET_KEY suffise.
    os.environ["SUPABASE_SERVICE_KEY"] = cle

    locale = "127.0.0.1" in url or "localhost" in url
    print(f"Cible : {url}" + ("  (locale)" if locale else ""))
    if not locale and not autoriser_remote:
        print(
            "❌ L'URL ne ressemble pas à la base locale et ces scripts écrivent avec la\n"
            "   clé service_role. Relancer avec --remote pour confirmer."
        )
        raise SystemExit(2)
    return url


def lancer(script: str, libelle: str) -> bool:
    chemin = SEEDS_DIR / script
    print(f"\n{'=' * 70}\n▶ {libelle}\n  {chemin.relative_to(BACKEND_DIR)}\n{'=' * 70}")
    debut = time.monotonic()
    resultat = subprocess.run([sys.executable, str(chemin)], cwd=BACKEND_DIR, env=os.environ)
    duree = time.monotonic() - debut
    if resultat.returncode != 0:
        print(f"\n❌ {script} a échoué (code {resultat.returncode}) après {duree:.0f}s")
        return False
    print(f"\n✅ {libelle} — {duree:.0f}s")
    return True


def resume() -> None:
    """Recompte les tables peuplées ; purement informatif, n'échoue jamais."""
    from supabase import create_client

    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    print(f"\n{'=' * 70}\nLignes en base\n{'=' * 70}")
    for libelle, colonne_non_nulle in CONTROLES:
        table = libelle.split(" ")[0]
        try:
            requete = client.table(table).select("*", count="exact", head=True)
            if colonne_non_nulle:
                requete = requete.not_.is_(colonne_non_nulle, "null")
            print(f"  {libelle:<32} {requete.execute().count}")
        except Exception as erreur:  # noqa: BLE001 — un contrôle raté ne doit rien casser
            print(f"  {libelle:<32} ? ({type(erreur).__name__})")


def nettoyer() -> None:
    """Supprime les sources téléchargées ; les scripts les retéléchargeront au besoin."""
    libere = 0
    supprimes = []
    for dossier in CACHES:
        if not dossier.is_dir():
            continue
        libere += sum(f.stat().st_size for f in dossier.rglob("*") if f.is_file())
        shutil.rmtree(dossier)
        supprimes.append(dossier.name)
    if supprimes:
        print(f"\nCSV supprimés ({libere / 1024 / 1024:.0f} Mo) : {', '.join(supprimes)}")


def main() -> int:
    noms = [nom for nom, _, _ in ETAPES]
    parser = argparse.ArgumentParser(description="Peuple une base vide (référentiels).")
    parser.add_argument("--skip", action="append", choices=noms, default=[], metavar="ETAPE")
    parser.add_argument("--remote", action="store_true", help="autoriser une cible non locale")
    parser.add_argument(
        "--garder-csv",
        dest="garder_csv",
        action="store_true",
        help="ne pas supprimer les CSV téléchargés à la fin",
    )
    args = parser.parse_args()

    charger_env()
    env_locale_depuis_cli()
    verifier_cible(args.remote)

    a_faire = [e for e in ETAPES if e[0] not in args.skip]
    if not a_faire:
        print("Toutes les étapes sont ignorées, rien à faire.")
        return 0

    print("\nÉtapes : " + ", ".join(nom for nom, _, _ in a_faire))
    if args.skip:
        print("Ignorées : " + ", ".join(args.skip))
    print("Premier passage : téléchargement des sources INSEE et data.gouv (plusieurs minutes).")

    debut = time.monotonic()
    for nom, script, libelle in a_faire:
        if not lancer(script, libelle):
            print(
                f"\nArrêt à l'étape « {nom} ». Les étapes suivantes en dépendent peut-être ;\n"
                f"corriger puis relancer avec --skip pour les étapes déjà passées.\n"
                f"Les CSV téléchargés sont conservés, la reprise ne les retéléchargera pas."
            )
            return 1

    resume()
    if args.garder_csv:
        print("\nCSV conservés (--garder-csv).")
    else:
        nettoyer()
    print(f"\n✅ Terminé en {time.monotonic() - debut:.0f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
