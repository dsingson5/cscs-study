@echo off
REM Removes the CSCS-Daily-Study scheduled task from Windows Task Scheduler.
REM GitHub Actions now handles daily regeneration, so the Windows task is no longer needed.

set TASK_NAME=CSCS-Daily-Study

echo Removing scheduled task "%TASK_NAME%"...
schtasks /Delete /TN "%TASK_NAME%" /F
if %errorlevel%==0 (
    echo.
    echo Task removed successfully.
    echo If you also want to delete the helper file, you can manually delete:
    echo    %~dp0_run_daily.bat
) else (
    echo.
    echo Task removal failed or the task was not found.
    echo If you see "ERROR: The system cannot find the file specified", the task was already gone.
)
echo.
pause
