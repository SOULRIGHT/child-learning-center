from app import app, db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    # 기본 사용자 생성
    users_data = [
        {'username': 'developer', 'name': '개발자', 'role': '개발자', 'email': 'dev_hoon@gmail.com'},
        {'username': 'center_director', 'name': '센터장', 'role': '센터장', 'email': 'center_director@gmail.com'},
        {'username': 'teacher', 'name': '돌봄선생님', 'role': '돌봄선생님', 'email': 'teacher@gmail.com'},
        {'username': 'sowo_1', 'name': '사회복무요원1', 'role': '사회복무요원', 'email': 'sowo_1@gmail.com'},
        {'username': 'sowo_2', 'name': '사회복무요원2', 'role': '사회복무요원', 'email': 'sowo_2@gmail.com'},
        {'username': 'sowo_3', 'name': '사회복무요원3', 'role': '사회복무요원', 'email': 'sowo_3@gmail.com'}
    ]
    
    for user_data in users_data:
        user = User(
            username=user_data['username'],
            name=user_data['name'],
            role=user_data['role'],
            email=user_data['email'],
            password_hash=generate_password_hash('password123')
        )
        db.session.add(user)
    
    db.session.commit()
    print('✅ 사용자 데이터 생성 완료!')