import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager
import sqlalchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
raw_url = (os.environ.get('DATABASE_URL') or os.environ.get('DATABASE_PUBLIC_URL') or '').strip()
if raw_url.startswith('postgres://'):
    raw_url = 'postgresql://' + raw_url[len('postgres://'):]
if raw_url.startswith('postgresql://') and '+psycopg' not in raw_url and '+psycopg2' not in raw_url:
    raw_url = 'postgresql+psycopg://' + raw_url[len('postgresql://'):]
app.config['SQLALCHEMY_DATABASE_URI'] = raw_url
print("DATABASE_URL utilisé :", app.config['SQLALCHEMY_DATABASE_URI'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Sécurité : forcer la présence de secrets en production
if not app.config['SECRET_KEY'] or app.config['SECRET_KEY'] == 'change_this_in_prod':
    raise RuntimeError('SECRET_KEY doit être défini dans les variables d\'environnement !')
if not app.config['SQLALCHEMY_DATABASE_URI'] or 'user:pass@localhost' in app.config['SQLALCHEMY_DATABASE_URI']:
    raise RuntimeError('DATABASE_URL PostgreSQL doit être défini dans les variables d\'environnement Railway !')

# Cookies de session sécurisés
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Headers HTTP de sécurité
@app.after_request
def set_security_headers(response):
    response.headers['Strict-Transport-Security'] = 'max-age=63072000; includeSubDomains; preload'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://code.jquery.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
        "img-src 'self' data:; "
        "object-src 'none'; "
        "base-uri 'self'; "
    )
    return response

# Upload configuration
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024  # 30 MB

db = SQLAlchemy(app)
csrf = CSRFProtect(app)

from flask_login import LoginManager
login_manager = LoginManager(app)
login_manager.login_view = 'main.auth'
login_manager.login_message_category = 'info'

# Import models and create tables
import models
from models import User
with app.app_context():
    db.create_all()
    # Création sécurisée de la table headphone_loans si elle n'existe pas déjà
    try:
        engine = db.get_engine()
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text('''
                CREATE TABLE IF NOT EXISTS headphone_loans (
                    id SERIAL PRIMARY KEY,
                    first_name VARCHAR(100) NOT NULL,
                    last_name VARCHAR(100) NOT NULL,
                    phone VARCHAR(50) NOT NULL,
                    deposit_type VARCHAR(20) NOT NULL,
                    deposit_details VARCHAR(200),
                    quantity INTEGER NOT NULL DEFAULT 1,
                    deposit_amount NUMERIC(10,2),
                    loan_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    return_date TIMESTAMP,
                    signature TEXT
                )
            '''))
            # Ajout automatique des colonnes manquantes (Railway, PostgreSQL)
            # Ajoute quantity si manquant
            result = conn.execute(sqlalchemy.text("""
                SELECT column_name FROM information_schema.columns WHERE table_name='headphone_loans' AND column_name='quantity'
            """))
            if result.fetchone() is None:
                conn.execute(sqlalchemy.text("ALTER TABLE headphone_loans ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1;"))
                conn.execute(sqlalchemy.text("COMMIT;"))
            # Ajoute deposit_amount si manquant
            result = conn.execute(sqlalchemy.text("""
                SELECT column_name FROM information_schema.columns WHERE table_name='headphone_loans' AND column_name='deposit_amount'
            """))
            if result.fetchone() is None:
                conn.execute(sqlalchemy.text("ALTER TABLE headphone_loans ADD COLUMN deposit_amount NUMERIC(10,2);"))
                conn.execute(sqlalchemy.text("COMMIT;"))
            # Ajoute status si manquant
            result = conn.execute(sqlalchemy.text("""
                SELECT column_name FROM information_schema.columns WHERE table_name='headphone_loans' AND column_name='status'
            """))
            if result.fetchone() is None:
                conn.execute(sqlalchemy.text("ALTER TABLE headphone_loans ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active';"))
                conn.execute(sqlalchemy.text("COMMIT;"))
            # Ajoute previous_status si manquant
            result = conn.execute(sqlalchemy.text("""
                SELECT column_name FROM information_schema.columns WHERE table_name='headphone_loans' AND column_name='previous_status'
            """))
            if result.fetchone() is None:
                conn.execute(sqlalchemy.text("ALTER TABLE headphone_loans ADD COLUMN previous_status VARCHAR(20);"))
                conn.execute(sqlalchemy.text("COMMIT;"))
            # --- Ensure shuttle_settings columns exist ---
            try:
                # loop_enabled
                result = conn.execute(sqlalchemy.text("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name='shuttle_settings' AND column_name='loop_enabled'
                """))
                if result.fetchone() is None:
                    conn.execute(sqlalchemy.text("ALTER TABLE shuttle_settings ADD COLUMN loop_enabled BOOLEAN NOT NULL DEFAULT FALSE;"))
                    conn.execute(sqlalchemy.text("COMMIT;"))
                # bidirectional_enabled
                result = conn.execute(sqlalchemy.text("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name='shuttle_settings' AND column_name='bidirectional_enabled'
                """))
                if result.fetchone() is None:
                    conn.execute(sqlalchemy.text("ALTER TABLE shuttle_settings ADD COLUMN bidirectional_enabled BOOLEAN NOT NULL DEFAULT FALSE;"))
                    conn.execute(sqlalchemy.text("COMMIT;"))
                # constrain_to_today_slots
                result = conn.execute(sqlalchemy.text("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name='shuttle_settings' AND column_name='constrain_to_today_slots'
                """))
                if result.fetchone() is None:
                    conn.execute(sqlalchemy.text("ALTER TABLE shuttle_settings ADD COLUMN constrain_to_today_slots BOOLEAN NOT NULL DEFAULT FALSE;"))
                    conn.execute(sqlalchemy.text("COMMIT;"))
            except Exception as e2:
                print(f"[WARN] Impossible d'ajouter les colonnes shuttle_settings: {e2}", file=sys.stderr)
    except Exception as e:
        import sys
        print(f"[WARN] Impossible de créer la table headphone_loans automatiquement : {e}", file=sys.stderr)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Register blueprints
import views
app.register_blueprint(views.bp)
import admin

# Register API blueprints
from api.trains import bp as trains_bp
app.register_blueprint(trains_bp)
app.register_blueprint(admin.bp_admin)

# --- Navette admin et API ---

from api_navette import api_navette_bp
app.register_blueprint(api_navette_bp)
import admin_shuttle
app.register_blueprint(admin_shuttle.bp)

print("DEBUG: ROUTES FLASK:")
for rule in app.url_map.iter_rules():
    print(rule, rule.endpoint)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
