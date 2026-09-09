"""add learning_study_session.learning_workbook_plan_id

Revision ID: a2b8c4d6e1f0
Revises: f7c2a19e4b80
Create Date: 2026-09-08

학습 세션을 기존 LearningWorkbookPlan 에 FK로 연결한다.
문자열 textbook_title 표기 차이로 교재를 추정하지 않는다.
아동별 workbook plan 테이블은 만들지 않는다.
"""
from alembic import op
import sqlalchemy as sa


revision = 'a2b8c4d6e1f0'
down_revision = 'f7c2a19e4b80'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'learning_study_session' not in tables:
        return
    columns = {col['name'] for col in inspector.get_columns('learning_study_session')}
    if 'learning_workbook_plan_id' not in columns:
        if conn.dialect.name == 'sqlite':
            with op.batch_alter_table('learning_study_session') as batch_op:
                batch_op.add_column(
                    sa.Column('learning_workbook_plan_id', sa.Integer(), nullable=True)
                )
                batch_op.create_foreign_key(
                    'fk_learning_study_session_workbook_plan',
                    'learning_workbook_plan',
                    ['learning_workbook_plan_id'],
                    ['id'],
                )
        else:
            op.add_column(
                'learning_study_session',
                sa.Column(
                    'learning_workbook_plan_id',
                    sa.Integer(),
                    sa.ForeignKey('learning_workbook_plan.id'),
                    nullable=True,
                ),
            )
    inspector = sa.inspect(conn)
    indexes = {
        idx['name']
        for idx in inspector.get_indexes('learning_study_session')
        if idx.get('name')
    }
    if 'ix_learning_study_session_learning_workbook_plan_id' not in indexes:
        op.create_index(
            'ix_learning_study_session_learning_workbook_plan_id',
            'learning_study_session',
            ['learning_workbook_plan_id'],
            unique=False,
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'learning_study_session' not in tables:
        return
    indexes = {
        idx['name']
        for idx in inspector.get_indexes('learning_study_session')
        if idx.get('name')
    }
    if 'ix_learning_study_session_learning_workbook_plan_id' in indexes:
        op.drop_index(
            'ix_learning_study_session_learning_workbook_plan_id',
            table_name='learning_study_session',
        )
    columns = {col['name'] for col in inspector.get_columns('learning_study_session')}
    if 'learning_workbook_plan_id' not in columns:
        return
    if conn.dialect.name == 'sqlite':
        with op.batch_alter_table('learning_study_session') as batch_op:
            batch_op.drop_constraint(
                'fk_learning_study_session_workbook_plan',
                type_='foreignkey',
            )
            batch_op.drop_column('learning_workbook_plan_id')
        return
    op.drop_column('learning_study_session', 'learning_workbook_plan_id')
