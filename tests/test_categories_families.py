"""Tests des familles de catégories — aucune base de données requise."""
import categories_families as cf
import matching


class _cat:
    def __init__(self, family=None):
        self.family = family


class _item:
    """Double léger d'un Item pour family_bonus (category_id + category.family)."""
    def __init__(self, category_id=None, family=None):
        self.category_id = category_id
        self.category = _cat(family) if family is not None else None


# ── Cohérence de la table ────────────────────────────────────────────────────

def test_every_category_belongs_to_exactly_one_family():
    vus = {}
    for famille, noms in cf.FAMILLES:
        for n in noms:
            assert n not in vus, f"{n} apparait dans {vus[n]} et {famille}"
            vus[n] = famille


def test_family_names_match_the_table():
    assert cf.FAMILY_NAMES == [f for f, _ in cf.FAMILLES]


def test_category_to_family_covers_the_whole_table():
    total = sum(len(noms) for _, noms in cf.FAMILLES)
    assert len(cf.CATEGORY_TO_FAMILY) == total


def test_seed_derives_from_the_families_table():
    """Le seed ne doit pas redupliquer la liste des categories : une divergence
    ferait disparaitre des categories du menu groupe."""
    import io
    src = io.open('categories_seed.py', encoding='utf-8').read()
    assert 'from categories_families import FAMILLES' in src
    assert 'for famille, noms in FAMILLES' in src


# ── Devinette ────────────────────────────────────────────────────────────────

def test_guess_family_known_name():
    assert cf.guess_family("Téléphone") == "Objets personnels"
    assert cf.guess_family("telephone") == "Objets personnels"


def test_guess_family_close_variant():
    assert cf.guess_family("Sacoche") == "Accessoires"
    assert cf.guess_family("Trottinette electrique") == "Objets de transport"


def test_guess_family_uses_matching_synonyms():
    """« portable » est un synonyme de « telephone » dans matching.SYNONYMS."""
    assert cf.guess_family("Portable") == "Objets personnels"


def test_guess_family_returns_none_when_unsure():
    """Mieux vaut aucune famille qu'une mauvaise : une famille erronee coute un
    malus, une famille absente est neutre."""
    assert cf.guess_family("Zzzqxwv") is None
    assert cf.guess_family("") is None
    assert cf.guess_family(None) is None
    assert cf.guess_family("   ") is None


# ── Bonus/malus ──────────────────────────────────────────────────────────────

def test_family_bonus_same_category_is_positive():
    bonus = matching.family_bonus(_item(3, "Accessoires"), _item(3, "Accessoires"))
    assert bonus == matching.MATCH_CONFIG['bonus_same_category']


def test_family_bonus_same_family_other_category_is_mildly_negative():
    """Sac a dos vs sac a main : plausible, mais moins qu'une categorie identique."""
    bonus = matching.family_bonus(_item(3, "Accessoires"), _item(4, "Accessoires"))
    assert bonus == -matching.MATCH_CONFIG['malus_other_category']


def test_family_bonus_other_family_is_strongly_negative():
    bonus = matching.family_bonus(_item(3, "Accessoires"), _item(9, "Santé"))
    assert bonus == -matching.MATCH_CONFIG['malus_other_family']


def test_family_bonus_is_neutral_when_a_family_is_unknown():
    """Une categorie creee a la volee sans famille ne doit jamais etre penalisee."""
    assert matching.family_bonus(_item(3, "Accessoires"), _item(9, None)) == 0.0
    assert matching.family_bonus(_item(3, None), _item(9, None)) == 0.0
    assert matching.family_bonus(_item(3, "Accessoires"), _item(9, "  ")) == 0.0


def test_family_bonus_survives_items_without_category():
    """Les sondes SimpleNamespace de l'apercu n'ont pas de relation category."""
    from types import SimpleNamespace
    probe = SimpleNamespace(title='x')
    assert matching.family_bonus(probe, _item(3, "Accessoires")) == 0.0


def test_other_family_malus_outweighs_a_full_structured_signal():
    """Un ecart de famille doit primer sur couleur + marque partagees, sinon un
    telephone noir Apple et une bouteille noire Apple resteraient au sommet."""
    cfg = matching.MATCH_CONFIG
    signal_max = cfg['bonus_color_match'] + cfg['bonus_brand_match']
    assert cfg['malus_other_family'] > signal_max - cfg['bonus_same_category']
