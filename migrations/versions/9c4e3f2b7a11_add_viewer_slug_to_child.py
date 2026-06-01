"""add viewer_slug to child

Revision ID: 9c4e3f2b7a11
Revises: 251520942c74
Create Date: 2026-05-24 01:42:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c4e3f2b7a11'
down_revision = '251520942c74'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [c['name'] for c in inspector.get_columns('child')]
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('child')]

    if 'viewer_slug' not in existing_columns:
        op.add_column('child', sa.Column('viewer_slug', sa.String(length=24), nullable=True))

    if 'ix_child_viewer_slug' not in existing_indexes:
        op.create_index('ix_child_viewer_slug', 'child', ['viewer_slug'], unique=True)


def downgrade():
    op.drop_index('ix_child_viewer_slug', table_name='child')
    op.drop_column('child', 'viewer_slug')
