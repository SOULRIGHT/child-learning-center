from app import app, db
with app.app_context():
    # 외래키 제약을 고려한 삭제 순서
    db.session.execute('DELETE FROM learning_record')
    db.session.execute('DELETE FROM daily_points')
    db.session.execute('DELETE FROM points_history')
    db.session.execute('DELETE FROM child')
    db.session.execute('DELETE FROM \"user\"')
    db.session.commit()
    print('✅ 모든 데이터 삭제 완료!')