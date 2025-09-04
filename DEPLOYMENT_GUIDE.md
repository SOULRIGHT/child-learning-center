# 배포 가이드 (Deployment Guide) - Ver. 2.2 (2025년 9월 4일)

## 📋 개요
이 문서는 아동 학습 센터 애플리케이션의 배포 과정과 관련 명령어를 정리한 가이드입니다.

## 🆕 **최신 업데이트 (2025-09-04)**
- **완전한 백업 시스템**: 자동 일일/월간 백업 + 수동 백업 기능
- **백업 복원 시스템**: CLI 기반 안전한 데이터 복원 도구
- **Application Context 오류 해결**: 백업 시스템 안정성 확보
- **CMD 가상환경 가이드**: PowerShell 실행 정책 문제 해결

## 🚀 배포 과정

### 1. 로컬 개발 환경 설정

#### 📌 Windows CMD 환경 (권장)
```cmd
# 프로젝트 디렉토리로 이동
cd child-learning-center

# 가상환경 생성
python -m venv .venv

# 가상환경 활성화 (CMD 권장)
.venv\Scripts\activate.bat

# 또는 편리한 서버 시작 스크립트 사용
start_server.bat

# 의존성 설치
pip install -r requirements.txt
```

#### 🚫 PowerShell 실행 정책 문제 해결
```cmd
# PowerShell에서 실행 정책 오류 발생 시 CMD 사용
cmd
.venv\Scripts\activate.bat
```

### 2. 데이터베이스 초기화 및 마이그레이션
```bash
# 마이그레이션 시스템 초기화 (최초 1회만)
flask db init

# 스키마 변경사항 적용
flask db upgrade

# 기본 데이터 시드 (선택사항)
python seed_data.py
```

### 3. 로컬 테스트
```bash
# Flask 개발 서버 실행
python app.py

# 브라우저에서 접속
# http://localhost:5000
```

### 4. Git 변경사항 커밋
```bash
# 변경된 파일들 스테이징
git add .

# 커밋 메시지와 함께 커밋
git commit -m "Database migration and seeding system added"

# 원격 저장소에 푸시
git push origin main
```

### 5. Render.com 자동 배포
- GitHub 저장소에 푸시하면 Render.com에서 자동으로 배포됩니다
- 배포 URL: `https://child-learning-center.onrender.com`

## 🔄 **노트북↔컴퓨터 데이터 동기화**

### **방법 1: 데이터베이스 파일 직접 복사 (권장)**
```bash
# 1. 현재 데이터베이스 백업
copy instance\child_center.db child_center_backup.db

# 2. 다른 기기로 파일 복사
# USB, 클라우드, 네트워크 등을 통해 전송

# 3. 새 기기에서 파일 교체
copy child_center.db instance\child_center.db
```

### **방법 2: 마이그레이션 + 시드 조합**
```bash
# 1. 코드 복사
git clone [repository] 또는 파일 복사

# 2. 가상환경 설정
python -m venv .venv
.venv\Scripts\activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 데이터베이스 생성
flask db upgrade

# 5. 실제 데이터 입력
python real_seed_data.py
```

### **방법 3: 시드 스크립트로 데이터 재생성**
```bash
# 개발용 테스트 데이터 생성
python seed_data.py

# 또는 실제 운영용 데이터 입력
python real_seed_data.py
```

## 🔧 주요 변경사항

### 📅 2025-08-31 업데이트
- **CMD 가상환경 가이드**: PowerShell 실행 정책 문제 해결
- **서버 시작 스크립트**: start_server.bat 자동 실행 스크립트 추가
- **백업 시스템 안정화**: 실시간 백업 오류 해결 및 월간 백업 수정
- **복원 기능 준비**: restore_backup.py 기초 구현

### 데이터베이스 마이그레이션 시스템
- **Flask-Migrate**: 스키마 변경사항 추적 및 관리
- **마이그레이션 명령어**: `init`, `migrate`, `upgrade`, `downgrade`
- **버전 관리**: 데이터베이스 스키마 버전 추적 및 롤백

### 데이터 시드 시스템
- **`seed_data.py`**: 개발용 샘플 데이터 생성 (30명 아동)
- **`real_seed_data.py`**: 실제 아동 데이터 입력용 (대화형 CLI)
- **웹 UI**: `/settings/data`에서 데이터 시드 실행 가능

### 데이터 이식 및 동기화
- **`DATA_MIGRATION_GUIDE.md`**: 상세한 마이그레이션 가이드
- **3가지 동기화 방법**: 파일 복사, 마이그레이션+시드, 시드 재생성
- **자동 백업**: 데이터베이스 백업 및 복원 시스템

### 테스트 계정 추가
- **아이디**: `test_user`
- **비밀번호**: `test_kohi`
- **역할**: 테스트사용자

### 권한 제한 기능
- 테스트사용자는 다음 페이지에 접근 불가:
  - 설정 페이지 (`/settings`)
  - 리포트 페이지 (`/reports`)
  - 프로필 페이지 (`/profile`)
- 접근 시도 시 "권한이 없습니다" 메시지 표시

### UI 개선사항
- 포인트 페이지에서 중복된 상단 버튼 제거
- 대시보드 빠른 작업에서 포인트 입력 링크를 `/points/input/1`로 변경
- 프로필 페이지 구현 및 권한 제한 추가
- 데이터 관리 페이지 추가 (`/settings/data`)

## 📝 사용 가능한 계정들

### 개발자 계정
- **아이디**: `developer`
- **비밀번호**: `dev123`
- **권한**: 모든 기능 접근 가능

### 테스트 계정
- **아이디**: `test_user`
- **비밀번호**: `test_kohi`
- **권한**: 제한적 (설정, 리포트, 프로필 접근 불가)

### 기타 계정들
- **센터장**: `center_head` / `center123!`
- **돌봄선생님**: `care_teacher` / `care123!`
- **사회복무요원1**: `social_worker1` / `social123!`
- **사회복무요원2**: `social_worker2` / `social456!`
- **보조교사**: `assistant` / `assist123!`

## 🔍 문제 해결

### 데이터베이스 마이그레이션 문제
```bash
# 오류: "No such command 'db'"
pip install flask-migrate

# 오류: "Directory migrations already exists"
# 정상입니다. 계속 진행하세요

# 오류: "No changes in schema detected"
# 스키마가 이미 최신 상태입니다

# 마이그레이션 상태 확인
flask db current
flask db history
```

### 데이터 시드 문제
```bash
# 시드 데이터 실행 오류
python -c "from app import app, db; app.app_context().push(); print('DB 연결 확인')"

# 기존 데이터 확인
python -c "from app import app, db, Child; app.app_context().push(); print(f'아동 수: {Child.query.count()}')"
```

### 로컬 서버 문제
```bash
# 서버 강제 종료
taskkill /f /im python.exe  # Windows
pkill -f python  # macOS/Linux

# 서버 재시작
python app.py
```

### Git 충돌 해결
```bash
# 현재 상태 확인
git status

# 강제로 원격 저장소와 동기화
git reset --hard HEAD
git pull origin main

# 강제 푸시 (주의: 기존 변경사항 덮어씀)
git push origin main --force
```

### 배포 확인
- 배포 후 2-3분 대기
- `https://child-learning-center.onrender.com` 접속
- 테스트 계정으로 로그인하여 권한 제한 확인

## 💾 **백업 및 복원 시스템**

### 자동 백업 스케줄
- **일일 백업**: 매일 22:00 자동 실행
- **월간 백업**: 매월 마지막 날 23:00 자동 실행
- **실시간 백업**: 포인트 입력 시 자동 생성
- **백업 위치**: `backups/` 디렉토리

### 수동 백업 실행
```bash
# 웹 UI에서 백업 실행
# 1. 로그인 후 설정 → 데이터 관리
# 2. "백업 생성" 버튼 클릭
# 3. 개발자 권한 필요
```

### 백업 복원 (CLI 도구)
```bash
# Windows CMD에서 실행
restore_backup.bat

# 또는 직접 실행
python restore_backup.py

# 복원 과정:
# 1. 현재 DB 백업 생성
# 2. 백업 파일 목록 표시
# 3. 복원할 파일 선택
# 4. 서버 재시작 필요
```

### 백업 파일 관리
```bash
# 백업 파일 확인
dir backups\daily
dir backups\monthly
dir backups\database

# 오래된 백업 파일 정리 (수동)
# 필요에 따라 오래된 파일 삭제
```

## 📊 **데이터베이스 관리 명령어**

### 마이그레이션 관리
```bash
# 마이그레이션 초기화
flask db init

# 스키마 변경사항 추적
flask db migrate -m "변경사항 설명"

# 변경사항 적용
flask db upgrade

# 이전 버전으로 되돌리기
flask db downgrade

# 현재 상태 확인
flask db current

# 마이그레이션 히스토리
flask db history
```

### 데이터 시드
```bash
# 개발용 시드 데이터
python seed_data.py

# 실제 운영용 시드 데이터
python real_seed_data.py

# 테스트용 아동 데이터
python create_children.py
```

## 📞 지원

문제가 발생하면 다음을 확인하세요:
1. 로컬에서 정상 작동하는지 확인
2. 데이터베이스 마이그레이션이 성공했는지 확인
3. Git 커밋이 성공했는지 확인
4. Render.com 대시보드에서 배포 상태 확인
5. 브라우저 캐시 삭제 후 재시도
6. `DATA_MIGRATION_GUIDE.md` 문서 참조

## 📚 **관련 문서**

- **`README.md`**: 프로젝트 개요 및 설치 가이드
- **`DATA_MIGRATION_GUIDE.md`**: 데이터 마이그레이션 상세 가이드
- **`PRD.md`**: 제품 요구사항 정의서
- **`requirements.txt`**: Python 의존성 목록

---

**마지막 업데이트**: 2025년 8월 31일  
**버전**: 2.1 (백업 시스템 안정화 및 CMD 환경 지원)  
**작성자**: 개발팀 