#!/usr/bin/env python3
"""
실제 운영용 데이터 시드 스크립트
================================
용도: 실제 센터 운영 시 사용자 입력으로 데이터 생성
기능:
- 기본 사용자 계정 생성 (환경변수에서 읽음)
- 사용자 입력으로 아동 데이터 생성
- 사용자 입력으로 포인트 데이터 생성
- 사용자 입력으로 학습 기록 생성
특징: 대화형 입력, 실제 운영용, 기존 데이터 삭제 옵션
주의: 실제 센터 데이터 입력용, 테스트용 아님
사용법: python seed_production.py
"""

from app import app, db, User, Child, LearningRecord, DailyPoints
from datetime import date, timedelta
from werkzeug.security import generate_password_hash

def create_users():
    """기본 사용자 계정 생성 (환경변수에서 읽어옴)"""
    print("👥 기본 사용자 계정 생성 중...")
    
    if User.query.count() == 0:
        # 환경변수에서 사용자 정보 읽기
        import os
        from dotenv import load_dotenv
        
        # 환경변수 로드
        load_dotenv()
        
        # 환경변수에서 사용자 정보 읽기
        usernames = os.environ.get('DEFAULT_USERS', 'developer,center_head,care_teacher').split(',')
        passwords = os.environ.get('DEFAULT_PASSWORDS', 'dev123,center123!,care123!').split(',')
        roles = os.environ.get('DEFAULT_USER_ROLES', '개발자,센터장,돌봄선생님').split(',')
        
        # 사용자 데이터 생성
        default_users = []
        for i, username in enumerate(usernames):
            if i < len(passwords) and i < len(roles):
                default_users.append({
                    'username': username.strip(),
                    'name': roles[i].strip(),
                    'role': roles[i].strip(),
                    'password': passwords[i].strip()
                })
        
        # 환경변수에서 읽을 수 없는 경우 기본값 사용
        if not default_users:
            print("⚠️ 환경변수에서 사용자 데이터를 읽을 수 없습니다. 기본 데이터를 사용합니다.")
            default_users = [
                {'username': 'developer', 'name': '개발자', 'role': '개발자', 'password': 'dev123'},
                {'username': 'center_head', 'name': '센터장', 'role': '센터장', 'password': 'center123!'},
                {'username': 'care_teacher', 'name': '돌봄선생님', 'role': '돌봄선생님', 'password': 'care123!'}
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

def input_real_children():
    """실제 아동 데이터 입력"""
    print("\n👶 실제 아동 데이터 입력")
    print("=" * 50)
    
    # 기존 아동이 있으면 삭제
    if Child.query.count() > 0:
        print("⚠️ 기존 아동 데이터가 발견되었습니다.")
        response = input("모든 아동 데이터를 삭제하고 새로 입력하시겠습니까? (y/N): ")
        if response.lower() == 'y':
            Child.query.delete()
            LearningRecord.query.delete()
            DailyPoints.query.delete()
            db.session.commit()
            print("🗑️ 기존 아동 데이터가 삭제되었습니다.")
        else:
            print("❌ 작업이 취소되었습니다.")
            return []
    
    children = []
    print("\n📝 아동 정보를 입력하세요 (종료하려면 이름에 'q' 입력)")
    
    while True:
        print(f"\n--- {len(children) + 1}번째 아동 ---")
        name = input("이름: ").strip()
        
        if name.lower() == 'q':
            break
        
        if not name:
            print("❌ 이름을 입력해주세요.")
            continue
        
        # 학년 입력
        while True:
            try:
                grade = int(input("학년 (1-6): "))
                if 1 <= grade <= 6:
                    break
                else:
                    print("❌ 1-6 사이의 숫자를 입력해주세요.")
            except ValueError:
                print("❌ 숫자를 입력해주세요.")
        
        # 통계 포함 여부
        include_stats = input("통계에 포함 (y/N): ").lower() == 'y'
        
        # 아동 생성
        child = Child(
            name=name,
            grade=grade,
            include_in_stats=include_stats
        )
        children.append(child)
        db.session.add(child)
        
        print(f"✅ {name}({grade}학년) 추가됨")
    
    if children:
        db.session.commit()
        print(f"\n🎉 총 {len(children)}명의 아동이 추가되었습니다!")
    
    return children

def input_historical_points(children):
    """과거 포인트 데이터 입력"""
    if not children:
        return
    
    print("\n⭐ 과거 포인트 데이터 입력")
    print("=" * 50)
    
    for child in children:
        print(f"\n--- {child.name}({child.grade}학년) ---")
        
        # 과거 포인트 입력
        try:
            korean_points = int(input("국어 누적 포인트: ") or "0")
            math_points = int(input("수학 누적 포인트: ") or "0")
            ssen_points = int(input("쎈수학 누적 포인트: ") or "0")
            reading_points = int(input("독서 누적 포인트: ") or "0")
        except ValueError:
            print("❌ 숫자를 입력해주세요. 기본값 0으로 설정됩니다.")
            korean_points = math_points = ssen_points = reading_points = 0
        
        total_points = korean_points + math_points + ssen_points + reading_points
        
        # 과거 30일간의 포인트 기록 생성
        today = date.today()
        for i in range(30):
            current_date = today - timedelta(days=i)
            
            # 일일 포인트 (누적 포인트를 30일로 나누어 분배)
            daily_korean = korean_points // 30
            daily_math = math_points // 30
            daily_ssen = ssen_points // 30
            daily_reading = reading_points // 30
            
            # 나머지 포인트는 오늘에 추가
            if i == 0:
                daily_korean += korean_points % 30
                daily_math += math_points % 30
                daily_ssen += ssen_points % 30
                daily_reading += reading_points % 30
            
            daily_point = DailyPoints(
                child_id=child.id,
                date=current_date,
                korean_points=daily_korean,
                math_points=daily_math,
                ssen_points=daily_ssen,
                reading_points=daily_reading,
                total_points=daily_korean + daily_math + daily_ssen + daily_reading,
                created_by=1
            )
            db.session.add(daily_point)
        
        print(f"✅ {child.name}의 과거 포인트 기록 생성 완료 (총 {total_points}포인트)")

def input_learning_records(children):
    """학습 기록 데이터 입력"""
    if not children:
        return
    
    print("\n📚 학습 기록 데이터 입력")
    print("=" * 50)
    
    for child in children:
        print(f"\n--- {child.name}({child.grade}학년) ---")
        
        # 최근 학습 기록 입력
        try:
            korean_page = int(input("국어 마지막 페이지: ") or "1")
            math_page = int(input("수학 마지막 페이지: ") or "1")
            reading_completed = input("독서 완료 여부 (y/N): ").lower() == 'y'
        except ValueError:
            print("❌ 숫자를 입력해주세요. 기본값으로 설정됩니다.")
            korean_page = math_page = 1
            reading_completed = False
        
        # 최근 7일간의 학습 기록 생성
        today = date.today()
        for i in range(7):
            current_date = today - timedelta(days=i)
            
            # 기본 학습 기록 (실제 운영 시 수정 필요)
            record = LearningRecord(
                child_id=child.id,
                date=current_date,
                korean_problems_solved=20,
                korean_problems_correct=18,
                korean_score=90.0,
                korean_last_page=korean_page,
                math_problems_solved=15,
                math_problems_correct=12,
                math_score=80.0,
                math_last_page=math_page,
                reading_completed=reading_completed,
                reading_score=200 if reading_completed else 100,
                total_score=0,
                created_by=1
            )
            
            record.total_score = record.korean_score + record.math_score + record.reading_score
            db.session.add(record)
        
        print(f"✅ {child.name}의 학습 기록 생성 완료")

def main():
    """메인 실행 함수"""
    print("🌱 실제 운영용 데이터 시드 시작...")
    print("이 스크립트는 실제 아동 데이터를 입력하는 용도입니다.")
    print("개인정보 보호를 위해 실제 이름과 포인트만 입력하세요.\n")
    
    with app.app_context():
        try:
            # 1. 사용자 계정 생성
            create_users()
            
            # 2. 실제 아동 데이터 입력
            children = input_real_children()
            
            if children:
                # 3. 과거 포인트 데이터 입력
                input_historical_points(children)
                
                # 4. 학습 기록 데이터 입력
                input_learning_records(children)
                
                # 5. 최종 저장
                db.session.commit()
                
                print("\n🎉 데이터베이스 시드 완료!")
                print("\n📊 현재 데이터베이스 현황:")
                print(f"  • 사용자: {User.query.count()}명")
                print(f"  • 아동: {Child.query.count()}명")
                print(f"  • 학습 기록: {LearningRecord.query.count()}개")
                print(f"  • 포인트 기록: {DailyPoints.query.count()}개")
                
                print("\n💡 다음 단계:")
                print("  1. 웹 UI에서 로그인하여 데이터 확인")
                print("  2. 필요시 추가 데이터 수정")
                print("  3. 정기적인 백업 수행")
                
            else:
                print("\n❌ 아동 데이터가 입력되지 않았습니다.")
                
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            db.session.rollback()
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    main()
