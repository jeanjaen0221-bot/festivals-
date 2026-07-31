"""Tests de zones.py — aucune base de données, aucune app Flask requise."""
import zones


def test_lieux_choix_starts_with_placeholder_and_ends_with_autre():
    assert zones.LIEUX_CHOIX[0][0] == ''
    assert zones.LIEUX_CHOIX[-1][0] == zones.OTHER_VALUE


def test_every_zone_value_is_unique():
    valeurs = [v for v, _ in zones.LIEUX_CHOIX]
    assert len(valeurs) == len(set(valeurs))


def test_labels_are_unique_too():
    """Deux zones de meme libelle rendraient to_form_values ambigu."""
    libelles = [l for _, l in zones.ZONES]
    assert len(libelles) == len(set(libelles))


def test_resolve_returns_the_label_not_the_value():
    """C'est le libelle qui est stocke en base et compare par le matching."""
    assert zones.resolve('camping_famille', '') == 'Camping Famille'
    assert zones.resolve('la_turbine', '') == 'La Turbine'


def test_resolve_uses_free_text_when_autre():
    assert zones.resolve('autre', '  Derriere la scene Nova ') == 'Derriere la scene Nova'


def test_resolve_keeps_free_text_when_nothing_selected():
    """Regression : l'ancien dict(choices).get(None, '') effacait la saisie."""
    assert zones.resolve('', 'Pres des douches') == 'Pres des douches'
    assert zones.resolve(None, 'Pres des douches') == 'Pres des douches'


def test_resolve_empty_is_empty():
    assert zones.resolve('', '') == ''
    assert zones.resolve(None, None) == ''


def test_to_form_values_round_trips_a_known_zone():
    for value, label in zones.ZONES:
        assert zones.to_form_values(label) == (value, '')
        assert zones.resolve(value, '') == label


def test_to_form_values_falls_back_to_autre_for_unknown_label():
    """Les declarations anterieures (texte libre) ne doivent pas etre perdues."""
    assert zones.to_form_values('Ancien lieu inconnu') == (zones.OTHER_VALUE, 'Ancien lieu inconnu')


def test_to_form_values_empty():
    assert zones.to_form_values('') == ('', '')
    assert zones.to_form_values(None) == ('', '')
