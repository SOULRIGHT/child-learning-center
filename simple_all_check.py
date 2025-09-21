from app import app, db, Child, DailyPoints

print("Starting system-wide verification...")

with app.app_context():
    # 강서진 확인
    gangseo = Child.query.filter_by(name='강서진').first()
    if gangseo:
        print(f"강서진 누적포인트: {gangseo.cumulative_points}")
        
        # 최신 기록
        latest = DailyPoints.query.filter_by(child_id=gangseo.id).order_by(DailyPoints.date.desc()).first()
        if latest:
            print(f"최신 기록 ({latest.date}): {latest.total_points}점")
            calc = latest.korean_points + latest.math_points + latest.ssen_points + latest.reading_points + latest.piano_points + latest.english_points + latest.advanced_math_points + latest.writing_points + latest.manual_points
            print(f"계산값: {calc}")
            
            if latest.total_points == 1400:
                print("✅ 1400점 정상!")
            else:
                print(f"❌ {latest.total_points}점으로 표시됨")
        
        # 전체 합계 확인
        all_records = DailyPoints.query.filter_by(child_id=gangseo.id).all()
        total = sum(r.total_points for r in all_records)
        print(f"전체 계산된 누적: {total}")
        
        if gangseo.cumulative_points == total:
            print("✅ 누적포인트 일치")
        else:
            print(f"❌ 누적포인트 불일치: DB {gangseo.cumulative_points} vs 계산 {total}")
    else:
        print("강서진을 찾을 수 없음")
        
print("Verification complete.")

