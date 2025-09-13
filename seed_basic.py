#!/usr/bin/env python3
"""
기본 개발/테스트용 데이터 시드 스크립트
==========================================
용도: 개발 및 테스트 환경에서 기본 데이터 생성
기능: 
- 기본 사용자 계정 생성 (7명)
- 샘플 아동 데이터 생성 (환경변수에서 읽음)
- 샘플 학습 기록 생성
- 샘플 포인트 데이터 생성
특징: 기존 데이터 보존, 환경변수 지원
사용법: python seed_basic.py
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
    """샘플 아동 데이터 생성 (환경변수에서 읽어옴)"""
    print("👶 샘플 아동 데이터 생성 중...")
    
    # 기존 아동이 없을 때만 생성
    if Child.query.count() == 0:
        # 환경변수에서 아동 데이터 읽기
        import os
        from dotenv import load_dotenv
        
        # 환경변수 로드
        load_dotenv()
        
        # 학년별 아동 이름들을 환경변수에서 읽기
        children_data = []
        
        for grade in range(1, 7):
            env_key = f'CHILDREN_GRADE{grade}'
            children_names = os.environ.get(env_key, '').split(',')
            
            for name in children_names:
                name = name.strip()
                if name:  # 빈 문자열이 아닌 경우만
                    children_data.append({
                        'name': name,
                        'grade': grade,
                        'include_in_stats': True
                    })
        
        if not children_data:
            print("⚠️ 환경변수에서 아동 데이터를 읽을 수 없습니다. 기본 데이터를 사용합니다.")
            # 기본 데이터 (fallback)
            children_data = [
                {'name': '김철수', 'grade': 1, 'include_in_stats': True},
                {'name': '박영희', 'grade': 2, 'include_in_stats': True},
                {'name': '이민수', 'grade': 3, 'include_in_stats': True},
                {'name': '최지영', 'grade': 4, 'include_in_stats': True},
            ]
        
        sample_children = children_data
        
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
