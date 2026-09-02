"""add missing growth_ai_attempt.safety_categories

Revision ID: d9e1b24c7a03
Revises: c3a8f17b2d01
Create Date: 2026-09-02

c3a8f17b2d01 은 테이블이 이미 있으면 no-op 한다.
create_all 로 만들어진 기존 테이블에 누락 컬럼만 추가한다.
"""
from alembic import op
import sqlalchemy as sa


revision = 'd9e1b24c7a03'
down_revision = 'c3a8f17b2d01'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'growth_ai_attempt' not in tables:
        return
    columns = {col['name'] for col in inspector.get_columns('growth_ai_attempt')}
    if 'safety_categories' not in columns:
        op.add_column(
            'growth_ai_attempt',
            sa.Column('safety_categories', sa.JSON(), nullable=True),
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'growth_ai_attempt' not in tables:
        return
    columns = {col['name'] for col in inspector.get_columns('growth_ai_attempt')}
    if 'safety_categories' in columns:
        op.drop_column('growth_ai_attempt', 'safety_categories')
