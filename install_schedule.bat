@echo off
REM ────────────────────────────────────────────────────────────────
REM  CSCS Daily Study — Windows Task Scheduler installer
REM  Registers a daily task at 7:00 AM that runs generate_daily.py
REM  Handles paths with spaces by writing a wrapper script first.
REM ────────────────────────────────────────────────────────────────

setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "TASK_NAME=CSCS-Daily-Study"
set "WRAPPER=%SCRIPT_DIR%_run_daily.bat"

REM Find a usable Python executable
where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
    goto :found_python
)
where python >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=python"
    goto :found_python
)
echo.
echo ERROR: Python was not found on this system.
echo Install Python from https://www.python.org/downloads/ and re-run this script.
echo.
pause
exit /b 1

:found_python
echo Found Python: %PYTHON_CMD%
echo.

REM Write a wrapper batch script that the task scheduler will invoke.
REM Wrappers avoid quoting nightmares with paths that contain spaces.
> "%WRAPPER%" echo @echo off
>>"%WRAPPER%" echo cd /d "%SCRIPT_DIR%"
>>"%WRAPPER%" echo %PYTHON_CMD% "%SCRIPT_DIR%generate_daily.py"

if not exist "%WRAPPER%" (
    echo ERROR: Could not write wrapper script at %WRAPPER%
    pause
    exit /b 1
)

echo Wrote wrapper: %WRAPPER%
echo Installing scheduled task "%TASK_NAME%" to run daily at 7:00 AM.
echo It will execute the wrapper above.
echo.

REM Remove any pre-existing version of the task first (ignore failure)
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>nul

REM /TR receives the wrapper path. The triple-quoted form is the
REM Microsoft-documented way to pass a path containing spaces to /TR.
schtasks /Create /TN "%TASK_NAME%" /TR "\"%WRAPPER%\"" /SC DAILY /ST 07:00 /F

if %errorlevel%==0 (
    echo.
    echo Task installed. It will fire daily at 7:00 AM and write today's HTML to:
    echo    %SCRIPT_DIR%daily\cscs_YYYY-MM-DD.html
    echo.
    echo To remove later, run this command in an admin terminal:
    echo    schtasks /Delete /TN "%TASK_NAME%" /F
    echo.
    echo To run the task right now without waiting until 7am:
    echo    schtasks /Run /TN "%TASK_NAME%"
) else (
    echo.
    echo Task installation failed. Try running this .bat as administrator
    echo right-click the file then choose "Run as administrator".
)
echo.
pause
