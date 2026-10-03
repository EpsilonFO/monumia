"""Emails sortants via Resend, avec repli console en dev.

Deux familles : l'invitation d'un collaborateur, et les rappels calendaires sur
les aides (échéance qui approche, aide qui devient disponible).

Les fonctions `render_*` sont pures (testées). Les `send_*` lisent la config
dans l'environnement ; si `RESEND_API_KEY` est vide, l'email est loggué dans la
console au lieu d'être envoyé (développement sans compte Resend).
"""

import logging
import os
from dataclasses import dataclass
from datetime import date
from html import escape

from services.rappels_service import LIBELLE_STATUT, RappelEcheance, RappelOuverture

logger = logging.getLogger(__name__)

DEFAULT_FROM = "Monumia <invitations@monumia.fr>"

# Expéditeur distinct des invitations : un rappel automatique et une invitation
# nominative ne se filtrent ni ne se désabonnent de la même façon.
DEFAULT_FROM_RAPPELS = "Monumia <rappels@monumia.fr>"


def render_invitation_email(
    *,
    inviter_nom: str,
    monument_nom: str,
    invite_url: str,
    expires_label: str,
    projet_titre: str | None = None,
) -> str:
    """HTML de l'email d'invitation, dans la charte Monumia.

    `projet_titre` renseigné = invitation sur UN chantier précis. Le dire est
    nécessaire : le destinataire n'aura accès qu'à celui-là, et découvrir après
    coup qu'on ne voit pas le reste du monument passerait pour une panne.
    """
    portee = (
        f"""
      <p style="margin:0 0 8px">Sur le projet de travaux :</p>
      <div style="background:#fff3e6;border-radius:8px;padding:12px 18px;margin:8px 0 16px;font-size:15px;font-weight:600;color:#a34a00">
        {projet_titre}
      </div>
      <p style="margin:0 0 24px">Vous aurez accès à ce projet — ses aides, ses dossiers, ses documents — et à la fiche du monument en lecture.</p>"""
        if projet_titre
        else """
      <p style="margin:0 0 24px">Vous pourrez consulter le monument et ses projets de travaux, et y déposer vos documents.</p>"""
    )
    return f"""\
<div style="background:#fdf9f0;padding:32px 0;font-family:Inter,Arial,sans-serif;color:#222b35">
  <div style="max-width:520px;margin:0 auto;background:#fffefb;border:1px solid #ece3d2;border-radius:12px;overflow:hidden">
    <div style="background:#0a369d;color:#fff;padding:18px 28px;font-size:18px;font-weight:700">Monumia</div>
    <div style="padding:28px">
      <p style="margin:0 0 16px">Bonjour,</p>
      <p style="margin:0 0 8px"><strong>{inviter_nom}</strong> vous invite à collaborer sur le monument :</p>
      <div style="background:#eef3ff;border-radius:8px;padding:14px 18px;margin:12px 0;font-size:17px;font-weight:600;color:#072a72">
        «&nbsp;{monument_nom}&nbsp;»
      </div>
{portee}
      <a href="{invite_url}" style="display:inline-block;background:#f17105;color:#fff;text-decoration:none;font-weight:600;padding:12px 24px;border-radius:8px">Rejoindre →</a>
      <p style="margin:24px 0 0;font-size:12px;color:#8a8a8a">Ce lien expire le {expires_label}. Si vous ne connaissez pas {inviter_nom}, ignorez simplement cet email.</p>
    </div>
  </div>
</div>"""


def send_invitation_email(
    *,
    to_email: str,
    inviter_nom: str,
    monument_nom: str,
    invite_url: str,
    expires_label: str,
    projet_titre: str | None = None,
) -> None:
    """Envoie l'email d'invitation, ou le logge si Resend n'est pas configuré."""
    html = render_invitation_email(
        inviter_nom=inviter_nom,
        monument_nom=monument_nom,
        invite_url=invite_url,
        expires_label=expires_label,
        projet_titre=projet_titre,
    )
    subject = (
        f"{inviter_nom} vous invite sur un projet de « {monument_nom} »"
        if projet_titre
        else f"{inviter_nom} vous invite sur le monument « {monument_nom} »"
    )
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    sender = os.environ.get("RESEND_FROM", DEFAULT_FROM)

    if not api_key:
        logger.warning(
            "[DEV] Resend non configuré — email d'invitation non envoyé.\n"
            "  À: %s\n  Sujet: %s\n  Lien: %s",
            to_email,
            subject,
            invite_url,
        )
        return

    import resend

    resend.api_key = api_key
    resend.Emails.send({"from": sender, "to": [to_email], "subject": subject, "html": html})


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


def render_echeances_email(*, prenom: str, blocs: list[BlocProjet], reglages_url: str) -> str:
    """Email « des aides arrivent à échéance », groupé par chantier."""
    corps: list[str] = []
    total = 0
    for bloc in blocs:
        if not bloc.echeances:
            continue
        corps.append(_en_tete_bloc(bloc))
        for e in bloc.echeances:
            total += 1
            montant = montant_fr(e.montant_max)
            detail = f"Date limite : {date_fr(e.date_limite)}"
            if montant:
                detail += f" · jusqu'à {montant}"
            corps.append(
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
    titre = (
        "Une aide de vos projets approche de sa date limite"
        if total == 1
        else f"{total} aides de vos projets approchent de leur date limite"
    )
    return _enveloppe(
        prenom=prenom,
        titre=titre,
        chapeau="Le dépôt reste possible, mais la fenêtre se referme.",
        corps="\n".join(corps),
        reglages_url=reglages_url,
    )


def _accroche_ouverture(o: RappelOuverture) -> str:
    statut = LIBELLE_STATUT.get(o.statut, "à étudier")
    if o.nature == "nouvelle":
        return f"Nouvelle aide au catalogue, « {statut} » pour ce projet"
    return f"Dépôt ouvert depuis le {date_fr(o.disponible_depuis)}, « {statut} » pour ce projet"


def titre_ouvertures(ouvertures: list[RappelOuverture]) -> tuple[str, str]:
    """(titre, chapeau) de l'email, selon ce qu'il annonce.

    Une aide nouvelle et une aide qui rouvre ne se disent pas pareil : la
    première, l'utilisateur ne l'a jamais vue ; la seconde, il l'a peut-être
    croisée dans « Disponibles bientôt ». Exposé pour servir aussi d'objet.
    """
    total = len(ouvertures)
    nouvelles = sum(1 for o in ouvertures if o.nature == "nouvelle")
    if nouvelles == total:
        titre = (
            "Une nouvelle aide pour vos projets"
            if total == 1
            else f"{total} nouvelles aides pour vos projets"
        )
        chapeau = (
            "Elle vient d'entrer au catalogue Monumia, et votre projet y répond d'après ce que vous avez déjà renseigné."
            if total == 1
            else "Elles viennent d'entrer au catalogue Monumia, et vos projets y répondent d'après ce que vous avez déjà renseigné."
        )
    elif nouvelles == 0:
        titre = (
            "Le dépôt vient d'ouvrir pour une aide de vos projets"
            if total == 1
            else f"Le dépôt vient d'ouvrir pour {total} aides de vos projets"
        )
        chapeau = (
            "Elle attendait dans « Disponibles bientôt » : le dossier peut maintenant être déposé."
            if total == 1
            else "Elles attendaient dans « Disponibles bientôt » : les dossiers peuvent maintenant être déposés."
        )
    else:
        titre = f"{total} aides deviennent disponibles pour vos projets"
        chapeau = "Nouvelles au catalogue ou guichets qui rouvrent : les dossiers peuvent maintenant être déposés."
    return titre, chapeau


def render_ouvertures_email(*, prenom: str, blocs: list[BlocProjet], reglages_url: str) -> str:
    """Email « une aide devient disponible » (nouvelle ou réouverture), par chantier."""
    corps: list[str] = []
    toutes: list[RappelOuverture] = []
    for bloc in blocs:
        if not bloc.ouvertures:
            continue
        corps.append(_en_tete_bloc(bloc))
        for o in bloc.ouvertures:
            toutes.append(o)
            montant = montant_fr(o.montant_max)
            detail = (
                f"À déposer avant le {date_fr(o.date_limite)}"
                if o.date_limite
                else "Dépôt ouvert, sans date limite annoncée"
            )
            if montant:
                detail += f" · jusqu'à {montant}"
            corps.append(
                _ligne_aide(
                    nom=o.aide_nom,
                    url=aide_url(bloc.projet_url, o.aide_id),
                    accroche=_accroche_ouverture(o),
                    detail=detail,
                    accent="#0a369d",
                )
            )
    titre, chapeau = titre_ouvertures(toutes)
    return _enveloppe(
        prenom=prenom,
        titre=titre,
        chapeau=chapeau,
        corps="\n".join(corps),
        reglages_url=reglages_url,
    )


def send_rappel_email(*, to_email: str, subject: str, html: str) -> None:
    """Envoie un email de rappel, ou le logge si Resend n'est pas configuré.

    Même repli console que `send_invitation_email` : le job de rappel doit
    pouvoir tourner en développement sans compte Resend.
    """
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    sender = os.environ.get("RESEND_FROM_RAPPELS", "").strip() or DEFAULT_FROM_RAPPELS

    if not api_key:
        logger.warning(
            "[DEV] Resend non configuré — email de rappel non envoyé.\n  À: %s\n  Sujet: %s",
            to_email,
            subject,
        )
        return

    import resend

    resend.api_key = api_key
    resend.Emails.send({"from": sender, "to": [to_email], "subject": subject, "html": html})
