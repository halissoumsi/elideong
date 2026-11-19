from flask import Blueprint, render_template, request, jsonify, current_app, send_from_directory, redirect, session
from config import send_email_notification
from i18n import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE, LANG_COOKIE_NAME, get_translations

public_bp = Blueprint('public', __name__)

@public_bp.route('/lang/<lang_code>')
def set_language(lang_code):
    """Change la langue active (FR/EN), enregistre la préférence et redirige vers la page courante."""
    code = (lang_code or '').strip().lower()
    if code not in SUPPORTED_LANGUAGES:
        code = DEFAULT_LANGUAGE

    session['lang'] = code

    next_url = (request.args.get('next') or '/').strip()
    if not next_url.startswith('/') or next_url.startswith('//'):
        next_url = '/'

    response = redirect(next_url)
    response.set_cookie(
        LANG_COOKIE_NAME,
        code,
        max_age=60 * 60 * 24 * 365,
        samesite='Lax',
        httponly=True
    )
    return response

@public_bp.route('/')
def index():
    return render_template('index.html')

@public_bp.route('/manifest.json')
def manifest():
    response = send_from_directory(current_app.static_folder, 'manifest.json', mimetype='application/manifest+json')
    response.headers['Cache-Control'] = 'no-cache'
    return response

@public_bp.route('/sw.js')
def service_worker():
    response = send_from_directory(current_app.static_folder, 'sw.js', mimetype='application/javascript')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Service-Worker-Allowed'] = '/'
    return response

@public_bp.route('/mentions-legales')
def mentions_legales():
    return render_template('mentions_legales.html')

@public_bp.route('/politique-de-confidentialite')
def politique_confidentialite():
    return render_template('politique_confidentialite.html')

@public_bp.route('/api/contact', methods=['POST'])
def contact():
    """Traite le formulaire de contact via envoi SMTP"""
    t = get_translations()
    try:
        data = request.get_json() or request.form
        name = (data.get('name') or '').strip()
        email = (data.get('email') or '').strip()
        subject = (data.get('subject') or '').strip()
        message = (data.get('message') or '').strip()
        
        if not all([name, email, subject, message]):
            return jsonify({'status': 'error', 'message': t['api_contact_missing']}), 400
            
        notify_email = current_app.config.get('PARTNER_NOTIFY_EMAIL', 'ongelide@gmail.com')
        
        email_subject = f"[Contact Site ELiDe] {subject} — {name}"
        email_body = (
            f"Nouveau message reçu depuis le formulaire de contact de l'ONG ELiDe :\n\n"
            f"Nom / Organisation : {name}\n"
            f"Email : {email}\n"
            f"Sujet : {subject}\n\n"
            f"Message :\n{message}\n"
        )
        
        # Envoi par SMTP (si configuré)
        email_sent = send_email_notification(
            subject=email_subject,
            body=email_body,
            to_email=notify_email,
            reply_to=email
        )
        
        return jsonify({
            'status': 'success',
            'email_sent': email_sent,
            'message': t['api_contact_success']
        }), 200
    except Exception as e:
        print(f"[CONTACT ERROR] {e}")
        return jsonify({'status': 'error', 'message': t['api_contact_error']}), 500
