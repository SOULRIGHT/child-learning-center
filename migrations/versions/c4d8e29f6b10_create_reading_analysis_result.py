"""create reading_analysis_result cache table

Revision ID: c4d8e29f6b10
Revises: b3c9d17e5a20
Create Date: 2026-09-09

독서 전용 AI 결과 캐시. additive only.
review_text / full prompt / Guardrail raw payload 컬럼을 만들지 않는다.
기존 reading / Growth AI 테이블은 ALTER/DROP 하지 않는다.
"""
from alembic import op
import sqlalchemy as sa


revision = 'c4d8e29f6b10'
down_revision = 'b3c9d17e5a20'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'reading_analysis_result' in tables:
        return
    op.create_table(
        'reading_analysis_result',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('child_id', sa.Integer(), nullable=False),
        sa.Column('requested_by_user_id', sa.Integer(), nullable=False),
        sa.Column('fingerprint', sa.String(length=64), nullable=False),
        sa.Column('as_of', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('sufficiency', sa.String(length=32), nullable=True),
        sa.Column('parsed_output', sa.JSON(), nullable=True),
        sa.Column('facts_snapshot', sa.JSON(), nullable=True),
        sa.Column('failure_code', sa.String(length=64), nullable=True),
        sa.Column('generator_provider', sa.String(length=32), nullable=True),
        sa.Column('model', sa.String(length=64), nullable=True),
        sa.Column('prompt_version', sa.String(length=64), nullable=True),
        sa.Column('analyzer_version', sa.String(length=64), nullable=True),
        sa.Column('output_schema_version', sa.String(length=64), nullable=True),
        sa.Column('validator_version', sa.String(length=64), nullable=True),
        sa.Column('safety_provider', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['child_id'], ['child.id']),
        sa.ForeignKeyConstraint(['requested_by_user_id'], ['user.id']),
    )
    op.create_index(
        'ix_reading_analysis_result_child_id',
        'reading_analysis_result',
        ['child_id'],
        unique=False,
    )
    op.create_index(
        'ix_reading_analysis_result_requested_by_user_id',
        'reading_analysis_result',
        ['requested_by_user_id'],
        unique=False,
    )
    op.create_index(
        'ix_reading_analysis_result_fingerprint',
        'reading_analysis_result',
        ['fingerprint'],
        unique=False,
    )
    op.create_index(
        'ix_reading_analysis_child_fingerprint',
        'reading_analysis_result',
        ['child_id', 'fingerprint'],
        unique=False,
    )
    op.create_index(
        'ix_reading_analysis_child_created',
        'reading_analysis_result',
        ['child_id', 'created_at'],
        unique=False,
    )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'reading_analysis_result' in inspector.get_table_names():
        op.drop_table('reading_analysis_result')
