"""Tests purs pour les primitives de réinitialisation de mot de passe."""
from datetime import timedelta
from types import SimpleNamespace

import password_reset


def _token(**overrides):
    now = password_reset.utcnow()
    base = dict(used_at=None, revoked=False, expires_at=now + timedelta(hours=1))
    base.update(overrides)
    return SimpleNamespace(**base)


def test_hash_token_is_deterministic_and_hides_the_raw_token():
    raw = 'un-token-quelconque'
    assert password_reset.hash_token(raw) == password_reset.hash_token(raw)
    assert password_reset.hash_token(raw) != raw
    assert len(password_reset.hash_token(raw)) == 64
    assert password_reset.hash_token('autre') != password_reset.hash_token(raw)


def test_generate_raw_token_is_unique_and_long_enough():
    tokens = {password_reset.generate_raw_token() for _ in range(50)}
    assert len(tokens) == 50
    assert all(len(t) >= 32 for t in tokens)


def test_expiry_is_24h_after_creation():
    now = password_reset.utcnow()
    assert password_reset.expiry_from(now) - now == timedelta(hours=password_reset.TOKEN_TTL_HOURS)
    assert password_reset.TOKEN_TTL_HOURS == 24


def test_fresh_token_is_usable():
    assert password_reset.is_usable(_token()) is True


def test_expired_token_is_not_usable():
    now = password_reset.utcnow()
    assert password_reset.is_usable(_token(expires_at=now - timedelta(seconds=1))) is False


def test_already_used_token_is_not_usable():
    # Usage unique : un lien déjà consommé ne doit plus jamais fonctionner.
    assert password_reset.is_usable(_token(used_at=password_reset.utcnow())) is False


def test_revoked_token_is_not_usable():
    # Générer un nouveau lien révoque les précédents.
    assert password_reset.is_usable(_token(revoked=True)) is False


def test_missing_token_is_not_usable():
    assert password_reset.is_usable(None) is False


def test_utcnow_is_naive_for_comparison_with_db_columns():
    assert password_reset.utcnow().tzinfo is None


# --- Identifiant de session lié au mot de passe (déconnexion de tous les appareils) ---

def test_session_id_round_trip_accepts_an_unchanged_password():
    sid = password_reset.build_session_id(42, 'scrypt:32768:8:1$abc')
    user_id, digest = password_reset.parse_session_id(sid)
    assert user_id == 42
    assert digest == password_reset.session_digest('scrypt:32768:8:1$abc')


def test_session_id_digest_changes_when_the_password_changes():
    # C'est ce qui invalide les sessions ouvertes après une réinitialisation.
    before = password_reset.build_session_id(42, 'hash-avant')
    after = password_reset.build_session_id(42, 'hash-apres')
    assert before != after
    _, digest_before = password_reset.parse_session_id(before)
    assert digest_before != password_reset.session_digest('hash-apres')


def test_legacy_numeric_session_ids_are_rejected():
    # Les sessions créées avant cette fonctionnalité doivent être refusées.
    assert password_reset.parse_session_id('42') == (None, None)


def test_malformed_session_ids_are_rejected():
    for bad in ('', None, ':', 'abc:def', '42:', ':abc'):
        assert password_reset.parse_session_id(bad) == (None, None), bad


def test_session_digest_tolerates_a_missing_password_hash():
    assert password_reset.session_digest(None) == password_reset.session_digest('')
