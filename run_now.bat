@echo off
REM Quick manual run — generates today's CSCS study HTML on demand.
setlocal
set SCRIPT_DIR=%~dp0
where py >nul 2>nul && (py -3 "%SCRIPT_DIR%generate_daily.py" & goto :done)
where python >nul 2>nul && (python "%SCRIPT_DIR%generate_daily.py" & goto :done)
echo Python not found on PATH. Install from https://www.python.org/downloads/
pause
exit /b 1
:done
echo.
echo Opening today's file...
for /f "tokens=2 delims==" %%i in ('wmic os get localdatetime /value') do set DT=%%i
set YEAR=%DT:~0,4%
set MONTH=%DT:~4,2%
set DAY=%DT:~6,2%
start "" "%SCRIPT_DIR%daily\cscs_%YEAR%-%MONTH%-%DAY%.html"
