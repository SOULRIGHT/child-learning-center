"""create manual_point_preset table and default rows

Revision ID: e3a7b16c4d20
Revises: c8f1d02b3e19
Create Date: 2026-08-19

수동 포인트 프리셋 테이블만 추가한다.
DailyPoints/PointsHistory/Book/ChildReading 등 기존 테이블은 ALTER/DROP 하지 않는다.
기본 5개 row는 key 기준 upsert(없으면 insert) 하므로 재실행해도 중복되지 않는다.
"""
from alembic import op
import sqlalchemy as sa


revision = 'e3a7b16c4d20'
down_revision = 'c8f1d02b3e19'
branch_labels = None
depends_on = None

DEFAULT_PRESETS = (
    ('textbook', '교재', 3000, '교재 완료', 10),
    ('print', '프린트', -100, '프린트 사용', 20),
    ('pencil', '연필', -300, '연필 구매', 30),
    ('eraser', '지우개', -500, '지우개 구매', 40),
    ('pencil_case', '필통', -1000, '필통 구매', 50),
)


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'manual_point_preset' not in tables:
        op.create_table(
            'manual_point_preset',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('key', sa.String(length=64), nullable=False),
            sa.Column('label', sa.String(length=80), nullable=False),
            sa.Column('default_points', sa.Integer(), nullable=False),
            sa.Column('default_reason', sa.String(length=80), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_manual_point_preset_key', 'manual_point_preset', ['key'], unique=True)
        op.create_index('ix_manual_point_preset_sort_order', 'manual_point_preset', ['sort_order'], unique=False)

    for key, label, points, reason, sort_order in DEFAULT_PRESETS:
        conn.execute(
            sa.text(
                "INSERT INTO manual_point_preset "
                "(key, label, default_points, default_reason, is_active, sort_order) "
                "SELECT :key, :label, :points, :reason, :active, :sort_order "
                "WHERE NOT EXISTS (SELECT 1 FROM manual_point_preset WHERE key = :key)"
            ),
            {
                'key': key,
                'label': label,
                'points': points,
                'reason': reason,
                'active': True,
                'sort_order': sort_order,
            },
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'manual_point_preset' not in tables:
        return
    op.drop_index('ix_manual_point_preset_sort_order', table_name='manual_point_preset')
    op.drop_index('ix_manual_point_preset_key', table_name='manual_point_preset')
    op.drop_table('manual_point_preset')
