#!/usr/bin/env python3
"""
배포환경 성능 테스트 스크립트
"""

import os
import sys
import time
from sqlalchemy import text
from app import app, db

def test_performance():
    """시각화 페이지 쿼리 성능 테스트"""
    try:
        with app.app_context():
            print("⏱️ 성능 테스트 시작...")
            
            # 1. 시각화 페이지 주간 데이터 쿼리
            print("\n1️⃣ 주간 데이터 쿼리 테스트:")
            start_time = time.time()
            
            result = db.session.execute(text('''
                SELECT date, SUM(total_points) as total
                FROM daily_points 
                WHERE date >= '2025-09-01' AND date <= '2025-09-30'
                GROUP BY date
                ORDER BY date;
            ''')).fetchall()
            
            end_time = time.time()
            print(f"   ⏱️ 실행 시간: {end_time - start_time:.3f}초")
            print(f"   📊 결과 개수: {len(result)}개")
            
            # 2. 월별 데이터 쿼리
            print("\n2️⃣ 월별 데이터 쿼리 테스트:")
            start_time = time.time()
            
            result = db.session.execute(text('''
                SELECT 
                    EXTRACT(MONTH FROM date) as month,
                    SUM(total_points) as total
                FROM daily_points 
                WHERE date >= '2025-01-01' AND date <= '2025-12-31'
                GROUP BY EXTRACT(MONTH FROM date)
                ORDER BY month;
            ''')).fetchall()
            
            end_time = time.time()
            print(f"   ⏱️ 실행 시간: {end_time - start_time:.3f}초")
            print(f"   📊 결과 개수: {len(result)}개")
            
            # 3. 학년별 데이터 쿼리
            print("\n3️⃣ 학년별 데이터 쿼리 테스트:")
            start_time = time.time()
            
            result = db.session.execute(text('''
                SELECT 
                    c.grade,
                    AVG(dp.total_points) as avg_points
                FROM children c
                JOIN daily_points dp ON c.id = dp.child_id
                WHERE c.include_in_stats = true
                GROUP BY c.grade
                ORDER BY c.grade;
            ''')).fetchall()
            
            end_time = time.time()
            print(f"   ⏱️ 실행 시간: {end_time - start_time:.3f}초")
            print(f"   📊 결과 개수: {len(result)}개")
            
            print("\n✅ 성능 테스트 완료!")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    test_performance()
