@echo off
echo ========================================
echo 🚀 아동센터 학습관리 시스템 서버 시작
echo ========================================
echo.

echo 📦 가상환경 활성화 중...
call .venv\Scripts\activate.bat

echo.
echo ✅ 가상환경 활성화 완료
echo.

echo 🔍 필수 패키지 확인 중...
python -c "import schedule, pandas, openpyxl, flask; print('✅ 모든 패키지 정상')"

echo.
echo 🌐 서버 시작 중...
echo 📍 접속 주소: http://127.0.0.1:5000
echo ⏹️  종료하려면 Ctrl+C를 누르세요
echo.

python app.py

echo.
echo 👋 서버가 종료되었습니다.
pause
