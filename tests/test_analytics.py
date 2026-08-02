"""Tests des agrégats du tableau de bord — sans base ni application Flask."""
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from analytics import (agreger_prets, affluence_prets,
                       CAUTION_ESPECES, CAUTION_CARTE_IDENTITE)

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


# ── Heures d'affluence ───────────────────────────────────────────────────────

def _pret_a(heure_utc, retour_utc=None, quantite=1):
    """Prêt dont les horodatages sont naifs et en UTC, comme en base."""
    return SimpleNamespace(
        quantity=quantite,
        deposit_type=CAUTION_CARTE_IDENTITE,
        deposit_amount=None,
        loan_date=datetime(2026, 7, 31, heure_utc, 0),
        return_date=datetime(2026, 7, 31, retour_utc, 0) if retour_utc is not None else None,
    )


def test_affluence_convertit_en_heure_locale():
    """Le coeur du sujet : 12 h UTC, c'est 14 h a Floreffe en ete. Afficher
    l'heure brute ferait placer les effectifs deux heures trop tot."""
    r = affluence_prets([_pret_a(12)])
    assert r['prets_par_heure'][14] == 1
    assert r['prets_par_heure'][12] == 0
    assert r['heure_pointe_prets'] == 14


def test_affluence_distingue_prets_et_retours():
    r = affluence_prets([_pret_a(12, retour_utc=20)])
    assert r['prets_par_heure'][14] == 1     # 12 h UTC -> 14 h locale
    assert r['retours_par_heure'][22] == 1   # 20 h UTC -> 22 h locale
    assert r['heure_pointe_prets'] == 14
    assert r['heure_pointe_retours'] == 22


def test_affluence_renvoie_toujours_24_heures():
    """L'activite d'un festival deborde apres minuit : tronquer la plage
    masquerait la nuit."""
    r = affluence_prets([_pret_a(12)])
    assert len(r['prets_par_heure']) == 24
    assert len(r['retours_par_heure']) == 24
    assert r['heures'] == list(range(24))


def test_affluence_compte_les_casques_en_plus_des_prets():
    r = affluence_prets([_pret_a(12, quantite=3)])
    assert r['prets_par_heure'][14] == 1
    assert r['casques_par_heure'][14] == 3


def test_affluence_pic_sur_l_heure_la_plus_chargee():
    r = affluence_prets([_pret_a(12), _pret_a(12), _pret_a(15)])
    assert r['heure_pointe_prets'] == 14
    assert r['max_prets_heure'] == 2


def test_affluence_sans_donnees():
    r = affluence_prets([])
    assert r['heure_pointe_prets'] is None
    assert r['heure_pointe_retours'] is None
    assert r['max_prets_heure'] == 0
    assert r['par_jour'] == []


def test_affluence_pas_de_pic_quand_aucun_retour():
    r = affluence_prets([_pret_a(12)])
    assert r['heure_pointe_retours'] is None, "aucun retour ne doit pas designer minuit"


def test_affluence_regroupe_par_journee_locale():
    """Un pret a 23 h UTC tombe le lendemain a Floreffe : c'est la journee
    locale qui compte pour le suivi."""
    tard = SimpleNamespace(quantity=2, deposit_type=CAUTION_CARTE_IDENTITE, deposit_amount=None,
                           loan_date=datetime(2026, 7, 31, 23, 0), return_date=None)
    r = affluence_prets([tard])
    assert len(r['par_jour']) == 1
    assert r['par_jour'][0]['date'].day == 1, "1er aout en heure locale"
    assert r['par_jour'][0]['casques'] == 2


def test_affluence_journees_triees():
    lignes = [_pret_a(12),
              SimpleNamespace(quantity=1, deposit_type=CAUTION_CARTE_IDENTITE, deposit_amount=None,
                              loan_date=datetime(2026, 8, 2, 10, 0), return_date=None)]
    r = affluence_prets(lignes)
    dates = [e['date'] for e in r['par_jour']]
    assert dates == sorted(dates)


def test_affluence_accepte_un_horodatage_deja_localise():
    from datetime import timezone as _tz
    aware = SimpleNamespace(quantity=1, deposit_type=CAUTION_CARTE_IDENTITE, deposit_amount=None,
                            loan_date=datetime(2026, 7, 31, 12, 0, tzinfo=_tz.utc), return_date=None)
    r = affluence_prets([aware])
    assert r['prets_par_heure'][14] == 1


def test_libelle_de_journee_en_francais():
    """strftime('%A') suit la locale du serveur, anglaise par defaut : le
    tableau affichait « Friday 31/07 » sur une interface francaise."""
    from analytics import libelle_jour
    from datetime import date
    assert libelle_jour(date(2026, 7, 31)) == 'vendredi 31/07'
    assert libelle_jour(date(2026, 8, 2)) == 'dimanche 02/08'


def test_affluence_expose_le_libelle_de_journee():
    r = affluence_prets([_pret_a(12)])
    assert r['par_jour'][0]['libelle'] == 'vendredi 31/07'
