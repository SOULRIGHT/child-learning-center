from app import app, db, Child, DailyPoints

with app.app_context():
    gangseo = Child.query.filter_by(name='강서진').first()
    if gangseo:
        print(f"DB에 저장된 누적포인트: {gangseo.cumulative_points}")
        print()
        
        # 모든 기록을 날짜순으로 가져오기
        all_records = DailyPoints.query.filter_by(child_id=gangseo.id).order_by(DailyPoints.date.asc()).all()
        
        print(f"전체 기록 개수: {len(all_records)}개")
        print("=" * 60)
        
        total_sum = 0
        for i, record in enumerate(all_records, 1):
            total_sum += record.total_points
            print(f"{i:2d}. {record.date} : {record.total_points:4d}점 (누적: {total_sum:5d}점)")
        
        print("=" * 60)
        print(f"처음부터 끝까지 전체 합계: {total_sum}점")
        print(f"DB 저장된 누적포인트:     {gangseo.cumulative_points}점")
        print(f"차이:                    {total_sum - gangseo.cumulative_points}점")
        
        if total_sum == gangseo.cumulative_points:
            print("✅ 정확히 일치!")
        else:
            print("❌ 불일치!")
            
        # 1400점 기록이 있는지 확인
        records_1400 = [r for r in all_records if r.total_points == 1400]
        if records_1400:
            print(f"\n1400점 기록: {len(records_1400)}개 발견")
            for r in records_1400:
                print(f"  - {r.date}: {r.total_points}점")
        else:
            print("\n1400점 기록 없음")
            
    else:
        print("강서진을 찾을 수 없음")

