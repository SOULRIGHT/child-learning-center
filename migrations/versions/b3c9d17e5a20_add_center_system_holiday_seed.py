"""add center_system_holiday_seed year initialization table

Revision ID: b3c9d17e5a20
Revises: a2b8c4d6e1f0
Create Date: 2026-09-08

연도별 법정공휴일 최초 제공 상태를 명시적으로 저장한다.
center_non_study_day row 개수로 seed 여부를 추론하지 않기 위한 additive 테이블이다.
기존 비학습일/공휴일 row, 요일 달력, 학습 세션은 ALTER/DROP 하지 않는다.
"""
from alembic import op
import sqlalchemy as sa


revision = 'b3c9d17e5a20'
down_revision = 'a2b8c4d6e1f0'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'center_system_holiday_seed' in tables:
        return
    op.create_table(
        'center_system_holiday_seed',
        sa.Column('year', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('seeded_at', sa.DateTime(), nullable=False),
    )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'center_system_holiday_seed' in inspector.get_table_names():
        op.drop_table('center_system_holiday_seed')
