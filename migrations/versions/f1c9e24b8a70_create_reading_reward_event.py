"""create reading_reward_event table

Revision ID: f1c9e24b8a70
Revises: a9c4e81f6b30
Create Date: 2026-08-20

추천독서 시작/완독 보상 원장만 추가한다.
Book 추천도서 실제 제목은 seed하지 않는다.
DailyPoints/PointsHistory/Book/ChildReading/ReadingDay/ManualPointPreset/
LearningSubject/LearningProgressEntry/User/Child 는 ALTER/DROP 하지 않는다.
"""
from alembic import op
import sqlalchemy as sa


revision = 'f1c9e24b8a70'
down_revision = 'a9c4e81f6b30'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'reading_reward_event' not in tables:
        op.create_table(
            'reading_reward_event',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('child_reading_id', sa.Integer(), nullable=False),
            sa.Column('event_type', sa.String(length=32), nullable=False),
            sa.Column('points', sa.Integer(), nullable=False),
            sa.Column('awarded_on', sa.Date(), nullable=False),
            sa.Column('policy_version', sa.String(length=32), nullable=False, server_default='recommended_v1'),
            sa.Column('created_by_user_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
            sa.Column('revoked_by_user_id', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['child_reading_id'], ['child_reading.id']),
            sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id']),
            sa.ForeignKeyConstraint(['revoked_by_user_id'], ['user.id']),
            sa.UniqueConstraint(
                'child_reading_id',
                'event_type',
                name='uq_reading_reward_event_reading_type',
            ),
        )
        op.create_index(
            'ix_reading_reward_event_child_reading_id',
            'reading_reward_event',
            ['child_reading_id'],
            unique=False,
        )
        op.create_index(
            'ix_reading_reward_event_awarded_on',
            'reading_reward_event',
            ['awarded_on'],
            unique=False,
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'reading_reward_event' in tables:
        op.drop_index('ix_reading_reward_event_awarded_on', table_name='reading_reward_event')
        op.drop_index('ix_reading_reward_event_child_reading_id', table_name='reading_reward_event')
        op.drop_table('reading_reward_event')
