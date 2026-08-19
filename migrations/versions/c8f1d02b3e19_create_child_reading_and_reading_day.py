"""create child_reading and reading_day tables

Revision ID: c8f1d02b3e19
Revises: b7e4c91a2d08
Create Date: 2026-08-19

ChildReading / ReadingDay 신규 테이블과 필요한 FK, unique/index 만 추가한다.
기존 User/Child/DailyPoints/PointsHistory/Book 테이블은 ALTER/DROP 하지 않는다.
"""
from alembic import op
import sqlalchemy as sa


revision = 'c8f1d02b3e19'
down_revision = 'b7e4c91a2d08'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    unexpected = {
        'user', 'child', 'daily_points', 'points_history', 'book',
        'learning_record', 'child_note',
    }
    # 기존 운영 테이블을 이 migration에서 바꾸지 않는다. 존재 여부만 확인.
    _ = unexpected

    if 'child_reading' not in tables:
        op.create_table(
            'child_reading',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('child_id', sa.Integer(), nullable=False),
            sa.Column('book_id', sa.Integer(), nullable=False),
            sa.Column('started_on', sa.Date(), nullable=False),
            sa.Column('completed_on', sa.Date(), nullable=True),
            sa.Column('ended_on', sa.Date(), nullable=True),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='in_progress'),
            sa.Column('program_type', sa.String(length=32), nullable=False, server_default='general'),
            sa.Column('policy_version', sa.String(length=32), nullable=False, server_default='general_v2'),
            sa.Column('created_by_user_id', sa.Integer(), nullable=False),
            sa.Column('actor_type', sa.String(length=16), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['child_id'], ['child.id']),
            sa.ForeignKeyConstraint(['book_id'], ['book.id']),
            sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id']),
        )
        op.create_index('ix_child_reading_child_id', 'child_reading', ['child_id'], unique=False)
        op.create_index('ix_child_reading_book_id', 'child_reading', ['book_id'], unique=False)
        op.create_index('ix_child_reading_status', 'child_reading', ['status'], unique=False)
        op.execute(
            "CREATE UNIQUE INDEX uq_child_reading_one_in_progress "
            "ON child_reading (child_id) WHERE status = 'in_progress'"
        )

    tables = inspector.get_table_names()
    if 'reading_day' not in tables:
        op.create_table(
            'reading_day',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('child_reading_id', sa.Integer(), nullable=False),
            sa.Column('date', sa.Date(), nullable=False),
            sa.Column('review_text', sa.Text(), nullable=True),
            sa.Column('created_by_user_id', sa.Integer(), nullable=False),
            sa.Column('actor_type', sa.String(length=16), nullable=False),
            sa.Column('policy_version', sa.String(length=32), nullable=False, server_default='general_v2'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['child_reading_id'], ['child_reading.id']),
            sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id']),
            sa.UniqueConstraint('child_reading_id', 'date', name='uq_reading_day_reading_date'),
        )
        op.create_index('ix_reading_day_child_reading_id', 'reading_day', ['child_reading_id'], unique=False)
        op.create_index('ix_reading_day_date', 'reading_day', ['date'], unique=False)


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'reading_day' in tables:
        op.drop_index('ix_reading_day_date', table_name='reading_day')
        op.drop_index('ix_reading_day_child_reading_id', table_name='reading_day')
        op.drop_table('reading_day')
    if 'child_reading' in tables:
        op.execute('DROP INDEX IF EXISTS uq_child_reading_one_in_progress')
        op.drop_index('ix_child_reading_status', table_name='child_reading')
        op.drop_index('ix_child_reading_book_id', table_name='child_reading')
        op.drop_index('ix_child_reading_child_id', table_name='child_reading')
        op.drop_table('child_reading')
