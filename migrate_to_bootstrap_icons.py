#!/usr/bin/env python3
"""
Script de nettoyage pour supprimer les fichiers obsolètes du système d'icônes.
À exécuter après validation que le nouveau système fonctionne correctement.
"""

import os
import shutil

def cleanup_old_icon_system():
    """Supprime les fichiers obsolètes du système d'icônes."""
    
    files_to_remove = [
        'fetch_category_icons.py',
        'category_icon_map.py'
    ]
    
    directories_to_clean = [
        'static/icons'  # Garder le dossier mais supprimer les fichiers d'icônes
    ]
    
    print("🧹 Nettoyage du système d'icônes obsolète...")
    
    # Supprimer les fichiers Python obsolètes
    for file_path in files_to_remove:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"  ✅ Supprimé: {file_path}")
        else:
            print(f"  ⚠️  Fichier non trouvé: {file_path}")
    
    # Nettoyer le dossier static/icons (garder .keep)
    icons_dir = 'static/icons'
    if os.path.exists(icons_dir):
        for filename in os.listdir(icons_dir):
            if filename != '.keep':
                file_path = os.path.join(icons_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    print(f"  ✅ Supprimé: {file_path}")
        print(f"  ✅ Dossier {icons_dir} nettoyé (gardé .keep)")
    
    print("\n🎉 Nettoyage terminé!")
    print("📝 Note: Les fichiers suivants ont été conservés:")
    print("  - category_icons.py (nouveau système)")
    print("  - update_category_icons.py (script de mise à jour)")
    print("  - static/icons/.keep (pour maintenir le dossier)")

if __name__ == "__main__":
    # Demander confirmation avant suppression
    response = input("⚠️  Êtes-vous sûr de vouloir supprimer les fichiers obsolètes ? (oui/non): ")
    if response.lower() in ['oui', 'o', 'yes', 'y']:
        cleanup_old_icon_system()
    else:
        print("❌ Nettoyage annulé.")
