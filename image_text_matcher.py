import os
from functools import lru_cache
from typing import Optional

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None  # type: ignore

_model = None
_processor = None

@lru_cache(maxsize=1)
def _load_model():
    """Charge paresseusement le modèle CLIP via sentence-transformers.
    Retourne un tuple (model, processor) ou (None, None) si indisponible.
    """
    global _model
    if _model is not None:
        return _model
    try:
        # Utilise un modèle CLIP compact compatible CPU
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
        return model.encode([text or '' ], convert_to_numpy=True)[0]
    except Exception:
        return None


def embed_image(image_path: str):
    model = _load_model()
    if not model:
        return None
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        # SentenceTransformers supporte encode_images si backends installés
        # Alternative: encode avec encode + PIL via encode_image
        from sentence_transformers import SentenceTransformer
        if hasattr(model, 'encode_image'):
            from PIL import Image as PILImage
            img = PILImage.open(image_path).convert('RGB')
            return model.encode_image(img, convert_to_numpy=True)
        elif hasattr(model, 'encode') and hasattr(model, 'encode_images'):
            return model.encode_images([image_path], convert_to_numpy=True)[0]
        else:
            # Fallback: pas support
            return None
    except Exception:
        return None


def text_image_similarity(text: str, image_path: str) -> float:
    """Retourne une similarité cosine entre le texte et l'image (0..1).
    0 si indisponible.
    """
    t = embed_text(text)
    i = embed_image(image_path)
    if t is None or i is None:
        return 0.0
    return _cosine_sim(t, i)
