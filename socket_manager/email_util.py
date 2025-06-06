import os
import smtplib
from email.message import EmailMessage

def send_health_email(subject: str, body: str) -> None:
    """
    Sends an email with the given subject and body to the SMTP_TO address,
    using SMTP credentials from environment variables.
    """
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM")
    smtp_to = os.getenv("SMTP_TO")

    if not all([smtp_host, smtp_port, smtp_user, smtp_pass, smtp_from, smtp_to]):
        raise RuntimeError("SMTP configuration is incomplete in environment variables.")

    # Build the email message
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = smtp_to
    msg.set_content(body)

    # Connect and send (using STARTTLS)
    with smtplib.SMTP(smtp_host, smtp_port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(smtp_user, smtp_pass)
        smtp.send_message(msg)

send_health_email("test","test")