import os
import sys
from datetime import datetime, timedelta
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import sqlalchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
raw_url = (os.environ.get('DATABASE_URL') or os.environ.get('DATABASE_PUBLIC_URL') or '').strip()
if raw_url.startswith('postgres://'):
    raw_url = 'postgresql://' + raw_url[len('postgres://'):]
if raw_url.startswith('postgresql://') and '+psycopg' not in raw_url and '+psycopg2' not in raw_url:
    raw_url = 'postgresql+psycopg://' + raw_url[len('postgresql://'):]
if 'sslmode=' not in raw_url:
    raw_url = f"{raw_url}{'&' if '?' in raw_url else '?'}sslmode=require"
app.config['SQLALCHEMY_DATABASE_URI'] = raw_url
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', '300')),
    'pool_size': int(os.environ.get('DB_POOL_SIZE', '5')),
    'max_overflow': int(os.environ.get('DB_MAX_OVERFLOW', '5')),
    'pool_timeout': int(os.environ.get('DB_POOL_TIMEOUT', '30')),
    'connect_args': {'sslmode': 'require'},
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Sécurité : forcer la présence de secrets en production
if not app.config['SECRET_KEY'] or app.config['SECRET_KEY'] == 'change_this_in_prod':
    raise RuntimeError('SECRET_KEY doit être défini dans les variables d\'environnement !')
if not app.config['SQLALCHEMY_DATABASE_URI'] or 'user:pass@localhost' in app.config['SQLALCHEMY_DATABASE_URI']:
    raise RuntimeError('DATABASE_URL PostgreSQL doit être défini dans les variables d\'environnement Railway !')

# Cookies de session sécurisés
app.config['SESSION_COOKIE_SECURE'] = not app.debug
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Durée de vie des sessions et des tokens CSRF
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
app.config['WTF_CSRF_TIME_LIMIT'] = 3600

# Headers HTTP de sécurité
@app.after_request
def set_security_headers(response):
    response.headers['Strict-Transport-Security'] = 'max-age=63072000; includeSubDomains; preload'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), usb=(), payment=(), geolocation=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
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
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["300 per minute"],
    storage_uri="memory://",
)

@app.context_processor
def inject_current_year():
    return {'current_year': datetime.utcnow().year}

@app.context_processor
def inject_unread_count():
    from flask_login import current_user
    try:
        if current_user.is_authenticated:
            from messaging import total_unread
            return {'unread_msg_count': total_unread(current_user.id)}
    except Exception:
        pass
    return {'unread_msg_count': 0}

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
            # Ajoute id_card_photo si manquant
            result = conn.execute(sqlalchemy.text("""
                SELECT column_name FROM information_schema.columns WHERE table_name='headphone_loans' AND column_name='id_card_photo'
            """))
            if result.fetchone() is None:
                conn.execute(sqlalchemy.text("ALTER TABLE headphone_loans ADD COLUMN id_card_photo TEXT;"))
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
                # display_direction
                result = conn.execute(sqlalchemy.text("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name='shuttle_settings' AND column_name='display_direction'
                """))
                if result.fetchone() is None:
                    conn.execute(sqlalchemy.text("ALTER TABLE shuttle_settings ADD COLUMN display_direction VARCHAR(10) NOT NULL DEFAULT 'forward';"))
                    conn.execute(sqlalchemy.text("COMMIT;"))
                # display_base_stop_sequence
                result = conn.execute(sqlalchemy.text("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name='shuttle_settings' AND column_name='display_base_stop_sequence'
                """))
                if result.fetchone() is None:
                    conn.execute(sqlalchemy.text("ALTER TABLE shuttle_settings ADD COLUMN display_base_stop_sequence INTEGER NULL;"))
                    conn.execute(sqlalchemy.text("COMMIT;"))
                # updated_at
                result = conn.execute(sqlalchemy.text("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name='shuttle_settings' AND column_name='updated_at'
                """))
                if result.fetchone() is None:
                    conn.execute(sqlalchemy.text("ALTER TABLE shuttle_settings ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT NOW();"))
                    conn.execute(sqlalchemy.text("COMMIT;"))
            except Exception as e2:
                print(f"[WARN] Impossible d'ajouter les colonnes shuttle_settings: {e2}", file=sys.stderr)
            # --- Ensure products.image_filename exists (Goodies images) ---
            try:
                result = conn.execute(sqlalchemy.text("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name='products' AND column_name='image_filename'
                """))
                if result.fetchone() is None:
                    conn.execute(sqlalchemy.text("ALTER TABLE products ADD COLUMN image_filename VARCHAR(200);"))
                    conn.execute(sqlalchemy.text("COMMIT;"))
            except Exception as e3:
                print(f"[WARN] Impossible d'ajouter la colonne products.image_filename: {e3}", file=sys.stderr)

            # --- Ensure products image columns exist (DB-backed images) ---
            try:
                for col, ddl in [
                    ('image_data', 'ALTER TABLE products ADD COLUMN image_data BYTEA;'),
                    ('image_mime_type', 'ALTER TABLE products ADD COLUMN image_mime_type VARCHAR(100);'),
                    ('image_original_filename', 'ALTER TABLE products ADD COLUMN image_original_filename VARCHAR(200);'),
                ]:
                    result = conn.execute(sqlalchemy.text(f"""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name='products' AND column_name='{col}'
                    """))
                    if result.fetchone() is None:
                        conn.execute(sqlalchemy.text(ddl))
                        conn.execute(sqlalchemy.text("COMMIT;"))
            except Exception as e4:
                print(f"[WARN] Impossible d'ajouter les colonnes image_* sur products: {e4}", file=sys.stderr)

            # --- Ensure items photo columns exist (DB-backed images) ---
            try:
                for col, ddl in [
                    ('photo_data', 'ALTER TABLE items ADD COLUMN photo_data BYTEA;'),
                    ('photo_mime_type', 'ALTER TABLE items ADD COLUMN photo_mime_type VARCHAR(100);'),
                    ('photo_original_filename', 'ALTER TABLE items ADD COLUMN photo_original_filename VARCHAR(200);'),
                    ('return_photo_data', 'ALTER TABLE items ADD COLUMN return_photo_data BYTEA;'),
                    ('return_photo_mime_type', 'ALTER TABLE items ADD COLUMN return_photo_mime_type VARCHAR(100);'),
                    ('return_photo_original_filename', 'ALTER TABLE items ADD COLUMN return_photo_original_filename VARCHAR(200);'),
                ]:
                    result = conn.execute(sqlalchemy.text(f"""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name='items' AND column_name='{col}'
                    """))
                    if result.fetchone() is None:
                        conn.execute(sqlalchemy.text(ddl))
                        conn.execute(sqlalchemy.text("COMMIT;"))
            except Exception as e5:
                print(f"[WARN] Impossible d'ajouter les colonnes photo_* sur items: {e5}", file=sys.stderr)

            # --- Ensure item_photos data columns exist (DB-backed images) ---
            try:
                for col, ddl in [
                    ('data', 'ALTER TABLE item_photos ADD COLUMN data BYTEA;'),
                    ('mime_type', 'ALTER TABLE item_photos ADD COLUMN mime_type VARCHAR(100);'),
                    ('original_filename', 'ALTER TABLE item_photos ADD COLUMN original_filename VARCHAR(200);'),
                ]:
                    result = conn.execute(sqlalchemy.text(f"""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name='item_photos' AND column_name='{col}'
                    """))
                    if result.fetchone() is None:
                        conn.execute(sqlalchemy.text(ddl))
                        conn.execute(sqlalchemy.text("COMMIT;"))
            except Exception as e6:
                print(f"[WARN] Impossible d'ajouter les colonnes data/mime_type sur item_photos: {e6}", file=sys.stderr)

            # --- Messagerie interne : enum types + tables ---
            try:
                # Types enum PostgreSQL (idempotents)
                conn.execute(sqlalchemy.text("""
                    DO $$ BEGIN
                        CREATE TYPE convtype AS ENUM ('direct', 'group');
                    EXCEPTION WHEN duplicate_object THEN null;
                    END $$;
                """))
                conn.execute(sqlalchemy.text("""
                    DO $$ BEGIN
                        CREATE TYPE participantrole AS ENUM ('member', 'admin');
                    EXCEPTION WHEN duplicate_object THEN null;
                    END $$;
                """))
                conn.execute(sqlalchemy.text("COMMIT;"))

                # Table conversations
                conn.execute(sqlalchemy.text("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id SERIAL PRIMARY KEY,
                        type convtype NOT NULL DEFAULT 'direct',
                        name VARCHAR(120),
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        created_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        is_archived BOOLEAN NOT NULL DEFAULT FALSE
                    );
                """))
                conn.execute(sqlalchemy.text("COMMIT;"))

                # Table conversation_participants
                conn.execute(sqlalchemy.text("""
                    CREATE TABLE IF NOT EXISTS conversation_participants (
                        id SERIAL PRIMARY KEY,
                        conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        role participantrole NOT NULL DEFAULT 'member',
                        joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        last_read_at TIMESTAMP
                    );
                """))
                conn.execute(sqlalchemy.text(
                    "CREATE INDEX IF NOT EXISTS ix_cp_conv ON conversation_participants(conversation_id);"
                ))
                conn.execute(sqlalchemy.text(
                    "CREATE INDEX IF NOT EXISTS ix_cp_user ON conversation_participants(user_id);"
                ))
                conn.execute(sqlalchemy.text("COMMIT;"))

                # Table messages
                conn.execute(sqlalchemy.text("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id SERIAL PRIMARY KEY,
                        conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                        sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        body TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                        pinned BOOLEAN NOT NULL DEFAULT FALSE,
                        pinned_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL
                    );
                """))
                conn.execute(sqlalchemy.text(
                    "CREATE INDEX IF NOT EXISTS ix_msg_conv ON messages(conversation_id);"
                ))
                conn.execute(sqlalchemy.text(
                    "CREATE INDEX IF NOT EXISTS ix_msg_sender ON messages(sender_id);"
                ))
                conn.execute(sqlalchemy.text(
                    "CREATE INDEX IF NOT EXISTS ix_msg_created ON messages(created_at);"
                ))
                conn.execute(sqlalchemy.text("COMMIT;"))
                print("[INFO] Tables messagerie vérifiées/créées avec succès.", file=sys.stderr)
            except Exception as e_msg:
                print(f"[WARN] Impossible de créer les tables messagerie : {e_msg}", file=sys.stderr)

    except Exception as e:
        print(f"[WARN] Impossible de créer la table headphone_loans automatiquement : {e}", file=sys.stderr)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

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

import messaging
app.register_blueprint(messaging.bp_msg)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
