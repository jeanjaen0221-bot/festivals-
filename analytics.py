"""Agrégats du tableau de bord, sans dépendance à Flask ni à la base.

Isolé volontairement : `admin.py` importe l'application, donc rien de ce qui y
vit ne peut être testé sans une base de données. Le calcul est ici pur — il
reçoit des lignes et rend des chiffres — et couvert par des tests.

Le type de caution est comparé sur sa valeur textuelle ('cash', 'id_card')
plutôt que sur l'énumération, pour que ce module reste indépendant de models.py.
"""
from datetime import timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

CAUTION_ESPECES = 'cash'
CAUTION_CARTE_IDENTITE = 'id_card'

# Les dates sont enregistrées en heure serveur (UTC) : affichées telles quelles,
# les heures d'affluence seraient décalées de deux heures en été et mèneraient à
# de mauvaises décisions d'effectifs. Même conversion que les rapports Z.
FUSEAU_FESTIVAL = 'Europe/Brussels'

# Noms de jours explicites plutôt que strftime('%A') : celui-ci suit la locale
# du serveur, qui est l'anglais par défaut sur Railway. Changer la locale du
# processus pour un libellé serait disproportionné et non thread-safe.
JOURS_FR = ('lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche')


def libelle_jour(date_locale) -> str:
    return f"{JOURS_FR[date_locale.weekday()]} {date_locale.strftime('%d/%m')}"


def _fuseau(nom):
    try:
        return ZoneInfo(nom)
    except Exception:
        # Base de fuseaux absente : mieux vaut des heures en UTC que pas de
        # statistiques du tout, l'appelant est prévenu par la clé 'fuseau'.
        return timezone.utc


def _en_heure_locale(valeur, tz):
    if valeur is None:
        return None
    if valeur.tzinfo is None:
        valeur = valeur.replace(tzinfo=timezone.utc)
    return valeur.astimezone(tz)


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


def affluence_prets(lignes, nom_fuseau=FUSEAU_FESTIVAL) -> dict:
    """Répartition des prêts et des retours dans le temps, en heure locale.

    Sert à placer les effectifs : le pic de prêts et le pic de retours ne
    tombent pas au même moment, et le second arrive souvent tard le soir.

    Les 24 heures sont toujours renvoyées, y compris vides : l'activité d'un
    festival déborde après minuit, et tronquer la plage masquerait la nuit.
    """
    tz = _fuseau(nom_fuseau)
    prets_par_heure = [0] * 24
    retours_par_heure = [0] * 24
    casques_par_heure = [0] * 24
    par_jour = {}

    def jour(date_locale):
        return par_jour.setdefault(date_locale, {
            'date': date_locale, 'libelle': libelle_jour(date_locale),
            'prets': 0, 'retours': 0, 'casques': 0})

    for ligne in lignes:
        quantite = int(getattr(ligne, 'quantity', 1) or 1)
        pris = _en_heure_locale(getattr(ligne, 'loan_date', None), tz)
        if pris:
            prets_par_heure[pris.hour] += 1
            casques_par_heure[pris.hour] += quantite
            entree = jour(pris.date())
            entree['prets'] += 1
            entree['casques'] += quantite
        rendu = _en_heure_locale(getattr(ligne, 'return_date', None), tz)
        if rendu:
            retours_par_heure[rendu.hour] += 1
            jour(rendu.date())['retours'] += 1

    def pointe(serie):
        maximum = max(serie) if serie else 0
        return serie.index(maximum) if maximum else None

    return {
        'heures':             list(range(24)),
        'prets_par_heure':    prets_par_heure,
        'retours_par_heure':  retours_par_heure,
        'casques_par_heure':  casques_par_heure,
        'heure_pointe_prets': pointe(prets_par_heure),
        'heure_pointe_retours': pointe(retours_par_heure),
        'max_prets_heure':    max(prets_par_heure) if prets_par_heure else 0,
        'max_retours_heure':  max(retours_par_heure) if retours_par_heure else 0,
        'par_jour':           sorted(par_jour.values(), key=lambda e: e['date']),
        'fuseau':             nom_fuseau if _fuseau(nom_fuseau) is not timezone.utc else 'UTC',
    }
