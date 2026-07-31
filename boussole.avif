"""add app_settings (registration_open toggle)

Revision ID: 20260727_01
Revises: 20260724_01
Create Date: 2026-07-27
"""
from alembic import op
import sqlalchemy as sa

revision = '20260727_01'
down_revision = '20260724_01'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'app_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('registration_open', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )


def downgrade():
    op.drop_table('app_settings')
