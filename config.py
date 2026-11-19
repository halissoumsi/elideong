import os
import secrets
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

class Config:
    # Clé secrète Flask stable entre les invocations Serverless (Vercel)
    SECRET_KEY = os.environ.get('SECRET_KEY', '8f4c9a2e7b1d6f3a5e0c8b4d2f9a1e7c3b5d8f0a2e4c6b8d1f3a5e7c9b2d4f6a')
    
    # Sécurisation des cookies de session et rechargement automatique des templates
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    TEMPLATES_AUTO_RELOAD = True
    
    # Email et WhatsApp de réception (ONG ELiDe)
    PARTNER_NOTIFY_EMAIL = os.environ.get('PARTNER_NOTIFY_EMAIL', 'ongelide@gmail.com')
    _raw_wa = os.environ.get('WHATSAPP_NUMBER', '22967576050').strip().replace(' ', '').lstrip('+')
    if _raw_wa.startswith('00'):
        _raw_wa = _raw_wa[2:]
    WHATSAPP_NUMBER = _raw_wa
    
    # Configuration SMTP (pour l'envoi réel d'e-mails)
    SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USER = os.environ.get('SMTP_USER', '')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')


def send_email_notification(subject: str, body: str, to_email: str, reply_to: str = None) -> bool:
    """Envoie un e-mail via SMTP si les identifiants SMTP sont configurés."""
    smtp_user = Config.SMTP_USER
    smtp_password = Config.SMTP_PASSWORD
    if not smtp_user or not smtp_password:
        print(f"[EMAIL - SMTP NON CONFIGURÉ] Sujet: {subject} | Destinataire: {to_email}")
        return False

    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = to_email
        if reply_to:
            msg['Reply-To'] = reply_to
        msg.set_content(body)

        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        print(f"[EMAIL ENVOYÉ] Sujet: {subject} -> {to_email}")
        return True
    except Exception as e:
        print(f"[ERREUR SMTP] Impossible d'envoyer l'e-mail ({subject}) : {e}")
        return False
