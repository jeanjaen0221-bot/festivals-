#!/usr/bin/env python3
"""
Script de migration pour remplacer le système d'icônes par Bootstrap Icons.
Peut être exécuté directement sur Railway ou en local.
"""

import os
import sys
from sqlalchemy import text

# Ajouter le répertoire parent au path pour importer les modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Category

# Mapping des catégories vers les icônes Bootstrap
CATEGORY_ICON_MAPPING = {
    'Portefeuille': 'bi-wallet2',
    'Porte-monnaie': 'bi-wallet',
    'Téléphone': 'bi-phone',
    'Trousseau': 'bi-key',
    'Clés': 'bi-key-fill',
    'Badge d\'accès': 'bi-credit-card-2-front',
    'Carte d\'identité': 'bi-person-vcard',
    'Bague': 'bi-gem',
    'Montre': 'bi-smartwatch',
    'Lunettes': 'bi-eyeglasses',
    'Collier': 'bi-heart',
    'Bracelet': 'bi-circle',
    'T-shirt': 'bi-person',
    'Sweat': 'bi-person-fill',
    'Pull': 'bi-person-fill',
    'Veste': 'bi-person-arms-up',
    'Pantalon': 'bi-person-standing',
    'Chaussures': 'bi-shoe-print',
    'Casquette': 'bi-cap',
    'Chapeau': 'bi-circle-fill',
    'Batterie externe': 'bi-battery-charging',
    'Chargeur': 'bi-plug',
    'Écouteurs': 'bi-headphones',
    'Appareil auditif': 'bi-ear',
    'Tablette': 'bi-tablet',
    'Ordinateur portable': 'bi-laptop',
    'Appareil photo': 'bi-camera',
    'Sac': 'bi-bag',
    'Banane': 'bi-apple',
    'Tapis de sol': 'bi-square',
    'Parapluie': 'bi-umbrella',
    'Livre': 'bi-book',
    'Cahier': 'bi-journal',
    'Stylo': 'bi-pen',
    'Bouteille': 'bi-cup-straw',
}

DEFAULT_ICON = 'bi-box-seam'

def check_column_exists(table_name, column_name):
    """Vérifie si une colonne existe dans une table."""
    try:
        result = db.session.execute(text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='{table_name}' AND column_name='{column_name}'
        """))
        return result.fetchone() is not None
    except Exception as e:
        print(f"Erreur lors de la vérification de colonne: {e}")
        return False

def migrate_to_bootstrap_icons():
    """Effectue la migration vers Bootstrap Icons."""
    
    print("🚀 Début de la migration vers Bootstrap Icons...")
    
    try:
        with app.app_context():
            # 1. Vérifier si la migration est nécessaire
            has_icon_class = check_column_exists('categories', 'icon_class')
            has_icon_data = check_column_exists('categories', 'icon_data')
            
            if has_icon_class and not has_icon_data:
                print("✅ Migration déjà effectuée!")
                return True
            
            # 2. Ajouter la colonne icon_class si elle n'existe pas
            if not has_icon_class:
                print("📝 Ajout de la colonne icon_class...")
                db.session.execute(text("ALTER TABLE categories ADD COLUMN icon_class VARCHAR(50)"))
                db.session.commit()
                print("✅ Colonne icon_class ajoutée")
            
            # 3. Récupérer toutes les catégories
            categories = Category.query.all()
            print(f"📋 Migration de {len(categories)} catégories...")
            
            # 4. Assigner les icônes Bootstrap
            updated_count = 0
            for category in categories:
                # Déterminer l'icône appropriée
                icon_class = CATEGORY_ICON_MAPPING.get(category.name, DEFAULT_ICON)
                
                # Recherche insensible à la casse si pas trouvé
                if icon_class == DEFAULT_ICON:
                    for cat_name, icon in CATEGORY_ICON_MAPPING.items():
                        if cat_name.lower() == category.name.lower():
                            icon_class = icon
                            break
                
                # Mettre à jour si nécessaire
                if category.icon_class != icon_class:
                    category.icon_class = icon_class
                    updated_count += 1
                    print(f"  📌 {category.name} → {icon_class}")
                else:
                    print(f"  ✓ {category.name} déjà configuré")
            
            # 5. Sauvegarder les changements
            if updated_count > 0:
                db.session.commit()
                print(f"💾 {updated_count} catégories mises à jour")
            
            # 6. Supprimer les anciennes colonnes si elles existent
            if has_icon_data:
                print("🧹 Suppression des anciennes colonnes...")
                try:
                    if check_column_exists('categories', 'icon_mime_type'):
                        db.session.execute(text("ALTER TABLE categories DROP COLUMN icon_mime_type"))
                    if check_column_exists('categories', 'icon_data'):
                        db.session.execute(text("ALTER TABLE categories DROP COLUMN icon_data"))
                    db.session.commit()
                    print("✅ Anciennes colonnes supprimées")
                except Exception as e:
                    print(f"⚠️  Erreur lors de la suppression des colonnes: {e}")
                    print("   (Ce n'est pas critique, le nouveau système fonctionne)")
            
            print("\n🎉 Migration terminée avec succès!")
            print("📱 Le système utilise maintenant Bootstrap Icons")
            return True
            
    except Exception as e:
        print(f"❌ Erreur lors de la migration: {e}")
        db.session.rollback()
        return False

def verify_migration():
    """Vérifie que la migration s'est bien passée."""
    try:
        with app.app_context():
            categories = Category.query.all()
            print(f"\n🔍 Vérification de {len(categories)} catégories:")
            
            for category in categories:
                icon = category.icon_bootstrap_class
                print(f"  ✓ {category.name}: {icon}")
            
            print("✅ Vérification terminée!")
            return True
    except Exception as e:
        print(f"❌ Erreur lors de la vérification: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Migration du système d'icônes vers Bootstrap Icons")
    print("=" * 60)
    
    # Effectuer la migration
    success = migrate_to_bootstrap_icons()
    
    if success:
        # Vérifier le résultat
        verify_migration()
        print("\n🚀 Prêt pour le déploiement!")
    else:
        print("\n💥 Échec de la migration")
        sys.exit(1)
