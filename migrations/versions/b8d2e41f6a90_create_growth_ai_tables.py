"""create growth AI generation and feedback tables

Revision ID: b8d2e41f6a90
Revises: a1b7c93e4d20
Create Date: 2026-09-01

Teacher Growth AI runtime용 최소 저장만 추가한다.
운영 instance DB는 이 파일 밖에서 직접 변경하지 않는다.
"""
from alembic import op
import sqlalchemy as sa


revision = 'b8d2e41f6a90'
down_revision = 'a1b7c93e4d20'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'growth_ai_generation' not in tables:
        op.create_table(
            'growth_ai_generation',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('child_id', sa.Integer(), nullable=False),
            sa.Column('requested_by_user_id', sa.Integer(), nullable=False),
            sa.Column('packet_hash', sa.String(length=64), nullable=False),
            sa.Column('runtime_signature', sa.String(length=64), nullable=False),
            sa.Column('as_of', sa.Date(), nullable=False),
            sa.Column('status', sa.String(length=16), nullable=False),
            sa.Column('parsed_output', sa.JSON(), nullable=True),
            sa.Column('failure_code', sa.String(length=64), nullable=True),
            sa.Column('generator_provider', sa.String(length=32), nullable=True),
            sa.Column('model', sa.String(length=64), nullable=True),
            sa.Column('prompt_version', sa.String(length=64), nullable=True),
            sa.Column('output_schema_version', sa.String(length=64), nullable=True),
            sa.Column('factual_validator_version', sa.String(length=64), nullable=True),
            sa.Column('safety_provider', sa.String(length=64), nullable=True),
            sa.Column('safety_guardrail_version', sa.String(length=64), nullable=True),
            sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['child_id'], ['child.id']),
            sa.ForeignKeyConstraint(['requested_by_user_id'], ['user.id']),
        )
        op.create_index(
            'ix_growth_ai_generation_child_id',
            'growth_ai_generation',
            ['child_id'],
            unique=False,
        )
        op.create_index(
            'ix_growth_ai_generation_requested_by_user_id',
            'growth_ai_generation',
            ['requested_by_user_id'],
            unique=False,
        )
        op.create_index(
            'ix_growth_ai_generation_packet_hash',
            'growth_ai_generation',
            ['packet_hash'],
            unique=False,
        )
        op.create_index(
            'ix_growth_ai_gen_child_hash_runtime',
            'growth_ai_generation',
            ['child_id', 'packet_hash', 'runtime_signature'],
            unique=False,
        )
        op.create_index(
            'ix_growth_ai_gen_user_created',
            'growth_ai_generation',
            ['requested_by_user_id', 'created_at'],
            unique=False,
        )

    tables = sa.inspect(conn).get_table_names()
    if 'growth_ai_feedback' not in tables:
        op.create_table(
            'growth_ai_feedback',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('generation_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('helpful', sa.Boolean(), nullable=False),
            sa.Column('comment', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['generation_id'], ['growth_ai_generation.id']),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.UniqueConstraint(
                'generation_id', 'user_id', name='uq_growth_ai_feedback_generation_user',
            ),
        )
        op.create_index(
            'ix_growth_ai_feedback_generation_id',
            'growth_ai_feedback',
            ['generation_id'],
            unique=False,
        )
        op.create_index(
            'ix_growth_ai_feedback_user_id',
            'growth_ai_feedback',
            ['user_id'],
            unique=False,
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'growth_ai_feedback' in tables:
        op.drop_table('growth_ai_feedback')
    tables = sa.inspect(conn).get_table_names()
    if 'growth_ai_generation' in tables:
        op.drop_table('growth_ai_generation')
