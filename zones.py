"""Zones du site — source unique pour les formulaires et le matching.

D'après le plan officiel Esperanzah! (Abbaye de Floreffe).

Pourquoi une liste partagée : le lieu pèse 20 % du score de correspondance, mais
il ne vaut ce poids que si les deux côtés parlent le même vocabulaire. Tant que
l'objet perdu se déclarait via une liste et l'objet trouvé en texte libre, les
deux chaînes ne pouvaient quasiment jamais coïncider et le champ était du poids
mort. Perdu et trouvé utilisent donc désormais exactement ces libellés.

Pour modifier les zones : éditer ZONES ci-dessous, rien d'autre. Les libellés
sont ce qui est stocké en base (`items.location` / `items.found_location`), donc
renommer une zone ne réécrit pas l'historique — les anciennes déclarations
gardent leur ancien libellé et resteront comparées en texte flou.
"""

# (valeur technique, libellé affiché ET stocké en base)
ZONES = [
    ('jardin',              'Jardin'),
    ('nova',                'Nova'),
    ('kokako',              'Kokako'),
    ('la_turbine',          'La Turbine'),
    ('la_rugissante',       'La Rugissante'),
    ('la_chaude_piste',     'La Chaude Piste'),
    ('bazar',               'Bazar'),
    ('comptoir_saveurs',    'Comptoir des Saveurs'),
    ('village_possibles',   'Village des Possibles'),
    ('village_enfants',     'Village des Enfants'),
    ('camping_festif',      'Camping Festif'),
    ('camping_famille',     'Camping Famille'),
    # Absent du plan mais indispensable : c'est là que les objets sont remis et
    # stockés, donc un lieu de découverte et de stockage à part entière.
    ('point_info',          'Point Info'),
]

OTHER_VALUE = 'autre'
OTHER_LABEL = 'Autre (précisez)'

# Utilisé tel quel par les SelectField de ItemForm.
LIEUX_CHOIX = [('', 'Sélectionnez un lieu')] + ZONES + [(OTHER_VALUE, OTHER_LABEL)]

ZONE_LABELS = dict(LIEUX_CHOIX)


_LABEL_TO_VALUE = {label: value for value, label in ZONES}


def to_form_values(stored_label: str) -> tuple[str, str]:
    """Inverse de :func:`resolve` : (valeur du select, contenu du champ « autre »).

    Nécessaire pour préremplir le formulaire d'édition, qui relit un libellé
    stocké en base. Un libellé hors liste (ancienne déclaration, saisie libre)
    bascule sur « Autre » avec le texte conservé, au lieu d'être perdu.
    """
    stored_label = (stored_label or '').strip()
    if not stored_label:
        return '', ''
    value = _LABEL_TO_VALUE.get(stored_label)
    if value:
        return value, ''
    return OTHER_VALUE, stored_label


def resolve(select_value: str, other_value: str) -> str:
    """Retourne le libellé à stocker pour un couple (select, champ « autre »).

    Centralisé parce que cette résolution était dupliquée à quatre endroits de
    views.py et qu'une des copies était fausse : elle appelait
    ``dict(choices).get(None, '')`` sur un select jamais rendu par le template,
    ce qui effaçait silencieusement le lieu saisi par le bénévole.
    """
    other_value = (other_value or '').strip()
    if select_value == OTHER_VALUE:
        return other_value
    if not select_value:
        # Pas de zone choisie : on garde tout de même une éventuelle saisie libre
        # plutôt que de perdre l'information.
        return other_value
    return ZONE_LABELS.get(select_value, '') or other_value
