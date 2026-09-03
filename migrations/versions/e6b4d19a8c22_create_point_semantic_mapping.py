"""create point_semantic_mapping table

Revision ID: e6b4d19a8c22
Revises: d9e1b24c7a03
Create Date: 2026-09-03

수동 label 의미 mapping 테이블만 추가한다.
DailyPoints/PointsHistory 등 기존 원장은 ALTER/DROP 하지 않는다.
아동/사용자 개인정보 컬럼을 두지 않는다.
"""
from alembic import op
import sqlalchemy as sa


revision = 'e6b4d19a8c22'
down_revision = 'd9e1b24c7a03'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'point_semantic_mapping' in tables:
        return
    op.create_table(
        'point_semantic_mapping',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('normalized_label', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=64), nullable=False),
        sa.Column('subject_key', sa.String(length=64), nullable=True),
        sa.Column('item_key', sa.String(length=64), nullable=True),
        sa.Column('source', sa.String(length=32), nullable=False, server_default='semantic_llm'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index(
        'ix_point_semantic_mapping_normalized_label',
        'point_semantic_mapping',
        ['normalized_label'],
        unique=True,
    )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'point_semantic_mapping' not in tables:
        return
    op.drop_index(
        'ix_point_semantic_mapping_normalized_label',
        table_name='point_semantic_mapping',
    )
    op.drop_table('point_semantic_mapping')
