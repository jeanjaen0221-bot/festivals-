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

### Rate limiting multi-workers

Le Procfile lance plusieurs workers gunicorn ; par défaut, `flask-limiter`
stocke ses compteurs en mémoire (`memory://`), ce qui n'est pas partagé entre
workers : la limite effective globale devient alors un multiple de la valeur
configurée. Pour un rate-limiting réellement cohérent en production, ajoutez
le plugin Redis sur Railway et définissez la variable `REDIS_URL` ; le code
la détecte déjà automatiquement (`app.py`, `Limiter(storage_uri=...)`).

### Mémoire des workers gunicorn

Le Procfile utilise `-w 2` par défaut : le modèle DINOv2 (`visual_matcher.py`)
se charge en mémoire séparément dans chaque worker (~300-500 Mo chacun avec
torch), donc réduire le nombre de workers limite l'empreinte mémoire totale.
Si le plan Railway dispose de suffisamment de RAM, `-w 4` (ou plus) peut être
remis pour absorber davantage de trafic simultané.

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
- **Matching interne** : détection de titres similaires avant validation (Ajax + RapidFuzz), voir « Moteur de correspondance » plus bas.
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
- **zones.py** : liste des zones du site (source unique des formulaires).
- **categories_families.py** : familles de catégories + devinette de famille.
- **matching.py** : moteur de correspondance (score texte, bonus, seuils).

## Moteur de correspondance

Le score d'une paire perdu↔trouvé se construit en trois temps :

1. **Score texte** — titre (0,60), description (0,20), lieu (0,20), comparés
   après normalisation (accents, casse, stopwords, stemming français,
   synonymes). Un champ vide d'un seul côté est **exclu** de la pondération : une
   information absente n'est pas une divergence. Le score combine
   `token_sort_ratio` et `token_set_ratio` ; `partial_ratio` et `WRatio` sont
   volontairement écartés car ils donnent 100 à des titres courts sans rapport.
2. **Bonus/malus** — catégorie et famille (`family_bonus`), écart de date,
   couleurs / marque / signes distinctifs cochés (`structured_field_bonus`),
   similarité DINOv2 image↔image si les deux objets ont une photo indexée.
3. **Application du bonus sur la marge restante** (`apply_bonus`) — un bonus ne
   peut qu'entamer l'écart jusqu'à 100 au lieu de s'y écraser. Sans cela les
   scores s'agglutinaient au plafond et le seuil ne discriminait plus rien.

Deux points de conception importants :

- **Le lieu ne vaut ses 20 % que parce que les deux formulaires partagent la
  même liste de zones** (`zones.py`). Si vous repassez un côté en texte libre,
  baissez son poids dans `MATCH_CONFIG['fields_weights']`.
- **Un écart de famille est un malus (−40), pas une exclusion** : un objet mal
  catégorisé par un bénévole reste retrouvable en abaissant le seuil sur
  `/matches`. Une catégorie sans famille connue est neutre, jamais pénalisée.

Les agents voient un palier (**Fort / Moyen / Faible**) plutôt qu'un pourcentage :
le score brut n'est pas une probabilité et afficher « 100 % » donnerait une
fausse certitude. Le chiffre reste accessible en infobulle et dans « Détails ».

### Recalibrer les seuils sur les données réelles

Les valeurs de `MATCH_CONFIG` (seuil 85, paliers 92/80) viennent d'un corpus
simulé. Une fois que les agents ont validé et rejeté quelques dizaines de paires,
mesurez-les sur le terrain :

```bash
flask calibrate-matching
```

La commande balaie les seuils, affiche pour chacun le nombre de paires proposées,
le rappel et la précision (paires validées = vrais positifs, rejetées = faux
positifs), et signale les paires validées qui passeraient sous le seuil configuré.

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

### Matching visuel DINOv2

Le matching image↔image utilise localement `facebook/dinov2-small`. Définissez
`VISUAL_MATCHER_CACHE_DIR` vers un volume Railway persistant (par exemple
`/data/huggingface`) afin de conserver les poids téléchargés entre les
déploiements. L’état du modèle est affiché sur le tableau de bord admin et peut
être contrôlé par `GET /admin/visual-model-status`; une indisponibilité renvoie
un état explicite et ne constitue jamais une similarité de 0 %.

**Embeddings persistés (pas d'inférence dans le chemin de requête) :**
chaque photo d'objet est encodée une seule fois, à l'upload
(`_persist_item_photo` appelle `ensure_photo_embedding`), et le vecteur
float32 est stocké dans la table `photo_embeddings` (bytea, une ligne par
photo x version de modèle). Les pages de correspondance (`/item/<id>`,
`/matches`, `/api/match_explain`) ne font plus jamais tourner DINOv2 :
elles comparent uniquement des vecteurs déjà prêts via un simple produit
scalaire (`photo_embeddings.item_embedding_similarity`). C'est ce qui rend
`/matches` utilisable en production - avant ce correctif, cette page
relançait DINOv2 pour chaque paire Lost x Found (potentiellement des
milliers d'inférences par chargement de page), un point de blocage majeur
sur l'infrastructure limitée de Railway.

Après un déploiement qui ajoute ou modifie ce module, ou pour indexer des
photos existantes qui n'ont pas encore d'embedding, lancez une fois (Railway
-> onglet "Run") :
```
flask index-photo-embeddings
```
Ajoutez `--force` après un changement de `PHOTO_EMBEDDING_MODEL_VERSION`
pour recalculer tous les vecteurs avec le nouveau modèle.
