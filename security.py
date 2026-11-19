import hmac
import hashlib
import re
import secrets
import time
from collections import defaultdict, deque

EMAIL_REGEX = re.compile(r'^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,24}$')

# Limitation de débit en mémoire (fenêtre glissante par IP et par route)
_RATE_BUCKETS = defaultdict(deque)
_MAX_TRACKED_KEYS = 2000


def sanitize_header_value(value: str) -> str:
    """Supprime les sauts de ligne (\r, \n) pour empêcher l'injection d'en-têtes SMTP."""
    if not value:
        return ''
    return value.replace('\r', ' ').replace('\n', ' ').strip()


def is_valid_email(email: str) -> bool:
    """Valide strictement une adresse e-mail (format, longueur, absence de CR/LF)."""
    if not email or len(email) > 254:
        return False
    if '\r' in email or '\n' in email:
        return False
    return bool(EMAIL_REGEX.match(email))


def get_client_ip(req) -> str:
    """Extrait l'adresse IP du client (compatible proxy Vercel X-Forwarded-For)."""
    forwarded = (req.headers.get('X-Forwarded-For') or '').strip()
    if forwarded:
        return forwarded.split(',')[0].strip()
    return (req.remote_addr or 'unknown').strip()


def check_rate_limit(scope: str, ip: str, limit: int = 5, window_seconds: int = 600) -> bool:
    """
    Vérifie si l'IP est autorisée à effectuer une requête pour le scope donné.
    Retourne True si autorisée, False si la limite est dépassée.
    """
    now = time.time()
    key = f"{scope}:{ip}"

    # Nettoyage préventif si trop de clés en mémoire
    if len(_RATE_BUCKETS) > _MAX_TRACKED_KEYS:
        stale_keys = [
            k for k, dq in list(_RATE_BUCKETS.items())
            if not dq or (now - dq[-1]) > window_seconds
        ]
        for k in stale_keys:
            _RATE_BUCKETS.pop(k, None)

    bucket = _RATE_BUCKETS[key]
    cutoff = now - window_seconds
    while bucket and bucket[0] < cutoff:
        bucket.popleft()

    if len(bucket) >= limit:
        return False

    bucket.append(now)
    return True


def generate_form_token(secret_key: str) -> str:
    """Génère un jeton horodaté signé HMAC-SHA256 (sans dépendre d'une session serveur)."""
    ts = str(int(time.time()))
    nonce = secrets.token_hex(8)
    payload = f"{ts}.{nonce}"
    sig = hmac.new(
        secret_key.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()[:32]
    return f"{payload}.{sig}"


def verify_form_token(secret_key: str, token: str, min_age: float = 2.0, max_age: float = 7200.0) -> bool:
    """Vérifie la signature HMAC et le délai humain d'un jeton de formulaire."""
    if not token or not isinstance(token, str):
        return False

    parts = token.split('.')
    if len(parts) != 3:
        return False

    ts_str, nonce, provided_sig = parts
    if not ts_str.isdigit() or len(nonce) != 16:
        return False

    payload = f"{ts_str}.{nonce}"
    expected_sig = hmac.new(
        secret_key.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()[:32]

    if not hmac.compare_digest(provided_sig, expected_sig):
        return False

    elapsed = time.time() - int(ts_str)
    if elapsed < min_age or elapsed > max_age:
        return False

    return True
