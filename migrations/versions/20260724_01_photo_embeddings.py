"""add persisted DINOv2 photo embeddings

Revision ID: 20260724_01
Revises:
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = '20260724_01'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'photo_embeddings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('item_photo_id', sa.Integer(), sa.ForeignKey('item_photos.id', ondelete='CASCADE'), nullable=False),
        sa.Column('model_version', sa.String(length=100), nullable=False),
        sa.Column('image_hash', sa.String(length=64), nullable=False),
        sa.Column('embedding', sa.LargeBinary(), nullable=True),
        sa.Column('embedding_dimension', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('item_photo_id', 'model_version', name='uq_photo_embedding_photo_model'),
    )
    op.create_index('ix_photo_embeddings_item_photo_id', 'photo_embeddings', ['item_photo_id'])
    op.create_index('ix_photo_embeddings_model_version', 'photo_embeddings', ['model_version'])
    op.create_index('ix_photo_embeddings_image_hash', 'photo_embeddings', ['image_hash'])
    op.create_index('ix_photo_embeddings_status', 'photo_embeddings', ['status'])


def downgrade():
    op.drop_table('photo_embeddings')
