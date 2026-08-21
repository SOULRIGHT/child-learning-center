"""add child_reading difficulty_rating and fun_rating

Revision ID: c2d9f01a7b44
Revises: e5b2c81d4a70
Create Date: 2026-08-21

완독 시 아동 체감 난이도·재미(1~5, nullable). Book AI 난이도와 별개다.
기존 ChildReading 행은 NULL로 유지한다. 다른 테이블은 ALTER/DROP 하지 않는다.
"""
from alembic import op
import sqlalchemy as sa


revision = 'c2d9f01a7b44'
down_revision = 'e5b2c81d4a70'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'child_reading' not in inspector.get_table_names():
        return
    cols = {col['name'] for col in inspector.get_columns('child_reading')}
    if 'difficulty_rating' not in cols:
        op.add_column(
            'child_reading',
            sa.Column('difficulty_rating', sa.Integer(), nullable=True),
        )
    if 'fun_rating' not in cols:
        op.add_column(
            'child_reading',
            sa.Column('fun_rating', sa.Integer(), nullable=True),
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'child_reading' not in inspector.get_table_names():
        return
    cols = {col['name'] for col in inspector.get_columns('child_reading')}
    if 'fun_rating' in cols:
        op.drop_column('child_reading', 'fun_rating')
    if 'difficulty_rating' in cols:
        op.drop_column('child_reading', 'difficulty_rating')
