import time
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from config import send_email_notification
from i18n import get_current_lang, get_translations

partenariat_bp = Blueprint('partenariat', __name__)

@partenariat_bp.route('/partenariat', methods=['GET'])
def partner_form():
    """Renders the partnership proposal form with invisible multi-layer anti-bot security"""
    security_token = secrets.token_urlsafe(24)
    session['partner_security_token'] = security_token
    session['partner_form_time'] = time.time()
    
    return render_template('partenariat.html', security_token=security_token)

@partenariat_bp.route('/partenariat', methods=['POST'])
def partner_submit():
    """Handles partnership proposal submission via SMTP"""
    lang = get_current_lang()
    t = get_translations(lang)

    # 1. Protection Anti-Robot Multicouche Invisible (Honeypot + Jeton dynamique JS + Délai humain)
    honeypot = request.form.get('website_url')
    submitted_token = request.form.get('security_token', '')
    expected_token = session.pop('partner_security_token', None)
    form_time = session.pop('partner_form_time', 0)
    elapsed = time.time() - form_time if form_time else 0
    
    if honeypot or not expected_token or submitted_token != expected_token or elapsed < 2.0:
        return render_template('partenariat_confirmation.html', 
                               title=t['partner_spam_title'], 
                               message=t['partner_spam_msg'], 
                               status="error")
        
    # 2. Input Extraction
    org_name = request.form.get('org_name', '').strip()
    partner_type = request.form.get('partner_type', '').strip()
    country = request.form.get('country', '').strip()
    contact_name = request.form.get('contact_name', '').strip()
    contact_role = request.form.get('contact_role', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    funding_capacity = request.form.get('funding_capacity', '').strip()
    message = request.form.get('message', '').strip()
    
    selected_domains = request.form.getlist('domains')
    domains_str = ", ".join(selected_domains)
    
    if not all([org_name, partner_type, country, contact_name, email, domains_str]):
        flash(t['partner_missing_fields'], "error")
        return redirect(url_for('partenariat.partner_form'))
        
    notify_email = current_app.config.get('PARTNER_NOTIFY_EMAIL', 'ongelide@gmail.com')
    
    # Préparation du récapitulatif pour l'ONG
    email_subject = f"[Partenariat ELiDe] Nouvelle proposition — {org_name}"
    email_body = (
        f"Bonjour l'équipe,\n\n"
        f"Une nouvelle proposition de partenariat a été soumise sur le site web (Langue : {lang.upper()}) :\n\n"
        f"- Organisation : {org_name} ({partner_type})\n"
        f"- Pays : {country}\n"
        f"- Contact : {contact_name} ({contact_role or 'Non renseigné'})\n"
        f"- Email : {email}\n"
        f"- Téléphone : {phone or 'Non renseigné'}\n"
        f"- Domaines d'intérêt : {domains_str}\n"
        f"- Capacité / Intention de financement : {funding_capacity or 'Non renseignée'}\n"
        f"- Message : {message or 'Aucun message'}\n"
    )
    
    # Envoi SMTP à l'ONG + accusé de réception au partenaire (si SMTP configuré)
    email_sent = send_email_notification(
        subject=email_subject,
        body=email_body,
        to_email=notify_email,
        reply_to=email
    )
    if email_sent:
        if lang == 'en':
            partner_ack_body = (
                f"Dear {contact_name},\n\n"
                f"Thank you sincerely for submitting a partnership proposal on behalf of '{org_name}' "
                f"regarding our focus areas ({domains_str}).\n"
                f"Our National Office will review your proposal and get back to you within 5 business days.\n\n"
                f"Warm regards,\nThe Les Élites de Demain NGO (ELiDe) Team"
            )
        else:
            partner_ack_body = (
                f"Bonjour {contact_name},\n\n"
                f"Nous vous remercions chaleureusement pour la proposition de partenariat de '{org_name}' "
                f"concernant nos domaines d'action ({domains_str}).\n"
                f"Notre Bureau National prendra contact avec vous sous 5 jours ouvrés.\n\n"
                f"Cordialement,\nL'équipe de l'ONG Les Élites de Demain (ELiDe)"
            )
        send_email_notification(
            subject=t['partner_ack_subject'],
            body=partner_ack_body,
            to_email=email
        )
    
    session['last_lead'] = {
        'org_name': org_name,
        'partner_type': partner_type,
        'country': country,
        'contact_name': contact_name,
        'contact_role': contact_role,
        'email': email,
        'phone': phone,
        'domains': domains_str,
        'funding_capacity': funding_capacity,
        'message': message,
        'email_sent': email_sent
    }
    return redirect(url_for('partenariat.partner_confirmation'))

@partenariat_bp.route('/partenariat/confirmation', methods=['GET'])
def partner_confirmation():
    """Renders the confirmation page for the submitted partner proposal"""
    lead = session.get('last_lead')
    if not lead:
        return redirect(url_for('partenariat.partner_form'))
    return render_template('partenariat_confirmation.html', lead=lead)
