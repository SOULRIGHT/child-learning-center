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
    with op.batch_alter_table('child', schema=None) as batch_op:
        batch_op.add_column(sa.Column('viewer_slug', sa.String(length=24), nullable=True))
        batch_op.create_index('ix_child_viewer_slug', ['viewer_slug'], unique=True)


def downgrade():
    with op.batch_alter_table('child', schema=None) as batch_op:
        batch_op.drop_index('ix_child_viewer_slug')
        batch_op.drop_column('viewer_slug')
