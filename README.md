# Lost & Found Festival

## Description

Application Flask pour gérer les objets perdus, trouvés et rendus lors d'un festival.

## Structure

- **app.py** : configuration Flask et initialisation SQLAlchemy.
- **models.py** : définition des tables `Category` et `Item`.
- **forms.py** : WTForms pour création/édition, réclamation et confirmation.
- **views.py** : routes Flask (CRUD, listing, matching, export).
- **categories_seed.py** : script pour peupler la table `categories`.
- **templates/** : vues Jinja2.
- **static/css/** : fichiers CSS (style.css).
- **static/js/** : fichiers JS (main.js).
- **static/uploads/** : stockage des photos (volume persistant sur Railway).
- **requirements.txt** : dépendances Python.
- **Procfile** : pour déploiement sur Railway.

## Installation locale

1. Cloner ce dépôt.
2. Créer un environnement virtuel Python 3.10+ :
   ```
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Installer les dépendances :
   ```
   pip install -r requirements.txt
   ```
4. Configurer `.env` (facultatif) ou définir les variables d'environnement :
   - `SECRET_KEY` : clé secrète Flask.
   - `DATABASE_URL` : URI PostgreSQL (ex. `postgresql://user:pass@localhost:5432/lostfound`).
5. Exécuter le script de seed des catégories :
   ```
   python categories_seed.py
   ```
6. Lancer l'application :
   ```
   python app.py
   ```
7. Ouvrir `http://127.0.0.1:5000` dans le navigateur.

## Déploiement sur Railway

1. Créer un projet Railway.
2. Ajouter le plugin PostgreSQL → récupérer `DATABASE_URL`.
3. Définir les variables d'environnement : `SECRET_KEY`, `DATABASE_URL`.
4. Configurer le volume persistant pour `./static/uploads`.
5. Connecter votre dépôt GitHub à Railway.
6. Lancer le script `categories_seed.py` via la commande “Run” sur Railway.
7. Railway détecte automatiquement le `Procfile` et déploie :
   ```
   web: gunicorn app:app
   ```
8. Tester l'application en production.

## Fonctionnalités

- **Authentification sécurisée** :
  - Connexion/inscription sur une page unique (`auth.html`).
  - Un seul administrateur peut être créé via l'interface (admin unique).
  - Protection CSRF sur tous les formulaires (pas de doublon d'id, gestion manuelle si besoin).
  - Les sessions sont gérées avec Flask-Login.
- **Gestion des droits** :
  - Tous les utilisateurs connectés peuvent consulter et signaler des objets.
  - Seuls les admins peuvent modifier ou supprimer des objets (contrôlé côté backend et UI).
  - Le bouton "Admin" dans la navbar n'apparaît que pour les admins.
- **Signalement Lost/Found** : formulaires avec upload photo, catégorie, description, coordonnées.
- **Matching interne** : détection de titres similaires avant validation (Ajax + RapidFuzz).
- **Listing en cartes** : interface responsive avec Bootstrap, pagination.
- **Détail & Réclamation** : passer un objet au statut “returned” via formulaire.
- **Modification & Suppression** : édition/suppression réservées à l'admin.
- **Export HTML** : télécharger un fichier `.html` brut contenant toutes les informations hors ligne.

## Structure actuelle

- **app.py** : point d'entrée Flask, config globale.
- **models.py** : modèles SQLAlchemy (User, Item, Category...).
- **forms.py** : WTForms (connexion, inscription, signalement, etc.).
- **views.py** : routes Flask, logique d'authentification, droits, listing, etc.
- **templates/** :
  - `base.html` (layout général, navbar conditionnelle selon le rôle)
  - `auth.html` (connexion/inscription)
  - `list.html` (listing objets, pagination)
  - `detail.html`, `report.html`, etc.
- **static/** : CSS, JS, uploads.
- **categories_seed.py** : script d'initialisation des catégories.

## Sécurité & Bonnes pratiques

- Authentification par email/mot de passe, hash sécurisé.
- Vérification stricte des droits admin sur toutes les routes sensibles.
- Protection CSRF sur tous les formulaires.
- Affichage des erreurs de validation et des messages flash.
- UI en français.

## Correction des bugs récents

- Correction du bug de connexion (détection fiable du formulaire via `name` sur les boutons submit).
- Correction du warning CSRF (id unique par formulaire).
- Correction des erreurs de template Jinja2 (structure des boucles, suppression du code mort).
- Vérification complète de la logique d'authentification et de droits.

## Comportement attendu (admin vs utilisateur)

- **Admin :** accès à l'interface admin, modification/suppression d'objets, bouton "Admin" visible.
- **Utilisateur normal :** accès à la liste, au détail, au signalement, mais pas d'édition/suppression ni d'accès admin.

## Dépannage

- **Erreur CSRF ou "duplicate id"** : vider le cache, vérifier le HTML généré, chaque input CSRF a un id unique (`login_csrf_token`, `register_csrf_token`).
- **Erreur Jinja2 (endfor/endblock)** : vérifier la structure du template, ne laisser qu'une seule boucle principale.
- **Problème de droits** : vérifier le rôle de l'utilisateur et la présence du bouton "Admin".
- **Connexion ne fonctionne pas** : s'assurer que les boutons submit ont bien un attribut `name` et que la vue Flask détecte le bon formulaire.

---
