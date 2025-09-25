#!/usr/bin/env python3
"""
Step 1: 강현준의 모든 기록을 수동으로 나열하고 계산
"""

import os
import sys
from datetime import datetime

# Flask 앱 컨텍스트 설정
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app import app, db, Child, DailyPoints

def manual_calculation_ganghyunjun():
    """강현준의 모든 기록을 수동으로 나열하고 계산"""
    
    with app.app_context():
        try:
            # 강현준 아동 찾기
            child = Child.query.filter_by(name='강현준').first()
            if not child:
                print("❌ 강현준을 찾을 수 없습니다.")
                return
            
            print("="*60)
            print(f"📊 강현준 포인트 수동 계산 분석")
            print("="*60)
            print(f"아동 ID: {child.id}")
            print(f"아동 이름: {child.name}")
            print(f"DB에 저장된 누적 포인트: {child.cumulative_points}")
            print()
            
            # 모든 DailyPoints 기록 조회
            records = db.session.query(DailyPoints).filter_by(child_id=child.id).order_by(DailyPoints.date.asc()).all()
            
            print(f"📋 총 일일 기록 수: {len(records)}개")
            print("-"*60)
            
            manual_total = 0
            for i, record in enumerate(records):
                # 기본 포인트 계산
                basic_points = (
                    record.korean_points + record.math_points + record.ssen_points + 
                    record.reading_points + record.piano_points + record.english_points +
                    record.advanced_math_points + record.writing_points
                )
                
                # 수동 포인트
                manual_points = record.manual_points or 0
                
                # 계산된 총점
                calculated_total = basic_points + manual_points
                
                # 저장된 총점
                stored_total = record.total_points
                
                # 누적 계산
                manual_total += stored_total
                
                # 일치 여부 확인
                match_status = "✅" if calculated_total == stored_total else "❌"
                
                print(f"{i+1:2d}. {record.date}")
                print(f"    기본포인트: {basic_points:4d} + 수동포인트: {manual_points:4d} = 계산값: {calculated_total:4d}")
                print(f"    저장된값: {stored_total:4d} {match_status}")
                print(f"    누적계산: {manual_total:4d}")
                
                if calculated_total != stored_total:
                    print(f"    ⚠️ 불일치! 차이: {stored_total - calculated_total}")
                
                # 수동 포인트 히스토리가 있으면 표시
                if record.manual_history and record.manual_history != '[]':
                    try:
                        import json
                        history = json.loads(record.manual_history)
                        if history:
                            print(f"    수동포인트 내역:")
                            for h in history:
                                print(f"      - {h.get('subject', 'N/A')}: {h.get('points', 0)}점 ({h.get('reason', 'N/A')})")
                    except:
                        print(f"    수동포인트 내역: 파싱 오류")
                
                print()
            
            print("="*60)
            print(f"📊 최종 결과")
            print("="*60)
            print(f"수동 계산 총합: {manual_total:4d}점")
            print(f"DB 저장된 누적: {child.cumulative_points:4d}점")
            print(f"차이: {manual_total - child.cumulative_points:4d}점")
            
            if manual_total == child.cumulative_points:
                print("✅ 계산 일치!")
            else:
                print("❌ 계산 불일치!")
                print(f"   예상: {manual_total}점")
                print(f"   실제: {child.cumulative_points}점")
                print(f"   오차: {manual_total - child.cumulative_points}점")
            
            return {
                'manual_total': manual_total,
                'db_cumulative': child.cumulative_points,
                'difference': manual_total - child.cumulative_points,
                'record_count': len(records)
            }
            
        except Exception as e:
            print(f"❌ 오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

if __name__ == "__main__":
    print("🔍 Step 1: 강현준 포인트 수동 계산")
    result = manual_calculation_ganghyunjun()
    
    if result:
        print(f"\n📝 요약:")
        print(f"   기록 수: {result['record_count']}개")
        print(f"   수동 계산: {result['manual_total']}점")
        print(f"   DB 저장값: {result['db_cumulative']}점")
        print(f"   차이: {result['difference']}점")
