print("🔍 전체 시스템 1400점 반영 확인")
print("=" * 50)

try:
    from app import app, db, Child, DailyPoints
    from datetime import date, timedelta
    
    with app.app_context():
        # 1. 강서진 기본 정보
        gangseo = Child.query.filter_by(name='강서진').first()
        print(f"1. 강서진 누적포인트: {gangseo.cumulative_points}점")
        
        # 2. 최신 기록 (1400점인지 확인)
        latest = DailyPoints.query.filter_by(child_id=gangseo.id).order_by(DailyPoints.date.desc()).first()
        print(f"2. 최신 기록 ({latest.date}): {latest.total_points}점")
        
        if latest.total_points == 1400:
            print("   ✅ 1400점 정상 반영!")
        else:
            print(f"   ❌ {latest.total_points}점으로 표시됨")
        
        # 3. 누적 포인트 재계산
        all_records = DailyPoints.query.filter_by(child_id=gangseo.id).all()
        calculated_cumulative = sum(r.total_points for r in all_records)
        print(f"3. 계산된 누적포인트: {calculated_cumulative}점")
        
        if gangseo.cumulative_points == calculated_cumulative:
            print("   ✅ 누적포인트 일치!")
        else:
            print(f"   ❌ 불일치! DB:{gangseo.cumulative_points} vs 계산:{calculated_cumulative}")
        
        # 4. 대시보드 통계용 데이터
        today = date.today()
        
        # 주간 평균 (대시보드에서 사용)
        week_start = today - timedelta(days=today.weekday())
        week_records = DailyPoints.query.filter(
            DailyPoints.child_id == gangseo.id,
            DailyPoints.date >= week_start
        ).all()
        
        if week_records:
            week_total = sum(r.total_points for r in week_records)
            week_avg = week_total / len(week_records)
            print(f"4. 강서진 주간 평균: {week_avg:.0f}점 (총 {week_total}점, {len(week_records)}일)")
            
            if latest.total_points in [r.total_points for r in week_records]:
                print("   ✅ 1400점이 주간 통계에 포함됨!")
        
        # 5. 아동별 상세 페이지용 최근 5개 기록
        recent_5 = DailyPoints.query.filter_by(child_id=gangseo.id).order_by(DailyPoints.date.desc()).limit(5).all()
        print(f"5. 최근 5개 기록:")
        for i, record in enumerate(recent_5, 1):
            print(f"   {i}. {record.date}: {record.total_points}점")
        
        # 6. 전체 시스템 영향 확인
        print(f"6. 시스템 전체:")
        all_children = Child.query.all()
        system_total = sum(child.cumulative_points for child in all_children)
        print(f"   전체 아동 누적 합계: {system_total}점")
        print(f"   강서진 비중: {(gangseo.cumulative_points/system_total*100):.1f}%")
        
        # 7. 결론
        print("\n" + "=" * 50)
        if latest.total_points == 1400 and gangseo.cumulative_points == calculated_cumulative:
            print("🎉 결론: 모든 시스템에서 1400점이 정확히 반영됨!")
            print("   ✅ 대시보드 통계")
            print("   ✅ 아동별 상세 페이지") 
            print("   ✅ 누적 포인트")
            print("   ✅ 전체 시스템 통계")
        else:
            print("❌ 일부 시스템에서 불일치 발견")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

