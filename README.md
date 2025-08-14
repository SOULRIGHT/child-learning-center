# 아동 학습 관리 시스템

아동들의 학습 진도를 추적하고 관리하는 웹 애플리케이션입니다.

## 🆕 **최근 업데이트 (2025년 8월 11일)**

### 🔄 **데이터베이스 마이그레이션 시스템 구축**
- Flask-Migrate를 통한 스키마 변경 추적
- `flask db init`, `migrate`, `upgrade` 명령어 지원
- 노트북↔컴퓨터 데이터베이스 동기화 완벽 지원

### 🌱 **데이터 시드 시스템 구축**
- `seed_basic.py`: 기본 개발/테스트용 데이터 생성 (7명 사용자 + 샘플 아동)
- `seed_quick_30.py`: 빠른 30명 아동 데이터 생성 (개발/테스트용)
- `seed_production.py`: 실제 운영용 데이터 입력 (대화형 CLI)
- 웹 UI에서 데이터 시드 실행 가능

### 💾 **데이터 이식 및 동기화**
- `DATA_MIGRATION_GUIDE.md`: 상세한 마이그레이션 가이드
- 노트북↔컴퓨터 데이터 전송 방법 (3가지 방식)
- 데이터베이스 백업 및 복원 시스템

### ⚙️ **웹 UI 데이터 관리 기능**
- `/settings/data`: 데이터 시드, 리셋, 내보내기 기능
- 아동별 누적 포인트 입력 페이지 (구현 예정)
- 데이터베이스 상태 모니터링

## 주요 기능

### 🔐 사용자 관리
- **다중 사용자 지원**: 개발자, 센터장, 돌봄교사, 사회복무요원 역할
- **권한 기반 접근 제어**: 역할별 기능 제한
- **계정 관리**: 사용자 정보 수정, 비밀번호 변경

### 👥 아동 관리
- **아동 등록/수정/삭제**: 기본 정보 관리
- **학년별 분류**: 1~6학년 아동 관리
- **통계 포함/제외**: 분석에서 제외할 아동 설정

### 📊 포인트 시스템
- **일일 포인트 입력**: 국어, 수학, 쎈수학, 독서 (200/100/0점)
- **누적 포인트 관리**: 아동별 총 누적 포인트 입력 및 관리
- **포인트 분석**: 개별 아동 및 학년별 비교
- **시각화**: 차트를 통한 포인트 트렌드 분석

### 📈 통계 및 리포트
- **학년별 통계**: 진도 현황 및 성취도
- **기간별 리포트**: 주간/월간 성과 분석
- **개별 아동 리포트**: 상세한 학습 기록

### ⚙️ 시스템 설정
- **포인트 시스템 설정**: 과목 관리, 점수 설정
- **데이터 관리**: 백업, 복원, 정리, 시드 기능
- **UI/UX 설정**: 테마, 테이블 표시 설정
- **시스템 정보**: 상태 모니터링

### 💾 데이터 백업 및 마이그레이션
- **JSON 백업**: 사용자, 아동, 포인트 기록 백업
- **데이터 복원**: 백업 파일로부터 데이터 복원
- **데이터 정리**: 오래된 기록 자동 정리
- **마이그레이션**: 스키마 변경 추적 및 적용
- **데이터 이식**: 노트북↔컴퓨터 동기화

## 기술 스택

- **Backend**: Flask, SQLAlchemy, Flask-Migrate
- **Frontend**: Bootstrap 5, Chart.js
- **Database**: SQLite (개발), PostgreSQL (배포)
- **Deployment**: Render.com

## 설치 및 실행

### 1. 저장소 클론
```bash
git clone https://github.com/SOULRIGHT/child-learning-center.git
cd child-learning-center
```

### 2. 가상환경 생성 및 활성화
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```

### 4. 데이터베이스 초기화 및 마이그레이션
```bash
# 마이그레이션 시스템 초기화
flask db init

# 스키마 변경사항 적용
flask db upgrade

# 기본 데이터 시드 (선택사항)
python seed_basic.py        # 기본 개발/테스트 데이터
python seed_quick_30.py     # 빠른 30명 아동 데이터
python seed_production.py   # 실제 운영용 데이터 입력
```

### 5. 애플리케이션 실행
```bash
python app.py
```

## 🚀 **노트북↔컴퓨터 데이터 동기화**

### **방법 1: 데이터베이스 파일 직접 복사 (권장)**
```bash
# 1. 현재 데이터베이스 백업
copy child_center.db child_center_backup.db

# 2. 다른 기기로 파일 복사
# USB, 클라우드, 네트워크 등을 통해 전송

# 3. 새 기기에서 파일 교체
copy child_center.db child_center.db
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

## 📊 **데이터 시드 시스템**

### **1. 기본 개발/테스트용 데이터 (`seed_basic.py`)**
```bash
# 웹 UI에서 실행
설정 → 데이터 관리 → 시드 데이터 실행

# 또는 터미널에서 실행
python seed_basic.py
```
**특징**: 7명 사용자 + 샘플 아동 + 학습 기록 + 포인트 데이터
**용도**: 개발 초기, 테스트 환경

### **2. 빠른 30명 아동 데이터 (`seed_quick_30.py`)**
```bash
python seed_quick_30.py
```
**특징**: 30명 아동 + 학습 기록 + 포인트 데이터 (랜덤)
**용도**: 개발/테스트 시 빠른 데이터 생성
**주의**: 기존 아동 데이터가 모두 삭제됩니다!

### **3. 실제 운영용 데이터 (`seed_production.py`)**
```bash
python seed_production.py
```
**특징**: 대화형 입력, 실제 아동 이름과 포인트 입력
**용도**: 실제 센터 운영 시 데이터 입력
**주의**: 실제 센터용, 테스트용 아님

## 배포 (Render.com)

### 1. GitHub에 푸시
```bash
git add .
git commit -m "Database migration and seeding system added"
git push origin main
```

### 2. Render.com 설정
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn app:app`

## 데이터 백업 및 마이그레이션

### 백업 실행
- 설정 → 데이터 관리 → 백업 실행
- `backups/` 폴더에 JSON 파일로 저장

### 백업 내용
- 사용자 정보 (아이디, 이름, 역할)
- 아동 정보 (이름, 학년, 통계 포함 여부)
- 포인트 기록 (일별 과목별 점수)

### 데이터 복원
- 백업 파일 업로드 후 복원 실행
- **주의**: 기존 데이터가 모두 삭제됩니다

### 마이그레이션 관리
```bash
# 스키마 변경사항 추적
flask db migrate -m "변경사항 설명"

# 변경사항을 데이터베이스에 적용
flask db upgrade

# 필요시 이전 버전으로 되돌리기
flask db downgrade
```

## 📁 **프로젝트 구조**

```
child-learning-center/
├── app.py                          # 메인 애플리케이션
├── requirements.txt                # Python 의존성
├── migrations/                     # 데이터베이스 마이그레이션
├── seed_basic.py                  # 기본 개발/테스트용 시드 데이터
├── seed_quick_30.py              # 빠른 30명 아동 데이터 생성
├── seed_production.py             # 실제 운영용 시드 데이터
├── DATA_MIGRATION_GUIDE.md        # 마이그레이션 가이드
├── templates/                      # HTML 템플릿
├── static/                         # CSS, JS, 이미지
└── instance/                       # 데이터베이스 파일
```

## 기본 계정

| 사용자명 | 역할 | 비밀번호 |
|---------|------|----------|
| developer | 개발자 | dev123 |
| center_head | 센터장 | center123! |
| care_teacher | 돌봄교사 | care123! |
| social_worker1 | 사회복무요원 | social123! |
| social_worker2 | 사회복무요원 | social456! |
| assistant | 보조교사 | assist123! |
| test_user | 테스트사용자 | test_kohi |

## 🔧 **문제 해결**

### 일반적인 오류
```bash
# 오류: "No such command 'db'"
pip install flask-migrate

# 오류: "Directory migrations already exists"
# 정상입니다. 계속 진행하세요

# 오류: "No changes in schema detected"
# 스키마가 이미 최신 상태입니다
```

### 데이터 복구
```bash
# 1. 백업 파일 확인
dir *.db

# 2. 최신 백업으로 복원
copy child_center_backup_20241201.db child_center.db

# 3. 시스템 재시작
```

## 📞 **지원 및 문의**

문제가 발생하거나 추가 도움이 필요한 경우:
1. `DATA_MIGRATION_GUIDE.md` 문서 확인
2. 시스템 로그 확인
3. 백업 파일로 복구 시도
4. 개발자에게 문의

## 라이선스

MIT License

---

**마지막 업데이트:** 2024년 12월 1일  
**버전:** 2.0 (마이그레이션 시스템 추가)  
**작성자:** 개발팀 