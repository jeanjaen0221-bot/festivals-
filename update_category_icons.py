# Rapport de conception et plan d'amélioration — Application "festival"

## 1. Structure du projet

```
festival/
├── app.py
├── config.py
├── models.py
├── templates/
│   ├── items/
│   ├── loans/
│   ├── admin/
│   └── ...
├── static/
│   ├── css/
│   ├── js/
│   └── icons/
├── blueprints/
│   ├── items.py
│   ├── loans.py
│   └── admin.py
├── forms.py
├── migrations/
├── tests/
└── ...
```

### Détails des dossiers/fichiers principaux
- `app.py` : point d’entrée de l’application Flask, enregistre les blueprints, configure l’app.
- `views.py` : contient la majorité des routes et de la logique métier (gestion objets, prêts, etc.).
- `models.py` : définit les modèles de données SQLAlchemy.
- `forms.py` : définit les formulaires WTForms utilisés dans l’UI.
- `admin.py` : routes et logique d’administration.
- `templates/` : templates Jinja2 pour toutes les pages HTML.
- `static/` : fichiers statiques (CSS, JS, images, icônes).
- `migrations/` : gestion des migrations de base de données (Flask-Migrate).
- `api/` : endpoints API (ex : trains, autres fonctionnalités REST).
- `category_icon_map.py` et `fetch_category_icons.py` : gestion des icônes de catégories.
- `ocr_utils.py` : utilitaires pour la reconnaissance de texte sur carte d’identité (OCR).
- `reset_db.py`, `create_admin.py`, `categories_seed.py` : scripts d’administration et d’initialisation.

---

## 2. Fonctionnalités principales

- Gestion des objets perdus/trouvés/rendus (modèle `Item`, routes dans `views.py`)
- Gestion des prêts de casques (modèle `HeadphoneLoan`, routes dans `views.py`)
- Gestion des catégories (modèle `Category`, routes, icônes, seed)
- Gestion des utilisateurs (authentification, rôles, avec Flask-Login)
- Administration (routes dédiées dans `admin.py`)
- Recherche et filtrage (par catégorie, par nom pour les prêts)
- Correspondance automatique objets perdus/trouvés (matching, fuzzy search)
- OCR pour extraire des infos sur les cartes d’identité
- Gestion des fichiers et images (upload, static)
- API REST pour certaines fonctionnalités
- Gestion des migrations et scripts d’initialisation
- Templates Bootstrap pour l’UI

---

## 3. Architecture recommandée

### a. Découpage par modules
- Séparer les routes métier (objets, prêts, admin, API…) dans différents fichiers (blueprints).
- Garder les modèles dans `models.py` ou les découper par domaine si le fichier devient trop gros.
- Séparer les formulaires dans `forms.py`.

### b. Utilisation des Blueprints
- Utiliser un blueprint principal (`main`), un blueprint admin, un blueprint API.
- Cela permet de mieux organiser les routes et de faciliter la maintenance.

### c. Templates et statiques
- Organiser les templates par fonctionnalité (ex : `templates/items/`, `templates/admin/`…).
- Mettre les JS/CSS spécifiques dans des sous-dossiers de `static/`.

### d. Configuration
- Centraliser la configuration (dev/prod/test) dans un fichier `config.py` ou via des variables d’environnement.

### e. Sécurité
- Utiliser Flask-Login pour la gestion des sessions.
- Protéger les routes sensibles par `@login_required` et des vérifications de rôle.
- Protéger les formulaires contre le CSRF.
- Valider et sécuriser les uploads de fichiers.

### f. Modèles de données
- Utiliser SQLAlchemy pour l’ORM.
- Préférer des relations explicites (ForeignKey, backref).
- Ajouter des méthodes utilitaires dans les modèles si besoin.

### g. Tests et scripts
- Prévoir un dossier `tests/` pour les tests unitaires et d’intégration.
- Utiliser des scripts d’init (`reset_db.py`, `categories_seed.py`) pour l’administration.

---

## 4. Conseils de conception

- Garder les vues courtes : déplacer la logique métier lourde dans des fonctions ou des services dédiés.
- Utiliser les blueprints pour séparer les domaines (objets, prêts, admin, API…).
- Centraliser les erreurs et messages flash pour une UX cohérente.
- Documenter les modèles, routes, et scripts dans le README.
- Préférer les formulaires WTForms pour la validation et la sécurité.
- Utiliser les migrations (Flask-Migrate) pour la gestion du schéma de la base.
- Versionner les dépendances dans `requirements.txt`.
- Automatiser les tâches répétitives (scripts, seed, reset…).

---

## 5. Plan d’amélioration intégré

### a. Ajouter des tests automatisés
- Créer un dossier `tests/` avec des tests unitaires pour les modèles, vues et formulaires.
- Utiliser `pytest` et `pytest-flask`.

### b. Gestion fine des rôles utilisateurs
- Ajouter des rôles (admin, staff, bénévole…) dans le modèle User.
- Restreindre certaines routes à certains rôles.

### c. Factorisation des templates
- Utiliser des blocs et des inclusions Jinja2 pour éviter la duplication de code HTML.

### d. API RESTful
- Étendre le dossier `api/` pour proposer des endpoints RESTful (CRUD objets, prêts, utilisateurs).
- Utiliser Flask-RESTful ou Flask-Classful.

### e. UX mobile
- Améliorer la responsivité avec Bootstrap.
- Tester sur mobile/tablette.
- Ajouter éventuellement une PWA (Progressive Web App).

### f. Documentation technique
- Ajouter des diagrammes (UML, schéma de base de données) dans le README ou un dossier `docs/`.
- Détailler les endpoints, modèles et scripts.

### g. Gestion globale des erreurs
- Créer des handlers d’erreurs globaux (404, 500, etc.) dans Flask.
- Afficher des pages d’erreur personnalisées.

### h. Sécurité renforcée
- Vérifier la gestion des sessions, CSRF, XSS, uploads.
- Utiliser HTTPS en production.

---

## 6. Exemple d’organisation finale recommandée

```
festival/
├── app.py
├── config.py
├── models.py
├── blueprints/
│   ├── items.py
│   ├── loans.py
│   ├── admin.py
│   └── api.py
├── forms.py
├── templates/
│   ├── base.html
│   ├── items/
│   ├── loans/
│   ├── admin/
│   └── ...
├── static/
│   ├── css/
│   ├── js/
│   └── icons/
├── tests/
├── migrations/
├── README.md
├── requirements.txt
└── docs/
```

---

**Ce plan et rapport te donnent une vision claire pour concevoir, maintenir et améliorer ton application festival. Tu peux l’adapter à tes besoins et t’en servir comme feuille de route pour la refonte ou l’évolution du projet.**
