"""Gmail SMTP email sender (stdlib only — no extra packages required)."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings


def send_email(to_address: str, subject: str, body: str) -> None:
    """Send a plain-text email via Gmail SMTP (STARTTLS, port 587)."""
    if not settings.gmail_user or not settings.gmail_app_password:
        raise RuntimeError(
            "GMAIL_USER and GMAIL_APP_PASSWORD must be set in .env. "
            "Generate an App Password at myaccount.google.com/apppasswords."
        )

    msg = MIMEMultipart()
    msg["From"] = settings.gmail_user
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.login(settings.gmail_user, settings.gmail_app_password)
        server.send_message(msg)
