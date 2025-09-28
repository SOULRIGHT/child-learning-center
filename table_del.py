from app import app, db

with app.app_context():
    db.drop_all()
    db.create_all()
    print('✅ 테이블 재생성 완료!')