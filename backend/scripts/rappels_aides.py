"""Job quotidien des rappels d'aides : échéances qui approchent, aides qui
deviennent disponibles.

Tourne une fois par jour (9 h Europe/Paris, cf. `scripts/cron-rappels.sh` à la
racine du dépôt). Deux temps :

  1. Le CATALOGUE. L'état d'ouverture de chaque aide servie est comparé à
     l'instantané de la veille (`aides_veille_etat`). Ce qui en sort, ce sont
     les aides devenues disponibles :
       * une aide qui entre au catalogue guichet ouvert (ingestion, typage
         achevé) → « nouvelle aide » ;
       * une aide qui était fermée et ne l'est plus, que sa `date_ouverture`
         soit atteinte ou que la veille ait posé les dates d'une nouvelle
         session → « le dépôt vient d'ouvrir ».
     Une aide qui arrive déjà fermée ne dit rien : elle s'annoncera le jour
     de son ouverture.
  2. Les PROJETS. Pour chaque compte, le diagnostic déterministe de chacun de
     ses chantiers est rejoué (purement CPU, ~2 ms, YAML en cache) :
       * une aide devenue disponible s'annonce si elle tombe dans l'un des
         trois seaux du haut : elle passe les critères automatiques de la
         fiche et aucune réponse déjà donnée ne l'écarte ;
       * une `date_limite` qui atteint un palier de rappel (30 jours par
         défaut, réglable par utilisateur) → email « approche de sa date
         limite ».

Trois garde-fous portent tout le reste :

  * `aide_rappels_envoyes` — un rappel donné (utilisateur, projet, aide, nature,
    palier, date annoncée) ne part qu'une fois. Sans lui, le job répéterait le
    même email tous les matins.
  * l'instantané du catalogue — vide au premier passage, il se remplit sans
    rien annoncer : sinon le premier matin présenterait tout le catalogue
    comme neuf.
  * l'OFFRE — les rappels par email font partie de ce que vendent les offres
    Veille et Multi-monuments (`services/offres.py`). Un compte sur l'offre
    gratuite est écarté entier, avant même de rejouer ses diagnostics :
    `peut_recevoir_rappels` est le point de branchement unique, les
    préférences de notification ne tranchent qu'ensuite.

Usage :
    cd backend && uv run python scripts/rappels_aides.py [options]

  --dry-run          détaille ce qui serait envoyé, sans rien envoyer ni écrire
                     (l'instantané du catalogue non plus)
  --today AAAA-MM-JJ fige la date du jour. Elle sert AUSSI au moteur : la
                     fenêtre de candidature de chaque aide est recalculée à
                     cette date, donc le rejeu est fidèle et pas seulement
                     décalé sur l'arithmétique des paliers. L'instantané n'est
                     alors ni lu ni écrit : les ouvertures se déduisent des
                     dates (fermée la veille, ouverte ce jour-là)
  --amorcer          mise en service : fait tout comme un vrai passage (instantané
                     du catalogue, journal des rappels) SANS envoyer d'email.
                     Les rappels dus aujourd'hui sont tenus pour envoyés et ne
                     partiront jamais ; tout rappel qui devient dû ensuite
                     (nouveau compte, nouveau projet, palier suivant) partira
  --annoncer SLUG    traite l'aide comme nouvelle au catalogue ce jour-là
                     (répétable). Pour tester l'annonce d'une aide sans
                     attendre une ingestion, ou la relancer à la main
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
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env.local", override=True)

from supabase import Client, create_client

from config import default_app_url
from eligibility_engine import disponibilite, engine_ready_aides
from routers.aides import deterministic_diagnostic_for, merge_projet_into_monument
from routers.monuments import fetch_user_monuments
from services import catalogue_admin
from services import stripe_billing as billing
from services.email_service import (
    BlocProjet,
    render_rappels_email,
    send_rappel_email,
    titre_rappels,
)
from services.rappels_service import (
    LIBELLE_STATUT,
    Disponibilite,
    EtatAide,
    RappelEcheance,
    RappelOuverture,
    comparer_catalogue,
    disponibilites_recentes,
    disponibles_pour_le_projet,
    echeances_a_rappeler,
    matches_a_portee,
    normaliser_paliers,
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


def compte_a_droit_aux_rappels(supabase: Client, user_id: str) -> bool:
    """L'offre du compte ouvre-t-elle les rappels par email ?

    Délègue à `stripe_billing.peut_recevoir_rappels`, l'autorité unique sur les
    droits d'un compte. Fonction locale pour que les tests du job la remplacent
    sans toucher au module de facturation.
    """
    return billing.peut_recevoir_rappels(supabase, user_id)


def charger_utilisateurs(supabase: Client, user_id: str | None) -> list[dict]:
    """Comptes à traiter, avec ce qu'il faut pour écrire l'email et le régler.

    Par pages : PostgREST plafonne une réponse à 1 000 lignes, et le compte
    1 001 ne recevrait jamais rien sans que personne ne s'en aperçoive.
    """
    colonnes = "id, email, prenom, notification_preferences"
    if user_id:
        return supabase.table("users").select(colonnes).eq("id", user_id).execute().data or []
    comptes: list[dict] = []
    page = 1000
    while True:
        rows = (
            supabase.table("users")
            .select(colonnes)
            .order("id")
            .range(len(comptes), len(comptes) + page - 1)
            .execute()
            .data
        ) or []
        comptes += rows
        if len(rows) < page:
            return comptes


def projets_de(supabase: Client, user_id: str) -> tuple[list[dict], dict[str, dict], dict]:
    """Projets visibles par l'utilisateur, leurs monuments, et les populations.

    Même règle de visibilité que `/dashboard` : les chantiers d'un monument dont
    on est membre de l'équipe, plus ceux qu'on a rejoints projet par projet.
    """
    monuments, population_by_code, roles_propres = fetch_user_monuments(supabase, user_id)
    if not monuments:
        return [], {}, population_by_code

    monuments_by_id = {m["id"]: m for m in monuments}
    equipe_monument = {m["id"] for m in monuments if m.get("my_role")}
    mes_projets = set(roles_propres)

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
    # `nature` sert de `kind` : « nouvelle » ou « ouverture ». La date annoncée
    # est le jour où l'aide est devenue disponible, si bien qu'une session
    # suivante (fermée puis rouverte) s'annonce à nouveau.
    return (projet_id, o.aide_id, o.nature, None, o.disponible_depuis.isoformat())


# ---------------------------------------------------------------------------
# Le catalogue : quelles aides viennent de devenir disponibles
# ---------------------------------------------------------------------------


def etat_du_catalogue(supabase: Client, jour: date) -> dict[str, bool]:
    """Chaque aide servie, et si son guichet est ouvert ce jour-là.

    Le catalogue SERVI : celui du diagnostic (`catalogue_effectif`, aides
    retirées exclues), restreint aux aides que le moteur traite. Une aide
    encore `untyped` n'est proposée à personne ; le jour où son typage
    s'achève, elle entre ici et s'annonce comme nouvelle.
    """
    aides = engine_ready_aides(catalogue_admin.catalogue_effectif(supabase).aides)
    return {slug: disponibilite(aide, jour) == "maintenant" for slug, aide in aides.items()}


def charger_instantane(supabase: Client) -> dict[str, EtatAide]:
    rows = (
        supabase.table("aides_veille_etat")
        .select("aide_id, ouverte, entree_le, ouverte_depuis")
        .execute()
        .data
    ) or []
    return {
        r["aide_id"]: EtatAide(
            ouverte=bool(r["ouverte"]),
            entree_le=date.fromisoformat(r["entree_le"]),
            ouverte_depuis=date.fromisoformat(r["ouverte_depuis"]) if r["ouverte_depuis"] else None,
        )
        for r in rows
    }


def enregistrer_instantane(
    supabase: Client, avant: dict[str, EtatAide], apres: dict[str, EtatAide]
) -> None:
    """N'écrit que les lignes qui ont changé : d'un matin à l'autre, presque rien."""
    maintenant = datetime.now(UTC).isoformat()
    rows = [
        {
            "aide_id": aide_id,
            "maj_le": maintenant,
            "ouverte": e.ouverte,
            "entree_le": e.entree_le.isoformat(),
            "ouverte_depuis": e.ouverte_depuis.isoformat() if e.ouverte_depuis else None,
        }
        for aide_id, e in apres.items()
        if avant.get(aide_id) != e
    ]
    for debut in range(0, len(rows), 500):
        supabase.table("aides_veille_etat").upsert(
            rows[debut : debut + 500], on_conflict="aide_id"
        ).execute()


def disponibilites_simulees(supabase: Client, jour: date) -> dict[str, Disponibilite]:
    """Les ouvertures de ce jour-là, déduites des seules dates du calendrier.

    Sert à `--today` et à `--agenda`, où l'instantané (qui dit l'état RÉEL du
    catalogue, aujourd'hui) n'a pas de sens : la veille est reconstituée en
    recalculant le catalogue à `jour - 1`. Ce qu'on perd, c'est ce que seul
    l'instantané sait : une aide nouvelle, ou une session posée par la veille
    sans `date_ouverture`. `--annoncer` couvre le premier cas.
    """
    hier = etat_du_catalogue(supabase, jour - timedelta(days=1))
    # Des dates d'entrée et d'ouverture arbitrairement anciennes : seules les
    # bascules du jour tombent dans la fenêtre d'annonce.
    precedent = {
        slug: EtatAide(ouverte=o, entree_le=date.min, ouverte_depuis=date.min if o else None)
        for slug, o in hier.items()
    }
    etat = comparer_catalogue(precedent, etat_du_catalogue(supabase, jour), jour)
    return disponibilites_recentes(etat, jour, fenetre_jours=0)


def disponibilites_du_jour(
    supabase: Client,
    today: date,
    *,
    simulation: bool,
    ecrire: bool,
    annoncer: list[str],
) -> dict[str, Disponibilite]:
    """Les aides à annoncer ce matin, calculées une fois pour tous les comptes.

    L'instantané est écrit AVANT les envois : si le job s'interrompt ensuite,
    la bascule reste datée du bon jour, et la fenêtre d'annonce laisse le
    lendemain rattraper les emails manqués sans doublon (le journal veille).
    """
    if simulation:
        dispos = disponibilites_simulees(supabase, today)
    else:
        avant = charger_instantane(supabase)
        apres = comparer_catalogue(avant, etat_du_catalogue(supabase, today), today)
        if not avant:
            log.info(
                "Instantané du catalogue vide : premier passage, %d aide(s) "
                "enregistrée(s) sans annonce.",
                len(apres),
            )
        if ecrire:
            enregistrer_instantane(supabase, avant, apres)
        dispos = disponibilites_recentes(apres, today)

    for slug in annoncer:
        dispos[slug] = Disponibilite(aide_id=slug, nature="nouvelle", depuis=today)

    for d in sorted(dispos.values(), key=lambda d: (d.nature, d.aide_id)):
        log.info("  disponible  %-10s %-45s depuis le %s", d.nature, d.aide_id, d.depuis)
    return dispos


# ---------------------------------------------------------------------------
# Traitement d'un utilisateur
# ---------------------------------------------------------------------------


def projets_a_rappeler(supabase: Client, user_id: str) -> list[tuple[dict, dict, int | None]]:
    """Chantiers sur lesquels un rappel peut partir : (projet, monument, population).

    Le droit au service se joue au niveau du COMPTE (`compte_a_droit_aux_rappels`,
    vérifié par l'appelant), pas du monument : le détail des aides est gratuit,
    ce qui se vend c'est la veille. Ici on ne fait que rattacher chaque chantier
    à sa fiche et à la population de sa commune.
    """
    projets, monuments_by_id, population_by_code = projets_de(supabase, user_id)
    retenus = []
    for projet in projets:
        monument = monuments_by_id.get(projet["monument_id"])
        if monument is None:
            continue
        retenus.append((projet, monument, population_by_code.get(monument.get("code_insee") or "")))
    return retenus


def diagnostic_du_projet(
    supabase: Client, projet: dict, monument: dict, population: int | None, today: date
) -> dict:
    """Diagnostic déterministe d'un chantier, daté de `today`.

    Le même que la page projet : fiche du monument + cadrage du chantier +
    réponses déjà données à SON questionnaire, surcouche d'administration
    comprise (une aide retirée ne s'annonce pas).

    La date compte doublement : elle fixe la fenêtre de candidature de chaque
    aide (`disponibilite`) ET sert d'origine au calcul des paliers. C'est ce qui
    rend `--today` fidèle, et donc testable.
    """
    return deterministic_diagnostic_for(
        merge_projet_into_monument(monument, projet),
        population,
        projet.get("questionnaire") or {},
        supabase=supabase,
        today=today,
    )


def collecter(
    supabase: Client,
    user: dict,
    today: date,
    app_url: str,
    disponibilites: dict[str, Disponibilite],
) -> tuple[list[BlocProjet], list[tuple]]:
    """Ce qu'il y a à annoncer à cet utilisateur, et les clés à journaliser.

    Retourne (un bloc par chantier qui a quelque chose à annoncer, clés de
    dédoublonnage). Un bloc porte ses échéances ET ses aides devenues
    disponibles : tout part dans le même email.
    """
    user_id = user["id"]
    prefs = user.get("notification_preferences") or {}
    veut_echeances = prefs.get("rappelsEcheances", True)
    veut_ouvertures = prefs.get("rappelsOuvertures", True)
    if not veut_echeances and not veut_ouvertures:
        return [], []
    # L'offre décide du droit au service, les préférences du souhait : un compte
    # gratuit sort ici, sans qu'on rejoue un seul de ses diagnostics.
    if not compte_a_droit_aux_rappels(supabase, user_id):
        return [], []

    paliers = normaliser_paliers(prefs.get("rappelDelaisJours"))
    cibles = projets_a_rappeler(supabase, user_id)
    if not cibles:
        return [], []

    deja = rappels_deja_envoyes(supabase, user_id)

    blocs: list[BlocProjet] = []
    nouvelles_cles: list[tuple] = []

    for projet, monument, population in cibles:
        diagnostic = diagnostic_du_projet(supabase, projet, monument, population, today)

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
                for o in disponibles_pour_le_projet(diagnostic, disponibilites)
                if _cle_ouverture(projet["id"], o) not in deja
            ]
            if veut_ouvertures and disponibilites
            else []
        )
        if not echeances and not ouvertures:
            continue

        blocs.append(
            BlocProjet(
                projet_titre=projet.get("titre") or "",
                monument_nom=monument.get("nom") or "Monument",
                projet_url=f"{app_url}/app/projets/{projet['id']}",
                projet_id=projet["id"],
                echeances=tuple(echeances),
                ouvertures=tuple(ouvertures),
            )
        )
        nouvelles_cles += [_cle_echeance(projet["id"], e) for e in echeances]
        nouvelles_cles += [_cle_ouverture(projet["id"], o) for o in ouvertures]

    return blocs, nouvelles_cles


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


def notifier_in_app(supabase: Client, user_id: str, blocs: list[BlocProjet]) -> None:
    """Une notification in-app par aide annoncée, en écho de l'email.

    Le projet part dans `lien_vers`, pour que la cloche ouvre l'aide DANS ce
    chantier, comme le lien de l'email.
    """
    rows = []
    for bloc in blocs:
        projet_id = bloc.projet_id
        for e in bloc.echeances:
            type_notif, categorie = NOTIF_ECHEANCE
            rows.append(
                {
                    "user_id": user_id,
                    "type": type_notif,
                    "categorie": categorie,
                    "titre": f"{e.aide_nom} : dépôt à boucler",
                    "message": f"{bloc.monument_nom} : la date limite tombe le "
                    f"{e.date_limite.isoformat()} ({e.jours_restants} jours).",
                    "lien_vers": {"type": "aide", "id": e.aide_id, "projetId": projet_id},
                }
            )
        for o in bloc.ouvertures:
            titre = (
                f"Nouvelle aide : {o.aide_nom}"
                if o.nature == "nouvelle"
                else f"{o.aide_nom} : le dépôt est ouvert"
            )
            type_notif, categorie = NOTIF_OUVERTURE
            rows.append(
                {
                    "user_id": user_id,
                    "type": type_notif,
                    "categorie": categorie,
                    "titre": titre,
                    "message": f"{bloc.monument_nom} · {bloc.projet_titre or 'Projet de travaux'} : "
                    f"{LIBELLE_STATUT.get(o.statut, 'à étudier')}.",
                    "lien_vers": {"type": "aide", "id": o.aide_id, "projetId": projet_id},
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
                "      %-9s %-45s depuis le %s  → %s",
                o.nature,
                o.aide_id,
                o.disponible_depuis,
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
    disponibilites: dict[str, Disponibilite],
    apercu: Path | None = None,
    amorcer: bool = False,
) -> tuple[int, int]:
    """Traite un utilisateur. Retourne (aides en échéance, aides disponibles).

    UN email au plus par compte et par passage : échéances et aides devenues
    disponibles, sur tous ses chantiers, partent ensemble.

    `amorcer` : journalise sans envoyer. C'est le passage de mise en service,
    pour que le premier matin ne déverse pas d'un coup tous les rappels déjà
    dus sur des comptes qui n'ont jamais rien reçu.
    """
    blocs, cles = collecter(supabase, user, today, app_url, disponibilites)
    n_e = sum(len(b.echeances) for b in blocs)
    n_o = sum(len(b.ouvertures) for b in blocs)
    if not n_e and not n_o:
        return 0, 0

    email = user.get("email") or ""
    prenom = user.get("prenom") or ""
    reglages_url = f"{app_url}/app/profil"

    log.info("%s : %d échéance(s), %d aide(s) disponible(s)", email or user["id"], n_e, n_o)
    if dry_run or apercu:
        _detailler(blocs)

    html = render_rappels_email(prenom=prenom, blocs=blocs, reglages_url=reglages_url)
    if apercu:
        _ecrire_apercu(apercu, user, today, "rappels", html)

    if dry_run:
        return n_e, n_o
    if amorcer:
        journaliser(supabase, user["id"], cles)
        return n_e, n_o
    if not email:
        log.warning("Compte %s sans email : rien envoyé.", user["id"])
        return 0, 0

    sujet, _ = titre_rappels(blocs)
    send_rappel_email(to_email=email, subject=sujet, html=html)
    notifier_in_app(supabase, user["id"], blocs)
    # Journalisé APRÈS l'envoi : si l'envoi échoue, le rappel repart demain.
    # Une fois journalisé, il ne repart plus jamais : le lendemain, l'échéance
    # relève du même palier et de la même date limite, donc de la même clé.
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
    prévoit, pas ce qu'il reste à envoyer. Seules les ouvertures DATÉES y
    figurent : une aide nouvelle ou une session posée par la veille ne se
    prévoit pas, elle se constate (cf. `--annoncer` pour la simuler).
    """
    prefs = user.get("notification_preferences") or {}
    paliers = normaliser_paliers(prefs.get("rappelDelaisJours"))
    cibles = projets_a_rappeler(supabase, user["id"])
    log.info(
        "%s : %d chantier(s), paliers %s",
        user.get("email") or user["id"],
        len(cibles),
        list(paliers),
    )
    # L'agenda reste affiché : il répond à « que prévoit le calendrier ? ». Mais
    # un testeur doit savoir que, sur ce compte, le job réel n'enverrait rien.
    if not compte_a_droit_aux_rappels(supabase, user["id"]):
        log.warning(
            "    offre sans rappels par email : le job n'enverrait RIEN à ce compte "
            "(il faut une offre Veille ou Multi-monuments)."
        )

    # Les ouvertures d'un jour valent pour tout le catalogue : calculées une
    # fois, partagées entre les chantiers.
    ouvertures_par_jour: dict[date, dict[str, Disponibilite]] = {}
    for projet, monument, population in cibles:
        log.info(
            "  %s · %s",
            monument.get("nom") or "Monument",
            projet.get("titre") or "(projet sans titre)",
        )

        # Dates candidates, déduites du calendrier des aides à portée
        # aujourd'hui ET de celles qui patientent en « Disponibles bientôt ».
        candidates: set[date] = set()
        diag_du_jour = diagnostic_du_projet(supabase, projet, monument, population, today)
        for match in matches_a_portee(diag_du_jour):
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
            diag = diagnostic_du_projet(supabase, projet, monument, population, jour)
            for e in echeances_a_rappeler(diag, jour, paliers):
                lignes.append(
                    (jour, "échéance ", e.aide_id, f"limite {e.date_limite} (J-{e.jours_restants})")
                )
            if jour not in ouvertures_par_jour:
                ouvertures_par_jour[jour] = disponibilites_simulees(supabase, jour)
            for o in disponibles_pour_le_projet(diag, ouvertures_par_jour[jour]):
                lignes.append((jour, "ouverture", o.aide_id, f"ouvre le {o.disponible_depuis}"))

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
    parser.add_argument(
        "--today",
        help="fige la date du jour (AAAA-MM-JJ) ; l'instantané du catalogue n'est alors pas touché",
    )
    parser.add_argument(
        "--annoncer",
        metavar="SLUG",
        action="append",
        default=[],
        help="traite cette aide comme nouvelle au catalogue (répétable)",
    )
    parser.add_argument(
        "--amorcer",
        action="store_true",
        help="mise en service : tient les rappels dus aujourd'hui pour envoyés, sans envoyer",
    )
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
    if args.amorcer and (args.dry_run or args.preview or args.today or args.agenda):
        # L'amorçage ÉCRIT : le combiner avec un mode qui simule ou qui change
        # la date marquerait comme envoyés des rappels d'un autre jour.
        parser.error("--amorcer ne se combine ni avec --dry-run, --preview, --today ni --agenda")

    today = date.fromisoformat(args.today) if args.today else date.today()
    app_url = default_app_url()
    supabase = _client()

    users = charger_utilisateurs(supabase, args.user)
    log.info("%d compte(s) à examiner, date du jour : %s", len(users), today)

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

    disponibilites = disponibilites_du_jour(
        supabase,
        today,
        simulation=args.today is not None,
        ecrire=not dry_run,
        annoncer=args.annoncer,
    )

    total_e = total_o = 0
    echecs = 0
    for user in users:
        try:
            n_e, n_o = traiter(
                supabase, user, today, app_url, dry_run, disponibilites, apercu, args.amorcer
            )
        except Exception:
            # Un compte en erreur (fiche incomplète, diagnostic qui casse) ne
            # doit pas priver tous les autres de leurs rappels.
            echecs += 1
            log.exception("Échec sur le compte %s", user.get("id"))
            continue
        total_e += n_e
        total_o += n_o

    log.info(
        "Terminé%s : %d échéance(s), %d aide(s) disponible(s), %d compte(s) en erreur.",
        " (dry-run)" if dry_run else " (amorçage, rien envoyé)" if args.amorcer else "",
        total_e,
        total_o,
        echecs,
    )
    return 1 if echecs else 0


if __name__ == "__main__":
    raise SystemExit(main())
