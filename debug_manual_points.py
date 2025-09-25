#!/usr/bin/env python3
"""
수동 포인트 계산 디버깅 시스템
강현준 케이스 재현 및 분석
"""

import os
import json
from datetime import datetime
from flask import Flask, request, jsonify
from app import app, db, Child, DailyPoints, PointsHistory, current_user

def debug_manual_points_detailed(child_name, points_to_add):
    """
    수동 포인트 추가 과정을 단계별로 디버깅
    """
    
    print("\n" + "="*60)
    print(f"🔍 수동 포인트 디버깅 시작: {child_name}")
    print(f"📝 추가할 포인트: {points_to_add}")
    print("="*60)
    
    with app.app_context():
        try:
            # 1. 아동 정보 확인
            child = Child.query.filter_by(name=child_name).first()
            if not child:
                print(f"❌ 아동을 찾을 수 없습니다: {child_name}")
                return
            
            print(f"👶 아동 정보:")
            print(f"   ID: {child.id}")
            print(f"   이름: {child.name}")
            print(f"   현재 누적 포인트: {child.cumulative_points}")
            
            # 2. 오늘 날짜 기록 확인
            today = datetime.now().date()
            daily_record = DailyPoints.query.filter_by(child_id=child.id, date=today).first()
            
            if daily_record:
                print(f"\n📊 오늘 기록 (수정 전):")
                print(f"   한국어: {daily_record.korean_points}")
                print(f"   수학: {daily_record.math_points}")
                print(f"   쎈수학: {daily_record.ssen_points}")
                print(f"   독서: {daily_record.reading_points}")
                print(f"   피아노: {daily_record.piano_points}")
                print(f"   영어: {daily_record.english_points}")
                print(f"   고학년수학: {daily_record.advanced_math_points}")
                print(f"   쓰기: {daily_record.writing_points}")
                print(f"   수동 포인트: {daily_record.manual_points}")
                print(f"   총 포인트: {daily_record.total_points}")
                
                # 수동 히스토리 확인
                try:
                    manual_history = json.loads(daily_record.manual_history or '[]')
                    print(f"   수동 히스토리: {len(manual_history)}개 항목")
                    for i, item in enumerate(manual_history):
                        print(f"     {i+1}. {item.get('subject')}: {item.get('points')}점 ({item.get('reason')})")
                except Exception as e:
                    print(f"   ⚠️ 수동 히스토리 파싱 오류: {e}")
                    manual_history = []
            else:
                print(f"\n📊 오늘 기록이 없음 - 새로 생성됨")
                daily_record = DailyPoints(
                    child_id=child.id,
                    date=today,
                    korean_points=0,
                    math_points=0,
                    ssen_points=0,
                    reading_points=0,
                    piano_points=0,
                    english_points=0,
                    advanced_math_points=0,
                    writing_points=0,
                    manual_points=0,
                    manual_history='[]',
                    total_points=0,
                    created_by=1  # 테스트용
                )
                db.session.add(daily_record)
                manual_history = []
            
            # 3. 수동 포인트 추가 과정 시뮬레이션
            print(f"\n🔧 수동 포인트 추가 과정:")
            
            # 히스토리에 새 항목 추가
            new_history_item = {
                'id': len(manual_history) + 1,
                'subject': '디버그테스트',
                'points': points_to_add,
                'reason': f'디버깅 테스트 ({points_to_add}점)',
                'created_by': 1,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            manual_history.append(new_history_item)
            
            # 수동 포인트 총합 계산
            manual_total_old = daily_record.manual_points
            manual_total_new = sum(item['points'] for item in manual_history)
            
            print(f"   기존 수동 포인트: {manual_total_old}")
            print(f"   새 수동 포인트 총합: {manual_total_new}")
            print(f"   차이: {manual_total_new - manual_total_old}")
            
            # 기본 포인트 총합 계산
            basic_points = (
                daily_record.korean_points + daily_record.math_points + 
                daily_record.ssen_points + daily_record.reading_points +
                daily_record.piano_points + daily_record.english_points +
                daily_record.advanced_math_points + daily_record.writing_points
            )
            
            print(f"   기본 포인트 총합: {basic_points}")
            
            # total_points 계산 (수정 전)
            total_points_old = daily_record.total_points
            total_points_new = basic_points + manual_total_new
            
            print(f"   기존 total_points: {total_points_old}")
            print(f"   새 total_points: {total_points_new}")
            print(f"   total_points 차이: {total_points_new - total_points_old}")
            
            # 4. DB 업데이트 수행
            print(f"\n💾 데이터베이스 업데이트:")
            
            # manual_history 업데이트
            daily_record.manual_history = json.dumps(manual_history, ensure_ascii=False)
            daily_record.manual_points = manual_total_new
            daily_record.total_points = total_points_new
            
            print(f"   ✅ daily_record 업데이트 완료")
            
            # 5. 누적 포인트 재계산
            print(f"\n🧮 누적 포인트 계산:")
            
            # 현재 누적 포인트
            cumulative_old = child.cumulative_points
            print(f"   현재 누적 포인트: {cumulative_old}")
            
            # 모든 일일 포인트 합계 재계산 (수정된 값 포함)
            db.session.flush()  # 현재 변경사항을 DB에 반영 (커밋은 안함)
            
            calculated_cumulative = db.session.query(
                db.func.sum(DailyPoints.total_points)
            ).filter_by(child_id=child.id).scalar() or 0
            
            print(f"   계산된 누적 포인트: {calculated_cumulative}")
            print(f"   누적 포인트 차이: {calculated_cumulative - cumulative_old}")
            
            # child.cumulative_points 업데이트
            child.cumulative_points = calculated_cumulative
            
            print(f"   ✅ child.cumulative_points 업데이트 완료")
            
            # 6. 최종 검증
            print(f"\n✅ 최종 결과:")
            print(f"   예상 누적 포인트: {cumulative_old + points_to_add}")
            print(f"   실제 누적 포인트: {calculated_cumulative}")
            print(f"   일치 여부: {'✅ 일치' if (cumulative_old + points_to_add) == calculated_cumulative else '❌ 불일치'}")
            
            # 7. 변경사항 커밋 (테스트이므로 롤백)
            print(f"\n⚠️ 테스트이므로 변경사항을 롤백합니다.")
            db.session.rollback()
            
            return {
                'expected': cumulative_old + points_to_add,
                'actual': calculated_cumulative,
                'difference': calculated_cumulative - (cumulative_old + points_to_add)
            }
            
        except Exception as e:
            print(f"❌ 오류 발생: {str(e)}")
            db.session.rollback()
            return None

def check_all_calculations(child_name):
    """
    해당 아동의 모든 계산 확인
    """
    print("\n" + "="*60)
    print(f"🔍 전체 계산 검증: {child_name}")
    print("="*60)
    
    with app.app_context():
        try:
            child = Child.query.filter_by(name=child_name).first()
            if not child:
                print(f"❌ 아동을 찾을 수 없습니다: {child_name}")
                return
            
            # 1. 모든 일일 기록 확인
            all_records = DailyPoints.query.filter_by(child_id=child.id).order_by(DailyPoints.date.desc()).all()
            
            print(f"📊 총 {len(all_records)}개의 일일 기록:")
            
            total_sum = 0
            for i, record in enumerate(all_records):
                basic_sum = (
                    record.korean_points + record.math_points + record.ssen_points + 
                    record.reading_points + record.piano_points + record.english_points +
                    record.advanced_math_points + record.writing_points
                )
                
                calculated_total = basic_sum + record.manual_points
                
                status = "✅" if calculated_total == record.total_points else "❌"
                
                print(f"   {i+1}. {record.date}: 기본{basic_sum} + 수동{record.manual_points} = {calculated_total} (저장된값: {record.total_points}) {status}")
                
                total_sum += record.total_points
                
                if calculated_total != record.total_points:
                    print(f"      ⚠️ 불일치 발견! 차이: {record.total_points - calculated_total}")
            
            print(f"\n🧮 누적 계산:")
            print(f"   일일 포인트 총합: {total_sum}")
            print(f"   저장된 누적 포인트: {child.cumulative_points}")
            print(f"   일치 여부: {'✅ 일치' if total_sum == child.cumulative_points else '❌ 불일치'}")
            
            if total_sum != child.cumulative_points:
                print(f"   차이: {child.cumulative_points - total_sum}")
                
        except Exception as e:
            print(f"❌ 오류 발생: {str(e)}")

def simulate_bug_scenario():
    """
    강현준 버그 시나리오 재현
    """
    print("\n" + "="*60)
    print("🐛 버그 시나리오 재현: 강현준 케이스")
    print("="*60)
    
    # 1. 현재 상태 확인
    print("1️⃣ 현재 상태 확인")
    check_all_calculations("강현준")
    
    # 2. +300 포인트 추가 시뮬레이션
    print("\n2️⃣ +300 포인트 추가 시뮬레이션")
    result_add = debug_manual_points_detailed("강현준", 300)
    
    # 3. -300 포인트 차감 시뮬레이션
    print("\n3️⃣ -300 포인트 차감 시뮬레이션")
    result_subtract = debug_manual_points_detailed("강현준", -300)
    
    # 4. 결과 분석
    print("\n" + "="*60)
    print("📊 결과 분석")
    print("="*60)
    
    if result_add and result_subtract:
        print(f"300점 추가 시:")
        print(f"  예상: {result_add['expected']}, 실제: {result_add['actual']}, 차이: {result_add['difference']}")
        
        print(f"-300점 차감 시:")
        print(f"  예상: {result_subtract['expected']}, 실제: {result_subtract['actual']}, 차이: {result_subtract['difference']}")
        
        if result_subtract['difference'] != 0:
            print(f"🚨 버그 확인! -300점 차감 시 {result_subtract['difference']}점 추가 차감됨")
        else:
            print("✅ 정상 작동 확인")

if __name__ == "__main__":
    print("🔧 수동 포인트 디버깅 시스템")
    print("1. 전체 계산 검증")
    print("2. 버그 시나리오 재현")
    print("3. 특정 포인트 추가 테스트")
    
    choice = input("\n선택하세요 (1-3): ")
    
    if choice == "1":
        child_name = input("아동 이름을 입력하세요: ")
        check_all_calculations(child_name)
    elif choice == "2":
        simulate_bug_scenario()
    elif choice == "3":
        child_name = input("아동 이름을 입력하세요: ")
        points = int(input("포인트를 입력하세요 (음수 가능): "))
        debug_manual_points_detailed(child_name, points)
    else:
        print("잘못된 선택입니다.")
