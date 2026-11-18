# Site Vitrine de l'ONG Les Élites de Demain (ELiDe)

Ce projet contient les sources du site vitrine institutionnel officiel de l'**ONG Les Élites de Demain (ELiDe)**, basée à Parakou, Bénin.

## 📁 Structure du Projet

- **`app.py` / `run.py` / `config.py`** : Serveur web léger sous Flask.
- **`routes/public.py`** : Route principale (`/`) et endpoint du formulaire de contact (`/api/contact`).
- **`routes/partenariat.py`** : Formulaire dédié aux propositions de partenariat (`/partenariat`).
- **`templates/index.html`** : Page d'accueil du site vitrine (Accueil, À Propos, Missions, Domaines d'Intervention, Contact).
- **`templates/partenariat.html` & `partenariat_confirmation.html`** : Pages de proposition de partenariat et de confirmation.
- **`static/css/style.css`** : Feuille de style principale.
- **`static/js/app.js`** : Script d'interactivité (animations au défilement, menu mobile, formulaire de contact).
- **`static/assets/`** : Logos officiels de l'organisation.

## 🚀 Lancement en Local

1. **Installer les dépendances** :
   ```bash
   pip install -r requirements.txt
   ```
2. **Lancer le serveur** :
   ```bash
   python run.py
   ```
3. **Ouvrir dans le navigateur** :
   Rendez-vous sur [http://127.0.0.1:5000](http://127.0.0.1:5000).

## 🌐 Mise en Production

Avec `waitress` :
```bash
waitress-serve --host=0.0.0.0 --port=5000 --call app:create_app
```
