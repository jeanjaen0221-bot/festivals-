"""Tests des agrégats du tableau de bord — sans base ni application Flask."""
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from analytics import agreger_prets, CAUTION_ESPECES, CAUTION_CARTE_IDENTITE

DEPART = datetime(2026, 7, 31, 14, 0)


def pret(quantite=1, caution=CAUTION_CARTE_IDENTITE, montant=None,
         minutes_avant=60, rendu_apres=None):
    """Un prêt ; rendu_apres=None signifie « toujours dehors »."""
    prete_a = DEPART - timedelta(minutes=minutes_avant)
    return SimpleNamespace(
        quantity=quantite,
        deposit_type=caution,
        deposit_amount=montant,
        loan_date=prete_a,
        return_date=prete_a + timedelta(minutes=rendu_apres) if rendu_apres is not None else None,
    )


def test_corpus_vide():
    r = agreger_prets([])
    assert r['casques_dehors'] == 0
    assert r['prets_total'] == 0
    assert r['taux_retour'] == 0, "aucune division par zero"
    assert r['especes_detenues'] == Decimal('0')
    assert r['duree_moyenne_min'] is None


def test_casques_dehors_compte_les_quantites_pas_les_prets():
    """Un prêt de 4 casques, c'est 4 casques dehors : c'est le nombre d'objets
    physiques qui doit revenir, pas le nombre de lignes."""
    r = agreger_prets([pret(quantite=4), pret(quantite=2)])
    assert r['prets_en_cours'] == 2
    assert r['casques_dehors'] == 6


def test_un_pret_rendu_ne_compte_plus_comme_dehors():
    r = agreger_prets([pret(quantite=3, rendu_apres=30), pret(quantite=1)])
    assert r['casques_dehors'] == 1
    assert r['casques_total'] == 4
    assert r['prets_rendus'] == 1


def test_especes_detenues_ne_somme_que_les_prets_en_cours():
    """C'est le montant a rendre : une caution deja restituee ne doit plus y
    figurer, sinon le compte ne tombe jamais juste avec la caisse."""
    r = agreger_prets([
        pret(caution=CAUTION_ESPECES, montant=Decimal('20.00')),
        pret(caution=CAUTION_ESPECES, montant=Decimal('15.50')),
        pret(caution=CAUTION_ESPECES, montant=Decimal('50.00'), rendu_apres=90),
    ])
    assert r['especes_detenues'] == Decimal('35.50')
    assert r['caution_especes_total'] == 3


def test_une_caution_carte_identite_n_ajoute_pas_d_especes():
    r = agreger_prets([pret(caution=CAUTION_CARTE_IDENTITE, montant=Decimal('99'))])
    assert r['especes_detenues'] == Decimal('0')


def test_cartes_identite_detenues():
    r = agreger_prets([
        pret(caution=CAUTION_CARTE_IDENTITE),
        pret(caution=CAUTION_CARTE_IDENTITE),
        pret(caution=CAUTION_CARTE_IDENTITE, rendu_apres=45),
        pret(caution=CAUTION_ESPECES, montant=Decimal('10')),
    ])
    assert r['cartes_detenues'] == 2, "seules celles encore detenues"
    assert r['caution_ci_total'] == 3


def test_taux_de_retour():
    r = agreger_prets([pret(rendu_apres=10), pret(rendu_apres=10), pret(), pret()])
    assert r['taux_retour'] == 50


def test_duree_moyenne_ignore_les_prets_en_cours():
    r = agreger_prets([pret(rendu_apres=30), pret(rendu_apres=90), pret()])
    assert r['duree_moyenne_min'] == 60


def test_quantite_absente_vaut_un():
    r = agreger_prets([pret(quantite=None)])
    assert r['casques_dehors'] == 1


def test_accepte_un_enum_comme_type_de_caution():
    """En production deposit_type est une enum SQLAlchemy, pas une chaine."""
    enum_especes = SimpleNamespace(value='cash')
    r = agreger_prets([pret(caution=enum_especes, montant=Decimal('25'))])
    assert r['especes_detenues'] == Decimal('25')
    assert r['caution_especes_total'] == 1


def test_montant_en_flottant_reste_exact():
    """deposit_amount arrive parfois en float selon le pilote : le passage par
    str evite d'accumuler une erreur binaire sur un montant en euros."""
    r = agreger_prets([
        pret(caution=CAUTION_ESPECES, montant=10.10),
        pret(caution=CAUTION_ESPECES, montant=20.20),
    ])
    assert r['especes_detenues'] == Decimal('30.30')
