import os
from functools import lru_cache

try:
    from PIL import Image as PILImage
except Exception:  # pragma: no cover
    PILImage = None  # type: ignore

_model = None

@lru_cache(maxsize=1)
def _load_model():
    """Charge paresseusement le modèle CLIP via sentence-transformers.
    Retourne le modèle ou None si indisponible.
    """
    global _model
    if _model is not None:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('clip-ViT-B-32')
        _model = model
        return _model
    except Exception:
        return None


def _cosine_sim(a, b) -> float:
    import numpy as np
    if a is None or b is None:
        return 0.0
    a = a / (np.linalg.norm(a) + 1e-10)
    b = b / (np.linalg.norm(b) + 1e-10)
    return float(np.clip(np.dot(a, b), -1.0, 1.0))


def embed_text(text: str):
    model = _load_model()
    if not model:
        return None
    try:
        return model.encode([text or ''], convert_to_numpy=True)[0]
    except Exception:
        return None


def embed_image(image_path: str):
    """Encode une image via CLIP. Utilise PIL pour charger et passer l'image au modèle."""
    model = _load_model()
    if not model:
        return None
    if not image_path or not os.path.exists(image_path):
        return None
    if PILImage is None:
        return None
    try:
        img = PILImage.open(image_path).convert('RGB')
        # sentence-transformers CLIP : model.encode accepte PIL.Image directement
        return model.encode(img, convert_to_numpy=True)
    except Exception:
        return None


def text_image_similarity(text: str, image_path: str) -> float:
    """Similarité cosine entre un texte et une image (0..1). 0 si indisponible."""
    t = embed_text(text)
    i = embed_image(image_path)
    if t is None or i is None:
        return 0.0
    return _cosine_sim(t, i)


def image_image_similarity(image_path1: str, image_path2: str) -> float:
    """Similarité cosine entre deux images via CLIP (0..1). 0 si indisponible."""
    i1 = embed_image(image_path1)
    i2 = embed_image(image_path2)
    if i1 is None or i2 is None:
        return 0.0
    return _cosine_sim(i1, i2)
