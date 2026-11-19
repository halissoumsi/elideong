from flask import Blueprint, render_template, request, jsonify, current_app, send_from_directory, redirect, session, Response
from config import send_email_notification, is_smtp_configured
from i18n import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE, LANG_COOKIE_NAME, get_translations
from security import (
    is_valid_email,
    get_client_ip,
    check_rate_limit,
    generate_form_token,
    verify_form_token,
)

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
        httponly=True,
        secure=current_app.config.get('SESSION_COOKIE_SECURE', False)
    )
    return response


@public_bp.route('/')
def index():
    contact_token = generate_form_token(current_app.config['SECRET_KEY'])
    return render_template('index.html', contact_token=contact_token)


@public_bp.route('/elide-track')
def elide_track():
    return render_template('elide_track.html')


@public_bp.route('/robots.txt')
def robots_txt():
    base_url = request.url_root.rstrip('/')
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /lang/\n"
        f"Sitemap: {base_url}/sitemap.xml\n"
    )
    return Response(content, mimetype='text/plain')


@public_bp.route('/sitemap.xml')
def sitemap_xml():
    base_url = request.url_root.rstrip('/')
    pages = [
        ('/', 'weekly', '1.0'),
        ('/partenariat', 'monthly', '0.9'),
        ('/elide-track', 'monthly', '0.8'),
        ('/mentions-legales', 'yearly', '0.3'),
        ('/politique-de-confidentialite', 'yearly', '0.3'),
    ]
    urls_xml = []
    for path, changefreq, priority in pages:
        loc = f"{base_url}{path}"
        fr_href = f"{loc}?lang=fr"
        en_href = f"{loc}?lang=en"
        urls_xml.append(
            f"  <url>\n"
            f"    <loc>{loc}</loc>\n"
            f"    <xhtml:link rel=\"alternate\" hreflang=\"fr\" href=\"{fr_href}\"/>\n"
            f"    <xhtml:link rel=\"alternate\" hreflang=\"en\" href=\"{en_href}\"/>\n"
            f"    <xhtml:link rel=\"alternate\" hreflang=\"x-default\" href=\"{loc}\"/>\n"
            f"    <changefreq>{changefreq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + "\n".join(urls_xml)
        + "\n</urlset>\n"
    )
    return Response(xml, mimetype='application/xml')


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
    """Traite le formulaire de contact via envoi SMTP avec protection anti-spam et rate limiting."""
    t = get_translations()
    try:
        # 1. Limitation de débit (max 5 messages / 10 minutes par IP)
        client_ip = get_client_ip(request)
        if not check_rate_limit('contact', client_ip, limit=5, window_seconds=600):
            return jsonify({'status': 'error', 'message': t['api_contact_rate_limited']}), 429

        data = request.get_json(silent=True) or request.form
        honeypot = (data.get('website_url') or '').strip()
        contact_token = (data.get('contact_token') or '').strip()

        # 2. Protection anti-robot invisible (Honeypot + Jeton HMAC horodaté)
        if honeypot or not verify_form_token(current_app.config['SECRET_KEY'], contact_token, min_age=2.0):
            return jsonify({'status': 'error', 'message': t['api_contact_spam']}), 400

        name = (data.get('name') or '').strip()
        email = (data.get('email') or '').strip()
        subject = (data.get('subject') or '').strip()
        message = (data.get('message') or '').strip()

        if not all([name, email, subject, message]):
            return jsonify({'status': 'error', 'message': t['api_contact_missing']}), 400

        if not is_valid_email(email):
            return jsonify({'status': 'error', 'message': t['api_contact_invalid_email']}), 400

        if len(name) > 150 or len(subject) > 200 or len(message) > 5000:
            return jsonify({'status': 'error', 'message': t['api_contact_too_long']}), 400

        notify_email = current_app.config.get('PARTNER_NOTIFY_EMAIL', 'ongelide@gmail.com')

        email_subject = f"[Contact Site ELiDe] {subject} — {name}"
        email_body = (
            f"Nouveau message reçu depuis le formulaire de contact de l'ONG ELiDe :\n\n"
            f"Nom / Organisation : {name}\n"
            f"Email : {email}\n"
            f"Sujet : {subject}\n\n"
            f"Message :\n{message}\n"
        )

        # 3. Envoi SMTP sécurisé
        email_sent = send_email_notification(
            subject=email_subject,
            body=email_body,
            to_email=notify_email,
            reply_to=email
        )

        if is_smtp_configured() and not email_sent:
            return jsonify({'status': 'error', 'message': t['api_contact_delivery_failed']}), 503

        next_token = generate_form_token(current_app.config['SECRET_KEY'])
        return jsonify({
            'status': 'success',
            'email_sent': email_sent,
            'next_token': next_token,
            'message': t['api_contact_success']
        }), 200
    except Exception as e:
        print(f"[CONTACT ERROR] {e}")
        return jsonify({'status': 'error', 'message': t['api_contact_error']}), 500
