#!/usr/bin/env python3
"""
배포환경 인덱스 상태 확인 스크립트
"""

import os
import sys
from sqlalchemy import text
from app import app, db

def check_indexes():
    """인덱스 상태 확인"""
    try:
        with app.app_context():
            print("🔍 인덱스 상태 확인 중...")
            
            # 인덱스 목록 확인
            result = db.session.execute(text('''
                SELECT indexname, tablename, indexdef 
                FROM pg_indexes 
                WHERE tablename IN ('daily_points', 'children', 'user', 'points_history')
                ORDER BY tablename, indexname;
            ''')).fetchall()
            
            print(f"\n📊 현재 인덱스 상태 ({len(result)}개):")
            if not result:
                print("❌ 인덱스가 생성되지 않았습니다!")
                return False
            else:
                for row in result:
                    print(f"  ✅ {row[0]} on {row[1]}")
                print(f"\n✅ 총 {len(result)}개 인덱스 발견")
                return True
                
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False

if __name__ == "__main__":
    check_indexes()
