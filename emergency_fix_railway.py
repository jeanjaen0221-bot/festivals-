#!/usr/bin/env python3
"""
Script d'urgence pour corriger Railway - Version minimale
Ajoute juste la colonne icon_class sans supprimer les anciennes
"""

import os
import sys
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db

def emergency_fix():
    """Correction d'urgence : ajoute icon_class sans supprimer l'ancien système."""
    
    print("🚨 Correction d'urgence Railway...")
    
    try:
        with app.app_context():
            # Vérifier si icon_class existe déjà
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='categories' AND column_name='icon_class'
            """))
            
            if result.fetchone():
                print("✅ Colonne icon_class existe déjà")
            else:
                print("📝 Ajout de la colonne icon_class...")
                db.session.execute(text("ALTER TABLE categories ADD COLUMN icon_class VARCHAR(50)"))
                db.session.commit()
                print("✅ Colonne icon_class ajoutée")
            
            # Assigner des icônes par défaut
            print("🔧 Attribution d'icônes par défaut...")
            db.session.execute(text("""
                UPDATE categories 
                SET icon_class = 'bi-box-seam' 
                WHERE icon_class IS NULL
            """))
            db.session.commit()
            
            print("🎉 Correction terminée! L'application devrait redémarrer.")
            return True
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        db.session.rollback()
        return False

if __name__ == "__main__":
    emergency_fix()
