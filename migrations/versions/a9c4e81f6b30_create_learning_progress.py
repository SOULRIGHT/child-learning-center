"""create learning_subject and learning_progress_entry

Revision ID: a9c4e81f6b30
Revises: e3a7b16c4d20
Create Date: 2026-08-19

학습진도 과목 마스터와 스냅샷 테이블만 추가한다.
DailyPoints/PointsHistory/Book/ChildReading/ManualPointPreset 등은 ALTER/DROP 하지 않는다.
기본 과목(korean, math, ssen)은 key 기준 없으면 insert 하므로 재실행해도 중복되지 않는다.
이미 math/ssen이 있는 DB에는 korean만 추가하고 기존 row는 덮어쓰지 않는다.
"""
from alembic import op
import sqlalchemy as sa


revision = 'a9c4e81f6b30'
down_revision = 'e3a7b16c4d20'
branch_labels = None
depends_on = None

DEFAULT_SUBJECTS = (
    ('korean', '국어', 10),
    ('math', '수학', 20),
    ('ssen', '쎈', 30),
)


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'learning_subject' not in tables:
        op.create_table(
            'learning_subject',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('key', sa.String(length=64), nullable=False),
            sa.Column('name', sa.String(length=80), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_learning_subject_key', 'learning_subject', ['key'], unique=True)
        op.create_index('ix_learning_subject_sort_order', 'learning_subject', ['sort_order'], unique=False)

    for key, name, sort_order in DEFAULT_SUBJECTS:
        conn.execute(
            sa.text(
                "INSERT INTO learning_subject "
                "(key, name, is_active, sort_order) "
                "SELECT :key, :name, :active, :sort_order "
                "WHERE NOT EXISTS (SELECT 1 FROM learning_subject WHERE key = :key)"
            ),
            {
                'key': key,
                'name': name,
                'active': True,
                'sort_order': sort_order,
            },
        )

    tables = sa.inspect(conn).get_table_names()
    if 'learning_progress_entry' not in tables:
        op.create_table(
            'learning_progress_entry',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('child_id', sa.Integer(), sa.ForeignKey('child.id'), nullable=False),
            sa.Column(
                'learning_subject_id',
                sa.Integer(),
                sa.ForeignKey('learning_subject.id'),
                nullable=False,
            ),
            sa.Column('recorded_on', sa.Date(), nullable=False),
            sa.Column('textbook_title', sa.String(length=120), nullable=False),
            sa.Column('page', sa.Integer(), nullable=False),
            sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.UniqueConstraint(
                'child_id',
                'learning_subject_id',
                'recorded_on',
                name='uq_progress_child_subject_date',
            ),
        )
        op.create_index(
            'ix_learning_progress_entry_child_id',
            'learning_progress_entry',
            ['child_id'],
            unique=False,
        )
        op.create_index(
            'ix_learning_progress_entry_learning_subject_id',
            'learning_progress_entry',
            ['learning_subject_id'],
            unique=False,
        )
        op.create_index(
            'ix_learning_progress_entry_recorded_on',
            'learning_progress_entry',
            ['recorded_on'],
            unique=False,
        )
        op.create_index(
            'ix_progress_child_recorded_on',
            'learning_progress_entry',
            ['child_id', 'recorded_on'],
            unique=False,
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'learning_progress_entry' in tables:
        op.drop_index('ix_progress_child_recorded_on', table_name='learning_progress_entry')
        op.drop_index('ix_learning_progress_entry_recorded_on', table_name='learning_progress_entry')
        op.drop_index('ix_learning_progress_entry_learning_subject_id', table_name='learning_progress_entry')
        op.drop_index('ix_learning_progress_entry_child_id', table_name='learning_progress_entry')
        op.drop_table('learning_progress_entry')
    if 'learning_subject' in tables:
        op.drop_index('ix_learning_subject_sort_order', table_name='learning_subject')
        op.drop_index('ix_learning_subject_key', table_name='learning_subject')
        op.drop_table('learning_subject')
