"""Emails sortants via Resend, avec repli console en dev.

Trois familles : l'invitation d'un collaborateur, les rappels calendaires sur
les aides (échéance qui approche, aide qui devient disponible), et l'avis
interne d'inscription envoyé à l'équipe à chaque compte créé.

Les fonctions `render_*` sont pures (testées). Les `send_*` lisent la config
dans l'environnement et sortent toutes par `_expedier` : Resend si
`RESEND_API_KEY` est posée, sinon le Mailpit du Supabase local si `SMTP_DEV`
l'est, sinon la console (développement sans compte Resend).
"""

import logging
import os
import smtplib
from dataclasses import dataclass
from datetime import date
from email.message import EmailMessage
from email.utils import parseaddr
from html import escape

from services.rappels_service import LIBELLE_STATUT, RappelEcheance, RappelOuverture

logger = logging.getLogger(__name__)

DEFAULT_FROM = "Monumia <invitations@monumia.fr>"

# Expéditeur distinct des invitations : un rappel automatique et une invitation
# nominative ne se filtrent ni ne se désabonnent de la même façon.
DEFAULT_FROM_RAPPELS = "Monumia <rappels@monumia.fr>"


def _expedier(
    *,
    nature: str,
    sender: str,
    to: list[str],
    subject: str,
    html: str,
    text: str | None = None,
    reply_to: str | None = None,
) -> None:
    """Point de sortie unique : Resend, sinon Mailpit, sinon la console.

    `SMTP_DEV` (« localhost:54325 ») envoie au Mailpit du Supabase local, celui
    de http://localhost:54324 : on y voit le rendu réel au lieu d'une ligne de
    log. Sans lui, ou si Mailpit ne répond pas, l'email est écrit en console.
    """
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    if api_key:
        import resend

        resend.api_key = api_key
        message: dict = {"from": sender, "to": to, "subject": subject, "html": html}
        if text:
            message["text"] = text
        if reply_to:
            message["reply_to"] = reply_to
        resend.Emails.send(message)  # pyright: ignore[reportArgumentType]
        return

    smtp_dev = os.environ.get("SMTP_DEV", "").strip()
    if smtp_dev:
        hote, _, port = smtp_dev.rpartition(":")
        message_smtp = EmailMessage()
        message_smtp["From"] = sender
        message_smtp["To"] = ", ".join(to)
        message_smtp["Subject"] = subject
        if reply_to:
            message_smtp["Reply-To"] = reply_to
        message_smtp.set_content(text or "(version HTML seulement)")
        message_smtp.add_alternative(html, subtype="html")
        try:
            with smtplib.SMTP(hote or "localhost", int(port), timeout=5) as smtp:
                smtp.send_message(message_smtp)
            return
        except (OSError, ValueError):
            logger.warning("Mailpit injoignable sur %s, repli sur la console.", smtp_dev)

    logger.warning(
        "[DEV] Resend non configuré — %s non envoyé.\n  À: %s\n  Sujet: %s%s",
        nature,
        ", ".join(to),
        subject,
        f"\n{text}" if text else "",
    )


def expediteur_invitation(inviter_nom: str) -> str:
    """« Marie Dupont via Monumia <invitations@monumia.fr> ».

    L'invitation est le message d'une personne, pas d'une marque : Gmail range
    volontiers en Promotions un expéditeur générique, beaucoup moins un nom
    propre (même usage que les partages Google Docs). L'adresse reste celle du
    domaine authentifié chez Resend, seul le nom affiché change.
    """
    nom_marque, adresse = parseaddr(os.environ.get("RESEND_FROM", "").strip() or DEFAULT_FROM)
    nom = " ".join(inviter_nom.replace('"', "").replace("<", "").replace(">", "").split())
    if not nom or nom == "Un membre":
        return f"{nom_marque or 'Monumia'} <{adresse}>"
    return f'"{nom} via Monumia" <{adresse}>'


def render_invitation_email(
    *,
    inviter_nom: str,
    monument_nom: str,
    invite_url: str,
    expires_label: str,
    projet_titre: str | None = None,
) -> str:
    """HTML de l'email d'invitation.

    `projet_titre` renseigné = invitation sur UN chantier précis. Le dire est
    nécessaire : le destinataire n'aura accès qu'à celui-là, et découvrir après
    coup qu'on ne voit pas le reste du monument passerait pour une panne.

    On ne promet que ce que l'invité verra. Une invitation fait toujours entrer
    en `member` (cf. `routers/invitations.py`), et l'onglet Aides d'un projet
    demande au moins `co_owner` (`canAccessAides` côté front) : l'email ne
    parle donc pas des aides.

    Mise en page volontairement sobre, celle d'un message écrit à la main : pas
    de bandeau, pas d'encadrés colorés. Un gabarit chargé ressemble à une
    newsletter, et Gmail le classe alors en Promotions.
    """
    inviter = escape(inviter_nom)
    monument = escape(monument_nom)
    url = escape(invite_url, quote=True)
    if projet_titre:
        objet = (
            f"sur le projet de travaux <strong>« {escape(projet_titre)} »</strong> "
            f"du monument <strong>« {monument} »</strong>"
        )
        portee = (
            "Vous verrez ses dossiers et ses documents, ainsi que la fiche du monument en lecture."
        )
    else:
        objet = f"sur le monument <strong>« {monument} »</strong>"
        portee = "Vous pourrez consulter le monument et ses projets de travaux, et y déposer vos documents."
    return f"""\
<div style="font-family:Inter,Arial,sans-serif;font-size:15px;line-height:1.55;color:#222b35;max-width:520px">
  <p style="margin:0 0 16px">Bonjour,</p>
  <p style="margin:0 0 16px">{inviter} vous invite à collaborer {objet} sur Monumia.</p>
  <p style="margin:0 0 24px">{portee}</p>
  <p style="margin:0 0 24px"><a href="{url}" style="display:inline-block;background:#f17105;color:#fff;text-decoration:none;font-weight:600;padding:10px 20px;border-radius:6px">Rejoindre</a></p>
  <p style="margin:0 0 16px;font-size:13px;color:#5b6573">Si le bouton ne s'ouvre pas, copiez ce lien dans votre navigateur :<br><a href="{url}" style="color:#0a369d">{url}</a></p>
  <p style="margin:0 0 16px;font-size:13px;color:#5b6573">Ce lien expire le {escape(expires_label)}. Si vous ne connaissez pas {inviter}, ignorez simplement cet email.</p>
  <p style="margin:0;font-size:13px;color:#0a369d;font-weight:600">Monumia</p>
</div>"""


def render_invitation_text(
    *,
    inviter_nom: str,
    monument_nom: str,
    invite_url: str,
    expires_label: str,
    projet_titre: str | None = None,
) -> str:
    """Version texte de l'invitation, envoyée avec le HTML.

    Un email sans partie texte est un signal de publipostage pour les filtres,
    et certains clients (ou lecteurs d'écran) n'affichent que celle-ci.
    """
    if projet_titre:
        objet = f"sur le projet de travaux « {projet_titre} » du monument « {monument_nom} »"
        portee = (
            "Vous verrez ses dossiers et ses documents, ainsi que la fiche du monument en lecture."
        )
    else:
        objet = f"sur le monument « {monument_nom} »"
        portee = "Vous pourrez consulter le monument et ses projets de travaux, et y déposer vos documents."
    return (
        f"Bonjour,\n\n"
        f"{inviter_nom} vous invite à collaborer {objet} sur Monumia.\n\n"
        f"{portee}\n\n"
        f"Pour rejoindre : {invite_url}\n\n"
        f"Ce lien expire le {expires_label}. Si vous ne connaissez pas {inviter_nom}, "
        f"ignorez simplement cet email.\n\n"
        f"Monumia\n"
    )


def send_invitation_email(
    *,
    to_email: str,
    inviter_nom: str,
    monument_nom: str,
    invite_url: str,
    expires_label: str,
    projet_titre: str | None = None,
    inviter_email: str | None = None,
) -> None:
    """Envoie l'email d'invitation (cf. `_expedier` pour les replis de dev).

    `inviter_email` devient le Reply-To : répondre à l'invitation écrit à celui
    qui invite, pas à une adresse de service que personne ne lit.
    """
    contenu = {
        "inviter_nom": inviter_nom,
        "monument_nom": monument_nom,
        "invite_url": invite_url,
        "expires_label": expires_label,
        "projet_titre": projet_titre,
    }
    subject = (
        f"{inviter_nom} vous invite sur un projet de « {monument_nom} »"
        if projet_titre
        else f"{inviter_nom} vous invite sur le monument « {monument_nom} »"
    )
    _expedier(
        nature="email d'invitation",
        sender=expediteur_invitation(inviter_nom),
        to=[to_email],
        subject=subject,
        html=render_invitation_email(**contenu),
        text=render_invitation_text(**contenu),
        reply_to=inviter_email or None,
    )


# ---------------------------------------------------------------------------
# Rappels calendaires sur les aides
# ---------------------------------------------------------------------------

MOIS_FR = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def date_fr(jour: date) -> str:
    """« 12 mars 2027 ». `strftime('%B')` dépend de la locale du conteneur, qui
    n'est pas garantie francophone — d'où la table en dur."""
    return f"{jour.day} {MOIS_FR[jour.month - 1]} {jour.year}"


def montant_fr(montant: int | float | None) -> str | None:
    """« 120 000 € », espace fine comme séparateur de milliers."""
    if montant is None:
        return None
    return f"{int(montant):,} €".replace(",", " ")


def jours_fr(jours: int) -> str:
    """Le temps restant, dit comme on le dirait à voix haute."""
    if jours <= 0:
        return "aujourd'hui"
    if jours == 1:
        return "demain"
    return f"dans {jours} jours"


@dataclass(frozen=True)
class BlocProjet:
    """Un chantier et ce qu'il y a à y annoncer.

    Les emails de rappel sont groupés par projet : c'est l'unité où
    l'utilisateur agit, et un même monument peut porter plusieurs chantiers
    dont les aides n'ont rien à voir entre elles.
    """

    projet_titre: str
    monument_nom: str
    projet_url: str
    projet_id: str = ""
    echeances: tuple[RappelEcheance, ...] = ()
    ouvertures: tuple[RappelOuverture, ...] = ()


def aide_url(projet_url: str, aide_id: str) -> str:
    """La fiche de l'aide DANS le projet (`/app/projets/:id/aides/:slug`) : le
    lien de l'email ouvre l'aide avec le diagnostic de ce chantier."""
    return f"{projet_url}/aides/{aide_id}"


def _en_tete_bloc(bloc: BlocProjet) -> str:
    # Nom du monument et titre du projet sont saisis par l'utilisateur : échappés.
    titre = escape(bloc.projet_titre or "Projet de travaux")
    return f"""\
      <div style="margin:22px 0 10px">
        <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#8a8a8a">{escape(bloc.monument_nom)}</div>
        <a href="{bloc.projet_url}" style="font-size:16px;font-weight:600;color:#072a72;text-decoration:none">{titre}</a>
      </div>"""


def _ligne_aide(*, nom: str, url: str, accroche: str, detail: str, accent: str) -> str:
    """Une aide dans la liste : nom cliquable, une accroche datée, un détail."""
    return f"""\
      <div style="border-left:3px solid {accent};background:#fdf9f0;border-radius:0 8px 8px 0;padding:12px 16px;margin:0 0 8px">
        <a href="{url}" style="font-size:15px;font-weight:600;color:#0a369d;text-decoration:none">{escape(nom)}</a>
        <div style="margin-top:4px;font-size:14px;font-weight:600;color:{accent}">{escape(accroche)}</div>
        <div style="margin-top:2px;font-size:13px;color:#6b6b6b">{escape(detail)}</div>
        <a href="{url}" style="display:inline-block;margin-top:8px;font-size:13px;font-weight:600;color:#f17105;text-decoration:none">Voir l'aide dans mon projet →</a>
      </div>"""


def _enveloppe(*, prenom: str, titre: str, chapeau: str, corps: str, reglages_url: str) -> str:
    """Charte Monumia, commune aux deux emails de rappel."""
    salutation = f"Bonjour {escape(prenom)}," if prenom else "Bonjour,"
    return f"""\
<div style="background:#fdf9f0;padding:32px 0;font-family:Inter,Arial,sans-serif;color:#222b35">
  <div style="max-width:560px;margin:0 auto;background:#fffefb;border:1px solid #ece3d2;border-radius:12px;overflow:hidden">
    <div style="background:#0a369d;color:#fff;padding:18px 28px;font-size:18px;font-weight:700">Monumia</div>
    <div style="padding:28px">
      <p style="margin:0 0 16px">{salutation}</p>
      <h1 style="margin:0 0 8px;font-size:20px;line-height:1.3;color:#072a72">{escape(titre)}</h1>
      <p style="margin:0 0 8px;font-size:14px;color:#6b6b6b">{escape(chapeau)}</p>
{corps}
      <p style="margin:26px 0 0;font-size:12px;color:#8a8a8a">Vous recevez cet email parce que les rappels sur vos aides sont activés. <a href="{reglages_url}" style="color:#0a369d">Modifier mes rappels</a>.</p>
    </div>
  </div>
</div>"""


def _lignes_echeances(bloc: BlocProjet) -> list[str]:
    lignes = []
    for e in bloc.echeances:
        montant = montant_fr(e.montant_max)
        detail = f"Date limite : {date_fr(e.date_limite)}"
        if montant:
            detail += f" · jusqu'à {montant}"
        lignes.append(
            _ligne_aide(
                nom=e.aide_nom,
                url=aide_url(bloc.projet_url, e.aide_id),
                accroche=f"Dépôt à boucler {jours_fr(e.jours_restants)}",
                detail=detail,
                # Rouge à une semaine ou moins, orange au-delà : la couleur
                # doit dire l'urgence avant qu'on ait lu la date.
                accent="#c0392b" if e.jours_restants <= 7 else "#f17105",
            )
        )
    return lignes


def _accroche_ouverture(o: RappelOuverture) -> str:
    statut = LIBELLE_STATUT.get(o.statut, "à étudier")
    if o.nature == "nouvelle":
        return f"Nouvelle aide au catalogue, « {statut} » pour ce projet"
    return f"Dépôt ouvert depuis le {date_fr(o.disponible_depuis)}, « {statut} » pour ce projet"


def _lignes_ouvertures(bloc: BlocProjet) -> list[str]:
    lignes = []
    for o in bloc.ouvertures:
        montant = montant_fr(o.montant_max)
        detail = (
            f"À déposer avant le {date_fr(o.date_limite)}"
            if o.date_limite
            else "Dépôt ouvert, sans date limite annoncée"
        )
        if montant:
            detail += f" · jusqu'à {montant}"
        lignes.append(
            _ligne_aide(
                nom=o.aide_nom,
                url=aide_url(bloc.projet_url, o.aide_id),
                accroche=_accroche_ouverture(o),
                detail=detail,
                accent="#0a369d",
            )
        )
    return lignes


def _titre_ouvertures(ouvertures: list[RappelOuverture]) -> tuple[str, str]:
    """Une aide nouvelle et une aide qui rouvre ne se disent pas pareil : la
    première, l'utilisateur ne l'a jamais vue ; la seconde, il l'a peut-être
    croisée dans « Disponibles bientôt »."""
    total = len(ouvertures)
    nouvelles = sum(1 for o in ouvertures if o.nature == "nouvelle")
    if nouvelles == total:
        if total == 1:
            return (
                "Une nouvelle aide pour vos projets",
                "Elle vient d'entrer au catalogue Monumia, et votre projet y répond d'après ce que vous avez déjà renseigné.",
            )
        return (
            f"{total} nouvelles aides pour vos projets",
            "Elles viennent d'entrer au catalogue Monumia, et vos projets y répondent d'après ce que vous avez déjà renseigné.",
        )
    if nouvelles == 0:
        if total == 1:
            return (
                "Le dépôt vient d'ouvrir pour une aide de vos projets",
                "Elle attendait dans « Disponibles bientôt » : le dossier peut maintenant être déposé.",
            )
        return (
            f"Le dépôt vient d'ouvrir pour {total} aides de vos projets",
            "Elles attendaient dans « Disponibles bientôt » : les dossiers peuvent maintenant être déposés.",
        )
    return (
        f"{total} aides deviennent disponibles pour vos projets",
        "Nouvelles au catalogue ou guichets qui rouvrent : les dossiers peuvent maintenant être déposés.",
    )


def _titre_echeances(total: int) -> tuple[str, str]:
    titre = (
        "Une aide de vos projets approche de sa date limite"
        if total == 1
        else f"{total} aides de vos projets approchent de leur date limite"
    )
    return titre, "Le dépôt reste possible, mais la fenêtre se referme."


def titre_rappels(blocs: list[BlocProjet]) -> tuple[str, str]:
    """(titre, chapeau) de l'email, qui sert aussi d'objet.

    L'email est UNIQUE par compte et par passage : il dit ce qu'il contient,
    échéances, aides devenues disponibles, ou les deux.
    """
    ouvertures = [o for b in blocs for o in b.ouvertures]
    n_e = sum(len(b.echeances) for b in blocs)
    if not ouvertures:
        return _titre_echeances(n_e)
    if not n_e:
        return _titre_ouvertures(ouvertures)
    n_o = len(ouvertures)
    dispo = "Une aide devient disponible" if n_o == 1 else f"{n_o} aides deviennent disponibles"
    echeance = (
        "une aide approche de sa date limite"
        if n_e == 1
        else f"{n_e} aides approchent de leur date limite"
    )
    return "Du nouveau sur les aides de vos projets", f"{dispo}, et {echeance}."


def render_rappels_email(*, prenom: str, blocs: list[BlocProjet], reglages_url: str) -> str:
    """L'email de rappel d'un compte, groupé par chantier.

    Dans chaque chantier, les aides qui deviennent disponibles d'abord (c'est
    la nouvelle), puis les échéances.
    """
    corps: list[str] = []
    for bloc in blocs:
        if not bloc.echeances and not bloc.ouvertures:
            continue
        corps.append(_en_tete_bloc(bloc))
        corps += _lignes_ouvertures(bloc)
        corps += _lignes_echeances(bloc)
    titre, chapeau = titre_rappels(blocs)
    return _enveloppe(
        prenom=prenom,
        titre=titre,
        chapeau=chapeau,
        corps="\n".join(corps),
        reglages_url=reglages_url,
    )


def send_rappel_email(*, to_email: str, subject: str, html: str) -> None:
    """Envoie un email de rappel (cf. `_expedier` pour les replis de dev) : le
    job de rappel doit pouvoir tourner en développement sans compte Resend."""
    sender = os.environ.get("RESEND_FROM_RAPPELS", "").strip() or DEFAULT_FROM_RAPPELS
    _expedier(nature="email de rappel", sender=sender, to=[to_email], subject=subject, html=html)


# ---------------------------------------------------------------------------
# Avis interne : un compte vient d'être créé
# ---------------------------------------------------------------------------

# Expéditeur propre à l'équipe : l'avis se filtre dans la boîte de contact sans
# se mêler aux invitations ni aux rappels envoyés aux utilisateurs.
DEFAULT_FROM_NOTIFS = "Monumia <notifications@monumia.fr>"


@dataclass(frozen=True)
class Inscription:
    """Ce que l'équipe veut savoir d'un compte qui vient d'être créé."""

    email: str
    prenom: str
    nom: str
    telephone: str | None
    # Métier déclaré : renseigné pour un collaborateur invité, absent sinon.
    metier: str | None
    # « mot de passe » ou « Google » : une inscription par mot de passe n'a pas
    # encore confirmé son adresse, il faut le savoir avant d'y répondre.
    connexion: str


def environnement_inscription() -> str | None:
    """Hôte de l'application hors production (« beta.monumia.fr »), sinon None.

    Le même avis part de la bêta si elle est configurée pour : sans ce repère
    dans l'objet, un compte de test passerait pour un vrai client.
    """
    base = os.environ.get("FRONTEND_URL", "").strip().rstrip("/")
    hote = base.split("://", 1)[-1]
    if not hote or hote == "app.monumia.fr":
        return None
    return hote


def sujet_inscription(inscription: Inscription, environnement: str | None) -> str:
    nom = " ".join(p for p in (inscription.prenom, inscription.nom) if p) or inscription.email
    parcours = "Nouveau collaborateur" if inscription.metier else "Nouvelle inscription"
    sujet = f"{parcours} sur Monumia : {nom}"
    return f"[{environnement}] {sujet}" if environnement else sujet


def render_inscription_email(*, inscription: Inscription, admin_url: str) -> str:
    """HTML de l'avis d'inscription. Tout ce qui vient du formulaire est échappé."""
    lignes = [
        ("Nom", " ".join(p for p in (inscription.prenom, inscription.nom) if p) or "—"),
        ("Email", inscription.email),
        ("Téléphone", inscription.telephone or "—"),
        (
            "Parcours",
            f"collaborateur invité ({inscription.metier})"
            if inscription.metier
            else "inscription directe",
        ),
        ("Connexion", inscription.connexion),
    ]
    tableau = "\n".join(
        f"""\
        <tr>
          <td style="padding:6px 16px 6px 0;color:#8a8a8a;white-space:nowrap">{libelle}</td>
          <td style="padding:6px 0;font-weight:600">{escape(valeur)}</td>
        </tr>"""
        for libelle, valeur in lignes
    )
    confirmation = (
        """
      <p style="margin:16px 0 0;font-size:13px;color:#6b6b6b">L'adresse n'est pas encore confirmée : le compte ne s'ouvrira qu'une fois le lien de l'email de confirmation suivi.</p>"""
        if inscription.connexion == "mot de passe"
        else ""
    )
    return f"""\
<div style="background:#fdf9f0;padding:32px 0;font-family:Inter,Arial,sans-serif;color:#222b35">
  <div style="max-width:520px;margin:0 auto;background:#fffefb;border:1px solid #ece3d2;border-radius:12px;overflow:hidden">
    <div style="background:#0a369d;color:#fff;padding:18px 28px;font-size:18px;font-weight:700">Monumia</div>
    <div style="padding:28px">
      <p style="margin:0 0 16px">Un compte vient d'être créé.</p>
      <table style="border-collapse:collapse;font-size:14px">
{tableau}
      </table>{confirmation}
      <p style="margin:24px 0 0;font-size:13px">Répondre à cet email écrit directement à la personne. <a href="{admin_url}" style="color:#0a369d">Voir les comptes</a></p>
    </div>
  </div>
</div>"""


def send_inscription_email(inscription: Inscription) -> None:
    """Prévient l'équipe d'une inscription, à l'adresse `NOTIF_INSCRIPTION_TO`.

    Variable vide ou absente = aucun avis : un poste de développement qui porte
    une vraie clé Resend n'écrit pas à la boîte de contact à chaque compte de
    test. Appelé en tâche de fond après la réponse ; une panne de Resend est
    journalisée et ne remonte jamais, l'inscription a déjà réussi.
    """
    destinataire = os.environ.get("NOTIF_INSCRIPTION_TO", "").strip()
    if not destinataire:
        return

    environnement = environnement_inscription()
    subject = sujet_inscription(inscription, environnement)
    app_url = (os.environ.get("FRONTEND_URL", "").strip() or "https://app.monumia.fr").rstrip("/")
    html = render_inscription_email(inscription=inscription, admin_url=f"{app_url}/admin")
    sender = os.environ.get("RESEND_FROM_NOTIFS", "").strip() or DEFAULT_FROM_NOTIFS
    try:
        _expedier(
            nature="avis d'inscription",
            sender=sender,
            to=[destinataire],
            subject=subject,
            html=html,
            reply_to=inscription.email,
        )
    except Exception:
        logger.exception("Avis d'inscription non envoyé pour %s", inscription.email)
