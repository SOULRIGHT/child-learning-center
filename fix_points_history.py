#!/usr/bin/env python3
"""
PointsHistory 테이블 컬럼 추가 스크립트
SQLite와 PostgreSQL 모두 지원
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

def get_database_url():
    """환경변수에서 데이터베이스 URL 가져오기"""
    if 'DATABASE_URL' in os.environ:
        return os.environ['DATABASE_URL']
    else:
        # SQLite 기본값 (instance 폴더)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, 'instance', 'child_center.db')
        return f'sqlite:///{db_path}'

def add_columns_to_points_history():
    """PointsHistory 테이블에 누락된 컬럼들 추가"""
    
    db_url = get_database_url()
    print(f"🔗 데이터베이스 연결: {db_url}")
    
    # SQLite와 PostgreSQL 구분
    is_sqlite = 'sqlite' in db_url.lower()
    is_postgres = 'postgresql' in db_url.lower() or 'postgres' in db_url.lower()
    
    engine = create_engine(db_url)
    
    # 추가할 컬럼들
    columns_to_add = [
        ('old_piano_points', 'INTEGER DEFAULT 0'),
        ('old_english_points', 'INTEGER DEFAULT 0'),
        ('old_advanced_math_points', 'INTEGER DEFAULT 0'),
        ('old_writing_points', 'INTEGER DEFAULT 0'),
        ('new_piano_points', 'INTEGER DEFAULT 0'),
        ('new_english_points', 'INTEGER DEFAULT 0'),
        ('new_advanced_math_points', 'INTEGER DEFAULT 0'),
        ('new_writing_points', 'INTEGER DEFAULT 0'),
    ]
    
    with engine.connect() as conn:
        try:
            # 트랜잭션 시작
            trans = conn.begin()
            
            for column_name, column_type in columns_to_add:
                try:
                    if is_sqlite:
                        # SQLite: ALTER TABLE ADD COLUMN
                        sql = f"ALTER TABLE points_history ADD COLUMN {column_name} {column_type}"
                    elif is_postgres:
                        # PostgreSQL: ALTER TABLE ADD COLUMN IF NOT EXISTS
                        sql = f"ALTER TABLE points_history ADD COLUMN IF NOT EXISTS {column_name} {column_type}"
                    else:
                        print(f"❌ 지원하지 않는 데이터베이스 타입: {db_url}")
                        return False
                    
                    print(f"➕ 컬럼 추가: {column_name}")
                    conn.execute(text(sql))
                    
                except OperationalError as e:
                    if 'already exists' in str(e).lower() or 'duplicate column name' in str(e).lower():
                        print(f"⚠️ 컬럼 {column_name} 이미 존재함")
                    else:
                        print(f"❌ 컬럼 {column_name} 추가 실패: {e}")
                        trans.rollback()
                        return False
            
            # 트랜잭션 커밋
            trans.commit()
            print("✅ 모든 컬럼 추가 완료!")
            return True
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            trans.rollback()
            return False

def check_existing_columns():
    """기존 컬럼 확인"""
    db_url = get_database_url()
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        try:
            if 'sqlite' in db_url.lower():
                # SQLite: PRAGMA table_info
                result = conn.execute(text("PRAGMA table_info(points_history)"))
                columns = [row[1] for row in result.fetchall()]
            else:
                # PostgreSQL: information_schema
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'points_history'
                """))
                columns = [row[0] for row in result.fetchall()]
            
            print("📋 현재 points_history 테이블 컬럼들:")
            for col in sorted(columns):
                print(f"  - {col}")
            
            return columns
            
        except Exception as e:
            print(f"❌ 컬럼 확인 실패: {e}")
            return []

if __name__ == "__main__":
    print("🔧 PointsHistory 테이블 컬럼 추가 스크립트")
    print("=" * 50)
    
    # 1. 기존 컬럼 확인
    print("\n1️⃣ 기존 컬럼 확인...")
    existing_columns = check_existing_columns()
    
    # 2. 컬럼 추가
    print("\n2️⃣ 누락된 컬럼 추가...")
    success = add_columns_to_points_history()
    
    if success:
        print("\n3️⃣ 최종 확인...")
        final_columns = check_existing_columns()
        
        # 새로 추가된 컬럼 확인
        new_columns = set(final_columns) - set(existing_columns)
        if new_columns:
            print(f"\n✅ 새로 추가된 컬럼: {', '.join(sorted(new_columns))}")
        else:
            print("\n✅ 모든 컬럼이 이미 존재합니다.")
        
        print("\n🎉 작업 완료! 이제 포인트 입력이 정상 작동할 것입니다.")
    else:
        print("\n❌ 작업 실패. 로그를 확인해주세요.")
        sys.exit(1)
