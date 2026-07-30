"""Tests purs pour matching.py — aucune base de données, aucune app Flask requise."""
import matching


def test_normalize_text_strips_accents_and_case():
    assert matching.normalize_text("PORTEFEUILLE Éléphant") == matching.normalize_text("portefeuille elephant")


def test_normalize_text_removes_stopwords():
    normalized = matching.normalize_text("le sac de sport pour la piscine")
    tokens = normalized.split()
    assert 'le' not in tokens and 'de' not in tokens and 'pour' not in tokens and 'la' not in tokens


def test_normalize_text_applies_synonyms():
    # "portable" est un synonyme de "telephone" (matching.SYNONYMS)
    a = matching.normalize_text("mon telephone noir")
    b = matching.normalize_text("mon portable noir")
    assert a == b


def test_normalize_text_empty_input():
    assert matching.normalize_text("") == ''
    assert matching.normalize_text(None) == ''


def test_match_score_identical_titles_scores_high():
    item1 = _item(title="Portefeuille noir Nike")
    item2 = _item(title="Portefeuille noir Nike")
    score = matching.match_score(item1, item2)
    assert score >= 90


def test_match_score_unrelated_titles_scores_low():
    item1 = _item(title="Portefeuille noir")
    item2 = _item(title="Trottinette electrique rouge")
    score = matching.match_score(item1, item2)
    assert score < 40


def test_structured_field_bonus_shared_color():
    item1 = _item(item_color="noir,rouge")
    item2 = _item(item_color="noir")
    bonus = matching.structured_field_bonus(item1, item2)
    assert bonus >= matching.MATCH_CONFIG['bonus_color_match']


def test_structured_field_bonus_color_conflict():
    item1 = _item(item_color="noir")
    item2 = _item(item_color="rouge")
    bonus = matching.structured_field_bonus(item1, item2)
    assert bonus < 0


def test_structured_field_bonus_brand_match():
    item1 = _item(item_brand="Nike")
    item2 = _item(item_brand="nike")
    bonus = matching.structured_field_bonus(item1, item2)
    assert bonus >= matching.MATCH_CONFIG['bonus_brand_match']


def test_multicolore_never_creates_a_color_conflict():
    """'multicolore' est compatible avec n'importe quelle couleur : un sac
    multicolore decrit comme 'noir' par l'autre partie n'est pas une divergence."""
    bonus = matching.structured_field_bonus(_item(item_color="multicolore"), _item(item_color="noir"))
    assert bonus == 0, "'multicolore' ne doit jamais declencher le malus de conflit"


def test_multicolore_shared_still_rewarded():
    bonus = matching.structured_field_bonus(_item(item_color="multicolore"),
                                            _item(item_color="multicolore"))
    assert bonus >= matching.MATCH_CONFIG['bonus_color_match']


def test_multicolore_does_not_mask_a_real_conflict():
    """Une couleur franche divergente reste un conflit meme si 'multicolore' est coche."""
    bonus = matching.structured_field_bonus(_item(item_color="multicolore,noir"),
                                            _item(item_color="rouge"))
    assert bonus < 0


def test_inconnu_stays_neutral():
    assert matching.structured_field_bonus(_item(item_color="inconnu"), _item(item_color="noir")) == 0


def test_confidence_label_bands():
    cfg = matching.MATCH_CONFIG
    assert matching.confidence_label(100) == 'Fort'
    assert matching.confidence_label(cfg['confidence_high']) == 'Fort'
    assert matching.confidence_label(cfg['confidence_medium']) == 'Moyen'
    assert matching.confidence_label(cfg['confidence_medium'] - 1) == 'Faible'
    assert matching.confidence_label(0) == 'Faible'


def test_confidence_level_keys_are_known():
    for score in (0, 50, 70, 95, 100):
        assert matching.confidence_level(score) in matching.CONFIDENCE_LEVELS


def test_extract_descriptors_returns_immutable_sets():
    """Le cache LRU partage ses valeurs : elles doivent etre non modifiables."""
    colors, brands = matching._extract_descriptors("sac noir nike")
    assert isinstance(colors, frozenset) and isinstance(brands, frozenset)
    assert 'noir' in colors and 'nike' in brands


def test_effective_threshold_switches_on_strong_structured_signal():
    assert matching.effective_threshold(0) == matching.MATCH_CONFIG['threshold_default']
    assert matching.effective_threshold(15) == matching.MATCH_CONFIG['threshold_structured_low']
    assert matching.effective_threshold(20) == matching.MATCH_CONFIG['threshold_structured_low']


def test_normalize_text_is_memoized(monkeypatch):
    """Régression pour la mémoïsation (section C) : un même texte ne doit être
    re-stemmé qu'une seule fois, même si normalize_text() est appelé plusieurs fois."""
    calls = []
    original_stem = matching._stemmer.stem

    def counting_stem(token):
        calls.append(token)
        return original_stem(token)

    monkeypatch.setattr(matching._stemmer, 'stem', counting_stem)
    matching.normalize_text.cache_clear()

    text = "Portefeuille noir en cuir tres particulier"
    matching.normalize_text(text)
    count_after_first_call = len(calls)
    assert count_after_first_call > 0

    matching.normalize_text(text)
    assert len(calls) == count_after_first_call, (
        "normalize_text() a re-execute le stemming pour un texte deja vu : "
        "le cache (functools.lru_cache) est absent ou inefficace."
    )


class _item:
    """Petit double léger imitant un Item pour matching.py (title/comments/location/...)."""
    def __init__(self, title='', comments='', location='', found_location='',
                 item_color='', item_brand='', item_distinctive=''):
        self.title = title
        self.comments = comments
        self.location = location
        self.found_location = found_location
        self.item_color = item_color
        self.item_brand = item_brand
        self.item_distinctive = item_distinctive
