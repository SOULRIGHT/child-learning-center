"""운영 DB에 ChildReading 평가 컬럼이 없으면 추가한다. alembic과 같은 목적의 안전망."""
from sqlalchemy import inspect, text

from extensions import db


def ensure_child_reading_rating_columns(engine=None):
    """기존 child_reading 행은 NULL로 두고 nullable integer 두 컬럼만 추가한다."""
    engine = engine or db.engine
    inspector = inspect(engine)
    if 'child_reading' not in inspector.get_table_names():
        return False
    cols = {col['name'] for col in inspector.get_columns('child_reading')}
    statements = []
    if 'difficulty_rating' not in cols:
        statements.append('ALTER TABLE child_reading ADD COLUMN difficulty_rating INTEGER')
    if 'fun_rating' not in cols:
        statements.append('ALTER TABLE child_reading ADD COLUMN fun_rating INTEGER')
    if not statements:
        return False
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
    return True
