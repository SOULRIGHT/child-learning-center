#!/usr/bin/env python3
"""
실제 가명으로 시드 데이터 생성
"""

import os
import sys
from datetime import datetime, timedelta
import random

# 상위 디렉토리의 app.py를 import하기 위해 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from app import Child, DailyPoints, User

def create_real_pseudonyms():
    """실제 가명으로 시드 데이터 생성"""
    
    with app.app_context():
        print("🔄 기존 데이터 초기화 중...")
        
        # 모든 테이블 데이터 삭제
        tables = ['daily_points', 'points_history', 'notification', 'child_note', 'child']
        
        for table in tables:
            db.session.execute(f'TRUNCATE TABLE {table} CASCADE')
            print(f'✅ {table} 테이블 초기화')
        
        db.session.commit()
        
        print("👥 실제 가명으로 아동 데이터 생성 중...")
        
        # 학년별 가명 데이터
        children_data = [
            # 1학년
            {"name": "돌고래", "grade": 1},
            {"name": "양양이", "grade": 1},
            {"name": "도마뱀", "grade": 1},
            
            # 2학년
            {"name": "탕수육", "grade": 2},
            {"name": "쫄라맨", "grade": 2},
            {"name": "핸드폰", "grade": 2},
            
            # 3학년
            {"name": "예나비", "grade": 3},
            {"name": "베이비", "grade": 3},
            {"name": "여고생", "grade": 3},
            {"name": "노진구", "grade": 3},
            {"name": "하늘이", "grade": 3},
            {"name": "먹대장", "grade": 3},
            {"name": "짜장면", "grade": 3},
            
            # 4학년
            {"name": "이쁜이", "grade": 4},
            {"name": "말랑이", "grade": 4},
            {"name": "누룽지", "grade": 4},
            {"name": "최씨군", "grade": 4},
            {"name": "포차코", "grade": 4},
            {"name": "우라늄", "grade": 4},
            {"name": "토끼야", "grade": 4},
            
            # 5학년
            {"name": "베트남", "grade": 5},
            {"name": "빡빡이", "grade": 5},
            {"name": "민수르", "grade": 5},
            {"name": "우등생", "grade": 5},
            
            # 6학년
            {"name": "태이프", "grade": 6},
            {"name": "머스크", "grade": 6},
            {"name": "다이키", "grade": 6},
            {"name": "감스트", "grade": 6},
            {"name": "두목짱", "grade": 6},
        ]
        
        # 아동 데이터 생성
        for child_data in children_data:
            child = Child(
                name=child_data["name"],
                grade=child_data["grade"],
                include_in_stats=True,
                created_at=datetime.utcnow()
            )
            db.session.add(child)
        
        db.session.commit()
        print(f"✅ {len(children_data)}명의 아동 데이터 생성 완료")
        
        # 포인트 데이터 생성 (최근 30일)
        print("📊 포인트 데이터 생성 중...")
        
        children = Child.query.all()
        today = datetime.utcnow().date()
        
        for child in children:
            for i in range(30):  # 최근 30일
                date = today - timedelta(days=i)
                
                # 랜덤 포인트 생성 (0-200점)
                korean_points = random.choice([0, 50, 100, 150, 200])
                math_points = random.choice([0, 50, 100, 150, 200])
                ssen_points = random.choice([0, 50, 100, 150, 200])
                reading_points = random.choice([0, 50, 100, 150, 200])
                piano_points = random.choice([0, 50, 100])
                english_points = random.choice([0, 50, 100])
                advanced_math_points = random.choice([0, 50, 100])
                writing_points = random.choice([0, 50, 100])
                manual_points = 0
                
                total_points = (korean_points + math_points + ssen_points + 
                              reading_points + piano_points + english_points + 
                              advanced_math_points + writing_points + manual_points)
                
                # 일부 날짜는 기록 없음 (더 현실적인 데이터)
                if random.random() > 0.3:  # 70% 확률로 기록 생성
                    daily_points = DailyPoints(
                        child_id=child.id,
                        date=date,
                        korean_points=korean_points,
                        math_points=math_points,
                        ssen_points=ssen_points,
                        reading_points=reading_points,
                        piano_points=piano_points,
                        english_points=english_points,
                        advanced_math_points=advanced_math_points,
                        writing_points=writing_points,
                        manual_points=manual_points,
                        manual_history='[]',
                        total_points=total_points,
                        created_by=1
                    )
                    db.session.add(daily_points)
        
        db.session.commit()
        print("✅ 포인트 데이터 생성 완료")
        
        # 누적 포인트 계산
        print("📈 누적 포인트 계산 중...")
        for child in children:
            total_cumulative = db.session.query(
                db.func.sum(DailyPoints.total_points)
            ).filter_by(child_id=child.id).scalar() or 0
            
            child.cumulative_points = total_cumulative
        
        db.session.commit()
        print("✅ 누적 포인트 계산 완료")
        
        print("🎉 실제 가명 시드 데이터 생성 완료!")
        print(f"📊 생성된 데이터:")
        print(f"   - 아동: {len(children)}명")
        print(f"   - 포인트 기록: {DailyPoints.query.count()}개")
        print(f"   - 학년별 분포:")
        for grade in range(1, 7):
            count = Child.query.filter_by(grade=grade).count()
            if count > 0:
                print(f"     {grade}학년: {count}명")

if __name__ == "__main__":
    create_real_pseudonyms()
