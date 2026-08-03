"""Primitives pour les liens de réinitialisation de mot de passe générés par un admin.

Isolée dans un module sans dépendance (ni Flask, ni DB) pour rester testable sans
avoir à démarrer l'application complète.

Le token brut n'est jamais stocké : seul son SHA-256 est mis en base. Le brut n'est
affiché qu'une seule fois, à l'admin qui vient de le générer.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

TOKEN_TTL_HOURS = 24


def utcnow():
    """UTC naïf.

    Les colonnes DateTime du projet sont sans fuseau ; on écrit et on compare
    toujours avec cette même fonction pour éviter les comparaisons
    naïf/aware qui explosent sur PostgreSQL.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def generate_raw_token():
    """Token brut, imprévisible, transmis dans l'URL."""
    return secrets.token_urlsafe(32)


def hash_token(raw):
    """Empreinte stockée en base pour un token brut."""
    return hashlib.sha256((raw or '').encode()).hexdigest()


def expiry_from(now=None, ttl_hours=TOKEN_TTL_HOURS):
    """Date d'expiration d'un token créé à `now`."""
    return (now or utcnow()) + timedelta(hours=ttl_hours)


def session_digest(password_hash):
    """Empreinte du mot de passe embarquée dans l'identifiant de session.

    Voir User.get_id() et le user_loader d'app.py : si le mot de passe change,
    l'empreinte change et toutes les sessions ouvertes deviennent invalides.
    """
    return hashlib.sha256((password_hash or '').encode()).hexdigest()[:16]


def build_session_id(user_id, password_hash):
    """Identifiant Flask-Login « <id>:<empreinte> »."""
    return f"{user_id}:{session_digest(password_hash)}"


def parse_session_id(raw):
    """Décompose un identifiant de session en (user_id:int, empreinte:str).

    Retourne (None, None) si le format est invalide — notamment pour les
    sessions à l'ancien format (identifiant numérique nu), qui doivent être
    rejetées.
    """
    raw = str(raw or '')
    if ':' not in raw:
        return None, None
    id_part, _, digest = raw.partition(':')
    if not digest:
        return None, None
    try:
        return int(id_part), digest
    except (TypeError, ValueError):
        return None, None


def is_usable(token_row, now=None):
    """Un token est utilisable s'il n'a été ni utilisé, ni révoqué, et qu'il n'est pas expiré."""
    if token_row is None:
        return False
    if getattr(token_row, 'used_at', None) is not None:
        return False
    if getattr(token_row, 'revoked', False):
        return False
    expires_at = getattr(token_row, 'expires_at', None)
    if expires_at is None:
        return False
    return expires_at > (now or utcnow())
