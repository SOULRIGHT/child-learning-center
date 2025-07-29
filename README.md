# 아동 학습 관리 시스템

아동들의 학습 진도를 추적하고 관리하는 웹 애플리케이션입니다.

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
- **포인트 분석**: 개별 아동 및 학년별 비교
- **시각화**: 차트를 통한 포인트 트렌드 분석

### 📈 통계 및 리포트
- **학년별 통계**: 진도 현황 및 성취도
- **기간별 리포트**: 주간/월간 성과 분석
- **개별 아동 리포트**: 상세한 학습 기록

### ⚙️ 시스템 설정
- **포인트 시스템 설정**: 과목 관리, 점수 설정
- **데이터 관리**: 백업, 복원, 정리 기능
- **UI/UX 설정**: 테마, 테이블 표시 설정
- **시스템 정보**: 상태 모니터링

### 💾 데이터 백업
- **JSON 백업**: 사용자, 아동, 포인트 기록 백업
- **데이터 복원**: 백업 파일로부터 데이터 복원
- **데이터 정리**: 오래된 기록 자동 정리

## 기술 스택

- **Backend**: Flask, SQLAlchemy
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
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정
`.env` 파일 생성:
```
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///child_center.db
```

### 5. 애플리케이션 실행
```bash
python app.py
```

## 배포 (Render.com)

### 1. GitHub에 푸시
```bash
git add .
git commit -m "Initial commit"
git push origin main
```

### 2. Render.com 설정
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn app:app`

## 데이터 백업

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

## 기본 계정

| 사용자명 | 역할 | 비밀번호 |
|---------|------|----------|
| developer | 개발자 | dev123 |
| center_head | 센터장 | center123 |
| teacher1 | 돌봄교사 | teacher123 |
| social1 | 사회복무요원 | social123 |
| social2 | 사회복무요원 | social123 |
| social3 | 사회복무요원 | social123 |

## 라이선스

MIT License 