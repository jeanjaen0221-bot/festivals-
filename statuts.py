"""Déduction du statut d'origine d'un objet, sans dépendance à Flask ni à la base.

Sert au refus d'une demande de suppression : l'objet doit retrouver la liste
d'où il vient. Le statut mémorisé (`items.previous_status`) est la source la
plus fiable, mais il peut manquer — colonne absente d'une base ancienne, ou
demande enregistrée avant que cette mémorisation n'existe. Le repli historique
renvoyait alors systématiquement « perdu », si bien qu'un objet trouvé
réapparaissait dans la mauvaise liste et restait introuvable pour les bénévoles.

Les valeurs retournées correspondent à models.Status ; l'appelant fait la
conversion, ce qui garde ce module indépendant.
"""

PERDU = 'lost'
TROUVE = 'found'
RENDU = 'returned'


def _rempli(valeur) -> bool:
    return bool((valeur or '').strip()) if isinstance(valeur, str) else bool(valeur)


def deduire_statut_initial(item) -> str:
    """Devine d'où vient l'objet à partir des champs qu'il porte lui-même.

    * une date de restitution ⇒ il avait été rendu ;
    * un lieu de découverte ou de stockage ⇒ il avait été trouvé, ces deux
      champs n'étant renseignés que par le formulaire « objet trouvé » ;
    * sinon ⇒ perdu, le cas restant.
    """
    if _rempli(getattr(item, 'return_date', None)):
        return RENDU
    if (_rempli(getattr(item, 'found_location', None))
            or _rempli(getattr(item, 'storage_location', None))):
        return TROUVE
    return PERDU


def statut_apres_refus(item) -> str:
    """Statut à réappliquer quand une demande de suppression est refusée.

    Privilégie le statut mémorisé, en ignorant une valeur incohérente
    ('pending_deletion' réenregistré sur lui-même) qui laisserait l'objet
    invisible malgré le refus.
    """
    memorise = getattr(item, 'previous_status', None)
    valeur = getattr(memorise, 'value', memorise)
    if valeur in (PERDU, TROUVE, RENDU):
        return valeur
    return deduire_statut_initial(item)
