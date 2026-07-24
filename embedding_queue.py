"""File durable et traitement différé des embeddings d'images."""
import json
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app import db
from models import BackgroundJob, ItemPhoto

logger = logging.getLogger(__name__)
JOB_TYPE = 'generate_visual_embedding'


def enqueue_visual_embedding(photo: ItemPhoto, max_attempts: int = 3) -> BackgroundJob:
    """Ajoute le job dans la même transaction que la photo, sans charger le modèle."""
    photo.embedding_status = 'pending'
    photo.embedding_error = None
    job = BackgroundJob(job_type=JOB_TYPE, item_photo_id=photo.id, max_attempts=max_attempts)
    db.session.add(job)
    return job


def _now():
    return datetime.now(timezone.utc)


def claim_next_job():
    """Réserve atomiquement un job; SKIP LOCKED permet plusieurs workers PostgreSQL."""
    now = _now()
    _recover_stale_jobs(now)
    query = (BackgroundJob.query.filter_by(job_type=JOB_TYPE, status='pending')
             .filter(BackgroundJob.available_at <= now)
             .order_by(BackgroundJob.created_at))
    if db.engine.dialect.name == 'postgresql':
        query = query.with_for_update(skip_locked=True)
    job = query.first()
    if job is None:
        return None
    job.status = 'processing'
    job.locked_at = now
    db.session.commit()
    return job.id


def _recover_stale_jobs(now):
    """Évite qu'un crash de worker ne bloque une photo indéfiniment."""
    cutoff = now - timedelta(minutes=int(os.environ.get('EMBEDDING_LOCK_TIMEOUT_MINUTES', '30')))
    stale_jobs = BackgroundJob.query.filter_by(job_type=JOB_TYPE, status='processing').filter(
        BackgroundJob.locked_at < cutoff
    ).all()
    for job in stale_jobs:
        job.attempts += 1
        job.last_error = 'Worker interrompu avant la fin du traitement'
        photo = db.session.get(ItemPhoto, job.item_photo_id)
        if job.attempts >= job.max_attempts:
            job.status = 'failed'
            if photo:
                photo.embedding_status, photo.embedding_error = 'failed', job.last_error
        else:
            job.status, job.available_at = 'pending', now
            if photo:
                photo.embedding_status, photo.embedding_error = 'pending', job.last_error
        logger.warning('embedding_job_stale job_id=%s photo_id=%s attempts=%s', job.id, job.item_photo_id, job.attempts)
    if stale_jobs:
        db.session.commit()


def process_job(job_id: int) -> bool:
    """Calcule un unique embedding; le modèle n'est importé que dans ce processus worker."""
    job = db.session.get(BackgroundJob, job_id)
    if not job or job.status != 'processing':
        return False
    photo = db.session.get(ItemPhoto, job.item_photo_id)
    try:
        if not photo or not photo.data:
            raise ValueError('Photo introuvable ou sans données binaires')
        from image_text_matcher import embed_image_bytes
        vector = embed_image_bytes(bytes(photo.data))
        if vector is None:
            raise RuntimeError("Le modèle n'a produit aucun embedding")
        photo.embedding = json.dumps(vector.tolist())
        photo.embedding_status = 'ready'
        photo.embedding_error = None
        photo.embedding_updated_at = _now()
        job.status = 'completed'
        job.last_error = None
        db.session.commit()
        logger.info('embedding_job_completed job_id=%s photo_id=%s', job.id, photo.id)
        return True
    except Exception as exc:
        db.session.rollback()
        return _handle_failure(job_id, str(exc))


def _handle_failure(job_id: int, error: str) -> bool:
    job = db.session.get(BackgroundJob, job_id)
    if job is None:
        return False
    photo = db.session.get(ItemPhoto, job.item_photo_id)
    job.attempts += 1
    job.last_error = error[:4000]
    if job.attempts >= job.max_attempts:
        job.status = 'failed'
        if photo:
            photo.embedding_status = 'failed'
            photo.embedding_error = job.last_error
            photo.embedding_updated_at = _now()
        logger.error('embedding_job_failed job_id=%s photo_id=%s attempts=%s error=%s', job.id, job.item_photo_id, job.attempts, job.last_error)
    else:
        job.status = 'pending'
        job.available_at = _now() + timedelta(minutes=2 ** (job.attempts - 1))
        if photo:
            photo.embedding_status = 'pending'
            photo.embedding_error = job.last_error
        logger.warning('embedding_job_retry job_id=%s photo_id=%s attempt=%s error=%s', job.id, job.item_photo_id, job.attempts, job.last_error)
    db.session.commit()
    return False


def retry_failed_jobs() -> int:
    """Réarme les erreurs terminales pour une reprise opérée explicitement."""
    now = _now()
    jobs = BackgroundJob.query.filter_by(job_type=JOB_TYPE, status='failed').all()
    for job in jobs:
        job.status, job.attempts, job.available_at, job.last_error = 'pending', 0, now, None
        if job.photo:
            job.photo.embedding_status, job.photo.embedding_error = 'pending', None
    db.session.commit()
    logger.info('embedding_jobs_requeued count=%s', len(jobs))
    return len(jobs)


def ensure_embedding_schema():
    """Met à niveau les installations existantes qui n'utilisent pas Alembic."""
    if db.engine.dialect.name != 'postgresql':
        return
    statements = (
        "ALTER TABLE item_photos ADD COLUMN IF NOT EXISTS embedding TEXT",
        "ALTER TABLE item_photos ADD COLUMN IF NOT EXISTS embedding_status VARCHAR(20) NOT NULL DEFAULT 'pending'",
        "ALTER TABLE item_photos ADD COLUMN IF NOT EXISTS embedding_error TEXT",
        "ALTER TABLE item_photos ADD COLUMN IF NOT EXISTS embedding_updated_at TIMESTAMP",
        "CREATE INDEX IF NOT EXISTS ix_item_photos_embedding_status ON item_photos (embedding_status)",
    )
    for statement in statements:
        db.session.execute(text(statement))
    db.session.commit()
