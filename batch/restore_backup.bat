@echo off
chcp 65001 >nul
echo 🔧 백업 복원 도구
echo ================================================

if "%1"=="" (
    echo 사용법:
    echo   restore_backup.bat [백업파일명]
    echo   restore_backup.bat --list
    echo.
    echo 사용 가능한 백업 파일:
    echo ------------------------------------------------
    
    if exist "backups\database" (
        for %%f in (backups\database\*.db) do (
            echo   %%~nxf
        )
    ) else (
        echo   백업 파일이 없습니다.
    )
    goto :eof
)

if "%1"=="--list" (
    echo 사용 가능한 백업 파일:
    echo ------------------------------------------------
    if exist "backups\database" (
        for %%f in (backups\database\*.db) do (
            echo   %%~nxf
        )
    ) else (
        echo   백업 파일이 없습니다.
    )
    goto :eof
)

set BACKUP_FILE=%1
set BACKUP_PATH=backups\database\%BACKUP_FILE%
set CURRENT_DB=child_center.db

echo ⚠️  백업 파일 '%BACKUP_FILE%'에서 복원하시겠습니까?
echo    현재 데이터가 백업으로 덮어써집니다!
set /p CONFIRM="   계속하려면 'yes'를 입력하세요: "

if /i not "%CONFIRM%"=="yes" (
    echo ❌ 복원이 취소되었습니다.
    goto :eof
)

if not exist "%BACKUP_PATH%" (
    echo ❌ 백업 파일을 찾을 수 없습니다: %BACKUP_PATH%
    goto :eof
)

echo.
echo 🔄 복원 중...

REM 현재 DB 백업 (안전을 위해)
if exist "%CURRENT_DB%" (
    for /f "tokens=1-6 delims=:., " %%a in ("%time%") do set TIMESTAMP=%%a%%b%%c
    copy "%CURRENT_DB%" "child_center_safety_backup_%date:~0,4%%date:~5,2%%date:~8,2%_%TIMESTAMP%.db" >nul
    echo ✅ 현재 DB를 안전 백업했습니다.
)

REM 복원 실행
copy "%BACKUP_PATH%" "%CURRENT_DB%" >nul
if %errorlevel%==0 (
    echo ✅ 복원 완료: %BACKUP_FILE%
    echo 💡 서버를 재시작하면 변경사항이 적용됩니다.
) else (
    echo ❌ 복원에 실패했습니다.
)

pause
