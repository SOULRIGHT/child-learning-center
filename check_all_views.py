#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Child, DailyPoints
from datetime import datetime, timedelta, date

def check_all_system_views():
    """모든 시스템 뷰에서 포인트 반영 확인"""
    with app.app_context():
        print("🔍 전체 시스템 포인트 반영 검증")
        print("=" * 60)
        
        # 강서진 아동 찾기
        gangseo = Child.query.filter_by(name='강서진').first()
        if not gangseo:
            print("❌ 강서진 아동을 찾을 수 없습니다!")
            return
            
        print(f"📊 강서진 (ID: {gangseo.id}) 포인트 검증")
        print("-" * 40)
        
        # 1. 누적 포인트 확인
        print(f"1. 누적 포인트: {gangseo.cumulative_points}점")
        
        # 2. 최신 일일 포인트 확인  
        latest_record = DailyPoints.query.filter_by(child_id=gangseo.id).order_by(DailyPoints.date.desc()).first()
        if latest_record:
            print(f"2. 최신 일일 포인트 ({latest_record.date}): {latest_record.total_points}점")
            print(f"   - 기존4과목: 국어{latest_record.korean_points} + 수학{latest_record.math_points} + 쎈수학{latest_record.ssen_points} + 독서{latest_record.reading_points} = {latest_record.korean_points + latest_record.math_points + latest_record.ssen_points + latest_record.reading_points}")
            print(f"   - 신규4과목: 피아노{latest_record.piano_points} + 영어{latest_record.english_points} + 고학년수학{latest_record.advanced_math_points} + 쓰기{latest_record.writing_points} = {latest_record.piano_points + latest_record.english_points + latest_record.advanced_math_points + latest_record.writing_points}")
        
        # 3. 전체 기록 합계 재계산
        all_records = DailyPoints.query.filter_by(child_id=gangseo.id).all()
        calculated_total = sum(record.total_points for record in all_records)
        print(f"3. 계산된 총 누적: {calculated_total}점 (전체 {len(all_records)}개 기록)")
        
        # 4. 누적 포인트 일치 여부
        if gangseo.cumulative_points == calculated_total:
            print("✅ 누적 포인트 일치!")
        else:
            print(f"❌ 누적 포인트 불일치! DB:{gangseo.cumulative_points} vs 계산:{calculated_total}")
        
        print("\n" + "=" * 60)
        
        # 5. 다른 주요 아동들도 샘플 체크
        print("👥 다른 아동들 샘플 검증:")
        print("-" * 30)
        
        other_children = Child.query.filter(Child.name != '강서진').limit(5).all()
        for child in other_children:
            child_records = DailyPoints.query.filter_by(child_id=child.id).all()
            if child_records:
                calculated = sum(record.total_points for record in child_records)
                stored = child.cumulative_points
                status = "✅" if calculated == stored else "❌"
                
                # 최신 기록 확인
                latest = max(child_records, key=lambda x: x.date) if child_records else None
                latest_total = latest.total_points if latest else 0
                
                print(f"   {child.name}: 누적{stored}점 (계산{calculated}) {status} | 최신: {latest_total}점")
        
        print("\n" + "=" * 60)
        
        # 6. 시스템 전체 통계 (대시보드용)
        print("📈 시스템 전체 통계:")
        print("-" * 25)
        
        today = date.today()
        
        # 오늘 총 포인트
        today_records = DailyPoints.query.filter_by(date=today).all()
        today_total = sum(record.total_points for record in today_records)
        print(f"   오늘 총 포인트: {today_total}점 ({len(today_records)}명)")
        
        # 이번 주 총 포인트
        week_start = today - timedelta(days=today.weekday())
        week_records = DailyPoints.query.filter(
            DailyPoints.date >= week_start,
            DailyPoints.date <= today
        ).all()
        week_total = sum(record.total_points for record in week_records)
        print(f"   이번 주 총 포인트: {week_total}점 ({len(week_records)}개 기록)")
        
        # 전체 아동 평균
        all_children = Child.query.all()
        total_cumulative = sum(child.cumulative_points for child in all_children)
        avg_points = total_cumulative / len(all_children) if all_children else 0
        print(f"   전체 아동 평균: {avg_points:.1f}점 ({len(all_children)}명)")
        
        print("\n🎯 검증 완료!")

if __name__ == '__main__':
    check_all_system_views()

