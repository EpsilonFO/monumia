"""Job quotidien des rappels d'aides : échéances qui approchent, guichets qui ouvrent.

Tourne une fois par jour (9 h Europe/Paris, cf. `scripts/cron-rappels.sh` à la
racine du dépôt). Pour chaque utilisateur, il rejoue le diagnostic déterministe
de chacun de ses projets — purement CPU, ~2 ms par projet, les YAML sont en
cache — puis compare le calendrier des aides à portée à la date du jour :

  * une `date_limite` qui atteint un palier de rappel (30 jours par défaut,
    réglable par utilisateur) → email « approche de sa date limite » ;
  * une `date_ouverture` qui vient d'être franchie → email « le dépôt vient
    d'ouvrir », l'aide ayant quitté « Disponibles bientôt » d'elle-même.

Deux garde-fous portent tout le reste :

  * `aide_rappels_envoyes` — un rappel donné (utilisateur, projet, aide, nature,
    palier, date annoncée) ne part qu'une fois. Sans lui, le job répéterait le
    même email tous les matins pendant un mois.
  * le PAYWALL — les projets dont le monument n'est pas débloqué sont écartés.
    Le produit caviarde le nom des aides d'un monument verrouillé
    (`redact_diagnostic_if_locked`) ; un email les nommerait en clair.

Usage :
    cd backend && uv run python scripts/rappels_aides.py [options]

  --dry-run          détaille ce qui serait envoyé, sans rien envoyer ni écrire
  --today AAAA-MM-JJ fige la date du jour. Elle sert AUSSI au moteur : la
                     fenêtre de candidature de chaque aide est recalculée à
                     cette date, donc le rejeu est fidèle et pas seulement
                     décalé sur l'arithmétique des paliers
  --user <uuid>      ne traite qu'un utilisateur
  --preview DOSSIER  écrit les emails rendus en HTML (implique --dry-run)
  --agenda           n'envoie rien : pour chaque rappel à venir, donne la date
                     à passer en --today pour le déclencher. C'est le point de
                     départ de tout test — deviner cette date à la main suppose
                     de refaire le calendrier des aides, les paliers du compte
                     et l'éligibilité du chantier
  --horizon N        profondeur de l'agenda, en jours avant et après aujourd'hui
                     (défaut : 400). Les dates passées comptent : ce sont les
                     plus commodes à rejouer
"""

import argparse
import logging
import os
import sys
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env.local", override=True)

from supabase import Client, create_client

from config import default_app_url
from routers.aides import deterministic_diagnostic_for, merge_projet_into_monument
from routers.monuments import fetch_user_monuments
from services import stripe_billing as billing
from services.email_service import (
    BlocProjet,
    render_echeances_email,
    render_ouvertures_email,
    send_rappel_email,
)
from services.project_access import projet_ids_membre
from services.rappels_service import (
    LIBELLE_STATUT,
    RappelEcheance,
    RappelOuverture,
    echeances_a_rappeler,
    matches_a_portee,
    normaliser_paliers,
    ouvertures_franchies,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("rappels")

# Le journal du job doit rester lisible, dans un cron comme à l'écran. Deux
# bavards à faire taire : httpx trace chaque requête Supabase, et le moteur
# résume chaque diagnostic — or `--agenda` en lance des dizaines par chantier.
for _bavard in ("httpx", "httpcore", "eligibility_engine"):
    logging.getLogger(_bavard).setLevel(logging.WARNING)

# Notification in-app posée en même temps que l'email : la cloche du produit et
# la boîte mail doivent dire la même chose. Catégories de `notification_category`.
NOTIF_ECHEANCE = ("urgent", "deadline_proche")
NOTIF_OUVERTURE = ("opportunite", "nouvelle_aide")


# ---------------------------------------------------------------------------
# Accès aux données
# ---------------------------------------------------------------------------


def _client() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])


def charger_utilisateurs(supabase: Client, user_id: str | None) -> list[dict]:
    """Comptes à traiter, avec ce qu'il faut pour écrire l'email et le régler."""
    query = supabase.table("users").select("id, email, prenom, notification_preferences")
    if user_id:
        query = query.eq("id", user_id)
    return query.execute().data or []


def projets_de(supabase: Client, user_id: str) -> tuple[list[dict], dict[str, dict], dict]:
    """Projets visibles par l'utilisateur, leurs monuments, et les populations.

    Même règle de visibilité que `/dashboard` : les chantiers d'un monument dont
    on est membre de l'équipe, plus ceux qu'on a rejoints projet par projet.
    """
    monuments, population_by_code = fetch_user_monuments(supabase, user_id)
    if not monuments:
        return [], {}, population_by_code

    monuments_by_id = {m["id"]: m for m in monuments}
    equipe_monument = {m["id"] for m in monuments if m.get("my_role")}
    mes_projets = set(projet_ids_membre(supabase, user_id))

    rows = (
        supabase.table("projets")
        .select("*")
        .in_("monument_id", list(monuments_by_id))
        # Un chantier clos n'a plus d'échéance à tenir.
        .is_("cloture_at", "null")
        .execute()
        .data
    ) or []
    projets = [p for p in rows if p["monument_id"] in equipe_monument or p["id"] in mes_projets]
    return projets, monuments_by_id, population_by_code


def rappels_deja_envoyes(supabase: Client, user_id: str) -> set[tuple]:
    """Clés des rappels déjà partis, dans la forme de `_cle_*` ci-dessous."""
    rows = (
        supabase.table("aide_rappels_envoyes")
        .select("projet_id, aide_id, kind, palier_jours, date_reference")
        .eq("user_id", user_id)
        .execute()
        .data
    ) or []
    return {
        (r["projet_id"], r["aide_id"], r["kind"], r["palier_jours"], r["date_reference"])
        for r in rows
    }


def _cle_echeance(projet_id: str, r: RappelEcheance) -> tuple:
    return (projet_id, r.aide_id, "echeance", r.palier_jours, r.date_limite.isoformat())


def _cle_ouverture(projet_id: str, o: RappelOuverture) -> tuple:
    return (projet_id, o.aide_id, "ouverture", None, o.date_ouverture.isoformat())


# ---------------------------------------------------------------------------
# Traitement d'un utilisateur
# ---------------------------------------------------------------------------


def projets_a_rappeler(supabase: Client, user_id: str) -> list[tuple[dict, dict, int | None]]:
    """Chantiers sur lesquels un rappel peut partir : (projet, monument, population).

    C'est ici que s'applique le PAYWALL. Le produit caviarde le nom des aides
    d'un monument non débloqué (`redact_diagnostic_if_locked`) ; un email les
    nommerait en clair, alors on écarte le chantier entier.
    """
    projets, monuments_by_id, population_by_code = projets_de(supabase, user_id)
    if not projets:
        return []

    acces = billing.access_snapshot(supabase, user_id)
    debloques = set(acces["unlockedMonumentIds"])
    tout_debloque = acces["allAccess"]

    retenus = []
    for projet in projets:
        monument = monuments_by_id.get(projet["monument_id"])
        if monument is None:
            continue
        if not tout_debloque and monument["id"] not in debloques:
            continue
        retenus.append((projet, monument, population_by_code.get(monument.get("code_insee") or "")))
    return retenus


def diagnostic_du_projet(projet: dict, monument: dict, population: int | None, today: date) -> dict:
    """Diagnostic déterministe d'un chantier, daté de `today`.

    La date compte doublement : elle fixe la fenêtre de candidature de chaque
    aide (`disponibilite`) ET sert d'origine au calcul des paliers. C'est ce qui
    rend `--today` fidèle, et donc testable.
    """
    return deterministic_diagnostic_for(
        merge_projet_into_monument(monument, projet),
        population,
        projet.get("questionnaire") or {},
        today,
    )


def collecter(
    supabase: Client, user: dict, today: date, app_url: str
) -> tuple[list[BlocProjet], list[BlocProjet], list[tuple]]:
    """Ce qu'il y a à annoncer à cet utilisateur, et les clés à journaliser.

    Retourne (blocs d'échéances, blocs d'ouvertures, clés de dédoublonnage).
    Les deux listes de blocs sont indépendantes : un utilisateur peut n'avoir
    activé que l'une des deux familles de rappel.
    """
    user_id = user["id"]
    prefs = user.get("notification_preferences") or {}
    veut_echeances = prefs.get("rappelsEcheances", True)
    veut_ouvertures = prefs.get("rappelsOuvertures", True)
    if not veut_echeances and not veut_ouvertures:
        return [], [], []

    paliers = normaliser_paliers(prefs.get("rappelDelaisJours"))
    cibles = projets_a_rappeler(supabase, user_id)
    if not cibles:
        return [], [], []

    deja = rappels_deja_envoyes(supabase, user_id)

    blocs_echeances: list[BlocProjet] = []
    blocs_ouvertures: list[BlocProjet] = []
    nouvelles_cles: list[tuple] = []

    for projet, monument, population in cibles:
        diagnostic = diagnostic_du_projet(projet, monument, population, today)

        echeances = (
            [
                e
                for e in echeances_a_rappeler(diagnostic, today, paliers)
                if _cle_echeance(projet["id"], e) not in deja
            ]
            if veut_echeances
            else []
        )
        ouvertures = (
            [
                o
                for o in ouvertures_franchies(diagnostic, today)
                if _cle_ouverture(projet["id"], o) not in deja
            ]
            if veut_ouvertures
            else []
        )
        if not echeances and not ouvertures:
            continue

        bloc = BlocProjet(
            projet_titre=projet.get("titre") or "",
            monument_nom=monument.get("nom") or "Monument",
            projet_url=f"{app_url}/app/projets/{projet['id']}",
        )
        if echeances:
            blocs_echeances.append(replace(bloc, echeances=tuple(echeances)))
            nouvelles_cles += [_cle_echeance(projet["id"], e) for e in echeances]
        if ouvertures:
            blocs_ouvertures.append(replace(bloc, ouvertures=tuple(ouvertures)))
            nouvelles_cles += [_cle_ouverture(projet["id"], o) for o in ouvertures]

    return blocs_echeances, blocs_ouvertures, nouvelles_cles


def journaliser(supabase: Client, user_id: str, cles: list[tuple]) -> None:
    """Marque les rappels comme envoyés. `upsert` plutôt qu'`insert` : deux
    exécutions du job le même matin ne doivent pas échouer sur l'index unique."""
    if not cles:
        return
    rows = [
        {
            "user_id": user_id,
            "projet_id": projet_id,
            "aide_id": aide_id,
            "kind": kind,
            "palier_jours": palier,
            "date_reference": date_reference,
        }
        for projet_id, aide_id, kind, palier, date_reference in cles
    ]
    supabase.table("aide_rappels_envoyes").upsert(
        rows,
        on_conflict="user_id,projet_id,aide_id,kind,palier_jours,date_reference",
        ignore_duplicates=True,
    ).execute()


def notifier_in_app(supabase: Client, user_id: str, blocs: list[BlocProjet], kind: str) -> None:
    """Une notification in-app par aide annoncée, en écho de l'email."""
    type_notif, categorie = NOTIF_ECHEANCE if kind == "echeance" else NOTIF_OUVERTURE
    rows = []
    for bloc in blocs:
        for e in bloc.echeances:
            rows.append(
                {
                    "user_id": user_id,
                    "type": type_notif,
                    "categorie": categorie,
                    "titre": f"{e.aide_nom} — dépôt à boucler",
                    "message": f"{bloc.monument_nom} : la date limite tombe le "
                    f"{e.date_limite.isoformat()} ({e.jours_restants} jours).",
                    "lien_vers": {"type": "aide", "id": e.aide_id},
                }
            )
        for o in bloc.ouvertures:
            rows.append(
                {
                    "user_id": user_id,
                    "type": type_notif,
                    "categorie": categorie,
                    "titre": f"{o.aide_nom} — le dépôt est ouvert",
                    "message": f"{bloc.monument_nom} : le guichet a ouvert le "
                    f"{o.date_ouverture.isoformat()}.",
                    "lien_vers": {"type": "aide", "id": o.aide_id},
                }
            )
    if rows:
        supabase.table("notifications").insert(rows).execute()


def _detailler(blocs: list[BlocProjet]) -> None:
    """Dit à voix haute ce qui partirait. C'est ce que lit un --dry-run."""
    for bloc in blocs:
        log.info("    %s · %s", bloc.monument_nom, bloc.projet_titre or "(projet sans titre)")
        for e in bloc.echeances:
            log.info(
                "      échéance  %-45s limite %s  (J-%d, palier %d)",
                e.aide_id,
                e.date_limite,
                e.jours_restants,
                e.palier_jours,
            )
        for o in bloc.ouvertures:
            log.info(
                "      ouverture %-45s ouvert le %s  → %s",
                o.aide_id,
                o.date_ouverture,
                LIBELLE_STATUT.get(o.statut, o.statut),
            )


def _ecrire_apercu(dossier: Path, user: dict, today: date, nom: str, html: str) -> None:
    """Écrit l'email rendu sur disque, à ouvrir dans un navigateur.

    Le repli console de `send_rappel_email` ne montre pas la mise en page, et
    brancher Resend pour vérifier une couleur de pastille est disproportionné.
    """
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / f"{today.isoformat()}-{user['id'][:8]}-{nom}.html"
    fichier.write_text(html, encoding="utf-8")
    log.info("    aperçu → %s", fichier)


def traiter(
    supabase: Client,
    user: dict,
    today: date,
    app_url: str,
    dry_run: bool,
    apercu: Path | None = None,
) -> tuple[int, int]:
    """Traite un utilisateur. Retourne (aides en échéance, aides ouvertes)."""
    blocs_e, blocs_o, cles = collecter(supabase, user, today, app_url)
    n_e = sum(len(b.echeances) for b in blocs_e)
    n_o = sum(len(b.ouvertures) for b in blocs_o)
    if not n_e and not n_o:
        return 0, 0

    email = user.get("email") or ""
    prenom = user.get("prenom") or ""
    reglages_url = f"{app_url}/app/profil"

    log.info("%s — %d échéance(s), %d ouverture(s)", email or user["id"], n_e, n_o)
    if dry_run or apercu:
        _detailler(blocs_e + blocs_o)

    html_e = (
        render_echeances_email(prenom=prenom, blocs=blocs_e, reglages_url=reglages_url)
        if n_e
        else None
    )
    html_o = (
        render_ouvertures_email(prenom=prenom, blocs=blocs_o, reglages_url=reglages_url)
        if n_o
        else None
    )

    if apercu:
        if html_e:
            _ecrire_apercu(apercu, user, today, "echeances", html_e)
        if html_o:
            _ecrire_apercu(apercu, user, today, "ouvertures", html_o)

    if dry_run:
        return n_e, n_o
    if not email:
        log.warning("Compte %s sans email : rien envoyé.", user["id"])
        return 0, 0

    # Deux emails distincts quand les deux s'appliquent : un rappel d'échéance
    # et une ouverture de guichet n'appellent pas la même action, et chacun se
    # règle séparément dans les préférences.
    if html_e:
        send_rappel_email(to_email=email, subject="Vos aides arrivent à échéance", html=html_e)
        notifier_in_app(supabase, user["id"], blocs_e, "echeance")
    if html_o:
        send_rappel_email(
            to_email=email, subject="Le dépôt vient d'ouvrir pour vos aides", html=html_o
        )
        notifier_in_app(supabase, user["id"], blocs_o, "ouverture")

    # Journalisé APRÈS l'envoi : si l'envoi échoue, le rappel repart demain.
    journaliser(supabase, user["id"], cles)
    return n_e, n_o


# ---------------------------------------------------------------------------
# Agenda : à quelle date chaque rappel partirait
# ---------------------------------------------------------------------------


def agenda(supabase: Client, user: dict, today: date, horizon: int) -> None:
    """Affiche, pour chaque rappel à venir, la date qui le déclenche.

    Attendre le bon jour pour vérifier un rappel n'est pas une option, et
    deviner la date à la main non plus : elle dépend du calendrier de l'aide,
    des paliers du compte, et de l'éligibilité du chantier. Ce mode SIMULE —
    il rejoue le diagnostic à chaque date candidate et rapporte ce qui part,
    plutôt que de refaire le calcul dans son coin et risquer d'en diverger.

    Le journal des envois est ignoré : l'agenda dit ce que le calendrier
    prévoit, pas ce qu'il reste à envoyer.
    """
    prefs = user.get("notification_preferences") or {}
    paliers = normaliser_paliers(prefs.get("rappelDelaisJours"))
    cibles = projets_a_rappeler(supabase, user["id"])
    log.info(
        "%s — %d chantier(s) débloqué(s), paliers %s",
        user.get("email") or user["id"],
        len(cibles),
        list(paliers),
    )

    for projet, monument, population in cibles:
        log.info(
            "  %s · %s",
            monument.get("nom") or "Monument",
            projet.get("titre") or "(projet sans titre)",
        )

        # Dates candidates, déduites du calendrier des aides à portée
        # aujourd'hui ET de celles qui patientent en « Disponibles bientôt ».
        candidates: set[date] = set()
        for match in matches_a_portee(diagnostic_du_projet(projet, monument, population, today)):
            aide = match["aide"]
            ouverture = _iso(aide.get("dateOuverture"))
            limite = _iso(aide.get("dateLimite"))
            if ouverture:
                candidates.add(ouverture)
            if limite and not aide.get("permanent"):
                candidates |= {limite - timedelta(days=p) for p in paliers}

        # Fenêtre symétrique : une date PASSÉE est le meilleur cas de test, elle
        # est certaine d'être atteignable — `--today` remonte le temps aussi bien
        # qu'il l'avance. Le futur, lui, doit porter assez loin pour couvrir les
        # dispositifs annuels, dont la session suivante est à plus d'un an.
        debut, fin = today - timedelta(days=horizon), today + timedelta(days=horizon)
        lignes = []
        for jour in sorted(d for d in candidates if debut <= d <= fin):
            diag = diagnostic_du_projet(projet, monument, population, jour)
            for e in echeances_a_rappeler(diag, jour, paliers):
                lignes.append(
                    (jour, "échéance ", e.aide_id, f"limite {e.date_limite} (J-{e.jours_restants})")
                )
            for o in ouvertures_franchies(diag, jour):
                lignes.append((jour, "ouverture", o.aide_id, f"ouvre le {o.date_ouverture}"))

        if not lignes:
            log.info("    rien à annoncer entre %s et %s.", debut, fin)
            continue
        for jour, kind, aide_id, detail in lignes:
            log.info("    --today %s  %s  %-45s %s", jour, kind, aide_id, detail)


def _iso(valeur: object) -> date | None:
    if not isinstance(valeur, str) or not valeur:
        return None
    try:
        return date.fromisoformat(valeur[:10])
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Entrée
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Rappels d'aides par email.")
    parser.add_argument("--dry-run", action="store_true", help="n'envoie rien, n'écrit rien")
    parser.add_argument("--today", help="fige la date du jour (AAAA-MM-JJ)")
    parser.add_argument("--user", help="ne traiter qu'un utilisateur, par son id")
    parser.add_argument(
        "--preview",
        metavar="DOSSIER",
        help="écrit les emails rendus en HTML dans DOSSIER, à ouvrir dans un navigateur",
    )
    parser.add_argument(
        "--agenda",
        action="store_true",
        help="n'envoie rien : liste les dates à passer en --today pour déclencher chaque rappel",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=400,
        help="profondeur de l'agenda, en jours avant ET après aujourd'hui "
        "(défaut : 400, de quoi couvrir la session suivante d'un dispositif annuel)",
    )
    args = parser.parse_args()

    today = date.fromisoformat(args.today) if args.today else date.today()
    app_url = default_app_url()
    supabase = _client()

    users = charger_utilisateurs(supabase, args.user)
    log.info("%d compte(s) à examiner — date du jour : %s", len(users), today)

    if args.agenda:
        for user in users:
            try:
                agenda(supabase, user, today, args.horizon)
            except Exception:
                log.exception("Échec sur le compte %s", user.get("id"))
        return 0

    # --preview implique --dry-run : produire un aperçu ne doit pas envoyer
    # l'email pour de vrai, ni marquer le rappel comme parti.
    apercu = Path(args.preview) if args.preview else None
    dry_run = args.dry_run or apercu is not None

    total_e = total_o = 0
    echecs = 0
    for user in users:
        try:
            n_e, n_o = traiter(supabase, user, today, app_url, dry_run, apercu)
        except Exception:
            # Un compte en erreur (fiche incomplète, diagnostic qui casse) ne
            # doit pas priver tous les autres de leurs rappels.
            echecs += 1
            log.exception("Échec sur le compte %s", user.get("id"))
            continue
        total_e += n_e
        total_o += n_o

    log.info(
        "Terminé%s — %d échéance(s), %d ouverture(s), %d compte(s) en erreur.",
        " (dry-run)" if dry_run else "",
        total_e,
        total_o,
        echecs,
    )
    return 1 if echecs else 0


if __name__ == "__main__":
    raise SystemExit(main())
