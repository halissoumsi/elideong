from urllib.parse import quote
from flask import Blueprint, render_template, request, jsonify, current_app
from config import send_email_notification

public_bp = Blueprint('public', __name__)

@public_bp.route('/')
def index():
    return render_template('index.html')

@public_bp.route('/mentions-legales')
def mentions_legales():
    return render_template('mentions_legales.html')

@public_bp.route('/politique-de-confidentialite')
def politique_confidentialite():
    return render_template('politique_confidentialite.html')

@public_bp.route('/api/contact', methods=['POST'])
def contact():
    """Traite le formulaire de contact : envoi SMTP + génération des liens WhatsApp et mailto"""
    try:
        data = request.get_json() or request.form
        name = (data.get('name') or '').strip()
        email = (data.get('email') or '').strip()
        subject = (data.get('subject') or '').strip()
        message = (data.get('message') or '').strip()
        
        if not all([name, email, subject, message]):
            return jsonify({'status': 'error', 'message': 'Veuillez remplir tous les champs du formulaire.'}), 400
            
        notify_email = current_app.config.get('PARTNER_NOTIFY_EMAIL', 'ongelide@gmail.com')
        whatsapp_number = current_app.config.get('WHATSAPP_NUMBER', '2290167576050')
        
        email_subject = f"[Contact Site ELiDe] {subject} — {name}"
        email_body = (
            f"Nouveau message reçu depuis le formulaire de contact de l'ONG ELiDe :\n\n"
            f"Nom / Organisation : {name}\n"
            f"Email : {email}\n"
            f"Sujet : {subject}\n\n"
            f"Message :\n{message}\n"
        )
        
        # 1. Envoi par SMTP (si configuré)
        email_sent = send_email_notification(
            subject=email_subject,
            body=email_body,
            to_email=notify_email,
            reply_to=email
        )
        
        # 2. Génération des liens directs WhatsApp et Mailto
        wa_text = (
            f"Bonjour ONG ELiDe,\n"
            f"Je suis *{name}* ({email}).\n"
            f"*Objet :* {subject}\n\n"
            f"{message}"
        )
        whatsapp_url = f"https://wa.me/{whatsapp_number}?text={quote(wa_text)}"
        mailto_url = f"mailto:{notify_email}?subject={quote(email_subject)}&body={quote(email_body)}"
        
        return jsonify({
            'status': 'success',
            'email_sent': email_sent,
            'whatsapp_url': whatsapp_url,
            'mailto_url': mailto_url,
            'message': 'Votre message a bien été préparé et enregistré.'
        }), 200
    except Exception as e:
        print(f"[CONTACT ERROR] {e}")
        return jsonify({'status': 'error', 'message': "Une erreur interne est survenue lors de l'envoi."}), 500
