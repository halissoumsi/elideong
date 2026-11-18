from flask import Flask
from config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Register blueprints
    from routes.public import public_bp
    from routes.partenariat import partenariat_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(partenariat_bp)

    return app

# Instance WSGI exposée pour Vercel
app = create_app()
