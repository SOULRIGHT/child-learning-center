"""Add cumulative_points field to Child model

Revision ID: 251520942c74
Revises: 
Create Date: 2025-08-11 00:59:39.073198

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '251520942c74'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [c['name'] for c in inspector.get_columns('child')]

    if 'cumulative_points' not in existing_columns:
        op.add_column('child', sa.Column('cumulative_points', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('child', 'cumulative_points')
