"""add exemption ticket ledger and reward_mode

Revision ID: d4e8a01c5b92
Revises: f1c9e24b8a70
Create Date: 2026-08-20

5~6학년 추천독서 보상 방식과 학습 면제권 장부만 추가한다.
면제 과목은 LearningSubject FK가 아니라 사용 당시 snapshot(key/name)으로 보존한다.
DailyPoints/PointsHistory/Book/ReadingDay/ReadingRewardEvent/
ManualPointPreset/LearningProgressEntry 는 ALTER/DROP 하지 않는다.
"""
from alembic import op
import sqlalchemy as sa


revision = 'd4e8a01c5b92'
down_revision = 'f1c9e24b8a70'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    reading_cols = {col['name'] for col in inspector.get_columns('child_reading')}
    if 'reward_mode' not in reading_cols:
        op.add_column(
            'child_reading',
            sa.Column('reward_mode', sa.String(length=16), nullable=True),
        )

    tables = inspector.get_table_names()
    if 'exemption_ticket' not in tables:
        op.create_table(
            'exemption_ticket',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('child_id', sa.Integer(), nullable=False),
            sa.Column('issued_on', sa.Date(), nullable=False),
            sa.Column('expires_on', sa.Date(), nullable=False),
            sa.Column('status', sa.String(length=16), nullable=False, server_default='active'),
            sa.Column('policy_version', sa.String(length=32), nullable=False, server_default='v1'),
            sa.Column('issued_by_user_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
            sa.Column('revoked_by_user_id', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['child_id'], ['child.id']),
            sa.ForeignKeyConstraint(['issued_by_user_id'], ['user.id']),
            sa.ForeignKeyConstraint(['revoked_by_user_id'], ['user.id']),
        )
        op.create_index('ix_exemption_ticket_child_id', 'exemption_ticket', ['child_id'], unique=False)
        op.create_index('ix_exemption_ticket_issued_on', 'exemption_ticket', ['issued_on'], unique=False)
        op.create_index('ix_exemption_ticket_status', 'exemption_ticket', ['status'], unique=False)
        op.create_index(
            'ix_exemption_ticket_child_status',
            'exemption_ticket',
            ['child_id', 'status'],
            unique=False,
        )
        op.execute(
            "CREATE UNIQUE INDEX uq_exemption_ticket_one_active "
            "ON exemption_ticket (child_id) WHERE status = 'active'"
        )

    tables = sa.inspect(conn).get_table_names()
    if 'exemption_ticket_source' not in tables:
        op.create_table(
            'exemption_ticket_source',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('exemption_ticket_id', sa.Integer(), nullable=False),
            sa.Column('child_reading_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['exemption_ticket_id'], ['exemption_ticket.id']),
            sa.ForeignKeyConstraint(['child_reading_id'], ['child_reading.id']),
            sa.UniqueConstraint(
                'exemption_ticket_id',
                'child_reading_id',
                name='uq_exemption_source_ticket_reading',
            ),
        )
        op.create_index(
            'ix_exemption_ticket_source_exemption_ticket_id',
            'exemption_ticket_source',
            ['exemption_ticket_id'],
            unique=False,
        )
        op.create_index(
            'ix_exemption_ticket_source_child_reading_id',
            'exemption_ticket_source',
            ['child_reading_id'],
            unique=False,
        )

    tables = sa.inspect(conn).get_table_names()
    if 'exemption_usage' not in tables:
        op.create_table(
            'exemption_usage',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('exemption_ticket_id', sa.Integer(), nullable=False),
            sa.Column('subject_key', sa.String(length=64), nullable=False),
            sa.Column('subject_name', sa.String(length=80), nullable=False),
            sa.Column('used_on', sa.Date(), nullable=False),
            sa.Column('recorded_by_user_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['exemption_ticket_id'], ['exemption_ticket.id']),
            sa.ForeignKeyConstraint(['recorded_by_user_id'], ['user.id']),
            sa.UniqueConstraint('exemption_ticket_id', name='uq_exemption_usage_ticket'),
        )
        op.create_index(
            'ix_exemption_usage_subject_key',
            'exemption_usage',
            ['subject_key'],
            unique=False,
        )
        op.create_index('ix_exemption_usage_used_on', 'exemption_usage', ['used_on'], unique=False)


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'exemption_usage' in tables:
        usage_indexes = {idx['name'] for idx in inspector.get_indexes('exemption_usage')}
        if 'ix_exemption_usage_used_on' in usage_indexes:
            op.drop_index('ix_exemption_usage_used_on', table_name='exemption_usage')
        if 'ix_exemption_usage_subject_key' in usage_indexes:
            op.drop_index('ix_exemption_usage_subject_key', table_name='exemption_usage')
        if 'ix_exemption_usage_learning_subject_id' in usage_indexes:
            op.drop_index('ix_exemption_usage_learning_subject_id', table_name='exemption_usage')
        op.drop_table('exemption_usage')
    if 'exemption_ticket_source' in tables:
        op.drop_index('ix_exemption_ticket_source_child_reading_id', table_name='exemption_ticket_source')
        op.drop_index('ix_exemption_ticket_source_exemption_ticket_id', table_name='exemption_ticket_source')
        op.drop_table('exemption_ticket_source')
    if 'exemption_ticket' in tables:
        op.execute('DROP INDEX IF EXISTS uq_exemption_ticket_one_active')
        op.drop_index('ix_exemption_ticket_child_status', table_name='exemption_ticket')
        op.drop_index('ix_exemption_ticket_status', table_name='exemption_ticket')
        op.drop_index('ix_exemption_ticket_issued_on', table_name='exemption_ticket')
        op.drop_index('ix_exemption_ticket_child_id', table_name='exemption_ticket')
        op.drop_table('exemption_ticket')

    reading_cols = {col['name'] for col in inspector.get_columns('child_reading')}
    if 'reward_mode' in reading_cols:
        op.drop_column('child_reading', 'reward_mode')
