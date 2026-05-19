# PostgreSQL Backup Runbook

## 1. 목적
- Render PostgreSQL 데이터를 복구 가능한 형태(`.dump`)로 주기 백업한다.
- 백업 파일을 Google Drive 전용 계정에 자동 동기화하여 서비스 장애 시 복구 기준점을 확보한다.

## 2. 기본 원칙
- 앱 내부의 `settings/data` 백업은 참고용(메타/보조)이며, PostgreSQL 복구 표준은 `pg_dump` 파일이다.
- 백업 파일은 최소 2중 보관한다.
  - 1차: 로컬 백업 폴더
  - 2차: Google Drive 동기화 폴더
- 백업 저장소는 백업 전용 구글 계정으로 분리한다.

## 3. 권장 폴더 구조
- Google Drive 동기화 루트 예시: `D:\CenterBackups`
- 상세 구조:
  - `D:\CenterBackups\postgres\daily\`
  - `D:\CenterBackups\postgres\weekly\`
  - `D:\CenterBackups\postgres\manual\`
  - `D:\CenterBackups\postgres\_logs\`

운영 자동 백업은 `daily`로 저장하고, 운영자가 수동으로 보존본을 분기할 때 `weekly`/`manual`을 사용한다.

## 4. 사전 준비
1. **PostgreSQL Client 설치**
   - `pg_dump`가 포함된 PostgreSQL client 설치.
2. **환경변수 설정**
   - `DATABASE_URL`: Render PostgreSQL 접속 문자열
   - `BACKUP_ROOT`: 백업 루트 경로 (예: `D:\CenterBackups\postgres\daily`)
   - (선택) `PG_DUMP_PATH`: `pg_dump.exe` 절대경로
3. **Google Drive Desktop 설정**
   - 백업 전용 구글 계정으로 로그인
   - 동기화 경로를 `D:\CenterBackups`로 지정

## 5. 스크립트
- PowerShell: `scripts/backup/pg_dump_backup.ps1`
- BAT wrapper: `scripts/backup/pg_dump_backup.bat`

### 수동 실행 테스트
```bat
scripts\backup\pg_dump_backup.bat
```

성공 기준:
- `postgres_YYYY-MM-DD_HH-mm.dump` 파일 생성
- `_logs\pg_dump_YYYY-MM-DD.log`에 `SUCCESS` 라인 기록

## 6. 작업 스케줄러 등록 (Windows)
작업 스케줄러에서 다음과 같이 등록한다.

- 이름: `ChildCenter_Postgres_Backup`
- 트리거: 매일 21:55
- 동작: 프로그램 시작
  - 프로그램/스크립트: `cmd.exe`
  - 인수: `/c "C:\Users\apple\Desktop\child-learning-center\scripts\backup\pg_dump_backup.bat"`
- 옵션:
  - 사용자가 로그온하지 않아도 실행
  - 실패 시 다시 시도(예: 10분 간격, 3회)

## 7. 보안 운영 가이드
- 백업 전용 구글 계정에 **2단계 인증(2FA)** 활성화.
- 백업 폴더는 링크 공유를 사용하지 않는다.
- 백업 파일 다운로드/열람 권한은 운영 담당 최소 인원만 유지한다.
- `DATABASE_URL`은 스크립트/문서에 평문으로 하드코딩하지 않는다.

## 8. 장애 대응 최소 절차
1. 최신 `.dump` 파일 존재 확인
2. 로그 파일에서 최근 성공 백업 시각 확인
3. 테스트 환경에 먼저 복구 시도
4. 검증 완료 후 운영 복구 진행

자세한 복구 리허설 절차는 `docs/POSTGRES_RESTORE_REHEARSAL.md`를 따른다.
