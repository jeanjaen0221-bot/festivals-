import re
from rapidfuzz import fuzz
from unidecode import unidecode
from nltk.stem.snowball import FrenchStemmer

# Liste de mots vides français courants
STOPWORDS = set([
    'le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'd', 'et', 'en', 'à', 'au', 'aux', 'pour', 'par', 'avec', 'sans', 'sur', 'sous', 'dans', 'chez', 'ce', 'cet', 'cette', 'ces', 'mon', 'ma', 'mes', 'ton', 'ta', 'tes', 'son', 'sa', 'ses', 'notre', 'nos', 'votre', 'vos', 'leur', 'leurs', 'qui', 'que', 'quoi', 'dont', 'où', 'ne', 'pas', 'plus', 'moins', 'très', 'a', 'as', 'ont', 'est', 'sont', 'était', 'étaient', 'été', 'être', 'avoir', 'fait', 'faites', 'fais', 'faire', 'on', 'il', 'elle', 'ils', 'elles', 'ceci', 'cela', 'ça', 'là', 'ici', 'y', 'en', 'comme', 'si', 'mais', 'ou', 'donc', 'or', 'ni', 'car', 'se', 'sa', 'ses', 'leur', 'leurs', 'notre', 'nos', 'votre', 'vos', 'plus', 'moins', 'très', 'peu', 'beaucoup', 'autre', 'autres', 'même', 'mêmes', 'chaque', 'aucun', 'aucune', 'tout', 'tous', 'toute', 'toutes', 'aucun', 'aucune', 'quel', 'quelle', 'quels', 'quelles', 'ainsi', 'après', 'avant', 'aussi', 'bien', 'encore', 'jamais', 'parce', 'pendant', 'puis', 'quand', 'sans', 'sous', 'sur', 'vers', 'voici', 'voilà', 'où', 'dont', 'du', 'des', 'au', 'aux', 'ce', 'cet', 'cette', 'ces', 'mon', 'ma', 'mes', 'ton', 'ta', 'tes', 'son', 'sa', 'ses'])

# Synonymes courants pour objets festival
SYNONYMS = {
    'téléphone': ['portable', 'gsm', 'mobile', 'cellulaire', 'smartphone'],
    'porte-monnaie': ['portefeuille', 'porte feuille', 'porte monnaie'],
    'clef': ['clé', 'cles', 'clefs', 'clé usb', 'cle usb'],
    'sac': ['sacoche', 'sac à dos', 'sac a dos', 'cartable'],
    'lunettes': ['lunette', 'solaire', 'sunglasses'],
    'casque': ['headphones', 'écouteurs', 'ecouteurs'],
    'badge': ['pass', 'accréditation', 'carte'],
}

# Inverse le mapping pour remplacer tous les synonymes par le mot principal
def replace_synonyms(text):
    for main, syns in SYNONYMS.items():
        for syn in syns:
            pattern = r'\b' + re.escape(syn) + r'\b'
            text = re.sub(pattern, main, text)
    return text

def normalize_text(text):
    if not text:
        return ''
    text = text.lower()
    text = unidecode(text)
    text = replace_synonyms(text)
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    tokens = text.split()
    tokens = [t for t in tokens if t not in STOPWORDS]
    stemmer = FrenchStemmer()
    tokens = [stemmer.stem(t) for t in tokens]
    return ' '.join(tokens)

def match_score(item1, item2, fields_weights=None):
    """
    Calcule un score de similarité pondéré entre deux objets.
    fields_weights: dict, ex: {'title':0.5, 'comments':0.3, 'location':0.2}
    """
    if fields_weights is None:
        fields_weights = {'title':0.5, 'comments':0.3, 'location':0.2}
    score = 0
    total = 0
    for field, weight in fields_weights.items():
        v1 = normalize_text(getattr(item1, field, ''))
        v2 = normalize_text(getattr(item2, field, ''))
        s = fuzz.token_sort_ratio(v1, v2)
        score += s * weight
        total += weight
    return round(score / total, 2) if total > 0 else 0

def match_explanation(item1, item2, fields_weights=None):
    """
    Retourne une explication détaillée du matching : score par champ, mots communs, synonymes détectés.
    """
    if fields_weights is None:
        fields_weights = {'title':0.5, 'comments':0.3, 'location':0.2}
    stemmer = FrenchStemmer()
    details = {}
    for field, weight in fields_weights.items():
        raw1 = getattr(item1, field, '') or ''
        raw2 = getattr(item2, field, '') or ''
        norm1 = normalize_text(raw1)
        norm2 = normalize_text(raw2)
        tokens1 = set(norm1.split())
        tokens2 = set(norm2.split())
        common = sorted(tokens1 & tokens2)
        score = fuzz.token_sort_ratio(norm1, norm2)
        # Synonymes détectés (dans le texte brut)
        syns = []
        for main, synlist in SYNONYMS.items():
            for syn in synlist:
                if syn in raw1.lower() or syn in raw2.lower():
                    syns.append((main, syn))
        details[field] = {
            'score': score,
            'common_words': common,
            'synonyms_found': syns,
            'value1': raw1,
            'value2': raw2
        }
    return details
