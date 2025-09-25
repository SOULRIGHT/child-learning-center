#!/usr/bin/env python3
"""
강현준의 수동 포인트 히스토리 중복 확인
"""

import os
import sys
import json
from datetime import datetime

# Flask 앱 컨텍스트 설정
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app import app, db, Child, DailyPoints

def check_manual_history():
    """강현준의 수동 포인트 히스토리 중복 확인"""
    
    with app.app_context():
        try:
            # 강현준 아동 찾기
            child = Child.query.filter_by(name='강현준').first()
            if not child:
                print("❌ 강현준을 찾을 수 없습니다.")
                return
            
            print("="*60)
            print(f"🔍 강현준 수동 포인트 히스토리 분석")
            print("="*60)
            print(f"아동 ID: {child.id}")
            print(f"아동 이름: {child.name}")
            print()
            
            # 가장 최근 기록 확인 (오늘 기록)
            today_record = DailyPoints.query.filter_by(child_id=child.id).order_by(DailyPoints.date.desc()).first()
            
            if not today_record:
                print("❌ 일일 기록을 찾을 수 없습니다.")
                return
            
            print(f"📅 최근 기록 날짜: {today_record.date}")
            print(f"📊 저장된 manual_points: {today_record.manual_points}")
            print(f"📊 저장된 total_points: {today_record.total_points}")
            print()
            
            # manual_history 파싱
            if today_record.manual_history:
                try:
                    history = json.loads(today_record.manual_history)
                    print(f"📋 수동 포인트 히스토리: 총 {len(history)}개 항목")
                    print("-"*60)
                    
                    total_manual_points = 0
                    seen_items = {}  # 중복 검출용
                    
                    for i, item in enumerate(history):
                        points = item.get('points', 0)
                        subject = item.get('subject', 'N/A')
                        reason = item.get('reason', 'N/A')
                        created_at = item.get('created_at', 'N/A')
                        item_id = item.get('id', 'N/A')
                        
                        total_manual_points += points
                        
                        print(f"{i+1:2d}. ID:{item_id} | {subject} | {points:4d}점 | {reason}")
                        print(f"     생성시간: {created_at}")
                        
                        # 중복 검출
                        key = f"{subject}_{points}_{reason}"
                        if key in seen_items:
                            print(f"     🚨 중복 발견! 이전 항목: {seen_items[key]+1}번")
                            seen_items[key + f"_dup_{i}"] = i
                        else:
                            seen_items[key] = i
                        
                        print()
                    
                    print("="*60)
                    print(f"📊 히스토리 분석 결과")
                    print("="*60)
                    print(f"히스토리 항목 수: {len(history)}개")
                    print(f"수동 계산 총합: {total_manual_points}점")
                    print(f"저장된 manual_points: {today_record.manual_points}점")
                    print(f"일치 여부: {'✅ 일치' if total_manual_points == today_record.manual_points else '❌ 불일치'}")
                    
                    if total_manual_points != today_record.manual_points:
                        print(f"차이: {today_record.manual_points - total_manual_points}점")
                    
                    print()
                    
                    # 중복 항목 요약
                    duplicates = [k for k in seen_items.keys() if k.endswith('_dup_0') or '_dup_' in k]
                    if duplicates:
                        print("🚨 중복 항목 발견!")
                        print(f"   중복 항목 수: {len(duplicates)}개")
                        print("   → 이것이 포인트 과다 차감의 원인일 가능성이 높습니다!")
                    else:
                        print("✅ 중복 항목 없음")
                    
                    # 기본 포인트 확인
                    basic_points = (
                        today_record.korean_points + today_record.math_points + 
                        today_record.ssen_points + today_record.reading_points +
                        today_record.piano_points + today_record.english_points +
                        today_record.advanced_math_points + today_record.writing_points
                    )
                    
                    expected_total = basic_points + today_record.manual_points
                    
                    print()
                    print("📊 total_points 검증:")
                    print(f"   기본 포인트: {basic_points}점")
                    print(f"   수동 포인트: {today_record.manual_points}점")
                    print(f"   계산된 총점: {expected_total}점")
                    print(f"   저장된 총점: {today_record.total_points}점")
                    print(f"   일치 여부: {'✅ 일치' if expected_total == today_record.total_points else '❌ 불일치'}")
                    
                    return {
                        'history_count': len(history),
                        'calculated_manual': total_manual_points,
                        'stored_manual': today_record.manual_points,
                        'has_duplicates': len(duplicates) > 0,
                        'duplicate_count': len(duplicates)
                    }
                    
                except json.JSONDecodeError as e:
                    print(f"❌ JSON 파싱 오류: {e}")
                    print(f"원본 데이터: {today_record.manual_history}")
                    return None
            else:
                print("📋 수동 포인트 히스토리 없음 (빈 기록)")
                return None
                
        except Exception as e:
            print(f"❌ 오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

if __name__ == "__main__":
    print("🔍 강현준 수동 포인트 히스토리 중복 검사")
    result = check_manual_history()
    
    if result:
        print(f"\n📝 요약:")
        print(f"   히스토리 항목: {result['history_count']}개")
        print(f"   계산된 수동포인트: {result['calculated_manual']}점")
        print(f"   저장된 수동포인트: {result['stored_manual']}점")
        print(f"   중복 여부: {'🚨 있음' if result['has_duplicates'] else '✅ 없음'}")
        if result['has_duplicates']:
            print(f"   중복 항목 수: {result['duplicate_count']}개")
