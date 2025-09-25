#!/usr/bin/env python3
"""
데이터베이스 컬럼 추가 스크립트
누락된 user 테이블 컬럼들을 추가합니다.
"""

import sqlite3
import os

def add_missing_columns():
    """누락된 컬럼들을 user 테이블에 추가"""
    
    # DB 파일 경로
    db_path = 'instance/child_center.db'
    
    if not os.path.exists(db_path):
        print(f"❌ 데이터베이스 파일을 찾을 수 없습니다: {db_path}")
        return False
    
    try:
        # DB 연결
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔄 데이터베이스 컬럼 추가 중...")
        
        # 추가할 컬럼들
        columns_to_add = [
            ('is_locked', 'BOOLEAN DEFAULT 0'),
            ('locked_until', 'DATETIME'),
            ('email', 'VARCHAR(120)'),
            ('firebase_uid', 'VARCHAR(128)')
        ]
        
        # 각 컬럼 추가
        for column_name, column_type in columns_to_add:
            try:
                sql = f'ALTER TABLE user ADD COLUMN {column_name} {column_type}'
                cursor.execute(sql)
                print(f"✅ {column_name} 컬럼 추가 완료")
            except sqlite3.OperationalError as e:
                if 'duplicate column name' in str(e).lower():
                    print(f"⚠️  {column_name} 컬럼이 이미 존재합니다")
                else:
                    print(f"❌ {column_name} 컬럼 추가 실패: {e}")
        
        # 변경사항 저장
        conn.commit()
        
        # 스키마 확인
        print("\n📋 현재 user 테이블 스키마:")
        cursor.execute("PRAGMA table_info(user)")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
        # 연결 종료
        conn.close()
        
        print("\n✅ 데이터베이스 컬럼 추가 완료!")
        print("🔧 이제 서버를 재시작하세요: python app.py")
        
        return True
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False

if __name__ == "__main__":
    print("🗄️  데이터베이스 컬럼 추가 스크립트")
    print("=" * 50)
    
    success = add_missing_columns()
    
    if success:
        print("\n🎉 성공적으로 완료되었습니다!")
    else:
        print("\n💥 실패했습니다. 다시 시도해주세요.")

