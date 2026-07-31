"""Tests de validation d'ItemForm — pas de base de données, models est stubbé.

Ces tests couvrent une régression coûteuse : le formulaire exigeait
`reporter_name` alors qu'aucun template ne l'affichait, donc aucune déclaration
d'objet perdu ne pouvait aboutir et le bénévole voyait une erreur portant sur un
champ invisible.
"""
import sys
import types

import pytest
from flask import Flask
from werkzeug.datastructures import MultiDict


@pytest.fixture(scope='module', autouse=True)
def _stub_models():
    """Évite d'importer models (donc SQLAlchemy et la base) pour ItemForm.__init__."""
    faux = types.ModuleType('models')

    class Category:
        _rows = [types.SimpleNamespace(id=1, name='Téléphone', family='Objets personnels')]

        class query:
            @staticmethod
            def order_by(*a, **k):
                return Category.query

            @staticmethod
            def all():
                return Category._rows

    faux.Category = Category
    ancien = sys.modules.get('models')
    sys.modules['models'] = faux
    yield
    if ancien is None:
        del sys.modules['models']
    else:
        sys.modules['models'] = ancien


@pytest.fixture
def app():
    application = Flask(__name__)
    application.config.update(SECRET_KEY='test', WTF_CSRF_ENABLED=False)
    return application


BASE_PERDU = {
    'lost-title': 'Telephone noir',
    'lost-comments': 'coque transparente',
    'lost-location': 'jardin',
    'lost-category': '1',
    'lost-item_color': 'noir',
    'submit_lost': '1',
}

BASE_TROUVE = {
    'found-title': 'Telephone noir',
    'found-found_location': 'jardin',
    'found-storage_location': 'point_info',
    'found-category': '1',
    'found-item_color': 'noir',
    'submit_found': '1',
}


def _valider(app, prefix, donnees):
    from forms import ItemForm
    with app.test_request_context(method='POST', data=MultiDict(donnees)):
        form = ItemForm(prefix=prefix)
        form.category.choices = [('', '—'), (1, 'Téléphone')]
        return form.validate_on_submit(), form


def _perdu(**extra):
    donnees = dict(BASE_PERDU)
    donnees.update(extra)
    return donnees


def test_objet_perdu_avec_nom_et_telephone(app):
    ok, _ = _valider(app, 'lost', _perdu(**{
        'lost-reporter_name': 'Marie Dupont', 'lost-reporter_phone': '0470123456'}))
    assert ok


def test_objet_perdu_avec_email_seulement(app):
    """Un email suffit : on n'impose pas le telephone."""
    ok, _ = _valider(app, 'lost', _perdu(**{
        'lost-reporter_name': 'Marie Dupont', 'lost-reporter_email': 'marie@exemple.be'}))
    assert ok


def test_objet_perdu_refuse_sans_moyen_de_contact(app):
    """Retrouver l'objet ne sert a rien si on ne peut prevenir personne."""
    ok, form = _valider(app, 'lost', _perdu(**{'lost-reporter_name': 'Marie Dupont'}))
    assert not ok
    assert form.reporter_phone.errors


def test_objet_perdu_refuse_sans_nom(app):
    ok, form = _valider(app, 'lost', _perdu(**{'lost-reporter_phone': '0470123456'}))
    assert not ok
    assert form.reporter_name.errors


def test_objet_perdu_refuse_sans_lieu(app):
    donnees = _perdu(**{'lost-reporter_name': 'Marie', 'lost-reporter_phone': '0470123456'})
    donnees.pop('lost-location')
    ok, form = _valider(app, 'lost', donnees)
    assert not ok
    assert form.location.errors


def test_objet_trouve_ne_demande_pas_de_coordonnees(app):
    """Le declarant d'un objet trouve est le benevole connecte : le formulaire
    ne doit pas exiger de coordonnees."""
    ok, _ = _valider(app, 'found', BASE_TROUVE)
    assert ok


def test_objet_trouve_exige_lieu_et_stockage(app):
    for champ in ('found-found_location', 'found-storage_location'):
        donnees = dict(BASE_TROUVE)
        donnees.pop(champ)
        ok, _ = _valider(app, 'found', donnees)
        assert not ok, f"{champ} devrait etre obligatoire"


def test_le_contexte_est_bien_detecte_malgre_le_suffixe_wtforms(app):
    """WTForms normalise prefix='lost' en _prefix='lost-' : comparer a 'lost'
    rendait tout le bloc de validation inoperant."""
    from forms import ItemForm
    with app.test_request_context(method='POST', data=MultiDict(BASE_PERDU)):
        form = ItemForm(prefix='lost')
        assert form._prefix == 'lost-'
        assert form._prefix.rstrip('-_;:/.') == 'lost'
