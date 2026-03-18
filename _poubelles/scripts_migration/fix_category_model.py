#!/usr/bin/env python3
"""
Fix de compatibilité pour le modèle Category
Remplace le modèle actuel par une version qui gère les erreurs d'import
"""

COMPATIBLE_CATEGORY_MODEL = '''
class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    icon_class = db.Column(db.String(50), nullable=True)  # Classe Bootstrap Icon (ex: 'bi-wallet')

    def __repr__(self):
        return f'<Category {self.name}>'

    @property
    def icon_bootstrap_class(self):
        """Retourne la classe Bootstrap Icon pour cette catégorie."""
        if self.icon_class:
            return self.icon_class
        
        # Auto-assignment basé sur le nom de la catégorie avec gestion d'erreur
        try:
            from category_icons import get_icon_for_category
            return get_icon_for_category(self.name)
        except ImportError:
            # Fallback si category_icons.py n'est pas disponible
            return 'bi-box-seam'
        except Exception:
            # Fallback pour toute autre erreur
            return 'bi-box-seam'
'''

print("🔧 Modèle Category compatible créé")
print("📝 Remplacez le modèle dans models.py par le contenu ci-dessus")
print("✅ Ce modèle gère les erreurs d'import et fournit un fallback")
