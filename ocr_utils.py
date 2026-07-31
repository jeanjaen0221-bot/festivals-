"""Tests purs pour la logique de réouverture des inscriptions (section B)."""
from registration_policy import compute_registration_open


def test_registration_open_during_bootstrap_before_any_admin():
    # Aucun admin n'existe encore : l'inscription doit être ouverte, quel que
    # soit le réglage explicite (qui n'a pas encore de sens tant qu'il n'y a
    # pas d'admin pour le configurer).
    assert compute_registration_open(admin_exists=False, registration_open_setting=False) is True
    assert compute_registration_open(admin_exists=False, registration_open_setting=True) is True


def test_registration_closed_by_default_once_admin_exists():
    assert compute_registration_open(admin_exists=True, registration_open_setting=False) is False


def test_registration_reopened_by_admin_toggle():
    assert compute_registration_open(admin_exists=True, registration_open_setting=True) is True
