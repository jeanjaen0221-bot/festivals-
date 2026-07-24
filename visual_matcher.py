"""Embeddings image↔image locaux avec DINOv2 Small.

Les poids Hugging Face sont mis en cache dans ``VISUAL_MATCHER_CACHE_DIR``. Sur
Railway, configurez cette variable vers un volume persistant; sinon le cache
standard Hugging Face (dans l'image de build si préchargé) est utilisé.
"""
import logging
import os
import threading
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModel

MODEL_ID = "facebook/dinov2-small"
_LOGGER = logging.getLogger(__name__)
_MODEL_LOCK = threading.Lock()
_MODEL: AutoModel | None = None
_PROCESSOR: AutoImageProcessor | None = None
_LOAD_ERROR: str | None = None
_LOAD_ATTEMPTED = False


def _cache_dir() -> str | None:
    """Retourne le cache configurable, en créant son dossier si nécessaire."""
    cache_dir = os.environ.get("VISUAL_MATCHER_CACHE_DIR")
    if cache_dir:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
    return cache_dir


def load_model() -> tuple[AutoModel, AutoImageProcessor] | None:
    """Charge DINOv2 une fois par processus et le prépare en lecture seule."""
    global _MODEL, _PROCESSOR, _LOAD_ERROR, _LOAD_ATTEMPTED
    if _MODEL is not None and _PROCESSOR is not None:
        return _MODEL, _PROCESSOR

    with _MODEL_LOCK:
        if _MODEL is not None and _PROCESSOR is not None:
            return _MODEL, _PROCESSOR
        if _LOAD_ATTEMPTED:
            return None
        _LOAD_ATTEMPTED = True
        try:
            cache_dir = _cache_dir()
            _LOGGER.info("Chargement du modèle visuel local %s (cache=%s)", MODEL_ID, cache_dir or "Hugging Face par défaut")
            processor = AutoImageProcessor.from_pretrained(MODEL_ID, cache_dir=cache_dir)
            model = AutoModel.from_pretrained(MODEL_ID, cache_dir=cache_dir)
            model.eval()
            for parameter in model.parameters():
                parameter.requires_grad_(False)
            _MODEL, _PROCESSOR = model, processor
            _LOGGER.info("Modèle visuel %s prêt pour les embeddings image↔image", MODEL_ID)
            return _MODEL, _PROCESSOR
        except Exception as exc:
            _LOAD_ERROR = f"{type(exc).__name__}: {exc}"
            _LOGGER.exception("Modèle visuel %s indisponible; la similarité image↔image est désactivée", MODEL_ID)
            return None


def model_status(load: bool = False) -> dict[str, Any]:
    """Expose un état explicite sans confondre un échec avec une similarité nulle."""
    if load:
        load_model()
    if _MODEL is not None:
        state = "ready"
    elif _LOAD_ATTEMPTED:
        state = "unavailable"
    else:
        state = "not_checked"
    return {
        "state": state,
        "model": MODEL_ID,
        "cache_dir": _cache_dir() or "Hugging Face par défaut",
        "error": _LOAD_ERROR,
    }


def embed_image(image_path: str) -> np.ndarray | None:
    """Retourne le vecteur CLS DINOv2 d'une image, ou ``None`` si indisponible."""
    loaded = load_model()
    if loaded is None:
        return None
    if not image_path or not os.path.isfile(image_path):
        _LOGGER.warning("Embedding image ignoré: fichier introuvable (%s)", image_path)
        return None
    model, processor = loaded
    try:
        with Image.open(image_path) as image:
            inputs = processor(images=image.convert("RGB"), return_tensors="pt")
        with torch.inference_mode():
            outputs = model(**inputs)
        return outputs.last_hidden_state[:, 0, :].squeeze(0).cpu().numpy()
    except Exception:
        _LOGGER.exception("Échec de l'embedding DINOv2 pour %s", image_path)
        return None


def image_similarity(vector_a: np.ndarray | None, vector_b: np.ndarray | None) -> float | None:
    """Similarité cosinus DINOv2 bornée à 0..1; ``None`` signifie non calculée."""
    if vector_a is None or vector_b is None:
        return None
    norm_a = float(np.linalg.norm(vector_a))
    norm_b = float(np.linalg.norm(vector_b))
    if norm_a == 0.0 or norm_b == 0.0:
        _LOGGER.warning("Similarité DINOv2 non calculable: vecteur nul")
        return None
    return float(np.clip(np.dot(vector_a, vector_b) / (norm_a * norm_b), 0.0, 1.0))
