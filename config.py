import hashlib
import os
import secrets
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
from security import sanitize_header_value

# Load environment variables from .env
load_dotenv()


def _resolve_secret_key() -> str:
    """
    Récupère SECRET_KEY depuis l'environnement.
    Si absente en production Serverless (Vercel), dérive une clé stable à partir
    de variables d'environnement secrètes plutôt que de coder un secret en dur dans Git.
    """
    env_key = os.environ.get('SECRET_KEY', '').strip()
    if env_key:
        return env_key

    seed_parts = [
        os.environ.get('VERCEL_PROJECT_ID', ''),
        os.environ.get('SMTP_PASSWORD', ''),
        os.environ.get('SMTP_USER', ''),
    ]
    if any(seed_parts):
        seed = '|'.join(seed_parts) + '|elide-ong-session-key'
        return hashlib.sha256(seed.encode('utf-8')).hexdigest()

    return secrets.token_hex(32)


class Config:
    IS_PRODUCTION = bool(os.environ.get('VERCEL') or os.environ.get('VERCEL_ENV'))

    # Clé secrète Flask (jamais codée en dur dans le dépôt)
    SECRET_KEY = _resolve_secret_key()

    # Sécurisation des cookies de session et limite de taille des requêtes (1 Mo)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = IS_PRODUCTION
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024
    TEMPLATES_AUTO_RELOAD = not IS_PRODUCTION

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

    # Configuration FedaPay (dons en ligne : MTN MoMo, Moov Money, Celtiis, Visa/Mastercard)
    FEDAPAY_ENV = os.environ.get('FEDAPAY_ENV', 'sandbox').strip().lower()
    FEDAPAY_SECRET_KEY = os.environ.get('FEDAPAY_SECRET_KEY', '').strip()
    FEDAPAY_WEBHOOK_SECRET = os.environ.get('FEDAPAY_WEBHOOK_SECRET', '').strip()


def get_fedapay_secret_key() -> str:
    """Récupère dynamiquement la clé secrète FedaPay depuis l'environnement."""
    for var_name in ('FEDAPAY_SECRET_KEY', 'FEDAPAY_API_KEY', 'FEDAPAY_SECRET'):
        val = (os.environ.get(var_name) or '').strip()
        if val:
            return val
    return (Config.FEDAPAY_SECRET_KEY or '').strip()


def get_fedapay_env() -> str:
    """Détermine l'environnement FedaPay (live ou sandbox) avec détection automatique depuis la clé."""
    key = get_fedapay_secret_key()
    if key.startswith('sk_live_'):
        return 'live'
    if key.startswith('sk_sandbox_'):
        return 'sandbox'
    env = (os.environ.get('FEDAPAY_ENV') or Config.FEDAPAY_ENV or 'sandbox').strip().lower()
    return 'live' if env == 'live' else 'sandbox'


def is_fedapay_configured() -> bool:
    """Indique si la clé secrète FedaPay est renseignée."""
    return bool(get_fedapay_secret_key())


def get_fedapay_base_url() -> str:
    """Retourne l'URL de base de l'API FedaPay selon l'environnement (live ou sandbox)."""
    if get_fedapay_env() == 'live':
        return 'https://api.fedapay.com/v1'
    return 'https://sandbox-api.fedapay.com/v1'


def is_smtp_configured() -> bool:
    """Indique si les identifiants SMTP sont renseignés."""
    return bool(Config.SMTP_USER and Config.SMTP_PASSWORD)


def send_email_notification(subject: str, body: str, to_email: str, reply_to: str = None) -> bool:
    """Envoie un e-mail via SMTP TLS si les identifiants SMTP sont configurés."""
    smtp_user = Config.SMTP_USER
    smtp_password = Config.SMTP_PASSWORD
    if not smtp_user or not smtp_password:
        print(f"[EMAIL - SMTP NON CONFIGURÉ] Sujet: {sanitize_header_value(subject)}")
        return False

    try:
        clean_subject = sanitize_header_value(subject)
        clean_to = sanitize_header_value(to_email)
        clean_reply_to = sanitize_header_value(reply_to) if reply_to else None

        msg = EmailMessage()
        msg['Subject'] = clean_subject
        msg['From'] = smtp_user
        msg['To'] = clean_to
        if clean_reply_to:
            msg['Reply-To'] = clean_reply_to
        msg.set_content(body)

        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        print(f"[EMAIL ENVOYÉ] Sujet: {clean_subject} -> {clean_to}")
        return True
    except Exception as e:
        print(f"[ERREUR SMTP] Impossible d'envoyer l'e-mail : {e}")
        return False
