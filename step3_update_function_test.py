#!/usr/bin/env python3
"""
Step 3: update_cumulative_points 함수 직접 실행 및 분석
"""

import os
import sys
from datetime import datetime

# Flask 앱 컨텍스트 설정
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app import app, db, Child, DailyPoints, update_cumulative_points
from sqlalchemy import func

def test_update_cumulative_points():
    """update_cumulative_points 함수를 직접 실행하고 분석"""
    
    with app.app_context():
        try:
            # 강현준 아동 찾기
            child = Child.query.filter_by(name='강현준').first()
            if not child:
                print("❌ 강현준을 찾을 수 없습니다.")
                return
            
            print("="*60)
            print(f"🔧 update_cumulative_points 함수 테스트")
            print("="*60)
            print(f"아동 ID: {child.id}")
            print(f"아동 이름: {child.name}")
            print()
            
            # 1. 현재 상태 확인
            print("1️⃣ 함수 실행 전 상태:")
            print(f"   현재 cumulative_points: {child.cumulative_points}점")
            
            # 현재 일일 포인트 총합 직접 계산
            current_sum = db.session.query(func.sum(DailyPoints.total_points)).filter_by(child_id=child.id).scalar() or 0
            print(f"   일일 포인트 총합: {current_sum}점")
            print(f"   차이: {current_sum - child.cumulative_points}점")
            print()
            
            # 2. update_cumulative_points 함수 실행 (커밋 없이)
            print("2️⃣ update_cumulative_points 함수 실행:")
            print("   함수 호출: update_cumulative_points(child_id, commit=False)")
            
            # 함수 실행 전 세션 상태 저장
            original_cumulative = child.cumulative_points
            
            try:
                result = update_cumulative_points(child.id, commit=False)
                print(f"   함수 반환값: {result}점")
            except Exception as func_error:
                print(f"   ❌ 함수 실행 오류: {func_error}")
                return None
            
            # 3. 함수 실행 후 상태 확인
            print("3️⃣ 함수 실행 후 상태:")
            
            # 세션을 새로고침하여 최신 상태 확인
            db.session.refresh(child)
            print(f"   업데이트된 cumulative_points: {child.cumulative_points}점")
            print(f"   변경량: {child.cumulative_points - original_cumulative}점")
            print()
            
            # 4. 함수 내부 로직 단계별 실행
            print("4️⃣ 함수 내부 로직 재현:")
            
            # update_cumulative_points 함수 내부와 동일한 쿼리
            total_cumulative = db.session.query(
                func.sum(DailyPoints.total_points)
            ).filter_by(child_id=child.id).scalar() or 0
            
            print(f"   함수 내부 쿼리 결과: {total_cumulative}점")
            print(f"   함수가 설정한 값: {child.cumulative_points}점")
            print(f"   일치 여부: {'✅ 일치' if total_cumulative == child.cumulative_points else '❌ 불일치'}")
            print()
            
            # 5. 개별 기록 상세 분석
            print("5️⃣ 개별 기록 상세 분석:")
            records = DailyPoints.query.filter_by(child_id=child.id).order_by(DailyPoints.date.desc()).all()
            
            print(f"   총 기록 수: {len(records)}개")
            manual_sum = 0
            
            for i, record in enumerate(records[-5:]):  # 최근 5개만 표시
                manual_sum += record.total_points
                print(f"   {record.date}: {record.total_points}점")
            
            if len(records) > 5:
                remaining_sum = sum(r.total_points for r in records[:-5])
                manual_sum += remaining_sum
                print(f"   ... 이전 {len(records)-5}개 기록: {remaining_sum}점")
            
            print(f"   수동 계산 총합: {manual_sum}점")
            print()
            
            # 6. 롤백 수행
            print("6️⃣ 변경사항 롤백:")
            print("   db.session.rollback() 실행")
            db.session.rollback()
            
            # 롤백 후 상태 확인
            db.session.refresh(child)
            print(f"   롤백 후 cumulative_points: {child.cumulative_points}점")
            print(f"   원래 값으로 복원: {'✅ 성공' if child.cumulative_points == original_cumulative else '❌ 실패'}")
            print()
            
            # 7. 결과 분석
            print("="*60)
            print("📊 분석 결과")
            print("="*60)
            print(f"원래 cumulative_points:     {original_cumulative:4d}점")
            print(f"일일 포인트 총합:           {current_sum:4d}점")
            print(f"함수 계산 결과:             {total_cumulative:4d}점")
            print(f"함수 반환값:               {result:4d}점" if result is not None else "함수 반환값:               ERROR")
            print()
            
            # 불일치 원인 분석
            if original_cumulative != current_sum:
                print("🔍 불일치 원인 분석:")
                print(f"   저장된 값과 계산 값 차이: {current_sum - original_cumulative}점")
                
                if current_sum > original_cumulative:
                    print("   → 일부 포인트가 누적에 반영되지 않음")
                else:
                    print("   → 누적에 과다 계산된 포인트 존재")
            else:
                print("✅ 저장된 값과 계산 값이 일치합니다!")
            
            return {
                'original_cumulative': original_cumulative,
                'calculated_sum': current_sum,
                'function_result': result,
                'difference': current_sum - original_cumulative if current_sum and original_cumulative else 0
            }
            
        except Exception as e:
            print(f"❌ 오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return None

if __name__ == "__main__":
    print("🔍 Step 3: update_cumulative_points 함수 테스트")
    result = test_update_cumulative_points()
    
    if result:
        print(f"\n📝 요약:")
        print(f"   원래 누적: {result['original_cumulative']}점")
        print(f"   계산 총합: {result['calculated_sum']}점")
        print(f"   함수 결과: {result['function_result']}점")
        print(f"   차이: {result['difference']}점")
