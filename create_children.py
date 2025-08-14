from app import app, db, Child, LearningRecord, DailyPoints
from datetime import date, timedelta
import random

app.app_context().push()

# 환경변수에서 아동 이름 읽기
import os
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 1~6학년별 아동 이름을 환경변수에서 읽기
grade_names = {}
for grade in range(1, 7):
    env_key = f'CHILDREN_GRADE{grade}'
    children_names = os.environ.get(env_key, '').split(',')
    
    # 빈 문자열이 아닌 이름만 필터링
    grade_names[grade] = [name.strip() for name in children_names if name.strip()]
    
    # 환경변수에서 읽을 수 없는 경우 기본값 사용
    if not grade_names[grade]:
        print(f"⚠️ {grade}학년 아동 데이터를 환경변수에서 읽을 수 없습니다. 기본 데이터를 사용합니다.")
        if grade == 1:
            grade_names[grade] = ['김민준', '이서연', '박도현', '최지우', '정현우']
        elif grade == 2:
            grade_names[grade] = ['강서진', '윤하은', '임준호', '한소희', '조민재']
        elif grade == 3:
            grade_names[grade] = ['신동현', '오유진', '권태현', '배수빈', '남준영']
        elif grade == 4:
            grade_names[grade] = ['김지원', '이승우', '박소연', '최민석', '정하나']
        elif grade == 5:
            grade_names[grade] = ['강현준', '윤지민', '임서연', '한도현', '조유진']
        elif grade == 6:
            grade_names[grade] = ['신태현', '오준호', '권소희', '배민재', '남수빈']

print("기존 아동 데이터 삭제 중...")
# 기존 아동 데이터 삭제
Child.query.delete()
db.session.commit()

print("30명 아동 데이터 생성 중...")
# 30명 아동 생성
children = []
for grade in range(1, 7):
    for name in grade_names[grade]:
        child = Child(name=name, grade=grade, include_in_stats=True)
        children.append(child)
        db.session.add(child)

db.session.commit()
print(f'✅ 30명 아동 데이터 생성 완료!')

print("학습 기록 생성 중...")
# 학습 기록 생성 (최근 7일)
today = date.today()
for child in children:
    for i in range(7):
        current_date = today - timedelta(days=i)
        
        # 랜덤한 학습 기록
        korean_solved = random.randint(15, 25)
        korean_correct = random.randint(korean_solved-5, korean_solved)
        math_solved = random.randint(10, 20)
        math_correct = random.randint(math_solved-3, math_solved)
        reading_completed = random.choice([True, False])
        
        record = LearningRecord(
            child_id=child.id,
            date=current_date,
            korean_problems_solved=korean_solved,
            korean_problems_correct=korean_correct,
            korean_score=round((korean_correct/korean_solved)*100, 1),
            korean_last_page=random.randint(10, 30),
            math_problems_solved=math_solved,
            math_problems_correct=math_correct,
            math_score=round((math_correct/math_solved)*100, 1),
            math_last_page=random.randint(15, 35),
            reading_completed=reading_completed,
            reading_score=200 if reading_completed else 100,
            total_score=0,
            created_by=1
        )
        
        # 총점 계산
        record.total_score = record.korean_score + record.math_score + record.reading_score
        db.session.add(record)
    
    print(f"  {child.name}({child.grade}학년) 학습 기록 생성 완료")

print("포인트 데이터 생성 중...")
# 포인트 데이터도 생성
for child in children:
    for i in range(30):  # 최근 30일
        current_date = today - timedelta(days=i)
        if random.random() > 0.2:  # 80% 확률로 기록
            daily_point = DailyPoints(
                child_id=child.id,
                date=current_date,
                korean_points=random.choice([0, 100, 200]),
                math_points=random.choice([0, 100, 200]),
                ssen_points=random.choice([0, 100, 200]),
                reading_points=random.choice([0, 100, 200]),
                total_points=0,
                created_by=1
            )
            daily_point.total_points = daily_point.korean_points + daily_point.math_points + daily_point.ssen_points + daily_point.reading_points
            db.session.add(daily_point)

db.session.commit()
print('✅ 학습 기록 및 포인트 데이터 생성 완료!')

# 최종 결과 출력
print(f'\n📊 데이터베이스 현황:')
print(f'  • 아동: {Child.query.count()}명')
print(f'  • 학습 기록: {LearningRecord.query.count()}개')
print(f'  • 포인트 기록: {DailyPoints.query.count()}개')

# 학년별 아동 수 출력
print(f'\n👥 학년별 아동 분포:')
for grade in range(1, 7):
    count = Child.query.filter_by(grade=grade).count()
    print(f'  • {grade}학년: {count}명')

print('\n🎉 30명 아동 데이터 생성이 완료되었습니다!')
