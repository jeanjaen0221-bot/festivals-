"""optional pgvector index for photo embeddings (apply manually after enabling extension)

Revision ID: 20260724_02_pgvector
Revises: 20260724_01
Create Date: 2026-07-24
"""
from alembic import op

revision = '20260724_02_pgvector'
down_revision = '20260724_01'
branch_labels = ('optional_pgvector',)
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    # Keep bytea as the source of truth. Populate this column with a controlled
    # backfill before using it for ANN queries in production.
    op.execute('ALTER TABLE photo_embeddings ADD COLUMN embedding_vector vector')
    op.execute("CREATE INDEX ix_photo_embeddings_vector_cosine ON photo_embeddings USING ivfflat (embedding_vector vector_cosine_ops) WITH (lists = 100) WHERE status = 'ready'")


def downgrade():
    op.execute('DROP INDEX IF EXISTS ix_photo_embeddings_vector_cosine')
    op.execute('ALTER TABLE photo_embeddings DROP COLUMN IF EXISTS embedding_vector')
