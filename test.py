from app import app, db, User
with app.app_context():
    # 기존 사용자 찾기
    user = User.query.filter_by(email='dev_hoon@gmail.com').first()
    if user:
        # Firebase UID 업데이트
        user.firebase_uid = 'rPz8S98pPscb6i2FVnjKtBH4d2f1'
        db.session.commit()
        print(f'✅ 사용자 {user.name}에 Firebase UID 추가 완료!')
    else:
        print('❌ 사용자를 찾을 수 없습니다.')