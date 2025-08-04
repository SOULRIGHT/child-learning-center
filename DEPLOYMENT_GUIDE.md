# 배포 가이드 (Deployment Guide)

## 📋 개요
이 문서는 아동 학습 센터 애플리케이션의 배포 과정과 관련 명령어를 정리한 가이드입니다.

## 🚀 배포 과정

### 1. 로컬 개발 환경 설정
```bash
# 프로젝트 디렉토리로 이동
cd child-learning-center

# 가상환경 생성 (선택사항)
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux

# 의존성 설치
pip install -r requirements.txt
```

### 2. 로컬 테스트
```bash
# Flask 개발 서버 실행
python app.py

# 브라우저에서 접속
# http://localhost:5000
```

### 3. Git 변경사항 커밋
```bash
# 변경된 파일들 스테이징
git add .

# 커밋 메시지와 함께 커밋
git commit -m "Add test user account with permission restrictions and UI improvements"

# 원격 저장소에 푸시
git push origin main
```

### 4. Render.com 자동 배포
- GitHub 저장소에 푸시하면 Render.com에서 자동으로 배포됩니다
- 배포 URL: `https://child-learning-center.onrender.com`

## 🔧 주요 변경사항

### 테스트 계정 추가
- **아이디**: `test_user`
- **비밀번호**: `test123`
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

## 📞 지원
문제가 발생하면 다음을 확인하세요:
1. 로컬에서 정상 작동하는지 확인
2. Git 커밋이 성공했는지 확인
3. Render.com 대시보드에서 배포 상태 확인
4. 브라우저 캐시 삭제 후 재시도

---
*마지막 업데이트: 2025년 7월 31일* 