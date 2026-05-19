# PostgreSQL Restore Rehearsal Checklist

## 목적
- 백업 파일(`.dump`)이 실제로 복구 가능한지 정기적으로 검증한다.
- 운영 장애 발생 시 복구 절차를 팀이 즉시 수행할 수 있도록 기준 절차를 고정한다.

## 사전 조건
- 최근 백업 파일 1개 이상
- 테스트용 PostgreSQL DB(운영 DB와 분리)
- `pg_restore` 사용 가능한 PC 환경

## 1) 리허설 준비
1. 복구 대상 백업 선택
   - 예: `postgres_2026-05-15_21-55.dump`
2. 대상 테스트 DB 준비
   - 기존 테스트 DB를 비우거나 새 DB 생성
3. 로그 기록 파일 생성
   - 예: `restore_rehearsal_YYYY-MM-DD.md`

## 2) 복구 실행
### 방법 A: DB 초기화 후 전체 복구
```bat
pg_restore --clean --if-exists --no-owner --no-privileges --dbname "postgresql://USER:PASSWORD@HOST:PORT/TEST_DB" "D:\CenterBackups\postgres\daily\postgres_YYYY-MM-DD_HH-mm.dump"
```

### 방법 B: 새 테스트 DB로 복구
```bat
pg_restore --no-owner --no-privileges --dbname "postgresql://USER:PASSWORD@HOST:PORT/NEW_TEST_DB" "D:\CenterBackups\postgres\daily\postgres_YYYY-MM-DD_HH-mm.dump"
```

## 3) 데이터 검증 체크
- [ ] 아동 수가 기대값과 일치
- [ ] 포인트 기록 수가 기대값과 일치
- [ ] 포인트 변경 이력 수가 기대값과 일치
- [ ] 주요 사용자 계정 로그인 가능
- [ ] 대시보드/아동상세/포인트입력 페이지 정상 렌더링

권장 검증 SQL:
```sql
SELECT COUNT(*) FROM child;
SELECT COUNT(*) FROM daily_points;
SELECT COUNT(*) FROM points_history;
SELECT COUNT(*) FROM "user";
```

## 4) 애플리케이션 검증
1. 테스트 서버를 복구된 테스트 DB에 연결
2. 아래 최소 시나리오 수행
   - 로그인
   - 아동 목록 조회
   - 특정 아동 상세 조회
   - 포인트 입력 1건 저장
3. 오류 로그 확인

## 5) 결과 기록 템플릿
- 리허설 일시:
- 수행자:
- 백업 파일명:
- 복구 대상 DB:
- 복구 명령:
- 테이블 건수 결과:
  - child:
  - daily_points:
  - points_history:
  - user:
- 앱 기능 점검 결과:
- 이슈/개선사항:
- 최종 판정(PASS/FAIL):

## 6) 실패 시 조치
1. 즉시 운영 반영 중단
2. 직전 백업 파일로 재시도
3. 로그(`_logs/pg_dump_*.log`) 분석
4. 원인/재발방지 항목을 Runbook에 반영

## 7) 권장 주기
- 최소 월 1회 리허설
- 구조 변경(마이그레이션/대규모 기능) 직후 추가 1회
