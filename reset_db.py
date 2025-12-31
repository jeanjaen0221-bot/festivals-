from app import app, db
from models import Item, Category
from sqlalchemy import text
from category_icons import get_icon_for_category

# Catégories par défaut avec leurs icônes Bootstrap
DEFAULT_CATEGORIES = [
    'Portefeuille',
    'Téléphone', 
    'Clés',
    'Lunettes',
    'Sac',
    'T-shirt',
    'Veste',
    'Chaussures',
    'Batterie externe',
    'Bague',
    'Montre',
    'Livre',
    'Parapluie',
    'Casquette'
]

if __name__ == "__main__":
    with app.app_context():
        print("💫 Suppression et recréation de toutes les tables...")
        db.drop_all()
        db.create_all()
        print("✅ Base de données réinitialisée.")

        # Nettoyage des anciens champs d’icône dans Category (si encore présents)
        with db.engine.connect() as conn:
            try:
                conn.execute(text('ALTER TABLE categories DROP COLUMN IF EXISTS icon_data'))
                conn.execute(text('ALTER TABLE categories DROP COLUMN IF EXISTS icon_mime_type'))
                conn.execute(text('ALTER TABLE categories DROP COLUMN IF EXISTS icon_filename'))
                print("🧹 Anciens champs d’icône supprimés de la table categories.")
            except Exception as e:
                print(f"⚠️ Impossible de supprimer les anciens champs d’icône : {e}")

        # Ajout des nouveaux champs à item_photos (si pas déjà présents)
        with db.engine.connect() as conn:
            try:
                conn.execute(text('ALTER TABLE item_photos ADD COLUMN IF NOT EXISTS data BYTEA'))
                conn.execute(text('ALTER TABLE item_photos ADD COLUMN IF NOT EXISTS mimetype VARCHAR(50)'))
                conn.execute(text('ALTER TABLE item_photos ADD COLUMN IF NOT EXISTS is_return_photo BOOLEAN DEFAULT FALSE'))
                print("🖼️ Champs data, mimetype et is_return_photo ajoutés à item_photos.")
            except Exception as e:
                print(f"⚠️ Impossible d’ajouter les champs à item_photos : {e}")

        # Créer les catégories par défaut avec Bootstrap Icons
        print("🏷️ Création des catégories par défaut...")
        for category_name in DEFAULT_CATEGORIES:
            icon_class = get_icon_for_category(category_name)
            category = Category(
                name=category_name,
                icon_class=icon_class
            )
            db.session.add(category)
            print(f"  ✅ {category_name} → {icon_class}")
        
        db.session.commit()
        print(f"🎉 {len(DEFAULT_CATEGORIES)} catégories créées avec succès!")

        # Diagnostic: afficher les colonnes des tables
        insp = db.inspect(db.engine)
        
        print("\n🔍 Diagnostic - Colonnes de la table categories :")
        columns_cat = insp.get_columns('categories')
        for col in columns_cat:
            print(f"  - {col['name']} ({col['type']})")
            
        print("\n🔍 Diagnostic - Colonnes de la table items :")
        columns = insp.get_columns('items')
        for col in columns:
            print(f"  - {col['name']} ({col['type']})")
            
        print("\n🔍 Diagnostic - Colonnes de la table item_photos :")
        columns_photos = insp.get_columns('item_photos')
        for col in columns_photos:
            print(f"  - {col['name']} ({col['type']})")
        
        print("\n🚀 Base de données prête avec le nouveau système Bootstrap Icons et la gestion des photos en base !")
