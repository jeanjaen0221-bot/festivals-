"""Tests purs pour la logique d'agrégation de photo_embeddings.py.

N'importent jamais torch/transformers : current_model_version() est
monkeypatché pour éviter le chargement de visual_matcher.py (qui importe
torch au niveau module). Les objets Item/ItemPhoto/PhotoEmbedding réels ne
sont jamais utilisés — de simples doubles suffisent pour cette logique pure.
"""
import numpy as np
import pytest

import photo_embeddings as pe


class FakeEmbedding:
    def __init__(self, model_version, status, vector=None):
        self.model_version = model_version
        self.status = status
        if vector is not None:
            arr = np.asarray(vector, dtype=np.float32)
            self.embedding = arr.tobytes()
            self.embedding_dimension = arr.size
        else:
            self.embedding = None
            self.embedding_dimension = None


class FakePhoto:
    def __init__(self, embeddings):
        self.embeddings = embeddings


class FakeItem:
    def __init__(self, photos):
        self.photos = photos


@pytest.fixture(autouse=True)
def fixed_model_version(monkeypatch):
    """Évite l'import de visual_matcher (donc de torch) pendant les tests."""
    monkeypatch.setattr(pe, 'current_model_version', lambda: 'test-model')


def test_image_hash_is_deterministic():
    data = b'\x89PNG\r\n\x1a\nfake-bytes'
    assert pe.image_hash(data) == pe.image_hash(data)
    assert pe.image_hash(data) != pe.image_hash(data + b'x')


def test_ready_vectors_filters_by_model_version_and_status():
    photo = FakePhoto(embeddings=[
        FakeEmbedding('test-model', pe.READY, vector=[1.0, 0.0, 0.0]),
        FakeEmbedding('other-model', pe.READY, vector=[0.0, 1.0, 0.0]),   # mauvaise version
        FakeEmbedding('test-model', pe.FAILED, vector=[0.0, 0.0, 1.0]),   # pas prêt
        FakeEmbedding('test-model', pe.READY, vector=None),               # pas de vecteur
    ])
    item = FakeItem(photos=[photo])
    vectors = pe._ready_vectors(item)
    assert len(vectors) == 1
    assert np.allclose(vectors[0], [1.0, 0.0, 0.0])


def test_item_embedding_similarity_none_when_no_ready_vectors():
    item_with_vector = FakeItem(photos=[
        FakePhoto(embeddings=[FakeEmbedding('test-model', pe.READY, vector=[1.0, 0.0])])
    ])
    item_without_vector = FakeItem(photos=[
        FakePhoto(embeddings=[FakeEmbedding('test-model', pe.FAILED, vector=None)])
    ])
    assert pe.item_embedding_similarity(item_with_vector, item_without_vector) is None
    assert pe.item_embedding_similarity(item_without_vector, item_without_vector) is None


def test_item_embedding_similarity_returns_cosine_similarity():
    item1 = FakeItem(photos=[FakePhoto(embeddings=[
        FakeEmbedding('test-model', pe.READY, vector=[1.0, 0.0])
    ])])
    item2 = FakeItem(photos=[FakePhoto(embeddings=[
        FakeEmbedding('test-model', pe.READY, vector=[1.0, 0.0])
    ])])
    similarity = pe.item_embedding_similarity(item1, item2)
    assert similarity == pytest.approx(1.0)


def test_item_embedding_similarity_picks_best_match_across_photos():
    item1 = FakeItem(photos=[
        FakePhoto(embeddings=[FakeEmbedding('test-model', pe.READY, vector=[1.0, 0.0])]),
        FakePhoto(embeddings=[FakeEmbedding('test-model', pe.READY, vector=[0.0, 1.0])]),
    ])
    item2 = FakeItem(photos=[
        FakePhoto(embeddings=[FakeEmbedding('test-model', pe.READY, vector=[0.0, 1.0])]),
    ])
    # Le meilleur score (1.0, entre la 2e photo de item1 et l'unique photo de item2)
    # doit l'emporter sur le pire (0.0).
    similarity = pe.item_embedding_similarity(item1, item2)
    assert similarity == pytest.approx(1.0)
