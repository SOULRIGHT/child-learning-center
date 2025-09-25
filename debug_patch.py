#!/usr/bin/env python3
"""
실제 add_manual_points 함수에 디버깅 로그를 추가하는 패치
"""

def add_debug_logs_to_manual_points():
    """
    app.py의 add_manual_points 함수에 디버깅 로그를 추가
    """
    
    debug_code = '''
    # 🔍 디버깅 로그 시작
    print("\\n" + "="*50)
    print(f"🔍 수동 포인트 디버깅: {child.name}")
    print(f"📝 입력 포인트: {points}")
    print(f"📝 과목: {subject}")
    print(f"📝 사유: {reason}")
    print("="*50)
    
    # 수정 전 상태 로깅
    print(f"📊 수정 전 상태:")
    print(f"   manual_points: {daily_record.manual_points}")
    print(f"   total_points: {daily_record.total_points}")
    print(f"   cumulative_points: {child.cumulative_points}")
    
    try:
        old_history = json.loads(daily_record.manual_history or '[]')
        print(f"   기존 manual_history: {len(old_history)}개 항목")
        for idx, item in enumerate(old_history):
            print(f"     {idx+1}. {item.get('subject', 'N/A')}: {item.get('points', 0)}점")
    except:
        print(f"   manual_history 파싱 오류")
    '''
    
    middle_debug_code = '''
    # 수정 중간 상태 로깅
    print(f"\\n🔧 계산 과정:")
    print(f"   새 manual_total: {manual_total}")
    print(f"   기본 포인트 합: {daily_record.korean_points + daily_record.math_points + daily_record.ssen_points + daily_record.reading_points + daily_record.piano_points + daily_record.english_points + daily_record.advanced_math_points + daily_record.writing_points}")
    '''
    
    final_debug_code = '''
    # 수정 후 상태 로깅
    print(f"\\n📊 수정 후 상태:")
    print(f"   새 manual_points: {daily_record.manual_points}")
    print(f"   새 total_points: {daily_record.total_points}")
    
    # DB 커밋 전 계산 검증
    db.session.flush()
    calculated_cumulative = db.session.query(db.func.sum(DailyPoints.total_points)).filter_by(child_id=child_id).scalar() or 0
    print(f"   계산된 누적: {calculated_cumulative}")
    print(f"   기존 누적: {child.cumulative_points}")
    print(f"   예상 누적: {child.cumulative_points + points}")
    
    # 최종 검증
    if calculated_cumulative == child.cumulative_points + points:
        print("   ✅ 계산 정상")
    else:
        print(f"   ❌ 계산 오류! 차이: {calculated_cumulative - (child.cumulative_points + points)}")
    
    print("="*50 + "\\n")
    '''
    
    return debug_code, middle_debug_code, final_debug_code

# 사용 예시를 위한 완전한 디버깅 버전 함수
def create_debug_manual_points_function():
    """
    완전한 디버깅 버전의 add_manual_points 함수 생성
    """
    
    function_code = '''
@app.route('/api/manual-points-debug', methods=['POST'])
@login_required
def add_manual_points_debug():
    """수동 포인트 추가 API - 디버깅 버전"""
    try:
        data = request.get_json()
        child_id = data.get('child_id')
        subject = data.get('subject')
        points = data.get('points')
        reason = data.get('reason')
        
        # 입력 검증
        if not all([child_id, subject, points is not None, reason]):
            return jsonify({'success': False, 'error': '모든 필드를 입력해주세요.'})
        
        # 아동 확인
        child = Child.query.get(child_id)
        if not child:
            return jsonify({'success': False, 'error': '아동을 찾을 수 없습니다.'})
        
        # 🔍 디버깅 로그 시작
        print("\\n" + "="*50)
        print(f"🔍 수동 포인트 디버깅: {child.name}")
        print(f"📝 입력 포인트: {points}")
        print(f"📝 과목: {subject}")
        print(f"📝 사유: {reason}")
        print("="*50)
        
        # 오늘 날짜의 기록 찾기 또는 생성
        today = datetime.now().date()
        daily_record = DailyPoints.query.filter_by(child_id=child_id, date=today).first()
        
        if not daily_record:
            print("📝 새 일일 기록 생성")
            daily_record = DailyPoints(
                child_id=child_id,
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
                created_by=current_user.id
            )
            db.session.add(daily_record)
        
        # 수정 전 상태 로깅
        print(f"📊 수정 전 상태:")
        print(f"   manual_points: {daily_record.manual_points}")
        print(f"   total_points: {daily_record.total_points}")
        print(f"   cumulative_points: {child.cumulative_points}")
        
        # 수동 히스토리 업데이트
        import json
        try:
            history = json.loads(daily_record.manual_history) if daily_record.manual_history else []
            print(f"   기존 manual_history: {len(history)}개 항목")
            for idx, item in enumerate(history):
                print(f"     {idx+1}. {item.get('subject', 'N/A')}: {item.get('points', 0)}점")
        except Exception as e:
            print(f"   manual_history 파싱 오류: {e}")
            history = []
        
        # 새 히스토리 항목 추가
        new_history_item = {
            'id': len(history) + 1,
            'subject': subject,
            'points': points,
            'reason': reason,
            'created_by': current_user.id,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        history.append(new_history_item)
        
        # 수동 포인트 총합 계산
        manual_total_old = daily_record.manual_points
        manual_total = sum(item['points'] for item in history)
        
        print(f"\\n🔧 계산 과정:")
        print(f"   기존 manual_total: {manual_total_old}")
        print(f"   새 manual_total: {manual_total}")
        print(f"   차이: {manual_total - manual_total_old}")
        
        basic_points = (
            daily_record.korean_points + daily_record.math_points + 
            daily_record.ssen_points + daily_record.reading_points +
            daily_record.piano_points + daily_record.english_points +
            daily_record.advanced_math_points + daily_record.writing_points
        )
        print(f"   기본 포인트 합: {basic_points}")
        
        # 기록 업데이트
        daily_record.manual_history = json.dumps(history, ensure_ascii=False)
        daily_record.manual_points = manual_total
        
        # 총 포인트 재계산
        total_points_old = daily_record.total_points
        daily_record.total_points = (
            daily_record.korean_points + daily_record.math_points + 
            daily_record.ssen_points + daily_record.reading_points +
            daily_record.piano_points + daily_record.english_points +
            daily_record.advanced_math_points + daily_record.writing_points +
            daily_record.manual_points
        )
        
        print(f"   기존 total_points: {total_points_old}")
        print(f"   새 total_points: {daily_record.total_points}")
        print(f"   total_points 차이: {daily_record.total_points - total_points_old}")
        
        # 변경 타입 결정
        change_type = '추가' if points > 0 else '차감'
        
        # PointsHistory 기록
        points_history = PointsHistory(
            child_id=child_id,
            date=today,
            old_korean_points=0, old_math_points=0, old_ssen_points=0, old_reading_points=0, 
            old_total_points=total_points_old,
            new_korean_points=0, new_math_points=0, new_ssen_points=0, new_reading_points=0, 
            new_total_points=daily_record.total_points,
            change_type=change_type,
            changed_by=current_user.id,
            change_reason=f'수동 {change_type}: {subject} ({reason})'
        )
        db.session.add(points_history)
        
        # 누적 포인트 자동 업데이트 전 상태
        cumulative_old = child.cumulative_points
        print(f"\\n🧮 누적 포인트 계산:")
        print(f"   업데이트 전 cumulative: {cumulative_old}")
        print(f"   예상 cumulative: {cumulative_old + points}")
        
        # 누적 포인트 자동 업데이트
        update_cumulative_points(child_id, commit=False)
        
        # DB 커밋 전 최종 검증
        db.session.flush()
        calculated_cumulative = db.session.query(db.func.sum(DailyPoints.total_points)).filter_by(child_id=child_id).scalar() or 0
        print(f"   계산된 cumulative: {calculated_cumulative}")
        print(f"   실제 cumulative: {child.cumulative_points}")
        
        # 최종 검증
        expected_cumulative = cumulative_old + points
        if calculated_cumulative == expected_cumulative:
            print("   ✅ 계산 정상")
        else:
            print(f"   ❌ 계산 오류! 차이: {calculated_cumulative - expected_cumulative}")
            print(f"      예상: {expected_cumulative}")
            print(f"      실제: {calculated_cumulative}")
            print(f"      오차: {calculated_cumulative - expected_cumulative}")
        
        print("="*50 + "\\n")
        
        db.session.commit()
        
        # 실시간 백업 호출
        try:
            from backup_system import realtime_backup
            backup_success = realtime_backup(child_id, f'manual_{change_type}')
            if not backup_success:
                print("⚠️ 실시간 백업 실패 (포인트 입력은 성공)")
        except Exception as backup_error:
            print(f"백업 실패: {backup_error}")
        
        return jsonify({
            'success': True, 
            'message': f'수동 포인트가 {change_type}되었습니다.',
            'debug_info': {
                'expected_cumulative': expected_cumulative,
                'actual_cumulative': calculated_cumulative,
                'difference': calculated_cumulative - expected_cumulative
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ 수동 포인트 추가 오류: {str(e)}")
        return jsonify({'success': False, 'error': f'처리 중 오류가 발생했습니다: {str(e)}'})
'''
    
    return function_code

if __name__ == "__main__":
    print("디버깅 패치 코드 생성 완료")
    print("1. debug_manual_points.py - 독립적인 디버깅 스크립트")
    print("2. add_manual_points_debug() - 디버깅 버전 API 엔드포인트")
    '''
    
    return function_code
