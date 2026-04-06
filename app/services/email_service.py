"""Async email service for member notifications and account emails."""

import logging
from email.message import EmailMessage

import aiosmtplib

from app.config import settings

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, html_body: str) -> None:
    """Send a HTML email via SMTP, or skip when SMTP is not configured."""
    if not settings.SMTP_HOST:
        logger.warning(
            "SMTP_HOST n'est pas configuré, envoi d'email ignoré pour %s (%s)",
            to,
            subject,
        )
        return

    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content("Votre client email ne supporte pas le HTML.")
    message.add_alternative(html_body, subtype="html")

    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER or None,
        password=settings.SMTP_PASSWORD or None,
        start_tls=settings.SMTP_TLS,
    )


async def send_activation_email(
    to: str, first_name: str, token: str, base_url: str
) -> None:
    """Send the account activation email."""
    activation_link = f"{base_url.rstrip('/')}/activate?token={token}"
    html_body = f"""
    <html>
      <body style=\"font-family: Arial, sans-serif; color: #1f2937; line-height: 1.6;\">
        <p>Bonjour {first_name},</p>
        <p>
          Votre compte sur le portail membres de la LIMA a été créé.
          Pour activer votre accès et définir votre mot de passe,
          cliquez sur le bouton ci-dessous.
        </p>
        <p style=\"margin: 24px 0;\">
          <a
            href=\"{activation_link}\"
            style=\"background: #7c3aed; color: white; text-decoration: none; padding: 12px 18px; border-radius: 8px; display: inline-block;\"
          >
            Activer mon compte
          </a>
        </p>
        <p>
          Si le bouton ne fonctionne pas, copiez-collez ce lien dans votre navigateur :<br>
          <a href=\"{activation_link}\">{activation_link}</a>
        </p>
        <p>À bientôt sur le portail membres LIMA.</p>
      </body>
    </html>
    """
    await send_email(to, "LIMA — Activez votre compte", html_body)


async def send_password_reset_email(
    to: str, first_name: str, token: str, base_url: str
) -> None:
    """Send the password reset email."""
    reset_link = f"{base_url.rstrip('/')}/reset-password?token={token}"
    html_body = f"""
    <html>
      <body style=\"font-family: Arial, sans-serif; color: #1f2937; line-height: 1.6;\">
        <p>Bonjour {first_name},</p>
        <p>
          Nous avons reçu une demande de réinitialisation de mot de passe
          pour votre accès au portail membres de la LIMA.
        </p>
        <p style=\"margin: 24px 0;\">
          <a
            href=\"{reset_link}\"
            style=\"background: #7c3aed; color: white; text-decoration: none; padding: 12px 18px; border-radius: 8px; display: inline-block;\"
          >
            Réinitialiser mon mot de passe
          </a>
        </p>
        <p>
          Si vous n'êtes pas à l'origine de cette demande, vous pouvez simplement ignorer cet email.
        </p>
        <p>
          Si le bouton ne fonctionne pas, copiez-collez ce lien dans votre navigateur :<br>
          <a href=\"{reset_link}\">{reset_link}</a>
        </p>
      </body>
    </html>
    """
    await send_email(to, "LIMA — Réinitialisation de mot de passe", html_body)


async def send_cast_assignment_email(
    to: str,
    first_name: str,
    event_title: str,
    event_date: str,
    role: str,
    alignment_name: str,
    base_url: str,
) -> None:
    """Send a cast assignment notification email."""
    planning_link = f"{base_url.rstrip('/')}/mon-planning"
    subject = f"LIMA — Tu es affecté(e) à {event_title}"
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #1f2937; line-height: 1.6;">
        <p>Bonjour {first_name},</p>
        <p>
          Tu as été affecté(e) au rôle <strong>{role}</strong>
          pour l'événement <strong>{event_title}</strong>.
        </p>
        <p>
          <strong>Date :</strong> {event_date}<br>
          <strong>Grille :</strong> {alignment_name}
        </p>
        <p style="margin: 24px 0;">
          <a
            href="{planning_link}"
            style="background: #7c3aed; color: white; text-decoration: none; padding: 12px 18px; border-radius: 8px; display: inline-block;"
          >
            Voir mon planning
          </a>
        </p>
        <p>
          Si le bouton ne fonctionne pas, copiez-collez ce lien dans votre navigateur :<br>
          <a href="{planning_link}">{planning_link}</a>
        </p>
      </body>
    </html>
    """
    await send_email(to, subject, html_body)


async def send_cast_unassignment_email(
    to: str,
    first_name: str,
    event_title: str,
    event_date: str,
    role: str,
    alignment_name: str,
    base_url: str,
) -> None:
    """Send a cast unassignment notification email."""
    planning_link = f"{base_url.rstrip('/')}/mon-planning"
    subject = f"LIMA — Mise à jour de ton affectation pour {event_title}"
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #1f2937; line-height: 1.6;">
        <p>Bonjour {first_name},</p>
        <p>
          Tu n'es plus affecté(e) au rôle <strong>{role}</strong>
          pour l'événement <strong>{event_title}</strong>.
        </p>
        <p>
          <strong>Date :</strong> {event_date}<br>
          <strong>Grille :</strong> {alignment_name}
        </p>
        <p>
          Tu peux consulter ton planning mis à jour ici :
          <a href="{planning_link}">{planning_link}</a>
        </p>
      </body>
    </html>
    """
    await send_email(to, subject, html_body)


async def send_event_reminder_email(
    to: str,
    first_name: str,
    event_title: str,
    event_date: str,
    role: str,
    venue_name: str | None,
    base_url: str,
) -> None:
    """Send a 24h reminder email for an upcoming assigned event."""
    planning_link = f"{base_url.rstrip('/')}/mon-planning"
    subject = f"LIMA — Rappel : {event_title} demain"
    venue_block = (
        f"<strong>Lieu :</strong> {venue_name}<br>" if venue_name else ""
    )
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #1f2937; line-height: 1.6;">
        <p>Bonjour {first_name},</p>
        <p>
          Petit rappel : tu es attendu(e) demain pour l'événement
          <strong>{event_title}</strong>.
        </p>
        <p>
          <strong>Date :</strong> {event_date}<br>
          <strong>Rôle :</strong> {role}<br>
          {venue_block}
        </p>
        <p style="margin: 24px 0;">
          <a
            href="{planning_link}"
            style="background: #7c3aed; color: white; text-decoration: none; padding: 12px 18px; border-radius: 8px; display: inline-block;"
          >
            Voir mon planning
          </a>
        </p>
        <p>
          Si le bouton ne fonctionne pas, copiez-collez ce lien dans votre navigateur :<br>
          <a href="{planning_link}">{planning_link}</a>
        </p>
        <p>À très vite sur scène 🎭</p>
      </body>
    </html>
    """
    await send_email(to, subject, html_body)
