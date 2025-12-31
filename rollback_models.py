#!/usr/bin/env python3
"""
Script de rollback temporaire pour restaurer l'ancien système d'icônes
en cas de problème sur Railway.
"""

# Sauvegarde du modèle Category original
ORIGINAL_CATEGORY_MODEL = '''
class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    icon_data = db.Column(db.LargeBinary, nullable=True)  # Données binaire de l'icône
    icon_mime_type = db.Column(db.String(32), nullable=True)  # Type MIME de l'icône

    def __repr__(self):
        return f'<Category {self.name}>'

    @property
    def icon_url(self):
        from flask import url_for, current_app
        import os
        if self.icon_data and self.icon_mime_type:
            return url_for('main.public_category_icon', category_id=self.id)
        # Fallback: static/icons/<slug>.(svg|png|jpg|jpeg)
        try:
            from fetch_category_icons import slugify
        except ImportError:
            def slugify(text):
                return (
                    text.lower()
                    .replace(' ', '_')
                    .replace('é', 'e')
                    .replace('è', 'e')
                    .replace('ê', 'e')
                    .replace('à', 'a')
                    .replace('ç', 'c')
                    .replace('ô', 'o')
                    .replace('û', 'u')
                    .replace('ù', 'u')
                    .replace('ï', 'i')
                    .replace('î', 'i')
                    .replace("'", '')
                    .replace('"', '')
                )
        slug = slugify(self.name)
        static_folder = os.path.join(current_app.static_folder, 'icons')
        for ext in ['svg', 'png', 'jpg', 'jpeg']:
            icon_filename = f"{slug}.{ext}"
            static_path = os.path.join(static_folder, icon_filename)
            if os.path.exists(static_path):
                return url_for('static', filename=f'icons/{icon_filename}')
        return None
'''

print("⚠️  Ce script contient le modèle Category original pour rollback")
print("📝 Si nécessaire, remplacez le modèle dans models.py par le contenu ci-dessus")
print("🔄 N'oubliez pas de restaurer aussi les templates et la route public_category_icon")
