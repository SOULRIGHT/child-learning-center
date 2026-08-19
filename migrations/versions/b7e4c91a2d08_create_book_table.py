"""create book table

Revision ID: b7e4c91a2d08
Revises: 9c4e3f2b7a11
Create Date: 2026-08-19

Book 신규 테이블과 normalized_key index 만 추가한다.
기존 Child/User/DailyPoints 등 운영 테이블은 변경하지 않는다.
"""
from alembic import op
import sqlalchemy as sa


revision = 'b7e4c91a2d08'
down_revision = '9c4e3f2b7a11'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'book' in tables:
        return

    op.create_table(
        'book',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('author', sa.String(length=255), nullable=True),
        sa.Column('normalized_key', sa.String(length=255), nullable=False),
        sa.Column('is_recommended', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('grade_band', sa.String(length=16), nullable=True),
        sa.Column('is_challenge_eligible', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('ai_difficulty_low', sa.Integer(), nullable=True),
        sa.Column('ai_difficulty_high', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_book_normalized_key', 'book', ['normalized_key'], unique=False)


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'book' not in tables:
        return
    op.drop_index('ix_book_normalized_key', table_name='book')
    op.drop_table('book')
