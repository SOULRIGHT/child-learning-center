"""ensure default learning subjects and exemption usage snapshot

Revision ID: e5b2c81d4a70
Revises: d4e8a01c5b92
Create Date: 2026-08-20

이미 적용된 a9c4e81f6b30 을 다시 수정하지 않는다.
learning_subject 기본 3과목(korean/math/ssen)이 없으면 key 기준 WHERE NOT EXISTS 로만 보충한다.
기존 row의 이름/순서/활성 값은 덮어쓰지 않는다.
로컬에 남아 있을 수 있는 is_exemption_eligible / exemption_usage.learning_subject_id 는
Step 6 미커밋 스키마를 snapshot 구조로 수렴시킨다.
"""
from alembic import op
import sqlalchemy as sa


revision = 'e5b2c81d4a70'
down_revision = 'd4e8a01c5b92'
branch_labels = None
depends_on = None

DEFAULT_SUBJECTS = (
    ('korean', '국어', 10),
    ('math', '수학', 20),
    ('ssen', '쎈', 30),
)


def _seed_default_subjects(conn):
    inspector = sa.inspect(conn)
    if 'learning_subject' not in inspector.get_table_names():
        return
    for key, name, sort_order in DEFAULT_SUBJECTS:
        conn.execute(
            sa.text(
                "INSERT INTO learning_subject "
                "(key, name, is_active, sort_order) "
                "SELECT :key, :name, 1, :sort_order "
                "WHERE NOT EXISTS (SELECT 1 FROM learning_subject WHERE key = :key)"
            ),
            {'key': key, 'name': name, 'sort_order': sort_order},
        )


def _rebuild_exemption_usage_snapshot(conn):
    inspector = sa.inspect(conn)
    if 'exemption_usage' not in inspector.get_table_names():
        return
    cols = {col['name'] for col in inspector.get_columns('exemption_usage')}
    if 'subject_key' in cols and 'learning_subject_id' not in cols:
        return
    if 'learning_subject_id' not in cols:
        return

    op.create_table(
        '_exemption_usage_snapshot',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('exemption_ticket_id', sa.Integer(), nullable=False),
        sa.Column('subject_key', sa.String(length=64), nullable=False),
        sa.Column('subject_name', sa.String(length=80), nullable=False),
        sa.Column('used_on', sa.Date(), nullable=False),
        sa.Column('recorded_by_user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['exemption_ticket_id'], ['exemption_ticket.id']),
        sa.ForeignKeyConstraint(['recorded_by_user_id'], ['user.id']),
    )
    conn.execute(
        sa.text(
            "INSERT INTO _exemption_usage_snapshot "
            "(id, exemption_ticket_id, subject_key, subject_name, used_on, "
            " recorded_by_user_id, created_at) "
            "SELECT u.id, u.exemption_ticket_id, "
            "COALESCE(s.key, 'unknown'), "
            "COALESCE(s.name, '알 수 없음'), "
            "u.used_on, u.recorded_by_user_id, u.created_at "
            "FROM exemption_usage AS u "
            "LEFT JOIN learning_subject AS s ON s.id = u.learning_subject_id"
        )
    )
    usage_indexes = {idx['name'] for idx in inspector.get_indexes('exemption_usage')}
    if 'ix_exemption_usage_used_on' in usage_indexes:
        op.drop_index('ix_exemption_usage_used_on', table_name='exemption_usage')
    if 'ix_exemption_usage_learning_subject_id' in usage_indexes:
        op.drop_index('ix_exemption_usage_learning_subject_id', table_name='exemption_usage')
    op.drop_table('exemption_usage')
    op.rename_table('_exemption_usage_snapshot', 'exemption_usage')
    op.create_index(
        'ix_exemption_usage_subject_key',
        'exemption_usage',
        ['subject_key'],
        unique=False,
    )
    op.create_index('ix_exemption_usage_used_on', 'exemption_usage', ['used_on'], unique=False)
    op.create_index(
        'uq_exemption_usage_ticket',
        'exemption_usage',
        ['exemption_ticket_id'],
        unique=True,
    )


def upgrade():
    conn = op.get_bind()
    _seed_default_subjects(conn)

    inspector = sa.inspect(conn)
    if 'learning_subject' in inspector.get_table_names():
        subject_cols = {col['name'] for col in inspector.get_columns('learning_subject')}
        if 'is_exemption_eligible' in subject_cols:
            with op.batch_alter_table('learning_subject') as batch_op:
                batch_op.drop_column('is_exemption_eligible')

    _rebuild_exemption_usage_snapshot(conn)


def downgrade():
    """기본 과목 seed 와 snapshot 이관은 되돌리지 않는다."""
    return
