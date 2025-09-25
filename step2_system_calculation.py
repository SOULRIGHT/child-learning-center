#!/usr/bin/env python3
"""
Step 2: 시스템이 사용하는 계산 과정 추적
"""

import os
import sys
from datetime import datetime

# Flask 앱 컨텍스트 설정
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app import app, db, Child, DailyPoints
from sqlalchemy import func

def system_calculation_analysis():
    """시스템이 사용하는 계산 과정을 분석"""
    
    with app.app_context():
        try:
            # 강현준 아동 찾기
            child = Child.query.filter_by(name='강현준').first()
            if not child:
                print("❌ 강현준을 찾을 수 없습니다.")
                return
            
            print("="*60)
            print(f"🔍 시스템 계산 과정 분석")
            print("="*60)
            print(f"아동 ID: {child.id}")
            print(f"아동 이름: {child.name}")
            print()
            
            # 1. 시스템이 사용하는 정확한 쿼리 (update_cumulative_points에서 사용)
            print("1️⃣ 시스템 누적 포인트 계산 쿼리:")
            print("   SELECT SUM(total_points) FROM daily_points WHERE child_id = ?")
            
            system_total = db.session.query(func.sum(DailyPoints.total_points)).filter_by(child_id=child.id).scalar()
            system_total = system_total or 0
            
            print(f"   결과: {system_total}점")
            print()
            
            # 2. 현재 DB에 저장된 누적 포인트
            print("2️⃣ DB에 저장된 누적 포인트:")
            print(f"   child.cumulative_points = {child.cumulative_points}점")
            print()
            
            # 3. 개별 계산으로 검증
            print("3️⃣ 개별 기록 SUM 계산:")
            records = DailyPoints.query.filter_by(child_id=child.id).all()
            individual_sum = sum(record.total_points for record in records)
            print(f"   Python sum() 결과: {individual_sum}점")
            print()
            
            # 4. SQL 직접 실행
            print("4️⃣ 원시 SQL 실행:")
            from sqlalchemy import text
            raw_sql_result = db.session.execute(
                text("SELECT SUM(total_points) FROM daily_points WHERE child_id = :child_id"), 
                {"child_id": child.id}
            ).scalar()
            raw_sql_result = raw_sql_result or 0
            print(f"   원시 SQL 결과: {raw_sql_result}점")
            print()
            
            # 5. 각 기록의 total_points 유효성 확인
            print("5️⃣ total_points 유효성 검사:")
            invalid_records = []
            for record in records:
                if record.total_points is None:
                    invalid_records.append(f"{record.date}: NULL")
                elif record.total_points < 0:
                    invalid_records.append(f"{record.date}: {record.total_points} (음수)")
            
            if invalid_records:
                print("   ⚠️ 유효하지 않은 기록 발견:")
                for invalid in invalid_records:
                    print(f"     - {invalid}")
            else:
                print("   ✅ 모든 total_points 값이 유효함")
            print()
            
            # 6. 결과 비교
            print("="*60)
            print("📊 계산 결과 비교")
            print("="*60)
            print(f"SQLAlchemy func.sum():  {system_total:4d}점")
            print(f"Python sum():           {individual_sum:4d}점") 
            print(f"원시 SQL:               {raw_sql_result:4d}점")
            print(f"DB 저장된 cumulative:   {child.cumulative_points:4d}점")
            print()
            
            # 7. 불일치 분석
            all_same = (system_total == individual_sum == raw_sql_result == child.cumulative_points)
            
            if all_same:
                print("✅ 모든 계산 방법이 일치합니다!")
            else:
                print("❌ 계산 방법 간 불일치 발견!")
                
                if system_total != individual_sum:
                    print(f"   SQLAlchemy vs Python: {system_total - individual_sum}점 차이")
                
                if system_total != raw_sql_result:
                    print(f"   SQLAlchemy vs 원시SQL: {system_total - raw_sql_result}점 차이")
                
                if system_total != child.cumulative_points:
                    print(f"   계산값 vs 저장값: {system_total - child.cumulative_points}점 차이")
            
            return {
                'system_total': system_total,
                'individual_sum': individual_sum,
                'raw_sql_result': raw_sql_result,
                'db_cumulative': child.cumulative_points,
                'all_match': all_same
            }
            
        except Exception as e:
            print(f"❌ 오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

if __name__ == "__main__":
    print("🔍 Step 2: 시스템 계산 과정 분석")
    result = system_calculation_analysis()
    
    if result:
        print(f"\n📝 요약:")
        print(f"   시스템 계산: {result['system_total']}점")
        print(f"   개별 합계: {result['individual_sum']}점")
        print(f"   원시 SQL: {result['raw_sql_result']}점")
        print(f"   DB 저장값: {result['db_cumulative']}점")
        print(f"   일치 여부: {'✅ 일치' if result['all_match'] else '❌ 불일치'}")
