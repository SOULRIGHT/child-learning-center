"""create growth_ai_attempt diagnostics table

Revision ID: c3a8f17b2d01
Revises: b8d2e41f6a90
Create Date: 2026-09-02

generation 내부 attempt 진단 로그. 일반 UI에 노출하지 않는다.
"""
from alembic import op
import sqlalchemy as sa


revision = 'c3a8f17b2d01'
down_revision = 'b8d2e41f6a90'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'growth_ai_attempt' in tables:
        return
    op.create_table(
        'growth_ai_attempt',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('generation_id', sa.Integer(), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('generator_provider', sa.String(length=32), nullable=True),
        sa.Column('model', sa.String(length=64), nullable=True),
        sa.Column('prompt_version', sa.String(length=64), nullable=True),
        sa.Column('output_schema_version', sa.String(length=64), nullable=True),
        sa.Column('stage', sa.String(length=32), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('generated_output', sa.JSON(), nullable=True),
        sa.Column('generated_text', sa.Text(), nullable=True),
        sa.Column('validator_valid', sa.Boolean(), nullable=True),
        sa.Column('validator_codes', sa.JSON(), nullable=True),
        sa.Column('validator_issues', sa.JSON(), nullable=True),
        sa.Column('safety_action', sa.String(length=64), nullable=True),
        sa.Column('safety_reason', sa.String(length=255), nullable=True),
        sa.Column('safety_categories', sa.JSON(), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('generator_latency_ms', sa.Integer(), nullable=True),
        sa.Column('validator_latency_ms', sa.Integer(), nullable=True),
        sa.Column('safety_latency_ms', sa.Integer(), nullable=True),
        sa.Column('total_latency_ms', sa.Integer(), nullable=True),
        sa.Column('failure_code', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['generation_id'], ['growth_ai_generation.id']),
    )
    op.create_index(
        'ix_growth_ai_attempt_generation_id',
        'growth_ai_attempt',
        ['generation_id'],
        unique=False,
    )
    op.create_index(
        'ix_growth_ai_attempt_status',
        'growth_ai_attempt',
        ['status'],
        unique=False,
    )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'growth_ai_attempt' in tables:
        op.drop_table('growth_ai_attempt')
