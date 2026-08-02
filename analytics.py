"""Agrégats du tableau de bord, sans dépendance à Flask ni à la base.

Isolé volontairement : `admin.py` importe l'application, donc rien de ce qui y
vit ne peut être testé sans une base de données. Le calcul est ici pur — il
reçoit des lignes et rend des chiffres — et couvert par des tests.

Le type de caution est comparé sur sa valeur textuelle ('cash', 'id_card')
plutôt que sur l'énumération, pour que ce module reste indépendant de models.py.
"""
from decimal import Decimal

CAUTION_ESPECES = 'cash'
CAUTION_CARTE_IDENTITE = 'id_card'


def _type_caution(ligne) -> str:
    """Valeur textuelle du type de caution, que ce soit un enum ou une chaîne."""
    brut = getattr(ligne, 'deposit_type', None)
    return getattr(brut, 'value', brut) or ''


def agreger_prets(lignes) -> dict:
    """Chiffres clés des prêts de casques.

    Deux d'entre eux engagent la responsabilité de l'organisation et doivent
    pouvoir être vérifiés à tout moment : le montant des cautions en espèces
    détenues, qui doit correspondre à la caisse, et le nombre de cartes
    d'identité conservées, qui doivent toutes être rendues avant la fermeture.

    `lignes` : itérable d'objets exposant quantity, deposit_type,
    deposit_amount, loan_date et return_date. Les prêts supprimés doivent avoir
    été écartés en amont : ils ne représentent plus un engagement.
    """
    lignes = list(lignes)
    en_cours = [l for l in lignes if l.return_date is None]
    rendus = [l for l in lignes if l.return_date is not None]

    def quantite(ensemble):
        return sum(int(l.quantity or 1) for l in ensemble)

    especes = Decimal('0')
    for l in en_cours:
        if _type_caution(l) == CAUTION_ESPECES and l.deposit_amount:
            especes += Decimal(str(l.deposit_amount))

    durees = [(l.return_date - l.loan_date).total_seconds() / 60
              for l in rendus if l.return_date and l.loan_date]
    duree_moyenne = round(sum(durees) / len(durees)) if durees else None

    total = len(lignes)
    return {
        'casques_dehors':        quantite(en_cours),
        'casques_total':         quantite(lignes),
        'prets_en_cours':        len(en_cours),
        'prets_rendus':          len(rendus),
        'prets_total':           total,
        'taux_retour':           round(100 * len(rendus) / total) if total else 0,
        'especes_detenues':      especes,
        'cartes_detenues':       sum(1 for l in en_cours
                                     if _type_caution(l) == CAUTION_CARTE_IDENTITE),
        'caution_ci_total':      sum(1 for l in lignes
                                     if _type_caution(l) == CAUTION_CARTE_IDENTITE),
        'caution_especes_total': sum(1 for l in lignes
                                     if _type_caution(l) == CAUTION_ESPECES),
        'duree_moyenne_min':     duree_moyenne,
    }
