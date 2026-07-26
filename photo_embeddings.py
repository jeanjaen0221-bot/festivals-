"""DINOv2 embedding persistence and similarity helpers for item photos.

Reuses the single DINOv2 model already loaded by ``visual_matcher`` (Hugging
Face ``facebook/dinov2-small``) so a process never keeps two separate DINOv2
weights sets in memory.
"""
import hashlib
import os
from datetime import datetime, timezone

import numpy as np

READY = "ready"
FAILED = "failed"
INVALIDATED = "invalidated"


def current_model_version() -> str:
    from visual_matcher import MODEL_ID
    return os.environ.get("PHOTO_EMBEDDING_MODEL_VERSION", MODEL_ID)


def image_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _embed_dinov2(data: bytes) -> np.ndarray:
    """Return a normalized float32 DINOv2 vector; model loading remains lazy."""
    from visual_matcher import embed_image_bytes

    vector = embed_image_bytes(data)
    if vector is None:
        raise RuntimeError("Le modèle visuel DINOv2 est indisponible")
    vector = np.asarray(vector, dtype=np.float32)
    norm = np.linalg.norm(vector)
    if not norm:
        raise ValueError("DINOv2 returned a zero vector")
    return vector / norm


def ensure_photo_embedding(photo, *, force: bool = False):
    """Create or refresh one embedding, copying an existing identical image when possible.

    Errors are recorded on the embedding row rather than failing the photo upload.
    """
    from app import db
    from models import PhotoEmbedding

    version = current_model_version()
    data = bytes(photo.data or b"")
    if not data:
        return None
    digest = image_hash(data)
    record = PhotoEmbedding.query.filter_by(item_photo_id=photo.id, model_version=version).first()
    if record and record.status == READY and record.image_hash == digest and not force:
        return record
    if not record:
        record = PhotoEmbedding(item_photo_id=photo.id, model_version=version)
        db.session.add(record)
    record.image_hash = digest
    record.updated_at = datetime.now(timezone.utc)

    # A byte-identical image does not need another model inference.
    duplicate = PhotoEmbedding.query.filter(
        PhotoEmbedding.item_photo_id != photo.id,
        PhotoEmbedding.model_version == version,
        PhotoEmbedding.image_hash == digest,
        PhotoEmbedding.status == READY,
    ).first()
    try:
        vector = np.frombuffer(duplicate.embedding, dtype=np.float32).copy() if duplicate else _embed_dinov2(data)
        record.embedding = vector.astype(np.float32).tobytes()
        record.embedding_dimension = int(vector.size)
        record.status = READY
    except Exception as exc:  # Availability is operational, not a failed upload.
        record.embedding = None
        record.embedding_dimension = None
        record.status = FAILED
        record.error_message = str(exc)[:500]
    return record


def invalidate_photo_embedding(photo) -> None:
    """Mark records stale when photo bytes are replaced before the next indexing run."""
    from models import PhotoEmbedding
    for record in PhotoEmbedding.query.filter_by(item_photo_id=photo.id).all():
        record.status = INVALIDATED


def item_embedding_similarity(item1, item2) -> float | None:
    """Best cosine similarity across *persisted ready* embeddings of both items.

    Returns ``None`` (not 0.0) when no ready embedding exists on either side,
    so an absent comparison is never confused with an actual low similarity.
    """
    vectors1 = _ready_vectors(item1)
    vectors2 = _ready_vectors(item2)
    if not vectors1 or not vectors2:
        return None
    return max(float(np.clip(np.dot(a, b), -1.0, 1.0)) for a in vectors1 for b in vectors2)


def _ready_vectors(item):
    result = []
    version = current_model_version()
    for photo in getattr(item, "photos", []):
        for embedding in getattr(photo, "embeddings", []):
            if embedding.model_version == version and embedding.status == READY and embedding.embedding:
                vector = np.frombuffer(embedding.embedding, dtype=np.float32)
                if embedding.embedding_dimension == vector.size and vector.size:
                    result.append(vector)
    return result
