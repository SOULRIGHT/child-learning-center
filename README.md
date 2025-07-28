# 아동 학습 센터 관리 시스템

아동들의 학습 진도와 포인트를 관리하는 웹 애플리케이션입니다.

## 주요 기능

- **아동 관리**: 아동 정보 등록, 수정, 삭제
- **학습 기록**: 국어, 수학, 쎈수학, 독서 점수 입력
- **포인트 시스템**: 일일 포인트 입력 및 관리
- **통계 분석**: 학년별, 과목별 진도 비교
- **리포트 생성**: 개별/학년별/기간별 리포트
- **시각화**: 차트를 통한 데이터 시각화

## 배포 방법

### Render.com 배포 (추천)

1. **GitHub에 코드 업로드**
   ```bash
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

2. **Render.com에서 배포**
   - [Render.com](https://render.com) 가입
   - "New Web Service" 클릭
   - GitHub 저장소 연결
   - 자동 배포 완료

### 로컬 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# 서버 실행
python app.py
```

## 기본 계정

- **센터장**: center_head / center123!
- **돌봄선생님**: care_teacher / care123!
- **사회복무요원1**: social_worker1 / social123!
- **사회복무요원2**: social_worker2 / social456!
- **보조교사**: assistant / assist123!

## 기술 스택

- **Backend**: Flask, SQLAlchemy
- **Frontend**: HTML, CSS, JavaScript, Chart.js
- **Database**: SQLite (개발) / PostgreSQL (배포)
- **Deployment**: Render.com 