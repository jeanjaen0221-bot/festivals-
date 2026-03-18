#!/usr/bin/env python3
"""
Script pour mettre à jour les icônes des catégories existantes vers Bootstrap Icons.
À exécuter après la migration de base de données.
"""

from app import app, db
from models import Category
from category_icons import get_icon_for_category

def update_category_icons():
    """Met à jour toutes les catégories avec les nouvelles icônes Bootstrap."""
    with app.app_context():
        categories = Category.query.all()
        updated_count = 0
        
        print(f"Mise à jour de {len(categories)} catégories...")
        
        for category in categories:
            # Obtenir l'icône Bootstrap appropriée
            new_icon_class = get_icon_for_category(category.name)
            
            # Mettre à jour seulement si différent
            if category.icon_class != new_icon_class:
                old_icon = category.icon_class or "Aucune"
                category.icon_class = new_icon_class
                updated_count += 1
                print(f"  {category.name}: {old_icon} → {new_icon_class}")
            else:
                print(f"  {category.name}: {new_icon_class} (inchangé)")
        
        # Sauvegarder les changements
        if updated_count > 0:
            db.session.commit()
            print(f"\n✅ {updated_count} catégories mises à jour avec succès!")
        else:
            print("\n✅ Toutes les catégories sont déjà à jour!")

if __name__ == "__main__":
    update_category_icons()
