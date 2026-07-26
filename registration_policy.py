"""Logique pure : l'inscription publique est-elle ouverte ?

Isolée dans un module sans dépendance (ni Flask, ni DB, ni torch) pour rester
testable sans avoir à démarrer l'application complète.
"""


def compute_registration_open(admin_exists: bool, registration_open_setting: bool) -> bool:
    """L'inscription publique est ouverte tant qu'aucun admin n'existe (amorçage),
    ou si un admin l'a explicitement rouverte depuis /admin/users."""
    return (not admin_exists) or bool(registration_open_setting)
