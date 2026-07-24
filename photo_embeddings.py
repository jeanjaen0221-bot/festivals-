"""DINOv2 embedding persistence and similarity helpers for item photos."""
import hashlib
import os
from functools import lru_cache
from datetime import datetime, timezone
from io import BytesIO

import numpy as np

DEFAULT_MODEL_VERSION = "dinov2_vits14"
READY = "ready"
FAILED = "failed"
INVALIDATED = "invalidated"


def current_model_version() -> str:
    return os.environ.get("PHOTO_EMBEDDING_MODEL_VERSION", DEFAULT_MODEL_VERSION)


def image_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@lru_cache(maxsize=1)
def _load_dinov2(model_version: str):
    import torch
    model = torch.hub.load("facebookresearch/dinov2", model_version)
    model.eval()
    return model


def _embed_dinov2(data: bytes) -> np.ndarray:
    """Return a normalized float32 DINOv2 vector; model loading remains lazy."""
    from PIL import Image
    import torch

    image = Image.open(BytesIO(data)).convert("RGB")
    model = _load_dinov2(current_model_version())
    # DINOv2's ImageNet preprocessing is intentionally kept alongside its model.
    from torchvision import transforms
    transform = transforms.Compose([
        transforms.Resize(256), transforms.CenterCrop(224), transforms.ToTensor(),
        transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
    ])
    with torch.no_grad():
        vector = model(transform(image).unsqueeze(0)).squeeze(0).cpu().numpy()
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


def item_embedding_similarity(item1, item2) -> float:
    """Best cosine similarity across *persisted ready* embeddings of both items."""
    vectors1 = _ready_vectors(item1)
    vectors2 = _ready_vectors(item2)
    if not vectors1 or not vectors2:
        return 0.0
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
