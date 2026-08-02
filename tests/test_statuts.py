"""Tests de la restauration de statut après refus de suppression.

Régression coûteuse : le repli renvoyait systématiquement « perdu », donc un
objet trouvé dont la suppression était refusée réapparaissait dans la liste des
perdus. Les bénévoles le cherchaient dans les objets trouvés sans le voir.
"""
from datetime import datetime
from types import SimpleNamespace

from statuts import (deduire_statut_initial, statut_apres_refus,
                     PERDU, TROUVE, RENDU)


def objet(**champs):
    base = dict(previous_status=None, return_date=None, location='',
                found_location='', storage_location='')
    base.update(champs)
    return SimpleNamespace(**base)


# ── Déduction à partir des champs de l'objet ─────────────────────────────────

def test_un_lieu_de_decouverte_signale_un_objet_trouve():
    assert deduire_statut_initial(objet(found_location='Jardin')) == TROUVE


def test_un_lieu_de_stockage_signale_un_objet_trouve():
    """storage_location n'est renseigne que par le formulaire objet trouve."""
    assert deduire_statut_initial(objet(storage_location='Festival')) == TROUVE


def test_une_date_de_restitution_signale_un_objet_rendu():
    assert deduire_statut_initial(
        objet(return_date=datetime(2026, 8, 1, 12, 0), found_location='Jardin')) == RENDU


def test_un_lieu_de_perte_seul_signale_un_objet_perdu():
    assert deduire_statut_initial(objet(location='Camping Famille')) == PERDU


def test_objet_sans_aucun_lieu_retombe_sur_perdu():
    assert deduire_statut_initial(objet()) == PERDU


def test_les_chaines_vides_ne_comptent_pas():
    """Un found_location vide ne doit pas faire passer l'objet pour trouve."""
    assert deduire_statut_initial(objet(found_location='   ')) == PERDU


# ── Statut appliqué au refus ─────────────────────────────────────────────────

def test_le_statut_memorise_est_prioritaire():
    assert statut_apres_refus(objet(previous_status='found')) == TROUVE
    assert statut_apres_refus(objet(previous_status='lost')) == PERDU
    assert statut_apres_refus(objet(previous_status='returned')) == RENDU


def test_accepte_un_enum_comme_statut_memorise():
    """En production previous_status est une enum SQLAlchemy."""
    enum_trouve = SimpleNamespace(value='found')
    assert statut_apres_refus(objet(previous_status=enum_trouve)) == TROUVE


def test_sans_statut_memorise_on_deduit_au_lieu_de_supposer_perdu():
    """Le coeur du correctif : un objet trouve doit revenir chez les trouves."""
    assert statut_apres_refus(objet(found_location='Nova')) == TROUVE
    assert statut_apres_refus(objet(storage_location='Camping Festif')) == TROUVE


def test_un_statut_memorise_incoherent_est_ignore():
    """Si pending_deletion a ete reenregistre sur lui-meme, le reappliquer
    laisserait l'objet invisible malgre le refus."""
    assert statut_apres_refus(
        objet(previous_status='pending_deletion', found_location='Bazar')) == TROUVE


def test_un_statut_memorise_inconnu_est_ignore():
    assert statut_apres_refus(objet(previous_status='n_importe_quoi')) == PERDU


def test_les_valeurs_correspondent_au_modele():
    """Ces chaines doivent rester alignees sur models.Status, l'appelant fait
    Status(valeur) et une divergence leverait une exception au refus."""
    import re, io
    src = io.open('models.py', encoding='utf-8').read()
    bloc = re.search(r'class Status\(enum\.Enum\):(.*?)\n\nclass', src, re.S).group(1)
    valeurs = set(re.findall(r"=\s*'([a-z_]+)'", bloc))
    for attendu in (PERDU, TROUVE, RENDU):
        assert attendu in valeurs, f"{attendu} absent de models.Status"
