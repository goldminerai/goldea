@echo off
chcp 65001 > nul
REM 개발 에이전트 활성화 - 더블클릭해서 실행하세요.
REM agents\ (정본) -> .claude\agents\ (클로드가 읽는 활성 사본) 복사

cd /d "%~dp0"

echo.
echo  ============================================
echo   개발 에이전트 활성화
echo  ============================================
echo.

if not exist "agents" (
    echo  [실패] agents 폴더가 없습니다.
    echo         이 파일이 레포 루트에 있는지 확인하세요.
    echo.
    pause
    exit /b 1
)

if not exist ".claude\agents" mkdir ".claude\agents"

copy /Y "agents\*.md" ".claude\agents\" > nul

if errorlevel 1 (
    echo  [실패] 복사 중 오류가 발생했습니다.
    echo.
    pause
    exit /b 1
)

echo  복사 완료:
for %%f in (agents\*.md) do echo    - %%~nxf
echo.
echo  [완료] .claude\agents\ 에 배치했습니다.
echo         이 폴더에서 클로드를 실행하면 에이전트가 로드됩니다.
echo.
pause
