from app import app, db, Child, DailyPoints

with app.app_context():
    gangseo = Child.query.filter_by(name='강서진').first()
    if gangseo:
        print(f"현재 누적포인트: {gangseo.cumulative_points}")
        
        # 모든 기록 합계 계산
        all_records = DailyPoints.query.filter_by(child_id=gangseo.id).all()
        calculated = sum(r.total_points for r in all_records)
        print(f"계산된 총합: {calculated}")
        print(f"기록 개수: {len(all_records)}개")
        
        # 최신 기록들
        recent = DailyPoints.query.filter_by(child_id=gangseo.id).order_by(DailyPoints.date.desc()).limit(3).all()
        print("최근 3개 기록:")
        for i, r in enumerate(recent, 1):
            print(f"  {i}. {r.date}: {r.total_points}점")
        
        if gangseo.cumulative_points != calculated:
            print("❌ 누적포인트 업데이트 필요!")
            print(f"차이: {calculated - gangseo.cumulative_points}")
        else:
            print("✅ 누적포인트 정확!")
    else:
        print("강서진을 찾을 수 없음")

