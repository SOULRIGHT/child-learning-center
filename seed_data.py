#!/usr/bin/env python3
"""
데이터베이스 시드 스크립트
실제 운영 시 아동 이름과 포인트만 수정하여 사용
"""

from app import app, db, User, Child, LearningRecord, DailyPoints
from datetime import date, timedelta
from werkzeug.security import generate_password_hash

def seed_users():
    """기본 사용자 계정 생성"""
    print("👥 기본 사용자 계정 생성 중...")
    
    # 기존 사용자가 없을 때만 생성
    if User.query.count() == 0:
        default_users = [
            {'username': 'developer', 'name': '개발자', 'role': '개발자', 'password': 'dev123'},
            {'username': 'center_head', 'name': '센터장', 'role': '센터장', 'password': 'center123!'},
            {'username': 'care_teacher', 'name': '돌봄선생님', 'role': '돌봄선생님', 'password': 'care123!'},
            {'username': 'social_worker1', 'name': '사회복무요원1', 'role': '사회복무요원', 'password': 'social123!'},
            {'username': 'social_worker2', 'name': '사회복무요원2', 'role': '사회복무요원', 'password': 'social456!'},
            {'username': 'assistant', 'name': '보조교사', 'role': '보조교사', 'password': 'assist123!'},
            {'username': 'test_user', 'name': '테스트사용자', 'role': '테스트사용자', 'password': 'test_kohi'}
        ]
        
        for user_data in default_users:
            password_hash = generate_password_hash(user_data['password'])
            user = User(
                username=user_data['username'],
                password_hash=password_hash,
                name=user_data['name'],
                role=user_data['role']
            )
            db.session.add(user)
        
        db.session.commit()
        print(f"✅ {len(default_users)}명의 사용자 계정 생성 완료")
    else:
        print("ℹ️ 사용자 계정이 이미 존재합니다")

def seed_sample_children():
    """샘플 아동 데이터 생성 (실제 운영 시 이름만 수정)"""
    print("👶 샘플 아동 데이터 생성 중...")
    
    # 기존 아동이 없을 때만 생성
    if Child.query.count() == 0:
        sample_children = [
            # 1학년
            {'name': '김철수', 'grade': 1, 'include_in_stats': True},
            {'name': '박영희', 'grade': 1, 'include_in_stats': True},
            {'name': '이민수', 'grade': 1, 'include_in_stats': True},
            {'name': '최지영', 'grade': 1, 'include_in_stats': True},
            {'name': '정현우', 'grade': 1, 'include_in_stats': True},
            
            # 2학년
            {'name': '강서진', 'grade': 2, 'include_in_stats': True},
            {'name': '윤하은', 'grade': 2, 'include_in_stats': True},
            {'name': '임준호', 'grade': 2, 'include_in_stats': True},
            {'name': '한소희', 'grade': 2, 'include_in_stats': True},
            {'name': '조민재', 'grade': 2, 'include_in_stats': True},
            
            # 3학년
            {'name': '신동현', 'grade': 3, 'include_in_stats': True},
            {'name': '오유진', 'grade': 3, 'include_in_stats': True},
            {'name': '권태현', 'grade': 3, 'include_in_stats': True},
            {'name': '배수빈', 'grade': 3, 'include_in_stats': True},
            {'name': '남준영', 'grade': 3, 'include_in_stats': True},
            
            # 4학년
            {'name': '김지원', 'grade': 4, 'include_in_stats': True},
            {'name': '이승우', 'grade': 4, 'include_in_stats': True},
            {'name': '박소연', 'grade': 4, 'include_in_stats': True},
            {'name': '최민석', 'grade': 4, 'include_in_stats': True},
            {'name': '정하나', 'grade': 4, 'include_in_stats': True},
            
            # 5학년
            {'name': '강현준', 'grade': 5, 'include_in_stats': True},
            {'name': '윤지민', 'grade': 5, 'include_in_stats': True},
            {'name': '임서연', 'grade': 5, 'include_in_stats': True},
            {'name': '한도현', 'grade': 5, 'include_in_stats': True},
            {'name': '조유진', 'grade': 5, 'include_in_stats': True},
            
            # 6학년
            {'name': '신태현', 'grade': 6, 'include_in_stats': True},
            {'name': '오준호', 'grade': 6, 'include_in_stats': True},
            {'name': '권소희', 'grade': 6, 'include_in_stats': True},
            {'name': '배민재', 'grade': 6, 'include_in_stats': True},
            {'name': '남수빈', 'grade': 6, 'include_in_stats': True},
        ]
        
        children = []
        for child_data in sample_children:
            child = Child(**child_data)
            children.append(child)
            db.session.add(child)
        
        db.session.commit()
        print(f"✅ {len(sample_children)}명의 샘플 아동 데이터 생성 완료")
        return children
    else:
        print("ℹ️ 아동 데이터가 이미 존재합니다")
        return Child.query.all()

def seed_sample_learning_records(children):
    """샘플 학습 기록 생성"""
    print("📚 샘플 학습 기록 생성 중...")
    
    # 기존 학습 기록이 없을 때만 생성
    if LearningRecord.query.count() == 0:
        today = date.today()
        
        for child in children:
            # 최근 7일간의 학습 기록
            for i in range(7):
                current_date = today - timedelta(days=i)
                
                # 랜덤한 학습 기록 (실제 운영 시 수정)
                korean_solved = 20
                korean_correct = 18
                math_solved = 15
                math_correct = 12
                reading_completed = True
                
                record = LearningRecord(
                    child_id=child.id,
                    date=current_date,
                    korean_problems_solved=korean_solved,
                    korean_problems_correct=korean_correct,
                    korean_score=round((korean_correct/korean_solved)*100, 1),
                    korean_last_page=15,
                    math_problems_solved=math_solved,
                    math_problems_correct=math_correct,
                    math_score=round((math_correct/math_solved)*100, 1),
                    math_last_page=22,
                    reading_completed=reading_completed,
                    reading_score=200 if reading_completed else 100,
                    total_score=0,
                    created_by=1
                )
                
                record.total_score = record.korean_score + record.math_score + record.reading_score
                db.session.add(record)
            
            print(f"  {child.name}({child.grade}학년) 학습 기록 생성 완료")
        
        db.session.commit()
        print("✅ 샘플 학습 기록 생성 완료")
    else:
        print("ℹ️ 학습 기록이 이미 존재합니다")

def seed_sample_points(children):
    """샘플 포인트 데이터 생성"""
    print("⭐ 샘플 포인트 데이터 생성 중...")
    
    # 기존 포인트 기록이 없을 때만 생성
    if DailyPoints.query.count() == 0:
        today = date.today()
        
        for child in children:
            # 최근 30일간의 포인트 기록
            for i in range(30):
                current_date = today - timedelta(days=i)
                
                # 샘플 포인트 (실제 운영 시 수정)
                daily_point = DailyPoints(
                    child_id=child.id,
                    date=current_date,
                    korean_points=100,
                    math_points=100,
                    ssen_points=100,
                    reading_points=100,
                    total_points=400,
                    created_by=1
                )
                db.session.add(daily_point)
            
            print(f"  {child.name}({child.grade}학년) 포인트 기록 생성 완료")
        
        db.session.commit()
        print("✅ 샘플 포인트 데이터 생성 완료")
    else:
        print("ℹ️ 포인트 기록이 이미 존재합니다")

def main():
    """메인 실행 함수"""
    print("🌱 데이터베이스 시드 시작...")
    
    with app.app_context():
        try:
            # 1. 사용자 계정 생성
            seed_users()
            
            # 2. 샘플 아동 데이터 생성
            children = seed_sample_children()
            
            # 3. 샘플 학습 기록 생성
            seed_sample_learning_records(children)
            
            # 4. 샘플 포인트 데이터 생성
            seed_sample_points(children)
            
            print("\n🎉 데이터베이스 시드 완료!")
            print("\n📊 현재 데이터베이스 현황:")
            print(f"  • 사용자: {User.query.count()}명")
            print(f"  • 아동: {Child.query.count()}명")
            print(f"  • 학습 기록: {LearningRecord.query.count()}개")
            print(f"  • 포인트 기록: {DailyPoints.query.count()}개")
            
            print("\n💡 실제 운영 시 수정 방법:")
            print("  1. 이 파일에서 아동 이름을 실제 이름으로 변경")
            print("  2. 포인트 값을 실제 누적 포인트로 변경")
            print("  3. python seed_data.py 실행")
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            db.session.rollback()

if __name__ == '__main__':
    main()
