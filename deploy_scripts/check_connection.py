#!/usr/bin/env python3
"""
배포환경 데이터베이스 연결 상태 확인 스크립트
"""

import os
import sys
import time
from sqlalchemy import text
from app import app, db

def check_connection():
    """데이터베이스 연결 상태 확인"""
    try:
        with app.app_context():
            print("🔗 데이터베이스 연결 상태 확인 중...")
            
            # 1. PostgreSQL 버전 확인
            result = db.session.execute(text('SELECT version();')).fetchone()
            print(f"🗄️ PostgreSQL 버전: {result[0][:50]}...")
            
            # 2. 활성 연결 수 확인
            result = db.session.execute(text('''
                SELECT count(*) as active_connections 
                FROM pg_stat_activity 
                WHERE state = 'active';
            ''')).fetchone()
            print(f"🔗 활성 연결 수: {result[0]}개")
            
            # 3. 최대 연결 수 확인
            result = db.session.execute(text('''
                SELECT setting as max_connections 
                FROM pg_settings 
                WHERE name = 'max_connections';
            ''')).fetchone()
            print(f"📊 최대 연결 수: {result[0]}개")
            
            # 4. 연결 응답 시간 테스트
            print("\n⏱️ 연결 응답 시간 테스트:")
            times = []
            for i in range(5):
                start_time = time.time()
                db.session.execute(text('SELECT 1;'))
                end_time = time.time()
                response_time = (end_time - start_time) * 1000  # ms
                times.append(response_time)
                print(f"   테스트 {i+1}: {response_time:.2f}ms")
            
            avg_time = sum(times) / len(times)
            print(f"   📊 평균 응답 시간: {avg_time:.2f}ms")
            
            # 5. 테이블 크기 확인
            print("\n📊 테이블 크기 확인:")
            result = db.session.execute(text('''
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
                FROM pg_tables 
                WHERE tablename IN ('daily_points', 'children', 'user', 'points_history')
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
            ''')).fetchall()
            
            for row in result:
                print(f"   📁 {row[1]}: {row[2]}")
            
            print("\n✅ 연결 상태 확인 완료!")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    check_connection()
