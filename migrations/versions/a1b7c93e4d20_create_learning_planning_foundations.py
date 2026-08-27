"""create learning workbook plan and study weekday tables

Revision ID: a1b7c93e4d20
Revises: c2d9f01a7b44
Create Date: 2026-08-27

학습 계획 foundation 테이블만 추가한다.
LearningProgressEntry / DailyPoints / Child 컬럼은 ALTER/DROP 하지 않는다.
센터 기본 학습요일은 월~금 singleton 1행을 넣는다. 운영 DB를 이 파일 밖에서 직접 변경하지 않는다.
"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b7c93e4d20'
down_revision = 'c2d9f01a7b44'
branch_labels = None
depends_on = None

CALENDAR_SINGLETON_KEY = 'default'
DEFAULT_STUDY_WEEKDAYS = [0, 1, 2, 3, 4]


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'learning_workbook_plan' not in tables:
        op.create_table(
            'learning_workbook_plan',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('grade', sa.Integer(), nullable=False),
            sa.Column('learning_subject_id', sa.Integer(), nullable=False),
            sa.Column('textbook_title', sa.String(length=120), nullable=False),
            sa.Column('start_page', sa.Integer(), nullable=False),
            sa.Column('end_page', sa.Integer(), nullable=False),
            sa.Column('start_date', sa.Date(), nullable=False),
            sa.Column('target_completion_date', sa.Date(), nullable=False),
            sa.Column('exclusion_ranges_text', sa.Text(), nullable=True),
            sa.Column('exclusion_ranges_json', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['learning_subject_id'], ['learning_subject.id']),
            sa.UniqueConstraint(
                'grade',
                'learning_subject_id',
                'textbook_title',
                'start_date',
                name='uq_workbook_plan_grade_subject_title_start',
            ),
            sa.CheckConstraint('start_page <= end_page', name='ck_workbook_plan_page_order'),
            sa.CheckConstraint('start_page >= 1', name='ck_workbook_plan_start_page'),
            sa.CheckConstraint(
                'target_completion_date >= start_date',
                name='ck_workbook_plan_date_order',
            ),
        )
        op.create_index(
            'ix_learning_workbook_plan_grade',
            'learning_workbook_plan',
            ['grade'],
            unique=False,
        )
        op.create_index(
            'ix_learning_workbook_plan_learning_subject_id',
            'learning_workbook_plan',
            ['learning_subject_id'],
            unique=False,
        )
        op.create_index(
            'ix_workbook_plan_grade_subject',
            'learning_workbook_plan',
            ['grade', 'learning_subject_id'],
            unique=False,
        )

    tables = sa.inspect(conn).get_table_names()
    if 'center_study_calendar' not in tables:
        op.create_table(
            'center_study_calendar',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('singleton_key', sa.String(length=16), nullable=False),
            sa.Column('study_weekdays', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.UniqueConstraint('singleton_key', name='uq_center_study_calendar_singleton'),
        )

    if 'center_study_calendar' in sa.inspect(conn).get_table_names():
        calendar = sa.table(
            'center_study_calendar',
            sa.column('singleton_key', sa.String),
            sa.column('study_weekdays', sa.JSON),
        )
        existing = conn.execute(
            sa.text(
                'SELECT 1 FROM center_study_calendar WHERE singleton_key = :key'
            ),
            {'key': CALENDAR_SINGLETON_KEY},
        ).fetchone()
        if existing is None:
            conn.execute(
                calendar.insert(),
                {
                    'singleton_key': CALENDAR_SINGLETON_KEY,
                    'study_weekdays': DEFAULT_STUDY_WEEKDAYS,
                },
            )

    tables = sa.inspect(conn).get_table_names()
    if 'child_study_weekdays' not in tables:
        op.create_table(
            'child_study_weekdays',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('child_id', sa.Integer(), nullable=False),
            sa.Column('study_weekdays', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['child_id'], ['child.id']),
            sa.UniqueConstraint('child_id', name='uq_child_study_weekdays_child'),
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'child_study_weekdays' in tables:
        op.drop_table('child_study_weekdays')

    tables = sa.inspect(conn).get_table_names()
    if 'center_study_calendar' in tables:
        op.drop_table('center_study_calendar')

    tables = sa.inspect(conn).get_table_names()
    if 'learning_workbook_plan' in tables:
        op.drop_index('ix_workbook_plan_grade_subject', table_name='learning_workbook_plan')
        op.drop_index('ix_learning_workbook_plan_learning_subject_id', table_name='learning_workbook_plan')
        op.drop_index('ix_learning_workbook_plan_grade', table_name='learning_workbook_plan')
        op.drop_table('learning_workbook_plan')
