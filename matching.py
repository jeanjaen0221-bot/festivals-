import re
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
    'fields_weights': {'title': 0.55, 'comments': 0.25, 'location': 0.20},
    'text_weight':    0.55,   # part du score texte dans le score final
    'image_weight':   0.30,   # part texte↔image
    'img_img_weight': 0.15,   # part image↔image (quand les deux ont une photo)
    'bonus_same_category': 10,
    'bonus_date_close':    10,  # ≤ 2 jours
    'malus_date_far':      10,  # > 14 jours
    'threshold_default':   60,
}

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


def normalize_text(text: str) -> str:
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


def _extract_descriptors(raw_text: str) -> tuple[set, set]:
    """Retourne (couleurs, marques) trouvées dans le texte brut (lowercased + unidecode)."""
    text = unidecode(raw_text.lower())
    found_colors = {c for c in COLORS if re.search(r'\b' + re.escape(c) + r'\b', text)}
    found_brands = {b for b in BRANDS if re.search(r'\b' + re.escape(b) + r'\b', text)}
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


def _text_field_score(v1: str, v2: str) -> float:
    """
    Score multi-stratégie pour deux textes normalisés (0-100).
    Combine token_sort_ratio, partial_ratio, WRatio et token_set_ratio.
    """
    if not v1 and not v2:
        return 0.0
    if not v1 or not v2:
        return 0.0
    best = max(
        fuzz.token_sort_ratio(v1, v2),
        fuzz.partial_ratio(v1, v2),
        fuzz.WRatio(v1, v2),
    )
    set_score = fuzz.token_set_ratio(v1, v2)
    return best * 0.50 + set_score * 0.50


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
        # Si les deux sont vides → score neutre, ne pas pénaliser
        if not v1 and not v2:
            continue
        s = _text_field_score(v1, v2)
        score += s * weight
        total += weight
    base = round(score / total, 2) if total > 0 else 0.0

    # Bonus descripteurs sur titre + commentaires
    raw1 = (getattr(item1, 'title', '') or '') + ' ' + (getattr(item1, 'comments', '') or '')
    raw2 = (getattr(item2, 'title', '') or '') + ' ' + (getattr(item2, 'comments', '') or '')
    desc_b = descriptor_bonus(raw1, raw2)

    return round(max(0.0, min(100.0, base + desc_b)), 2)


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
        # Si les deux champs sont vides, on ne peut pas les comparer (N/A)
        if not norm1 and not norm2:
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
        score = _text_field_score(norm1, norm2)
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
