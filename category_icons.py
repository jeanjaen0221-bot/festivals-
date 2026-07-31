# Mapping des catégories vers les icônes Bootstrap Icons
# Utilisé pour assigner automatiquement des icônes aux catégories

CATEGORY_ICON_MAP = {
    # Objets personnels
    'Portefeuille': 'bi-wallet2',
    'Porte-monnaie': 'bi-wallet',
    'Téléphone': 'bi-phone',
    'Trousseau': 'bi-key',
    'Clés': 'bi-key-fill',
    'Badge d\'accès': 'bi-credit-card-2-front',
    'Carte d\'identité': 'bi-person-vcard',
    
    # Bijoux et accessoires
    'Bague': 'bi-gem',
    'Montre': 'bi-smartwatch',
    'Lunettes': 'bi-eyeglasses',
    'Collier': 'bi-heart',
    'Bracelet': 'bi-circle',
    
    # Vêtements
    'T-shirt': 'bi-person',
    'Sweat': 'bi-person-fill',
    'Pull': 'bi-person-fill',
    'Veste': 'bi-person-arms-up',
    'Pantalon': 'bi-person-standing',
    'Chaussures': 'bi-shoe-print',
    'Casquette': 'bi-cap',
    'Chapeau': 'bi-circle-fill',
    
    # Électronique
    'Batterie externe': 'bi-battery-charging',
    'Chargeur': 'bi-plug',
    'Écouteurs': 'bi-headphones',
    'Appareil auditif': 'bi-ear',
    'Tablette': 'bi-tablet',
    'Ordinateur portable': 'bi-laptop',
    'Appareil photo': 'bi-camera',
    
    # Objets divers
    'Sac': 'bi-bag',
    'Banane': 'bi-apple',
    'Tapis de sol': 'bi-square',
    'Parapluie': 'bi-umbrella',
    'Livre': 'bi-book',
    'Cahier': 'bi-journal',
    'Stylo': 'bi-pen',
    'Bouteille': 'bi-cup-straw',
}

# Icône par défaut si aucune correspondance trouvée
DEFAULT_ICON = 'bi-box-seam'

def get_icon_for_category(category_name):
    """
    Retourne la classe d'icône Bootstrap pour une catégorie donnée.
    
    Args:
        category_name (str): Nom de la catégorie
        
    Returns:
        str: Classe CSS de l'icône Bootstrap (ex: 'bi-wallet')
    """
    if not category_name:
        return DEFAULT_ICON
    
    # Recherche exacte
    if category_name in CATEGORY_ICON_MAP:
        return CATEGORY_ICON_MAP[category_name]
    
    # Recherche insensible à la casse
    for cat_name, icon_class in CATEGORY_ICON_MAP.items():
        if cat_name.lower() == category_name.lower():
            return icon_class
    
    # Recherche partielle (contient le mot)
    category_lower = category_name.lower()
    for cat_name, icon_class in CATEGORY_ICON_MAP.items():
        if any(word in category_lower for word in cat_name.lower().split()):
            return icon_class
    
    return DEFAULT_ICON
