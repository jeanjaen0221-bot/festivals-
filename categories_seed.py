"""Insertion des catégories de référence, avec leur famille.

La liste des catégories n'est plus dupliquée ici : elle est dérivée de
``categories_families.FAMILLES``, seule source de vérité, également utilisée par
le menu déroulant du formulaire et par le moteur de correspondance. Auparavant
les deux listes pouvaient diverger — une catégorie présente ici mais absente des
familles disparaissait purement et simplement du menu.
"""
from app import app, db
from models import Category
from categories_families import FAMILLES


def seed_categories():
    with app.app_context():
        crees = rattrapees = 0
        for famille, noms in FAMILLES:
            for n in noms:
                existe = Category.query.filter_by(name=n).first()
                if not existe:
                    db.session.add(Category(name=n, family=famille))
                    crees += 1
                elif not existe.family:
                    # Rattrape les bases créées avant l'ajout de la colonne.
                    existe.family = famille
                    rattrapees += 1
        db.session.commit()
        print(f"Catégories : {crees} créée(s), {rattrapees} famille(s) renseignée(s).")


if __name__ == '__main__':
    seed_categories()
