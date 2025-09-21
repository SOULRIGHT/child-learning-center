#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 강서진의 누적 포인트를 강제로 재계산하여 수정
import sys
sys.path.append('.')

from app import app, db, Child, DailyPoints, update_cumulative_points

with app.app_context():
    # 강서진 찾기 (2학년)
    gangseo = Child.query.filter_by(name='강서진', grade=2).first()
    
    if gangseo:
        print(f'📊 {gangseo.name} (ID: {gangseo.id}) 현재 누적 포인트: {gangseo.cumulative_points}')
        
        # 실제 일일 포인트 총합 계산
        actual_total = db.session.query(db.func.sum(DailyPoints.total_points)).filter_by(child_id=gangseo.id).scalar() or 0
        print(f'📊 실제 일일 포인트 총합: {actual_total}')
        
        if gangseo.cumulative_points != actual_total:
            print(f'⚠️ 불일치 발견! DB: {gangseo.cumulative_points}, 실제: {actual_total}')
            print('🔧 누적 포인트 자동 수정 중...')
            
            # 누적 포인트 강제 업데이트
            update_cumulative_points(gangseo.id, commit=True)
            
            # 다시 확인
            db.session.refresh(gangseo)
            print(f'✅ 수정 완료! 새 누적 포인트: {gangseo.cumulative_points}')
        else:
            print('✅ 누적 포인트가 이미 정확합니다.')
    else:
        print('❌ 강서진을 찾을 수 없습니다.')
