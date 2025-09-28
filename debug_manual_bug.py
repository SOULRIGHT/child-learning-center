#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app import app, db, Child, DailyPoints, PointsHistory
import json

def debug_manual_points_bug():
    """수동 포인트 버그 정확한 검증"""
    with app.app_context():
        print("🔍 수동 포인트 버그 정밀 분석")
        print("=" * 60)
        
        # 테스트할 아동 찾기
        child = Child.query.first()
        if not child:
            print("❌ 테스트할 아동이 없습니다")
            return
            
        print(f"📊 테스트 대상: {child.name}")
        
        # 오늘 기록 찾기
        from datetime import datetime
        today = datetime.now().date()
        
        record = DailyPoints.query.filter_by(child_id=child.id, date=today).first()
        if not record:
            print("❌ 오늘 포인트 기록이 없습니다")
            return
            
        print(f"📅 날짜: {record.date}")
        print(f"🎯 현재 상태:")
        print(f"  - 기존포인트: {record.korean_points + record.math_points + record.ssen_points + record.reading_points + record.piano_points + record.english_points + record.advanced_math_points + record.writing_points}")
        print(f"  - manual_points: {record.manual_points}")
        print(f"  - total_points: {record.total_points}")
        print(f"  - manual_history: {record.manual_history}")
        
        # manual_history 파싱 테스트
        try:
            history = json.loads(record.manual_history) if record.manual_history else []
            manual_calculated = sum(item.get('points', 0) for item in history if isinstance(item, dict))
            print(f"  - manual_history에서 계산: {manual_calculated}")
            
            if record.manual_points != manual_calculated:
                print(f"  ❌ 불일치 발견! DB:{record.manual_points} vs 계산:{manual_calculated}")
            else:
                print(f"  ✅ manual_points 일치")
                
        except Exception as e:
            print(f"  ❌ JSON 파싱 오류: {e}")
        
        # 실제 total_points 검증
        expected_total = (
            record.korean_points + record.math_points + 
            record.ssen_points + record.reading_points +
            record.piano_points + record.english_points +
            record.advanced_math_points + record.writing_points +
            manual_calculated
        )
        
        print(f"🧮 계산 검증:")
        print(f"  - 예상 총점: {expected_total}")
        print(f"  - 실제 총점: {record.total_points}")
        
        if expected_total != record.total_points:
            print(f"  ❌ 총점 불일치! 차이: {record.total_points - expected_total}")
        else:
            print(f"  ✅ 총점 정확")
            
        # PointsHistory 최근 기록 확인
        recent_history = PointsHistory.query.filter_by(child_id=child.id).order_by(PointsHistory.id.desc()).limit(3).all()
        
        print(f"\n📋 최근 PointsHistory:")
        for i, ph in enumerate(recent_history):
            print(f"  {i+1}. {ph.change_reason}")
            print(f"     old_total: {ph.old_total_points} → new_total: {ph.new_total_points}")
            print(f"     차이: {ph.new_total_points - ph.old_total_points}")

if __name__ == "__main__":
    debug_manual_points_bug()

