"""Envoi de l'email d'invitation via Resend, avec repli console en dev.

`render_invitation_email` est pur (testé). `send_invitation_email` lit la
config dans l'environnement ; si `RESEND_API_KEY` est vide, l'email est loggué
dans la console au lieu d'être envoyé (développement sans compte Resend).
"""

import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_FROM = "Monumia <invitations@monumia.fr>"


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
