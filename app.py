from flask import Flask, request, url_for, g, session
from config import Config
from i18n import get_current_lang, get_translations, LANG_COOKIE_NAME

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    @app.context_processor
    def inject_i18n():
        lang = get_current_lang()
        t = get_translations(lang)

        def switch_lang_url(target_lang):
            next_path = request.path or '/'
            return url_for('public.set_language', lang_code=target_lang, next=next_path)

        return {
            'lang': lang,
            't': t,
            'switch_lang_url': switch_lang_url
        }

    @app.after_request
    def persist_language_preference(response):
        persist_lang = getattr(g, 'persist_lang_cookie', None)
        if persist_lang:
            session['lang'] = persist_lang
            response.set_cookie(
                LANG_COOKIE_NAME,
                persist_lang,
                max_age=60 * 60 * 24 * 365,
                samesite='Lax',
                httponly=True
            )
        if response.mimetype == 'text/html':
            response.headers.add('Vary', 'Cookie')
        return response

    # Register blueprints
    from routes.public import public_bp
    from routes.partenariat import partenariat_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(partenariat_bp)

    return app

# Instance WSGI exposée pour Vercel
app = create_app()
