from flask import Flask, request, url_for, g, session, render_template, jsonify
from config import Config
from i18n import get_current_lang, get_translations, LANG_COOKIE_NAME

CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.fedapay.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.fedapay.com; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "img-src 'self' data: https:; "
    "connect-src 'self' https://*.fedapay.com; "
    "frame-src 'self' https://*.fedapay.com; "
    "manifest-src 'self'; "
    "worker-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    @app.context_processor
    def inject_i18n():
        lang = get_current_lang()
        t = get_translations(lang)
        base_url = request.url_root.rstrip('/')
        clean_path = request.path or '/'
        canonical_url = f"{base_url}{clean_path}" if clean_path != '/' else f"{base_url}/"

        def switch_lang_url(target_lang):
            return url_for('public.set_language', lang_code=target_lang, next=clean_path)

        return {
            'lang': lang,
            't': t,
            'base_url': base_url,
            'canonical_url': canonical_url,
            'switch_lang_url': switch_lang_url
        }

    @app.after_request
    def apply_security_and_lang_headers(response):
        # Persistance de la langue si choisie via ?lang=fr|en
        persist_lang = getattr(g, 'persist_lang_cookie', None)
        if persist_lang:
            session['lang'] = persist_lang
            response.set_cookie(
                LANG_COOKIE_NAME,
                persist_lang,
                max_age=60 * 60 * 24 * 365,
                samesite='Lax',
                httponly=True,
                secure=app.config.get('SESSION_COOKIE_SECURE', False)
            )

        # En-têtes de sécurité HTTP (OWASP)
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault(
            'Permissions-Policy',
            'geolocation=(), microphone=(), camera=(), payment=(), usb=()'
        )
        if app.config.get('IS_PRODUCTION') or request.is_secure:
            response.headers.setdefault(
                'Strict-Transport-Security',
                'max-age=31536000; includeSubDomains'
            )

        if request.path.startswith('/static/') and response.status_code == 200:
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'

        if response.mimetype == 'text/html':
            response.headers.setdefault('Content-Security-Policy', CSP_POLICY)
            response.headers.add('Vary', 'Cookie')

        return response

    # Pages d'erreur personnalisées bilingues (404 / 500 / 429)
    @app.errorhandler(404)
    def handle_not_found(_err):
        t = get_translations()
        if request.path.startswith('/api/'):
            return jsonify({'status': 'error', 'message': t['error_404_heading']}), 404
        return render_template(
            'error.html',
            error_code=404,
            page_title=t['error_404_title'],
            error_heading=t['error_404_heading'],
            error_desc=t['error_404_desc']
        ), 404

    @app.errorhandler(429)
    def handle_too_many_requests(_err):
        t = get_translations()
        if request.path.startswith('/api/'):
            return jsonify({'status': 'error', 'message': t['api_contact_rate_limited']}), 429
        return render_template(
            'error.html',
            error_code=429,
            page_title=t['error_429_title'],
            error_heading=t['error_429_heading'],
            error_desc=t['error_429_desc']
        ), 429

    @app.errorhandler(500)
    def handle_internal_error(_err):
        t = get_translations()
        if request.path.startswith('/api/'):
            return jsonify({'status': 'error', 'message': t['api_contact_error']}), 500
        return render_template(
            'error.html',
            error_code=500,
            page_title=t['error_500_title'],
            error_heading=t['error_500_heading'],
            error_desc=t['error_500_desc']
        ), 500

    # Register blueprints
    from routes.public import public_bp
    from routes.partenariat import partenariat_bp
    from routes.don import don_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(partenariat_bp)
    app.register_blueprint(don_bp)

    return app


# Instance WSGI exposée pour Vercel
app = create_app()
