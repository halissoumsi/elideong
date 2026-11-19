import hashlib
import hmac
import json
import re
import urllib.error
import urllib.request
from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from config import (
    Config,
    get_fedapay_base_url,
    get_fedapay_env,
    get_fedapay_secret_key,
    is_fedapay_configured,
    send_email_notification,
)
from i18n import get_current_lang, get_translations
from security import (
    check_rate_limit,
    generate_form_token,
    get_client_ip,
    is_valid_email,
    verify_form_token,
)

don_bp = Blueprint('don', __name__)

CAUSE_KEYS = {
    'general': 'donate_cause_general',
    'education': 'donate_cause_education',
    'environment': 'donate_cause_environment',
    'digital': 'donate_cause_digital',
    'agriculture': 'donate_cause_agriculture',
    'entrepreneurship': 'donate_cause_entrepreneurship',
}


def _extract_tx(payload: dict) -> dict:
    """Extrait l'objet transaction quelle que soit l'enveloppe JSON renvoyée par FedaPay."""
    if not isinstance(payload, dict):
        return {}
    return payload.get('v1/transaction') or payload.get('transaction') or payload


def _fedapay_request(method: str, endpoint: str, payload: dict = None) -> dict:
    """Exécute un appel HTTPS authentifié vers l'API REST FedaPay v1."""
    api_key = get_fedapay_secret_key()
    if not api_key:
        raise RuntimeError('FEDAPAY_SECRET_KEY non configurée')

    base_url = get_fedapay_base_url()
    url = f"{base_url}/{endpoint.lstrip('/')}"
    body = json.dumps(payload).encode('utf-8') if payload is not None else None

    req = urllib.request.Request(
        url,
        data=body,
        method=method.upper(),
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'ONG-ELiDe-Web/1.0',
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode('utf-8')
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='replace')
        print(f"[FEDAPAY HTTP {e.code}] {endpoint}: {err_body[:400]}")
        raise RuntimeError(f"FedaPay HTTP {e.code}") from e
    except Exception as e:
        print(f"[FEDAPAY ERROR] {endpoint}: {e}")
        raise


def create_fedapay_checkout(
    amount: int,
    description: str,
    callback_url: str,
    firstname: str,
    lastname: str,
    email: str,
    phone: str = '',
    metadata: dict = None,
) -> dict:
    """Crée une transaction FedaPay et génère son lien de paiement hébergé sécurisé."""
    customer = {
        'firstname': firstname,
        'lastname': lastname,
        'email': email,
    }
    clean_phone = re.sub(r'[^\d+]', '', phone or '')
    if len(clean_phone) >= 8:
        customer['phone_number'] = {
            'number': clean_phone,
            'country': 'bj',
        }

    tx_payload = {
        'description': description[:255],
        'amount': int(amount),
        'currency': {'iso': 'XOF'},
        'callback_url': callback_url,
        'customer': customer,
    }
    if metadata:
        tx_payload['custom_metadata'] = metadata

    created_raw = _fedapay_request('POST', '/transactions', tx_payload)
    tx = _extract_tx(created_raw)
    tx_id = tx.get('id')
    if not tx_id:
        raise RuntimeError('ID de transaction FedaPay manquant')

    token_raw = _fedapay_request('POST', f'/transactions/{tx_id}/token', {})
    checkout_url = (token_raw.get('url') or '').strip()
    if not checkout_url.startswith('https://'):
        raise RuntimeError('URL de paiement FedaPay invalide')

    return {
        'id': str(tx_id),
        'reference': tx.get('reference') or str(tx_id),
        'url': checkout_url,
    }


def fetch_fedapay_transaction(tx_id: str) -> dict:
    """Récupère et vérifie côté serveur l'état réel d'une transaction FedaPay."""
    raw = _fedapay_request('GET', f'/transactions/{tx_id}')
    return _extract_tx(raw)


def _format_xof(amount) -> str:
    try:
        return f"{int(amount):,}".replace(',', ' ') + ' FCFA'
    except (TypeError, ValueError):
        return f"{amount} FCFA"


@don_bp.route('/soutenir', methods=['GET'])
def donate_page():
    """Affiche la page bilingue de don sécurisé via FedaPay."""
    donation_token = generate_form_token(current_app.config['SECRET_KEY'])
    return render_template(
        'soutenir.html',
        donation_token=donation_token,
        fedapay_ready=is_fedapay_configured(),
        fedapay_is_sandbox=(get_fedapay_env() != 'live'),
    )


@don_bp.route('/soutenir', methods=['POST'])
def donate_submit():
    """Valide le don, initialise la transaction FedaPay côté serveur et redirige vers le paiement."""
    lang = get_current_lang()
    t = get_translations(lang)

    if not is_fedapay_configured():
        flash(t['donate_not_configured'], 'error')
        return redirect(url_for('don.donate_page'))

    # 1. Limitation de débit
    client_ip = get_client_ip(request)
    if not check_rate_limit('don', client_ip, limit=10, window_seconds=600):
        flash(t['donate_err_rate'], 'error')
        return redirect(url_for('don.donate_page'))

    # 2. Protection anti-spam invisible (honeypot + jeton HMAC)
    honeypot = (request.form.get('website_url') or '').strip()
    donation_token = (request.form.get('donation_token') or '').strip()
    if honeypot or not verify_form_token(current_app.config['SECRET_KEY'], donation_token, min_age=1.5):
        flash(t['donate_err_spam'], 'error')
        return redirect(url_for('don.donate_page'))

    # 3. Validation stricte des champs
    raw_amount = re.sub(r'[^\d]', '', (request.form.get('amount') or '').strip())
    try:
        amount = int(raw_amount)
    except ValueError:
        amount = 0

    if amount < 500 or amount > 50_000_000:
        flash(t['donate_err_amount'], 'error')
        return redirect(url_for('don.donate_page'))

    cause_key = (request.form.get('cause') or 'general').strip().lower()
    if cause_key not in CAUSE_KEYS:
        cause_key = 'general'
    cause_label = t[CAUSE_KEYS[cause_key]]

    firstname = (request.form.get('firstname') or '').strip()[:80]
    lastname = (request.form.get('lastname') or '').strip()[:80]
    email = (request.form.get('email') or '').strip()[:254]
    phone = (request.form.get('phone') or '').strip()[:30]
    note = (request.form.get('note') or '').strip()[:500]

    if not all([firstname, lastname, email]) or not is_valid_email(email):
        flash(t['donate_err_fields'], 'error')
        return redirect(url_for('don.donate_page'))

    callback_url = url_for('don.donate_return', _external=True)
    description = f"Don ONG ELiDe — {cause_label}"

    try:
        checkout = create_fedapay_checkout(
            amount=amount,
            description=description,
            callback_url=callback_url,
            firstname=firstname,
            lastname=lastname,
            email=email,
            phone=phone,
            metadata={
                'cause': cause_label,
                'cause_key': cause_key,
                'donor_name': f"{firstname} {lastname}",
                'donor_email': email,
                'note': note,
                'lang': lang,
            },
        )
    except Exception:
        flash(t['donate_err_gateway'], 'error')
        return redirect(url_for('don.donate_page'))

    session['pending_donation'] = {
        'tx_id': checkout['id'],
        'reference': checkout['reference'],
        'amount': amount,
        'cause_label': cause_label,
        'firstname': firstname,
        'lastname': lastname,
        'email': email,
        'phone': phone,
        'note': note,
        'lang': lang,
    }
    return redirect(checkout['url'])


@don_bp.route('/soutenir/retour', methods=['GET'])
def donate_return():
    """Vérifie officiellement la transaction auprès de FedaPay et affiche le statut vérifié."""
    lang = get_current_lang()
    t = get_translations(lang)

    tx_id = (request.args.get('id') or '').strip()
    pending = session.get('pending_donation') or {}

    if not tx_id.isdigit() or not is_fedapay_configured():
        return render_template(
            'soutenir_retour.html',
            tx_status='failed',
            tx_reference=tx_id or '—',
            tx_amount_display='—',
            tx_cause=pending.get('cause_label') or t['donate_cause_general'],
        )

    try:
        tx = fetch_fedapay_transaction(tx_id)
    except Exception:
        return render_template(
            'soutenir_retour.html',
            tx_status='pending',
            tx_reference=pending.get('reference') or tx_id,
            tx_amount_display=_format_xof(pending.get('amount')) if pending.get('amount') else '—',
            tx_cause=pending.get('cause_label') or t['donate_cause_general'],
        )

    raw_status = (tx.get('status') or '').strip().lower()
    amount = tx.get('amount') or pending.get('amount') or 0
    reference = tx.get('reference') or pending.get('reference') or tx_id
    meta = tx.get('custom_metadata') if isinstance(tx.get('custom_metadata'), dict) else {}
    cause_label = meta.get('cause') or pending.get('cause_label') or t['donate_cause_general']
    donor_email = meta.get('donor_email') or pending.get('email') or ''
    donor_name = meta.get('donor_name') or f"{pending.get('firstname', '')} {pending.get('lastname', '')}".strip()
    donor_note = meta.get('note') or pending.get('note') or ''
    payment_mode = tx.get('mode') or 'FedaPay'

    if raw_status == 'approved':
        view_status = 'approved'
        notified = session.get('notified_txs') or []
        if tx_id not in notified:
            notify_email = current_app.config.get('PARTNER_NOTIFY_EMAIL', 'ongelide@gmail.com')
            ngo_body = (
                f"Nouveau don validé sur FedaPay pour l'ONG ELiDe :\n\n"
                f"- Référence FedaPay : {reference} (ID #{tx_id})\n"
                f"- Montant : {_format_xof(amount)}\n"
                f"- Mode de paiement : {payment_mode}\n"
                f"- Initiative soutenue : {cause_label}\n"
                f"- Donateur : {donor_name or 'Non renseigné'}\n"
                f"- Email : {donor_email or 'Non renseigné'}\n"
                f"- Mot d'encouragement : {donor_note or 'Aucun'}\n"
            )
            send_email_notification(
                subject=f"[Don FedaPay ELiDe] {_format_xof(amount)} — {donor_name or reference}",
                body=ngo_body,
                to_email=notify_email,
                reply_to=donor_email if is_valid_email(donor_email) else None,
            )

            if is_valid_email(donor_email):
                if lang == 'en':
                    ack_body = (
                        f"Dear {donor_name or 'Supporter'},\n\n"
                        f"Thank you sincerely for your generous donation of {_format_xof(amount)} "
                        f"in support of '{cause_label}' with Les Élites de Demain NGO (ELiDe).\n"
                        f"FedaPay Transaction Reference: {reference}\n\n"
                        f"Your contribution directly empowers youth and communities across Benin.\n\n"
                        f"Warm regards,\nThe Les Élites de Demain NGO (ELiDe) Team"
                    )
                else:
                    ack_body = (
                        f"Bonjour {donor_name or 'cher donateur'},\n\n"
                        f"Nous vous remercions chaleureusement pour votre don de {_format_xof(amount)} "
                        f"en soutien à l'initiative « {cause_label} » de l'ONG Les Élites de Demain (ELiDe).\n"
                        f"Référence FedaPay : {reference}\n\n"
                        f"Votre générosité contribue concrètement à l'impact de nos actions au Bénin.\n\n"
                        f"Cordialement,\nLe Bureau National de l'ONG Les Élites de Demain (ELiDe)"
                    )
                send_email_notification(
                    subject=t['donate_ack_subject'],
                    body=ack_body,
                    to_email=donor_email,
                )

            notified.append(tx_id)
            session['notified_txs'] = notified[-10:]
            session.pop('pending_donation', None)
    elif raw_status == 'pending':
        view_status = 'pending'
    else:
        view_status = 'failed'

    return render_template(
        'soutenir_retour.html',
        tx_status=view_status,
        tx_reference=reference,
        tx_amount_display=_format_xof(amount) if amount else '—',
        tx_cause=cause_label,
        tx_raw_status=raw_status or 'unknown',
    )


@don_bp.route('/api/fedapay/webhook', methods=['POST'])
def fedapay_webhook():
    """Endpoint optionnel de réception sécurisée des webhooks FedaPay."""
    webhook_secret = current_app.config.get('FEDAPAY_WEBHOOK_SECRET') or Config.FEDAPAY_WEBHOOK_SECRET
    raw_body = request.get_data() or b''

    if webhook_secret:
        sig_header = (request.headers.get('X-FEDAPAY-SIGNATURE') or '').strip()
        if not sig_header:
            return jsonify({'status': 'error', 'message': 'Missing signature'}), 400

        # FedaPay signe le payload avec HMAC-SHA256 (format t=...,s=... ou hex direct)
        parts = dict(item.split('=', 1) for item in sig_header.split(',') if '=' in item)
        if 't' in parts and 's' in parts:
            signed_payload = f"{parts['t']}.".encode('utf-8') + raw_body
            expected = hmac.new(webhook_secret.encode('utf-8'), signed_payload, hashlib.sha256).hexdigest()
            valid = hmac.compare_digest(parts['s'], expected)
        else:
            expected = hmac.new(webhook_secret.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()
            valid = hmac.compare_digest(sig_header, expected)

        if not valid:
            return jsonify({'status': 'error', 'message': 'Invalid signature'}), 401

    return jsonify({'status': 'received'}), 200
