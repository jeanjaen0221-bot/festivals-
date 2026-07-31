#!/usr/bin/env python3
"""
Script de diagnostic pour identifier les problèmes Railway
"""

import sys
import os

def test_imports():
    """Teste tous les imports critiques."""
    print("🔍 Test des imports...")
    
    try:
        print("  ✓ Importing Flask modules...")
        from flask import Flask
        
        print("  ✓ Importing app...")
        from app import app, db
        
        print("  ✓ Importing models...")
        from models import Category, Item, Status
        
        print("  ✓ Importing category_icons...")
        from category_icons import get_icon_for_category
        
        print("  ✓ Testing category_icons function...")
        test_icon = get_icon_for_category("Test")
        print(f"    → get_icon_for_category('Test') = {test_icon}")
        
        print("✅ Tous les imports réussis!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur d'import: {e}")
        return False

def test_database():
    """Teste la connexion à la base de données."""
    print("\n🗄️ Test de la base de données...")
    
    try:
        from app import app, db
        from models import Category
        
        with app.app_context():
            print("  ✓ Connexion à la base...")
            
            # Tester une requête simple
            count = Category.query.count()
            print(f"  ✓ Nombre de catégories: {count}")
            
            # Tester les propriétés des catégories
            if count > 0:
                cat = Category.query.first()
                print(f"  ✓ Première catégorie: {cat.name}")
                print(f"  ✓ icon_class: {cat.icon_class}")
                print(f"  ✓ icon_bootstrap_class: {cat.icon_bootstrap_class}")
            
        print("✅ Base de données OK!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur de base de données: {e}")
        return False

def test_templates():
    """Teste que les templates peuvent être rendus."""
    print("\n📄 Test des templates...")
    
    try:
        from app import app
        from models import Category, Item
        
        with app.app_context():
            with app.test_client() as client:
                print("  ✓ Test client créé...")
                
                # Tester la page d'accueil
                response = client.get('/')
                print(f"  ✓ Page d'accueil: {response.status_code}")
                
                if response.status_code != 200:
                    print(f"    ⚠️ Réponse: {response.data.decode()[:200]}...")
                
        print("✅ Templates OK!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur de template: {e}")
        return False

def main():
    """Exécute tous les tests de diagnostic."""
    print("🚨 DIAGNOSTIC RAILWAY")
    print("=" * 50)
    
    # Test 1: Imports
    imports_ok = test_imports()
    
    # Test 2: Base de données
    db_ok = test_database() if imports_ok else False
    
    # Test 3: Templates
    templates_ok = test_templates() if imports_ok else False
    
    # Résumé
    print("\n📊 RÉSUMÉ")
    print("=" * 50)
    print(f"Imports: {'✅' if imports_ok else '❌'}")
    print(f"Base de données: {'✅' if db_ok else '❌'}")
    print(f"Templates: {'✅' if templates_ok else '❌'}")
    
    if imports_ok and db_ok and templates_ok:
        print("\n🎉 Tout semble fonctionner!")
        print("🤔 L'erreur 502 pourrait venir d'un problème de configuration Railway")
    else:
        print("\n💥 Problèmes détectés - voir les erreurs ci-dessus")
    
    return imports_ok and db_ok and templates_ok

if __name__ == "__main__":
    main()
