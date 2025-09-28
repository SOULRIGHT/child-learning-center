from app import app, db
from sqlalchemy import text

with app.app_context():
    # 외래키 제약을 고려한 삭제 순서
    db.session.execute(text('DELETE FROM learning_record'))
    db.session.execute(text('DELETE FROM daily_points'))
    db.session.execute(text('DELETE FROM points_history'))
    db.session.execute(text('DELETE FROM child'))
    db.session.execute(text('DELETE FROM "user"'))
    db.session.commit()
    print('✅ 모든 데이터 삭제 완료!')