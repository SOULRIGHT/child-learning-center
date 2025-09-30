-- 성능 최적화를 위한 인덱스 추가
-- 안전하게 추가 (IF NOT EXISTS 사용)

-- 1. 날짜별 조회 최적화 (시각화, 통계 페이지)
CREATE INDEX IF NOT EXISTS idx_daily_points_date ON daily_points(date);

-- 2. 아동별 조회 최적화 (대시보드, 아동 상세)
CREATE INDEX IF NOT EXISTS idx_daily_points_child_id ON daily_points(child_id);

-- 3. 복합 인덱스 (날짜 + 아동) - 가장 효과적
CREATE INDEX IF NOT EXISTS idx_daily_points_date_child ON daily_points(date, child_id);

-- 4. 학년별 조회 최적화 (통계 페이지)
CREATE INDEX IF NOT EXISTS idx_children_grade ON children(grade);

-- 5. 통계 포함 아동 조회 최적화
CREATE INDEX IF NOT EXISTS idx_children_include_stats ON children(include_in_stats) WHERE include_in_stats = true;

-- 6. 포인트 히스토리 조회 최적화
CREATE INDEX IF NOT EXISTS idx_points_history_child_date ON points_history(child_id, date);

-- 7. 사용자 이메일 조회 최적화 (Firebase 로그인)
CREATE INDEX IF NOT EXISTS idx_user_email ON "user"(email);
CREATE INDEX IF NOT EXISTS idx_user_firebase_uid ON "user"(firebase_uid);

-- 인덱스 생성 완료 메시지
SELECT '인덱스 생성 완료 - 성능 최적화 적용됨' as status;
