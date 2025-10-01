#!/usr/bin/env python3
"""
Supabase 마이그레이션 스크립트 (한국 → Oregon)
"""

import os
import sys
from sqlalchemy import create_engine, text
from app import app, db

def migrate_data():
    """기존 데이터를 새 Supabase로 마이그레이션"""
    
    # 기존 DATABASE_URL (한국)
    old_db_url = os.environ.get('DATABASE_URL')
    
    if not old_db_url:
        print("❌ 기존 DATABASE_URL을 찾을 수 없습니다.")
        return
    
    # 새 DATABASE_URL (Oregon) - 환경변수에서 가져오기
    new_db_url = input("새 Supabase DATABASE_URL을 입력하세요: ")
    
    if not new_db_url:
        print("❌ 새 DATABASE_URL을 입력해주세요.")
        return
    
    print("🔄 데이터 마이그레이션 시작...")
    
    try:
        # 기존 DB 연결
        old_engine = create_engine(old_db_url)
        
        # 새 DB 연결
        new_engine = create_engine(new_db_url)
        
        # 테이블 목록 (예약어는 따옴표로 감싸기)
        tables = ['"user"', 'child', 'daily_points', 'points_history', 'notification']
        
        for table in tables:
            print(f"📊 {table} 테이블 마이그레이션 중...")
            
            # 기존 데이터 조회
            with old_engine.connect() as conn:
                result = conn.execute(text(f"SELECT * FROM {table}"))
                rows = result.fetchall()
                columns = result.keys()
            
            # 새 DB에 삽입
            if rows:
                with new_engine.connect() as conn:
                    # 테이블 구조 확인 및 기존 데이터 삭제
                    conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                    
                    # 데이터 삽입
                    for row in rows:
                        # NULL 값 처리
                        values = []
                        for v in row:
                            if v is None:
                                values.append('NULL')
                            elif isinstance(v, str):
                                # 문자열 이스케이프
                                escaped = v.replace("'", "''")
                                values.append(f"'{escaped}'")
                            else:
                                values.append(f"'{v}'")
                        
                        values_str = ', '.join(values)
                        conn.execute(text(f"INSERT INTO {table} VALUES ({values_str})"))
                    conn.commit()
            
            print(f"✅ {table}: {len(rows)}개 레코드 마이그레이션 완료")
        
        print("🎉 마이그레이션 완료!")
        print("📝 다음 단계:")
        print("1. Render 대시보드에서 DATABASE_URL 환경변수 업데이트")
        print("2. Manual Deploy 실행")
        print("3. 성능 테스트")
        
    except Exception as e:
        print(f"❌ 마이그레이션 오류: {e}")
        return False
    
    return True

if __name__ == "__main__":
    migrate_data()