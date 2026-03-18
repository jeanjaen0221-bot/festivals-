from app import app, db
from models import Category

def seed_categories():
    noms = [
        # Objets personnels
        "Téléphone", "Clés", "Portefeuille", "Carte bancaire", "Carte d'identité", "Permis de conduire", "Badge d'accès", "Papiers d’identité",
        # Accessoires
        "Sac à dos", "Sac à main", "Banane", "Pochette", "Trousseau",
        # Vêtements
        "Veste", "Pull", "Sweat", "T-shirt", "Pantalon", "Short", "Jupe", "Robe", "Casquette", "Chapeau", "Bonnet", "Écharpe", "Gants", "Chaussures", "Sandales",
        # Lunettes & optique
        "Lunettes de soleil", "Lunettes de vue",
        # Bijoux
        "Bijoux", "Bague", "Collier", "Bracelet", "Boucles d’oreilles",
        # Audio & tech
        "Écouteurs", "Casque audio", "Batterie externe", "Chargeur", "Câble USB",
        # Festival & camping
        "Tente", "Sac de couchage", "Matelas gonflable", "Lampe frontale", "Gourde", "Bouteille", "Verre réutilisable", "Badge festival", "Bracelet festival", "Pochette étanche", "Gobelet réutilisable", "Poncho pluie", "Bouchons d’oreille", "Crème solaire", "Plaid", "Tapis de sol", "Cendrier de poche",
        # Divers précieux
        "Argent liquide", "Carte cadeau",
        # Objets de transport
        "Vélo", "Trottinette", "Skateboard", "Clé de voiture", "Clé de moto",
        # Santé
        "Médicaments", "Boîte à médicaments", "Inhalateur", "Appareil auditif",
        # Autres
        "Livre", "Carnet", "Stylo", "Parapluie", "Briquet", "Jeu de cartes", "Doudou", "Peluche", "Jouet", "Accessoire animalier", "Accessoire de déguisement", "Maillot de bain"
    ]
    with app.app_context():
        for n in noms:
            existe = Category.query.filter_by(name=n).first()
            if not existe:
                db.session.add(Category(name=n))
        db.session.commit()
        print("Catégories insérées.")

if __name__ == '__main__':
    seed_categories()
