@echo off
chcp 65001 >nul
title 오늘의 말씀 - 영상 생성/업로드

cd /d "%~dp0"
cd ..
call .venv\Scripts\activate.bat
cd shorts_new

:MENU
echo ================================================
echo   오늘의 말씀 영상 생성
echo ================================================
echo   1. 오늘 날짜만 실행
echo   2. 날짜 범위 직접 입력해서 실행
echo   3. 종료
echo ================================================
set /p CHOICE=번호를 입력하세요 (1/2/3): 

if "%CHOICE%"=="1" goto TODAY
if "%CHOICE%"=="2" goto RANGE
if "%CHOICE%"=="3" goto END
echo 잘못된 입력입니다. 다시 선택해주세요.
echo.
goto MENU

:TODAY
echo.
echo 오늘 날짜로 실행합니다...
echo.
python src\main.py
goto DONE

:RANGE
echo.
set /p START_DATE=시작 날짜 입력 (예: 2026-08-05): 
set /p END_DATE=끝 날짜 입력 (예: 2026-08-11, 하루만이면 시작일과 동일하게): 
echo.
echo %START_DATE% ~ %END_DATE% 로 실행합니다...
echo.
python src\main.py --date %START_DATE% --end %END_DATE% --time_type all
goto DONE

:DONE
echo.
echo ================================================
echo   완료. 위 로그에서 오류가 없었는지 확인해주세요.
echo ================================================
pause
exit /b

:END
exit /b
