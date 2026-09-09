"""create growth vNext study session and calendar foundation

Revision ID: f7c2a19e4b80
Revises: e6b4d19a8c22
Create Date: 2026-09-07

학습 세션 / 과목별 요일 / 비학습일 / 세션 변경 이력만 추가한다.
LearningProgressEntry, LearningWorkbookPlan, CenterStudyCalendar,
ChildStudyWeekdays, DailyPoints, reading session 테이블은 ALTER/DROP 하지 않는다.
기존 진도 스냅샷을 start/end 로 추정해 backfill 하지 않는다.

테이블이 이미 있으면 CREATE TABLE 은 건너뛴다.
create_all 이 먼저 만든 경우에도 named index / partial unique 는 보정한다.
SQLite 는 기존 테이블에 CHECK 를 추가하지 못한다.
현재 모델 create_all 은 CHECK/FK 를 포함하므로 그 경로와는 일치한다.
"""
from alembic import op
import sqlalchemy as sa


revision = 'f7c2a19e4b80'
down_revision = 'e6b4d19a8c22'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'center_subject_study_weekdays' not in tables:
        op.create_table(
            'center_subject_study_weekdays',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('learning_subject_id', sa.Integer(), nullable=False),
            sa.Column('study_weekdays', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['learning_subject_id'], ['learning_subject.id']),
        )
        op.create_index(
            'ix_center_subject_study_weekdays_learning_subject_id',
            'center_subject_study_weekdays',
            ['learning_subject_id'],
            unique=True,
        )

    tables = sa.inspect(conn).get_table_names()
    if 'center_non_study_day' not in tables:
        op.create_table(
            'center_non_study_day',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('day', sa.Date(), nullable=False),
            sa.Column('source', sa.String(length=32), nullable=False, server_default='center'),
            sa.Column('label', sa.String(length=80), nullable=True),
            sa.Column('created_by_user_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id']),
            sa.UniqueConstraint('day', name='uq_center_non_study_day_day'),
            sa.CheckConstraint(
                "source IN ('center', 'system_holiday')",
                name='ck_center_non_study_day_source',
            ),
        )
        op.create_index(
            'ix_center_non_study_day_day',
            'center_non_study_day',
            ['day'],
            unique=False,
        )

    tables = sa.inspect(conn).get_table_names()
    if 'learning_study_session' not in tables:
        op.create_table(
            'learning_study_session',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('child_id', sa.Integer(), nullable=False),
            sa.Column('learning_subject_id', sa.Integer(), nullable=False),
            sa.Column('study_date', sa.Date(), nullable=False),
            sa.Column('textbook_title', sa.String(length=120), nullable=True),
            sa.Column('study_status', sa.String(length=32), nullable=False),
            sa.Column('start_page', sa.Integer(), nullable=True),
            sa.Column('end_page', sa.Integer(), nullable=True),
            sa.Column(
                'record_verification',
                sa.String(length=16),
                nullable=False,
                server_default='observed',
            ),
            sa.Column('recorded_by_user_id', sa.Integer(), nullable=False),
            sa.Column(
                'actor_type',
                sa.String(length=16),
                nullable=False,
                server_default='teacher',
            ),
            sa.Column('input_channel', sa.String(length=32), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['child_id'], ['child.id']),
            sa.ForeignKeyConstraint(['learning_subject_id'], ['learning_subject.id']),
            sa.ForeignKeyConstraint(['recorded_by_user_id'], ['user.id']),
            sa.CheckConstraint(
                "study_status IN ('studied', 'explicit_not_studied', 'unknown')",
                name='ck_learning_study_session_study_status',
            ),
            sa.CheckConstraint(
                "record_verification IN ('observed', 'verified')",
                name='ck_learning_study_session_record_verification',
            ),
            sa.CheckConstraint(
                "("
                "study_status = 'studied' AND start_page IS NOT NULL AND end_page IS NOT NULL "
                "AND start_page >= 1 AND start_page <= end_page"
                ") OR ("
                "study_status IN ('explicit_not_studied', 'unknown') "
                "AND start_page IS NULL AND end_page IS NULL"
                ")",
                name='ck_learning_study_session_pages_match_status',
            ),
        )
        op.create_index(
            'ix_learning_study_session_child_id',
            'learning_study_session',
            ['child_id'],
            unique=False,
        )
        op.create_index(
            'ix_learning_study_session_learning_subject_id',
            'learning_study_session',
            ['learning_subject_id'],
            unique=False,
        )
        op.create_index(
            'ix_learning_study_session_study_date',
            'learning_study_session',
            ['study_date'],
            unique=False,
        )
        op.create_index(
            'ix_learning_study_session_child_subject_date',
            'learning_study_session',
            ['child_id', 'learning_subject_id', 'study_date'],
            unique=False,
        )
        op.execute(
            "CREATE UNIQUE INDEX uq_learning_study_session_non_range_day "
            "ON learning_study_session (child_id, learning_subject_id, study_date) "
            "WHERE study_status IN ('explicit_not_studied', 'unknown')"
        )

    tables = sa.inspect(conn).get_table_names()
    if 'learning_study_session_change' not in tables:
        op.create_table(
            'learning_study_session_change',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('session_id', sa.Integer(), nullable=True),
            sa.Column('child_id', sa.Integer(), nullable=False),
            sa.Column('learning_subject_id', sa.Integer(), nullable=False),
            sa.Column('study_date', sa.Date(), nullable=False),
            sa.Column('event_type', sa.String(length=16), nullable=False),
            sa.Column('before_payload', sa.JSON(), nullable=True),
            sa.Column('after_payload', sa.JSON(), nullable=True),
            sa.Column('change_reason', sa.Text(), nullable=True),
            sa.Column('changed_by_user_id', sa.Integer(), nullable=False),
            sa.Column('changed_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ['session_id'],
                ['learning_study_session.id'],
                ondelete='SET NULL',
            ),
            sa.ForeignKeyConstraint(['child_id'], ['child.id']),
            sa.ForeignKeyConstraint(['learning_subject_id'], ['learning_subject.id']),
            sa.ForeignKeyConstraint(['changed_by_user_id'], ['user.id']),
            sa.CheckConstraint(
                "event_type IN ('created', 'updated', 'deleted')",
                name='ck_learning_study_session_change_event',
            ),
        )
        op.create_index(
            'ix_learning_study_session_change_session_id',
            'learning_study_session_change',
            ['session_id'],
            unique=False,
        )
        op.create_index(
            'ix_learning_study_session_change_child_date',
            'learning_study_session_change',
            ['child_id', 'study_date'],
            unique=False,
        )

    _ensure_study_foundation_schema(conn)


def _table_names(conn):
    return set(sa.inspect(conn).get_table_names())


def _index_names(conn, table):
    if table not in _table_names(conn):
        return set()
    return {idx['name'] for idx in sa.inspect(conn).get_indexes(table) if idx.get('name')}


def _ensure_index(conn, *, name, table, columns, unique=False, where=None):
    if table not in _table_names(conn):
        return
    if name in _index_names(conn, table):
        return
    if where:
        uniqueness = 'UNIQUE ' if unique else ''
        cols = ', '.join(columns)
        op.execute(
            f'CREATE {uniqueness}INDEX IF NOT EXISTS {name} '
            f'ON {table} ({cols}) WHERE {where}'
        )
        return
    op.create_index(name, table, list(columns), unique=unique)


def _ensure_unique(conn, table, name, columns):
    if table not in _table_names(conn):
        return
    inspector = sa.inspect(conn)
    wanted = list(columns)
    for constraint in inspector.get_unique_constraints(table):
        if constraint.get('name') == name or list(constraint.get('column_names') or []) == wanted:
            return
    for idx in inspector.get_indexes(table):
        dialect = idx.get('dialect_options') or {}
        if dialect.get('sqlite_where') or dialect.get('postgresql_where'):
            continue
        if idx.get('unique') and list(idx.get('column_names') or []) == wanted:
            return
    cols = ', '.join(columns)
    op.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS {name} ON {table} ({cols})')


def _ensure_check(conn, table, name, sqltext):
    if table not in _table_names(conn):
        return
    existing = {
        item.get('name')
        for item in sa.inspect(conn).get_check_constraints(table)
        if item.get('name')
    }
    if name in existing:
        return
    if conn.dialect.name == 'sqlite':
        return
    op.create_check_constraint(name, table, sqltext)


def _ensure_postgresql_defaults(conn):
    if conn.dialect.name != 'postgresql':
        return
    if 'learning_study_session' in _table_names(conn):
        op.execute(
            "ALTER TABLE learning_study_session "
            "ALTER COLUMN record_verification SET DEFAULT 'observed'"
        )
        op.execute(
            "ALTER TABLE learning_study_session "
            "ALTER COLUMN actor_type SET DEFAULT 'teacher'"
        )
    if 'center_non_study_day' in _table_names(conn):
        op.execute(
            "ALTER TABLE center_non_study_day "
            "ALTER COLUMN source SET DEFAULT 'center'"
        )


def _ensure_study_foundation_schema(conn):
    _ensure_index(
        conn,
        name='ix_center_subject_study_weekdays_learning_subject_id',
        table='center_subject_study_weekdays',
        columns=['learning_subject_id'],
        unique=True,
    )
    _ensure_index(
        conn,
        name='ix_center_non_study_day_day',
        table='center_non_study_day',
        columns=['day'],
    )
    _ensure_unique(
        conn,
        'center_non_study_day',
        'uq_center_non_study_day_day',
        ['day'],
    )
    _ensure_index(
        conn,
        name='ix_learning_study_session_child_id',
        table='learning_study_session',
        columns=['child_id'],
    )
    _ensure_index(
        conn,
        name='ix_learning_study_session_learning_subject_id',
        table='learning_study_session',
        columns=['learning_subject_id'],
    )
    _ensure_index(
        conn,
        name='ix_learning_study_session_study_date',
        table='learning_study_session',
        columns=['study_date'],
    )
    _ensure_index(
        conn,
        name='ix_learning_study_session_child_subject_date',
        table='learning_study_session',
        columns=['child_id', 'learning_subject_id', 'study_date'],
    )
    _ensure_index(
        conn,
        name='uq_learning_study_session_non_range_day',
        table='learning_study_session',
        columns=['child_id', 'learning_subject_id', 'study_date'],
        unique=True,
        where="study_status IN ('explicit_not_studied', 'unknown')",
    )
    _ensure_index(
        conn,
        name='ix_learning_study_session_change_session_id',
        table='learning_study_session_change',
        columns=['session_id'],
    )
    _ensure_index(
        conn,
        name='ix_learning_study_session_change_child_date',
        table='learning_study_session_change',
        columns=['child_id', 'study_date'],
    )
    _ensure_check(
        conn,
        'center_non_study_day',
        'ck_center_non_study_day_source',
        "source IN ('center', 'system_holiday')",
    )
    _ensure_check(
        conn,
        'learning_study_session',
        'ck_learning_study_session_study_status',
        "study_status IN ('studied', 'explicit_not_studied', 'unknown')",
    )
    _ensure_check(
        conn,
        'learning_study_session',
        'ck_learning_study_session_record_verification',
        "record_verification IN ('observed', 'verified')",
    )
    _ensure_check(
        conn,
        'learning_study_session',
        'ck_learning_study_session_pages_match_status',
        "("
        "study_status = 'studied' AND start_page IS NOT NULL AND end_page IS NOT NULL "
        "AND start_page >= 1 AND start_page <= end_page"
        ") OR ("
        "study_status IN ('explicit_not_studied', 'unknown') "
        "AND start_page IS NULL AND end_page IS NULL"
        ")",
    )
    _ensure_check(
        conn,
        'learning_study_session_change',
        'ck_learning_study_session_change_event',
        "event_type IN ('created', 'updated', 'deleted')",
    )
    _ensure_postgresql_defaults(conn)


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'learning_study_session_change' in tables:
        op.drop_index(
            'ix_learning_study_session_change_child_date',
            table_name='learning_study_session_change',
        )
        op.drop_index(
            'ix_learning_study_session_change_session_id',
            table_name='learning_study_session_change',
        )
        op.drop_table('learning_study_session_change')

    tables = sa.inspect(conn).get_table_names()
    if 'learning_study_session' in tables:
        op.execute('DROP INDEX IF EXISTS uq_learning_study_session_non_range_day')
        op.drop_index(
            'ix_learning_study_session_child_subject_date',
            table_name='learning_study_session',
        )
        op.drop_index(
            'ix_learning_study_session_study_date',
            table_name='learning_study_session',
        )
        op.drop_index(
            'ix_learning_study_session_learning_subject_id',
            table_name='learning_study_session',
        )
        op.drop_index(
            'ix_learning_study_session_child_id',
            table_name='learning_study_session',
        )
        op.drop_table('learning_study_session')

    tables = sa.inspect(conn).get_table_names()
    if 'center_non_study_day' in tables:
        op.drop_index('ix_center_non_study_day_day', table_name='center_non_study_day')
        op.drop_table('center_non_study_day')

    tables = sa.inspect(conn).get_table_names()
    if 'center_subject_study_weekdays' in tables:
        op.drop_index(
            'ix_center_subject_study_weekdays_learning_subject_id',
            table_name='center_subject_study_weekdays',
        )
        op.drop_table('center_subject_study_weekdays')
