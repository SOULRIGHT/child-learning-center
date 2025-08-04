#!/usr/bin/env python3
"""
초기 데이터 시딩 스크립트
데이터베이스에 기본 사용자와 테스트 데이터를 생성합니다.
"""

import sys
import os
from datetime import datetime, timedelta, timezone
import random

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db, User, Child, DailyPoints
from werkzeug.security import generate_password_hash

def seed_initial_data():
    """초기 데이터를 데이터베이스에 삽입합니다."""
    with app.app_context():
        try:
            print("초기 데이터 시딩을 시작합니다...")
            
            # 기존 데이터가 있는지 확인
            if User.query.first():
                print("데이터가 이미 존재합니다. 시딩을 건너뜁니다.")
                return
            
            # 1. 기본 사용자 생성
            print("기본 사용자를 생성합니다...")
            default_users = [
                {'username': 'developer', 'name': '개발자', 'role': '개발자', 'password': 'dev123'},
                {'username': 'center_head', 'name': '센터장', 'role': '센터장', 'password': 'center123!'},
                {'username': 'care_teacher', 'name': '돌봄선생님', 'role': '돌봄선생님', 'password': 'care123!'},
                {'username': 'social_worker1', 'name': '사회복무요원1', 'role': '사회복무요원', 'password': 'social123!'},
                {'username': 'social_worker2', 'name': '사회복무요원2', 'role': '사회복무요원', 'password': 'social456!'},
                {'username': 'assistant', 'name': '보조교사', 'role': '보조교사', 'password': 'assist123!'},
                {'username': 'test_user', 'name': '테스트사용자', 'role': '테스트사용자', 'password': 'test123'}
            ]
            
            for user_data in default_users:
                user = User(
                    username=user_data['username'],
                    name=user_data['name'],
                    role=user_data['role'],
                    password_hash=generate_password_hash(user_data['password'])
                )
                db.session.add(user)
            
            # 2. 테스트 아동 생성
            print("테스트 아동을 생성합니다...")
            test_children = [
                {'name': '김철수', 'grade': 3},
                {'name': '이영희', 'grade': 4},
                {'name': '박민수', 'grade': 5},
                {'name': '정수진', 'grade': 6},
                {'name': '한지우', 'grade': 3}
            ]
            
            for child_data in test_children:
                child = Child(
                    name=child_data['name'],
                    grade=child_data['grade'],
                    include_in_stats=True
                )
                db.session.add(child)
            
            # 3. 테스트 포인트 데이터 생성
            print("테스트 포인트 데이터를 생성합니다...")
            children = Child.query.all()
            users = User.query.all()
            
            # 최근 20일간의 테스트 데이터 생성
            for i in range(20):
                date = datetime.now(timezone.utc).date() - timedelta(days=i)
                
                for child in children:
                    # 랜덤 포인트 생성 (200, 100, 0 중 선택)
                    korean_points = random.choice([200, 100, 0])
                    math_points = random.choice([200, 100, 0])
                    ssen_points = random.choice([200, 100, 0])
                    reading_points = random.choice([200, 100, 0])
                    
                    total_points = korean_points + math_points + ssen_points + reading_points
                    
                    # 랜덤 사용자 선택
                    creator = random.choice(users)
                    
                    daily_points = DailyPoints(
                        child_id=child.id,
                        date=date,
                        korean_points=korean_points,
                        math_points=math_points,
                        ssen_points=ssen_points,
                        reading_points=reading_points,
                        total_points=total_points,
                        created_by=creator.id
                    )
                    db.session.add(daily_points)
            
            # 변경사항 저장
            db.session.commit()
            print("✅ 초기 데이터 시딩이 완료되었습니다!")
            print(f"생성된 사용자: {len(default_users)}명")
            print(f"생성된 아동: {len(test_children)}명")
            print(f"생성된 포인트 기록: {len(children) * 20}개")
            
        except Exception as e:
            print(f"❌ 시딩 중 오류 발생: {e}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    seed_initial_data() 