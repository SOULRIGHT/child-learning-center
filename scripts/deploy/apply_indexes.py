#!/usr/bin/env python3
"""
인덱스 추가 스크립트
안전하게 데이터베이스에 인덱스를 추가합니다.
"""

import os
import sys
from sqlalchemy import text
from app import app, db

def add_indexes():
    """인덱스를 안전하게 추가"""
    try:
        with app.app_context():
            print("🔧 인덱스 추가 시작...")
            
            # 인덱스 SQL 파일 읽기
            with open('add_indexes.sql', 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # SQL 문장들을 분리 (세미콜론 기준)
            sql_statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
            
            for i, sql in enumerate(sql_statements, 1):
                if sql.upper().startswith('CREATE INDEX'):
                    print(f"  {i}. {sql[:50]}...")
                    db.session.execute(text(sql))
                elif sql.upper().startswith('SELECT'):
                    # 상태 확인 쿼리
                    result = db.session.execute(text(sql)).fetchone()
                    print(f"  ✅ {result[0] if result else '완료'}")
            
            # 변경사항 커밋
            db.session.commit()
            print("🎉 인덱스 추가 완료!")
            print("📊 성능 향상이 즉시 적용됩니다.")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        db.session.rollback()
        sys.exit(1)

if __name__ == "__main__":
    add_indexes()
