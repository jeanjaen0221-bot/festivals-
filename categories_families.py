"""Familles de catégories — source unique pour le formulaire, le seed et le matching.

Pourquoi : la catégorie ne servait que de bonus binaire (+10 si identique). Un
*écart* de catégorie n'était jamais pénalisé, si bien qu'un téléphone perdu et une
bouteille trouvée pouvaient atteindre 100/100. En regroupant les ~90 catégories en
familles, on peut distinguer trois situations très différentes :

* même catégorie                      → signal fort
* même famille, catégorie différente  → plausible (sac à dos / sac à main)
* familles différentes                → quasi certainement pas le même objet

Cette table était codée en dur dans ``ItemForm.__init__``, uniquement pour
grouper le menu déroulant. Elle est ici pour que le formulaire, le seed et le
moteur de correspondance partagent exactement la même vérité.
"""
from rapidfuzz import fuzz, process

FAMILLES = [
    ("Objets personnels", [
        "Téléphone", "Clés", "Portefeuille", "Carte bancaire", "Carte d'identité",
        "Permis de conduire", "Badge d'accès", "Papiers d’identité",
    ]),
    ("Accessoires", [
        "Sac à dos", "Sac à main", "Banane", "Pochette", "Trousseau",
    ]),
    ("Vêtements", [
        "Veste", "Pull", "Sweat", "T-shirt", "Pantalon", "Short", "Jupe", "Robe",
        "Casquette", "Chapeau", "Bonnet", "Écharpe", "Gants", "Chaussures", "Sandales",
    ]),
    ("Lunettes & optique", [
        "Lunettes de soleil", "Lunettes de vue",
    ]),
    ("Bijoux", [
        "Bijoux", "Bague", "Collier", "Bracelet", "Boucles d’oreilles",
    ]),
    ("Audio & tech", [
        "Écouteurs", "Casque audio", "Batterie externe", "Chargeur", "Câble USB",
    ]),
    ("Festival & camping", [
        "Tente", "Sac de couchage", "Matelas gonflable", "Lampe frontale", "Gourde",
        "Bouteille", "Verre réutilisable", "Badge festival", "Bracelet festival",
        "Pochette étanche", "Gobelet réutilisable", "Poncho pluie", "Bouchons d’oreille",
        "Crème solaire", "Plaid", "Tapis de sol", "Cendrier de poche",
    ]),
    ("Divers précieux", [
        "Argent liquide", "Carte cadeau",
    ]),
    ("Objets de transport", [
        "Vélo", "Trottinette", "Skateboard", "Clé de voiture", "Clé de moto",
    ]),
    ("Santé", [
        "Médicaments", "Boîte à médicaments", "Inhalateur", "Appareil auditif",
    ]),
    ("Autres", [
        "Livre", "Carnet", "Stylo", "Parapluie", "Briquet", "Jeu de cartes", "Doudou",
        "Peluche", "Jouet", "Accessoire animalier", "Accessoire de déguisement",
        "Maillot de bain",
    ]),
]

CATEGORY_TO_FAMILY = {
    nom: famille for famille, noms in FAMILLES for nom in noms
}

FAMILY_NAMES = [famille for famille, _ in FAMILLES]

# En dessous de ce score de similarité, on préfère ne rien affirmer : une famille
# inconnue est neutre pour le matching, une famille fausse est un malus injustifié.
GUESS_CUTOFF = 80


def guess_family(category_name: str) -> str | None:
    """Devine la famille d'une catégorie créée à la volée par un bénévole.

    Rapproche le nom saisi des catégories connues (« Sacoche » → « Sac à dos » →
    Accessoires). Retourne ``None`` en cas de doute : le matching traite une
    famille inconnue comme neutre, jamais comme une divergence, donc l'absence de
    réponse est sans risque alors qu'une mauvaise réponse coûterait un malus.

    Utilise ``matching.normalize_text`` pour comparer sur la même base que le
    reste du moteur : accents, casse, pluriels et synonymes (« portable » →
    « telephone ») sont donc pris en compte.

    Limite assumée : sur 11 cas de test la devinette en place 9 correctement.
    « Doudoune » part vers Autres (rapproché de « Doudou ») et « Chargeur
    téléphone » vers Objets personnels plutôt qu'Audio & tech. C'est acceptable
    parce qu'une famille erronée coûte un malus, pas une exclusion : la paire
    reste rattrapable en baissant le seuil sur /matches.
    """
    if not category_name or not category_name.strip():
        return None

    from matching import normalize_text  # import tardif : évite un cycle au chargement

    cible = normalize_text(category_name)
    if not cible:
        return None

    # Un nom déjà connu (à la casse/accent près) n'a pas besoin de devinette.
    for nom, famille in CATEGORY_TO_FAMILY.items():
        if normalize_text(nom) == cible:
            return famille

    connus = {normalize_text(nom): famille for nom, famille in CATEGORY_TO_FAMILY.items()}
    connus.pop('', None)
    meilleur = process.extractOne(cible, connus.keys(), scorer=fuzz.token_set_ratio)
    if meilleur and meilleur[1] >= GUESS_CUTOFF:
        return connus[meilleur[0]]
    return None
