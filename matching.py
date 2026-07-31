import re
from functools import lru_cache
import nltk
from rapidfuzz import fuzz
from unidecode import unidecode

try:
    nltk.download('stopwords', quiet=True)
    nltk.download('punkt', quiet=True)
    nltk.download('snowball_data', quiet=True)
except Exception:
    pass

from nltk.stem.snowball import FrenchStemmer

# ── Stemmer singleton ──────────────────────────────────────────────────────────
_stemmer = FrenchStemmer()

# ── Configuration centralisée ──────────────────────────────────────────────────
MATCH_CONFIG = {
    # Le lieu ne pèse autant que parce que perdus et trouvés partagent désormais
    # la même liste de zones (voir zones.py) : sans vocabulaire commun il ne
    # pouvait quasiment jamais correspondre.
    'fields_weights': {'title': 0.60, 'comments': 0.20, 'location': 0.20},
    'text_weight':    0.85,   # texte quand une comparaison image↔image est disponible
    'img_img_weight': 0.15,   # DINOv2 image↔image (quand les deux ont une photo)
    'bonus_date_close':         10,  # ≤ 2 jours
    'malus_date_far':           10,  # > 14 jours
    # ── Catégorie & famille ───────────────────────────────────────────────────
    # Une catégorie identique est un signal fort ; un écart en est un aussi, et
    # il n'était pas exploité (l'ancien bonus binaire ne pénalisait jamais rien).
    'bonus_same_category':      12,
    'malus_other_category':     10,  # même famille, catégorie différente
    'malus_other_family':       40,  # familles différentes
    # ── Champs structurés (item_color / item_brand / item_distinctive CSV) ────
    'bonus_color_match':        15,  # par couleur commune
    'malus_color_conflict':      8,  # couleurs présentes ET aucune commune
    'bonus_brand_match':        20,  # même marque normalisée
    'bonus_distinctive_match':  12,  # par flag commun (a_document_id, a_argent…)
    # ── Seuils ────────────────────────────────────────────────────────────────
    # Relevés après dé-saturation des scores (cf. bonus_full_scale) : les
    # anciennes valeurs 60/45/60 laissaient passer un quart de toutes les paires.
    'threshold_default':        85,
    'threshold_structured_low': 70,  # seuil si signal structuré fort (≥15 pts)
    'threshold_duplicate':      75,  # détection de doublons (find_similar_items)
    # Échelle de conversion des bonus : un bonus de cette valeur consomme toute
    # la marge restante jusqu'à 100. Empêche les scores de s'empiler au plafond.
    'bonus_full_scale':         55,
    # Paliers de confiance affichés aux agents plutôt qu'un pourcentage brut.
    'confidence_high':          92,
    'confidence_medium':        80,
}

# Couleurs qui ne doivent jamais servir de preuve de divergence.
# 'inconnu'     : l'agent a explicitement coché « je ne sais pas ».
# 'multicolore' : compatible avec n'importe quelle couleur — un sac multicolore
#                 déclaré « noir » par l'autre partie n'est PAS une contradiction.
NEUTRAL_COLORS = {'inconnu'}
WILDCARD_COLORS = {'multicolore'}

# ── Stopwords ─────────────────────────────────────────────────────────────────
STOPWORDS = {
    'le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'd', 'et', 'en',
    'a', 'au', 'aux', 'pour', 'par', 'avec', 'sans', 'sur', 'sous', 'dans',
    'chez', 'ce', 'cet', 'cette', 'ces', 'mon', 'ma', 'mes', 'ton', 'ta',
    'tes', 'son', 'sa', 'ses', 'notre', 'nos', 'votre', 'vos', 'leur',
    'leurs', 'qui', 'que', 'quoi', 'dont', 'ne', 'pas', 'plus', 'moins',
    'tres', 'as', 'ont', 'est', 'sont', 'etait', 'etaient', 'ete', 'etre',
    'avoir', 'fait', 'faites', 'fais', 'faire', 'on', 'il', 'elle', 'ils',
    'elles', 'ceci', 'cela', 'ca', 'la', 'ici', 'y', 'comme', 'si', 'mais',
    'ou', 'donc', 'or', 'ni', 'car', 'se', 'peu', 'beaucoup', 'autre',
    'autres', 'meme', 'memes', 'chaque', 'aucun', 'aucune', 'tout', 'tous',
    'toute', 'toutes', 'quel', 'quelle', 'quels', 'quelles', 'ainsi',
    'apres', 'avant', 'aussi', 'bien', 'encore', 'jamais', 'parce',
    'pendant', 'puis', 'quand', 'vers', 'voici', 'voila',
}

# ── Synonymes ─────────────────────────────────────────────────────────────────
SYNONYMS = {
    'telephone':       ['portable', 'gsm', 'mobile', 'cellulaire', 'smartphone',
                        'iphone', 'android', 'telephone portable'],
    'porte-monnaie':   ['portefeuille', 'porte feuille', 'porte monnaie',
                        'wallet', 'bourse'],
    'clef':            ['cle', 'cles', 'clefs', 'cle usb', 'clef usb',
                        'trousseau', 'trousseau de cles'],
    'sac':             ['sacoche', 'sac a dos', 'cartable', 'tote bag',
                        'tote', 'besace', 'banane', 'sac banane'],
    'lunettes':        ['lunette', 'solaire', 'sunglasses', 'lunettes de soleil',
                        'lunettes de vue'],
    'casque':          ['headphones', 'ecouteurs', 'ecouteur', 'airpods',
                        'oreillette', 'oreillettes'],
    'badge':           ['pass', 'accreditation', 'carte', 'laissez-passer',
                        'bracelet festival', 'wristband'],
    'veste':           ['manteau', 'hoodie', 'sweat', 'pull', 'gilet',
                        'veste en jean', 'blouson', 'parka', 'imperméable',
                        'impermeable', 'k-way', 'kway'],
    'chapeau':         ['casquette', 'bonnet', 'bob', 'beret', 'panama',
                        'galurin', 'fedora'],
    'chargeur':        ['cable', 'adaptateur', 'power bank', 'powerbank',
                        'batterie externe', 'chargeur usb'],
    'appareil photo':  ['camera', 'reflex', 'gopro', 'go pro', 'appareil',
                        'objectif'],
    'bijou':           ['bague', 'collier', 'bracelet', 'boucle', 'pendentif',
                        'montre', 'jonc', 'alliance'],
    'montre':          ['watch', 'smartwatch', 'montre connectee'],
    'livre':           ['bouquin', 'roman', 'cahier', 'carnet', 'agenda'],
    'bouteille':       ['gourde', 'thermos', 'bidon', 'flasque'],
    'medicament':      ['medicaments', 'pilule', 'traitement', 'ordonnance',
                        'insuline', 'epipen'],
    'document':        ['papier', 'papiers', 'carte identite', 'passeport',
                        'permis', 'carte vitale', 'titre'],
    'parapluie':       ['parasol', 'ombrelle'],
    'ceinture':        ['baudrier', 'sangle'],
    'chaussure':       ['chaussures', 'basket', 'baskets', 'sandale', 'sandales',
                        'botte', 'bottes', 'tong', 'tongs'],
}

# ── Descripteurs couleur et marque ────────────────────────────────────────────
COLORS = {
    'noir', 'noire', 'noirs', 'noires', 'black',
    'blanc', 'blanche', 'blancs', 'blanches', 'white',
    'rouge', 'rouges', 'red',
    'bleu', 'bleue', 'bleus', 'bleues', 'blue',
    'vert', 'verte', 'verts', 'vertes', 'green',
    'jaune', 'jaunes', 'yellow',
    'rose', 'roses', 'pink',
    'gris', 'grise', 'gris', 'grey', 'gray',
    'orange', 'violet', 'violette', 'violets', 'violettes', 'purple',
    'marron', 'brun', 'brune', 'brown',
    'beige', 'creme', 'cream', 'gold', 'dore', 'doree', 'argent', 'argente',
    'silver', 'bordeaux', 'kaki', 'turquoise',
}

BRANDS = {
    'apple', 'samsung', 'huawei', 'xiaomi', 'oppo', 'sony', 'lg', 'nokia',
    'nike', 'adidas', 'puma', 'reebok', 'new balance', 'converse', 'vans',
    'north face', 'columbia', 'patagonia', 'quechua',
    'canon', 'nikon', 'fujifilm', 'olympus',
    'bose', 'sennheiser', 'jbl', 'beats',
    'levis', 'zara', 'h&m', 'uniqlo',
    'eastpak', 'herschel', 'fjallraven', 'dakine',
}

# ── Construction du mapping inverse synonymes (une seule fois au chargement) ──
_SYNONYM_FLAT: list[tuple[str, str]] = []
for _main, _syns in SYNONYMS.items():
    for _syn in _syns:
        _SYNONYM_FLAT.append((_syn, _main))
_SYNONYM_FLAT.sort(key=lambda x: -len(x[0]))  # plus long en premier


def _replace_synonyms(text: str) -> str:
    for syn, main in _SYNONYM_FLAT:
        pattern = r'\b' + re.escape(syn) + r'\b'
        text = re.sub(pattern, main, text)
    return text


@lru_cache(maxsize=4096)
def normalize_text(text: str) -> str:
    """Fonction pure : mémoïsée car appelée plusieurs fois pour le même texte
    (match_score() et match_explanation() normalisent chacun les mêmes champs)."""
    if not text:
        return ''
    text = text.lower()
    text = unidecode(text)
    text = _replace_synonyms(text)
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    tokens = text.split()
    tokens = [t for t in tokens if t not in STOPWORDS and len(t) > 1]
    tokens = [_stemmer.stem(t) for t in tokens]
    return ' '.join(tokens)


@lru_cache(maxsize=4096)
def _extract_descriptors(raw_text: str) -> tuple[frozenset, frozenset]:
    """Retourne (couleurs, marques) trouvées dans le texte brut (lowercased + unidecode).

    Mémoïsée : ~70 regex par appel, et la boucle O(perdus × trouvés) de /matches
    repasse en permanence sur les mêmes textes. Les frozensets évitent qu'un
    appelant modifie par erreur une valeur partagée par le cache."""
    text = unidecode(raw_text.lower())
    found_colors = frozenset(c for c in COLORS if re.search(r'\b' + re.escape(c) + r'\b', text))
    found_brands = frozenset(b for b in BRANDS if re.search(r'\b' + re.escape(b) + r'\b', text))
    return found_colors, found_brands


def descriptor_bonus(raw1: str, raw2: str) -> float:
    """
    Calcule un bonus/malus basé sur les couleurs et marques partagées.
    +8 par couleur partagée, +8 par marque partagée.
    -5 si l'un cite une couleur et l'autre pas du tout.
    Retour : valeur float (peut être négative).
    """
    colors1, brands1 = _extract_descriptors(raw1)
    colors2, brands2 = _extract_descriptors(raw2)
    bonus = 0.0
    bonus += 8.0 * len(colors1 & colors2)
    bonus += 8.0 * len(brands1 & brands2)
    if (colors1 and not colors2) or (colors2 and not colors1):
        bonus -= 5.0
    return bonus


def _get_location(item) -> str:
    """
    Retourne le bon champ lieu selon le statut de l'objet.
    Les objets FOUND stockent leur lieu dans found_location, pas location.
    """
    loc = getattr(item, 'location', '') or ''
    if not loc:
        loc = getattr(item, 'found_location', '') or ''
    return loc


def _get_field(item, field: str) -> str:
    """Lit un champ textuel sur un item, avec gestion spéciale du champ location."""
    if field == 'location':
        return _get_location(item)
    return getattr(item, field, '') or ''


def _text_field_score(v1: str, v2: str) -> float | None:
    """
    Score de similarité entre deux textes normalisés (0-100), ou ``None`` si la
    comparaison n'a pas de sens (au moins un des deux côtés est vide).

    ``None`` — et non 0 — parce qu'un champ rempli face à un champ vide n'est pas
    une divergence : c'est une absence d'information. L'ancien 0 coûtait tout le
    poids du champ (jusqu'à 25 points sur la description), ce qui écrasait les
    vraies paires dès qu'un déclarant avait laissé un champ de côté.

    On n'utilise plus ``partial_ratio`` ni ``WRatio`` : sur des titres courts ils
    montent à 100 pour des objets sans rapport (« cles voitur » vs « cle usb »).
    ``token_sort_ratio`` compare l'ensemble des mots, ``token_set_ratio`` tolère
    qu'un côté soit plus détaillé que l'autre — d'où sa part minoritaire.
    """
    if not v1 or not v2:
        return None
    return 0.65 * fuzz.token_sort_ratio(v1, v2) + 0.35 * fuzz.token_set_ratio(v1, v2)


def match_score(item1, item2, fields_weights=None):
    """
    Calcule un score de similarité pondéré entre deux objets.
    fields_weights: dict, ex: {'title':0.55, 'comments':0.25, 'location':0.20}
    """
    if fields_weights is None:
        fields_weights = MATCH_CONFIG['fields_weights']
    score = 0.0
    total = 0.0
    for field, weight in fields_weights.items():
        v1 = normalize_text(_get_field(item1, field))
        v2 = normalize_text(_get_field(item2, field))
        s = _text_field_score(v1, v2)
        # None = champ non comparable (vide d'au moins un côté) : on le retire de
        # la pondération au lieu de le compter comme une divergence.
        if s is None:
            continue
        score += s * weight
        total += weight
    base = round(score / total, 2) if total > 0 else 0.0

    # Bonus descripteurs sur titre + commentaires
    raw1 = (getattr(item1, 'title', '') or '') + ' ' + (getattr(item1, 'comments', '') or '')
    raw2 = (getattr(item2, 'title', '') or '') + ' ' + (getattr(item2, 'comments', '') or '')
    desc_b = descriptor_bonus(raw1, raw2)

    return apply_bonus(base, desc_b)


def match_explanation(item1, item2, fields_weights=None):
    """
    Retourne une explication détaillée du matching : score par champ, mots communs, synonymes détectés.
    """
    if fields_weights is None:
        fields_weights = MATCH_CONFIG['fields_weights']
    details = {}
    for field, weight in fields_weights.items():
        raw1 = _get_field(item1, field)
        raw2 = _get_field(item2, field)
        norm1 = normalize_text(raw1)
        norm2 = normalize_text(raw2)
        score = _text_field_score(norm1, norm2)
        # None = champ vide d'au moins un côté : non comparable (N/A), et exclu
        # de la pondération par match_score. L'agent doit voir « — », pas « 0 % »,
        # sinon il croit à une divergence alors qu'il manque juste l'information.
        if score is None:
            details[field] = {
                'score': None,
                'score_na': True,
                'common_words': [],
                'synonyms_found': [],
                'value1': raw1,
                'value2': raw2,
            }
            continue
        tokens1 = set(norm1.split())
        tokens2 = set(norm2.split())
        common = sorted(tokens1 & tokens2)
        syns = []
        for main, synlist in SYNONYMS.items():
            for syn in synlist:
                if re.search(r'\b' + re.escape(syn) + r'\b', raw1.lower()) or \
                   re.search(r'\b' + re.escape(syn) + r'\b', raw2.lower()):
                    syns.append((main, syn))
        details[field] = {
            'score': round(score, 2),
            'score_na': False,
            'common_words': common,
            'synonyms_found': syns,
            'value1': raw1,
            'value2': raw2,
        }
    raw1_full = (getattr(item1, 'title', '') or '') + ' ' + (getattr(item1, 'comments', '') or '')
    raw2_full = (getattr(item2, 'title', '') or '') + ' ' + (getattr(item2, 'comments', '') or '')
    c1, b1 = _extract_descriptors(raw1_full)
    c2, b2 = _extract_descriptors(raw2_full)
    details['_descriptors'] = {
        'colors_item1': sorted(c1),
        'colors_item2': sorted(c2),
        'brands_item1': sorted(b1),
        'brands_item2': sorted(b2),
        'shared_colors': sorted(c1 & c2),
        'shared_brands': sorted(b1 & b2),
        'descriptor_bonus': descriptor_bonus(raw1_full, raw2_full),
    }
    return details


def _parse_csv_field(value: str) -> set:
    """Retourne un set depuis un champ CSV (ex: 'noir,rouge' → {'noir','rouge'})."""
    if not value:
        return set()
    return {v.strip() for v in value.split(',') if v.strip()}


def structured_field_bonus(item1, item2) -> float:
    """
    Bonus/malus basé sur les champs structurés item_color, item_brand, item_distinctive.
    Ces champs sont remplis par coches → pas de variabilité de vocabulaire.

    Retourne un float (peut être négatif en cas de conflit couleur).
    """
    cfg = MATCH_CONFIG
    bonus = 0.0

    # ── Couleurs ──────────────────────────────────────────────────────────────
    colors1 = _parse_csv_field(getattr(item1, 'item_color', '') or '')
    colors2 = _parse_csv_field(getattr(item2, 'item_color', '') or '')
    # Une couleur commune reste un signal, y compris 'multicolore' des deux côtés.
    shared_colors = (colors1 & colors2) - NEUTRAL_COLORS
    # Seules les couleurs discriminantes peuvent prouver une divergence :
    # 'multicolore' est compatible avec tout, 'inconnu' n'affirme rien.
    discriminant1 = colors1 - NEUTRAL_COLORS - WILDCARD_COLORS
    discriminant2 = colors2 - NEUTRAL_COLORS - WILDCARD_COLORS
    if shared_colors:
        bonus += cfg['bonus_color_match'] * len(shared_colors)
    elif discriminant1 and discriminant2:
        # Les deux ont des couleurs franches mais aucune commune → conflit explicite
        bonus -= cfg['malus_color_conflict']

    # ── Marque ────────────────────────────────────────────────────────────────
    brand1 = unidecode((getattr(item1, 'item_brand', '') or '').lower().strip())
    brand2 = unidecode((getattr(item2, 'item_brand', '') or '').lower().strip())
    if brand1 and brand2 and brand1 != 'inconnu' and brand2 != 'inconnu':
        # Correspondance exacte ou très proche (fuzz ≥ 85)
        if brand1 == brand2 or fuzz.ratio(brand1, brand2) >= 85:
            bonus += cfg['bonus_brand_match']

    # ── Signes distinctifs ────────────────────────────────────────────────────
    dist1 = _parse_csv_field(getattr(item1, 'item_distinctive', '') or '')
    dist2 = _parse_csv_field(getattr(item2, 'item_distinctive', '') or '')
    shared_dist = dist1 & dist2
    if shared_dist:
        bonus += cfg['bonus_distinctive_match'] * len(shared_dist)

    return round(bonus, 2)


def effective_threshold(structured_bonus: float) -> float:
    """
    Retourne le seuil de matching effectif.
    Si le signal structuré est fort (≥15 pts), abaisse le seuil à threshold_structured_low.
    """
    cfg = MATCH_CONFIG
    if structured_bonus >= 15:
        return cfg['threshold_structured_low']
    return cfg['threshold_default']


def _category_family(item) -> str | None:
    """Famille de l'item, en tolérant qu'il n'ait pas de catégorie chargée."""
    category = getattr(item, 'category', None)
    if category is None:
        return None
    return (getattr(category, 'family', None) or '').strip() or None


def family_bonus(item1, item2) -> float:
    """
    Bonus/malus tiré de la catégorie et de sa famille.

    L'ancien système n'accordait qu'un +10 si les catégories étaient identiques
    et ne pénalisait *jamais* un écart : un téléphone perdu et une bouteille
    trouvée pouvaient donc atteindre 100/100. Trois situations sont désormais
    distinguées :

    * même catégorie                     → signal fort
    * même famille, catégorie différente → plausible (sac à dos ↔ sac à main)
    * familles différentes               → quasi certainement pas le même objet

    Le cas « familles différentes » est un malus, pas une exclusion : un objet
    mal catégorisé par un bénévole pressé doit rester retrouvable en abaissant
    le seuil sur /matches. Une famille inconnue (catégorie créée à la volée dont
    la devinette n'a rien donné) est neutre : mieux vaut ne rien affirmer que
    pénaliser à tort.
    """
    cfg = MATCH_CONFIG
    cat1 = getattr(item1, 'category_id', None)
    cat2 = getattr(item2, 'category_id', None)
    if cat1 and cat2 and cat1 == cat2:
        return float(cfg['bonus_same_category'])

    fam1 = _category_family(item1)
    fam2 = _category_family(item2)
    if fam1 is None or fam2 is None:
        return 0.0
    if fam1 == fam2:
        return -float(cfg['malus_other_category'])
    return -float(cfg['malus_other_family'])


def apply_bonus(base: float, bonus: float) -> float:
    """
    Applique un bonus/malus à un score de base sans jamais saturer.

    L'ancien `min(100, base + bonus)` écrasait tout contre le plafond : sur un
    corpus de 10 000 paires, 509 affichaient exactement 100 — vraies et fausses
    confondues — ce qui rendait le tri et le seuil inopérants.

    Ici un bonus positif ne peut qu'entamer la marge restante jusqu'à 100 :
    une paire déjà à 90 gagne au plus 10 points, une paire à 40 en gagne jusqu'à
    60. La fonction reste strictement croissante en `base` comme en `bonus`,
    donc le classement est préservé, mais les ex æquo artificiels disparaissent.
    Les malus, eux, restent soustractifs : une contradiction doit coûter cher.
    """
    if bonus > 0:
        scale = MATCH_CONFIG['bonus_full_scale']
        score = base + (100.0 - base) * min(1.0, bonus / scale)
    else:
        score = base + bonus
    return round(max(0.0, min(100.0, score)), 2)


# ── Affichage de la confiance ─────────────────────────────────────────────────
# Le score brut cumule bonus catégorie, date, couleur, marque et signes
# distinctifs, puis est borné à 100 : de nombreuses paires sans rapport
# atteignent le plafond. Afficher « 100 % » à un agent lui donnerait une
# certitude que le score ne porte pas. On expose donc un palier qualitatif.
CONFIDENCE_LEVELS = {
    'high':   {'label': 'Fort',   'css': 'high',   'icon': 'bi-check-circle-fill'},
    'medium': {'label': 'Moyen',  'css': 'medium', 'icon': 'bi-question-circle-fill'},
    'low':    {'label': 'Faible', 'css': 'low',    'icon': 'bi-dash-circle'},
}


def confidence_level(score: float) -> str:
    """Retourne la clé de palier ('high' / 'medium' / 'low') pour un score 0-100."""
    cfg = MATCH_CONFIG
    if score is None:
        return 'low'
    if score >= cfg['confidence_high']:
        return 'high'
    if score >= cfg['confidence_medium']:
        return 'medium'
    return 'low'


def confidence_label(score: float) -> str:
    """Libellé affiché aux agents à la place du pourcentage brut."""
    return CONFIDENCE_LEVELS[confidence_level(score)]['label']
