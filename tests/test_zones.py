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


# ── Lieux de stockage : liste volontairement fermée ──────────────────────────

def test_il_y_a_exactement_trois_lieux_de_stockage():
    """Un objet n'est entrepose qu'a ces trois endroits : c'est la que les
    benevoles vont le chercher. Elargir cette liste sans le decider rendrait
    des objets introuvables."""
    assert len(zones.STOCKAGE) == 3
    assert [libelle for _, libelle in zones.STOCKAGE] == [
        'Festival', 'Camping Famille', 'Camping Festif']


def test_pas_d_option_autre_pour_le_stockage():
    valeurs = [v for v, _ in zones.STOCKAGE_CHOIX]
    assert zones.OTHER_VALUE not in valeurs
    assert valeurs[0] == '', "un choix vide doit forcer une selection explicite"


def test_le_stockage_ne_reprend_pas_les_zones_du_site():
    """Les 12 zones servent a dire OU l'objet a ete perdu ou trouve, pas ou il
    est range : les deux listes ne doivent pas etre confondues."""
    zones_site = {v for v, _ in zones.ZONES}
    stockage = {v for v, _ in zones.STOCKAGE}
    assert 'la_turbine' in zones_site and 'la_turbine' not in stockage
    assert len(stockage) < len(zones_site)


def test_resolve_stockage_renvoie_le_libelle():
    assert zones.resolve_stockage('camping_festif') == 'Camping Festif'
    assert zones.resolve_stockage('festival') == 'Festival'


def test_resolve_stockage_rejette_hors_liste():
    for valeur in ('autre', 'point_info', 'la_turbine', '', None):
        assert zones.resolve_stockage(valeur) == ''


def test_stockage_aller_retour():
    for valeur, libelle in zones.STOCKAGE:
        assert zones.stockage_to_form_value(libelle) == valeur
        assert zones.resolve_stockage(valeur) == libelle


def test_ancien_libelle_de_stockage_laisse_le_select_vide():
    """Les declarations anterieures a la fermeture de la liste ne doivent pas
    preselectionner un lieu invalide : le select reste vide et la validation
    obligera a en choisir un."""
    assert zones.stockage_to_form_value('Point Info Festival') == ''
    assert zones.stockage_to_form_value('') == ''
    assert zones.stockage_to_form_value(None) == ''
